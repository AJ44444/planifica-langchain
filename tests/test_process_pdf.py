import pytest
import os
import sys
from unittest.mock import patch
import pypdfium2 as pdfium

# Ensure app package is accessible in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.parser_tool import (
    convert_pdf_bytes,
    extract_career_name,
    extract_curricular_structure_table,
    parse_curricular_areas,
)


TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_files")
REAL_CNB_FILE = os.path.join(TEST_FILES_DIR, "cnb.md")
PYPROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))


def test_pypdfium2_presence():
    """
    Verifies the presence and initialization of pypdfium2 library
    and correct configuration of 'pypdfium2' dependency in pyproject.toml.
    """
    assert hasattr(pdfium, "PdfDocument"), "pypdfium2 does not contain PdfDocument class."

    assert os.path.exists(PYPROJECT_PATH), f"pyproject.toml not found at {PYPROJECT_PATH}."
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        pyproject_content = f.read()

    assert "pypdfium2" in pyproject_content, (
        "Dependency 'pypdfium2' is not configured in pyproject.toml."
    )


def test_extract_career_name():
    """
    Verifies that career name is extracted using real cnb.md file.
    """
    assert os.path.exists(REAL_CNB_FILE), f"Real test file {REAL_CNB_FILE} does not exist."

    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    career_name = extract_career_name(content)
    assert career_name == "Bachillerato en Ciencias y Letras con Orientación en Computación", (
        f"Expected 'Bachillerato en Ciencias y Letras con Orientación en Computación', got: '{career_name}'"
    )


def test_parse_curricular_areas():
    """
    Verifies correct parsing into curricular areas by fetching PDF bytes from S3 using file_key.
    """
    assert os.path.exists(REAL_CNB_FILE), f"Real test file {REAL_CNB_FILE} does not exist."

    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    career = extract_career_name(content)
    assert career == "Bachillerato en Ciencias y Letras con Orientación en Computación"

    lines = content.splitlines()
    areas_found = [line.strip() for line in lines if "Área Curricular de" in line]

    assert len(areas_found) > 0, "No curricular areas detected in real cnb.md file."
    assert any("Comunicación y Lenguaje" in a for a in areas_found), "Missing Curricular Area of Communication and Language."
    assert any("Matemáticas" in a for a in areas_found), "Missing Curricular Area of Mathematics."
    assert any("Contabilidad" in a for a in areas_found), "Missing Curricular Area of Accounting."

    with open(REAL_CNB_FILE, "rb") as f:
        raw_bytes = f.read()

    with patch("tools.parser_tool.fetch_pdf_bytes_from_s3", return_value=raw_bytes):
        parsed_result = parse_curricular_areas.invoke({"file_key": "cnb/test_document.pdf"})
        assert len(parsed_result) > 0
        assert parsed_result[0]["clean_name"] == "Estructura Curricular"
        assert parsed_result[0]["index"] == 0
        assert "Tabla No. 1" in parsed_result[0]["content"]


def test_in_memory_pdf_processing():
    """
    Verifies that convert_pdf_bytes processes binary bytes in memory.
    """
    assert os.path.exists(REAL_CNB_FILE), f"Real test file {REAL_CNB_FILE} does not exist."

    with open(REAL_CNB_FILE, "rb") as f:
        raw_bytes = f.read()

    result = convert_pdf_bytes(raw_bytes)
    assert len(result) > 0, "Conversion result for binary PDF bytes is empty."


def test_extract_curricular_structure_table():
    """
    Verifies dynamic extraction of 'Tabla No. 1: Estructura...' from the document.
    """
    assert os.path.exists(REAL_CNB_FILE), f"Real test file {REAL_CNB_FILE} does not exist."

    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    table1_block = extract_curricular_structure_table(content)

    assert len(table1_block) > 0, "Could not extract Table No. 1 block from document."
    assert "Tabla No. 1" in table1_block or "Estructura de Bachillerato" in table1_block
    assert "Tabla No. 2" not in table1_block, "Captured block must close before Table No. 2."
    assert "Bachillerato en Ciencias y Letras" in table1_block

    sample_doc_no_table2 = """
Tabla No. 1: Estructura de Bachillerato en Ciencias y Letras con Orientación en Computación
1. Comunicación y Lenguaje
2. Matemáticas

Área Curricular de Comunicación y Lenguaje
Contenido del área...
"""
    table1_fallback = extract_curricular_structure_table(sample_doc_no_table2)
    assert "Tabla No. 1" in table1_fallback
    assert "2. Matemáticas" in table1_fallback
    assert "Área Curricular de Comunicación y Lenguaje" not in table1_fallback

    # Test returning 'Unidentified' when pattern is absent
    doc_without_table1 = "Este es un documento sin tabla de estructura curricular."
    assert extract_curricular_structure_table(doc_without_table1) == "Unidentified"


def test_slugify_and_fallback_parse():
    """
    Verifies slugify Unicode NFD normalization and alternative area extraction flow using file_key.
    """
    from tools.parser_tool import slugify

    assert slugify("Área de Comunicación y Lenguaje L 1") == "comunicacion_y_lenguaje_l1"
    assert slugify("Área de Matemáticas") == "matematicas"
    assert slugify("Área de Medio Social y Natural") == "medio_social_y_natural"

    # Simulated Primaria document with sub-areas (no career, no structure table)
    sample_primaria_md = """
Desarrollo de las Áreas
Área de Comunicación y Lenguaje
Introducción al área general...

Área de Comunicación y Lenguaje L 1
Contenido de Lengua Materna...

Área de Comunicación y Lenguaje L 2
Contenido de Segunda Lengua...

Área de Matemáticas
Contenido de Matemáticas...

Los aprendizajes esperados o estándares
Estándares finales...
"""
    raw_bytes = sample_primaria_md.encode("utf-8")

    with patch("tools.parser_tool.fetch_pdf_bytes_from_s3", return_value=raw_bytes):
        parsed = parse_curricular_areas.invoke({"file_key": "cnb/primaria.pdf"})

        assert isinstance(parsed, list)
        assert len(parsed) == 3
        names = [item["clean_name"] for item in parsed]
        assert "Comunicación y Lenguaje L 1" in names
        assert "Comunicación y Lenguaje L 2" in names
        assert "Matemáticas" in names
        assert "Comunicación y Lenguaje" not in names  # skipped generic intro header


def test_malla_curricular_basico_parse():
    """
    Verifies dynamic parsing of Ciclo Básico Malla Curricular + Grade headers using file_key.
    """
    sample_basico_md = """
Desarrollo de las Áreas
Malla curricular
 Área de Matemáticas
Primero Básico
Contenido del primer grado...

Malla curricular
 Área de Matemáticas
Segundo Básico
Contenido del segundo grado...

Malla curricular
 Área de Matemáticas
Tercero Básico
Contenido del tercer grado...

Bibliografía
1. Referencia...
"""
    raw_bytes = sample_basico_md.encode("utf-8")

    with patch("tools.parser_tool.fetch_pdf_bytes_from_s3", return_value=raw_bytes):
        parsed = parse_curricular_areas.invoke({"file_key": "cnb/basico_matematicas.pdf"})

        assert isinstance(parsed, list)
        assert len(parsed) == 3
        names = [item["clean_name"] for item in parsed]
        assert "Matemáticas Primero Básico" in names
        assert "Matemáticas Segundo Básico" in names
        assert "Matemáticas Tercero Básico" in names

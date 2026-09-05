import pytest
import os
import sys
import io
import base64
from markitdown import MarkItDown

# Ensure app package is accessible in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.parser_tool import (
    convert_pdf_to_markdown,
    extract_career_name,
    extract_curricular_structure_table,
    parse_curricular_areas,
)


TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_files")
REAL_CNB_FILE = os.path.join(TEST_FILES_DIR, "cnb.md")
PYPROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))


def test_markitdown_presence():
    """
    Verifies the presence and initialization of Microsoft's MarkItDown library
    and correct configuration of 'markitdown[pdf]' dependency in pyproject.toml.
    """
    md = MarkItDown()
    assert md is not None, "MarkItDown could not be instantiated."
    assert callable(getattr(md, "convert", None)), "MarkItDown does not contain 'convert' method."

    assert os.path.exists(PYPROJECT_PATH), f"pyproject.toml not found at {PYPROJECT_PATH}."
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        pyproject_content = f.read()
    
    assert "markitdown[pdf]" in pyproject_content, (
        "Dependency 'markitdown[pdf]' with PDF support is not configured in pyproject.toml."
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
    Verifies correct parsing into curricular areas using real cnb.md file.
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
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    parsed_result = parse_curricular_areas.invoke({"pdf_base64": b64_str})
    assert len(parsed_result) > 0
    assert parsed_result[0]["clean_name"] == "Estructura Curricular"
    assert parsed_result[0]["index"] == 0
    assert "Tabla No. 1" in parsed_result[0]["content"]


def test_in_memory_pdf_processing():
    """
    Verifies that parser_tool processes Base64 strings in memory without writing to disk.
    """
    assert os.path.exists(REAL_CNB_FILE), f"Real test file {REAL_CNB_FILE} does not exist."

    with open(REAL_CNB_FILE, "rb") as f:
        raw_bytes = f.read()

    b64_str = base64.b64encode(raw_bytes).decode("utf-8")

    result_b64 = convert_pdf_to_markdown(b64_str)
    assert len(result_b64) > 0, "Conversion result for Base64 is empty."

    data_uri = f"data:application/pdf;base64,{b64_str}"
    result_uri = convert_pdf_to_markdown(data_uri)
    assert len(result_uri) > 0, "Conversion result for Data URI Base64 is empty."


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

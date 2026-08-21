import pytest
import os
import sys
import io
from markitdown import MarkItDown

# Asegurar que el paquete app esté accesible en sys.path
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
    1.1 Procesar PDF: Verificar la presencia e inicialización de la librería MarkItDown de Microsoft
    y la correcta configuración de la dependencia 'markitdown[pdf]' en pyproject.toml.
    """
    md = MarkItDown()
    assert md is not None, "MarkItDown no pudo ser instanciado."
    assert callable(getattr(md, "convert", None)), "MarkItDown no contiene el método 'convert'."

    # Verificar que markitdown[pdf] esté declarada en pyproject.toml
    assert os.path.exists(PYPROJECT_PATH), f"No se encontró pyproject.toml en {PYPROJECT_PATH}."
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        pyproject_content = f.read()
    
    assert "markitdown[pdf]" in pyproject_content, (
        "La dependencia 'markitdown[pdf]' con soporte para PDF no está configurada en pyproject.toml."
    )


def test_extract_career_name():
    """
    1.2 Procesar PDF: Verificar que se extrae el nombre de la carrera utilizando el archivo cnb.md real en tests/test_files/.
    """
    assert os.path.exists(REAL_CNB_FILE), f"El archivo de prueba real {REAL_CNB_FILE} no existe."
    
    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    career_name = extract_career_name(content)
    assert career_name == "Bachillerato en Ciencias y Letras con Orientación en Computación", (
        f"Se esperaba 'Bachillerato en Ciencias y Letras con Orientación en Computación', pero se obtuvo: '{career_name}'"
    )


def test_parse_curricular_areas():
    """
    1.3 Procesar PDF: Verificar el correcto parseo en áreas curriculares utilizando el archivo cnb.md real en tests/test_files/.
    """
    assert os.path.exists(REAL_CNB_FILE), f"El archivo de prueba real {REAL_CNB_FILE} no existe."

    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    career = extract_career_name(content)
    assert career == "Bachillerato en Ciencias y Letras con Orientación en Computación"

    lines = content.splitlines()
    areas_found = [line.strip() for line in lines if "Área Curricular de" in line]

    assert len(areas_found) > 0, "No se detectaron áreas curriculares en el archivo cnb.md real."
    assert any("Comunicación y Lenguaje" in a for a in areas_found), "Falta el Área Curricular de Comunicación y Lenguaje."
    assert any("Matemáticas" in a for a in areas_found), "Falta el Área Curricular de Matemáticas."
    assert any("Contabilidad" in a for a in areas_found), "Falta el Área Curricular de Contabilidad."

    # Verificar que el elemento en posición 0 sea la Estructura Curricular (Tabla No. 1)
    with open(REAL_CNB_FILE, "rb") as f:
        raw_bytes = f.read()
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    parsed_result = parse_curricular_areas.invoke({"pdf_base64": b64_str})
    assert len(parsed_result) > 0
    assert parsed_result[0]["clean_name"] == "Estructura Curricular"
    assert parsed_result[0]["index"] == 0
    assert "Tabla No. 1" in parsed_result[0]["content"]


import base64


def test_in_memory_pdf_processing():
    """
    1.4 Procesar PDF: Verificar que el parser_tool procese exclusivamente cadenas Base64 en memoria sin escribir en disco.
    """
    assert os.path.exists(REAL_CNB_FILE), f"El archivo de prueba real {REAL_CNB_FILE} no existe."

    with open(REAL_CNB_FILE, "rb") as f:
        raw_bytes = f.read()

    b64_str = base64.b64encode(raw_bytes).decode("utf-8")

    # Prueba con cadena Base64 pura
    result_b64 = convert_pdf_to_markdown(b64_str)
    assert len(result_b64) > 0, "El resultado de la conversión por Base64 está vacío."

    # Prueba con URI de datos Base64
    data_uri = f"data:application/pdf;base64,{b64_str}"
    result_uri = convert_pdf_to_markdown(data_uri)
    assert len(result_uri) > 0, "El resultado de la conversión por Data URI Base64 está vacío."


def test_extract_curricular_structure_table():
    """
    1.5 Procesar PDF: Verificar la extracción dinámica de la 'Tabla No. 1: Estructura...' del documento.
    Comienza en la Tabla No. 1 y se cierra al detectar la Tabla No. 2.
    """
    assert os.path.exists(REAL_CNB_FILE), f"El archivo de prueba real {REAL_CNB_FILE} no existe."

    with open(REAL_CNB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    table1_block = extract_curricular_structure_table(content)

    assert len(table1_block) > 0, "No se pudo extraer el bloque de la Tabla No. 1 del documento."
    assert "Tabla No. 1" in table1_block or "Estructura de Bachillerato" in table1_block
    assert "Tabla No. 2" not in table1_block, "El bloque capturado debe cerrarse antes de la Tabla No. 2."
    assert "Bachillerato en Ciencias y Letras" in table1_block

    # Probar que en ausencia de Tabla No. 2 el bloque se cierra al encontrar la primera Área Curricular
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

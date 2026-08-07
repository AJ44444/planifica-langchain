import pytest
import os
import sys
from markitdown import MarkItDown

# Asegurar que el paquete app esté accesible en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.parser_tool import convert_pdf_to_markdown, extract_career_name, parse_curricular_areas


TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_files")
REAL_CNB_FILE = os.path.join(TEST_FILES_DIR, "cnb.md")


def test_markitdown_presence():
    """
    1.1 Procesar PDF: Verificar la presencia e inicialización de la librería MarkItDown de Microsoft.
    """
    md = MarkItDown()
    assert md is not None, "MarkItDown no pudo ser instanciado."
    assert callable(getattr(md, "convert", None)), "MarkItDown no contiene el método 'convert'."


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

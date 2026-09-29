import pytest
import os
import sys
import json
from unittest.mock import patch
import pypdfium2 as pdfium

# Ensure app package is accessible in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from workers.pdf_worker import (
    convert_pdf_bytes,
    extract_career_name,
    extract_curricular_structure_table,
    parse_curricular_areas,
    slugify,
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
    Verifies correct parsing into curricular areas using text content.
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

    table = extract_curricular_structure_table(content)
    parsed_result = parse_curricular_areas(content, career_name=career, structure_table=table)
    assert isinstance(parsed_result, list)
    assert len(parsed_result) > 0
    assert parsed_result[0]["clean_name"] != "Estructura Curricular"
    assert parsed_result[0]["index"] == 1


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

    doc_without_table1 = "Este es un documento sin tabla de estructura curricular."
    assert extract_curricular_structure_table(doc_without_table1) == "Unidentified"


def test_slugify_and_fallback_parse():
    """
    Verifies slugify Unicode NFD normalization and alternative area extraction flow using text content.
    """
    assert slugify("Área de Comunicación y Lenguaje L 1") == "comunicacion_y_lenguaje_l1"
    assert slugify("Área de Matemáticas") == "matematicas"
    assert slugify("Área de Medio Social y Natural") == "medio_social_y_natural"

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
    parsed = parse_curricular_areas(sample_primaria_md)

    assert isinstance(parsed, list)
    assert len(parsed) == 3
    names = [item["clean_name"] for item in parsed]
    assert "Comunicación y Lenguaje L 1" in names
    assert "Comunicación y Lenguaje L 2" in names
    assert "Matemáticas" in names
    assert "Comunicación y Lenguaje" not in names


def test_malla_curricular_basico_parse():
    """
    Verifies dynamic parsing of Ciclo Básico Malla Curricular + Grade headers using text content.
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
    parsed = parse_curricular_areas(sample_basico_md)

    assert isinstance(parsed, list)
    assert len(parsed) == 3
    names = [item["clean_name"] for item in parsed]
    assert "Matemáticas Primero Básico" in names
    assert "Matemáticas Segundo Básico" in names
    assert "Matemáticas Tercero Básico" in names


def test_process_pdf_job_uses_user_nombre_carrera_fallback():
    """
    Verifies that when extract_career_name returns Unidentified, user_nombre_carrera is used as fallback.
    """
    import asyncio
    from unittest.mock import MagicMock
    from workers.pdf_worker import PdfProcessingWorker

    async def run_test():
        with patch("workers.pdf_worker.get_env_variable", return_value="redis://localhost:6379"):
            worker = PdfProcessingWorker()
        mock_redis = MagicMock()

        async def mock_set(key, val):
            pass

        async def mock_publish(channel, msg):
            pass

        mock_redis.set = MagicMock(side_effect=mock_set)
        mock_redis.publish = MagicMock(side_effect=mock_publish)
        worker.redis = mock_redis

        from core.tool_inputs import SaveCurricularStructureInput

        fake_areas = [{"clean_name": "Matemáticas", "content": "Contenido del área"}]
        mock_llm_res = SaveCurricularStructureInput(
            nombre_carrera="Perito Contador",
            nombre_area="Matemáticas",
            actividades_sugeridas=[],
            criterios_evaluacion_sugeridos=[],
            subareas=[]
        )

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_res
        worker._llm = mock_llm

        mock_subareas_extractor = MagicMock()
        mock_subareas_extractor.invoke.return_value = {"subareas": ["Matemáticas Cuarto Grado"]}
        worker._subarea_extractor = mock_subareas_extractor

        with patch("workers.pdf_worker.fetch_pdf_bytes_from_s3", return_value=b"%PDF-fake"), \
             patch("workers.pdf_worker.convert_pdf_bytes", return_value="Documento sin titulo"), \
             patch("workers.pdf_worker.extract_career_name", return_value="Unidentified"), \
             patch("workers.pdf_worker.extract_curricular_structure_table", return_value="Tabla No. 1: Estructura de Perito Contador"), \
             patch("workers.pdf_worker.parse_curricular_areas", return_value=fake_areas), \
             patch("workers.pdf_worker.save_curricular_structure", return_value='{"status": "success", "subareas_insertadas": []}'):

            await worker.process_pdf_job(
                job_id="job_carrera_test",
                file_key="cnb/test.pdf",
                file_hash="hash123",
                user_nombre_carrera="Perito Contador"
            )

            assert mock_llm.invoke.call_count == 1
            invoked_user_msg = mock_llm.invoke.call_args[0][0][1]["content"]
            assert "Perito Contador" in invoked_user_msg
            assert "Matemáticas Cuarto Grado" in invoked_user_msg

    asyncio.run(run_test())


def test_process_pdf_job_when_structure_table_is_unidentified():
    """
    Verifies that when extract_curricular_structure_table returns 'Unidentified',
    the worker continues parsing, structuring, storing in DB, and triggering Redis vectorization events.
    """
    import asyncio
    from unittest.mock import MagicMock, AsyncMock
    from workers.pdf_worker import PdfProcessingWorker

    async def run_test():
        with patch("workers.pdf_worker.get_env_variable", return_value="redis://localhost:6379"):
            worker = PdfProcessingWorker()
        
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.xadd = AsyncMock()
        worker.redis = mock_redis

        from core.tool_inputs import SaveCurricularStructureInput

        fake_areas = [{
            "clean_name": "Matemáticas",
            "content": "Contenido de Matemáticas de la Malla Curricular"
        }]

        mock_llm_res = SaveCurricularStructureInput(
            nombre_carrera="Educación Primaria",
            nombre_area="Matemáticas",
            actividades_sugeridas=["Resolver sumas"],
            criterios_evaluacion_sugeridos=["Aplica adición"],
            subareas=[]
        )

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_res
        worker._llm = mock_llm

        mock_subareas_extractor = MagicMock()
        worker._subarea_extractor = mock_subareas_extractor

        save_db_response = json.dumps({
            "status": "success",
            "id_area": "60d5ec49f1a2c81234567810",
            "subareas_insertadas": [{"id_subarea": "60d5ec49f1a2c81234567820", "nombre_subarea": "Matemáticas 1"}]
        })

        with patch("workers.pdf_worker.fetch_pdf_bytes_from_s3", return_value=b"%PDF-fake"), \
             patch("workers.pdf_worker.convert_pdf_bytes", return_value="Malla curricular Área de Matemáticas Primero Básico"), \
             patch("workers.pdf_worker.extract_career_name", return_value="Educación Primaria"), \
             patch("workers.pdf_worker.extract_curricular_structure_table", return_value="Unidentified"), \
             patch("workers.pdf_worker.parse_curricular_areas", return_value=fake_areas), \
             patch("workers.pdf_worker.save_curricular_structure", return_value=save_db_response):

            await worker.process_pdf_job(
                job_id="job_unidentified_table_test",
                file_key="cnb/primaria.pdf",
                file_hash="hash456",
                user_nombre_carrera="Educación Primaria"
            )

            # 1. Subareas extractor was NOT called because structure table was Unidentified
            assert mock_subareas_extractor.invoke.call_count == 0

            # 2. LLM was invoked for structuring the area
            assert mock_llm.invoke.call_count == 1

            # 3. Vectorization action event was queued in Redis Stream
            assert mock_redis.xadd.call_count == 1
            xadd_call_args = mock_redis.xadd.call_args[0]
            assert xadd_call_args[0] == "stream:vectorize"
            assert xadd_call_args[1]["action"] == "vectorize"
            assert xadd_call_args[1]["id_subarea"] == "60d5ec49f1a2c81234567820"
            assert xadd_call_args[1]["nombre_subarea"] == "Matemáticas 1"

    asyncio.run(run_test())


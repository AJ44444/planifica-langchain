import re
import json
import logging
import asyncio
import unicodedata
import pypdfium2
from typing import Optional, List, Dict, Any, Union
from redis.asyncio import Redis, from_url
from pydantic import BaseModel, Field, ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import get_env_variable
from core.tool_inputs import SaveCurricularStructureInput
from middleware.security_middleware import sanitize_external_text
from api.upload_handler import get_s3_client
from tools.persistence_tool import save_curricular_structure
from tools.vector_tool import is_google_rate_limit_error

logger = logging.getLogger(__name__)

STREAM_KEY = "stream:jobs"
GROUP_NAME = "group:pdf_workers"
CONSUMER_NAME = "pdf-worker-1"
NOTIFICATION_CHANNEL = "channel:notifications"


class OfficialSubareasInput(BaseModel):
    subareas: List[str] = Field(
        default_factory=list,
        description="Lista de nombres oficiales de las subáreas curriculares con su grado (ej. Matemáticas Cuarto Grado, Estadística Quinto Grado)."
    )


def fetch_pdf_bytes_from_s3(file_key: str) -> bytes:
    s3_client, bucket_name = get_s3_client()
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key.strip())
    return response["Body"].read()


def convert_pdf_bytes(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        raise ValueError("PDF content cannot be empty.")

    if pdf_bytes.startswith(b"%PDF"):
        pdf = pypdfium2.PdfDocument(pdf_bytes)
        extracted_pages = []
        for page_idx in range(len(pdf)):
            page = pdf[page_idx]
            textpage = page.get_textpage()
            page_text = textpage.get_text_range()
            if page_text.strip():
                extracted_pages.append(page_text)
        full_text = "\n".join(extracted_pages)
        text_normalized = full_text.replace("\r\n", "\n").replace("\r", "\n")
        text_no_double_newlines = re.sub(r"\n{2,}", "\n", text_normalized).strip()
        return sanitize_external_text(text_no_double_newlines, wrap_xml=True)
    else:
        text_content = pdf_bytes.decode("utf-8", errors="ignore")
        text_normalized = text_content.replace("\r\n", "\n").replace("\r", "\n")
        text_no_double_newlines = re.sub(r"\n{2,}", "\n", text_normalized).strip()
        return sanitize_external_text(text_no_double_newlines, wrap_xml=True)


def extract_career_name(document: str) -> str:
    lines = document.splitlines()
    for line in lines[:500]:
        m = re.search(r'(?i)(?:Curricul?um|Curr[ií]culum)\s+Nacional\s+Base\s*[-–—]\s*(.+)', line)
        if m:
            val = m.group(1).strip()
            val = re.sub(r'^\d+\s*', '', val).strip()
            if val:
                return val
    return "Unidentified"


def extract_curricular_structure_table(document: str) -> str:
    if not document or not isinstance(document, str):
        return "Unidentified"

    lines = document.splitlines()
    capturing = False
    captured_lines = []

    table1_pattern = re.compile(r'(?i)Tabla\s+(?:No\.?|N°|Nº)?\s*1\s*:\s*Estructura\s+de\s+')
    closing_pattern = re.compile(
        r'(?i)(?:Tabla\s+(?:No\.?|N°|Nº)?\s*2\b|^(?:#+\s*)?(?:Área|Area)\s+curricular\s+de\s+)'
    )

    for line in lines:
        if not capturing:
            if table1_pattern.search(line):
                capturing = True
                captured_lines.append(line)
        else:
            if closing_pattern.search(line.strip()):
                break
            captured_lines.append(line)

    result = "\n".join(captured_lines).strip()
    return result if result else "Unidentified"


def slugify(title: str) -> str:
    clean = re.sub(r'^(?:Área|Area)\s+de\s+', '', title, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\s*\([^)]*\)', '', clean).strip()
    nfkd = unicodedata.normalize('NFD', clean)
    ascii_str = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', ascii_str).strip('_').lower()
    slug = re.sub(r'_l_(\d+)$', r'_l\1', slug)
    return slug


def parse_curricular_areas(content: str, career_name: str = "Unidentified", structure_table: str = "Unidentified") -> Union[List[Dict[str, str]], str]:
    if not isinstance(content, str):
        content = str(content)

    areas_list = []

    if career_name != "Unidentified" and structure_table != "Unidentified":
        lines = content.splitlines(keepends=True)
        n_lines = len(lines)

        md_heading_indices = []
        for i, line in enumerate(lines):
            if re.match(r'^#+\s*(?:Área|Area)\s+curricular\s+de\s+', line.strip(), re.IGNORECASE):
                md_heading_indices.append(i)

        areas_meta = []

        if len(md_heading_indices) >= 2:
            for k, idx in enumerate(md_heading_indices):
                line_str = lines[idx].strip()
                title = re.sub(r'^#+\s*', '', line_str)
                clean_name = re.sub(r'^(?:Área|Area)\s+curricular\s+de\s+', '', title, flags=re.IGNORECASE).strip()
                full_title = title if re.match(r'^(?:Área|Area)\s+curricular\s+de\s+', title, re.IGNORECASE) else f'Área Curricular de {clean_name}'
                areas_meta.append({
                    'start_idx': idx,
                    'header_idx': idx,
                    'full_title': full_title,
                    'clean_name': clean_name
                })
        else:
            current_active_area = None
            start_search = min(1000, n_lines)

            for i in range(start_search, n_lines):
                line = lines[i].strip()
                if re.match(r'^(?:#+\s*)?(?:Área|Area)\s+curricular\s+de\s+', line, re.IGNORECASE):
                    title = line
                    if i + 1 < n_lines:
                        l_next = lines[i+1].strip()
                        if not l_next.startswith('Descriptor') and not l_next.isdigit() and not re.match(r'^(?:#+\s*)?(?:Área|Area)', l_next):
                            if i + 2 < n_lines and lines[i+2].strip() == 'Descriptor':
                                title = line + ' ' + l_next

                    has_descriptor = False
                    for k in range(1, 5):
                        if i + k < n_lines and lines[i+k].strip() == 'Descriptor':
                            has_descriptor = True
                            break
                    if not has_descriptor:
                        continue

                    clean_name = re.sub(r'^(?:#+\s*)?(?:Área|Area)\s+curricular\s+de\s+', '', title, flags=re.IGNORECASE).strip()

                    if current_active_area is not None and clean_name.lower() == current_active_area.lower():
                        continue

                    start_idx = i
                    if i > 0 and lines[i-1].strip().isdigit():
                        start_idx = i - 1
                    elif i > 1 and lines[i-2].strip().isdigit():
                        start_idx = i - 2

                    if re.match(r'^(?:Área|Area)\s+curricular\s+de\s+', title, re.IGNORECASE):
                        full_title = title
                    else:
                        full_title = f'Área Curricular de {clean_name}'

                    areas_meta.append({
                        'start_idx': start_idx,
                        'header_idx': i,
                        'full_title': full_title,
                        'clean_name': clean_name
                    })
                    current_active_area = clean_name

        for k in range(len(areas_meta)):
            if k < len(areas_meta) - 1:
                areas_meta[k]['end_idx'] = areas_meta[k+1]['start_idx']
            else:
                last_start = areas_meta[k]['start_idx']
                end_idx = n_lines
                for j in range(last_start + 10, n_lines):
                    l_str = lines[j].strip()
                    if re.match(r'^(?:3\s+)?Tercera\s+parte', l_str, re.IGNORECASE) or re.match(r'^#+\s*(?:3\s+)?Tercera\s+parte', l_str, re.IGNORECASE):
                        end_idx = j
                        break
                areas_meta[k]['end_idx'] = end_idx

        if areas_meta:
            for idx, area in enumerate(areas_meta, 1):
                s_idx = area['start_idx']
                e_idx = area['end_idx']
                full_title = area['full_title']

                header = f"# {career_name}\n## {full_title}\n\n"
                raw_body = "".join(lines[s_idx:e_idx])
                full_area_content = header + raw_body

                areas_list.append({
                    'index': idx,
                    'career_name': career_name,
                    'area_title': full_title,
                    'clean_name': area['clean_name'],
                    'content': full_area_content
                })

    if not areas_list:
        regex_malla_grade = re.compile(
            r'^[ \t]*#*[ \t]*Malla\s+curricular\s*\r?\n[ \t]*((?:Área|Area)\s+de\s+[^\n\r]+)\r?\n[ \t]*([^\n\r]+)',
            re.MULTILINE
        )
        regex_end_sections_basico = re.compile(
            r"(?m)^[ \t]*(?:Bibliograf|\d+\s*\r?\n\s*Bibliograf|Los\s+aprendizajes\s+esperados\s+o\s+estándares)",
            re.IGNORECASE
        )

        body_search_start = content.rfind("Desarrollo de las")
        if body_search_start == -1:
            body_search_start = 0

        body_text = content[body_search_start:]

        malla_matches = list(regex_malla_grade.finditer(body_text))
        if malla_matches:
            areas_meta_alt = []
            for m in malla_matches:
                area_name = m.group(1).strip()
                grade_name = m.group(2).strip()
                full_title = f"{area_name} {grade_name}"
                clean_area = re.sub(r'^(?:Área|Area)\s+de\s+', '', area_name, flags=re.IGNORECASE).strip()
                clean_name = f"{clean_area} {grade_name}"
                file_name = slugify(full_title)
                abs_pos = body_search_start + m.start()

                areas_meta_alt.append({
                    'title': full_title,
                    'area_name': area_name,
                    'grade_name': grade_name,
                    'clean_area': clean_area,
                    'clean_name': clean_name,
                    'file_name': file_name,
                    'start_pos': abs_pos
                })

            end_match = regex_end_sections_basico.search(content, areas_meta_alt[-1]['start_pos'])
            end_global_pos = end_match.start() if end_match else len(content)

            for i, area in enumerate(areas_meta_alt, 1):
                start_idx = area['start_pos']
                end_idx = areas_meta_alt[i]['start_pos'] if i < len(areas_meta_alt) else end_global_pos

                area_raw_content = content[start_idx:end_idx].strip()
                title_str = area['title']
                item_career_name = area['grade_name'] if career_name == "Unidentified" else career_name
                header = f"# {item_career_name}\n## {title_str}\n\n"

                full_area_content = header + area_raw_content

                areas_list.append({
                    'index': i,
                    'career_name': item_career_name,
                    'area_title': title_str,
                    'clean_name': area['clean_name'],
                    'content': full_area_content
                })

    if not areas_list:
        regex_header_area = re.compile(
            r'^[ \t]*#*[ \t]*((?:Área|Area)\s+de\s+[A-ZÁÉÍÓÚÑ][^\n\r]*)',
            re.MULTILINE
        )
        regex_end_sections_primaria = re.compile(
            r"(?m)^(?:\d+\s*\r?\n\s*)?Los\s+aprendizajes\s+esperados\s+o\s+estándares\b"
        )

        body_search_start = content.rfind("Desarrollo de las")
        if body_search_start == -1:
            body_search_start = 0

        body_text = content[body_search_start:]

        matches = []
        for m in regex_header_area.finditer(body_text):
            title = m.group(1).strip()
            is_subarea = bool(re.search(r'(?i)\bL\s*\d+$', title))
            is_toc = bool(re.search(r'\.{2,}\s*\d+$', title)) or (not is_subarea and bool(re.search(r'\b\d{1,3}$', title)))
            if is_toc:
                continue
            abs_pos = body_search_start + m.start()
            matches.append((title, abs_pos))

        areas_meta_alt = []
        for title, pos in matches:
            clean_name = re.sub(r'^(?:Área|Area)\s+de\s+', '', title, flags=re.IGNORECASE).strip()
            file_name = slugify(title)
            if file_name == "comunicacion_y_lenguaje":
                continue
            if not areas_meta_alt or areas_meta_alt[-1]['clean_name'] != clean_name:
                areas_meta_alt.append({
                    'title': title,
                    'clean_name': clean_name,
                    'file_name': file_name,
                    'start_pos': pos
                })

        if areas_meta_alt:
            end_match = regex_end_sections_primaria.search(content, areas_meta_alt[-1]['start_pos'])
            end_global_pos = end_match.start() if end_match else len(content)

            for i, area in enumerate(areas_meta_alt, 1):
                start_idx = area['start_pos']
                end_idx = areas_meta_alt[i]['start_pos'] if i < len(areas_meta_alt) else end_global_pos

                area_raw_content = content[start_idx:end_idx].strip()
                title_str = area['title']
                header = f"# {career_name}\n## {title_str}\n\n" if career_name != "Unidentified" else f"## {title_str}\n\n"
                full_area_content = header + area_raw_content

                areas_list.append({
                    'index': i,
                    'career_name': career_name,
                    'area_title': title_str,
                    'clean_name': area['clean_name'],
                    'content': full_area_content
                })

    if not areas_list:
        return "Unidentified"

    return areas_list


class PdfProcessingWorker:

    def __init__(self):
        self.redis_uri = get_env_variable("REDIS_URI")
        self.redis: Optional[Redis] = None
        self.running = False
        self._llm = None
        self._subarea_extractor = None

    @property
    def llm(self):
        if not self._llm:
            google_api_key = get_env_variable("GOOGLE_API_KEY")
            base_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=google_api_key,
                temperature=0.0
            )
            self._llm = base_llm.with_structured_output(SaveCurricularStructureInput)
        return self._llm

    @property
    def subarea_extractor(self):
        if not self._subarea_extractor:
            google_api_key = get_env_variable("GOOGLE_API_KEY")
            base_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=google_api_key,
                temperature=0.0
            )
            self._subarea_extractor = base_llm.with_structured_output(OfficialSubareasInput)
        return self._subarea_extractor

    async def connect(self):
        if not self.redis:
            self.redis = from_url(self.redis_uri, decode_responses=True)

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()
            self.redis = None

    async def init_consumer_group(self):
        await self.connect()
        try:
            await self.redis.xgroup_create(
                name=STREAM_KEY,
                groupname=GROUP_NAME,
                id="0",
                mkstream=True
            )
        except Exception as e:
            logger.warning(f"Consumer group '{GROUP_NAME}' status: {e}")

    async def publish_job_status(self, job_id: str, file_key: str, file_hash: str, main_task: str, subtask: str, status: str) -> Dict[str, Any]:
        await self.connect()
        job_payload = {
            "id": job_id,
            "file_key": file_key,
            "file_hash": file_hash,
            "main_task": main_task,
            "subtask": subtask,
            "status": status
        }
        json_msg = json.dumps(job_payload, ensure_ascii=False)

        await self.redis.set(f"job:{job_id}:status", json_msg)
        await self.redis.publish(NOTIFICATION_CHANNEL, json_msg)
        return job_payload

    async def process_pdf_job(self, job_id: str, file_key: str, file_hash: str, user_nombre_carrera: str = ""):
        main_task = "Procesar Currículum"

        await self.publish_job_status(
            job_id=job_id,
            file_key=file_key,
            file_hash=file_hash,
            main_task=main_task,
            subtask="Descargando archivo PDF desde almacenamiento S3",
            status="progress"
        )

        try:
            pdf_bytes = fetch_pdf_bytes_from_s3(file_key)
            pdf_text = convert_pdf_bytes(pdf_bytes)

            # 1. extract_career_name
            carrera_name = extract_career_name(pdf_text)
            if (carrera_name == "Unidentified" or not carrera_name) and user_nombre_carrera:
                carrera_name = user_nombre_carrera

            # 2. extract_curricular_structure_table
            structure_table = extract_curricular_structure_table(pdf_text)

            # 3. Extraer nombres oficiales de subáreas de la tabla si no es Unidentified
            official_subareas: List[str] = []
            if structure_table != "Unidentified":
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask="Extrayendo lista de nombres oficiales de subáreas de la tabla de estructura",
                    status="progress"
                )

                system_prompt_subareas = (
                    "Eres un experto en currículos educativos. Analiza la siguiente tabla de estructura curricular "
                    "y extrae un listado plano de los nombres oficiales de todas las subáreas curriculares, "
                    "incluyendo el grado correspondiente si aplica (por ejemplo: 'Matemáticas Cuarto Grado', "
                    "'Estadística Quinto Grado', 'Comunicación y Lenguaje L1 Tercer Grado', 'Matemáticas Primero Básico')."
                )
                try:
                    subareas_res = await asyncio.to_thread(
                        self.subarea_extractor.invoke,
                        [
                            {"role": "system", "content": system_prompt_subareas},
                            {"role": "user", "content": f"Nombre de la carrera: {carrera_name}\n\nTabla de estructura curricular:\n{structure_table}"}
                        ]
                    )
                    if isinstance(subareas_res, OfficialSubareasInput):
                        official_subareas = subareas_res.subareas
                    elif isinstance(subareas_res, dict):
                        official_subareas = subareas_res.get("subareas", [])
                except Exception as sub_err:
                    if is_google_rate_limit_error(sub_err):
                        logger.warning(f"Límite de cuota en API de Google alcanzado al extraer subáreas para job {job_id}: {sub_err}")
                        await self.publish_job_status(
                            job_id=job_id,
                            file_key=file_key,
                            file_hash=file_hash,
                            main_task=main_task,
                            subtask="Límite de cuota alcanzado en API de Google. Trabajo pausado para reanudación posterior.",
                            status="paused"
                        )
                        self.stop()
                        return
                    logger.warning(f"No se pudieron extraer nombres oficiales de subáreas con LLM: {sub_err}")

            # 4. parse_curricular_areas
            areas_data = parse_curricular_areas(content=pdf_text, career_name=carrera_name, structure_table=structure_table)

            if not areas_data or areas_data == "Unidentified":
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask="No se pudieron extraer áreas curriculares del documento PDF",
                    status="error"
                )
                return

            subareas_to_vectorize: List[Dict[str, str]] = []

            # Iterar todos los elementos devueltos por parse_curricular_areas
            for idx, area_item in enumerate(areas_data, start=1):
                area_name = area_item.get("clean_name", area_item.get("nombre_area", f"Área {idx}"))
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask=f"Estructurando información del área: {area_name}",
                    status="progress"
                )

                prompt_user = (
                    f"Nombre de la carrera / grado: {carrera_name}\n"
                    f"Listado de nombres oficiales de subáreas curriculares (utiliza estos nombres oficiales al estructurar las subáreas): {json.dumps(official_subareas, ensure_ascii=False)}\n\n"
                    f"Información del área curricular a estructurar:\n"
                    f"{json.dumps(area_item, ensure_ascii=False)}"
                )

                system_prompt = (
                    "Eres un asistente experto en estructuración de diseños curriculares educativos (CNB de Guatemala).\n"
                    "Tu única tarea es estructurar la información proporcionada únicamente en el formato del esquema SaveCurricularStructureInput cumpliendo estrictamente las siguientes reglas:\n\n"
                    "1. FIDELIDAD TEXTUAL:\n"
                    "   - Mantén las descripciones de competencias, indicadores de logro y contenidos TEXTUALMENTE IDÉNTICAS a como aparecen en la información proporcionada.\n\n"
                    "2. MANEJO DE NIVELES Y ESTRUCTURA:\n"
                    "   - NIVEL PRIMARIA: El documento se divide en Áreas (ej. 'Área de Comunicación y Lenguaje L1', 'Área de Comunicación y Lenguaje L2', 'Área de Matemáticas'). Identifica lo que corresponde a la estructura de Área ('nombre_area') y asigna el árbol de competencias a la Subárea correspondiente ('nombre_subarea').\n"
                    "   - CICLO BÁSICO: Para currículos de Ciclo Básico (ej. Matemáticas con secciones de 1ro, 2do y 3er grado), cada grado se trata como un ámbito de carrera distinto ('nombre_carrera', ej. 'Primero Básico', 'Segundo Básico', 'Tercero Básico'). Cada sección de grado debe guardarse bajo su nombre de carrera/grado correspondiente.\n"
                    "   - CRITERIOS DE EVALUACIÓN EN CICLO BÁSICO: En Ciclo Básico, los Criterios de Evaluación suelen encontrarse dentro de la tabla junto a competencias, indicadores y contenidos. Debes EXTRAER estos criterios de evaluación de la tabla de competencias y agruparlos en el arreglo 'criterios_evaluacion_sugeridos' del área, separándolos del árbol de competencias de la subárea.\n\n"
                    "3. NOMBRES OFICIALES DE SUBÁREAS Y GRADOS:\n"
                    "   - Asigna a cada subárea su nombre oficial utilizando la lista de nombres oficiales proporcionada cuando aplique.\n"
                    "   - Incluye siempre el nombre del grado en el nombre de la subárea cuando aplique (ej. 'Matemáticas Primero Básico', 'Comunicación y Lenguaje L1 Tercer Grado', 'Matemáticas Tercer Grado').\n\n"
                    "4. IDENTIFICADORES JERÁRQUICOS:\n"
                    "   - Asigna identificadores numéricos simples según el texto (ej. id_competencia: '1', id_indicador: '1.1', id_contenido: '1.1.1').\n\n"
                    "5. ESTRUCTURA DE SALIDA:\n"
                    "   - Retorna únicamente el objeto estructurado con: nombre_carrera, nombre_area, actividades_sugeridas, criterios_evaluacion_sugeridos y subareas."
                )

                # Instancia del agente Google con estructuración
                try:
                    structured_response = await asyncio.to_thread(
                        self.llm.invoke,
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_user}
                        ]
                    )
                except Exception as llm_err:
                    if is_google_rate_limit_error(llm_err):
                        logger.warning(f"Límite de cuota en API de Google alcanzado para job {job_id} al estructurar área {area_name}: {llm_err}")
                        await self.publish_job_status(
                            job_id=job_id,
                            file_key=file_key,
                            file_hash=file_hash,
                            main_task=main_task,
                            subtask=f"Límite de cuota alcanzado en API de Google al estructurar área {area_name}. Trabajo pausado para reanudación posterior.",
                            status="paused"
                        )
                        self.stop()
                        return
                    raise llm_err

                # Validar formato
                if isinstance(structured_response, SaveCurricularStructureInput):
                    validated_input = structured_response
                elif isinstance(structured_response, dict):
                    validated_input = SaveCurricularStructureInput.model_validate(structured_response)
                else:
                    raise ValueError(f"Formato no válido recibido para el área {area_name}")

                # Guardar utilizando save_curricular_structure
                save_result_str = save_curricular_structure(
                    nombre_carrera=validated_input.nombre_carrera or carrera_name,
                    nombre_area=validated_input.nombre_area or area_name,
                    actividades_sugeridas=validated_input.actividades_sugeridas,
                    criterios_evaluacion_sugeridos=validated_input.criterios_evaluacion_sugeridos,
                    subareas=validated_input.subareas
                )

                save_result = json.loads(save_result_str)
                if save_result.get("status") == "success":
                    inserted_subareas = save_result.get("subareas_inserted") or save_result.get("subareas_insertadas") or []
                    for sub_info in inserted_subareas:
                        subareas_to_vectorize.append({
                            "id_subarea": sub_info.get("id_subarea", ""),
                            "nombre_subarea": sub_info.get("nombre_subarea", "")
                        })

                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask=f"Guardada estructura de área: {area_name}",
                    status="progress"
                )

            # Al finalizar de procesar todos los elementos, informar y disparar worker de vectores
            await self.publish_job_status(
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                main_task=main_task,
                subtask="Estructura curricular guardada. Disparando vectorización de subáreas.",
                status="progress"
            )

            for sub_data in subareas_to_vectorize:
                id_subarea = sub_data["id_subarea"]
                nombre_subarea = sub_data["nombre_subarea"]
                if id_subarea:
                    await self.redis.xadd(
                        STREAM_KEY,
                        {
                            "action": "vectorize",
                            "job_id": job_id,
                            "file_key": file_key,
                            "file_hash": file_hash,
                            "id_subarea": id_subarea,
                            "nombre_subarea": nombre_subarea
                        }
                    )

        except ValidationError as val_err:
            logger.warning(f"Error de validación Pydantic para job {job_id}: {val_err}")
            await self.publish_job_status(
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                main_task=main_task,
                subtask=f"Error de validación de formato: {str(val_err)}",
                status="error"
            )
        except Exception as e:
            if is_google_rate_limit_error(e):
                logger.warning(f"Límite de cuota en API de Google alcanzado para job {job_id}: {e}")
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask="Límite de cuota alcanzado en API de Google. Trabajo pausado para reanudación posterior.",
                    status="paused"
                )
                self.stop()
            else:
                logger.warning(f"Error procesando PDF job {job_id}: {e}")
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask=f"Error en procesamiento: {str(e)}",
                    status="error"
                )

    async def process_message(self, message_id: str, message_fields: dict):
        action = message_fields.get("action")
        if action != "process_pdf":
            return

        job_id = message_fields.get("job_id")
        file_key = message_fields.get("file_key")
        file_hash = message_fields.get("file_hash", "")
        user_nombre_carrera = message_fields.get("nombre_carrera", "")

        if not job_id or not file_key:
            await self.redis.xack(STREAM_KEY, GROUP_NAME, message_id)
            return

        try:
            await self.process_pdf_job(
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                user_nombre_carrera=user_nombre_carrera
            )
        finally:
            await self.redis.xack(STREAM_KEY, GROUP_NAME, message_id)

    async def run(self):
        await self.init_consumer_group()
        self.running = True
        logger.warning(f"PdfProcessingWorker activo, escuchando en el stream '{STREAM_KEY}'...")

        while self.running:
            try:
                streams = await self.redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},
                    count=1,
                    block=2000
                )
                if not streams:
                    continue

                for _, messages in streams:
                    for msg_id, fields in messages:
                        await self.process_message(msg_id, fields)

            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                logger.warning(f"Error en bucle de PdfProcessingWorker: {e}")
                await asyncio.sleep(1)

        await self.disconnect()

    def stop(self):
        self.running = False


async def main():
    worker = PdfProcessingWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

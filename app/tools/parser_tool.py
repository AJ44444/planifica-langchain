import io
import re
import base64
from typing import List, Dict, Union, Any
from markitdown import MarkItDown, StreamInfo
from langchain_core.tools import tool
from middleware.security_middleware import sanitize_external_text


def convert_pdf_to_markdown(pdf_input: Union[bytes, io.BufferedIOBase, str, Any]) -> str:
    """
    Convierte un documento PDF recibido en memoria a Markdown utilizando MarkItDown.
    No admite ni procesa rutas de archivos en disco; la entrada debe ser un buffer de bytes en memoria (io.BytesIO / bytes)
    o una cadena codificada en base64. Sanitiza el contenido extraído contra inyecciones de prompt indirectas.

    Args:
        pdf_input: Bytes en memoria, buffer en memoria (io.BytesIO) o representación en Base64 / texto Markdown.

    Returns:
        str: El contenido procesado, sanitizado y convertido a Markdown.
    """
    md = MarkItDown()

    if isinstance(pdf_input, bytes):
        stream = io.BytesIO(pdf_input)
        result = md.convert(stream, stream_info=StreamInfo(mimetype="application/pdf", extension=".pdf"))

    elif isinstance(pdf_input, io.BufferedIOBase) or hasattr(pdf_input, "read"):
        result = md.convert(pdf_input, stream_info=StreamInfo(mimetype="application/pdf", extension=".pdf"))

    elif isinstance(pdf_input, str):
        # Procesar datos recibidos en Base64 exclusivamente en memoria
        if pdf_input.startswith("data:application/pdf;base64,") or len(pdf_input) > 200:
            clean_b64 = pdf_input.split(",")[-1]
            try:
                pdf_bytes = base64.b64decode(clean_b64)
                stream = io.BytesIO(pdf_bytes)
                result = md.convert(stream, stream_info=StreamInfo(mimetype="application/pdf", extension=".pdf"))
            except Exception:
                # Si la cadena es texto markdown directo en memoria
                return sanitize_external_text(pdf_input)
        else:
            return sanitize_external_text(pdf_input)
    else:
        raise ValueError("El parámetro pdf_input debe ser un objeto de bytes en memoria (bytes / io.BytesIO) o una cadena en Base64. No se admiten rutas de archivo en disco.")

    return sanitize_external_text(result.text_content, wrap_xml=True)


def extract_career_name(document: str) -> str:
    """
    Extrae dinámicamente el nombre de la carrera o programa de estudios.
    
    Args:
        document (str): El contenido Markdown a procesar.

    Returns:
        str: El nombre de la carrera u opción por defecto: No identificada.
    """
    lines = document.splitlines()

    for line in lines[:500]:
        m = re.search(r'(?i)(?:Curricul?um|Curr[ií]culum)\s+Nacional\s+Base\s*[-–—]\s*(.+)', line)
        if m:
            val = m.group(1).strip()
            val = re.sub(r'^\d+\s*', '', val).strip()
            if val:
                return val

    return "No identificada"


@tool
def parse_curricular_areas(pdf_source: Union[bytes, io.BufferedIOBase, str, Any]) -> List[Dict[str, str]]:
    """
    Analiza dinámicamente las áreas curriculares de un documento PDF recibido exclusivamente en memoria.
    No admite rutas de disco. Procesa el contenido en memoria y retorna las áreas curriculares con su contenido Markdown.
    
    Args:
        pdf_source: Bytes en memoria, buffer io.BytesIO o string Base64 del PDF.
    
    Returns:
        List[Dict[str, str]]: Lista de áreas curriculares procesadas con su contenido Markdown.
    """
    content = convert_pdf_to_markdown(pdf_source)

    career_name = extract_career_name(content)

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

    areas_list = []
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

    return areas_list
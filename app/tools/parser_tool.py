import io
import re
import base64
from typing import List, Dict
from langchain_core.tools import tool
from middleware.security_middleware import sanitize_external_text


def convert_pdf_to_markdown(pdf_base64: str) -> str:
    """
    Converts a Base64-encoded PDF document into Markdown format.

    Args:
        pdf_base64 (str): Base64-encoded PDF document string.

    Returns:
        str: Document content converted to Markdown format and sanitized.
    """
    if not isinstance(pdf_base64, str) or not pdf_base64.strip():
        raise ValueError("The 'pdf_base64' parameter must be a valid Base64 encoded string.")

    clean_b64 = pdf_base64.strip()
    if clean_b64.startswith("data:application/pdf;base64,"):
        clean_b64 = clean_b64.split(",")[-1].strip()

    try:
        pdf_bytes = base64.b64decode(clean_b64)
        if pdf_bytes.startswith(b"%PDF"):
            stream = io.BytesIO(pdf_bytes)
            md = MarkItDown()
            result = md.convert(stream, stream_info=StreamInfo(mimetype="application/pdf", extension=".pdf"))
            return sanitize_external_text(result.text_content, wrap_xml=True)
        else:
            text_content = pdf_bytes.decode("utf-8", errors="ignore")
            return sanitize_external_text(text_content, wrap_xml=True)
    except Exception:
        return sanitize_external_text(clean_b64, wrap_xml=True)


def extract_career_name(document: str) -> str:
    """
    Extracts the academic career or program name from the document.

    Args:
        document (str): Document content in Markdown format.

    Returns:
        str: Identified career name or 'Unidentified'.
    """
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
    """
    Extracts the general curricular structure table for the career.

    Args:
        document (str): Document content in Markdown format.

    Returns:
        str: Markdown block corresponding to the curricular structure table.
    """
    if not document or not isinstance(document, str):
        return ""

    career_name = extract_career_name(document)
    lines = document.splitlines()

    capturing = False
    captured_lines = []

    escaped_career = re.escape(career_name) if career_name != "Unidentified" else r'.+'
    table1_pattern = re.compile(
        r'(?i)(?:Tabla\s+(?:No\.?|N°|Nº)?\s*1\b|Estructura\s+de\s+' + escaped_career + r')'
    )
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

    return "\n".join(captured_lines).strip()


@tool("parse_curricular_areas")
def parse_curricular_areas(pdf_base64: str) -> List[Dict[str, str]]:
    """
    Parses and segmentates a PDF document into its corresponding curricular areas.

    Args:
        pdf_base64 (str): Base64 encoded string of the PDF document.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing the structure and Markdown content of each curricular area.
    """
    content = convert_pdf_to_markdown(pdf_base64)

    career_name = extract_career_name(content)

    structure_table = extract_curricular_structure_table(content)

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

    structure_item = {
        'index': 0,
        'career_name': career_name,
        'area_title': 'Estructura Curricular',
        'clean_name': 'Estructura Curricular',
        'content': structure_table
    }

    areas_list = [structure_item]
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
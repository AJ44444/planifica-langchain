import re
import unicodedata
import pypdfium2
from typing import List, Dict, Union
from langchain_core.tools import tool
from middleware.security_middleware import sanitize_external_text
from api.upload_handler import get_s3_client


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


@tool("parse_curricular_areas", description="Parses and segments a PDF document from Guatemala's National Basic Curriculum into curricular areas.")
def parse_curricular_areas(file_key: str) -> Union[List[Dict[str, str]], str]:
    pdf_bytes = fetch_pdf_bytes_from_s3(file_key)
    content = convert_pdf_bytes(pdf_bytes)
    career_name = extract_career_name(content)
    structure_table = extract_curricular_structure_table(content)

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
            structure_item = {
                'index': 0,
                'career_name': career_name,
                'area_title': 'Estructura Curricular',
                'clean_name': 'Estructura Curricular',
                'content': structure_table
            }
            areas_list.append(structure_item)
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
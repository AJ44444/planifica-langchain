---
name: process-pdf
description: Processes PDF documents from Guatemala's National Basic Curriculum.
tools: parse_curricular_areas, save_curricular_structure, generate_subarea_vector_embeddings
---

## Process PDF

1. **Extraction**
   - Extracts the curriculum structure in Guatemala's CNB format.

2. **Grade Identification & Structuring**
   - Uses the Curricular Structure to identify which grade each subarea belongs to.
   - The grade **must be included in the subarea name** (e.g. *Communication and Language Fourth Grade*, *Physical Education Fourth Grade*).
   - **Curricular Area**: Area name, area competencies, suggested activities, and evaluation criteria.
   - **Curricular Subarea**: Subarea name, competencies, indicators, and contents.
   - **Identifiers**: Must be simple numeric identifiers based on text (e.g. `id_competencia: '1'`, `id_indicador: '1.1'`, `id_contenido: '1.1.1'`).

3. **Structure Flattening**
   - Flattens each area structure into: `competencias_area`, `actividades_sugeridas`, `criterios_evaluacion_sugeridos`, and `subareas`.

4. **Persistence**
   - Saves the complete curricular structure for each area.

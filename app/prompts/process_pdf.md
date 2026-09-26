---
name: process-pdf
description: Processes PDF documents from Guatemala's National Basic Curriculum.
tools: parse_curricular_areas, save_curricular_structure, dispatch_subarea_vectorization
---

## Process PDF Workflow

- Keep competencies, indicators, and contents **textually identical** to how they appear in the document.
- For **Ciclo Básico** curricula (e.g. Mathematics containing 1st, 2nd, and 3rd grade sections), **each grade is treated as its own distinct career name** (e.g. *Primero Básico*, *Segundo Básico*, *Tercero Básico*). Each grade section MUST be saved under its corresponding grade/career name (`nombre_carrera`) so that the subarea competency tree is associated with the correct area and grade scope.

---

## Workflows

## 1. Save Curriculum
1. **Extraction & Parsing**
   - Execute `parse_curricular_areas` to convert and segment the document into curricular areas.
   - If `parse_curricular_areas` returns `career_name: "Unidentified"` (or if the career/program name cannot be determined), **you must ask the user to provide the career/grade name** (e.g. *Primero Básico*, *Primer Grado*, *Bachillerato en Ciencias y Letras con Orientación en Computación*, etc.) before calling persistence tools.

2. **Grade Identification & Area Structuring**
   - **Curricular Area**: Area name (`nombre_area`), suggested activities (`actividades_sugeridas`), and evaluation criteria (`criterios_evaluacion_sugeridos`).
   - **Separating Evaluation Criteria in Ciclo Básico**: In Ciclo Básico curricula, evaluation criteria (*Criterios de evaluación*) are located inside the competency table alongside competencies, indicators, and contents. Extract these evaluation criteria from the competency table and aggregate them into the area's `criterios_evaluacion_sugeridos` array, separating them from the subarea competency tree.
   - **Curricular Subarea**: Subarea name (`nombre_subarea`), competencies (`competencias`), achievement indicators (`indicadores_logro`), and contents (`contenidos`).
   - The grade name **must be included in the subarea name** when applicable (e.g. *Matemáticas Primero Básico*).
   - **Identifiers**: Use simple numeric identifiers based on text (e.g. `id_competencia: '1'`, `id_indicador: '1.1'`, `id_contenido: '1.1.1'`).

3. **Structure Flattening & Persistence**
   - Flatten each area structure into: `nombre_carrera`, `nombre_area`, `actividades_sugeridas`, `criterios_evaluacion_sugeridos`, and `subareas`.
   - Call `save_curricular_structure` to save the complete area and subarea structure first.

4. **Vectorization Event Dispatch**
   - After `save_curricular_structure` has persisted the structure, obtain the subarea IDs (`id_subarea`) returned by `save_curricular_structure`.
   - Call `dispatch_subarea_vectorization` for each `id_subarea` to trigger background vector embeddings generation.

---
name: process-pdf
description: Processes PDF documents from Guatemala's National Basic Curriculum.
tools: parse_curricular_areas, save_curricular_structure, generate_subarea_vector_embeddings
---

## Process PDF

1. **Extracción**
   - Extrae la estructura del currículo con formato CNB de Guatemala.

2. **Identificación de Grados y Estructuración**
   - Utiliza la Estructura Curricular para identificar a qué grado pertenece cada subárea.
   - El grado **debe incluirse en el nombre de la subárea** (ej. *Comunicación y Lenguaje Cuarto Grado*, *Educación Física Cuarto Grado*).
   - **Área Curricular**: Nombre del área, competencias del área, actividades sugeridas y criterios de evaluación.
   - **Subárea Curricular**: Nombre de la subárea, competencias, indicadores y contenidos.
   - **Identificadores**: Deben ser numéricos simples según el texto (ej. `id_competencia: '1'`, `id_indicador: '1.1'`, `id_contenido: '1.1.1'`).

3. **Aplanamiento de la Estructura**
   - Aplana la estructura de cada área en: `competencias_area`, `actividades_sugeridas`, `criterios_evaluacion_sugeridos` y `subareas`.

4. **Persistencia**
   - Guarda la estructura curricular completa de cada área.

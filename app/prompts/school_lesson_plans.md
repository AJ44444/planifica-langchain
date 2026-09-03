---
name: lesson-plans
description: Class schedule management.
tools: search_curriculum_vector_db, save_lesson_plan, get_paginated_lesson_plans, get_planification_by_id, update_lesson_plan, delete_lesson_plan
---

## Lesson Plans

- Mantén las competencias, indicadores y contenidos **textualmente igual** como se encuentran en el árbol curricular.

---

## Flujos de Trabajo

### 1. Crear Planificación Directa
1. **Verificar**
   - El grado del usuario **debe coincidir** con el grado de la subárea (no se permite elaborar planificaciones para otro grado).

2. **Obtener Árbol Curricular**
   - Solicita el árbol curricular con la subárea seleccionada.

3. **Aplanamiento y Redacción**
   - Al recibir `arbol_curricular`, aplana la estructura en competencia, indicador y contenido en filas de desarrollo curricular. Cada competencia es una fila de desarrollo curricular (no mezclar indicadores o contenidos que no pertenezcan a su nodo padre).
   - Redacta entre **3 y 5 actividades de aprendizaje** por competencia de forma impersonal con verbos en infinitivo (`Presentar...`, `Analizar...`, `Desarrollar...`).
   - Las descripciones deben ser de **máximo 50 palabras** por actividad.

4. **Guardar Planificación**
   - Guarda la planificación. Si faltan metadatos o datos de encabezado, solicítalos para completar el registro.

### 2. Crear Planificaciones en Cascada (a partir de una existente)
1. **Identificar el Objetivo**
   - **Plan semestral**: Desglosa la Planificación Anual provista en dos semestres.
   - **Plan bimestral**: Divide la Planificación Semestral provista en bloques de dos meses.
   - **Plan semanal**: Convierte la Planificación Bimestral provista en unidades didácticas semanales.
   - **Plan diario**: Transforma la Planificación Semanal o general en sesiones de clase detalladas por día.

2. **Historial de Planificaciones**
   - Consulta el listado de planificaciones para identificar la planificación deseada.

3. **Detalle de Planificación**
   - Busca la planificación seleccionada para obtener su detalle.

4. **Validar Duración**
   - Identifica si la duración de la planificación es **mayor a un día**. Si no es así, no es posible crear planificaciones en cascada a partir de ella.

5. **Preservar Parámetros**
   - Utiliza la misma cantidad y duración de periodos. Utiliza textualmente las competencias, indicadores y contenidos.

6. **Dosificación y Redacción**
   - Dosifica los contenidos y redacta entre 3 y 5 actividades de aprendizaje en infinitivo (máximo 50 palabras por actividad).

7. **Estructuración**
   - Aplana la estructura en competencia, indicador y contenido en filas de desarrollo curricular.

8. **Persistencia**
   - Guarda las planificaciones.

### 3. Consultar Planificaciones
1. **Consultar**
   - Consulta el listado de planificaciones para ubicar la planificación objetivo.

2. **Mostrar**
   - Consultar el detalle de la planificación.

### 4. Actualizar Planificaciones
1. **Consultar**
   - Consulta el listado de planificaciones para ubicar la planificación objetivo.

2. **Actualizar**
   - Modifica únicamente los campos solicitados.

### 5. Eliminar Planificaciones
1. **Consultar**
   - Consulta el listado de planificaciones.

2. **Eliminar**
   - Elimina la planificación (requiere confirmación explícita).

---
name: assessment-instruments
description: Manage assessment instruments.
tools: get_learning_activity_by_id, save_assessment_instrument, get_assessment_instrument_by_id, update_assessment_instrument, delete_assessment_instrument
---

## Assessment Instruments

- To **query, update, or delete**, request `id_instrumento`.
- **Title (`titulo`)**:
    - Must be clear, concise, and direct.
    - Do NOT include the instrument type in the title (e.g. do not write "Rubric for...", "Checklist...", "Rating scale...").
    - Do NOT include the activity to which it belongs (e.g. do not write "for Activity 1...", "Activity: ...").
    - Do NOT include the purpose (e.g. do not write "with the purpose of...", "to evaluate...").
- **Scale (`escala`)**:
    - Must NOT include points, scores, or numeric values (e.g. no "10 pts", "5 points", etc.). Use strictly qualitative and descriptive performance levels.

* **Register**
    - Query the learning activity.
    - Select the appropriate instrument type: `lista_cotejo`, `rubrica`, or `escala_rango`.
    - Set a clear title following the title rules (without instrument type, without activity reference, and without purpose).
    - Design the instrument considering the pedagogical complexity of the activity:
        - For `lista_cotejo` (checklist) instruments, do not include criterion definitions; the `definiciones` field for each criterion must remain empty (`[]`).
        - The performance scale must not include points or numeric values.
    - Save the assessment instrument.

* **Query**
    - Query the assessment instrument.

* **Update**
    - Modify only the requested fields.

* **Delete**
    - Delete the assessment instrument (requires explicit confirmation).

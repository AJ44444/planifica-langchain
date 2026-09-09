---
name: assessment-instruments
description: Manage assessment instruments.
tools: get_learning_activity_by_id, save_assessment_instrument, get_assessment_instrument_by_id, update_assessment_instrument, delete_assessment_instrument
---

## Assessment Instruments

- To **query, update, or delete**, request `id_instrumento`.

* **Register**
    - Query the learning activity.
    - Select the appropriate instrument type: `lista_cotejo`, `rubrica`, or `escala_rango`.
    - Design the instrument considering the pedagogical complexity of the activity:
        - For `lista_cotejo` (checklist) instruments, do not include criterion definitions; the `definiciones` field for each criterion must remain empty (`[]`).
    - Save the assessment instrument.

* **Query**
    - Query the assessment instrument.

* **Update**
    - Modify only the requested fields.

* **Delete**
    - Delete the assessment instrument (requires explicit confirmation).

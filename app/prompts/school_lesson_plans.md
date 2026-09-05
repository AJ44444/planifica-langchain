---
name: lesson-plans
description: Class schedule management.
tools: search_curriculum_vector_db, save_lesson_plan, get_paginated_lesson_plans, get_planification_by_id, update_lesson_plan, delete_lesson_plan
---

## Lesson Plans

- Keep competencies, indicators, and contents **textually identical** to how they appear in the curriculum tree.

---

## Workflows

### 1. Create Lesson Plan
1. **Verify**
   - The user's grade **must match** the subarea grade (creating lesson plans for another grade is not allowed).

2. **Obtain Curriculum Tree**
   - Request the curriculum tree for the selected subarea.

3. **Flattening and Redaction**
   - Upon receiving `arbol_curricular`, flatten the structure into competency, indicator, and content in curricular development rows. Each competency is a curricular development row (do not mix indicators or contents not belonging to their parent node).
   - Write between **3 and 5 learning activities** per competency in impersonal form starting with infinitive verbs (`Present...`, `Analyze...`, `Develop...`).
   - Descriptions must be a **maximum of 50 words** per activity.

4. **Persistence**
   - Save the lesson plan. If metadata or header data is missing, request it to complete registration.

### 2. Create Cascade Lesson Plans (from an existing plan)
1. **Identify Goal**
   - **Semester plan**: Break down the provided Annual Plan into two semesters.
   - **Bimonthly plan**: Divide the provided Semester Plan into two-month blocks.
   - **Weekly plan**: Convert the provided Bimonthly Plan into weekly didactic units.
   - **Daily plan**: Transform the provided Weekly or general Plan into detailed daily class sessions.

2. **Lesson Plan History**
   - Query the lesson plan list to identify the target lesson plan.

3. **Lesson Plan Details**
   - Search the selected lesson plan to retrieve its full details.

4. **Validate Duration**
   - Identify whether the duration of the lesson plan is **greater than 1 day**. If not, cascade lesson plans cannot be created from it.

5. **Preserve Parameters**
   - Use the same number and duration of periods. Use competencies, indicators, and contents textually.

6. **Dosage and Redaction**
   - Dose contents and write between 3 and 5 learning activities in infinitive form (maximum 50 words per activity).

7. **Structuring**
   - Flatten structure into competency, indicator, and content in curricular development rows.

8. **Persistence**
   - Save the lesson plans.

### 3. Query Lesson Plans
1. **Query**
   - Query the lesson plan list to locate the target lesson plan.

2. **Display**
   - Query the details of the lesson plan.

### 4. Update Lesson Plans
1. **Query**
   - Query the lesson plan list to locate the target lesson plan.

2. **Update**
   - Modify only the requested fields.

### 5. Delete Lesson Plans
1. **Query**
   - Query the lesson plan list.

2. **Delete**
   - Delete the lesson plan (requires explicit confirmation).

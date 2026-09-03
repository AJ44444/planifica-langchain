from core import load_prompt


def test_load_prompt_existing_md_files():
    prompts_to_test = [
        "supervisor.md",
        "process_pdf.md",
        "school_lesson_plans.md",
        "school_assessment_instruments.md",
        "school_multimodal_resources.md",
        "specialized_queries.md"
    ]

    for p_name in prompts_to_test:
        content = load_prompt(p_name)
        assert isinstance(content, str)
        assert len(content) > 0
        without_ext = p_name.replace(".md", "")
        content_no_ext = load_prompt(without_ext)
        assert content_no_ext == content

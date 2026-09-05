import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
PROMPTS_DIR = os.path.join(APP_DIR, "prompts")


def load_prompt(filename: str) -> str:
    """
    Reads and loads system prompt content from a Markdown (.md) file in the 'prompts' directory using UTF-8 encoding.

    Args:
        filename (str): Name of the Markdown file (with or without .md extension).

    Returns:
        str: Textual content of the system prompt.
    """
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    file_path = os.path.join(PROMPTS_DIR, filename)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

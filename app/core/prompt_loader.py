import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
PROMPTS_DIR = os.path.join(APP_DIR, "prompts")


def load_prompt(filename: str) -> str:
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    file_path = os.path.join(PROMPTS_DIR, filename)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

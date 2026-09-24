from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / (filename if filename.endswith(".md") else f"{filename}.md")
    return path.read_text(encoding="utf-8").strip()

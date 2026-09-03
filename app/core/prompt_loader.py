import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
PROMPTS_DIR = os.path.join(APP_DIR, "prompts")


def load_prompt(filename: str) -> str:
    """
    Lee y carga el contenido de un archivo Markdown (.md) de prompt de sistema desde la carpeta 'prompts' con decodificación UTF-8.

    Args:
        filename (str): Nombre del archivo Markdown (con o sin extensión .md).

    Returns:
        str: Contenido textual del prompt de sistema.
    """
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    file_path = os.path.join(PROMPTS_DIR, filename)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

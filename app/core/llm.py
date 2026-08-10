import os
from langchain_deepseek import ChatDeepSeek
from core.config import DEEPSEEK

if not DEEPSEEK:
    raise ValueError("La variable de entorno DEEPSEEK_API_KEY no está configurada en .env.")

llm = ChatDeepSeek(
    model="deepseek-v4-flash",
    api_key=DEEPSEEK,
    temperature=0.7,
    max_tokens=4096,
    timeout=None,
    max_retries=3
)
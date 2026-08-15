from langchain_deepseek import ChatDeepSeek
from core.config import DEEPSEEK

if not DEEPSEEK:
    raise ValueError("La variable de entorno DEEPSEEK_API_KEY no está configurada en .env.")

llm = ChatDeepSeek(
    model="deepseek-v4-flash",
    api_key=DEEPSEEK,
    temperature=0.3,
    max_tokens=8192,
    timeout=60.0,
    max_retries=0
)
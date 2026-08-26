from langchain_deepseek import ChatDeepSeek
from core.config import get_env_variable

llm = ChatDeepSeek(
    model="deepseek-v4-flash",
    api_key=get_env_variable("DEEPSEEK_API_KEY"),
    temperature=0.3,
    max_tokens=8192,
    timeout=60.0,
    max_retries=0
)
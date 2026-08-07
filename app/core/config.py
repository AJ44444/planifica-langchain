import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")
DB = os.getenv("DB_URI")
DB_NAME = os.getenv("DB_NAME", "planifica_db")
SERPER = os.getenv("SERPER_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
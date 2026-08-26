import os
import pytest

# Configurar variables de entorno mínimas para el entorno de ejecución de pruebas de pytest
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-deepseek-key-for-pytest")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key-for-pytest")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id-for-pytest")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "planifica_test_db")
os.environ.setdefault("SERPER_API_KEY", "test-serper-key-for-pytest")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_12345")

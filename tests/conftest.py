import os
import pytest

# Configurar variables de entorno mínimas para el entorno de ejecucion de pruebas de pytest
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-deepseek-key-for-pytest")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key-for-pytest")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id-for-pytest")

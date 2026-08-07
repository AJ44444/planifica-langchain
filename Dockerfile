# ==============================================================================
# DOCKERFILE PRODUCCIÓN PARA SISTEMA MULTIAGENTE PLANIFICA (LANGGRAPH SERVER)
# ==============================================================================

FROM python:3.11-slim

# Evitar la escritura de archivos .pyc y forzar buffer de salida para logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instalar dependencias del sistema operativo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar manifiesto de dependencias para aprovechar la caché de capas de Docker
COPY pyproject.toml README.md ./

# Actualizar pip e instalar dependencias del proyecto incluyendo markitdown[pdf] y langgraph-cli
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copiar el paquete app/ y la especificación oficial langgraph.json
COPY app/ ./app/
COPY langgraph.json ./

# Puerto expuesto para LangGraph Server
EXPOSE 2024

# Comando por defecto para iniciar el servidor de produccion de LangGraph Server
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "2024"]

# Sistema Multiagente Educativo "Planifica" 🚀

**Planifica** es una plataforma educativa inteligente impulsada por una arquitectura **Multiagente con LangGraph Server**. Diseñada para automatizar la extracción curricular, la elaboración de planificaciones docentes y el diseño de instrumentos de evaluación alineados al **Currículum Nacional Base (CNB) de Guatemala**.

---

## 🌟 Características Principales

* **Arquitectura Jerárquica de 5 Subagentes**: Un grafo supervisor enruta dinámicamente las solicitudes hacia agentes altamente especializados.
* **Procesamiento de PDF en Memoria**: Extracción y análisis de documentos PDF del CNB directamente en memoria mediante `MarkItDown[pdf]`, sin persistencia temporal en disco.
* **Búsqueda Vectorial Semántica de 768 Dimensiones**: Búsqueda sobre el CNB implementada con `$vectorSearch` de **MongoDB Atlas Search** utilizando el modelo oficial **Google Gemini `gemini-embedding-2`**.
* **Autenticación Nativa de Producción (Google OAuth)**: Middleware integrado en LangGraph Server que valida el token de ID de Google y registra automáticamente al usuario en MongoDB por su `google_id`.
* **Modelos de Respuesta Estructurada (Pydantic)**: Garantía de salidas estrictamente tipadas para planificaciones, rúbricas, listas de cotejo y recursos multimodales.
* **Seguridad y Privacidad de Datos**: Aislamiento estricto de sesiones y documentos por `user_id` del docente autenticado.

---

## 🧠 Arquitectura del Sistema Multiagente

```mermaid
flowchart TD
    Client["Docente / Cliente Web (Google Bearer Auth)"] --> Auth["Auth Middleware (Google OAuth ID Token)"]
    Auth --> Supervisor["Agente Supervisor (app/graph.py)"]
    
    Supervisor --> AgentPDF["Subagente Procesador de PDF"]
    Supervisor --> AgentPlans["Subagente Planificador de Clases"]
    Supervisor --> AgentAssess["Subagente Instrumentos de Evaluación"]
    Supervisor --> AgentMulti["Subagente Recursos Multimodales"]
    Supervisor --> AgentQuery["Subagente Consultas Especializadas"]

    AgentPDF --> Parser["ParserTool (MarkItDown en memoria)"]
    AgentPlans --> VectorDB[("MongoDB Atlas ($vectorSearch)")]
    AgentMulti --> Serper["Serper API (Búsqueda Web/YouTube)"]
    
    AgentPDF --> DB[("MongoDB (CNB / Planificaciones)")]
    AgentPlans --> DB
    AgentAssess --> DB
    AgentMulti --> DB
    AgentQuery --> DB
```

### Subagentes Especializados

1. **`process_pdf`**: Procesa documentos PDF curriculares en memoria, extrae áreas y subáreas, y genera embeddings de 768 dimensiones.
2. **`school_lesson_plans`**: Elabora y gestiona planificaciones docentes (diarias, semanales, bimestrales, semestrales, anuales) alineadas al CNB.
3. **`school_assessment_instruments`**: Diseña rúbricas, listas de cotejo y escalas de rango para actividades de aprendizaje.
4. **`school_multimodal_resources`**: Explora la web en tiempo real para vincular videos, imágenes y recursos educativos.
5. **`specialized_queries`**: Atiende los datos analíticos del dashboard, catálogo de carreras/áreas del CNB e historial paginado.

---

## 📂 Estructura del Proyecto

```plaintext
planifica-langchain/
├── app/                        # Paquete principal del código fuente
│   ├── agents/                 # Subagentes y Agente Supervisor
│   ├── auth/                   # Handler de autenticación Google OAuth (langgraph_sdk.Auth)
│   ├── core/                   # Configuración, LLM (DeepSeek), colecciones y DTOs Pydantic
│   ├── memory/                 # Persistencia PostgresSaver y MongoDBSaver
│   ├── prompts/                # Prompts de sistema para cada agente
│   └── tools/                  # Herramientas (Parser, Vector Search, Web Search, Persistencia)
├── tests/                      # Suite de pruebas unitarias
│   ├── test_files/             # Archivos reales del CNB para evaluación
│   ├── test_auth.py            # Pruebas del flujo de autenticación Google OAuth
│   ├── test_process_pdf.py     # Pruebas del parser en memoria
│   ├── test_lesson_plans.py    # Pruebas de búsqueda vectorial
│   └── test_multimodal_resources.py # Pruebas de búsqueda web
├── Dockerfile                  # Contenedor de producción para LangGraph Server
├── langgraph.json              # Configuración oficial de LangGraph Server
├── pyproject.toml              # Dependencias del proyecto
└── main.py                     # Runner CLI de desarrollo local
```

---

## 🛠️ Variables de Entorno (`.env`)

Para desplegar el contenedor en cualquier infraestructura (Kubernetes, Cloud Run, AWS ECS, Docker), inyecta las siguientes variables de entorno:

```bash
# === Conexiones a Bases de Datos y Cachening ===
DATABASE_URI="postgres://usuario:password@host_postgres:5432/db_name?sslmode=require"
REDIS_URI="redis://host_redis:6379"
MONGODB_URI="mongodb+srv://usuario:password@cluster.mongodb.net/planifica_db"
DB_NAME="planifica_db"

# === Licencia y Autenticación del Servidor ===
# Para Producción Self-Hosted:
LANGGRAPH_CLOUD_LICENSE_KEY="tu-licencia-oficial-de-langgraph-cloud"

# Para Desarrollo / Pruebas Locales (alternativa):
LANGSMITH_API_KEY="lsv2_pt_tu_api_key_de_langsmith"

# === Tracing y Observabilidad (LangSmith) ===
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_PROJECT="Planifica"

# === Autenticación de Usuarios y Runtime ===
GOOGLE_CLIENT_ID="tu-google-client-id.apps.googleusercontent.com"
JWT_SECRET="tu-jwt-secret-de-firma"
LANGGRAPH_AUTH='{"path": "/deps/planifica-langchain/app/auth/auth_handler.py:auth", "openapi": {"securitySchemes": {"cookieAuth": {"type": "apiKey", "in": "cookie", "name": "access_token", "description": "Cookie HTTP segura (HttpOnly, SameSite=Lax, Secure) que contiene el Access Token JWT de sesión (expiración 5 min)"}}, "security": [{"cookieAuth": []}]}}'
LANGGRAPH_HTTP='{"app": "./app/server.py:app", "enable_custom_route_auth": true, "cors": {"allow_origins": ["https://app.planifica.study"], "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Cookie"], "allow_credentials": true, "max_age": 600}}'
LANGSERVE_GRAPHS='{"supervisor": "/deps/planifica-langchain/app/graph.py:supervisor_graph"}'

# === Llaves de APIs Externas ===
DEEPSEEK_API_KEY="sk-tu-api-key-de-deepseek"
GOOGLE_API_KEY="tu-google-api-key-para-embeddings-768d"
SERPER_API_KEY="tu-serper-api-key"
```

---

## 🚀 Construcción y Despliegue en Producción

### 1. Construir la Imagen de Producción con LangGraph CLI

```bash
# Construir la imagen Docker optimizada para producción
langgraph build -t planifica-langgraph-server:latest
```

### 2. Ejecutar el Contenedor de Producción

```bash
docker run -d \
  --name planifica-langgraph-server \
  -p 8000:8000 \
  --env-file .env \
  planifica-langgraph-server:latest
```

El servidor estará listo para recibir solicitudes con el encabezado de autenticación HTTP:
`Authorization: Bearer <ID_TOKEN_GOOGLE_OAUTH>`

---

## 🧪 Ejecución de Pruebas Unitarias

```bash
python -m pytest tests/ -v
```

---

## 📜 Licencia

Desarrollado para el ecosistema educativo **Planifica**. Todos los derechos reservados.

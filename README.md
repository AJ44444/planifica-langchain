# Sistema Multiagente Educativo "Planifica" 🚀

**Planifica** es una plataforma educativa inteligente impulsada por un arquitectura **Multiagente con LangGraph Server (LangChain)**. Diseñada para automatizar la extracción curricular, la elaboración de planificaciones docentes y el diseño de instrumentos de evaluación alineados al **Currículum Nacional Base (CNB) de Guatemala**.

---

## 🌟 Características Principales

* **Arquitectura Jerárquica de 5 Subagentes**: Un grafo supervisor enruta dinámicamente las solicitudes hacia agentes altamente especializados.
* **Procesamiento de PDF en Memoria**: Extracción y análisis de documentos PDF del CNB directamente en memoria mediante `MarkItDown[pdf]`, sin persistencia temporal en disco.
* **Búsqueda Vectorial Semántica de 768 Dimensiones**: Búsqueda sobre el CNB implementada con `$vectorSearch` de **MongoDB Atlas Search** utilizando el modelo oficial **Google Gemini `text-embedding-004`**.
* **Autenticación Nativa de Producción (Google OAuth)**: Middleware integrado en LangGraph Server que valida el token de ID de Google y registra automáticamente al usuario en MongoDB por su `google_id`.
* **Modelos de Respuesta Estructurada (Pydantic / DTO)**: Garantía de salidas estrictamente tipadas en formato YAML para planificaciones, rubricas, listas de cotejo y recursos multimodales.
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

1. **`call_process_pdf_agent`**: Procesa documentos PDF curriculares en memoria, extrae áreas y subáreas, y genera vectores de embedding (768d).
2. **`call_school_lesson_plans_agent`**: Elabora y gestiona planificaciones docentes (diarias, semanales y bimestrales) alineadas al CNB.
3. **`call_school_assessment_instruments_agent`**: Diseña rúbricas, listas de cotejo y escalas de rango para actividades de aprendizaje.
4. **`call_school_multimodal_resources_agent`**: Explora la web en tiempo real mediante Serper API para vincular videos, imágenes y recursos educativos.
5. **`call_specialized_queries_agent`**: Atiende los datos analíticos del dashboard, catálogo de carreras/áreas del CNB e historial paginado.

---

## 📂 Estructura del Proyecto

```plaintext
planifica-langchain/
├── app/                        # Paquete principal del código fuente
│   ├── agents/                 # Subagentes y Agente Supervisor
│   ├── auth/                   # Handler de autenticación Google OAuth (langgraph_sdk.Auth)
│   ├── core/                   # Configuración, LLM (DeepSeek), colecciones y DTOs Pydantic
│   ├── memory/                 # Persistencia MongoDBSaver e índices automáticos
│   ├── prompts/                # Prompts de sistema para cada agente
│   └── tools/                  # Herramientas (Parser, Vector Search, Web Search, Persistencia)
├── tests/                      # Suite de pruebas unitarias
│   ├── test_files/             # Archivos reales del CNB para evaluación
│   ├── test_auth.py            # Pruebas del flujo de autenticación Google OAuth
│   ├── test_process_pdf.py     # Pruebas del parser en memoria
│   ├── test_lesson_plans.py    # Pruebas de búsqueda vectorial
│   └── test_multimodal_resources.py # Pruebas de búsqueda web
├── Dockerfile                  # Contenedor de producción para LangGraph Server
├── docker-compose.yml          # Orquestación de contenedores
├── langgraph.json              # Configuración oficial de LangGraph Server
├── pyproject.toml              # Dependencias del proyecto (markitdown[pdf], langgraph, etc.)
└── main.py                     # Runner CLI de desarrollo local
```

---

## 🛠️ Variables de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
DEEPSEEK_API_KEY="sk-tu-api-key-de-deepseek"
GOOGLE_API_KEY="tu-google-api-key-para-embeddings-768d"
DB_URI="mongodb+srv://usuario:password@cluster.mongodb.net"
DB_NAME="planifica_db"
SERPER_API_KEY="tu-serper-api-key"
GOOGLE_CLIENT_ID="tu-google-client-id.apps.googleusercontent.com"
```

---

## 🚀 Instalación y Ejecución

### 1. Desarrollo Local

```bash
# Clonar e instalar dependencias en entorno virtual
python -m venv .venv
.venv\Scripts\activate  # En Windows
pip install -e .

# Verificar compilación del grafo y servicios
python main.py

# Iniciar servidor de desarrollo de LangGraph CLI
langgraph dev --host 0.0.0.0 --port 2024
```

### 2. Despliegue con Docker Compose (Producción)

```bash
# Construir y levantar el contenedor de produccion
docker-compose up --build -d
```

El servidor quedará disponible en `http://localhost:2024` procesando solicitudes con encabezado HTTP:
`Authorization: Bearer <ID_TOKEN_GOOGLE_OAUTH>`

---

## 🧪 Ejecución de Pruebas Unitarias

Para ejecutar el conjunto completo de pruebas automatizadas:

```bash
python -m pytest tests/ -v
```

---

## 📜 Licencia

Desarrollado para el ecosistema educativo **Planifica**. Todos los derechos reservados.

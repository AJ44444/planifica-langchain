from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.parser_tool import parse_curricular_areas
from tools.persistence_tool import save_curricular_structure
from tools.vector_tool import generate_subarea_vector_embeddings
from middleware.security_middleware import SecurityGuardrailMiddleware
from core import load_prompt

agent = create_agent(
    model=llm,
    tools=[parse_curricular_areas, save_curricular_structure, generate_subarea_vector_embeddings],
    system_prompt=load_prompt("process_pdf.md"),
    name="procesador_pdf_cnb",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
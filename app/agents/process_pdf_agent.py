from langchain.agents import create_agent
from core.llm import llm
from tools.parser_tool import parse_curricular_areas
from tools.persistence_tool import save_curricular_structure
from tools.vector_tool import generate_subarea_vector_embeddings
from prompts.system_prompts import SYSTEM_PROMPT_PROCESS_PDF

agent = create_agent(
    model=llm,
    tools=[parse_curricular_areas, save_curricular_structure, generate_subarea_vector_embeddings],
    system_prompt=SYSTEM_PROMPT_PROCESS_PDF
)
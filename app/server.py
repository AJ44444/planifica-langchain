import asyncio
import logging
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.routing import Route
from api.auth_handler import login_with_google, logout, verify_session
from api.lesson_plan_handler import get_paginated_lesson_plans_endpoint, get_lesson_plan_details_endpoint
from api.upload_handler import generate_presigned_url_endpoint
from api.notifications_handler import notifications_sse_endpoint
from api.process_pdf_handler import process_pdf_endpoint
from workers.pdf_worker import PdfProcessingWorker
from workers.vectorization_worker import VectorizationWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")


@asynccontextmanager
async def lifespan(app: Starlette):
    logger.info("Iniciando workers de procesamiento de PDF y vectorización en segundo plano...")
    pdf_worker = PdfProcessingWorker()
    vec_worker = VectorizationWorker()
    pdf_task = asyncio.create_task(pdf_worker.run())
    vec_task = asyncio.create_task(vec_worker.run())
    try:
        yield
    finally:
        logger.info("Deteniendo workers en segundo plano...")
        pdf_worker.stop()
        vec_worker.stop()
        pdf_task.cancel()
        vec_task.cancel()
        await asyncio.gather(pdf_task, vec_task, return_exceptions=True)


routes = [
    Route("/auth/login", endpoint=login_with_google, methods=["POST", "OPTIONS"]),
    Route("/auth/logout", endpoint=logout, methods=["POST", "OPTIONS"]),
    Route("/auth/verify", endpoint=verify_session, methods=["GET", "OPTIONS"]),
    Route("/api/lesson-plans", endpoint=get_paginated_lesson_plans_endpoint, methods=["GET", "OPTIONS"]),
    Route("/api/lesson-plans/{id_planificacion}", endpoint=get_lesson_plan_details_endpoint, methods=["GET", "OPTIONS"]),
    Route("/api/generate-url", endpoint=generate_presigned_url_endpoint, methods=["GET", "OPTIONS"]),
    Route("/api/notifications", endpoint=notifications_sse_endpoint, methods=["GET", "OPTIONS"]),
    Route("/api/process-pdf", endpoint=process_pdf_endpoint, methods=["POST", "OPTIONS"]),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)


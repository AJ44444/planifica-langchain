import json
import hashlib
from starlette.requests import Request
from starlette.responses import JSONResponse
from redis.asyncio import from_url
from core.config import get_env_variable
from workers.pdf_worker import fetch_pdf_bytes_from_s3

STREAM_PDF = "stream:process_pdf"
STREAM_KEY = STREAM_PDF
NOTIFICATION_CHANNEL = "channel:notifications"


async def process_pdf_endpoint(request: Request) -> JSONResponse:
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    try:
        raw_body = await request.json()
        body = raw_body if isinstance(raw_body, dict) else {}
    except Exception:
        body = {}

    file_key = str(body.get("file_key", "")).strip()
    nombre_carrera = str(body.get("nombre_carrera", "")).strip()
    if not file_key:
        return JSONResponse(
            {"detail": "Field 'file_key' is required in request body."},
            status_code=400
        )

    try:
        pdf_bytes = fetch_pdf_bytes_from_s3(file_key)
    except Exception as e:
        return JSONResponse(
            {"detail": f"Error fetching PDF file from S3 bucket: {str(e)}"},
            status_code=400
        )

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    idempotency_key = f"idempotency:process_pdf:{file_key}:{file_hash}"

    redis_uri = get_env_variable("REDIS_URI")
    redis_client = from_url(redis_uri, decode_responses=True)

    try:
        existing_job_id = await redis_client.get(idempotency_key)
        if existing_job_id:
            existing_job_json = await redis_client.get(f"job:{existing_job_id}:status")
            if existing_job_json:
                existing_job = json.loads(existing_job_json)
                if existing_job.get("status") in ("progress", "finish"):
                    return JSONResponse(
                        {
                            "status": "success",
                            "message": "El archivo PDF ya fue procesado o se encuentra en proceso.",
                            "job_id": existing_job_id
                        },
                        status_code=200
                    )

        job_id = f"job_{file_hash[:16]}"
        job_data = {
            "id": job_id,
            "file_key": file_key,
            "file_hash": file_hash,
            "nombre_carrera": nombre_carrera,
            "main_task": "Procesar Currículum",
            "subtask": "Petición recibida. Encolando procesamiento de PDF",
            "status": "progress"
        }

        json_job = json.dumps(job_data, ensure_ascii=False)

        await redis_client.set(idempotency_key, job_id, ex=86400)
        await redis_client.set(f"job:{job_id}:status", json_job)

        await redis_client.xadd(
            STREAM_KEY,
            {
                "action": "process_pdf",
                "job_id": job_id,
                "file_key": file_key,
                "file_hash": file_hash,
                "nombre_carrera": nombre_carrera
            }
        )

        await redis_client.publish(NOTIFICATION_CHANNEL, json_job)

        return JSONResponse(
            {
                "status": "success",
                "message": "Trabajo de procesamiento de PDF iniciado exitosamente.",
                "job_id": job_id
            },
            status_code=200
        )

    except Exception as err:
        return JSONResponse(
            {"detail": f"Internal server error initiating PDF process: {str(err)}"},
            status_code=500
        )
    finally:
        await redis_client.aclose()

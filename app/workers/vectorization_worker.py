import asyncio
import json
import logging
from typing import Optional, Dict, Any
from redis.asyncio import Redis, from_url
from core.config import get_env_variable
from tools.vector_tool import generate_and_store_subarea_embeddings, is_google_rate_limit_error

logger = logging.getLogger(__name__)

STREAM_KEY = "stream:jobs"
GROUP_NAME = "group:vectorization_workers"
CONSUMER_NAME = "vectorization-worker-1"
NOTIFICATION_CHANNEL = "channel:notifications"


class VectorizationWorker:

    def __init__(self):
        self.redis_uri = get_env_variable("REDIS_URI")
        self.redis: Optional[Redis] = None
        self.running = False

    async def connect(self):
        if not self.redis:
            self.redis = from_url(self.redis_uri, decode_responses=True)

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()
            self.redis = None

    async def init_consumer_group(self):
        await self.connect()
        try:
            await self.redis.xgroup_create(
                name=STREAM_KEY,
                groupname=GROUP_NAME,
                id="0",
                mkstream=True
            )
        except Exception as e:
            logger.info(f"Consumer group '{GROUP_NAME}' status: {e}")

    async def publish_job_status(self, job_id: str, file_key: str, file_hash: str, main_task: str, subtask: str, status: str) -> Dict[str, Any]:
        await self.connect()
        job_payload = {
            "id": job_id,
            "file_key": file_key,
            "file_hash": file_hash,
            "main_task": main_task,
            "subtask": subtask,
            "status": status
        }
        json_msg = json.dumps(job_payload, ensure_ascii=False)

        if job_id:
            await self.redis.set(f"job:{job_id}:status", json_msg)

        await self.redis.publish(NOTIFICATION_CHANNEL, json_msg)
        return job_payload

    async def process_vectorization_job(self, job_id: str, file_key: str, file_hash: str, id_subarea: str, nombre_subarea: str):
        main_task = "Procesar Currículum"
        subtask_desc = f"Generando vectores de la subárea de {nombre_subarea}"
        print(f"[VEC_WORKER] Petición recibida para vectorizar subárea. job_id={job_id}, id_subarea={id_subarea}, nombre={nombre_subarea}", flush=True)

        await self.publish_job_status(
            job_id=job_id,
            file_key=file_key,
            file_hash=file_hash,
            main_task=main_task,
            subtask=subtask_desc,
            status="progress"
        )

        try:
            print(f"[VEC_WORKER] Invocando generate_and_store_subarea_embeddings para id_subarea={id_subarea}...", flush=True)
            res_str = await asyncio.to_thread(generate_and_store_subarea_embeddings, id_subarea)
            if isinstance(res_str, str):
                try:
                    res_data = json.loads(res_str)
                    if isinstance(res_data, dict) and res_data.get("status") == "error":
                        raise RuntimeError(res_data.get("message", "Error generando embeddings"))
                except json.JSONDecodeError:
                    pass

            print(f"[VEC_WORKER] Vectorización exitosa para subárea '{nombre_subarea}' (id={id_subarea}).", flush=True)
            await self.publish_job_status(
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                main_task=main_task,
                subtask=f"Vectorización completada para la subárea de {nombre_subarea}",
                status="finish"
            )
        except Exception as err:
            print(f"[VEC_WORKER_ERROR] Error al vectorizar subárea '{nombre_subarea}' (id={id_subarea}): {err}", flush=True)
            if is_google_rate_limit_error(err):
                logger.warning(f"Límite de cuota alcanzado en API de Google para subárea {id_subarea} ({nombre_subarea}): {err}")
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask=f"Límite de cuota alcanzado en API de Google al vectorizar {nombre_subarea}. Trabajo pausado para reanudación posterior.",
                    status="paused"
                )
                self.stop()
            else:
                logger.error(f"Error vectorizando subárea {id_subarea} ({nombre_subarea}): {err}")
                await self.publish_job_status(
                    job_id=job_id,
                    file_key=file_key,
                    file_hash=file_hash,
                    main_task=main_task,
                    subtask=f"Error al generar vectores para {nombre_subarea}: {str(err)}",
                    status="error"
                )

    async def process_message(self, message_id: str, message_fields: dict):
        action = message_fields.get("action")
        # Procesar mensajes de acción "vectorize" o mensajes antiguos con id_subarea
        if action and action != "vectorize":
            return

        id_subarea = message_fields.get("id_subarea")
        if not id_subarea:
            await self.redis.xack(STREAM_KEY, GROUP_NAME, message_id)
            return

        job_id = message_fields.get("job_id", f"job_vec_{id_subarea}")
        file_key = message_fields.get("file_key", "")
        file_hash = message_fields.get("file_hash", "")
        nombre_subarea = message_fields.get("nombre_subarea", id_subarea)

        try:
            await self.process_vectorization_job(
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                id_subarea=id_subarea,
                nombre_subarea=nombre_subarea
            )
        finally:
            await self.redis.xack(STREAM_KEY, GROUP_NAME, message_id)

    async def run_once(self) -> int:
        await self.init_consumer_group()
        count = 0
        streams = await self.redis.xreadgroup(
            groupname=GROUP_NAME,
            consumername=CONSUMER_NAME,
            streams={STREAM_KEY: ">"},
            count=10,
            block=500
        )
        if streams:
            for _, messages in streams:
                for msg_id, fields in messages:
                    await self.process_message(msg_id, fields)
                    count += 1
        return count

    async def run(self):
        await self.init_consumer_group()
        self.running = True
        logger.info(f"VectorizationWorker activo, escuchando en el stream '{STREAM_KEY}'...")

        while self.running:
            try:
                streams = await self.redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},
                    count=1,
                    block=2000
                )
                if not streams:
                    continue

                for _, messages in streams:
                    for msg_id, fields in messages:
                        await self.process_message(msg_id, fields)

            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error en bucle de VectorizationWorker: {e}")
                await asyncio.sleep(1)

        await self.disconnect()

    def stop(self):
        self.running = False


async def main():
    worker = VectorizationWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

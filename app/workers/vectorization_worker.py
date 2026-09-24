import asyncio
import json
import logging
from typing import Optional
from redis.asyncio import Redis, from_url
from core.config import get_env_variable
from tools.vector_tool import generate_and_store_subarea_embeddings

logger = logging.getLogger(__name__)

STREAM_KEY = "stream:vectorization"
GROUP_NAME = "group:vectorization_workers"
CONSUMER_NAME = "worker-1"
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
            logger.info(f"Consumer group '{GROUP_NAME}' existing or note: {e}")

    async def publish_status(self, id_subarea: str, status: str):
        await self.connect()
        payload = {
            "id_subarea": id_subarea,
            "status": status
        }
        json_msg = json.dumps(payload, ensure_ascii=False)

        await self.redis.set(f"task:{id_subarea}:status", json_msg)

        await self.redis.publish(NOTIFICATION_CHANNEL, json_msg)

    async def process_message(self, message_id: str, message_fields: dict):
        id_subarea = message_fields.get("id_subarea")
        if not id_subarea:
            await self.redis.xack(STREAM_KEY, GROUP_NAME, message_id)
            return

        await self.publish_status(id_subarea, "in_progress")

        try:
            generate_and_store_subarea_embeddings(id_subarea)

            await self.publish_status(id_subarea, "completed")
        except Exception as err:
            logger.error(f"Error vectorizing subarea {id_subarea}: {err}")
            await self.publish_status(id_subarea, "error")
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
        logger.info(f"VectorizationWorker active, consuming from stream '{STREAM_KEY}'...")

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
                logger.error(f"Error in vectorization worker loop: {e}")
                await asyncio.sleep(1)

        await self.disconnect()

    def stop(self):
        self.running = False


async def main():
    worker = VectorizationWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

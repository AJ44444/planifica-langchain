import asyncio
import json
from starlette.responses import StreamingResponse
from starlette.requests import Request
from redis.asyncio import from_url
from core.config import get_env_variable

NOTIFICATION_CHANNEL = "channel:notifications"


async def notifications_sse_endpoint(request: Request) -> StreamingResponse:
    redis_uri = get_env_variable("REDIS_URI")
    redis_client = from_url(redis_uri, decode_responses=True)

    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(NOTIFICATION_CHANNEL)
        try:
            init_msg = json.dumps({"status": "connected", "message": "SSE notification stream active"}, ensure_ascii=False)
            yield f"data: {init_msg}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    raw_data = message.get("data")
                    yield f"data: {raw_data}\n\n"

                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(NOTIFICATION_CHANNEL)
            await pubsub.close()
            await redis_client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

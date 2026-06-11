import asyncio

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from microgpt.services.training import TrainingService

router = APIRouter()
svc = TrainingService()
_tasks: set[asyncio.Task] = set()


@router.post("/training/start")
async def start_training(config: dict):
    run_id = svc.reserve_run()
    task = asyncio.create_task(svc.start_training(config, run_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": run_id, "status": "started"}


@router.get("/training/stream/{run_id}")
async def stream_training(run_id: int):
    queue = svc.get_queue(run_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
                if msg["event"] in ("complete", "error"):
                    break
            except TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/training/configs")
async def list_configs():
    return {"configs": []}


@router.post("/training/{run_id}/stop")
async def stop_training(run_id: int):
    return {"status": "stopped"}

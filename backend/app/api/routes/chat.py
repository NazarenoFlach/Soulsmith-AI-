from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.soulsmith_agent import SoulsmithAgent
from app.dependencies import get_agent
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: SoulsmithAgent = Depends(get_agent),
) -> ChatResponse:
    return await agent.respond(
        message=request.message,
        conversation_id=request.conversation_id,
    )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    agent: SoulsmithAgent = Depends(get_agent),
) -> StreamingResponse:
    return StreamingResponse(
        agent.stream(request.message, request.conversation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

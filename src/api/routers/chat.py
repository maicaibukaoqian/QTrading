"""问股对话 router"""

import json
import logging
from typing import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.api.schemas.chat import (
    SendRequest,
    SessionCreate,
    SessionOut,
    SessionWithMessages,
)
from src.api.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/sessions", response_model=SessionOut)
def post_session(payload: SessionCreate):
    """新建一个针对某只股票的对话会话"""
    return chat_service.create_session(payload.code, payload.title)


@router.get("/sessions", response_model=list[SessionOut])
def get_sessions():
    """列所有会话（按更新时间倒序）"""
    return chat_service.list_sessions()


@router.get("/sessions/{session_id}", response_model=SessionWithMessages)
def get_session(session_id: str):
    """拉一个会话的完整历史（消息按时间正序）"""
    return chat_service.get_session_with_messages(session_id)


@router.delete("/sessions/{session_id}")
def del_session(session_id: str):
    ok = chat_service.delete_session(session_id)
    return {"deleted": ok}


@router.post("/sessions/{session_id}/send")
def post_send(session_id: str, payload: SendRequest):
    """发送消息，SSE 流式返回 LLM 响应

    协议：text/event-stream，每行格式
      data: {"chunk": "..."}\\n\\n
      data: {"done": true, "message_id": 17}\\n\\n
    """
    def event_source() -> Iterator[str]:
        try:
            for event in chat_service.send_message_streaming(session_id, payload.content):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"SSE 流异常 {session_id}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

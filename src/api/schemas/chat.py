"""chat 模块 Pydantic 模型"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    code: str = Field(min_length=6, max_length=6, description="6 位股票代码")
    title: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    code: str
    title: str
    created_at: float
    updated_at: float


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tokens: Optional[int] = None
    created_at: float


class SessionWithMessages(BaseModel):
    session: SessionOut
    messages: List[MessageOut]


class SendRequest(BaseModel):
    content: str = Field(min_length=1, description="用户消息内容")


class StreamChunk(BaseModel):
    """SSE 单个事件载荷"""
    chunk: Optional[str] = None
    done: bool = False
    message_id: Optional[int] = None
    error: Optional[str] = None

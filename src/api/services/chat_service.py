"""问股对话 service

依赖：ChatStore（持久化）+ LLMClient（模型）+ stock_context（数据）+ chat_prompt（提示词）
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator, List

from src.agent.llm_caller import LLMCallError, LLMUnavailableError, get_llm_client
from src.api.errors import AppError
from src.api.schemas.chat import (
    MessageOut,
    SessionOut,
    SessionWithMessages,
)
from src.data.chat_store import ChatStore, Message, Session, get_chat_store
from src.data.stock_context import format_for_prompt, get_stock_context
from src.ai_prompts.investment_analyst import build_chat_prompt as build_chat_system_prompt

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 800


class ChatError(AppError):
    code = "chat_error"
    http_status = 500


class SessionNotFoundError(ChatError):
    code = "session_not_found"
    http_status = 404


def _session_to_out(s: Session) -> SessionOut:
    return SessionOut(
        id=s.id,
        code=s.code,
        title=s.title,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _message_to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        tokens=m.tokens,
        created_at=m.created_at,
    )


def create_session(code: str, title: str | None = None) -> SessionOut:
    s = get_chat_store().create_session(code, title)
    return _session_to_out(s)


def list_sessions(limit: int = 50) -> List[SessionOut]:
    return [_session_to_out(s) for s in get_chat_store().list_sessions(limit=limit)]


def get_session_with_messages(session_id: str) -> SessionWithMessages:
    store = get_chat_store()
    s = store.get_session(session_id)
    if not s:
        raise SessionNotFoundError(f"会话 {session_id} 不存在", detail={"session_id": session_id})
    msgs = store.get_messages(session_id)
    return SessionWithMessages(
        session=_session_to_out(s),
        messages=[_message_to_out(m) for m in msgs],
    )


def delete_session(session_id: str) -> bool:
    store = get_chat_store()
    if not store.get_session(session_id):
        raise SessionNotFoundError(f"会话 {session_id} 不存在", detail={"session_id": session_id})
    return store.delete_session(session_id)


def _truncate_history(messages: List[Message]) -> List[Message]:
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    return messages[-MAX_HISTORY_MESSAGES:]


def _build_messages(session: Session, history: List[Message], user_content: str) -> List[dict]:
    """拼最终发给 LLM 的 messages 列表"""
    system_prompt = build_chat_system_prompt()
    stock_ctx = get_stock_context(session.code)
    stock_block = (
        "以下是当前对话关联股票的实时数据，请结合回答：\n" + format_for_prompt(stock_ctx)
    )
    msgs: List[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": stock_block},
    ]
    for m in _truncate_history(history):
        msgs.append({"role": m.role, "content": m.content})
    msgs.append({"role": "user", "content": user_content})
    return msgs


def send_message_streaming(session_id: str, content: str) -> Iterator[dict]:
    """SSE 事件流

    事件类型（每条都是 dict，由 router 序列化为 JSON）：
      {"chunk": "..."}     流式文本片段
      {"done": true, ...}  结束（携带 message_id 与 tokens）
      {"error": "..."}     出错
    """
    store = get_chat_store()
    session = store.get_session(session_id)
    if not session:
        yield {"error": f"会话 {session_id} 不存在"}
        return

    store.add_message(session_id, "user", content)
    history = store.get_messages(session_id)

    try:
        client = get_llm_client()
        messages = _build_messages(session, history, content)
        full_text_parts: List[str] = []
        for chunk in client.stream_chat(
            messages,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
        ):
            full_text_parts.append(chunk)
            yield {"chunk": chunk}
    except LLMUnavailableError as e:
        logger.warning(f"chat {session_id} AI 不可用: {e}")
        yield {"error": f"AI 不可用: {e}"}
        return
    except LLMCallError as e:
        logger.error(f"chat {session_id} LLM 错误: {e}")
        yield {"error": f"LLM 错误: {e}"}
        return
    except GeneratorExit:
        logger.info(f"chat {session_id} 客户端断开连接")
        return

    full_text = "".join(full_text_parts).strip()
    if not full_text:
        yield {"error": "LLM 返回为空"}
        return

    saved = store.add_message(session_id, "assistant", full_text)
    yield {
        "done": True,
        "message_id": saved.id,
        "tokens": saved.tokens,
        "session_id": session_id,
    }

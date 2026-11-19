"""Real LLM / RAG behind the graph's hook functions (BACKEND-PLAN GĐ2).

``graph.py`` keeps deterministic placeholders so ``scripts/agui_selfcheck.py``
runs offline; at startup ``main.py`` installs a ``MentorBackend`` with
``graph.configure(...)``. Every internal model call (classification,
structured generation) runs with ``INTERNAL_LLM_CONFIG`` so its tokens and
tool calls never reach the client.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ValidationError

from app.agents.mentor_agui.prompts import Prompts
from app.services import agui_documents

from .schemas import (
    FollowupsDraft,
    Intent,
    IntentDraft,
    MindmapDraft,
    QuizDraft,
    clean_followups,
    mindmap_from_draft,
    quiz_from_draft,
)
from .state import message_text
from .ui_catalog import ShowMindmap, ShowQuiz

logger = structlog.get_logger(__name__)

INTERNAL_LLM_CONFIG: RunnableConfig = {
    "metadata": {"emit-messages": False, "emit-tool-calls": False},
    "tags": ["mentor:internal"],
}
STRUCTURED_ATTEMPTS = 3
TOP_K_PASSAGES = 6
HISTORY_TURNS_FOR_INTENT = 6
MAX_CONTEXT_CHARS = 60_000

StructuredCall = Callable[[type[BaseModel], list[BaseMessage], RunnableConfig], Awaitable[Any]]
T = TypeVar("T")


def merge_config(config: RunnableConfig | None, extra: RunnableConfig) -> RunnableConfig:
    merged: dict[str, Any] = dict(config or {})
    merged["metadata"] = {**(config or {}).get("metadata", {}), **extra.get("metadata", {})}
    merged["tags"] = [*(config or {}).get("tags", []), *extra.get("tags", [])]
    return merged  # type: ignore[return-value]


def format_context(chunks: Sequence[agui_documents.RetrievedChunk]) -> str:
    parts = [f"[{c['file_name']}]\n{c['text']}" for c in chunks]
    return "\n\n---\n\n".join(parts)[:MAX_CONTEXT_CHARS]


class ServiceDocuments:
    """Default document access: app DB + Qdrant + MinIO (blocking, run in threads)."""

    async def resolve(self, session_id: str, client_ids: Sequence[str]) -> list[str]:
        return await asyncio.to_thread(agui_documents.selected_document_ids, session_id, client_ids)

    async def passages(self, session_id: str, question: str, ids: Sequence[str], k: int):
        return await asyncio.to_thread(agui_documents.retrieve_passages, session_id, question, ids, k)

    async def whole(self, session_id: str, ids: Sequence[str]):
        return await asyncio.to_thread(agui_documents.whole_documents, session_id, ids)


class MentorBackend:
    def __init__(
        self,
        chat_model_factory: Callable[[], BaseChatModel],
        structured_call: StructuredCall | None = None,
        documents: Any = None,
    ) -> None:
        self.chat_model_factory = chat_model_factory
        self._structured = structured_call or self._llm_structured
        self.documents = documents or ServiceDocuments()

    async def _llm_structured(self, schema, messages, config):
        model = self.chat_model_factory().with_structured_output(schema, method="function_calling")
        return await model.ainvoke(messages, merge_config(config, INTERNAL_LLM_CONFIG))

    async def _draft(
        self,
        schema: type[BaseModel],
        messages: list[BaseMessage],
        config: RunnableConfig,
        convert: Callable[[Any], T],
        attempts: int = STRUCTURED_ATTEMPTS,
    ) -> T:
        """Structured call + strict conversion, retried with the error as feedback."""
        prompt = list(messages)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                draft = await self._structured(schema, prompt, config)
                if draft is None:
                    raise ValueError("the model returned no structured output")
                if isinstance(draft, dict):
                    draft = schema.model_validate(draft)
                return convert(draft)
            except (ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(f"{schema.__name__} attempt {attempt}/{attempts} invalid: {exc}")
                prompt = [
                    *messages,
                    HumanMessage(
                        content=f"Kết quả trước không hợp lệ ({str(exc)[:300]}). Hãy tạo lại đúng yêu cầu."
                    ),
                ]
        raise ValueError(f"{schema.__name__} still invalid after {attempts} attempts") from last_error

    # --- hooks used by graph.py ------------------------------------------

    async def classify_intent(
        self, question: str, history: Sequence[BaseMessage], config: RunnableConfig
    ) -> Intent:
        turns = [
            m
            for m in history
            if getattr(m, "type", None) in ("human", "ai") and message_text(m).strip()
        ][-HISTORY_TURNS_FOR_INTENT:]
        transcript = "\n".join(f"{m.type}: {message_text(m)[:500]}" for m in turns)
        messages = [
            SystemMessage(content=Prompts.INTENT),
            HumanMessage(content=f"LỊCH SỬ:\n{transcript or '(trống)'}\n\nYÊU CẦU MỚI NHẤT: {question}"),
        ]
        return await self._draft(IntentDraft, messages, config, lambda d: d.intent)

    async def resolve_document_ids(self, session_id: str, client_ids: Sequence[str]) -> list[str]:
        return await self.documents.resolve(session_id, client_ids)

    async def retrieve(
        self, question: str, document_ids: Sequence[str], session_id: str, whole_documents: bool
    ) -> list[agui_documents.RetrievedChunk]:
        if not document_ids:
            return []
        if whole_documents:
            return await self.documents.whole(session_id, document_ids)
        return await self.documents.passages(session_id, question, document_ids, TOP_K_PASSAGES)

    async def suggest_followups(self, question: str, answer: str, config: RunnableConfig) -> list[str]:
        prompt = Prompts.FOLLOWUPS.format(question=question[:1000], answer=answer[:3000])
        try:
            return await self._draft(
                FollowupsDraft, [HumanMessage(content=prompt)], config, lambda d: clean_followups(d.questions)
            )
        except ValueError as exc:  # follow-ups are optional: never fail the turn
            logger.warning(f"follow-ups skipped: {exc}")
            return []

    async def generate_quiz(
        self, topic: str, chunks, count: int, difficulty: str, config: RunnableConfig
    ) -> ShowQuiz:
        context = (
            Prompts.CONTEXT_BLOCK.format(context=format_context(chunks)) if chunks else Prompts.NO_CONTEXT
        )
        prompt = Prompts.QUIZ.format(count=count, difficulty=difficulty, topic=topic, context=context)
        return await self._draft(
            QuizDraft,
            [HumanMessage(content=prompt)],
            config,
            lambda d: quiz_from_draft(d, count, difficulty),  # type: ignore[arg-type]
        )

    async def generate_mindmap(self, topic: str, chunks, config: RunnableConfig) -> ShowMindmap:
        context = (
            Prompts.CONTEXT_BLOCK.format(context=format_context(chunks)) if chunks else Prompts.NO_CONTEXT
        )
        prompt = Prompts.MINDMAP.format(topic=topic, context=context)
        return await self._draft(MindmapDraft, [HumanMessage(content=prompt)], config, mindmap_from_draft)


def default_backend() -> MentorBackend:
    """Backend with the app's chat model (settings.CHAT_MODEL via OpenRouter)."""
    from app.agents.base import init_llm
    from app.core.config import settings

    def factory() -> BaseChatModel:
        return init_llm(
            model=settings.CHAT_MODEL,
            temperature=settings.CHAT_MODEL_TEMPERATURE,
            streaming=True,
        )

    return MentorBackend(chat_model_factory=factory)

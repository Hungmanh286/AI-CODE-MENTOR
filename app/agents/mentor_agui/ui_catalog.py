"""Pydantic v2 models for the UI tools rendered by the frontend.

This file mirrors docs/agui/PLAN.md, section 4.5 field by field. If the contract
changes, change it there first, then here, then the frontend renderers.

Type mapping used throughout:
    TS ``string``            -> ``str``
    TS ``number``            -> ``int`` (every numeric field in 4.5 is an index,
                                a page number or a column index)
    TS ``T[]``               -> ``List[T]``
    TS ``x?: T``             -> ``Optional[T] = None`` (dump with
                                ``exclude_none=True`` so the key is omitted,
                                see ``dump_args``)
    TS ``"a" | "b"``         -> ``Literal["a", "b"]``

Every model forbids unknown keys (``extra="forbid"``): the backend must emit
exactly the contract, and a strict schema also helps LLM structured output.
The frontend still tolerates partial/streaming args; that is its job, not ours.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# show_quiz: { title: string, questions: Array<{ id, question, options,
#              answer_index, explanation, difficulty }> }
# ---------------------------------------------------------------------------

Difficulty = Literal["easy", "medium", "hard"]


class QuizQuestion(_ContractModel):
    id: str
    question: str
    options: list[str]
    answer_index: int = Field(ge=0)
    explanation: str
    difficulty: Difficulty

    @model_validator(mode="after")
    def _answer_index_in_range(self) -> QuizQuestion:
        # Not a new field: it guards the meaning of answer_index so the
        # frontend never highlights a non-existent option.
        if self.answer_index >= len(self.options):
            raise ValueError(
                f"answer_index={self.answer_index} out of range for "
                f"{len(self.options)} options"
            )
        return self


class ShowQuiz(_ContractModel):
    title: str
    questions: list[QuizQuestion]


# ---------------------------------------------------------------------------
# show_mindmap: { title: string, root: Node }
# Node = { id: string, label: string, children?: Node[] }
# ---------------------------------------------------------------------------


class MindmapNode(_ContractModel):
    id: str
    label: str
    children: list[MindmapNode] | None = None


MindmapNode.model_rebuild()


class ShowMindmap(_ContractModel):
    title: str
    root: MindmapNode


# ---------------------------------------------------------------------------
# cite_sources: { sources: Array<{ file_id: string, file_name: string,
#                 page?: number, quote: string }> }
# ---------------------------------------------------------------------------


class SourceRef(_ContractModel):
    file_id: str
    file_name: str
    page: int | None = None
    quote: str


class CiteSources(_ContractModel):
    sources: list[SourceRef]


# ---------------------------------------------------------------------------
# suggest_followups: { questions: string[] }
# ---------------------------------------------------------------------------


class SuggestFollowups(_ContractModel):
    questions: list[str]


# ---------------------------------------------------------------------------
# present_ui: { title?: string, blocks: Block[] }
# Block is a union discriminated by "type".
# ---------------------------------------------------------------------------


class CalloutBlock(_ContractModel):
    type: Literal["callout"]
    tone: Literal["info", "tip", "warning"]
    title: str
    body_md: str


class StepItem(_ContractModel):
    title: str
    body_md: str


class StepsBlock(_ContractModel):
    type: Literal["steps"]
    items: list[StepItem]


class ComparisonTableBlock(_ContractModel):
    type: Literal["comparison_table"]
    columns: list[str]
    rows: list[list[str]]
    highlight_col: int | None = Field(
        default=None,
        ge=0,
        description="0-based index into `columns` of the column to highlight.",
    )

    @model_validator(mode="after")
    def _highlight_col_in_range(self) -> ComparisonTableBlock:
        # Contract 4.5: highlight_col counts from 0 over `columns`.
        if self.highlight_col is not None and self.highlight_col >= len(self.columns):
            raise ValueError(
                f"highlight_col={self.highlight_col} out of range for {len(self.columns)} columns"
            )
        return self


class CodeDiffBlock(_ContractModel):
    type: Literal["code_diff"]
    language: str
    before: str
    after: str
    explanation_md: str


class ConceptCardBlock(_ContractModel):
    type: Literal["concept_card"]
    term: str
    definition_md: str
    example_code: str | None = None
    language: str | None = None


Block = Annotated[
    CalloutBlock | StepsBlock | ComparisonTableBlock | CodeDiffBlock | ConceptCardBlock,
    Field(discriminator="type"),
]


class PresentUI(_ContractModel):
    title: str | None = None
    blocks: list[Block]


def validate_present_ui(payload: Any) -> PresentUI:
    """Validate a ``present_ui`` payload (dict or JSON string).

    Raises ``pydantic.ValidationError`` when a block has an unknown ``type``
    or a field does not match section 4.5. Unknown block types are rejected on
    the backend on purpose: the frontend fallback ("Không hỗ trợ khối này") is
    a safety net, not something the backend should rely on.
    """
    if isinstance(payload, (str, bytes, bytearray)):
        return PresentUI.model_validate_json(payload)
    return PresentUI.model_validate(payload)


# ---------------------------------------------------------------------------
# Helpers shared by tools.py / graph.py
# ---------------------------------------------------------------------------

TOOL_ARG_MODELS: dict[str, type[_ContractModel]] = {
    "show_quiz": ShowQuiz,
    "show_mindmap": ShowMindmap,
    "cite_sources": CiteSources,
    "suggest_followups": SuggestFollowups,
    "present_ui": PresentUI,
}


def validate_tool_args(tool_name: str, payload: Any) -> _ContractModel:
    """Validate args for any of the five UI tools by name."""
    model = TOOL_ARG_MODELS[tool_name]
    if isinstance(payload, (str, bytes, bytearray)):
        return model.model_validate_json(payload)
    return model.model_validate(payload)


def dump_args(model: BaseModel) -> dict[str, Any]:
    """JSON-ready dict for TOOL_CALL_ARGS: optional fields left unset are omitted.

    ``exclude_none=True`` turns ``page=None`` into "no page key", matching the
    TS ``page?: number`` (absent, not null).
    """
    return model.model_dump(mode="json", exclude_none=True)

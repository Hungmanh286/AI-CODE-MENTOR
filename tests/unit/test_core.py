"""Behaviour of the shared helpers: security, paths, state, formatting, prompts."""

import json

import bcrypt
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.common.prompts import Prompts as CommonPrompts
from app.agents.common.state import get_conversation_messages, get_tool_messages
from app.agents.document_processing.formatting import (
    clean_markdown_json,
    execute_parallel_tasks,
    format_dict_to_markdown,
    format_qa_for_judge,
    format_question_answer_dict,
)
from app.agents.document_processing.prompts import Prompts as DocPrompts
from app.agents.document_processing.schemas import (
    Question,
    QuestionList,
    QuestionWithAnswer,
    QuestionWithAnswerList,
)
from app.agents.feedback_answer.prompts import Prompts as FeedbackPrompts
from app.agents.question_expert.prompts import Prompts as QuestionPrompts
from app.core.paths import BASE_DIR, DATA_DIR, VAR_DIR, var_path
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_access_token,
    verify_password,
)
from app.infra.prompts import Prompts as InfraPrompts

# ---------------------------------------------------------------- security


def test_password_roundtrip():
    assert verify_password("s3cret", get_password_hash("s3cret"))
    assert not verify_password("wrong", get_password_hash("s3cret"))


def test_password_hash_keeps_the_legacy_bcrypt_format():
    """Hashes written by the old passlib setup must keep verifying."""
    legacy = bcrypt.hashpw(b"legacy", bcrypt.gensalt(rounds=12)).decode()
    assert verify_password("legacy", legacy)
    assert get_password_hash("x").startswith("$2b$12$")


@pytest.mark.parametrize("plain,stored", [("", ""), ("pw", ""), ("pw", "not-a-hash")])
def test_password_verify_never_raises(plain, stored):
    assert verify_password(plain, stored) is False


def test_password_longer_than_bcrypt_limit_does_not_raise():
    long_password = "x" * 200
    assert verify_password(long_password, get_password_hash(long_password))


def test_jwt_roundtrip():
    token = create_access_token({"user_id": "7", "username": "u"})
    assert verify_access_token(token)["user_id"] == "7"
    assert verify_access_token("garbage") is None


# ---------------------------------------------------------------- paths


def test_paths_anchor_to_the_repository_root():
    assert (BASE_DIR / "pyproject.toml").exists()
    assert DATA_DIR.parent == BASE_DIR and VAR_DIR.parent == BASE_DIR


def test_var_path_creates_its_parent():
    assert var_path("pytest_tmp", "f.txt").parent.exists()


# ---------------------------------------------------------------- graph state


def test_conversation_messages_drop_tool_noise():
    messages = [
        SystemMessage(content="sys"),
        HumanMessage(content="q1"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="tool output", tool_call_id="1"),
        AIMessage(content="a1", name="answer"),
    ]
    kept = get_conversation_messages({"messages": messages}, aimessage_name=["answer"])
    assert [m.content for m in kept] == ["sys", "q1", "a1"]
    assert [m.content for m in get_tool_messages({"messages": messages[:4]})] == ["tool output"]


# ---------------------------------------------------------------- formatting


def test_clean_markdown_json_strips_fences():
    assert clean_markdown_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert clean_markdown_json('{"a": 1}') == '{"a": 1}'


def test_execute_parallel_tasks_maps_task_id_to_result():
    assert execute_parallel_tasks(lambda x: (x, x * 2), list(range(4)), max_workers=2) == {
        0: 0, 1: 2, 2: 4, 3: 6
    }


def test_format_dict_to_markdown():
    out = format_dict_to_markdown({"c1": [{"id": 1, "question": "Q?", "options": ["a"], "average_score": 3}]})
    assert "Câu 1:" in out and "Q?" in out


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps([{"id": 1, "question": "Q?", "options": ["a", "b"], "related_passage": "p"}]),
        '{"id":1,"question":"A","options":[]}{"id":2,"question":"B","options":[]}',
    ],
)
def test_format_question_answer_dict_parses_awkward_json(payload):
    assert "Câu 1" in format_question_answer_dict({"c1": [payload]})


def test_format_qa_for_judge():
    qa = QuestionWithAnswerList(
        questions=[QuestionWithAnswer(id=1, question="Q?", options=["A. a", "B. b"], related_passage="p")]
    )
    assert "CHUNK c1" in format_qa_for_judge(qa, "c1")


def test_question_schemas():
    q = Question(
        id="1", type="mcq", difficulty="easy", question="Q?",
        options=["a", "b", "c", "d"], correct_answer=0, explanation="e",
    )
    assert QuestionList(selected_questions=[q]).selected_questions[0].question == "Q?"


# ---------------------------------------------------------------- prompt split

ORIGINAL_PROMPTS = [
    "SUMMARIZE_CHUNK_SUMMARY_PROMPT", "MIND_MAP_PROMPT", "MARK_DOWN_PROMPT",
    "QUESTION_GENERATION_PROMPT", "QUESTION_REGENERATION_PROMPT", "ANSWER_GENERATION_PROMPT",
    "EVALUATE_QA_PROMPT", "EVALUATE_AND_SELECT_PROMPT", "EXTRACTIVE_SUMMARIZE_PROMPT",
    "SUMMARIZE_CHUNK_SUMMARY_CIATATIONS_PROMPT", "SUMMARIZE_CHUNK_SUMMARY_Extract_PROMPT",
    "HMerge_SUMMARY_PROMPT", "HMerge_SUMMARY_Citations_PROMPT", "Extract_Retrieve_Support_PROMPT",
    "Cite_Support_PROMPT", "SUMMARIZE_PROMPT", "GENERATE_QUESTIONS_PROMPT",
    "FEEDBACK_QUESTIONS_PROMPT", "QUESTIONS_GEN_PROMPT",
]
PROMPT_HOMES = {
    "common": CommonPrompts, "document_processing": DocPrompts, "question_expert": QuestionPrompts,
    "feedback_answer": FeedbackPrompts, "infra": InfraPrompts,
}


@pytest.mark.parametrize("name", ORIGINAL_PROMPTS)
def test_prompt_lives_in_exactly_one_module(name):
    owners = [home for home, cls in PROMPT_HOMES.items() if hasattr(cls, name)]
    assert len(owners) == 1, f"{name} -> {owners or 'MISSING'}"

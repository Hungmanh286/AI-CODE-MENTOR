from openai import OpenAI
import json
import re

from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langfuse.callback import CallbackHandler
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain.tools import tool


from app.config import settings
from app.graph.generate import generate_agent
from app.graph.prompts import Prompts
from app.routes.process_data import process_pdf
from app.routes.notify import (
    sse_event_queues,
)
from app.graph.agents.summarize_agent import pdf_summarize_agent
from app.graph.agents.feedbacks_answer import feedbacks_answer
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client

model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
client = OpenAI(api_key=api_key)


class QState(MessagesState):
    document_chunks: list[str] | None = None
    questions: list[str] | None = None
    question_answers: str | None = None
    judged_answers: list[str] | None = None
    retry_count: int | None = None
    good_questions: list[str] | None = None
    check_questions: str | None = None
    bad_questions: str | None = None
    good_question_answers: list[str] | None = None
    quizz: list[str] | None = None
    query: str | None = None


tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


max_retry = 2


def format_dict_to_markdown(data: dict) -> str:
    """Format dict Q&A thành chuỗi Markdown dễ đọc"""
    formatted = ""
    for chunk_id, items in data.items():
        formatted += f"\n📘 **Chunk {chunk_id}**\n\n"
        for item in items:
            qid = item.get("id", "")
            question = item.get("question", "")
            options = item.get("options", [])
            avg_score = item.get("average_score", "")
            formatted += f"**Câu {qid}:** {question}\n"
            if options:
                formatted += "**Các lựa chọn:**\n"
                for opt in options:
                    formatted += f"  {opt}\n"
            formatted += f"**Điểm trung bình:** {avg_score}\n\n"
        formatted += "-" * 40 + "\n"
    return formatted


def format_question_answer_dict(data: dict) -> str:
    """
    Format dict chứa list JSON Q&A thành văn bản đẹp (Markdown),
    phù hợp với cấu trúc dữ liệu KHÔNG có correct_answer/explanation.
    """
    formatted = ""

    for chunk_id, json_list in data.items():
        formatted += f"**Chunk {chunk_id}**\n\n"

        for json_str in json_list:
            try:
                qa_items = json.loads(json_str)
            except json.JSONDecodeError as e:
                formatted += f"⚠️ Lỗi parse JSON: {e}\n\n"
                continue

            for item in qa_items:
                qid = item.get("id", "")
                q = item.get("question", "").strip()
                options = item.get("options", [])
                related_passage = item.get("related_passage", "").strip()

                formatted += f"###Câu {qid}: {q}\n"

                if options:
                    formatted += "**Các lựa chọn:**\n"
                    for opt in options:
                        formatted += f"- {opt}\n"

                if related_passage:
                    formatted += f"\n**Đoạn văn liên quan:**\n{related_passage}\n"

                formatted += "\n---\n\n"

        formatted += "\n" + "=" * 100 + "\n\n"

    return formatted


# node 1 : chunker
def document_preprocessing(state: QState, config: RunnableConfig):
    """Tiền xử lý tài liệu: tách nhỏ văn bản thành các đoạn (chunks)."""
    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)
    query = state.get("query", None)
    document_chunks = []
    chunk_size = 5

    for file_id in file_ids:
        # Đọc docs từ MinIO (trong folder session)
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")
                docs = [docs_content]

                splitter = MarkdownHeaderTextSplitter(
                    headers_to_split_on=[
                        ("#", "Header_1"),
                        ("##", "Header_2"),
                    ],
                )
                splits = [split for doc in docs for split in splitter.split_text(doc)]
                total_splits = len(splits)

                # Gộp các split lại thành các chunk với chunk_size
                for i in range(0, total_splits, chunk_size):
                    chunk_text = "\n".join(
                        [split.page_content for split in splits[i : i + chunk_size]]
                    )
                    document_chunks.append(chunk_text)

    return {"document_chunks": document_chunks, "query": query}


# node 2 : generate question
def question_node(state: QState, config: RunnableConfig):
    """Sinh câu hỏi tự động từ chunks đã tóm tắt."""

    check_questions = {}
    good_questions = state.get("good_questions", None)
    bad_questions = state.get("bad_questions", None)
    query = state.get("query", None)

    document_chunks = state.get("document_chunks", [])
    retry_count = state.get("retry_count", 0)

    idx = 0
    if retry_count == 0:
        for chunk in document_chunks:
            prompt = Prompts.QUESTION_GENERATION_PROMPT.format(chunk=chunk, query=query)
            response_msg = generate_agent.invoke(
                {"messages": [HumanMessage(content=prompt)]}, config=config
            )
            question = response_msg["messages"][-1].content
            key = idx
            if key not in check_questions:
                check_questions[key] = []
            check_questions[key].append(question)
            idx += 1

    else:
        if bad_questions is not None:
            for chunk_index, bad_qs in bad_questions.items():
                chunk = document_chunks[int(chunk_index)]
                prompt = Prompts.QUESTION_REGENERATION_PROMPT.format(
                    chunk=chunk, bad_qs=bad_qs, good_questions=good_questions
                )
                response_msg = generate_agent.invoke(
                    {"messages": [HumanMessage(content=prompt)]}, config=config
                )
                question = response_msg["messages"][-1].content
                key = str(chunk_index)
                if key not in check_questions:
                    check_questions[key] = []
                check_questions[key].append(question)

    return {
        "check_questions": check_questions,
        "document_chunks": document_chunks,
    }


# xử lý câu trả lời khi không còn bad questions , chỉ trả lời cho good questions
# node 3 : answer generate
def answer_node(state: QState, config: RunnableConfig):
    """Sinh ra các đáp án cho các câu hỏi dựa trên các đoạn tài liệu đã tóm tắt."""
    check_questions = state.get("check_questions", {})
    question_answers = {}

    for idx, questions in check_questions.items():
        formatted_prompt = f"Chunk {idx}\n" + "\n".join([q for q in questions])

        prompt = Prompts.ANSWER_GENERATION_PROMPT.format(questions=formatted_prompt)
        response_msg = generate_agent.invoke(
            {"messages": [HumanMessage(content=prompt)]}, config=config
        )
        question_answer = response_msg["messages"][-1].content
        chunk_idx = str(idx)
        if chunk_idx not in question_answers:
            question_answers[chunk_idx] = []
        question_answers[chunk_idx].append(question_answer)

    return {
        "question_answers": question_answers,
    }


# node 3 : đánh giá chất lượng câu hỏi, nếu chưa tốt quay lại bước 2
def judge(state: QState, config: RunnableConfig):
    """Đánh giá chất lượng cặp question và answer, phân loại good/bad."""

    question_answers = state.get("question_answers", {})

    formatted_question_answers = format_question_answer_dict(question_answers)

    good_question_answers = state.get("good_question_answers", None)
    good_questions = state.get("good_questions", None)
    retry = state.get("retry_count", 0)

    prompt = Prompts.EVALUATE_QA_PROMPT.format(
        question_answers=formatted_question_answers
    )
    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=prompt)]}, config=config
    )

    judgment = response_msg["messages"][-1].content.strip()

    if judgment.startswith("```"):
        judgment = re.sub(r"^```(json)?", "", judgment.strip())
        judgment = re.sub(r"```$", "", judgment.strip())
        judgment = judgment.strip()

    try:
        result = json.loads(judgment)
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        print(f"Error at line {e.lineno}, column {e.colno}, position {e.pos}")

        judgment_fixed = re.sub(
            r'\\(?![ntr"\\/bfu])',
            r"\\\\",
            judgment,
        )

        try:
            result = json.loads(judgment_fixed)
        except json.JSONDecodeError as e2:
            print(f"Still failed after fix: {e2}")
            print(
                f"Content around error: {judgment_fixed[max(0, e2.pos - 100) : e2.pos + 100]}"
            )

            result = {
                "good_question_answer": {},
                "bad_questions": {},
                "good_questions": {},
            }

    good_question_answer = result.get("good_question_answer", {})
    bad_questions = result.get("bad_questions", {})
    good_question = result.get("good_questions", {})

    # Cập nhật good_questions
    if good_questions is None:
        good_questions = {}
    for k, v in good_question.items():
        if k not in good_questions:
            good_questions[k] = []
        if isinstance(v, list):
            good_questions[k].extend(v)
        else:
            good_questions[k].append(v)

    # Cập nhật good_question_answers
    if good_question_answers is None:
        good_question_answers = {}
    for k, v in good_question_answer.items():
        if k not in good_question_answers:
            good_question_answers[k] = []
        if isinstance(v, list):
            good_question_answers[k].extend(v)
        else:
            good_question_answers[k].append(v)

    retry += 1

    return {
        "bad_questions": bad_questions,
        "retry_count": retry,
        "good_question_answers": good_question_answers,
        "good_questions": good_questions,
    }


def should_continue(state: QState) -> str:
    """Quyết định có tiếp tục loop hay không"""
    retry_count = state.get("retry_count", 0)
    bad_questions = state.get("bad_questions", None)

    if len(bad_questions) > 0 and retry_count < max_retry:
        for k, v in bad_questions.items():
            if len(v) > 0:
                return "question_node"
        return "end"

    return "end"


# node 5 : đánh giá lại 1 lần nữa rồi cho đáp án cuối cùng
def validate(state: QState, config: RunnableConfig):
    """Xác nhận đầu ra cuối cùng."""
    good_question_answers = state.get("good_question_answers", None)

    formatted_question_answers = format_dict_to_markdown(good_question_answers)
    query = state.get("query", None)

    system_message = SystemMessage(
        content=Prompts.EVALUATE_AND_SELECT_PROMPT.format(
            questions=formatted_question_answers, query=query
        )
    )

    prompt = {"messages": [system_message]}
    response_msg = generate_agent.invoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {"quizz": content}


workflow = StateGraph(QState)

workflow.add_node("document_preprocessing", document_preprocessing)
workflow.add_node("question_node", question_node)
workflow.add_node("answer_node", answer_node)
workflow.add_node("judge", judge)
workflow.add_node("validate", validate)

workflow.add_edge(START, "document_preprocessing")
workflow.add_edge("document_preprocessing", "question_node")
workflow.add_edge("question_node", "answer_node")
workflow.add_edge("answer_node", "judge")


workflow.add_conditional_edges(
    "judge", should_continue, {"question_node": "question_node", "end": "validate"}
)
workflow.add_edge("validate", END)

document_processing_agent = workflow.compile()


@tool("using_to_create_questions")
async def document_processing_tool(query: str, config: RunnableConfig):
    """
    Công cụ tạo câu hỏi trắc nghiệm từ tài liệu.
    Sử dụng khi người dùng yêu cầu tạo câu hỏi, bài kiểm tra, hoặc quiz từ tài liệu PDF đã tải lên.

    Args:
        query (str): Câu truy vấn của người dùng
        config (RunnableConfig): Cấu hình chứa session_id.
    """
    session_id = config["configurable"].get("thread_id")
    if not session_id:
        return "session_id không hợp lệ."

    # Ensure a queue exists for this session (client may not have connected yet)
    if session_id not in sse_event_queues:
        import asyncio

        sse_event_queues[session_id] = asyncio.Queue()
        print(f"[DocumentProcessing] Created SSE queue for session_id: {session_id}")

    try:
        # Directly await the async process_pdf (no thread pool needed)
        await process_pdf(
            session_id, document_processing_agent=document_processing_agent, query=query
        )
        queue = sse_event_queues.get(session_id)
        if queue:
            await queue.put("done")
            print("SSE event sent to", session_id)
        else:
            print("SSE queue not found for session_id:", session_id)
        return "Đã tạo câu hỏi thành công từ tài liệu."
    except Exception as e:
        print(f"[DocumentProcessing] Error during processing: {e}")
        queue = sse_event_queues.get(session_id)
        if queue:
            await queue.put(f"error: {str(e)}")


@tool("document_summarize_tool")
async def document_summarize_tool(query: str, config: RunnableConfig):
    """
    Công cụ tóm tắt nội dung tài liệu.
    Sử dụng khi người dùng yêu cầu tóm tắt, tổng hợp nội dung, hoặc rút gọn thông tin từ tài liệu PDF đã tải lên.

    Args:
        query (str): Câu truy vấn của người dùng.
        config (RunnableConfig): Cấu hình chứa session_id.
    """
    response_msg = await pdf_summarize_agent.ainvoke(
        {"messages": [HumanMessage(content="Tóm tắt tài liệu")]}, config=config
    )
    content = response_msg["messages"][-1].content
    return {"message": content}


@tool("answer_tool")
async def answer_tool(query: str, config: RunnableConfig):
    """
    Công cụ trả lời câu hỏi hoặc giải thích nội dung cụ thể trong tài liệu.
    Sử dụng khi người dùng hỏi về một chi tiết cụ thể, yêu cầu giải thích một đoạn văn, hoặc hỏi đáp thông thường dựa trên tài liệu.

    Args:
        query (str): Nội dung câu hỏi hoặc đoạn văn bản cần giải thích.
        config (RunnableConfig): Cấu hình chứa session_id.
    """
    response_msg = await feedbacks_answer.ainvoke(
        {"messages": [HumanMessage(content=query)]}, config=config
    )
    content = response_msg["messages"][-1].content
    return {"message": content}


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            print(s)

    inputs = {"messages": [HumanMessage(content="Test")]}
    print_stream(
        document_processing_agent.stream(
            inputs, stream_mode="values", config={"callbacks": [tracer]}
        )
    )

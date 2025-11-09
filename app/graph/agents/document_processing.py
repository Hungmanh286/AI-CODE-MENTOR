from io import BytesIO
from openai import OpenAI
import base64
from pdf2image import convert_from_path
import json
import re

from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langfuse.callback import CallbackHandler


from app.config import settings
from app.graph.generate import generate_agent
from app.graph.prompts import Prompts

model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
client = OpenAI(api_key=api_key)


class QState(MessagesState):
    document_chunks: list[str] | None
    questions: list[str] | None
    question_answers: list[str] | None
    judged_answers: list[str] | None
    retry_count: int | None
    good_questions: str | None
    bad_questions: str | None
    quizz: list[str] | None


tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)

input_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

max_retry = 3


def summarize_chunk(chunk_images: list, chunk_index: int) -> str:
    """
    Tóm tắt một chunk (nhóm các trang) từ PDF.

    Args:
        chunk_images: Danh sách các ảnh base64 trong chunk
        chunk_index: Chỉ số của chunk

    Returns:
        Bản tóm tắt của chunk
    """
    content = [
        {
            "type": "input_text",
            "text": Prompts.SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(
                document=f"Đây là phần {chunk_index + 1} của tài liệu (các trang được thể hiện dưới dạng hình ảnh)"
            ),
        }
    ]

    for img_b64 in chunk_images:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{img_b64}",
            }
        )

    response = client.responses.create(
        model=model, input=[{"role": "user", "content": content}]
    )

    return response.output_text


# node 1 : chunker


def document_preprocessing(state: QState, config: RunnableConfig):
    """Tiền xử lý tài liệu: tách nhỏ văn bản thành các đoạn (chunks)."""

    images = convert_from_path(input_path)

    image_b64_list = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_b64_list.append(img_b64)

    total_pages = len(image_b64_list)

    document_chunks = []
    if total_pages < 50:
        chunk_size = 15
        overlap = 3
    elif 50 <= total_pages <= 150:
        chunk_size = 30
        overlap = 7
    else:
        chunk_size = 50
        overlap = 10

    start = 0
    while start < total_pages:
        end = min(start + chunk_size, total_pages)
        chunk = image_b64_list[start:end]
        chunk_summary = summarize_chunk(chunk, start // chunk_size)
        document_chunks.append(chunk_summary)
        start += chunk_size - overlap

    return {"document_chunks": document_chunks}


def question_node(state: QState, config: RunnableConfig):
    """Sinh câu hỏi tự động từ chunks đã tóm tắt."""
    good_questions = state.get("good_questions", None)
    bad_questions = state.get("bad_questions", None)
    document_chunks = state.get("document_chunks", [])

    idx = 0
    if good_questions is None:
        good_questions = {}
        for chunk in document_chunks:
            prompt = Prompts.QUESTION_GENERATION_PROMPT.format(chunk=chunk)
            response_msg = generate_agent.invoke(
                {"messages": [HumanMessage(content=prompt)]}, config=config
            )
            question = response_msg["messages"][-1].content
            if idx not in good_questions:
                good_questions[idx] = []
            good_questions[idx].append(question)
            idx += 1
    else:
        if bad_questions is not None:
            for chunk_index, bad_qs in bad_questions.items():
                chunk = document_chunks[int(chunk_index)]
                prompt = Prompts.QUESTION_REGENERATION_PROMPT.format(
                    chunk=chunk,
                    bad_qs=bad_qs,
                    good_questions=good_questions[chunk_index],
                )
                response_msg = generate_agent.invoke(
                    {"messages": [HumanMessage(content=prompt)]}, config=config
                )
                question = response_msg["messages"][-1].content
                if chunk_index not in good_questions:
                    good_questions[chunk_index] = []
                good_questions[chunk_index].append(question)

    return {"good_questions": good_questions, "document_chunks": document_chunks}


def question_extractor(state: QState, config: RunnableConfig):
    """xử lý câu hỏi các câu hỏi, loại bỏ trùng lặp, đảm bảo chỉ giữ lại
    các câu hỏi liên quan, đa dạng và không dư thừa."""
    good_questions = state.get("good_questions", None)
    document_chunks = state.get("document_chunks", [])

    return {"good_questions": good_questions, "document_chunks": document_chunks}


def answer_node(state: QState, config: RunnableConfig):
    """Sinh ra các đáp án cho các câu hỏi dựa trên các đoạn tài liệu đã tóm tắt."""
    good_questions = state.get("good_questions", {})
    document_chunks = state.get("document_chunks", [])
    question_answers = []

    for idx, questions in good_questions.items():
        chunk = document_chunks[int(idx)]
        prompt = Prompts.ANSWER_GENERATION_PROMPT.format(
            chunk=chunk, questions=questions
        )
        response_msg = generate_agent.invoke(
            {"messages": [HumanMessage(content=prompt)]}, config=config
        )
        question_answer = response_msg["messages"][-1].content
        question_answers.append(
            {"chunk_index": idx, "question_answer": question_answer}
        )
    return {"question_answers": question_answers}


def judge(state: QState, config: RunnableConfig):
    """Đánh giá chất lượng cặp question và answer, phân loại good/bad."""
    question_answers = state.get("question_answers", [])
    retry = state.get("retry_count", 0)
    prompt = Prompts.EVALUATE_QA_PROMPT.format(question_answers=question_answers)
    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=prompt)]}, config=config
    )

    judgment = response_msg["messages"][-1].content.strip()

    if judgment.startswith("```"):
        judgment = re.sub(r"^```(json)?", "", judgment.strip())
        judgment = re.sub(r"```$", "", judgment.strip())
        judgment = judgment.strip()

    result = json.loads(judgment)
    print("result:", result)
    good_questions = result.get("good_questions", None)
    bad_questions = result.get("bad_questions", None)
    retry += 1
    return {
        "good_questions": good_questions,
        "bad_questions": bad_questions,
        "retry_count": retry,
        "question_answers": question_answers,
    }


def should_continue(state: QState) -> str:
    """Quyết định có tiếp tục loop hay không"""
    retry_count = state.get("retry_count", 0)
    bad_questions = state.get("bad_questions", None)

    if len(bad_questions) > 0 and retry_count < max_retry:
        return "question_node"
    else:
        return "end"


def validate(state: QState, config: RunnableConfig):
    """Xác nhận đầu ra cuối cùng."""
    question_answers = state.get("question_answers", None)

    system_message = SystemMessage(
        content=Prompts.EVALUATE_QUESTIONS_PROMPT.format(
            questions=question_answers,
        )
    )

    prompt = {"messages": [system_message]}
    response_msg = generate_agent.invoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {"quizz": content}


# Xây dựng workflow
workflow = StateGraph(QState)

# Thêm các nodes
workflow.add_node("document_preprocessing", document_preprocessing)
workflow.add_node("question_node", question_node)
workflow.add_node("question_extractor", question_extractor)
workflow.add_node("answer_node", answer_node)
workflow.add_node("judge", judge)
workflow.add_node("validate", validate)

# Định nghĩa luồng
workflow.add_edge(START, "document_preprocessing")
workflow.add_edge("document_preprocessing", "question_node")
workflow.add_edge("question_node", "question_extractor")
workflow.add_edge("question_extractor", "answer_node")
workflow.add_edge("answer_node", "judge")

# Thêm conditional edge từ judge
workflow.add_conditional_edges(
    "judge", should_continue, {"question_node": "question_node", "end": "validate"}
)
workflow.add_edge("validate", END)

# Compile workflow
document_processing_agent = workflow.compile()


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

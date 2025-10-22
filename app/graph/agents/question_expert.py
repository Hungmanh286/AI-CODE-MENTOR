import os
import sys

from langchain_core.runnables.config import RunnableConfig
from docling.document_converter import DocumentConverter
from langchain_core.messages import SystemMessage
from langchain_core.messages import (
    AIMessage,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate

from app.graph.state import State
from app.graph.prompts import Prompts
from app.graph.generate import generate_agent
from app.chatmodel import init_llm
from app.config import settings
from app.services.datasource import get_active_file_id


UPLOAD_DIR = "/home/hungmanh/upload_pdf"
os.makedirs(UPLOAD_DIR, exist_ok=True)
converter = DocumentConverter()


try:
    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["feedback_agent"],
    )
except Exception as e:
    print(f"Fatal Error: Failed to initialize API agent model: {e}")
    sys.exit(1)


def get_human_message_content(state: State):
    messages = state.get("messages", [])
    for msg in messages:
        if msg.__class__.__name__ == "HumanMessage":
            return msg.content
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg.get("content", "")
    return ""


# node trích xuất dữ liệu từ file pdf
async def extract_pdf_text(state: State, config: RunnableConfig):
    session_id = config["configurable"].get("thread_id")

    file_ids = get_active_file_id(session_id)
    all_texts = []
    for file_id in file_ids:
        latest_file = os.path.join(UPLOAD_DIR, f"{file_id}_{session_id}_latest.txt")
        print(f"Looking for latest file at: {latest_file}")
        if os.path.exists(latest_file):
            with open(latest_file, "r") as f:
                file_path = f.read().strip()
                try:
                    if not os.path.exists(file_path):
                        continue
                    doc = converter.convert(file_path).document
                    text = doc.export_to_markdown()
                    all_texts.append(text)
                except Exception:
                    continue
    if not all_texts:
        return {"documents": None}

    big_text = "\n\n".join(all_texts)
    return {"documents": big_text}


# node summarize context
async def summarize_context(state: State, config: RunnableConfig):
    documents = state.get("documents", None)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=10000,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks = splitter.split_text(documents)
    summaries = []

    prompt = PromptTemplate.from_template("""
Tóm tắt đoạn văn sau bằng tiếng Việt, giữ lại thông tin quan trọng:
---
{text}
---
Tóm tắt:
""")
    for chunk in chunks:
        response = await llm.ainvoke(prompt.format(text=chunk), config=config)
        text = response.content
        summaries.append(text)
    return {"summarize_context": summaries}


def check_pdf_exists(state: State, config: RunnableConfig):
    documents = state.get("summarize_context", None)
    if not documents:
        return "web_search"
    else:
        return "pdf_exists"


# node sinh câu hỏi :
async def generate_questions(state: State, config: RunnableConfig):
    documents = state.get("summarize_context", [])
    question = get_human_message_content(state)

    system_message = SystemMessage(
        content=Prompts.GENERATE_QUESTIONS_PROMPT.format(
            question=question,
            documents=documents,
        )
    )
    # system_context = SystemMessage(
    #     content=f"Use the following documents as context for your response:\n\n{documents}"
    # )

    prompt = {"messages": [system_message]}
    response_msg = await generate_agent.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {
        "ai_answer": content,
    }


# node đánh giá câu hỏi :
async def evaluate_questions(state: State, config: RunnableConfig):
    """Đánh giá chất lượng câu hỏi sinh ra từ tài liệu."""
    documents = state.get("summarize_context", [])
    generated_questions = state.get("ai_answer", "")

    # Tạo system prompt
    system_message = SystemMessage(
        content=Prompts.EVALUATE_QUESTIONS_PROMPT.format(
            documents=documents,
            questions=generated_questions,
        )
    )

    prompt = {"messages": [system_message]}

    # Gọi LLM để đánh giá
    response_msg = await generate_agent.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {
        "messages": [AIMessage(content=content, name="evaluation_agent")],
        "evaluation_result": content,
    }


def build_expert_workflow():
    from langgraph.graph import StateGraph, START, END

    workflow = StateGraph(State)
    workflow.add_node("extract_pdf_text", extract_pdf_text)
    workflow.add_node("generate_questions", generate_questions)
    workflow.add_node("summarize_context", summarize_context)
    workflow.add_node("evaluate_questions", evaluate_questions)

    workflow.add_conditional_edges(
        "extract_pdf_text",
        check_pdf_exists,
        {
            "pdf_exists": "generate_questions",
            "web_search": END,
        },
    )
    workflow.add_edge(START, "extract_pdf_text")
    workflow.add_edge("extract_pdf_text", "summarize_context")
    workflow.add_edge("summarize_context", "generate_questions")
    workflow.add_edge("generate_questions", "evaluate_questions")
    workflow.add_edge("evaluate_questions", END)
    return workflow


workflow = build_expert_workflow()
question_expert = workflow.compile()

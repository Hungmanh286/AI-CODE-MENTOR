import os

from langchain_core.runnables.config import RunnableConfig
from docling.document_converter import DocumentConverter
from langchain_core.messages import SystemMessage

from app.graph.state import State
from app.graph.prompts import Prompts
from app.graph.generate import generate_agent
from langchain_core.messages import (
    AIMessage,
)

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
converter = DocumentConverter()


# node trích xuất dữ liệu từ file pdf
async def extract_pdf_text(state: State, config: RunnableConfig):
    session_id = config["configurable"].get("thread_id")

    latest_file = os.path.join(UPLOAD_DIR, f"{session_id}_latest.txt")
    print(f"Looking for latest file at: {latest_file}")
    if os.path.exists(latest_file):
        with open(latest_file, "r") as f:
            file_path = f.read().strip()
    else:
        return {"documents": None}

    try:
        if not os.path.exists(file_path):
            return {"documents": None}

        doc = converter.convert(file_path).document
        text = doc.export_to_markdown()
        return {"documents": text}
    except Exception:
        return {"documents": None}


def check_pdf_exists(state: State, config: RunnableConfig):
    documents = state.get("documents", None)
    if not documents:
        return "web_search"
    else:
        return "pdf_exists"


# node sinh câu hỏi :
async def generate_questions(
    state: State, config: RunnableConfig, system_prompt_content: Prompts = None
):
    documents = state.get("documents", [])
    print(documents)
    system_message = SystemMessage(
        content=Prompts.GENERATE_QUESTIONS_PROMPT.format(
            documents=documents,
        )
    )
    system_context = SystemMessage(
        content=f"Use the following documents as context for your response:\n\n{documents}"
    )

    prompt = {"messages": [system_message] + [system_context]}
    response_msg = await generate_agent.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content

    return {
        "messages": [AIMessage(content=content, name="question_expert")],
        "ai_answer": content,
    }


def build_expert_workflow():
    from langgraph.graph import StateGraph, START, END

    workflow = StateGraph(State)
    workflow.add_node("extract_pdf_text", extract_pdf_text)
    workflow.add_node("generate_questions", generate_questions)

    workflow.add_conditional_edges(
        "extract_pdf_text",
        check_pdf_exists,
        {
            "pdf_exists": "generate_questions",
            "web_search": END,
        },
    )
    workflow.add_edge(START, "extract_pdf_text")
    workflow.add_edge("generate_questions", END)
    return workflow


workflow = build_expert_workflow()
question_expert = workflow.compile()

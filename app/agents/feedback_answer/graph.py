#
import base64
import os

import structlog
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.runnables import RunnableConfig
from langchain_qdrant import QdrantVectorStore
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from app.agents.common.state import (
    State,
    get_conversation_messages,
)
from app.agents.feedback_answer.prompts import Prompts
from app.agents.generator.graph import generate_agent
from app.core.config import settings
from app.core.paths import VAR_DIR
from app.db.datasource import get_active_file_id
from app.infra.minio_client import minio_client
from app.schemas import MessageName

logger = structlog.get_logger(__name__)

# TOOLS = []


embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

url = "http://localhost:6333"


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def image_to_text(image_path):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model=settings.CHAT_MODEL_VISION,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "chuyển ảnh sang text"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content


# lấy câu hỏi
def get_human_message_content(state: State):
    messages = state.get("messages", [])
    for msg in messages:
        # Nếu là HumanMessage
        if msg.__class__.__name__ == "HumanMessage":
            return msg.content
        # Nếu là dict và role là user
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg.get("content", "")
    return ""


# node parse pdf text
def parse_pdf_text(state: State, config: RunnableConfig):
    session_id = config["configurable"].get("thread_id")

    file_ids = get_active_file_id(session_id)
    for file_id in file_ids:
        crop_files = minio_client.list_files(prefix=f"{session_id}/crop_{file_id}")
        if not crop_files:
            return {"documents": None}
        crop_minio_path = crop_files[0]

        try:
            temp_image_path = f"/tmp/crop_{file_id}.png"
            if not minio_client.download_file(crop_minio_path, temp_image_path):
                return {"documents": None}
            text = image_to_text(temp_image_path)
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
            minio_client.delete_file(crop_minio_path)
            return {"documents": text}
        except Exception as e:
            logger.info(f"Error converting image to text: {e}")
            return {"documents": None}


# node điều kiện
def check_pdf(state: State, config: RunnableConfig):
    documents = state.get("documents", None)
    if not documents:
        return "normal"
    else:
        return "not normal"


# điều kiện 1
# node 2: information_retriever
def information_retriever(state: State, config: RunnableConfig) -> str:
    query = get_human_message_content(state)

    collection_name = config["configurable"].get("thread_id")

    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=collection_name,
        url=url,
    )
    doc_retriever = vector_store.as_retriever(
        search_kwargs={"k": 5},
    )
    retrieved_docs = doc_retriever.invoke(query)
    docs = []
    for doc in retrieved_docs:
        doc_obj = doc.model_dump()
        docs.append(doc_obj)
    return {"docs": docs}


# điều kiện 2
# node 3 :
def information_retriever_image(state: State, config: RunnableConfig) -> str:
    query = state.get("documents", "")

    collection_name = config["configurable"].get("thread_id")

    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=collection_name,
        url=url,
    )
    doc_retriever = vector_store.as_retriever(
        search_kwargs={"k": 3},
    )
    retrieved_docs = doc_retriever.invoke(query)
    docs = []
    for doc in retrieved_docs:
        doc_obj = doc.model_dump()
        docs.append(doc_obj)
    return {"docs": docs, "selected_text": query}


# Step 3: Extract documents from tool messages
def documents_node(state: State, config: RunnableConfig) -> dict:
    """Add documents to state."""
    docs = state.get("docs", [])

    documents = "\n".join(item["page_content"] for item in docs)
    return {"documents": documents}


async def answer_node(state: State, config: RunnableConfig):
    """Đánh giá chất lượng câu hỏi sinh ra từ tài liệu."""
    import json

    documents = state.get("documents", [])
    question = get_human_message_content(state)
    selected_text = state.get("selected_text", "")
    docs = state.get("docs", [])

    # Tạo system prompt
    system_message = SystemMessage(
        content=Prompts.FEEDBACK_QUESTIONS_PROMPT.format(
            documents=documents,
            question=question,
            selected_text=selected_text,
        )
    )
    full_conversation_messages = get_conversation_messages(
        state, aimessage_name=[MessageName.answer]
    )
    conversation_messages = trim_messages(
        full_conversation_messages,
        strategy="last",
        token_counter=len,
        max_tokens=settings.HISTORY_CONTEXT_LEN,
        start_on=HumanMessage,
        end_on=(HumanMessage, AIMessage),
        include_system=False,
    )

    prompt = {"messages": [system_message] + conversation_messages}
    response_msg = await generate_agent.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content

    # Lưu query, context và answer vào file JSON
    log_dir = VAR_DIR / "query_logs"
    log_dir.mkdir(exist_ok=True, parents=True)

    # Chỉ lấy page_content từ docs
    context = [doc.get("page_content", "") for doc in docs]

    log_entry = {"query": question, "context": context, "answer": content}

    # Sử dụng 1 file duy nhất cho tất cả session
    log_file = log_dir / "query_context_logs.json"

    # Append vào file nếu đã tồn tại, hoặc tạo mới
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        if not isinstance(existing_data, list):
            existing_data = [existing_data]
        existing_data.append(log_entry)
    else:
        existing_data = [log_entry]

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)

    return {
        "messages": [AIMessage(content=content, name="feedbacks_answer")],
    }


def build_feedbacks_workflow():
    workflow = StateGraph(State)
    workflow.add_node("parse_pdf", parse_pdf_text)

    workflow.add_node("information_retriever", information_retriever)
    workflow.add_node("information_retriever_image", information_retriever_image)
    workflow.add_node(MessageName.feedbacks_answer, answer_node)
    workflow.add_node("documents", documents_node)

    workflow.add_conditional_edges(
        "parse_pdf",
        check_pdf,
        {
            "normal": "information_retriever",
            "not normal": "information_retriever_image",
        },
    )
    workflow.add_edge(START, "parse_pdf")
    workflow.add_edge("information_retriever", "documents")
    workflow.add_edge("information_retriever_image", "documents")
    workflow.add_edge("documents", MessageName.feedbacks_answer)
    workflow.add_edge(MessageName.feedbacks_answer, END)

    return workflow


workflow = build_feedbacks_workflow()
feedbacks_answer = workflow.compile()


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            message = s["messages"][-1]
            if isinstance(message, tuple):
                logger.info(message)
            else:
                message.pretty_print()

    inputs = {"messages": [HumanMessage(content="4 nhân 9 bao nhiêu")]}
    print_stream(feedbacks_answer.stream(inputs, stream_mode="values"))

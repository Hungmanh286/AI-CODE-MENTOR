import os

#
import base64

from openai import OpenAI
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)

from app.graph.state import State
from app.schema import MessageName
from app.config import settings
from app.graph.prompts import Prompts
from app.graph.generate import generate_agent
from app.services.datasource import get_active_file_id
from app.graph.state import (
    get_conversation_messages,
)
from app.services.minio_client import minio_client


TOOLS = []


embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

url = "http://localhost:6333"


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Path to your image
def image_to_text(image_path):
    # Getting the Base64 string
    client = OpenAI(api_key=settings.CHAT_MODEL_VISION_KEY)
    base64_image = encode_image(image_path)

    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "chuyển ảnh sang text"},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{base64_image}",
                    },
                ],
            }
        ],
    )
    return response.output_text


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


# node : lấy ảnh crop và chuyển sang text
# đồng thời xóa ảnh ở trong folder
# xử lý nếu chọn nhiều file cùng lúc
def parse_pdf_text(state: State, config: RunnableConfig):
    session_id = config["configurable"].get("thread_id")

    file_ids = get_active_file_id(session_id)
    for file_id in file_ids:
        # Tìm ảnh crop từ MinIO
        crop_files = minio_client.list_files(prefix=f"{session_id}/crop_{file_id}")
        
        if not crop_files:
            return {"documents": None}
        
        # Lấy file crop đầu tiên
        crop_minio_path = crop_files[0]
        
        try:
            # Download ảnh về tạm
            temp_image_path = f"/tmp/crop_{file_id}.png"
            if not minio_client.download_file(crop_minio_path, temp_image_path):
                return {"documents": None}
            
            # Chuyển ảnh sang text
            text = image_to_text(temp_image_path)
            
            # Xóa file tạm và file trên MinIO
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
            minio_client.delete_file(crop_minio_path)
            return {"documents": text}
        except Exception as e:
            print(f"Error converting image to text: {e}")
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
        search_kwargs={"k": 10},
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
        search_kwargs={"k": 10},
    )
    retrieved_docs = doc_retriever.invoke(query)
    docs = []
    for doc in retrieved_docs:
        doc_obj = doc.model_dump()
        docs.append(doc_obj)
    return {"docs": docs}


# Step 3: Extract documents from tool messages
def documents_node(state: State) -> dict:
    """Add documents to state."""
    docs = state.get("docs", [])
    for doc in docs:
        print(doc["page_content"])
    documents = "\n".join(item["page_content"] for item in docs)
    return {"documents": documents}


async def answer_node(state: State, config: RunnableConfig):
    """Đánh giá chất lượng câu hỏi sinh ra từ tài liệu."""
    documents = state.get("documents", [])
    question = get_human_message_content(state)

    # Tạo system prompt
    system_message = SystemMessage(
        content=Prompts.FEEDBACK_QUESTIONS_PROMPT.format(
            documents=documents,
            question=question,
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
                print(message)
            else:
                message.pretty_print()

    inputs = {"messages": [HumanMessage(content="4 nhân 9 bao nhiêu")]}
    print_stream(feedbacks_answer.stream(inputs, stream_mode="values"))

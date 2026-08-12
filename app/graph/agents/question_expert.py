#

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

from app.chatmodel import init_llm
from app.config import settings
from app.graph.prompts import Prompts
from app.graph.state import (
    State,
    get_conversation_messages,
)
from app.schema import MessageName

TOOLS = []

quizz: list[str] | None = None

embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

url = "http://localhost:6333"


# điều kiện 1
# node 2: information_retriever
def information_retriever(state: State, config: RunnableConfig) -> str:
    query = config["metadata"]["query"]
    collection_name = config["configurable"].get("thread_id")

    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=collection_name,
        url=url,
    )
    doc_retriever = vector_store.as_retriever(
        search_kwargs={"k": 20},
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
    documents = "\n".join(item["page_content"] for item in docs)
    return {"documents": documents}


llm = init_llm(
    model=settings.CHAT_MODEL,
    temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
    tags=["agent"],
)


async def question_node(state: State, config: RunnableConfig):
    """Sinh câu hỏi từ tài liệu"""
    documents = state.get("documents", [])
    # Tạo system prompt
    system_message = SystemMessage(
        content=Prompts.QUESTIONS_GEN_PROMPT.format(document=documents)
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

    # Truyền list of messages trực tiếp thay vì dict
    messages = [system_message] + conversation_messages
    response_msg = llm.invoke(messages, config=config)
    content = response_msg.content
    return {
        "messages": [AIMessage(content=content, name="feedbacks_question")],
        "quizz": content,
    }


def build_feedbacks_workflow():
    workflow = StateGraph(State)

    workflow.add_node("information_retriever", information_retriever)
    workflow.add_node(MessageName.feedbacks_question, question_node)
    workflow.add_node("documents", documents_node)

    workflow.add_edge(START, "information_retriever")
    workflow.add_edge("information_retriever", "documents")
    workflow.add_edge("documents", MessageName.feedbacks_question)
    workflow.add_edge(MessageName.feedbacks_question, END)
    return workflow


workflow = build_feedbacks_workflow()
question_agent = workflow.compile()

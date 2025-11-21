import os
import re

from langchain_core.runnables.config import RunnableConfig
from docling.document_converter import DocumentConverter
from langchain_qdrant import QdrantVectorStore
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from qdrant_client import QdrantClient
from langgraph.graph.state import StateGraph
from langgraph.graph import START, END

from app.graph.state import State
from app.config import settings
from app.services.minio_client import minio_client
from app.services.datasource import get_active_file_id

converter = DocumentConverter()


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


embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)
url = "http://localhost:6333"


# step 1 : node chunk pdf
def parse_and_chunk_pdf(state: State, config: RunnableConfig):
    session_id = config["configurable"].get("thread_id")
    
    # Lấy file từ database
    file_ids = get_active_file_id(session_id)
    if not file_ids:
        return {"documents": None}
    
    file_id = file_ids[0]
    
    # Lấy thông tin file từ database
    from app.schema.upload import UploadFileStatus
    from sqlmodel import Session, select
    
    engine = settings._app_db_engine
    with Session(engine) as session:
        file_record = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
        ).first()
        if not file_record:
            return {"documents": None}
        
        filename = file_record.file_name
        minio_path = f"{session_id}/{filename}"
    
    # Download file từ MinIO về tạm
    temp_local_path = f"/tmp/parse_{filename}"
    if not minio_client.download_file(minio_path, temp_local_path):
        return {"documents": None}

    try:
        converter = DocumentConverter()
        doc = converter.convert(temp_local_path).document
        markdown_text = doc.export_to_markdown()
        
        # Xóa file tạm
        os.remove(temp_local_path)
    except Exception as e:
        print(f"Error converting document: {e}")
        if os.path.exists(temp_local_path):
            os.remove(temp_local_path)
        return {"documents": None}

    # --- Tự động trích xuất topic ---
    base_name = os.path.splitext(filename)[0]

    # Tìm "Bài X - ..." trong tên file
    match = re.search(r"(?i)bài\s*(\d+)[_\-\s]*(.*)", base_name)
    if match:
        lesson_num = match.group(1)
        lesson_title = match.group(2).replace("_", " ").strip().title()
        topic = f"{lesson_title} (Bài {lesson_num})"
    else:
        # Nếu không match thì lấy tiêu đề đầu tiên trong markdown
        first_heading = re.search(r"^#\s*(.+)", markdown_text, re.MULTILINE)
        topic = first_heading.group(1).strip() if first_heading else "Tài liệu học tập"

    # --- Chunk theo section ---
    sections = re.split(r"(?:^|\n)(#{2,3} .+)", markdown_text)
    documents = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=100, separators=["\n\n", "\n", ".", " "]
    )

    for i in range(1, len(sections), 2):
        section_title = sections[i].strip("# ").strip()
        section_text = sections[i + 1].strip()
        chunks = splitter.split_text(section_text)

        for j, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": filename,
                        "section": section_title,
                        "chunk_index": j,
                        "topic": topic,
                    },
                )
            )

    return {"documents": documents}


# step 2 : node embedding document
def embedding_document(state: State, config: RunnableConfig):
    docs = state.get("documents", [])

    collection_name = config["configurable"].get("thread_id")

    client = QdrantClient(url=url)

    existing_collections = [c.name for c in client.get_collections().collections]
    if collection_name not in existing_collections:
        vector_store = QdrantVectorStore.from_documents(
            docs,
            embeddings,
            url=url,
            prefer_grpc=True,
            collection_name=collection_name,
        )
    else:
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        vector_store.add_documents(docs)

    return {"collection_name": collection_name}


# node 3: information_retriever
def information_retriever(state: State, config: RunnableConfig) -> str:
    query = get_human_message_content(state)

    collection_name = state.get("collection_name", "")

    vector_store = QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=collection_name,
        url="http://localhost:6333",
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


subgraph_builder = StateGraph(State)

subgraph_builder.add_node("parse_and_chunk_pdf", parse_and_chunk_pdf)
subgraph_builder.add_node("embedding_document", embedding_document)
subgraph_builder.add_node("information_retriever", information_retriever)
subgraph_builder.add_edge(START, "parse_and_chunk_pdf")
subgraph_builder.add_edge("parse_and_chunk_pdf", "embedding_document")
subgraph_builder.add_edge("embedding_document", "information_retriever")
subgraph_builder.add_edge("information_retriever", END)

subgraph = subgraph_builder.compile()

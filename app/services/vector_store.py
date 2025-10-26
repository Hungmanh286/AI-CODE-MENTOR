import os

from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.config import settings

embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

url = "http://localhost:6333"


def parse_pdf_text(file_path: str):
    try:
        if not os.path.exists(file_path):
            return None
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.MARKDOWN,
        )
        docs = loader.load()
        return docs
    except Exception as e:
        print(f"Error parsing PDF text: {e}")
        return None


def embedding_document(docs, session_id: str):
    collection_name = session_id

    client = QdrantClient(url="http://localhost:6333")

    existing_collections = [c.name for c in client.get_collections().collections]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ],
    )
    splits = [split for doc in docs for split in splitter.split_text(doc.page_content)]
    
    try:
        if collection_name not in existing_collections:
            vector_store = QdrantVectorStore.from_documents(
                splits,
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
            vector_store.add_documents(splits)
    except Exception as e:
        import traceback

        print("Error in embedding_document:", str(e))
        print(traceback.format_exc())
        print("splits type:", type(splits))
        if splits:
            print("First split type:", type(splits[0]))
            print("First split content:", getattr(splits[0], "page_content", splits[0]))

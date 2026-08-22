"""LangChain tools exposed by the document-processing agent."""


import structlog
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agents.document_processing.graph import document_processing_agent
from app.agents.feedback_answer import feedbacks_answer
from app.agents.mindmap import summarize_agent
from app.agents.question_expert import question_agent
from app.agents.summarizer import pdf_summarize_agent
from app.services.events import sse_event_queues
from app.services.quiz_service import process_pdf

logger = structlog.get_logger(__name__)



@tool("using_to_create_questions_for_document")
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

    if session_id not in sse_event_queues:
        import asyncio

        sse_event_queues[session_id] = asyncio.Queue()
        logger.info(
            f"[DocumentProcessing] Created SSE queue for session_id: {session_id}"
        )

    queue = sse_event_queues.get(session_id)

    try:
        # Send start event
        if queue:
            await queue.put({"type": "start", "message": "Bắt đầu xử lý tài liệu..."})
            logger.info(f"[DocumentProcessing] SSE 'start' event sent to {session_id}")

        # Process
        logger.info(
            f"[DocumentProcessing] Starting process_pdf for session_id: {session_id}"
        )
        result = await process_pdf(
            session_id, document_processing_agent=document_processing_agent, query=query
        )
        logger.info(
            f"[DocumentProcessing] process_pdf completed for session_id: {session_id}"
        )
        logger.info(f"[DocumentProcessing] Result: {result}")

        import asyncio

        for i in range(5):
            current_queue = sse_event_queues.get(session_id)
            if current_queue:
                await current_queue.put("document_done")
                logger.info(
                    f"[DocumentProcessing] SSE 'done' event (string) sent to {session_id}"
                )
                break
            else:
                if i < 4:
                    logger.info(
                        f"[DocumentProcessing] SSE queue not found, retrying in 1s ({i + 1}/5)..."
                    )
                    await asyncio.sleep(1)
                else:
                    logger.info(
                        f"[DocumentProcessing] SSE queue not found for session_id: {session_id} after retries (Client disconnected)"
                    )

        return "Đã tạo câu hỏi thành công từ tài liệu."

    except Exception as e:
        logger.info(f"[DocumentProcessing] Error during processing: {e}")
        import traceback

        traceback.print_exc()
        if queue:
            try:
                await queue.put({"type": "error", "message": str(e)})
            except Exception:
                pass
        raise


@tool("question_generation_tool")
async def question_generation_tool(query: str, config: RunnableConfig):
    """
    Công cụ tạo câu hỏi trắc nghiệm nhanh từ chương cụ thể trong tài liệu.
    Sử dụng khi người dùng yêu cầu tạo câu hỏi từ một chương hoặc phần cụ thể.

    Args:
        query: Yêu cầu về câu hỏi (ví dụ: "tạo 10 câu hỏi về chương 3").
        config: Cấu hình chứa session_id.
    """
    import asyncio

    session_id = config["configurable"].get("thread_id")
    if not session_id:
        return "session_id không hợp lệ."

    # Ensure SSE queue exists
    if session_id not in sse_event_queues:
        sse_event_queues[session_id] = asyncio.Queue()
        logger.info(f"[QuestionGen] Created SSE queue for session_id: {session_id}")

    queue = sse_event_queues.get(session_id)

    try:
        # Send start event
        if queue:
            await queue.put({"type": "start", "message": "Đang tạo câu hỏi..."})
            logger.info(f"[QuestionGen] SSE 'start' event sent to {session_id}")

        # Process using process_pdf with question_agent
        logger.info(
            f"[QuestionGen] Starting question generation for session_id: {session_id}"
        )
        result = await process_pdf(
            session_id, document_processing_agent=question_agent, query=query
        )
        logger.info(
            f"[QuestionGen] Question generation completed for session_id: {session_id}"
        )
        logger.info(f"[QuestionGen] Result: {result}")

        # Send done event
        for i in range(5):
            current_queue = sse_event_queues.get(session_id)
            if current_queue:
                await current_queue.put("question_done")
                logger.info(f"[QuestionGen] SSE 'done' event sent to {session_id}")
                break
            else:
                if i < 4:
                    logger.info(
                        f"[QuestionGen] SSE queue not found, retrying in 1s ({i + 1}/5)..."
                    )
                    await asyncio.sleep(1)
                else:
                    logger.info(
                        f"[QuestionGen] SSE queue not found for session_id: {session_id} after retries"
                    )

        return "Đã tạo câu hỏi thành công."

    except Exception as e:
        logger.info(f"[QuestionGen] Error: {e}")
        import traceback

        traceback.print_exc()
        if queue:
            try:
                await queue.put({"type": "error", "message": str(e)})
            except Exception:
                pass
        raise


@tool("mindmap_tool")
async def mindmap_tool(query: str, config: RunnableConfig):
    """
    Công cụ để tạo bản đồ tư duy (mindmap)
    Sử dụng khi người dùng yêu cầu tạo mind map, tạo bản đồ tư duy

    Args:
        query (str): Câu truy vấn của người dùng.
        config (RunnableConfig): Cấu hình chứa session_id.
    """
    session_id = config["configurable"].get("thread_id")
    if not session_id:
        return "session_id không hợp lệ."

    if session_id not in sse_event_queues:
        import asyncio

        sse_event_queues[session_id] = asyncio.Queue()
        logger.info(f"[MindMap] Created SSE queue for session_id: {session_id}")

    queue = sse_event_queues.get(session_id)

    try:
        # Send start event
        if queue:
            await queue.put({"type": "start", "message": "Bắt đầu tạo mind map..."})
            logger.info(f"[MindMap] SSE 'start' event sent to {session_id}")

        # Process
        logger.info(
            f"[MindMap] Starting mind map generation for session_id: {session_id}"
        )
        response_msg = await pdf_summarize_agent.ainvoke(
            {"messages": [HumanMessage(content="Tóm tắt tài liệu")]}, config=config
        )
        logger.info(
            f"[MindMap] Mind map generation completed for session_id: {session_id}"
        )

        content = response_msg["messages"][-1].content

        # Send mindmap_done event với đường dẫn ảnh
        import asyncio

        mindmap_path = f"{session_id}/mindmap.png"
        for i in range(5):
            current_queue = sse_event_queues.get(session_id)
            if current_queue:
                await current_queue.put(
                    {
                        "type": "mindmap_done",
                        "message": content,
                        "mindmap_path": mindmap_path,
                    }
                )
                logger.info(
                    f"[MindMap] SSE 'mindmap_done' event sent to {session_id} with path: {mindmap_path}"
                )
                break
            else:
                if i < 4:
                    logger.info(
                        f"[MindMap] SSE queue not found, retrying in 1s ({i + 1}/5)..."
                    )
                    await asyncio.sleep(1)
                else:
                    logger.info(
                        f"[MindMap] SSE queue not found for session_id: {session_id} after retries"
                    )

        return content

    except Exception as e:
        logger.info(f"[MindMap] Error during processing: {e}")
        import traceback

        traceback.print_exc()
        if queue:
            try:
                await queue.put({"type": "error", "message": str(e)})
            except Exception:
                pass
        raise


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


@tool("summary_tool")
async def summary_tool(query: str, config: RunnableConfig):
    """
    Công cụ tóm tắt  nội dung tài liệu.
    Sử dụng khi người dùng yêu cầu tóm tắt nội dung tài liệu đã tải lên.

    Args:
        query (str): Câu truy vấn của người dùng.
        config (RunnableConfig): Cấu hình chứa session_id.
    """
    response_msg = await summarize_agent.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )
    content = response_msg["messages"][-1].content
    return {"message": content}


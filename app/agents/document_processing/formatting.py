"""Parsing/formatting helpers for the document-processing agent."""

import concurrent.futures
import json
import re

import structlog
from tqdm import tqdm

from app.agents.document_processing.schemas import QuestionWithAnswerList

logger = structlog.get_logger(__name__)


def clean_markdown_json(content: str) -> str:
    """Remove markdown code blocks from JSON/text response

    Args:
        content: Raw content from LLM that may contain ```json or ``` markers

    Returns:
        Cleaned content without markdown markers
    """
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n", "", content)
        content = re.sub(r"\n```\s*$", "", content)
    return content.strip()


def execute_parallel_tasks(
    process_func,
    tasks_data: list,
    max_workers: int,
    desc: str = "Processing",
    disable_progress: bool = True,
) -> dict:
    """Execute tasks in parallel with standardized error handling

    Args:
        process_func: Function to process each task, should return (task_id, result)
        tasks_data: List of task data to process
        max_workers: Maximum number of parallel workers
        desc: Description for progress bar
        disable_progress: Whether to disable tqdm progress bar

    Returns:
        Dictionary mapping task_id to results
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_func, task_data): task_data
            for task_data in tasks_data
        }

        results = {}
        with tqdm(total=len(futures), desc=desc, disable=disable_progress) as pbar:
            for future in concurrent.futures.as_completed(futures):
                task_id, result = future.result()
                results[task_id] = result
                pbar.update(1)

    return results


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
    Xử lý cả trường hợp JSON bị stringify nhiều lần và multiple JSON objects nối liền nhau.
    """
    formatted = ""

    def parse_multiple_json_objects(text):
        """
        Parse string chứa nhiều JSON objects nối liền nhau.
        Ví dụ: '{"id":1,...}{"id":2,...}{"id":3,...}'
        """
        objects = []
        text = text.strip()

        # Remove markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)
            text = text.strip()

        # Try to parse as single JSON array or object first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

        # If that fails, try to split multiple JSON objects
        depth = 0
        start_idx = None

        for i, char in enumerate(text):
            if char == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_text = text[start_idx : i + 1]
                    try:
                        obj = json.loads(obj_text)
                        objects.append(obj)
                    except json.JSONDecodeError as e:
                        logger.info(
                            f"Failed to parse object: {obj_text[:100]}... Error: {e}"
                        )
                    start_idx = None

        return objects

    def parse_nested_json(value):
        """
        Parse JSON đệ quy để xử lý trường hợp bị stringify nhiều lần.
        """
        if isinstance(value, list):
            # Already a list, check if items need parsing
            result = []
            for item in value:
                if isinstance(item, str):
                    sub_items = parse_multiple_json_objects(item)
                    result.extend(sub_items)
                else:
                    result.append(item)
            return result
        elif isinstance(value, dict):
            return [value]
        elif isinstance(value, str):
            return parse_multiple_json_objects(value)
        else:
            return []

    for chunk_id, json_list in data.items():
        formatted += f"**Chunk {chunk_id}**\n\n"

        for json_str in json_list:
            try:
                qa_items = parse_nested_json(json_str)
            except Exception as e:
                formatted += f"Lỗi parse JSON: {e}\n\n"
                logger.info(f"Error parsing chunk {chunk_id}: {e}")
                logger.info(f"Content preview: {str(json_str)[:200]}...")
                continue

            if not qa_items:
                formatted += "Không thể parse được dữ liệu trong chunk này\n\n"
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


def format_qa_for_judge(qa_list: QuestionWithAnswerList, chunk_id: str) -> str:
    """Format structured QuestionWithAnswerList thành text đẹp cho judge node

    Args:
        qa_list: QuestionWithAnswerList object từ answer node
        chunk_id: ID của chunk

    Returns:
        Formatted text string with structure:
        CHUNK X
        CÂU HỎI 1:
        Nội dung: [question]
        Đáp án:
        A. ...
        B. ...
        C. ...
        D. ...

        Đoạn văn liên quan:
        [related_passage]
    """
    formatted_text = f"CHUNK {chunk_id}\n"

    for i, question in enumerate(qa_list.questions, 1):
        formatted_text += f"CÂU HỎI {i}:\n"
        formatted_text += f"Nội dung: {question.question}\n"

        # Add options (đáp án trắc nghiệm)
        formatted_text += "Đáp án:\n"
        for option in question.options:
            formatted_text += f"{option}\n"

        formatted_text += f"\nĐoạn văn liên quan:\n{question.related_passage}\n"

        # Add separator between questions (except for the last one)
        if i < len(qa_list.questions):
            formatted_text += "\n"

    return formatted_text

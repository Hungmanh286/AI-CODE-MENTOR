"""Graph nodes for the document-processing agent."""

import concurrent.futures
import json
import re

import structlog
from langchain_core.runnables import RunnableConfig
from openai import OpenAI
from tqdm import tqdm

from app.agents.base import init_llm
from app.agents.document_processing.formatting import (
    clean_markdown_json,
    execute_parallel_tasks,
    format_qa_for_judge,
)
from app.agents.document_processing.prompts import Prompts
from app.agents.document_processing.schemas import QuestionList, QuestionWithAnswerList
from app.agents.document_processing.state import QState
from app.core.config import settings
from app.db.datasource import get_active_file_id
from app.infra.minio_client import minio_client
from app.services.events import sse_event_queues

logger = structlog.get_logger(__name__)

model = settings.CHAT_MODEL_VISION
api_key = settings.OPENROUTER_API_KEY


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)


max_retry = 2


llm = init_llm(
    model=settings.CHAT_MODEL,
    temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
    tags=["agent"],
)


structured_llm = llm.with_structured_output(QuestionList, method="json_schema")


structured_llm_answer = llm.with_structured_output(
    QuestionWithAnswerList, method="json_schema"
)


# node 1 : chunker
def document_preprocessing(state: QState, config: RunnableConfig):
    """Tiền xử lý tài liệu: tách nhỏ văn bản thành các đoạn (chunks) với overlap."""
    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)
    query = state.get("query", None)
    document_chunks = []

    for file_id in file_ids:
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"
        # docs_minio_path_test = f"{session_id}"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")

                # Chia docs_content thành 10 phần có overlap
                content_length = len(docs_content)
                if content_length < 5000:
                    num_parts = 3
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                elif 5000 <= content_length < 10000:
                    num_parts = 5
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                elif 10000 <= content_length < 30000:
                    num_parts = 8
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20
                else:
                    num_parts = 10
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                logger.info(
                    f"File {file_id}: Total content length = {content_length} chars"
                )
                logger.info(
                    f"Splitting into {num_parts} parts with {overlap_size} chars overlap"
                )
                logger.info(f"Each chunk: ~{chunk_size} chars")

                for part_idx in range(num_parts):
                    start_idx = max(
                        0, part_idx * chunk_size - overlap_size if part_idx > 0 else 0
                    )
                    end_idx = min((part_idx + 1) * chunk_size, content_length)

                    part_content = docs_content[start_idx:end_idx]
                    document_chunks.append(part_content)

                    logger.info(
                        f"Part {part_idx + 1}/{num_parts}: {len(part_content)} chars (from {start_idx} to {end_idx})"
                    )

                logger.info(f"\nCreated {len(document_chunks)} chunks with overlap")
    return {"document_chunks": document_chunks, "query": query}


# node 2 : generate question (với PARALLEL PROCESSING)
def question_node(state: QState, config: RunnableConfig):
    """Sinh câu hỏi tự động từ chunks đã tóm tắt (PARALLEL)."""
    session_id = config["configurable"].get("thread_id")
    queue = sse_event_queues.get(session_id)

    check_questions = {}
    good_questions = state.get("good_questions", None)
    bad_questions = state.get("bad_questions", None)

    document_chunks = state.get("document_chunks", [])
    retry_count = state.get("retry_count", 0)

    def process_single_question(chunk_data):
        """Process một chunk và generate question"""
        idx, chunk = chunk_data
        try:
            if queue:
                try:
                    if retry_count == 0:
                        queue.put_nowait(
                            {
                                "type": "progress",
                                "message": f"Đang tạo câu hỏi chunk {idx + 1}...",
                            }
                        )
                    else:
                        queue.put_nowait(
                            {
                                "type": "progress",
                                "message": f"Đang tạo lại câu hỏi chunk {idx}...",
                            }
                        )
                except Exception as e:
                    logger.info(f"[SSE] Warning: Could not send progress: {e}")

            if retry_count == 0:
                prompt = Prompts.QUESTION_GENERATION_PROMPT.format(chunk=chunk)
            else:
                bad_qs = bad_questions.get(str(idx), [])
                prompt = Prompts.QUESTION_REGENERATION_PROMPT.format(
                    chunk=chunk, bad_qs=bad_qs, good_questions=good_questions
                )

            response_msg = llm.invoke(input=prompt, config=config)
            question = clean_markdown_json(response_msg.content)

            return (idx, question)

        except Exception as e:
            logger.info(f"Error processing chunk {idx}: {e}")
            return (idx, f"[ERROR: Failed to generate question for chunk {idx}]")

    max_workers = 30

    if retry_count == 0:
        chunks_data = [(idx, chunk) for idx, chunk in enumerate(document_chunks)]
        results = execute_parallel_tasks(
            process_single_question,
            chunks_data,
            max_workers=max_workers,
            desc="Generating questions",
        )
        for idx in sorted(results.keys()):
            key = idx
            if key not in check_questions:
                check_questions[key] = []
            check_questions[key].append(results[idx])

        logger.info(f"Generated {len(check_questions)} questions in parallel")

    else:
        if bad_questions is not None and len(bad_questions) > 0:
            chunks_to_regenerate = [
                (int(chunk_index), document_chunks[int(chunk_index)])
                for chunk_index in bad_questions.keys()
            ]

            results = execute_parallel_tasks(
                process_single_question,
                chunks_to_regenerate,
                max_workers=max_workers,
                desc="Regenerating questions",
            )

            for idx in sorted(results.keys()):
                key = str(idx)
                if key not in check_questions:
                    check_questions[key] = []
                check_questions[key].append(results[idx])

            logger.info(f"Regenerated {len(check_questions)} questions in parallel")

    return {
        "check_questions": check_questions,
        "document_chunks": document_chunks,
    }


# node 3 : answer generate (với PARALLEL PROCESSING)
def answer_node(state: QState, config: RunnableConfig):
    """Sinh ra các đáp án cho các câu hỏi dựa trên các đoạn tài liệu đã tóm tắt (PARALLEL)."""
    session_id = config["configurable"].get("thread_id")
    queue = sse_event_queues.get(session_id)

    check_questions = state.get("check_questions", {})
    question_answers = {}

    def process_single_answer(question_data):
        """Process một chunk questions và generate answers"""
        idx, questions = question_data
        try:
            if queue:
                try:
                    queue.put_nowait(
                        {
                            "type": "progress",
                            "message": f"Đang tạo đáp án chunk {idx}...",
                        }
                    )
                except Exception as e:
                    logger.info(f"[SSE] Warning: Could not send progress: {e}")

            formatted_questions = ""
            for q_str in questions:
                try:
                    # Try to parse and format nicely
                    cleaned = q_str.strip()
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
                        cleaned = re.sub(r"\n```\s*$", "", cleaned)
                        cleaned = cleaned.strip()

                    q_list = json.loads(cleaned)
                    for i, q_item in enumerate(q_list, 1):
                        formatted_questions += f"CÂU HỎI {i}:\n"
                        formatted_questions += (
                            f"Nội dung: {q_item.get('question', '')}\n"
                        )
                        formatted_questions += f"\nĐoạn văn liên quan:\n{q_item.get('related_passage', '')}\n"

                except (json.JSONDecodeError, TypeError, AttributeError):
                    formatted_questions += f"\n{q_str}\n"

            formatted_prompt = f"CHUNK {idx}\n{formatted_questions}"

            prompt = Prompts.ANSWER_GENERATION_PROMPT.format(questions=formatted_prompt)

            # Use structured_llm_answer to get QuestionWithAnswerList object
            response_obj = structured_llm_answer.invoke(input=prompt, config=config)

            # Format the structured response for judge node
            formatted_json = format_qa_for_judge(response_obj, str(idx))

            logger.info(
                f"Chunk {idx} - Generated {len(response_obj.questions)} questions with answers"
            )

            return (idx, formatted_json)

        except Exception as e:
            logger.info(f"Error generating answer for chunk {idx}: {e}")
            import traceback

            traceback.print_exc()
            return (idx, None)  # Return None for error cases

    max_workers = 30

    questions_data = [(idx, questions) for idx, questions in check_questions.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_answer, question_data): question_data[0]
            for question_data in questions_data
        }

        results = {}
        with tqdm(total=len(futures), desc="Generating answers", disable=True) as pbar:
            for future in concurrent.futures.as_completed(futures):
                idx, answer = future.result()
                results[idx] = answer
                pbar.update(1)

    for idx in sorted(
        results.keys(),
        key=lambda x: int(x) if isinstance(x, str) and x.isdigit() else x,
    ):
        chunk_idx = str(idx)
        answer_data = results[idx]

        # Skip error cases (None)
        if answer_data is None:
            logger.info(f"Skipping chunk {chunk_idx} due to error in answer generation")
            continue

        if chunk_idx not in question_answers:
            question_answers[chunk_idx] = []
        question_answers[chunk_idx].append(answer_data)

    logger.info(f"Generated answers for {len(question_answers)} chunks in parallel")

    return {
        "question_answers": question_answers,
    }


# chia question thành 10 phần nhỏ để đánh giá song song căn cứ vào số chunk
# node 3 : đánh giá chất lượng câu hỏi, nếu chưa tốt quay lại bước 2
def judge(state: QState, config: RunnableConfig):
    """Đánh giá chất lượng cặp question và answer, phân loại good/bad (PARALLEL)."""
    session_id = config["configurable"].get("thread_id")
    queue = sse_event_queues.get(session_id)

    question_answers = state.get("question_answers", {})
    good_question_answers = state.get("good_question_answers", None)
    good_questions = state.get("good_questions", None)
    retry = state.get("retry_count", 0)
    num_chunks = len(question_answers)

    # Each worker processes 2 chunks
    batch_size = 2
    max_workers = max(
        1, (num_chunks + batch_size - 1) // batch_size
    )  # Ceiling division

    logger.info(
        f"Judge node: Processing {num_chunks} chunks with {max_workers} workers (batch_size={batch_size})"
    )

    def process_judge_batch(batch_data):
        """Process một batch của question_answers"""
        batch_id, batch_dict = batch_data
        try:
            if queue:
                try:
                    queue.put_nowait(
                        {
                            "type": "progress",
                            "message": f"Đang đánh giá batch {batch_id + 1}...",
                        }
                    )
                except Exception as e:
                    logger.info(f"[SSE] Warning: Could not send progress: {e}")

            # batch_dict values are now formatted text strings from format_qa_for_judge()
            # Concatenate all text chunks in the batch
            batch_text = ""
            for chunk_id, text_list in batch_dict.items():
                for text in text_list:
                    batch_text += text + "\n\n"

            prompt = Prompts.EVALUATE_QA_PROMPT.format(question_answers=batch_text)
            response_msg = llm.invoke(input=prompt, config=config)

            judgment = clean_markdown_json(response_msg.content)

            try:
                result = json.loads(judgment)
            except json.JSONDecodeError as e:
                logger.info(f"JSONDecodeError in batch {batch_id}: {e}")
                logger.info(f"Error position: line {e.lineno}, column {e.colno}")

                error_start = max(0, e.pos - 100)
                error_end = min(len(judgment), e.pos + 100)
                logger.info(f"Content around error:\n{judgment[error_start:error_end]}")

                try:
                    if judgment.count("{") > judgment.count("}"):
                        judgment_fixed = judgment + "}"
                    elif judgment.count("[") > judgment.count("]"):
                        judgment_fixed = judgment + "]"
                    else:
                        judgment_fixed = re.sub(
                            r'\\(?![ntr"\\/bfu])', r"\\\\", judgment
                        )
                    result = json.loads(judgment_fixed)

                    logger.info(f"Fixed JSON successfully for batch {batch_id}")
                except json.JSONDecodeError as e2:
                    logger.info(f"Still failed after fix in batch {batch_id}: {e2}")

                    try:
                        valid_json = judgment[: e.pos].rstrip()
                        last_open = max(valid_json.rfind("{"), valid_json.rfind("["))
                        if last_open > 0:
                            partial = valid_json[:last_open]
                            if partial.count("{") > partial.count("}"):
                                partial += "}"
                            if partial.count("[") > partial.count("]"):
                                partial += "]"
                            result = json.loads(partial)
                            logger.info(f"Using partial JSON for batch {batch_id}")
                        else:
                            raise e2
                    except Exception as e3:
                        logger.info(
                            f"All fixes failed for batch {batch_id}: {e3}, using empty result"
                        )
                        result = {
                            "good_question_answer": {},
                            "bad_questions": {},
                            "good_questions": {},
                        }

            return (batch_id, result)

        except Exception as e:
            logger.info(f"Error judging batch {batch_id}: {e}")
            return (
                batch_id,
                {
                    "good_question_answer": {},
                    "bad_questions": {},
                    "good_questions": {},
                },
            )

    chunk_items = list(question_answers.items())
    batches = []
    for i in range(0, len(chunk_items), batch_size):
        batch_dict = dict(chunk_items[i : i + batch_size])
        batches.append((len(batches), batch_dict))

    all_good_question_answer = {}
    all_bad_questions = {}
    all_good_question = {}

    results = execute_parallel_tasks(
        process_judge_batch, batches, max_workers=max_workers, desc="Judging batches"
    )

    # Merge results from all batches - nối các kết quả lại thành một dictionary hoàn chỉnh
    for batch_id in sorted(results.keys()):
        result = results[batch_id]

        good_question_answer = result.get("good_question_answer", {})
        bad_questions_batch = result.get("bad_questions", {})
        good_question_batch = result.get("good_questions", {})

        for k, v in good_question_answer.items():
            if k not in all_good_question_answer:
                all_good_question_answer[k] = []

            if isinstance(v, str):
                try:
                    v_cleaned = v.strip()
                    if v_cleaned.startswith("```"):
                        v_cleaned = re.sub(r"^```(?:json)?\s*\n", "", v_cleaned)
                        v_cleaned = re.sub(r"\n```\s*$", "", v_cleaned)
                        v_cleaned = v_cleaned.strip()

                    parsed_v = json.loads(v_cleaned)
                    if isinstance(parsed_v, list):
                        all_good_question_answer[k].extend(parsed_v)
                    else:
                        all_good_question_answer[k].append(parsed_v)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    # Nếu không parse được, giữ nguyên string
                    all_good_question_answer[k].append(v)
            elif isinstance(v, list):
                all_good_question_answer[k].extend(v)
            else:
                all_good_question_answer[k].append(v)

        for k, v in bad_questions_batch.items():
            if k not in all_bad_questions:
                all_bad_questions[k] = []
            if isinstance(v, list):
                all_bad_questions[k].extend(v)
            else:
                all_bad_questions[k].append(v)

        for k, v in good_question_batch.items():
            if k not in all_good_question:
                all_good_question[k] = []
            if isinstance(v, list):
                all_good_question[k].extend(v)
            else:
                all_good_question[k].append(v)

    # Cập nhật good_questions
    if good_questions is None:
        good_questions = {}
    for k, v in all_good_question.items():
        if k not in good_questions:
            good_questions[k] = []

        if isinstance(v, list):
            good_questions[k].extend(v)
        else:
            good_questions[k].append(v)
    for k, v in all_good_question.items():
        if k not in good_questions:
            good_questions[k] = []

    # Cập nhật good_question_answers
    if good_question_answers is None:
        good_question_answers = {}
    for k, v in all_good_question_answer.items():
        if k not in good_question_answers:
            good_question_answers[k] = []
        if isinstance(v, list):
            good_question_answers[k].extend(v)
        else:
            good_question_answers[k].append(v)

    retry += 1

    logger.info(
        f"Judge completed: {len(all_good_question_answer)} good, {len(all_bad_questions)} bad chunks"
    )

    return {
        "bad_questions": all_bad_questions,
        "retry_count": retry,
        "good_question_answers": good_question_answers,
        "good_questions": good_questions,
    }


# node 5 : đánh giá lại 1 lần nữa rồi cho đáp án cuối cùng
def validate(state: QState, config: RunnableConfig):
    """Xác nhận đầu ra cuối cùng (PARALLEL)."""
    session_id = config["configurable"].get("thread_id")
    queue = sse_event_queues.get(session_id)

    good_question_answers = state.get("good_question_answers", None)
    question_answers = state.get("question_answers", {})
    query = state.get("query", None)

    data_to_validate = (
        good_question_answers if good_question_answers is not None else question_answers
    )

    num_chunks = len(data_to_validate)

    # Each worker processes 2 chunks
    batch_size = 2
    max_workers = max(1, (num_chunks + batch_size - 1) // batch_size)

    logger.info(
        f"Validate node: Processing {num_chunks} chunks with {max_workers} workers (batch_size={batch_size})"
    )

    def process_validate_batch(batch_data):
        """Process một batch của question_answers để validate"""
        batch_id, batch_dict = batch_data
        try:
            if queue:
                try:
                    queue.put_nowait(
                        {
                            "type": "progress",
                            "message": f"Đang đánh giá cuối cùng batch {batch_id + 1}...",
                        }
                    )
                except Exception as e:
                    logger.info(f"[SSE] Warning: Could not send progress: {e}")

            formatted_questions = ""
            for chunk_idx, questions_list in batch_dict.items():
                formatted_questions += f"CHUNK {chunk_idx}:\n"
                if isinstance(questions_list, list):
                    questions_json = json.dumps(
                        questions_list, ensure_ascii=False, indent=2
                    )
                else:
                    questions_json = str(questions_list)

                formatted_questions += questions_json + "\n"
                logger.info(num_chunks)
            prompt_template = Prompts.EVALUATE_AND_SELECT_PROMPT
            prompt = (
                prompt_template.replace("{query}", query)
                .replace("{questions}", formatted_questions)
                .replace("{num_chunks}", str(num_chunks))
            )

            # Invoke structured_llm - response will be a QuestionList Pydantic object
            response_obj = structured_llm.invoke(input=prompt, config=config)

            # Print for debugging
            logger.info(f"Batch {batch_id} - Response type: {type(response_obj)}")
            logger.info(
                f"Batch {batch_id} - Questions count: {len(response_obj.selected_questions)}"
            )

            return (batch_id, response_obj)

        except Exception as e:
            logger.info(f" Error validating batch {batch_id}: {e}")
            import traceback

            traceback.print_exc()
            logger.info(f"   Batch data keys: {list(batch_dict.keys())}")
            logger.info(f"   Sample data (first 500 chars): {str(batch_dict)[:500]}...")
            return (batch_id, None)  # Return None for error cases

    # Chia data_to_validate thành batches
    chunk_items = list(data_to_validate.items())
    batches = []
    for i in range(0, len(chunk_items), batch_size):
        batch_dict = dict(chunk_items[i : i + batch_size])
        batches.append((len(batches), batch_dict))

    results = execute_parallel_tasks(
        process_validate_batch,
        batches,
        max_workers=max_workers,
        desc="Validating batches",
    )

    # Collect all questions from structured responses
    all_questions = []
    for batch_id in sorted(results.keys()):
        response_obj = results[batch_id]

        # Skip error cases (None)
        if response_obj is None:
            logger.info(f"Skipping error batch {batch_id}")
            continue

        # Handle QuestionList Pydantic object
        if isinstance(response_obj, QuestionList):
            for question in response_obj.selected_questions:
                # Convert Pydantic Question object to dict
                all_questions.append(question.dict())
        else:
            logger.info(
                f"Unexpected response type for batch {batch_id}: {type(response_obj)}"
            )
            continue
    final_quizz_json = json.dumps(all_questions, ensure_ascii=False, indent=2)

    logger.info(
        f"Validate completed: Processed {len(results)} batches, total {len(all_questions)} questions"
    )

    return {
        "quizz": final_quizz_json,
    }


def should_continue(state: QState) -> str:
    """Quyết định có tiếp tục loop hay không"""
    retry_count = state.get("retry_count", 0)
    # judge() luôn set bad_questions (dict chunk_id -> list); mặc định {} để node
    # không nổ khi graph được resume từ checkpoint hoặc judge lỗi giữa chừng.
    bad_questions = state.get("bad_questions") or {}

    if len(bad_questions) > 20 and retry_count < max_retry:
        for k, v in bad_questions.items():
            if len(v) > 0:
                return "question_node"
        return "end"

    return "end"

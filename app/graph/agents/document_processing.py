from openai import OpenAI
import json
import re
import concurrent.futures

from tqdm import tqdm
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langfuse.callback import CallbackHandler
from langchain.tools import tool  # noqa


from app.config import settings
from app.graph.prompts import Prompts
from app.routes.notify import (
    sse_event_queues,
)
from app.graph.agents.summarize_agent import pdf_summarize_agent  # noqa
from app.graph.agents.feedbacks_answer import feedbacks_answer  # noqa
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client
from app.chatmodel import init_llm
from app.routes.process_data import process_pdf
from app.graph.generate import generate_agent  # noqa


model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
client = OpenAI(api_key=api_key)


class QState(MessagesState):
    document_chunks: list[str] | None = None
    questions: list[str] | None = None
    question_answers: str | None = None
    judged_answers: list[str] | None = None
    retry_count: int | None = None
    good_questions: list[str] | None = None
    check_questions: str | None = None
    bad_questions: str | None = None
    good_question_answers: list[str] | None = None
    quizz: list[str] | None = None
    query: str | None = None


tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


max_retry = 2


llm = init_llm(
    api_key=settings.CHAT_MODEL_KEY,
    model=settings.CHAT_MODEL,
    temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
    tags=["agent"],
)


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
    Xử lý cả trường hợp JSON bị stringify nhiều lần.
    """
    formatted = ""

    def parse_nested_json(value):
        """
        Parse JSON đệ quy để xử lý trường hợp bị stringify nhiều lần.
        Xử lý cả markdown code fence (```json ... ```).
        Trả về list các câu hỏi cuối cùng.
        """
        current = value
        while isinstance(current, str):
            if current.strip().startswith("```"):
                current = re.sub(r"^```(?:json)?\s*\n", "", current.strip())
                current = re.sub(r"\n```\s*$", "", current.strip())
                current = current.strip()

            try:
                current = json.loads(current)
            except json.JSONDecodeError:
                break
        while (
            isinstance(current, list)
            and len(current) == 1
            and isinstance(current[0], str)
        ):
            try:
                temp = current[0]
                if temp.strip().startswith("```"):
                    temp = re.sub(r"^```(?:json)?\s*\n", "", temp.strip())
                    temp = re.sub(r"\n```\s*$", "", temp.strip())
                    temp = temp.strip()

                current = json.loads(temp)
            except json.JSONDecodeError:
                break

        if isinstance(current, list):
            return current
        elif isinstance(current, dict):
            return [current]
        else:
            return []

    for chunk_id, json_list in data.items():
        formatted += f"**Chunk {chunk_id}**\n\n"

        for json_str in json_list:
            try:
                qa_items = parse_nested_json(json_str)
            except Exception as e:
                formatted += f"⚠️ Lỗi parse JSON: {e}\n\n"
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


# node 1 : chunker
def document_preprocessing(state: QState, config: RunnableConfig):
    """Tiền xử lý tài liệu: tách nhỏ văn bản thành các đoạn (chunks) với overlap."""
    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)
    query = state.get("query", None)
    document_chunks = []

    for file_id in file_ids:
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")

                # Chia docs_content thành 10 phần có overlap
                content_length = len(docs_content)
                num_parts = 10
                chunk_size = content_length // num_parts
                overlap_size = chunk_size // 20  # 20% overlap

                print(f"File {file_id}: Total content length = {content_length} chars")
                print(
                    f"Splitting into {num_parts} parts with {overlap_size} chars overlap"
                )
                print(f"Each chunk: ~{chunk_size} chars")

                for part_idx in range(num_parts):
                    start_idx = max(
                        0, part_idx * chunk_size - overlap_size if part_idx > 0 else 0
                    )
                    end_idx = min((part_idx + 1) * chunk_size, content_length)

                    part_content = docs_content[start_idx:end_idx]
                    document_chunks.append(part_content)

                    print(
                        f"Part {part_idx + 1}/{num_parts}: {len(part_content)} chars (from {start_idx} to {end_idx})"
                    )

                print(f"\nCreated {len(document_chunks)} chunks with overlap")
    return {"document_chunks": document_chunks, "query": query}


# node 2 : generate question (với PARALLEL PROCESSING)
def question_node(state: QState, config: RunnableConfig):
    """Sinh câu hỏi tự động từ chunks đã tóm tắt (PARALLEL)."""
    session_id = config["configurable"].get("thread_id")
    queue = sse_event_queues.get(session_id)

    check_questions = {}
    good_questions = state.get("good_questions", None)
    bad_questions = state.get("bad_questions", None)
    query = state.get("query", None)

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
                    print(f"[SSE] Warning: Could not send progress: {e}")

            if retry_count == 0:
                prompt = Prompts.QUESTION_GENERATION_PROMPT.format(
                    chunk=chunk, query=query
                )
            else:
                bad_qs = bad_questions.get(str(idx), [])
                prompt = Prompts.QUESTION_REGENERATION_PROMPT.format(
                    chunk=chunk, bad_qs=bad_qs, good_questions=good_questions
                )

            response_msg = llm.invoke(input=prompt, config=config)

            question = response_msg.content

            return (idx, question)

        except Exception as e:
            print(f"Error processing chunk {idx}: {e}")
            return (idx, f"[ERROR: Failed to generate question for chunk {idx}]")

    max_workers = 30

    if retry_count == 0:
        chunks_data = [(idx, chunk) for idx, chunk in enumerate(document_chunks)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single_question, chunk_data): chunk_data[0]
                for chunk_data in chunks_data
            }
            results = {}
            with tqdm(
                total=len(futures), desc="Generating questions", disable=True
            ) as pbar:
                for future in concurrent.futures.as_completed(futures):
                    idx, question = future.result()
                    results[idx] = question
                    pbar.update(1)
        for idx in sorted(results.keys()):
            key = idx
            if key not in check_questions:
                check_questions[key] = []
            check_questions[key].append(results[idx])

        print(f"Generated {len(check_questions)} questions in parallel")

    else:
        if bad_questions is not None and len(bad_questions) > 0:
            chunks_to_regenerate = [
                (int(chunk_index), document_chunks[int(chunk_index)])
                for chunk_index in bad_questions.keys()
            ]

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = {
                    executor.submit(process_single_question, chunk_data): chunk_data[0]
                    for chunk_data in chunks_to_regenerate
                }

                results = {}
                with tqdm(
                    total=len(futures), desc="Regenerating questions", disable=True
                ) as pbar:
                    for future in concurrent.futures.as_completed(futures):
                        idx, question = future.result()
                        results[idx] = question
                        pbar.update(1)

            for idx in sorted(results.keys()):
                key = str(idx)
                if key not in check_questions:
                    check_questions[key] = []
                check_questions[key].append(results[idx])

            print(f"Regenerated {len(check_questions)} questions in parallel")

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
                    print(f"[SSE] Warning: Could not send progress: {e}")

            formatted_prompt = f"Chunk {idx}\n" + "\n".join([q for q in questions])

            prompt = Prompts.ANSWER_GENERATION_PROMPT.format(questions=formatted_prompt)
            response_msg = llm.invoke(input=prompt, config=config)
            question_answer = response_msg.content

            return (idx, question_answer)

        except Exception as e:
            print(f"Error generating answer for chunk {idx}: {e}")
            return (idx, f"[ERROR: Failed to generate answer for chunk {idx}]")

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
        if chunk_idx not in question_answers:
            question_answers[chunk_idx] = []
        question_answers[chunk_idx].append(results[idx])

    print(f"Generated answers for {len(question_answers)} chunks in parallel")

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

    # ✅ Sử dụng cố định 4 workers cho judge
    max_workers = 4
    chunks_per_worker = max(1, num_chunks // max_workers)
    batch_size = max(1, chunks_per_worker)

    print(
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
                    print(f"[SSE] Warning: Could not send progress: {e}")

            formatted_batch = format_question_answer_dict(batch_dict)

            prompt = Prompts.EVALUATE_QA_PROMPT.format(question_answers=formatted_batch)
            response_msg = llm.invoke(input=prompt, config=config)

            judgment = response_msg.content.strip()

            if judgment.startswith("```"):
                judgment = re.sub(r"^```(json)?", "", judgment.strip())
                judgment = re.sub(r"```$", "", judgment.strip())
                judgment = judgment.strip()

            try:
                result = json.loads(judgment)
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError in batch {batch_id}: {e}")
                print(f"Error position: line {e.lineno}, column {e.colno}")

                error_start = max(0, e.pos - 100)
                error_end = min(len(judgment), e.pos + 100)
                print(f"Content around error:\n{judgment[error_start:error_end]}")

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

                    print(f"Fixed JSON successfully for batch {batch_id}")
                except json.JSONDecodeError as e2:
                    print(f"Still failed after fix in batch {batch_id}: {e2}")

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
                            print(f"Using partial JSON for batch {batch_id}")
                        else:
                            raise e2
                    except Exception as e3:
                        print(
                            f"All fixes failed for batch {batch_id}: {e3}, using empty result"
                        )
                        result = {
                            "good_question_answer": {},
                            "bad_questions": {},
                            "good_questions": {},
                        }

            return (batch_id, result)

        except Exception as e:
            print(f"Error judging batch {batch_id}: {e}")
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_judge_batch, batch_data): batch_data[0]
            for batch_data in batches
        }

        results = {}
        with tqdm(total=len(futures), desc="Judging batches", disable=True) as pbar:
            for future in concurrent.futures.as_completed(futures):
                batch_id, result = future.result()
                results[batch_id] = result
                pbar.update(1)

    # Merge results from all batches - nối các kết quả lại thành một dictionary hoàn chỉnh
    for batch_id in sorted(results.keys()):
        result = results[batch_id]

        good_question_answer = result.get("good_question_answer", {})
        bad_questions_batch = result.get("bad_questions", {})
        good_question_batch = result.get("good_questions", {})

        # Merge good_question_answer - parse JSON nếu cần
        for k, v in good_question_answer.items():
            if k not in all_good_question_answer:
                all_good_question_answer[k] = []

            # Parse JSON string nếu v là string
            if isinstance(v, str):
                try:
                    # Remove markdown code fences if present
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
                except json.JSONDecodeError:
                    # Nếu không parse được, giữ nguyên
                    all_good_question_answer[k].append(v)
            elif isinstance(v, list):
                all_good_question_answer[k].extend(v)
            else:
                all_good_question_answer[k].append(v)

        # Merge bad_questions
        for k, v in bad_questions_batch.items():
            if k not in all_bad_questions:
                all_bad_questions[k] = []
            if isinstance(v, list):
                all_bad_questions[k].extend(v)
            else:
                all_bad_questions[k].append(v)

        # Merge good_questions
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

    print(
        f"Judge completed: {len(all_good_question_answer)} good, {len(all_bad_questions)} bad chunks"
    )

    return {
        "bad_questions": all_bad_questions,
        "retry_count": retry,
        "good_question_answers": good_question_answers,
        "good_questions": good_questions,
    }


def should_continue(state: QState) -> str:
    """Quyết định có tiếp tục loop hay không"""
    retry_count = state.get("retry_count", 0)
    bad_questions = state.get("bad_questions", None)

    if len(bad_questions) > 20 and retry_count < max_retry:
        for k, v in bad_questions.items():
            if len(v) > 0:
                return "question_node"
        return "end"

    return "end"


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

    max_workers = 3
    chunks_per_worker = max(1, num_chunks // max_workers)
    batch_size = max(1, chunks_per_worker)

    print(
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
                    print(f"[SSE] Warning: Could not send progress: {e}")

            formatted_questions = ""
            for chunk_idx, questions_list in batch_dict.items():
                formatted_questions += f"\n{'=' * 80}\n"
                formatted_questions += f"CHUNK {chunk_idx}:\n"
                formatted_questions += f"{'=' * 80}\n"

                if isinstance(questions_list, list):
                    questions_json = json.dumps(
                        questions_list, ensure_ascii=False, indent=2
                    )
                else:
                    questions_json = str(questions_list)

                formatted_questions += questions_json + "\n"

            prompt_template = Prompts.EVALUATE_AND_SELECT_PROMPT
            prompt = prompt_template.replace("{query}", query).replace(
                "{questions}", formatted_questions
            )

            response_msg = llm.invoke(input=prompt, config=config)
            content = response_msg.content

            return (batch_id, content)

        except Exception as e:
            print(f" Error validating batch {batch_id}: {e}")
            import traceback

            traceback.print_exc()
            print(f"   Batch data keys: {list(batch_dict.keys())}")
            print(f"   Sample data (first 500 chars): {str(batch_dict)[:500]}...")
            return (batch_id, f"[ERROR: Failed to validate batch {batch_id}]")

    # Chia data_to_validate thành batches
    chunk_items = list(data_to_validate.items())
    batches = []
    for i in range(0, len(chunk_items), batch_size):
        batch_dict = dict(chunk_items[i : i + batch_size])
        batches.append((len(batches), batch_dict))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_validate_batch, batch_data): batch_data[0]
            for batch_data in batches
        }

        results = {}
        with tqdm(total=len(futures), desc="Validating batches", disable=True) as pbar:
            for future in concurrent.futures.as_completed(futures):
                batch_id, content = future.result()
                results[batch_id] = content
                pbar.update(1)

    all_questions = []
    for batch_id in sorted(results.keys()):
        batch_content = results[batch_id].strip()

        # Skip error messages
        if batch_content.startswith("[ERROR:"):
            print(f"Skipping error batch {batch_id}")
            continue

        if batch_content.startswith("```"):
            batch_content = re.sub(r"^```(?:json)?\s*\n", "", batch_content)
            batch_content = re.sub(r"\n```\s*$", "", batch_content)
            batch_content = batch_content.strip()

        try:
            batch_questions = json.loads(batch_content)
            if isinstance(batch_questions, list):
                all_questions.extend(batch_questions)
            elif isinstance(batch_questions, dict):
                all_questions.append(batch_questions)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from batch {batch_id}: {e}")
            print(f"Content: {batch_content[:200]}...")
            continue
    final_quizz_json = json.dumps(all_questions, ensure_ascii=False, indent=2)

    print(
        f"Validate completed: Processed {len(results)} batches, total {len(all_questions)} questions"
    )

    return {
        "quizz": final_quizz_json,
    }


workflow = StateGraph(QState)

workflow.add_node("document_preprocessing", document_preprocessing)
workflow.add_node("question_node", question_node)
workflow.add_node("answer_node", answer_node)
workflow.add_node("judge", judge)
workflow.add_node("validate", validate)

workflow.add_edge(START, "document_preprocessing")
workflow.add_edge("document_preprocessing", "question_node")
workflow.add_edge("question_node", "answer_node")
workflow.add_edge("answer_node", "judge")


workflow.add_conditional_edges(
    "judge", should_continue, {"question_node": "question_node", "end": "validate"}
)
workflow.add_edge("validate", END)

document_processing_agent = workflow.compile()


@tool("using_to_create_questions")
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
        print(f"[DocumentProcessing] Created SSE queue for session_id: {session_id}")

    queue = sse_event_queues.get(session_id)

    try:
        # Send start event
        if queue:
            await queue.put({"type": "start", "message": "Bắt đầu xử lý tài liệu..."})
            print(f"[DocumentProcessing] SSE 'start' event sent to {session_id}")

        # Process
        print(f"[DocumentProcessing] Starting process_pdf for session_id: {session_id}")
        result = await process_pdf(
            session_id, document_processing_agent=document_processing_agent, query=query
        )
        print(
            f"[DocumentProcessing] process_pdf completed for session_id: {session_id}"
        )
        print(f"[DocumentProcessing] Result: {result}")

        import asyncio

        for i in range(5):
            current_queue = sse_event_queues.get(session_id)
            if current_queue:
                await current_queue.put("done")
                print(
                    f"[DocumentProcessing] SSE 'done' event (string) sent to {session_id}"
                )
                break
            else:
                if i < 4:
                    print(
                        f"[DocumentProcessing] SSE queue not found, retrying in 1s ({i + 1}/5)..."
                    )
                    await asyncio.sleep(1)
                else:
                    print(
                        f"[DocumentProcessing] SSE queue not found for session_id: {session_id} after retries (Client disconnected)"
                    )

        return "Đã tạo câu hỏi thành công từ tài liệu."

    except Exception as e:
        print(f"[DocumentProcessing] Error during processing: {e}")
        import traceback

        traceback.print_exc()
        if queue:
            try:
                await queue.put({"type": "error", "message": str(e)})
            except Exception:
                pass
        raise


@tool("document_summarize_tool")
async def document_summarize_tool(query: str, config: RunnableConfig):
    """
    Công cụ tóm tắt nội dung tài liệu.
    Sử dụng khi người dùng yêu cầu tạo mind map

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
        print(f"[MindMap] Created SSE queue for session_id: {session_id}")

    queue = sse_event_queues.get(session_id)

    try:
        # Send start event
        if queue:
            await queue.put({"type": "start", "message": "Bắt đầu tạo mind map..."})
            print(f"[MindMap] SSE 'start' event sent to {session_id}")

        # Process
        print(f"[MindMap] Starting mind map generation for session_id: {session_id}")
        response_msg = await pdf_summarize_agent.ainvoke(
            {"messages": [HumanMessage(content="Tóm tắt tài liệu")]}, config=config
        )
        print(f"[MindMap] Mind map generation completed for session_id: {session_id}")

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
                print(
                    f"[MindMap] SSE 'mindmap_done' event sent to {session_id} with path: {mindmap_path}"
                )
                break
            else:
                if i < 4:
                    print(
                        f"[MindMap] SSE queue not found, retrying in 1s ({i + 1}/5)..."
                    )
                    await asyncio.sleep(1)
                else:
                    print(
                        f"[MindMap] SSE queue not found for session_id: {session_id} after retries"
                    )

        return content

    except Exception as e:
        print(f"[MindMap] Error during processing: {e}")
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


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            print(s)

    inputs = {"messages": [HumanMessage(content="Test")]}
    print_stream(
        document_processing_agent.stream(
            inputs, stream_mode="values", config={"callbacks": [tracer]}
        )
    )

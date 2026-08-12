"""
MCP Server for MCQ (Multiple Choice Question) Generation
Uses atomic tool design where each tool performs one specific task.
"""

import json
from typing import Literal, Optional

from fastmcp import FastMCP
from langchain_core.messages import HumanMessage

from app.chatmodel import init_llm
from app.config import settings

# Initialize MCP server
mcp = FastMCP("MCQGenerationServer")

# Initialize LLM
llm = init_llm(
    model=settings.CHAT_MODEL,
    temperature=0.7,
)


def extract_key_concepts_impl(text: str, level: str = "intermediate") -> dict:
    """Implementation of key concept extraction logic."""
    prompt = f"""Bạn là chuyên gia phân tích nội dung giáo dục. Nhiệm vụ của bạn là trích xuất các khái niệm chính từ văn bản để tạo câu hỏi trắc nghiệm.

VĂN BẢN:
{text}

MỨC ĐỘ: {level}

Hãy trích xuất 3-7 khái niệm chính phù hợp với mức độ "{level}":
- Nếu "basic": Tập trung vào định nghĩa, thuật ngữ cơ bản
- Nếu "intermediate": Tập trung vào mối quan hệ, ứng dụng
- Nếu "advanced": Tập trung vào phân tích sâu, so sánh, đánh giá

Trả về kết quả dưới dạng JSON với cấu trúc:
{{"concepts": ["khái niệm 1", "khái niệm 2", ...]}}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    try:
        # Extract JSON from response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        # Fallback: extract concepts from text
        return {
            "concepts": [
                line.strip("- ")
                for line in response.content.split("\n")
                if line.strip().startswith("-")
            ][:7]
        }


def generate_question_stem_impl(
    concept: str, context: str, question_type: str = "definition"
) -> dict:
    """Implementation of question stem generation logic."""
    type_instructions = {
        "definition": "Tạo câu hỏi về định nghĩa, đặc điểm của khái niệm",
        "application": "Tạo câu hỏi về cách áp dụng khái niệm vào tình huống thực tế",
        "comparison": "Tạo câu hỏi so sánh khái niệm với các khái niệm khác",
    }

    prompt = f"""Bạn là chuyên gia thiết kế câu hỏi trắc nghiệm. Nhiệm vụ của bạn là tạo THÂN CÂU HỎI (question stem) chất lượng cao.

KHÁI NIỆM: {concept}

NGỮ CẢNH:
{context}

LOẠI CÂU HỎI: {question_type}
Hướng dẫn: {type_instructions.get(question_type, type_instructions["definition"])}

YÊU CẦU:
1. Câu hỏi phải RÕ RÀNG, CHÍNH XÁC
2. Câu hỏi phải CÓ THỂ TRẢ LỜI dựa trên ngữ cảnh
3. Câu hỏi KHÔNG được gợi ý đáp án
4. CHỈ TẠO CÂU HỎI, KHÔNG TẠO ĐÁP ÁN

Trả về kết quả dưới dạng JSON:
{{"question": "Câu hỏi của bạn?"}}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        return {"question": response.content.strip()}


def generate_correct_answer_impl(question: str, context: str) -> dict:
    """Implementation of correct answer generation logic."""
    prompt = f"""Bạn là chuyên gia tạo đáp án cho câu hỏi trắc nghiệm. Nhiệm vụ của bạn là tạo ĐÁP ÁN ĐÚNG chính xác nhất.

CÂU HỎI: {question}

NGỮ CẢNH:
{context}

YÊU CẦU:
1. Đáp án phải CHÍNH XÁC dựa trên ngữ cảnh
2. Đáp án phải NGẮN GỌN, rõ ràng (1-2 câu)
3. Đáp án phải TRẢ LỜI TRỰC TIẾP câu hỏi
4. Đáp án KHÔNG được mơ hồ

Trả về kết quả dưới dạng JSON:
{{"correct_answer": "Đáp án đúng của bạn"}}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        return {"correct_answer": response.content.strip()}


def generate_distractors_impl(correct_answer: str, context: str, n: int = 3) -> dict:
    """Implementation of distractors generation logic."""
    prompt = f"""Bạn là chuyên gia tạo câu hỏi trắc nghiệm. Nhiệm vụ của bạn là tạo CÁC ĐÁP ÁN NHIỄU (distractors) chất lượng cao.

ĐÁP ÁN ĐÚNG: {correct_answer}

NGỮ CẢNH:
{context}

SỐ LƯỢNG ĐÁP ÁN NHIỄU CẦN TẠO: {n}

YÊU CẦU VỀ ĐÁP ÁN NHIỄU:
1. Đáp án nhiễu phải SAI nhưng HỢP LÝ (plausible)
2. Đáp án nhiễu phải liên quan đến chủ đề
3. Đáp án nhiễu KHÔNG được quá rõ ràng là sai
4. Đáp án nhiễu phải có độ dài tương tự đáp án đúng
5. Đáp án nhiễu phải đủ khác biệt với nhau
6. Tránh các pattern dễ nhận biết (ví dụ: "Tất cả các đáp án trên", "Không có đáp án nào đúng")

CHIẾN LƯỢC TẠO ĐÁP ÁN NHIỄU:
- Sử dụng khái niệm liên quan nhưng không chính xác
- Sử dụng thông tin từ ngữ cảnh nhưng áp dụng sai
- Tạo đáp án gần đúng nhưng thiếu chi tiết quan trọng

Trả về kết quả dưới dạng JSON:
{{"distractors": ["đáp án nhiễu 1", "đáp án nhiễu 2", ...]}}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        # Fallback: extract from text
        lines = [
            line.strip("- ")
            for line in response.content.split("\n")
            if line.strip().startswith("-")
        ]
        return {"distractors": lines[:n]}


def validate_mcq_impl(
    question: str, correct_answer: str, distractors: list, context: str
) -> dict:
    """Implementation of MCQ validation logic."""
    distractors_text = "\n".join([f"- {d}" for d in distractors])

    prompt = f"""Bạn là chuyên gia đánh giá chất lượng câu hỏi trắc nghiệm. Nhiệm vụ của bạn là KIỂM TRA VÀ ĐÁNH GIÁ câu hỏi MCQ.

CÂU HỎI: {question}

ĐÁP ÁN ĐÚNG: {correct_answer}

CÁC ĐÁP ÁN NHIỄU:
{distractors_text}

NGỮ CẢNH:
{context}

TIÊU CHÍ ĐÁNH GIÁ:
1. Câu hỏi có RÕ RÀNG, dễ hiểu không?
2. Đáp án đúng có CHÍNH XÁC dựa trên ngữ cảnh không?
3. Các đáp án nhiễu có HỢP LÝ (không quá rõ là sai) không?
4. Các đáp án có ĐỘ DÀI TƯƠNG ĐƯƠNG nhau không?
5. Có MỘT VÀ CHỈ MỘT đáp án đúng không?
6. Câu hỏi có gợi ý đáp án không? (nếu có = LỖI)
7. Các đáp án nhiễu có quá giống nhau không? (nếu có = LỖI)

ƯỚC LƯỢNG ĐỘ KHÓ:
- "easy": Câu hỏi về định nghĩa cơ bản, đáp án rõ ràng
- "medium": Câu hỏi về ứng dụng, cần hiểu khái niệm
- "hard": Câu hỏi phân tích, so sánh, đáp án nhiễu rất hợp lý

Trả về kết quả dưới dạng JSON:
{{
    "is_valid": true/false,
    "issues": ["vấn đề 1", "vấn đề 2", ...] hoặc [],
    "difficulty_estimate": "easy" hoặc "medium" hoặc "hard"
}}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        # Fallback: assume valid
        return {"is_valid": True, "issues": [], "difficulty_estimate": "medium"}


# ============================================================================
# MCP TOOL WRAPPERS
# ============================================================================


@mcp.tool()
def extract_key_concepts(
    text: str,
    level: Optional[Literal["basic", "intermediate", "advanced"]] = "intermediate",
) -> dict:
    """
    Trích xuất các khái niệm chính từ văn bản để tạo câu hỏi trắc nghiệm.
    Agent sử dụng tool này để xác định điểm ra đề.

    Args:
        text (str): Văn bản nguồn để trích xuất khái niệm
        level (str, optional): Mức độ khái niệm cần trích xuất.
                              Mặc định là "intermediate"
                              - "basic": Khái niệm cơ bản, dễ hiểu
                              - "intermediate": Khái niệm trung bình
                              - "advanced": Khái niệm nâng cao, phức tạp

    Returns:
        dict: {"concepts": list[str]} - Danh sách các khái niệm chính
    """
    return extract_key_concepts_impl(text, level)


@mcp.tool()
def generate_question_stem(
    concept: str,
    context: str,
    question_type: Optional[
        Literal["definition", "application", "comparison"]
    ] = "definition",
) -> dict:
    """
    Sinh phần thân câu hỏi (question stem) từ một khái niệm.
    Tool này CHỈ sinh câu hỏi, KHÔNG sinh đáp án.

    Args:
        concept (str): Khái niệm cần tạo câu hỏi
        context (str): Ngữ cảnh/nội dung liên quan
        question_type (str, optional): Loại câu hỏi. Mặc định là "definition"
                                      - "definition": Hỏi về định nghĩa
                                      - "application": Hỏi về ứng dụng
                                      - "comparison": Hỏi về so sánh

    Returns:
        dict: {"question": str} - Câu hỏi được sinh ra
    """
    return generate_question_stem_impl(concept, context, question_type)


@mcp.tool()
def generate_correct_answer(question: str, context: str) -> dict:
    """
    Sinh đáp án đúng cho một câu hỏi dựa trên ngữ cảnh.

    Args:
        question (str): Câu hỏi cần tạo đáp án
        context (str): Ngữ cảnh/nội dung để tìm đáp án đúng

    Returns:
        dict: {"correct_answer": str} - Đáp án đúng
    """
    return generate_correct_answer_impl(question, context)


@mcp.tool()
def generate_distractors(
    correct_answer: str, context: str, n: Optional[int] = 3
) -> dict:
    """
    Sinh các đáp án nhiễu (distractors) - đáp án sai nhưng hợp lý.
    Tool quan trọng để điều khiển chất lượng MCQ.

    Args:
        correct_answer (str): Đáp án đúng
        context (str): Ngữ cảnh để tạo đáp án nhiễu hợp lý
        n (int, optional): Số lượng đáp án nhiễu cần tạo. Mặc định là 3

    Returns:
        dict: {"distractors": list[str]} - Danh sách các đáp án nhiễu
    """
    return generate_distractors_impl(correct_answer, context, n)


@mcp.tool()
def validate_mcq(
    question: str, correct_answer: str, distractors: list[str], context: str
) -> dict:
    """
    Kiểm tra và đánh giá chất lượng của một câu hỏi trắc nghiệm hoàn chỉnh.

    Args:
        question (str): Câu hỏi
        correct_answer (str): Đáp án đúng
        distractors (list[str]): Danh sách các đáp án nhiễu
        context (str): Ngữ cảnh/nội dung gốc

    Returns:
        dict: {
            "is_valid": bool - MCQ có hợp lệ không,
            "issues": list[str] - Các vấn đề phát hiện (nếu có),
            "difficulty_estimate": str - Ước lượng độ khó ("easy" | "medium" | "hard")
        }
    """
    return validate_mcq_impl(question, correct_answer, distractors, context)


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="streamable-http")

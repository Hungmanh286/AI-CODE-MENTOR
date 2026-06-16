import structlog

import os
import random
import typing_extensions as typing
from docling.document_converter import DocumentConverter
from google import genai

logger = structlog.get_logger(__name__)

client = genai.Client(api_key="AIzaSyCNaj6br2Z27r68fQ_SpHzN_1wBxs4KalE")


def extract_passages(pdf_or_txt_path, chunk_size=500):
    ext = os.path.splitext(pdf_or_txt_path)[1].lower()

    if ext == ".txt":
        logger.info(
            " ".join(
                str(_log_value)
                for _log_value in ("Reading from TXT file:", pdf_or_txt_path)
            )
        )
        with open(pdf_or_txt_path, "r", encoding="utf-8") as f:
            text = f.read()

    else:
        logger.info(
            " ".join(
                str(_log_value)
                for _log_value in ("Processing via Docling:", pdf_or_txt_path)
            )
        )
        converter = DocumentConverter()
        doc = converter.convert(pdf_or_txt_path)
        text = doc.document.export_to_text()

    words = text.split()
    passages = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size]).strip()
        if len(chunk) > 50:
            passages.append(chunk)

    return passages


def generate_distractors(
    passages: typing.List[str], gold_passage: str, k: int = 20
) -> typing.List[str]:
    """
    Chọn ngẫu nhiên k đoạn văn làm nhiễu (distractors), loại trừ đoạn văn vàng (gold_passage).
    """
    pool = [p for p in passages if p != gold_passage]
    random.shuffle(pool)
    return pool[:k]


def gold_passage(
    distractors: typing.List[str], gold_passage: str, insert_indices: typing.List[int]
) -> typing.List[str]:
    """
    Chèn gold_passage vào các vị trí index được chỉ định trong list distractors.
    Lưu ý: Các index này là index MỚI sau mỗi lần chèn.
    Để đơn giản và đảm bảo vị trí tương đối, ta sẽ xây dựng list mới.
    """
    sorted_indices = sorted(list(set(insert_indices)))

    temp_list = list(distractors)

    for index in sorted_indices:
        if index <= len(temp_list):
            temp_list.insert(index, gold_passage)
    return temp_list


def search_related_passage_with_gemini(
    question: str, passages: typing.List[str]
) -> str:
    """
    Sử dụng Gemini để tìm đoạn văn liên quan nhất cho câu hỏi.
    """
    _prompt = f"""Câu hỏi: {question}

Dưới đây là danh sách các đoạn văn. Hãy tìm và trả về CHÍNH XÁC đoạn văn liên quan nhất để trả lời câu hỏi trên.
Chỉ trả về nội dung đoạn văn, không thêm giải thích hay nội dung khác.

Các đoạn văn:
{passages}
"""


if __name__ == "__main__":
    question = "Java là ngôn ngữ lập trình gì và nó được giới thiệu lần đầu khi nào?"
    related_passage = "Java là ngôn ngữ lập trình hướng đối tượng (tựa C++) do Sun Microsystem đưa ra vào giữa thập niên 90. Chương trình viết bằng ngôn ngữ lập trình java có thể chạy trên bất kỳ hệ thống nào có cài máy ảo java Năm 1990: James Gosling và các cộng sự của Công ty Sun Microsystems tham gia dự án Green Team - xây dựng công nghệ mới cho ngành điện tử tiêu dùng (cho các thiết bị điện dân dụng). Để giải quyết vấn đề này nhóm nghiên cứu phát triển đã xây dựng một ngôn ngữ lập trình rất đơn giản cho các hệ máy có thể chạy trên nhiều nền phần cứng khác nhau. Năm 1993 world wide web bắt đầu phát triển. Năm 1994, Sun đưa ra trình duyệt web viết bằng ngôn ngữ oak là webrunner, sau đổi tên thành hostJava. Sau đó, Sun đổi tên oak thành Java và được giới thiệu năm 1995 tại Sunworld 1995."

    passages = extract_passages(
        pdf_or_txt_path="/home/hungmanh/Documents/CodeMentor/app/data/xg8btwgv034yvs1zasbnx_docs.txt"
    )

    # Test với các insert_indices khác nhau: 1, 5, 10, 15, 20
    test_indices = [1, 5, 10, 15, 20]

    for idx in test_indices:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Testing with insert_index = {idx}")
        logger.info(f"{'=' * 80}")

        distractor = generate_distractors(passages, related_passage, k=20)
        context_passages = gold_passage(distractor, related_passage, [idx])

        logger.info(f"\nTổng số đoạn văn trong context: {len(context_passages)}")
        logger.info(f"Gold passage được chèn tại vị trí: {idx}")

        # Sử dụng Gemini để tìm đoạn văn liên quan
        logger.info("\nĐang sử dụng Gemini để tìm kiếm đoạn văn liên quan...")
        found_passage = search_related_passage_with_gemini(question, context_passages)

        logger.info("\nĐoạn văn Gemini tìm được:")
        logger.info(found_passage)

        # Kiểm tra xem Gemini có tìm đúng gold passage không
        is_correct = (
            related_passage in found_passage or found_passage in related_passage
        )
        logger.info(f"\nKết quả: {'✓ ĐÚNG' if is_correct else '✗ SAI'}")

        if is_correct:
            logger.info(f"Gemini đã tìm đúng gold passage tại vị trí {idx}")

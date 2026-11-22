"""Deterministic stand-ins for the LLM/RAG hooks of ``graph.py``.

Used when no backend is configured (``scripts/agui_selfcheck.py``, offline
tests). Never used by ``main.app``, which installs ``backends.default_backend``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .schemas import Intent
from .ui_catalog import (
    CalloutBlock,
    CodeDiffBlock,
    ComparisonTableBlock,
    MindmapNode,
    PresentUI,
    QuizQuestion,
    ShowMindmap,
    ShowQuiz,
    StepItem,
    StepsBlock,
)

QA_ANSWER = (
    "**Đa hình** (polymorphism) cho phép cùng một lời gọi chạy cài đặt khác nhau. "
    "Gọi phương thức ảo qua bảng phương thức có chi phí $O(1)$.\n\n"
    "```java\nAnimal a = new Dog();\na.speak(); // Gâu gâu\n```"
)
SUMMARY = "**Tóm tắt:**\n\n- Đóng gói\n- Kế thừa\n- Đa hình\n- Trừu tượng"
QUIZ_INTRO = "Mình sẽ sinh câu hỏi trắc nghiệm. Bạn chọn số câu và độ khó nhé."
MINDMAP_INTRO = "Đây là sơ đồ tư duy cho chủ đề bạn yêu cầu:"
FOLLOWUPS = [
    "Đa hình lúc biên dịch khác gì đa hình lúc chạy?",
    "Cho ví dụ đa hình với interface trong Java?",
    "Ghi đè (override) và nạp chồng (overload) khác nhau thế nào?",
]
MENTOR_FOLLOWUPS = ["Giải thích đa hình", "So sánh abstract class và interface", "Vẽ mindmap OOP"]


def classify(question: str) -> Intent:
    q = question.lower()
    if re.search(r"tóm tắt|summar", q):
        return "summarize"
    if re.search(r"mindmap|sơ đồ", q):
        return "mindmap"
    if re.search(r"quiz|câu hỏi|kiểm tra|trắc nghiệm", q):
        return "mcq"
    if re.search(r"\?|là gì|tại sao|giải thích|thế nào", q):
        return "ask"
    return "other"


def chunks(document_ids: Sequence[str]) -> list[dict]:
    return [
        {
            "file_id": doc_id,
            "file_name": f"{doc_id}.pdf",
            "page": 1,
            "text": "Đa hình cho phép cùng một lời gọi phương thức chạy cài đặt khác nhau tùy kiểu thực của đối tượng.",
        }
        for doc_id in list(document_ids)[:2]
    ]


_QUIZ_BANK = [
    ("Từ khóa nào dùng để kế thừa một lớp trong Java?", ["implements", "extends", "inherits", "super"], 1,
     "Lớp con dùng `extends` để kế thừa lớp cha; `implements` dành cho interface."),
    ("Tính đóng gói (encapsulation) chủ yếu đạt được bằng cách nào?",
     ["Dùng static", "Dùng private + getter/setter", "Dùng final", "Dùng abstract"], 1,
     "Ẩn trạng thái bằng `private` và chỉ mở qua phương thức công khai."),
    ("Đa hình lúc chạy trong Java dựa trên cơ chế nào?", ["Nạp chồng", "Ghi đè + liên kết động", "Generic", "Annotation"], 1,
     "JVM chọn phương thức ghi đè theo kiểu thực của đối tượng lúc chạy."),
    ("Lớp trừu tượng (abstract class) có thể làm gì mà interface (trước Java 8) không làm được?",
     ["Có hàm khởi tạo và trường thể hiện", "Đa kế thừa", "Khai báo hằng", "Được new trực tiếp"], 0,
     "Abstract class có constructor và trường thể hiện; interface thì không."),
    ("Phát biểu nào đúng về `final` trên một phương thức?",
     ["Không thể gọi", "Không thể ghi đè", "Không thể nạp chồng", "Bắt buộc static"], 1,
     "Phương thức `final` không thể bị lớp con ghi đè."),
]


def quiz(count: int, difficulty: str) -> ShowQuiz:
    level = difficulty if difficulty in ("easy", "medium", "hard") else "medium"
    questions = []
    for i in range(count):
        text, options, answer, explanation = _QUIZ_BANK[i % len(_QUIZ_BANK)]
        suffix = f" (biến thể {i // len(_QUIZ_BANK) + 1})" if i >= len(_QUIZ_BANK) else ""
        questions.append(
            QuizQuestion(
                id=f"q{i + 1}",
                question=f"Câu {i + 1}: {text}{suffix}",
                options=list(options),
                answer_index=answer,
                explanation=explanation,
                difficulty=level,  # type: ignore[arg-type]
            )
        )
    return ShowQuiz(title="Ôn tập lập trình hướng đối tượng", questions=questions)


def mindmap() -> ShowMindmap:
    def node(node_id: str, label: str, *children: MindmapNode) -> MindmapNode:
        return MindmapNode(id=node_id, label=label, children=list(children) or None)

    root = node(
        "root", "Lập trình hướng đối tượng",
        node("enc", "Đóng gói", node("enc1", "private + getter/setter"), node("enc2", "Ẩn chi tiết cài đặt")),
        node("inh", "Kế thừa", node("inh1", "extends"), node("inh2", "super"), node("inh3", "Ghi đè phương thức")),
        node("pol", "Đa hình", node("pol1", "Nạp chồng (compile-time)"), node("pol2", "Ghi đè (runtime)")),
        node("abs", "Trừu tượng", node("abs1", "abstract class"), node("abs2", "interface")),
    )
    return ShowMindmap(title="Sơ đồ tư duy: OOP", root=root)


def present_ui() -> PresentUI:
    return PresentUI(
        title="Abstract class và interface",
        blocks=[
            ComparisonTableBlock(
                type="comparison_table",
                columns=["Tiêu chí", "Abstract class", "Interface"],
                rows=[
                    ["Kế thừa", "Chỉ 1 lớp cha", "Nhiều interface"],
                    ["Trường thể hiện", "Có", "Không (chỉ hằng)"],
                    ["Constructor", "Có", "Không"],
                ],
                highlight_col=2,
            ),
            CalloutBlock(type="callout", tone="tip", title="Mẹo",
                         body_md="Ưu tiên **interface** để mô tả khả năng; dùng abstract class khi cần chia sẻ trạng thái."),
            CodeDiffBlock(
                type="code_diff", language="java",
                before="abstract class Shape { abstract double area(); }",
                after="interface Shape { double area(); }",
                explanation_md="Không có trạng thái chung nên chuyển sang `interface`.",
            ),
            StepsBlock(type="steps", items=[
                StepItem(title="Xác định hành vi chung", body_md="Liệt kê các phương thức."),
                StepItem(title="Có trạng thái chung?", body_md="Có thì dùng abstract class."),
                StepItem(title="Cài đặt", body_md="`implements` hoặc `extends`."),
            ]),
        ],
    )

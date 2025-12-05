import json
import re
from typing import List, Dict
from datetime import datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage
from langfuse.callback import CallbackHandler

from app.graph.generate import generate_agent
from app.graph.test_prompt import (
    Understanding_Evaluation_Prompt,
    Clarity_Evaluation_Prompt,
    Quality_of_Choices_Evaluation_Prompt,
    Difficulty_Evaluation_Prompt,
    Cognitive_Level_Evaluation_Prompt,
    Engagement_Evaluation_Prompt,
)

from app.services.minio_client import minio_client
from app.graph.agents.document_processing import document_processing_agent
from app.config import settings

tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


class QualityTester:
    """Test agent sử dụng document_processing_agent để đánh giá chất lượng câu hỏi"""

    def __init__(self):
        self.results = []
        self.evaluation_prompts = {
            "understanding": Understanding_Evaluation_Prompt,
            "clarity": Clarity_Evaluation_Prompt,
            "quality_of_choices": Quality_of_Choices_Evaluation_Prompt,
            "difficulty": Difficulty_Evaluation_Prompt,
            "cognitive_level": Cognitive_Level_Evaluation_Prompt,
            "engagement": Engagement_Evaluation_Prompt,
        }

        # Hardcode danh sách folders và file_id tương ứng
        # Cấu trúc: {folder_name: file_id}
        # MinIO structure: folder_name/file_id_docs.txt
        # Mỗi folder chỉ chứa 1 file duy nhất
        self.test_data = {
            # "quality_02eb6eda": "wcgx6op29zjhgnamk3rkkj",
            # "quality_45c48cce": "fn3jd6awgbooze9xa7ito",
            # "quality_119d07f2": "3r41au7mq0m67ajre6cuup",
            # "quality_396a405c": "zl4pxbrrp7nvyvuqba9s6k",
            # "quality_9040fc0e": "kg41nifyuqzv5qduk5bs",
            # "quality_16705013": "kb0rm6pjaz4qbrz05p1r3",
            "quality_a09c0f36": "nol5ats9whlmh0dt7u43i",
            "quality_c4c0cfa0": "wsuvkfod09hrb2bjfcynv",
            "quality_ca9c24a7": "0gtqkqqucjnjpi021541ta",
            "quality_d3d94468": "xg8btwgv034yvs1zasbnx",
        }

    def list_quality_folders(self) -> List[str]:
        """Trả về danh sách folders đã hardcode"""
        folders = list(self.test_data.keys())
        print(f"📂 Configured {len(folders)} test folders")
        return folders

    def verify_folder_on_minio(self, folder_name: str) -> bool:
        """Verify file cụ thể tồn tại trên MinIO

        Note: MinIO structure: folder_name/file_id_docs.txt
        Example: quality_d3d94468/zl4pxbrrp7nvyvuqba9s6k_docs.txt
        """
        file_id = self.test_data.get(folder_name)

        if not file_id:
            print(f"   ❌ No file_id configured for folder: {folder_name}")
            return False

        minio_path = f"{folder_name}/{file_id}_docs.txt"

        if minio_client.file_exists(minio_path):
            print(f"   ✓ Found: {minio_path}")
            return True
        else:
            print(f"   ❌ Missing: {minio_path}")
            return False

    def evaluate_question(self, qa: dict, metric: str, config: RunnableConfig) -> int:
        """Đánh giá một câu hỏi theo metric cụ thể"""
        try:
            prompt_template = self.evaluation_prompts[metric]

            question = qa.get("question", "")
            options = "\n".join(qa.get("options", []))
            answer_idx = qa.get("correct_answer", 0)
            answer = (
                qa.get("options", [])[answer_idx]
                if answer_idx < len(qa.get("options", []))
                else ""
            )

            prompt = prompt_template.format(
                question=question, options=options, answer=answer
            )

            response_msg = generate_agent.invoke(
                {"messages": [HumanMessage(content=prompt)]}, config=config
            )
            content = response_msg["messages"][-1].content.strip()

            # Extract score (1-4)
            match = re.search(r"[1-4]", content)
            score = int(match.group()) if match else 0
            return score

        except Exception as e:
            print(f"Error evaluating {metric}: {e}")
            return 0

    def calculate_score_distribution(
        self, evaluated_questions: List[dict]
    ) -> Dict[str, Dict[int, int]]:
        """Đếm số lượng câu hỏi theo từng mức điểm (1-4) cho mỗi metric"""
        distribution = {
            metric: {1: 0, 2: 0, 3: 0, 4: 0}
            for metric in self.evaluation_prompts.keys()
        }

        for qa in evaluated_questions:
            scores = qa.get("scores", {})
            for metric, score in scores.items():
                if 1 <= score <= 4:
                    distribution[metric][score] += 1

        return distribution

    def process_folder(self, folder_name: str, target_questions: int = 100):
        """Xử lý một folder bằng document_processing_agent

        Note: folder_name = session_id (ví dụ: quality_d3d94468)
        Folder chứa nhiều file: quality_d3d94468/file_id1_docs.txt, file_id2_docs.txt...
        """
        print(f"\n{'=' * 80}")
        print(f"📂 Processing folder: {folder_name}")
        print(f"{'=' * 80}")

        print("🔍 Verifying folder on MinIO...")
        if not self.verify_folder_on_minio(folder_name):
            print(f"⚠️  Skipping folder {folder_name} - no files found")
            return None

        print("✅ Ready to process\n")

        # Tạo đường dẫn MinIO đầy đủ
        file_id = self.test_data.get(folder_name)
        minio_path = f"{folder_name}/{file_id}_docs.txt"

        print(f"📄 MinIO path: {minio_path}")

        config = RunnableConfig(
            configurable={"thread_id": minio_path}, callbacks=[tracer]
        )

        query = f"Tạo {target_questions} câu hỏi trắc nghiệm từ tài liệu"

        print("🚀 Running document_processing_agent...")
        print(f"   Query: {query}")

        try:
            result = document_processing_agent.invoke({"query": query}, config=config)
        except Exception as e:
            print(f"❌ Error running agent: {e}")
            return None

        # 4. Extract questions from result
        quizz_json = result.get("quizz", "[]")

        try:
            questions = json.loads(quizz_json)
            if not isinstance(questions, list):
                questions = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse quizz JSON: {e}")
            questions = []

        print(f"Generated {len(questions)} questions")

        if not questions:
            return None

        # 5. Evaluate questions
        print(f"Evaluating {len(questions)} questions...")
        evaluated_questions = []

        for qa in questions[:target_questions]:  # Limit to target
            scores = {}
            for metric in self.evaluation_prompts.keys():
                score = self.evaluate_question(qa, metric, config)
                scores[metric] = score

            avg_score = sum(scores.values()) / len(scores) if scores else 0

            evaluated_questions.append(
                {
                    **qa,
                    "scores": scores,
                    "average_score": round(avg_score, 2),
                }
            )

        # 6. Calculate score distribution
        score_distribution = self.calculate_score_distribution(evaluated_questions)

        # 7. Calculate statistics
        avg_scores = {
            metric: sum(q["scores"].get(metric, 0) for q in evaluated_questions)
            / len(evaluated_questions)
            for metric in self.evaluation_prompts.keys()
        }

        overall_avg = sum(avg_scores.values()) / len(avg_scores)

        folder_result = {
            "folder_name": folder_name,
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(evaluated_questions),
            "score_distribution": score_distribution,
            "average_scores": {k: round(v, 2) for k, v in avg_scores.items()},
            "overall_average": round(overall_avg, 2),
            "questions": evaluated_questions,
        }

        print(f"\n📊 Results for {folder_name}:")
        print(f"   Total questions: {len(evaluated_questions)}")
        print(f"   Overall average: {folder_result['overall_average']:.2f}\n")

        print("   Score Distribution (count per level):")
        for metric in self.evaluation_prompts.keys():
            dist = score_distribution[metric]
            print(
                f"   {metric:20s}: [1⭐:{dist[1]:3d}] [2⭐:{dist[2]:3d}] [3⭐:{dist[3]:3d}] [4⭐:{dist[4]:3d}] (avg: {avg_scores[metric]:.2f})"
            )

        return folder_result

    def run_test(self, max_folders: int = 10, questions_per_doc: int = 100):
        """Chạy test trên nhiều folders"""
        print(f"\n{'=' * 80}")
        print("Starting Quality Test with document_processing_agent")
        print(f"{'=' * 80}\n")

        # 1. List quality folders
        folders = self.list_quality_folders()
        folders = folders[:max_folders]

        if not folders:
            print(" No quality folders found!")
            return

        print(f"Processing {len(folders)} folders...\n")

        # 2. Process each folder
        for folder in folders:
            try:
                result = self.process_folder(folder, questions_per_doc)
                if result:
                    self.results.append(result)
            except Exception as e:
                print(f"Error processing {folder}: {e}")
                continue

        self.save_results()
        self.print_summary()

    def save_results(self):
        """Lưu kết quả vào JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/home/hungmanh/Documents/CodeMentor/app/data/quality_test_results_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n Results saved to: {filename}")

    def print_summary(self):
        """In tổng kết kết quả"""
        if not self.results:
            print("\n No results to summarize!")
            return

        print(f"\n{'=' * 80}")
        print("📈 SUMMARY - Quality Test Results")
        print(f"{'=' * 80}\n")

        total_questions = sum(r["total_questions"] for r in self.results)
        print(f"📊 Total folders processed: {len(self.results)}")
        print(f"📊 Total questions evaluated: {total_questions}\n")

        # Calculate overall score distribution across all documents
        all_metrics = list(self.evaluation_prompts.keys())
        overall_distribution = {
            metric: {1: 0, 2: 0, 3: 0, 4: 0} for metric in all_metrics
        }

        for result in self.results:
            dist = result["score_distribution"]
            for metric in all_metrics:
                for score in [1, 2, 3, 4]:
                    overall_distribution[metric][score] += dist[metric][score]

        # Calculate overall averages
        overall_by_metric = {
            metric: sum(r["average_scores"][metric] for r in self.results)
            / len(self.results)
            for metric in all_metrics
        }

        print("📊 Overall Score Distribution (across all documents):")
        print("-" * 80)
        for metric in all_metrics:
            dist = overall_distribution[metric]
            total = sum(dist.values())
            print(f"{metric:20s}: ", end="")
            print(f"[1⭐:{dist[1]:4d} ({dist[1] / total * 100:5.1f}%)] ", end="")
            print(f"[2⭐:{dist[2]:4d} ({dist[2] / total * 100:5.1f}%)] ", end="")
            print(f"[3⭐:{dist[3]:4d} ({dist[3] / total * 100:5.1f}%)] ", end="")
            print(f"[4⭐:{dist[4]:4d} ({dist[4] / total * 100:5.1f}%)] ", end="")
            print(f"(avg: {overall_by_metric[metric]:.2f})")

        overall_avg = sum(overall_by_metric.values()) / len(overall_by_metric)
        print(f"\n🏆 OVERALL AVERAGE SCORE: {overall_avg:.2f}")

        print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    tester = QualityTester()
    tester.run_test(max_folders=10, questions_per_doc=100)

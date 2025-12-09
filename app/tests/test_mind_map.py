import json
from pathlib import Path


from langfuse.callback import CallbackHandler

from app.chatmodel import init_llm
from app.config import settings

tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


Fullset_Evaluation_PROMPT = """
Task:
Evaluate how well a given summary covers a provided set
of arguments. Assign a score from 1 to 4 based on the
extent of coverage, provide a clear explanation for your
rating, and output the result in a specified JSON format.
Instructions:
• Read the provided arguments and summary carefully.
• Rate the extent to which the arguments are covered
by the summary using the scale described in Table 8.
• Format your evaluation as a JSON object with:
– "explanation": A concise explanation of
your rating.
– "rating": The assigned score (1 to 4).
Example Output Format:
{{
"explanation": "Place your explanation here",
"rating": "Place your rating here"
}}
Input:
• Arguments: {reference_arguments}
• Summary: {generated_summary}
Output:
Provide your evaluation in the specified JSON format.
"""
Argument_Role_Evaluation_PROMPT = """
Task:
Determine whether a summary fully supports a given argument or omits/contradicts key information.
Instructions:
• Output 1 if the summary fully supports the argument
without omissions or contradictions.
• Output 0 if the summary fails to support the argument or contains contradictory or incorrect details
(e.g., logical errors, entity mismatches).
• Respond in a JSON object with:
– "decision": Either 1 or 0.
– "explanation": A brief justification, noting
missing or conflicting content.
Input:
Argument: {argument}
Summary: {summary}
Output Format:
Respond only with a JSON object structured as:
{{
"explanation": "<Brief reasoning for your
decision>",
"decision": <0 or 1>
}}
Note: Think critically before deciding. Do not include
any extra text beyond the JSON output.
"""


def test_summarize_agent():
    """Test Argument Role Evaluation with existing summaries from results folder"""

    # Khởi tạo LLM cho evaluation
    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
        tags=["evaluation"],
    )

    # Đường dẫn thư mục
    # doc_dir = Path("/home/hungmanh/Documents/CodeMentor/app/data/doc")
    mindmap_dir = Path("/home/hungmanh/Documents/CodeMentor/app/data/data_mindmap")
    results_dir = Path("/home/hungmanh/Documents/CodeMentor/app/tests/results")
    results_dir.mkdir(exist_ok=True)

    # Lấy danh sách file results đã có
    result_files = sorted(results_dir.glob("*_result.json"))

    print(f"Found {len(result_files)} result files to evaluate")

    all_results = []

    for result_file in result_files:
        print(f"\n{'=' * 80}")
        print(f"Processing: {result_file.name}")
        print(f"{'=' * 80}")

        try:
            # Đọc summary từ file result
            with open(result_file, "r", encoding="utf-8") as f:
                existing_result = json.load(f)

            summary = existing_result.get("summary", "")
            doc_file_name = existing_result.get("document_file", "")
            mindmap_file_name = existing_result.get("mindmap_file", "")

            print(f"\nDocument: {doc_file_name}")
            print(f"Mindmap file: {mindmap_file_name}")
            print(f"Summary length: {len(summary)} chars")

            # Tìm mindmap file tương ứng
            mindmap_file = mindmap_dir / mindmap_file_name

            if not mindmap_file.exists():
                print(f"Warning: Mindmap file not found: {mindmap_file}")
                continue

            # Đọc arguments từ file mindmap
            with open(mindmap_file, "r", encoding="utf-8") as f:
                mindmap_data = json.load(f)

            # DEBUG: In ra cấu trúc của mindmap_data
            print("\nDEBUG - Mindmap data structure:")
            print(f"  Type: {type(mindmap_data)}")
            if isinstance(mindmap_data, dict):
                print(f"  Keys: {list(mindmap_data.keys())}")
            print(f"  Content preview: {str(mindmap_data)[:200]}...")

            # Chuẩn hóa reference_arguments thành list
            reference_arguments = []

            if isinstance(mindmap_data, dict):
                # Kiểm tra nếu có keys dạng 'arg1', 'arg2', ...
                if any(key.startswith("arg") for key in mindmap_data.keys()):
                    # Lấy values từ các keys arg1, arg2, ... theo thứ tự
                    sorted_keys = sorted(
                        [k for k in mindmap_data.keys() if k.startswith("arg")],
                        key=lambda x: int(x.replace("arg", "")),
                    )
                    reference_arguments = [mindmap_data[k] for k in sorted_keys]
                else:
                    # Thử các key khác
                    reference_arguments = mindmap_data.get(
                        "arguments",
                        mindmap_data.get(
                            "reference_arguments",
                            mindmap_data.get(
                                "items",
                                mindmap_data.get(
                                    "content", mindmap_data.get("data", [])
                                ),
                            ),
                        ),
                    )
            elif isinstance(mindmap_data, list):
                reference_arguments = mindmap_data
            else:
                reference_arguments = mindmap_data

            # Đảm bảo reference_arguments là list
            if not isinstance(reference_arguments, list):
                # Nếu là string, tách thành list dựa trên dấu xuống dòng
                if isinstance(reference_arguments, str):
                    reference_arguments = [
                        arg.strip()
                        for arg in reference_arguments.split("\n")
                        if arg.strip()
                    ]
                    # Nếu chỉ có 1 dòng, thử tách theo dấu chấm
                    if len(reference_arguments) == 1:
                        reference_arguments = [
                            arg.strip() + "."
                            for arg in reference_arguments[0].split(".")
                            if arg.strip()
                        ]
                else:
                    reference_arguments = [str(reference_arguments)]

            print(
                f"Loaded {len(reference_arguments)} arguments from: {mindmap_file.name}"
            )

            # # COMMENT: Evaluation 1: Fullset Evaluation
            # fullset_prompt = Fullset_Evaluation_PROMPT.format(
            #     reference_arguments="\n".join(
            #         [f"{i+1}. {arg}" for i, arg in enumerate(reference_arguments)]
            #     ),
            #     generated_summary=summary,
            # )
            # fullset_response = llm.invoke(fullset_prompt)
            # fullset_eval = json.loads(fullset_response.content)
            # print("\nFullset Evaluation:")
            # print(f"  Rating: {fullset_eval.get('rating')}/4")
            # print(f"  Explanation: {fullset_eval.get('explanation')}")

            fullset_eval = existing_result.get("fullset_evaluation", {})

            # Evaluation 2: Argument Role Evaluation - LUÔN CHẠY
            argument_evals = []
            print(f"\nEvaluating {len(reference_arguments)} arguments individually...")

            for idx, arg in enumerate(reference_arguments):
                try:
                    arg_prompt = Argument_Role_Evaluation_PROMPT.format(
                        argument=arg, summary=summary
                    )
                    arg_response = llm.invoke(arg_prompt)
                    arg_eval = json.loads(arg_response.content)
                    argument_evals.append(
                        {
                            "argument_index": idx,
                            "argument": arg,
                            "decision": arg_eval.get("decision"),
                            "explanation": arg_eval.get("explanation"),
                        }
                    )
                    print(
                        f"  Argument {idx + 1}/{len(reference_arguments)} - Decision: {arg_eval.get('decision')}"
                    )
                except Exception as e:
                    print(f"  Error evaluating argument {idx + 1}: {str(e)}")
                    argument_evals.append(
                        {
                            "argument_index": idx,
                            "argument": arg,
                            "decision": None,
                            "explanation": f"Error: {str(e)}",
                        }
                    )

            # Tính tổng kết
            total_args = len(argument_evals)
            supported_args = sum(1 for e in argument_evals if e.get("decision") == 1)
            support_rate = (supported_args / total_args * 100) if total_args > 0 else 0

            print("\nArgument Support Summary:")
            print(f"  Total arguments: {total_args}")
            print(f"  Supported: {supported_args}")
            print(f"  Support rate: {support_rate:.1f}%")

            # Lưu kết quả
            base_name = result_file.stem.replace("_result", "")
            file_result = {
                "document_file": doc_file_name,
                "mindmap_file": mindmap_file_name,
                "summary": summary,
                "fullset_evaluation": fullset_eval,
                "argument_evaluations": argument_evals,
                "statistics": {
                    "total_arguments": total_args,
                    "supported_arguments": supported_args,
                    "support_rate": support_rate,
                },
            }
            all_results.append(file_result)

            # Lưu kết quả từng file
            output_file = results_dir / f"{base_name}_result.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(file_result, f, indent=2, ensure_ascii=False)

            print(f"\nResult saved to: {output_file}")

        except Exception as e:
            print(f"Error processing {result_file.name}: {str(e)}")
            import traceback

            traceback.print_exc()

    # Lưu tổng hợp tất cả kết quả
    summary_file = results_dir / "all_results_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print(f"All results saved to: {summary_file}")
    print(f"Total files processed: {len(all_results)}")
    print(f"{'=' * 80}")

    return all_results


if __name__ == "__main__":
    test_summarize_agent()

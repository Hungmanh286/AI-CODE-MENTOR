import os
import subprocess
from pathlib import Path


def get_git_diff() -> str:
    """Gets the diff between base branch and current HEAD."""
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    try:
        # Fetch base branch if needed
        subprocess.run(["git", "fetch", "origin", base_ref], check=False)

        # Get diff
        diff_cmd = ["git", "diff", f"origin/{base_ref}...HEAD"]
        result = subprocess.run(diff_cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        print(f"Error getting git diff: {e}")
        return ""


def generate_ai_review(diff_text: str) -> str:
    """Calls OpenAI, Gemini, or OpenRouter to perform code review based on project conventions."""
    if not diff_text.strip():
        return "### ℹ️ AI Code Review\n\nKhông có thay đổi nào trong file code để review."

    # Truncate diff if extremely large to fit model context safely
    max_len = 30000
    if len(diff_text) > max_len:
        diff_text = diff_text[:max_len] + "\n\n...[Diff bị cắt bớt do quá dài]..."

    prompt = f"""Bạn là một Senior Python Code Reviewer chuyên nghiệp. Hãy review pull request diff dưới đây dựa trên các quy chuẩn dự án:

### Quy chuẩn dự án (CODE_CONVENTION.md):
1. **Async/Await**: Bắt buộc dùng async def cho I/O operation. Không dùng blocking calls (time.sleep, requests.get) trong async context. Dùng asyncio.sleep, httpx.AsyncClient.
2. **Logging**: Không dùng `print()`. Sử dụng `app.log.logger` (structlog).
3. **Type Hinting**: Bắt buộc dùng Type Hints cho tham số và return type.
4. **Code Style & Naming**:
   - Line length: <= 100 ký tự.
   - Naming: snake_case cho file/function/variable, PascalCase cho Class, UPPER_CASE cho Constant.
   - Absolute imports: `from app.xxx import yyy` thay vì relative import.
5. **Security & Config**: Không hardcode secrets, API keys, passwords. Phải dùng settings từ `app.config`.
6. **Docstrings**: Sử dụng Google Style docstrings cho public functions/classes.

### Git Diff Cần Review:
```diff
{diff_text}
```

---
### Định dạng Phản hồi (Bằng Tiếng Việt):
Hãy đưa ra nhận xét súc tích, chuyên nghiệp và có thể hành động ngay dưới dạng Markdown:

1. **📊 Tổng quan thay đổi (Summary)**
2. **⚠️ Lỗi & Vi phạm Quy chuẩn (Issues & Violations)** (Nêu rõ file/dòng nếu có)
3. **💡 Đánh giá An toàn & Hiệu năng (Security & Performance)**
4. **✅ Kết luận (Verdict)**: [PASS / NEEDS_IMPROVEMENT / BLOCK]
"""

    # Check for Gemini API key first, then OpenAI / OpenRouter
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")

    if gemini_key:
        try:
            from google import genai

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Gemini API error, falling back if possible: {e}")

    if openai_key:
        try:
            import openai

            client = openai.OpenAI(
                api_key=openai_key,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
            response = client.chat.completions.create(
                model=os.environ.get("CHAT_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a helpful Senior Python Code Reviewer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")

    return "### ⚠️ AI Code Review Warning\n\nKhông tìm thấy API Key (`GEMINI_API_KEY` hoặc `OPENAI_API_KEY`/`OPENROUTER_API_KEY`). Vui lòng cấu hình Secret trong repository."


def main():
    diff = get_git_diff()
    review_markdown = generate_ai_review(diff)

    # Save review to file for GitHub Action step
    output_path = Path("review.md")
    output_path.write_text(review_markdown, encoding="utf-8")
    print("AI Code Review completed successfully and saved to review.md")


if __name__ == "__main__":
    main()

# Quality Evaluation Script

## Mô tả

Script này tự động đánh giá chất lượng câu hỏi trắc nghiệm được sinh ra từ tài liệu. Script sẽ:

1. **Quét MinIO** để tìm tất cả các folder có tên bắt đầu bằng `quality`
2. **Xử lý từng file doc** trong mỗi folder:
   - Chia nhỏ tài liệu thành chunks
   - Sinh ~100 câu hỏi trắc nghiệm (10 câu/chunk)
   - Sinh đáp án và lựa chọn nhiễu cho mỗi câu hỏi
3. **Đánh giá chất lượng** mỗi câu hỏi theo 6 tiêu chí:
   - **Understanding** (Mức độ hiểu biết): Câu hỏi kiểm tra hiểu biết sâu hay chỉ ghi nhớ?
   - **Clarity** (Mức độ rõ ràng): Câu hỏi có rõ ràng, không mơ hồ?
   - **Quality of Choices** (Chất lượng lựa chọn): Các lựa chọn nhiễu có hợp lý?
   - **Difficulty** (Độ khó): Câu hỏi có đủ thách thức?
   - **Cognitive Level** (Mức độ nhận thức): Câu hỏi ở mức nào theo thang Bloom?
   - **Engagement** (Tính hấp dẫn): Câu hỏi có thú vị, kích thích tư duy?
4. **Lưu kết quả** vào file JSON với cấu trúc chi tiết

## Cài đặt

Script sử dụng các thư viện đã có trong project. Đảm bảo đã cài đặt:

```bash
pip install openai langchain langchain-text-splitters tqdm
```

## Cách sử dụng

### 1. Xử lý tất cả các folder quality*

```bash
python app/graph/test_quality_evaluation.py
```

### 2. Xử lý một folder cụ thể

```bash
python app/graph/test_quality_evaluation.py --folder quality_02eb6eda
```

### 3. Tùy chỉnh số worker song song

```bash
python app/graph/test_quality_evaluation.py --max-workers 20
```

### 4. Chỉ định thư mục output

```bash
python app/graph/test_quality_evaluation.py --output-dir my_results
```

### 5. Kết hợp các tùy chọn

```bash
python app/graph/test_quality_evaluation.py \
  --folder quality_02eb6eda \
  --max-workers 15 \
  --output-dir evaluation_results
```

## Cấu trúc Output

Kết quả được lưu trong file JSON với format:

```json
{
  "folder_name": "quality_02eb6eda",
  "file_id": "abc123",
  "object_path": "quality_02eb6eda/abc123_docs.txt",
  "total_questions": 98,
  "questions": [
    {
      "id": 1,
      "question": "Câu hỏi về OOP...",
      "options": [
        "A. Lựa chọn 1",
        "B. Lựa chọn 2",
        "C. Lựa chọn 3",
        "D. Lựa chọn 4"
      ],
      "correct_answer": 0,
      "explanation": "Giải thích đáp án đúng...",
      "related_passage": "Đoạn văn liên quan từ tài liệu...",
      "evaluation_scores": {
        "understanding": 4,
        "clarity": 3,
        "quality_of_choices": 4,
        "difficulty": 3,
        "cognitive_level": 4,
        "engagement": 3,
        "average": 3.5
      }
    }
  ],
  "statistics": {
    "avg_understanding": 3.45,
    "avg_clarity": 3.67,
    "avg_quality_of_choices": 3.23,
    "avg_difficulty": 3.12,
    "avg_cognitive_level": 3.56,
    "avg_engagement": 3.34,
    "overall_average": 3.395
  }
}
```

## Giải thích các thang điểm

Mỗi tiêu chí được đánh giá theo thang điểm 1-4:

### Understanding (Mức độ hiểu biết)
- **4**: Kiểm tra hiểu biết chuyên sâu, yêu cầu tích hợp nhiều ý tưởng
- **3**: Kiểm tra hiểu biết trực tiếp, ít cần tích hợp
- **2**: Chủ yếu ghi nhớ nhưng có chút yêu cầu hiểu khái niệm
- **1**: Chỉ kiểm tra ghi nhớ đơn thuần

### Clarity (Mức độ rõ ràng)
- **4**: Hoàn toàn rõ ràng, không mơ hồ
- **3**: Đa phần rõ ràng nhưng có vài điểm hơi mơ hồ
- **2**: Có mơ hồ đáng kể, dễ gây nhầm lẫn
- **1**: Rất khó hiểu hoặc không rõ

### Quality of Choices (Chất lượng lựa chọn)
- **4**: Lựa chọn nhiễu hợp lý, liên quan, khó loại trừ
- **3**: Lựa chọn nhiễu tương đối tốt nhưng chưa tinh vi
- **2**: Hầu hết dễ loại trừ, chỉ có 1 nhiễu hợp lý
- **1**: Nhiễu rất dễ loại bỏ hoặc không liên quan

### Difficulty (Độ khó)
- **4**: Rất thách thức, yêu cầu hiểu sâu và vận dụng nâng cao
- **3**: Khó vừa phải, cần hiểu và vận dụng khái niệm
- **2**: Tương đối dễ, chủ yếu ghi nhớ hoặc hiểu cơ bản
- **1**: Rất dễ, không cần kiến thức chuyên môn

### Cognitive Level (Mức độ nhận thức - Bloom)
- **4**: Tư duy bậc cao (phân tích, tổng hợp, đánh giá)
- **3**: Vận dụng hoặc hiểu khái niệm
- **2**: Hiểu cơ bản hoặc ghi nhớ
- **1**: Chỉ ghi nhớ máy móc

### Engagement (Tính hấp dẫn)
- **4**: Rất hấp dẫn và kích thích tư duy
- **3**: Hấp dẫn nhưng không đặc biệt
- **2**: Hơi hấp dẫn nhưng đơn giản
- **1**: Không thú vị hoặc không hấp dẫn

## Hiệu năng

- **Song song hóa**: Script xử lý song song cả việc sinh câu hỏi và đánh giá
- **Max workers**: Mặc định 10, có thể tăng lên 20-30 tùy thuộc vào tài nguyên hệ thống
- **Tốc độ ước tính**: 
  - Sinh 100 câu hỏi: ~5-10 phút (tùy số chunks)
  - Đánh giá 100 câu × 6 tiêu chí = 600 API calls: ~10-15 phút
  - **Tổng**: ~15-25 phút/file

## Troubleshooting

### Lỗi kết nối MinIO
```
Error: Could not connect to MinIO
```
→ Kiểm tra MinIO đang chạy và cấu hình trong `.env`

### Lỗi OpenAI API
```
Error: OpenAI API rate limit exceeded
```
→ Giảm `--max-workers` xuống (ví dụ: 5)

### Không tìm thấy folder quality*
```
No quality folders found in MinIO
```
→ Kiểm tra bucket name và prefix trong MinIO

### JSON parse error
```
Failed to parse JSON for chunk X
```
→ Model đôi khi trả về format không chuẩn, script sẽ skip chunk đó và tiếp tục

## Lưu ý

1. **API Cost**: Script này tốn khá nhiều API calls (100 câu × 7 calls/câu ≈ 700 calls/file)
2. **Thời gian xử lý**: Mỗi file mất 15-25 phút, hãy kiên nhẫn
3. **Kết quả**: Các file JSON output có thể dùng để phân tích, so sánh các phương pháp sinh câu hỏi khác nhau

## File liên quan

- `app/graph/test_quality_evaluation.py`: Main script
- `app/graph/test_prompt.py`: Các prompt đánh giá chất lượng
- `app/graph/agents/document_processing.py`: Logic gốc sinh câu hỏi
- `app/services/minio_client.py`: MinIO client service
- `results/`: Thư mục chứa output JSON

## Tác giả

Script được tạo để đánh giá chất lượng hệ thống sinh câu hỏi tự động cho CodeMentor.


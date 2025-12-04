# Quick Start: Quality Evaluation Script

## 🚀 Cách sử dụng nhanh

### Bước 1: Kiểm tra script hoạt động
```bash
python test_quality_script.py
```

Script này sẽ test các components cơ bản:
- ✅ Imports và dependencies
- ✅ Kết nối MinIO
- ✅ List quality folders
- ✅ Document chunking

### Bước 2: Chạy evaluation

#### Option A: Sử dụng shell script (dễ nhất)
```bash
./run_quality_evaluation.sh
```

#### Option B: Chạy trực tiếp Python

**Xử lý tất cả folders:**
```bash
python app/graph/test_quality_evaluation.py
```

**Xử lý một folder cụ thể:**
```bash
python app/graph/test_quality_evaluation.py --folder quality_02eb6eda
```

**Tăng tốc độ (nhiều workers hơn):**
```bash
python app/graph/test_quality_evaluation.py --max-workers 20
```

### Bước 3: Xem kết quả

Kết quả được lưu trong thư mục `results/`:
```bash
ls -lh results/
cat results/quality_02eb6eda_abc123_evaluation.json | jq .statistics
```

## 📋 Yêu cầu hệ thống

- Python 3.8+
- MinIO đang chạy
- OpenAI API key đã cấu hình trong `.env`
- Các folders `quality_*` có file `*_docs.txt` trong MinIO

## ⚙️ Configuration

File `.env` cần có:
```env
CHAT_MODEL_VISION=gpt-4o-mini
CHAT_MODEL_VISION_KEY=sk-...
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123
```

## 📊 Output Format

Mỗi file sẽ tạo ra một JSON với:
```json
{
  "folder_name": "quality_02eb6eda",
  "file_id": "abc123",
  "total_questions": 98,
  "questions": [...],
  "statistics": {
    "avg_understanding": 3.45,
    "avg_clarity": 3.67,
    "overall_average": 3.42
  }
}
```

## ⏱️ Thời gian xử lý ước tính

- **1 file (~100 câu hỏi)**: 20-30 phút
- **10 files**: 3-5 giờ
- **Có thể chạy qua đêm** cho nhiều files

## 🔧 Troubleshooting

### MinIO không kết nối được
```bash
# Kiểm tra MinIO đang chạy
docker ps | grep minio
# hoặc
systemctl status minio
```

### API rate limit
→ Giảm `--max-workers` xuống 5 hoặc 3

### Không tìm thấy quality folders
→ Kiểm tra bucket name trong MinIO

## 📚 Tài liệu đầy đủ

- `README_QUALITY_EVALUATION.md` - Hướng dẫn chi tiết
- `IMPLEMENTATION_SUMMARY.md` - Tổng quan implementation
- `app/graph/test_quality_evaluation.py` - Source code chính

## 💡 Tips

1. **Test trước**: Chạy `test_quality_script.py` để đảm bảo mọi thứ hoạt động
2. **Bắt đầu nhỏ**: Test với 1 folder trước (`--folder quality_xxx`)
3. **Monitor**: Để terminal mở để xem progress bars
4. **Backup**: Kết quả JSON rất giá trị, nên backup thường xuyên

## 🎯 Next Steps

Sau khi có kết quả JSON, bạn có thể:
1. Phân tích thống kê chất lượng câu hỏi
2. So sánh các phương pháp sinh câu hỏi khác nhau
3. Identify câu hỏi chất lượng cao/thấp
4. Cải thiện prompt templates dựa trên insights

---

**Need help?** Check `README_QUALITY_EVALUATION.md` for detailed documentation.


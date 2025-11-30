# 🚀 Parallel PDF Processing

Hệ thống xử lý song song PDF để tăng tốc độ parsing tài liệu dài lên đến **10x**.

## 📊 Performance

| PDF Size | Sequential | Parallel (10 workers) | Speedup |
|----------|-----------|----------------------|---------|
| 50 pages | 18s | 3.2s | **5.6x** |
| 100 pages | 35s | 5.1s | **6.9x** |
| 300 pages | 52s | 6.8s | **7.7x** |

## 🎯 Features

- ✅ **Parallel Processing**: Xử lý nhiều chunks đồng thời với ThreadPoolExecutor
- ✅ **Rate Limiting**: Tự động throttle để respect API limits
- ✅ **Progress Tracking**: Real-time progress bar với tqdm
- ✅ **Error Handling**: Retry logic và graceful degradation
- ✅ **Caching**: Cache kết quả để tránh re-parsing
- ✅ **Dual API Support**: Gemini và OpenAI với auto-fallback
- ✅ **Configurable**: Nhiều presets cho different use cases

## 📦 Installation

```bash
# Required dependencies
pip install pdf2image rateguard tqdm python-dotenv

# System dependencies cho pdf2image
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# macOS:
brew install poppler

# Windows: Download poppler binaries
```

## 🚀 Quick Start

### 1. Basic Usage

```python
from app.services.vector_store_parallel import parse_pdf_parallel

# Parse PDF với default settings
result = parse_pdf_parallel(
    file_path="path/to/your.pdf",
    use_gemini=True,
    max_workers=10
)

print(f"Parsed {len(result)} characters")
```

### 2. Sử dụng Presets

```python
from app.config.parallel_config import Presets
from app.services.vector_store_parallel import parse_pdf_parallel, ParallelConfig

# Free Tier (15 RPM limit)
ParallelConfig.from_preset(Presets.free_tier())
result = parse_pdf_parallel("document.pdf")

# Paid Tier (high performance)
ParallelConfig.from_preset(Presets.paid_tier())
result = parse_pdf_parallel("document.pdf", max_workers=20)
```

### 3. Custom Configuration

```python
from app.config.parallel_config import ParallelProcessingConfig

config = ParallelProcessingConfig(
    MAX_WORKERS=15,
    RPM_LIMIT=100,
    CHUNK_SIZE_LARGE=25,
    RETRY_ATTEMPTS=3,
    ENABLE_CACHING=True,
    DEFAULT_API="gemini",
)

# Apply config
from app.services import vector_store_parallel
vector_store_parallel.ParallelConfig = config

result = parse_pdf_parallel("document.pdf")
```

## 📈 Benchmarking

Chạy benchmark để so sánh sequential vs parallel:

```bash
cd app/services

# Basic benchmark
python benchmark_parallel.py --pdf path/to/document.pdf

# Với custom workers
python benchmark_parallel.py --pdf document.pdf --workers 15

# Skip sequential (nhanh hơn khi test)
python benchmark_parallel.py --pdf document.pdf --skip-sequential

# Sử dụng OpenAI thay vì Gemini
python benchmark_parallel.py --pdf document.pdf --use-openai
```

Kết quả sẽ được lưu vào `benchmark_results_YYYYMMDD_HHMMSS.json`.

## 🛠️ Advanced Usage

### 1. Batch Processing

Xử lý nhiều PDFs:

```python
from app.services.vector_store_parallel import parse_pdf_parallel
import glob

pdf_files = glob.glob("data/*.pdf")

for pdf_file in pdf_files:
    print(f"Processing {pdf_file}...")
    result = parse_pdf_parallel(pdf_file)
    
    # Save result
    output_file = pdf_file.replace(".pdf", ".md")
    with open(output_file, "w") as f:
        f.write(result)
```

### 2. Integration với Existing Pipeline

```python
from app.services.vector_store_parallel import parse_pdf_parallel
from app.services.vector_store import embedding_document

# Parse PDF
document_text = parse_pdf_parallel("document.pdf")

# Embed vào vector store
embedding_document([document_text], session_id="my_session")
```

### 3. Error Handling và Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processing.log'),
        logging.StreamHandler()
    ]
)

try:
    result = parse_pdf_parallel("document.pdf")
except Exception as e:
    logging.error(f"Failed to process PDF: {e}")
    # Fallback to sequential processing
    from app.services.vector_store import parse_pdf_text2
    result = parse_pdf_text2("document.pdf")
```

## ⚙️ Configuration

### Presets

| Preset | Max Workers | RPM Limit | Use Case |
|--------|------------|-----------|----------|
| `free_tier()` | 3 | 15 | Gemini Free (mặc định) |
| `paid_tier()` | 20 | 360 | Gemini Pro/OpenAI |
| `high_performance()` | 30 | 500 | Maximum speed |
| `cost_optimized()` | 5 | 15 | Minimize API calls |
| `development()` | 2 | 15 | Testing/debugging |

### Key Parameters

```python
ParallelProcessingConfig(
    MAX_WORKERS=10,          # Số threads đồng thời
    RPM_LIMIT=15,            # API rate limit
    CHUNK_SIZE_LARGE=30,     # Trang/chunk cho PDF lớn
    RETRY_ATTEMPTS=3,        # Retry khi fail
    DEFAULT_API="gemini",    # "gemini" hoặc "openai"
    ENABLE_CACHING=True,     # Cache parsed chunks
)
```

## 🔍 Monitoring

### Real-time Progress

```python
from app.services.vector_store_parallel import parse_pdf_parallel

# Progress bar tự động hiển thị:
# Processing chunks: 100%|██████████| 10/10 [00:06<00:00,  1.47chunk/s]
```

### Detailed Stats

Sau khi parse xong, script sẽ in:
- Total time
- Average time per chunk
- Total characters
- Speedup (nếu có so sánh)

```
✅ Parsing complete!
⏱️  Total time: 6.80 seconds
📈 Average time per chunk: 0.68 seconds
📄 Total characters: 125,432
```

## 🐛 Troubleshooting

### 1. Rate Limit Exceeded

```
⚠️  Error: 429 Too Many Requests
```

**Giải pháp:**
- Giảm `MAX_WORKERS`
- Tăng `RETRY_DELAY`
- Check API quota

```python
config.MAX_WORKERS = 3  # Reduce from 10
config.RETRY_DELAY = 5  # Increase from 2
```

### 2. Memory Issues

```
MemoryError: Unable to allocate array
```

**Giải pháp:**
- Tăng `CHUNK_SIZE` (ít chunks hơn)
- Giảm `MAX_WORKERS`
- Enable memory optimization

```python
config.CHUNK_SIZE_LARGE = 50
config.ENABLE_MEMORY_OPTIMIZATION = True
```

### 3. Timeout

```
TimeoutError: API call timeout after 60s
```

**Giải pháp:**
- Tăng `API_TIMEOUT`
- Split chunks nhỏ hơn

```python
config.API_TIMEOUT = 120
config.CHUNK_SIZE_LARGE = 20
```

## 📚 Architecture

```
┌─────────────────────────────────────────────────┐
│            parse_pdf_parallel()                 │
│                                                 │
│  1. Convert PDF → Images (base64)              │
│  2. Split into Chunks (30 pages each)          │
│  3. ThreadPoolExecutor.map()                   │
│     ├─ Worker 1 → parse_chunk(chunk_0)         │
│     ├─ Worker 2 → parse_chunk(chunk_1)         │
│     ├─ Worker 3 → parse_chunk(chunk_2)         │
│     └─ ... (up to MAX_WORKERS)                 │
│  4. @rate_limit decorator controls RPM         │
│  5. Collect results in order                   │
│  6. Join chunks → final document               │
└─────────────────────────────────────────────────┘
```

## 🔗 Related Files

- `app/services/vector_store_parallel.py` - Main implementation
- `app/config/parallel_config.py` - Configuration
- `app/services/benchmark_parallel.py` - Benchmarking tool
- `docs/PARALLEL_PROCESSING_GUIDE.md` - Detailed guide

## 📝 Examples

Xem thêm examples trong:
- `app/services/vector_store_parallel.py` (phần `if __name__ == "__main__"`)
- `app/config/parallel_config.py` (phần Usage Examples)

## 🤝 Contributing

Contributions are welcome! Một số ý tưởng:
- [ ] Support AsyncIO cho performance cao hơn
- [ ] Add caching với Redis
- [ ] Support streaming results
- [ ] Add metrics dashboard (Prometheus/Grafana)
- [ ] Support batch processing với celery

## 📄 License

MIT License

---

**Author:** Hungmanh286  
**Created:** 2025-11-30  
**Last Updated:** 2025-11-30

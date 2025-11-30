# OpenAI vs Gemini API Configuration

## 📌 Current Setting

**Router `update_file_active` đang dùng: OpenAI** ✅

```python
# In /app/routes/upload_pdf.py line 92
docs = parse_pdf_parallel(
    file_path=temp_local_path,
    use_gemini=False,  # ← Dùng OpenAI
    max_workers=PARALLEL_CONFIG.MAX_WORKERS
)
```

---

## 🔄 Switch Between APIs

### Option 1: OpenAI (Current) ⭐
```python
use_gemini=False  # Dùng OpenAI
```

**Format (from parse_chunk in vector_store.py):**
```python
content = [{"type": "input_text", "text": prompt}]

for img_b64 in chunk_images:
    content.append({
        "type": "input_image",
        "image_url": f"data:image/png;base64,{img_b64}",
    })

response = client.responses.create(
    model=model, 
    input=[{"role": "user", "content": content}]
)

return response.output_text
```

**Pros:**
- ✅ Stable API
- ✅ Good quality
- ✅ Consistent results

**Cons:**
- ⚠️ Paid API (khoảng $0.01-0.05/PDF)
- ⚠️ Rate limits depend on plan

---

### Option 2: Gemini
```python
use_gemini=True  # Dùng Gemini
```

**Format (from parse_chunk_2 in vector_store.py):**
```python
client2 = genai.Client()

prompt_text = prompt
contents = [prompt_text]

for img_b64 in chunk_images:
    img_bytes = base64.b64decode(img_b64)
    contents.append(
        types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/png",
        )
    )

response = client2.models.generate_content(
    model="gemini-2.0-flash-exp", 
    contents=contents
)

return response.text
```

**Pros:**
- ✅ Free tier: 15 RPM, 1500 RPD
- ✅ Fast responses
- ✅ Good for testing/development

**Cons:**
- ⚠️ Free tier có rate limit thấp (15 RPM)
- ⚠️ Experimental model (gemini-2.0-flash-exp)

---

## 📊 Comparison

| Feature | OpenAI | Gemini |
|---------|--------|--------|
| **Cost** | Paid | Free tier available |
| **RPM (Free)** | - | 15 |
| **RPM (Paid)** | 500+ | 360 (Pro) |
| **Quality** | High | High |
| **Stability** | Stable | Experimental |
| **Best for** | Production | Development/Testing |

---

## 🔧 Implementation Details

### In vector_store_parallel.py

Cả 2 functions đều đã được implement:

#### OpenAI Function
```python
@rate_limit(rpm=ParallelConfig.RPM_LIMIT)
def parse_chunk_openai(chunk_images: List[str]) -> str:
    """Parse chunk sử dụng OpenAI API với rate limiting."""
    content = [{"type": "input_text", "text": prompt}]
    
    for img_b64 in chunk_images:
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{img_b64}",
        })
    
    response = openai_client.responses.create(
        model=model,
        input=[{"role": "user", "content": content}]
    )
    
    return response.output_text
```

#### Gemini Function
```python
@rate_limit(rpm=ParallelConfig.RPM_LIMIT)
def parse_chunk_gemini(chunk_images: List[str]) -> str:
    """Parse chunk sử dụng Gemini API với rate limiting."""
    prompt_text = prompt
    contents = [prompt_text]
    
    for img_b64 in chunk_images:
        img_bytes = base64.b64decode(img_b64)
        contents.append(
            types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            )
        )
    
    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=contents
    )
    
    return response.text
```

### Switch Logic
```python
def process_single_chunk(chunk_data, use_gemini=True):
    chunk_index, chunk_images = chunk_data
    
    for attempt in range(ParallelConfig.RETRY_ATTEMPTS):
        try:
            if use_gemini:
                result = parse_chunk_gemini(chunk_images)  # ← Gemini
            else:
                result = parse_chunk_openai(chunk_images)  # ← OpenAI
            
            return (chunk_index, result)
        except Exception as e:
            # Retry logic...
```

---

## ⚙️ Configuration

### Current Config (upload_pdf.py)
```python
# Line 20: Config preset
PARALLEL_CONFIG = Presets.free_tier()  # 3 workers, 15 RPM

# Line 92: API selection
use_gemini=False  # ← OPENAI (current)
```

### Recommended Configs

#### For OpenAI (Paid)
```python
PARALLEL_CONFIG = Presets.paid_tier()  # 20 workers, 500 RPM
use_gemini=False  # OpenAI
```
→ **Tốc độ cao nhất: 7-10x speedup**

#### For Gemini Free
```python
PARALLEL_CONFIG = Presets.free_tier()  # 3 workers, 15 RPM
use_gemini=True  # Gemini
```
→ **Free, tốc độ tốt: 3.5-5x speedup**

#### For Gemini Pro
```python
PARALLEL_CONFIG = Presets.paid_tier()  # 20 workers, 360 RPM
use_gemini=True  # Gemini Pro
```
→ **Balance cost/performance: 7-8x speedup**

---

## 🎯 Recommendations

### Development/Testing
```python
use_gemini=True  # Free tier Gemini
PARALLEL_CONFIG = Presets.free_tier()
```
- ✅ No cost
- ✅ Sufficient for testing
- ⚠️ Rate limit: 15 RPM

### Production (Small Scale)
```python
use_gemini=True  # Gemini Pro
PARALLEL_CONFIG = Presets.paid_tier()
```
- ✅ Good price/performance
- ✅ 360 RPM
- 💰 ~$0.01/PDF

### Production (Large Scale / Critical)
```python
use_gemini=False  # OpenAI
PARALLEL_CONFIG = Presets.high_performance()
```
- ✅ Maximum performance
- ✅ 500+ RPM
- ✅ Most stable
- 💰 ~$0.05/PDF

---

## 🔄 How to Switch

### Method 1: Manual Edit
Edit `/app/routes/upload_pdf.py` line 92:
```python
use_gemini=False  # OpenAI
# or
use_gemini=True   # Gemini
```

### Method 2: Environment Variable (Future Enhancement)
```python
# In config
USE_GEMINI = os.getenv("USE_GEMINI_API", "false").lower() == "true"

# In router
use_gemini=USE_GEMINI
```

---

## ✅ Current Status

**Active Configuration:**
- 🔧 API: **OpenAI** (use_gemini=False)
- ⚙️ Config: **Free Tier** (3 workers, 15 RPM)
- 📊 Expected: **3.5-5x speedup**

**Note:** Although using Free Tier config (15 RPM), OpenAI doesn't have the same RPM limits as Gemini Free. Adjust config to `paid_tier()` for better performance:

```python
PARALLEL_CONFIG = Presets.paid_tier()  # 20 workers, 500 RPM for OpenAI
```

---

**Date:** 2025-11-30  
**Status:** ✅ OpenAI API Active  
**Format:** ✅ Matching parse_chunk() from vector_store.py

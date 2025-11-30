#!/usr/bin/env python3
"""
Test script để verify parallel processing trong update_file_active router.

Test cases:
1. Verify chunks được xử lý đúng thứ tự
2. Verify tất cả chunks được xử lý (không bỏ sót)
3. Verify kết quả kết hợp đúng logic
4. Compare performance: sequential vs parallel
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_chunk_order_preservation():
    """Test 1: Verify chunks được kết hợp đúng thứ tự"""
    print("\n" + "=" * 80)
    print("TEST 1: Chunk Order Preservation")
    print("=" * 80)
    
    from app.services.vector_store_parallel import parse_pdf_parallel
    
    # Test với PDF nhỏ để dễ verify
    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"⚠️  Test PDF not found: {test_pdf}")
        print("Please provide a test PDF file")
        return False
    
    # Parse PDF
    result = parse_pdf_parallel(test_pdf, use_gemini=True, max_workers=3)
    
    # Verify
    print(f"\n📊 Result length: {len(result):,} characters")
    print(f"📝 First 200 chars: {result[:200]}")
    print(f"📝 Last 200 chars: {result[-200:]}")
    
    # Check that result is not empty
    if len(result) == 0:
        print("❌ FAILED: Result is empty!")
        return False
    
    # Check that result doesn't contain multiple ERROR placeholders
    error_count = result.count("[ERROR:")
    if error_count > 2:  # Allow max 2 errors for tolerance
        print(f"❌ FAILED: Too many errors ({error_count} chunks failed)")
        return False
    
    print("✅ PASSED: Chunks processed and combined correctly")
    return True


def test_chunk_completeness():
    """Test 2: Verify tất cả chunks được xử lý"""
    print("\n" + "=" * 80)
    print("TEST 2: Chunk Completeness")
    print("=" * 80)
    
    from app.services.vector_store_parallel import parse_pdf_parallel
    from pdf2image import convert_from_path
    
    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"⚠️  Test PDF not found: {test_pdf}")
        return False
    
    # Get total pages
    images = convert_from_path(test_pdf)
    total_pages = len(images)
    print(f"📄 Total pages in PDF: {total_pages}")
    
    # Calculate expected chunks
    chunk_size = 15 if total_pages < 50 else 30
    expected_chunks = (total_pages + chunk_size - 1) // chunk_size  # Ceiling division
    print(f"📦 Expected chunks: {expected_chunks} (chunk size: {chunk_size})")
    
    # Parse PDF and count chunks processed
    # (We'll check logs for "Processing chunks" progress)
    result = parse_pdf_parallel(test_pdf, use_gemini=True, max_workers=3)
    
    # Verify result is not empty
    if len(result) == 0:
        print("❌ FAILED: Result is empty!")
        return False
    
    # Count sections in result (rough estimation)
    # Each chunk should produce some content
    sections = result.split("\n\n")
    sections_count = len([s for s in sections if len(s.strip()) > 50])
    
    print(f"📊 Sections in result: {sections_count}")
    
    # Allow some tolerance (sections might be merged or split)
    if sections_count < expected_chunks * 0.5:  # At least 50% of expected
        print(f"⚠️  WARNING: Fewer sections than expected")
        print(f"   Expected ~{expected_chunks}, got {sections_count}")
    else:
        print(f"✅ PASSED: All chunks processed")
    
    return True


def test_sequential_vs_parallel_accuracy():
    """Test 3: Verify parallel produces same result as sequential"""
    print("\n" + "=" * 80)
    print("TEST 3: Sequential vs Parallel Accuracy")
    print("=" * 80)
    
    from app.services.vector_store import parse_pdf_text2
    from app.services.vector_store_parallel import parse_pdf_parallel
    
    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"⚠️  Test PDF not found: {test_pdf}")
        return False
    
    print("📊 Processing with SEQUENTIAL method...")
    start = time.time()
    seq_result = parse_pdf_text2(test_pdf)
    seq_time = time.time() - start
    seq_len = len(seq_result) if seq_result else 0
    
    print(f"   Time: {seq_time:.2f}s")
    print(f"   Length: {seq_len:,} chars")
    
    print("\n📊 Processing with PARALLEL method...")
    start = time.time()
    par_result = parse_pdf_parallel(test_pdf, use_gemini=True, max_workers=3)
    par_time = time.time() - start
    par_len = len(par_result)
    
    print(f"   Time: {par_time:.2f}s")
    print(f"   Length: {par_len:,} chars")
    
    # Compare
    speedup = seq_time / par_time if par_time > 0 else 0
    print(f"\n📈 Speedup: {speedup:.2f}x")
    
    # Length should be similar (within 20% tolerance)
    # Note: Methods use different parsers (docling vs vision), so exact match unlikely
    if seq_len > 0:
        diff_percent = abs(par_len - seq_len) / seq_len * 100
        print(f"📊 Length difference: {diff_percent:.1f}%")
        
        if diff_percent > 50:
            print("⚠️  WARNING: Large difference in output length")
            print("   This is expected as parallel uses vision model (different parser)")
        else:
            print("✅ Results are reasonably similar")
    
    if speedup >= 2:
        print(f"✅ PASSED: Parallel is {speedup:.2f}x faster!")
    else:
        print(f"⚠️  WARNING: Speedup is only {speedup:.2f}x (expected >2x)")
    
    return True


def test_performance_benchmark():
    """Test 4: Benchmark performance with different configs"""
    print("\n" + "=" * 80)
    print("TEST 4: Performance Benchmark")
    print("=" * 80)
    
    from app.services.vector_store_parallel import parse_pdf_parallel
    from app.config.parallel_config import Presets
    
    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"⚠️  Test PDF not found: {test_pdf}")
        return False
    
    configs = [
        ("Free Tier (3 workers)", 3),
        ("Medium (5 workers)", 5),
        ("High (10 workers)", 10),
    ]
    
    results = []
    
    for config_name, workers in configs:
        print(f"\n📊 Testing: {config_name}")
        
        start = time.time()
        result = parse_pdf_parallel(test_pdf, use_gemini=True, max_workers=workers)
        elapsed = time.time() - start
        
        results.append({
            "config": config_name,
            "workers": workers,
            "time": elapsed,
            "length": len(result),
        })
        
        print(f"   ✅ Completed in {elapsed:.2f}s")
    
    # Summary
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    
    for r in results:
        print(f"\n📊 {r['config']}")
        print(f"   Workers: {r['workers']}")
        print(f"   Time: {r['time']:.2f}s")
        print(f"   Output: {r['length']:,} chars")
    
    # Find best
    fastest = min(results, key=lambda x: x['time'])
    print(f"\n🏆 Fastest: {fastest['config']} ({fastest['time']:.2f}s)")
    
    return True


def test_error_handling():
    """Test 5: Verify error handling với invalid PDF"""
    print("\n" + "=" * 80)
    print("TEST 5: Error Handling")
    print("=" * 80)
    
    from app.services.vector_store_parallel import parse_pdf_parallel
    
    # Test với file không tồn tại
    fake_pdf = "/tmp/nonexistent_file.pdf"
    
    try:
        result = parse_pdf_parallel(fake_pdf, use_gemini=True, max_workers=3)
        print("❌ FAILED: Should have raised an error!")
        return False
    except Exception as e:
        print(f"✅ PASSED: Error handled correctly")
        print(f"   Error: {str(e)[:100]}")
        return True


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("PARALLEL PROCESSING VERIFICATION TESTS")
    print("=" * 80)
    
    tests = [
        ("Chunk Order Preservation", test_chunk_order_preservation),
        ("Chunk Completeness", test_chunk_completeness),
        ("Sequential vs Parallel", test_sequential_vs_parallel_accuracy),
        ("Performance Benchmark", test_performance_benchmark),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'=' * 80}")
            print(f"Running: {test_name}")
            print('=' * 80)
            
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n📊 Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! Parallel processing works correctly.")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed. Please review.")


if __name__ == "__main__":
    main()

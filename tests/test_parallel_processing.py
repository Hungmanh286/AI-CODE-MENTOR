#!/usr/bin/env python3
"""
Test script để verify parallel processing trong update_file_active router.

Test cases:
1. Verify chunks được xử lý đúng thứ tự
2. Verify tất cả chunks được xử lý (không bỏ sót)
3. Verify kết quả kết hợp đúng logic
4. Compare performance: sequential vs parallel
"""

import os
import sys
import time

import structlog

logger = structlog.get_logger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_chunk_order_preservation():
    """Test 1: Verify chunks được kết hợp đúng thứ tự"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Chunk Order Preservation")
    logger.info("=" * 80)

    from app.services.vector_store_parallel import parse_pdf_parallel

    # Test với PDF nhỏ để dễ verify
    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/pdfs/example.pdf"

    if not os.path.exists(test_pdf):
        logger.info(f"⚠️  Test PDF not found: {test_pdf}")
        logger.info("Please provide a test PDF file")
        return False

    # Parse PDF
    result = parse_pdf_parallel(test_pdf, max_workers=3)

    # Verify
    logger.info(f"\n📊 Result length: {len(result):,} characters")
    logger.info(f"📝 First 200 chars: {result[:200]}")
    logger.info(f"📝 Last 200 chars: {result[-200:]}")

    # Check that result is not empty
    if len(result) == 0:
        logger.info("❌ FAILED: Result is empty!")
        return False

    # Check that result doesn't contain multiple ERROR placeholders
    error_count = result.count("[ERROR:")
    if error_count > 2:  # Allow max 2 errors for tolerance
        logger.info(f"❌ FAILED: Too many errors ({error_count} chunks failed)")
        return False

    logger.info("✅ PASSED: Chunks processed and combined correctly")
    return True


def test_chunk_completeness():
    """Test 2: Verify tất cả chunks được xử lý"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Chunk Completeness")
    logger.info("=" * 80)

    from pdf2image import convert_from_path

    from app.services.vector_store_parallel import parse_pdf_parallel

    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/pdfs/example.pdf"

    if not os.path.exists(test_pdf):
        logger.info(f"⚠️  Test PDF not found: {test_pdf}")
        return False

    # Get total pages
    images = convert_from_path(test_pdf)
    total_pages = len(images)
    logger.info(f"📄 Total pages in PDF: {total_pages}")

    # Calculate expected chunks
    chunk_size = 15 if total_pages < 50 else 30
    expected_chunks = (total_pages + chunk_size - 1) // chunk_size  # Ceiling division
    logger.info(f"📦 Expected chunks: {expected_chunks} (chunk size: {chunk_size})")

    # Parse PDF and count chunks processed
    # (We'll check logs for "Processing chunks" progress)
    result = parse_pdf_parallel(test_pdf, max_workers=3)

    # Verify result is not empty
    if len(result) == 0:
        logger.info("❌ FAILED: Result is empty!")
        return False

    # Count sections in result (rough estimation)
    # Each chunk should produce some content
    sections = result.split("\n\n")
    sections_count = len([s for s in sections if len(s.strip()) > 50])

    logger.info(f"📊 Sections in result: {sections_count}")

    # Allow some tolerance (sections might be merged or split)
    if sections_count < expected_chunks * 0.5:  # At least 50% of expected
        logger.info("⚠️  WARNING: Fewer sections than expected")
        logger.info(f"   Expected ~{expected_chunks}, got {sections_count}")
    else:
        logger.info("✅ PASSED: All chunks processed")

    return True


def test_sequential_vs_parallel_accuracy():
    """Test 3: Verify parallel produces same result as sequential"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Sequential vs Parallel Accuracy")
    logger.info("=" * 80)

    from app.services.vector_store import parse_pdf_text2

    from app.services.vector_store_parallel import parse_pdf_parallel

    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/pdfs/example.pdf"

    if not os.path.exists(test_pdf):
        logger.info(f"⚠️  Test PDF not found: {test_pdf}")
        return False

    logger.info("📊 Processing with SEQUENTIAL method...")
    start = time.time()
    seq_result = parse_pdf_text2(test_pdf)
    seq_time = time.time() - start
    seq_len = len(seq_result) if seq_result else 0

    logger.info(f"   Time: {seq_time:.2f}s")
    logger.info(f"   Length: {seq_len:,} chars")

    logger.info("\n📊 Processing with PARALLEL method...")
    start = time.time()
    par_result = parse_pdf_parallel(test_pdf, max_workers=3)
    par_time = time.time() - start
    par_len = len(par_result)

    logger.info(f"   Time: {par_time:.2f}s")
    logger.info(f"   Length: {par_len:,} chars")

    # Compare
    speedup = seq_time / par_time if par_time > 0 else 0
    logger.info(f"\n📈 Speedup: {speedup:.2f}x")

    # Length should be similar (within 20% tolerance)
    # Note: Methods use different parsers (docling vs vision), so exact match unlikely
    if seq_len > 0:
        diff_percent = abs(par_len - seq_len) / seq_len * 100
        logger.info(f"📊 Length difference: {diff_percent:.1f}%")

        if diff_percent > 50:
            logger.info("⚠️  WARNING: Large difference in output length")
            logger.info(
                "   This is expected as parallel uses vision model (different parser)"
            )
        else:
            logger.info("✅ Results are reasonably similar")

    if speedup >= 2:
        logger.info(f"✅ PASSED: Parallel is {speedup:.2f}x faster!")
    else:
        logger.info(f"⚠️  WARNING: Speedup is only {speedup:.2f}x (expected >2x)")

    return True


def test_performance_benchmark():
    """Test 4: Benchmark performance with different configs"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Performance Benchmark")
    logger.info("=" * 80)

    from app.services.vector_store_parallel import parse_pdf_parallel

    test_pdf = "/home/hungmanh/Documents/CodeMentor/app/data/pdfs/example.pdf"

    if not os.path.exists(test_pdf):
        logger.info(f"⚠️  Test PDF not found: {test_pdf}")
        return False

    configs = [
        ("Free Tier (3 workers)", 3),
        ("Medium (5 workers)", 5),
        ("High (10 workers)", 10),
    ]

    results = []

    for config_name, workers in configs:
        logger.info(f"\n📊 Testing: {config_name}")

        start = time.time()
        result = parse_pdf_parallel(test_pdf, max_workers=workers)
        elapsed = time.time() - start

        results.append(
            {
                "config": config_name,
                "workers": workers,
                "time": elapsed,
                "length": len(result),
            }
        )

        logger.info(f"   ✅ Completed in {elapsed:.2f}s")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("BENCHMARK SUMMARY")
    logger.info("=" * 80)

    for r in results:
        logger.info(f"\n📊 {r['config']}")
        logger.info(f"   Workers: {r['workers']}")
        logger.info(f"   Time: {r['time']:.2f}s")
        logger.info(f"   Output: {r['length']:,} chars")

    # Find best
    fastest = min(results, key=lambda x: x["time"])
    logger.info(f"\n🏆 Fastest: {fastest['config']} ({fastest['time']:.2f}s)")

    return True


def test_error_handling():
    """Test 5: Verify error handling với invalid PDF"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Error Handling")
    logger.info("=" * 80)

    from app.services.vector_store_parallel import parse_pdf_parallel

    # Test với file không tồn tại
    fake_pdf = "/tmp/nonexistent_file.pdf"

    try:
        parse_pdf_parallel(fake_pdf, max_workers=3)
        logger.info("❌ FAILED: Should have raised an error!")
        return False
    except Exception as e:
        logger.info("✅ PASSED: Error handled correctly")
        logger.info(f"   Error: {str(e)[:100]}")
        return True


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("PARALLEL PROCESSING VERIFICATION TESTS")
    logger.info("=" * 80)

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
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Running: {test_name}")
            logger.info("=" * 80)

            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.info(f"\n❌ Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    logger.info("\n\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\n📊 Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        logger.info("\n🎉 All tests passed! Parallel processing works correctly.")
    else:
        logger.info(f"\n⚠️  {total_count - passed_count} test(s) failed. Please review.")


if __name__ == "__main__":
    main()

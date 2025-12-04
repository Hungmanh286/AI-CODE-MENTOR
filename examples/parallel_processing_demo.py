#!/usr/bin/env python3
"""
Example script demonstrating parallel PDF processing.

This script shows various use cases:
1. Basic parallel processing
2. Using different presets
3. Comparing sequential vs parallel
4. Error handling
5. Integration with vector store
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.vector_store_parallel import parse_pdf_parallel
from app.services.vector_store import parse_pdf_text2, embedding_document
from app.config.parallel_config import ParallelProcessingConfig, Presets
import datetime


def example_1_basic_usage():
    """Example 1: Basic parallel processing"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Parallel Processing")
    print("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    result = parse_pdf_parallel(file_path=pdf_path, use_gemini=True, max_workers=50)

    print(f"\n✅ Parsed {len(result):,} characters")
    return result


def example_2_use_presets():
    """Example 2: Using configuration presets"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Using Configuration Presets")
    print("=" * 80)

    # Option 1: Free Tier
    print("\n🔹 Testing with Free Tier preset...")
    config = Presets.free_tier()
    print(f"Config: {config.MAX_WORKERS} workers, {config.RPM_LIMIT} RPM")

    # Option 2: High Performance (requires paid tier)
    # config = Presets.high_performance()

    # Apply config (in production, do this at startup)
    # from app.services import vector_store_parallel
    # vector_store_parallel.ParallelConfig = config


def example_3_compare_sequential_vs_parallel():
    """Example 3: Compare sequential vs parallel performance"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Sequential vs Parallel Comparison")
    print("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    # Sequential
    print("\n📊 Sequential Processing...")
    start = datetime.datetime.now()
    seq_result = parse_pdf_text2(pdf_path)
    seq_duration = (datetime.datetime.now() - start).total_seconds()
    print(f"✅ Sequential: {seq_duration:.2f}s")

    # Parallel
    print("\n📊 Parallel Processing...")
    start = datetime.datetime.now()
    par_result = parse_pdf_parallel(pdf_path, max_workers=10)
    par_duration = (datetime.datetime.now() - start).total_seconds()
    print(f"✅ Parallel: {par_duration:.2f}s")

    # Comparison
    speedup = seq_duration / par_duration
    print(f"\n🚀 Speedup: {speedup:.2f}x faster!")


def example_4_error_handling():
    """Example 4: Graceful error handling"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Error Handling")
    print("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    try:
        result = parse_pdf_parallel(pdf_path)
        print(f"✅ Success: {len(result):,} characters")
    except Exception as e:
        print(f"❌ Parallel processing failed: {e}")
        print("🔄 Falling back to sequential processing...")

        try:
            result = parse_pdf_text2(pdf_path)
            print(f"✅ Fallback success: {len(result):,} characters")
        except Exception as e2:
            print(f"❌ Both methods failed: {e2}")
            raise


def example_5_integration_with_vector_store():
    """Example 5: Full pipeline integration"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Integration with Vector Store")
    print("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    session_id = f"test_session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Step 1: Parse PDF (parallel)
    print("\n📄 Step 1: Parsing PDF...")
    document_text = parse_pdf_parallel(pdf_path, max_workers=10)
    print(f"✅ Parsed {len(document_text):,} characters")

    # Step 2: Embed into vector store
    print(f"\n🔍 Step 2: Embedding into vector store (session: {session_id})...")
    embedding_document([document_text], session_id)
    print("✅ Embedded successfully")

    return session_id


def example_6_batch_processing():
    """Example 6: Process multiple PDFs"""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Batch Processing Multiple PDFs")
    print("=" * 80)

    import glob

    # Find all PDFs in data directory
    pdf_files = glob.glob("/home/hungmanh/Documents/CodeMentor/app/data/*.pdf")

    if not pdf_files:
        print("⚠️  No PDF files found in data directory")
        return

    print(f"📚 Found {len(pdf_files)} PDF files")

    results = {}
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing {os.path.basename(pdf_file)}...")

        try:
            result = parse_pdf_parallel(pdf_file, max_workers=5)
            results[pdf_file] = {
                "status": "success",
                "length": len(result),
            }
            print(f"✅ Success: {len(result):,} characters")
        except Exception as e:
            results[pdf_file] = {
                "status": "failed",
                "error": str(e),
            }
            print(f"❌ Failed: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 80)

    success = sum(1 for r in results.values() if r["status"] == "success")
    failed = len(results) - success

    print(f"✅ Success: {success}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")


def example_7_custom_config():
    """Example 7: Custom configuration"""
    print("\n" + "=" * 80)
    print("EXAMPLE 7: Custom Configuration")
    print("=" * 80)

    # Create custom config
    config = ParallelProcessingConfig(
        MAX_WORKERS=15,
        RPM_LIMIT=100,
        CHUNK_SIZE_LARGE=25,
        RETRY_ATTEMPTS=3,
        ENABLE_CACHING=True,
        DEFAULT_API="gemini",
        ENABLE_VERBOSE_LOGGING=True,
    )

    print("📝 Custom Configuration:")
    print(f"   Max Workers: {config.MAX_WORKERS}")
    print(f"   RPM Limit: {config.RPM_LIMIT}")
    print(f"   Chunk Size: {config.CHUNK_SIZE_LARGE}")
    print(f"   Retry Attempts: {config.RETRY_ATTEMPTS}")
    print(f"   Caching: {config.ENABLE_CACHING}")
    print(f"   API: {config.DEFAULT_API}")

    # Use this config in your application
    # from app.services import vector_store_parallel
    # vector_store_parallel.ParallelConfig = config


def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("PARALLEL PDF PROCESSING EXAMPLES")
    print("=" * 80)

    examples = {
        "1": ("Basic Usage", example_1_basic_usage),
        "2": ("Use Presets", example_2_use_presets),
        "3": ("Sequential vs Parallel", example_3_compare_sequential_vs_parallel),
        "4": ("Error Handling", example_4_error_handling),
        "5": ("Vector Store Integration", example_5_integration_with_vector_store),
        "6": ("Batch Processing", example_6_batch_processing),
        "7": ("Custom Configuration", example_7_custom_config),
    }

    print("\nAvailable Examples:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("  all. Run all examples")
    print("  q. Quit")

    choice = input("\nSelect example (1-7, all, or q): ").strip().lower()

    if choice == "q":
        print("👋 Goodbye!")
        return

    if choice == "all":
        for name, func in examples.values():
            try:
                func()
            except Exception as e:
                print(f"❌ Error in {name}: {e}")
                import traceback

                traceback.print_exc()
    elif choice in examples:
        name, func = examples[choice]
        try:
            func()
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"❌ Invalid choice: {choice}")


if __name__ == "__main__":
    main()

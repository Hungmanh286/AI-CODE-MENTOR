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

import datetime
import os
import sys

import structlog

logger = structlog.get_logger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.vector_store import embedding_document, parse_pdf_text2  # noqa: E402

from app.config.parallel_config import ParallelProcessingConfig, Presets  # noqa: E402
from app.services.vector_store_parallel import parse_pdf_parallel  # noqa: E402


def example_1_basic_usage():
    """Example 1: Basic parallel processing"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 1: Basic Parallel Processing")
    logger.info("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    result = parse_pdf_parallel(file_path=pdf_path, use_gemini=True, max_workers=50)

    logger.info(f"\n✅ Parsed {len(result):,} characters")
    return result


def example_2_use_presets():
    """Example 2: Using configuration presets"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 2: Using Configuration Presets")
    logger.info("=" * 80)

    # Option 1: Free Tier
    logger.info("\n🔹 Testing with Free Tier preset...")
    config = Presets.free_tier()
    logger.info(f"Config: {config.MAX_WORKERS} workers, {config.RPM_LIMIT} RPM")

    # Option 2: High Performance (requires paid tier)
    # config = Presets.high_performance()

    # Apply config (in production, do this at startup)
    # from app.services import vector_store_parallel
    # vector_store_parallel.ParallelConfig = config


def example_3_compare_sequential_vs_parallel():
    """Example 3: Compare sequential vs parallel performance"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 3: Sequential vs Parallel Comparison")
    logger.info("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    # Sequential
    logger.info("\n📊 Sequential Processing...")
    start = datetime.datetime.now()
    parse_pdf_text2(pdf_path)
    seq_duration = (datetime.datetime.now() - start).total_seconds()
    logger.info(f"✅ Sequential: {seq_duration:.2f}s")

    # Parallel
    logger.info("\n📊 Parallel Processing...")
    start = datetime.datetime.now()
    parse_pdf_parallel(pdf_path, max_workers=10)
    par_duration = (datetime.datetime.now() - start).total_seconds()
    logger.info(f"✅ Parallel: {par_duration:.2f}s")

    # Comparison
    speedup = seq_duration / par_duration
    logger.info(f"\n🚀 Speedup: {speedup:.2f}x faster!")


def example_4_error_handling():
    """Example 4: Graceful error handling"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 4: Error Handling")
    logger.info("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    try:
        result = parse_pdf_parallel(pdf_path)
        logger.info(f"✅ Success: {len(result):,} characters")
    except Exception as e:
        logger.info(f"❌ Parallel processing failed: {e}")
        logger.info("🔄 Falling back to sequential processing...")

        try:
            result = parse_pdf_text2(pdf_path)
            logger.info(f"✅ Fallback success: {len(result):,} characters")
        except Exception as e2:
            logger.info(f"❌ Both methods failed: {e2}")
            raise


def example_5_integration_with_vector_store():
    """Example 5: Full pipeline integration"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 5: Integration with Vector Store")
    logger.info("=" * 80)

    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    session_id = f"test_session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Step 1: Parse PDF (parallel)
    logger.info("\n📄 Step 1: Parsing PDF...")
    document_text = parse_pdf_parallel(pdf_path, max_workers=10)
    logger.info(f"✅ Parsed {len(document_text):,} characters")

    # Step 2: Embed into vector store
    logger.info(f"\n🔍 Step 2: Embedding into vector store (session: {session_id})...")
    embedding_document([document_text], session_id)
    logger.info("✅ Embedded successfully")

    return session_id


def example_6_batch_processing():
    """Example 6: Process multiple PDFs"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 6: Batch Processing Multiple PDFs")
    logger.info("=" * 80)

    import glob

    # Find all PDFs in data directory
    pdf_files = glob.glob("/home/hungmanh/Documents/CodeMentor/app/data/*.pdf")

    if not pdf_files:
        logger.info("⚠️  No PDF files found in data directory")
        return

    logger.info(f"📚 Found {len(pdf_files)} PDF files")

    results = {}
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(
            f"\n[{i}/{len(pdf_files)}] Processing {os.path.basename(pdf_file)}..."
        )

        try:
            result = parse_pdf_parallel(pdf_file, max_workers=5)
            results[pdf_file] = {
                "status": "success",
                "length": len(result),
            }
            logger.info(f"✅ Success: {len(result):,} characters")
        except Exception as e:
            results[pdf_file] = {
                "status": "failed",
                "error": str(e),
            }
            logger.info(f"❌ Failed: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("BATCH PROCESSING SUMMARY")
    logger.info("=" * 80)

    success = sum(1 for r in results.values() if r["status"] == "success")
    failed = len(results) - success

    logger.info(f"✅ Success: {success}/{len(results)}")
    logger.info(f"❌ Failed: {failed}/{len(results)}")


def example_7_custom_config():
    """Example 7: Custom configuration"""
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 7: Custom Configuration")
    logger.info("=" * 80)

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

    logger.info("📝 Custom Configuration:")
    logger.info(f"   Max Workers: {config.MAX_WORKERS}")
    logger.info(f"   RPM Limit: {config.RPM_LIMIT}")
    logger.info(f"   Chunk Size: {config.CHUNK_SIZE_LARGE}")
    logger.info(f"   Retry Attempts: {config.RETRY_ATTEMPTS}")
    logger.info(f"   Caching: {config.ENABLE_CACHING}")
    logger.info(f"   API: {config.DEFAULT_API}")

    # Use this config in your application
    # from app.services import vector_store_parallel
    # vector_store_parallel.ParallelConfig = config


def main():
    """Main entry point"""
    logger.info("\n" + "=" * 80)
    logger.info("PARALLEL PDF PROCESSING EXAMPLES")
    logger.info("=" * 80)

    examples = {
        "1": ("Basic Usage", example_1_basic_usage),
        "2": ("Use Presets", example_2_use_presets),
        "3": ("Sequential vs Parallel", example_3_compare_sequential_vs_parallel),
        "4": ("Error Handling", example_4_error_handling),
        "5": ("Vector Store Integration", example_5_integration_with_vector_store),
        "6": ("Batch Processing", example_6_batch_processing),
        "7": ("Custom Configuration", example_7_custom_config),
    }

    logger.info("\nAvailable Examples:")
    for key, (name, _) in examples.items():
        logger.info(f"  {key}. {name}")
    logger.info("  all. Run all examples")
    logger.info("  q. Quit")

    choice = input("\nSelect example (1-7, all, or q): ").strip().lower()

    if choice == "q":
        logger.info("👋 Goodbye!")
        return

    if choice == "all":
        for name, func in examples.values():
            try:
                func()
            except Exception as e:
                logger.info(f"❌ Error in {name}: {e}")
                import traceback

                traceback.print_exc()
    elif choice in examples:
        name, func = examples[choice]
        try:
            func()
        except Exception as e:
            logger.info(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
    else:
        logger.info(f"❌ Invalid choice: {choice}")


if __name__ == "__main__":
    main()

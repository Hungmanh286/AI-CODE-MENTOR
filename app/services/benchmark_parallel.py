"""
Script benchmark để so sánh hiệu suất giữa sequential và parallel processing.

Usage:
    python benchmark_parallel.py --pdf <path_to_pdf> --workers <num_workers>
"""

import argparse
import datetime
import json
from vector_store import parse_pdf_text2 as parse_sequential
from vector_store_parallel import parse_pdf_parallel


def benchmark_sequential(pdf_path: str):
    """Benchmark sequential processing"""
    print("\n" + "=" * 80)
    print("📊 SEQUENTIAL PROCESSING")
    print("=" * 80)
    
    start = datetime.datetime.now()
    result = parse_sequential(pdf_path)
    end = datetime.datetime.now()
    
    duration = (end - start).total_seconds()
    
    return {
        "method": "sequential",
        "duration_seconds": duration,
        "result_length": len(result) if result else 0,
        "timestamp": start.isoformat(),
    }


def benchmark_parallel(pdf_path: str, max_workers: int = 10, use_gemini: bool = True):
    """Benchmark parallel processing"""
    print("\n" + "=" * 80)
    print("📊 PARALLEL PROCESSING")
    print("=" * 80)
    
    start = datetime.datetime.now()
    result = parse_pdf_parallel(
        pdf_path,
        use_gemini=use_gemini,
        max_workers=max_workers
    )
    end = datetime.datetime.now()
    
    duration = (end - start).total_seconds()
    
    return {
        "method": "parallel",
        "max_workers": max_workers,
        "use_gemini": use_gemini,
        "duration_seconds": duration,
        "result_length": len(result) if result else 0,
        "timestamp": start.isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark PDF parsing performance")
    parser.add_argument("--pdf", type=str, required=True, help="Path to PDF file")
    parser.add_argument("--workers", type=int, default=10, help="Number of worker threads")
    parser.add_argument("--skip-sequential", action="store_true", help="Skip sequential test")
    parser.add_argument("--use-openai", action="store_true", help="Use OpenAI instead of Gemini")
    
    args = parser.parse_args()
    
    results = []
    
    # Sequential benchmark
    if not args.skip_sequential:
        seq_result = benchmark_sequential(args.pdf)
        results.append(seq_result)
    
    # Parallel benchmark
    par_result = benchmark_parallel(
        args.pdf,
        max_workers=args.workers,
        use_gemini=not args.use_openai
    )
    results.append(par_result)
    
    # Summary
    print("\n" + "=" * 80)
    print("📈 BENCHMARK SUMMARY")
    print("=" * 80)
    
    for r in results:
        print(f"\n🔹 Method: {r['method'].upper()}")
        if "max_workers" in r:
            print(f"   Workers: {r['max_workers']}")
            print(f"   API: {'Gemini' if r['use_gemini'] else 'OpenAI'}")
        print(f"   Duration: {r['duration_seconds']:.2f} seconds")
        print(f"   Output length: {r['result_length']:,} characters")
    
    # Calculate speedup
    if len(results) == 2:
        speedup = results[0]['duration_seconds'] / results[1]['duration_seconds']
        print(f"\n🚀 Speedup: {speedup:.2f}x faster with parallel processing!")
    
    # Save results
    output_file = f"benchmark_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    main()

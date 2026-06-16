"""
Test script for MCQ Generation Server
Tests each atomic tool individually to verify functionality
"""
import structlog

logger = structlog.get_logger(__name__)


import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the implementation functions directly for testing
from tests.mcq_generation_server import (
    extract_key_concepts_impl,
    generate_question_stem_impl,
    generate_correct_answer_impl,
    generate_distractors_impl,
    validate_mcq_impl,
)

# Sample educational text for testing
SAMPLE_TEXT = """
Python là một ngôn ngữ lập trình bậc cao, thông dịch, hướng đối tượng với cú pháp đơn giản và dễ học.
Python được sử dụng rộng rãi trong nhiều lĩnh vực như phát triển web, khoa học dữ liệu, machine learning, 
và tự động hóa. Một trong những đặc điểm nổi bật của Python là có thư viện phong phú và cộng đồng người dùng lớn.
Python hỗ trợ nhiều paradigm lập trình bao gồm lập trình hướng đối tượng, lập trình hàm và lập trình thủ tục.
"""


def print_separator():
    logger.info("\n" + "=" * 80 + "\n")


def test_extract_key_concepts():
    logger.info("🧪 TEST 1: extract_key_concepts")
    print_separator()

    # Call the implementation function directly
    result = extract_key_concepts_impl(text=SAMPLE_TEXT, level="intermediate")

    logger.info("📊 Result:")
    logger.info(f"   Concepts extracted: {len(result.get('concepts', []))}")
    for i, concept in enumerate(result.get("concepts", []), 1):
        logger.info(f"   {i}. {concept}")

    print_separator()
    return result.get("concepts", [])


def test_generate_question_stem(concept):
    logger.info("🧪 TEST 2: generate_question_stem")
    print_separator()

    # Call the implementation function directly
    result = generate_question_stem_impl(
        concept=concept, context=SAMPLE_TEXT, question_type="definition"
    )

    logger.info("📊 Result:")
    logger.info(f"   Question: {result.get('question', 'N/A')}")

    print_separator()
    return result.get("question", "")


def test_generate_correct_answer(question):
    logger.info("🧪 TEST 3: generate_correct_answer")
    print_separator()

    # Call the implementation function directly
    result = generate_correct_answer_impl(question=question, context=SAMPLE_TEXT)

    logger.info("📊 Result:")
    logger.info(f"   Correct answer: {result.get('correct_answer', 'N/A')}")

    print_separator()
    return result.get("correct_answer", "")


def test_generate_distractors(correct_answer):
    logger.info("🧪 TEST 4: generate_distractors")
    print_separator()

    # Call the implementation function directly
    result = generate_distractors_impl(
        correct_answer=correct_answer, context=SAMPLE_TEXT, n=3
    )

    logger.info("📊 Result:")
    logger.info(f"   Number of distractors: {len(result.get('distractors', []))}")
    for i, distractor in enumerate(result.get("distractors", []), 1):
        logger.info(f"   {i}. {distractor}")

    print_separator()
    return result.get("distractors", [])


def test_validate_mcq(question, correct_answer, distractors):
    logger.info("🧪 TEST 5: validate_mcq")
    print_separator()

    # Call the implementation function directly
    result = validate_mcq_impl(
        question=question,
        correct_answer=correct_answer,
        distractors=distractors,
        context=SAMPLE_TEXT,
    )

    logger.info("📊 Result:")
    logger.info(f"   Is valid: {result.get('is_valid', False)}")
    logger.info(f"   Difficulty: {result.get('difficulty_estimate', 'N/A')}")

    issues = result.get("issues", [])
    if issues:
        logger.info(f"   Issues found ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            logger.info(f"      {i}. {issue}")
    else:
        logger.info("   No issues found ✅")

    print_separator()
    return result


def run_complete_workflow():
    logger.info("\n" + "🚀 " + "=" * 76)
    logger.info("   TESTING MCQ GENERATION SERVER - COMPLETE WORKFLOW")
    logger.info("=" * 80 + "\n")

    try:
        # Step 1: Extract concepts
        concepts = test_extract_key_concepts()
        if not concepts:
            logger.info("❌ No concepts extracted. Test failed.")
            return

        # Use first concept
        selected_concept = concepts[0]
        logger.info(f"✅ Selected concept for testing: '{selected_concept}'")
        print_separator()

        # Step 2: Generate question stem
        question = test_generate_question_stem(selected_concept)
        if not question:
            logger.info("❌ Question generation failed. Test failed.")
            return

        # Step 3: Generate correct answer
        correct_answer = test_generate_correct_answer(question)
        if not correct_answer:
            logger.info("❌ Correct answer generation failed. Test failed.")
            return

        # Step 4: Generate distractors
        distractors = test_generate_distractors(correct_answer)
        if not distractors:
            logger.info("❌ Distractor generation failed. Test failed.")
            return

        # Step 5: Validate MCQ
        validation_result = test_validate_mcq(question, correct_answer, distractors)

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("📝 FINAL MCQ GENERATED:")
        logger.info("=" * 80 + "\n")
        logger.info(f"Question: {question}\n")
        logger.info(f"A) {correct_answer}")
        for i, distractor in enumerate(distractors, 2):
            logger.info(f"{chr(64 + i)}) {distractor}")
        logger.info("\nCorrect Answer: A")
        logger.info(f"\nValidation: {'✅ VALID' if validation_result.get('is_valid') else '❌ INVALID'}")
        logger.info(f"Difficulty: {validation_result.get('difficulty_estimate', 'N/A').upper()}")
        logger.info("\n" + "=" * 80)

        logger.info("\n✅ ALL TESTS COMPLETED SUCCESSFULLY!\n")

    except Exception as e:
        logger.info(f"\n❌ ERROR during testing: {str(e)}\n")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    logger.info("\n🔧 Initializing MCQ Generation Server Test...\n")
    run_complete_workflow()

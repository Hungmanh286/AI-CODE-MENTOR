# module đánh giá câu hỏi
Understanding_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the understanding level of the question on a scale of
1 to 4 based on the following criteria:
- Score 4 if the question tests a deep understanding
of a concept, requiring integration and application
of ideas.
- Score 3 if the question tests understanding of a
concept but is more straightforward, requiring less
integration or application.
- Score 2 if the question largely depends on recall but
includes some context-specific details that require a
conceptual understanding.
- Score 1 if the question primarily tests memorization
of facts or details with minimal to no application of
concepts.
Please output only a score between 1 and 4.
"""

Clarity_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the clarity level of the question on a scale of 1 to 4
based on the following criteria:
- Score 4 if the question is completely clear and
unambiguous.
- Score 3 if the question is mostly clear, but may
have some ambiguity.
- Score 2 if the question has notable ambiguity that
could confuse the reader.
- Score 1 if the question is highly confusing or unclear.
Please output only a score between 1 and 4.
"""

Quality_of_Choices_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the quality of choices in the question on a scale of 1
to 4 based on the following criteria:
- Score 4 if it is challenging to eliminate any incorrect choice due to well-crafted distractors that are
plausible, unambiguous, and relevant to the question.
- Score 3 if incorrect choices can be somewhat challenging to eliminate, requiring a good understanding of the material, but they are less sophisticated.
- Score 2 if most incorrect choices are fairly easy to
eliminate, with perhaps one plausible distractor.
- Score 1 if incorrect choices are very easy to eliminate, often due to being obviously incorrect or
irrelevant.
Please output only a score between 1 and 4
"""

Difficulty_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the difficulty level of the question on a scale of 1 to
4 based on the following criteria:
- Score 4 if the question is very challenging, requiring deep understanding and advanced conceptual
application.
- Score 3 if the question is moderately difficult,
requiring understanding and some conceptual
application.
- Score 2 if the question is relatively easy and mainly
requires recall or basic understanding.
- Score 1 if the question is very easy and can be
answered without specific knowledge.
Please output only a score between 1 and 4.
"""

Cognitive_Level_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the cognitive level of the question based on Bloom’s
taxonomy on a scale of 1 to 4 based on the following
criteria:
- Score 4 if the question requires higher-level thinking (e.g., analysis, synthesis, or evaluation).
- Score 3 if the question requires application or
understanding of concepts.
- Score 2 if the question requires basic understanding
or recall.
- Score 1 if the question only tests rote memorization
with minimal understanding.
Please output only a score between 1 and 4.
"""
Engagement_Evaluation_Prompt = """
For the following multiple-choice question:
———–
Question: {question}
Options: {options}
Answer: {answer}
———–
Please answer the following:
Please carefully read the multiple-choice question, the
options, and the correct answer.
Rate the engagement level of the question on a scale from
1 to 4 based on the following criteria:
- Score 4 if the question is highly engaging and
thought-provoking.
- Score 3 if the question is engaging but not particularly unique or thought-provoking.
- Score 2 if the question is somewhat engaging but
fairly straightforward.
- Score 1 if the question is uninteresting or not engaging.
Please output only a score between 1 and 4.
"""

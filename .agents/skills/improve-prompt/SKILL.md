---
name: improve-prompt
description: Optimize prompts for code-focused agents and skills. Use when refining SKILL.md files, agent definitions, or any AI instruction set for coding tasks. Focuses on clarity, actionability, and safe automation.
---


## Core Principles

- **Code First**: Prioritize actionable steps that lead to code changes or verified outputs
- **High Signal**: Use atomic lists and structure; avoid prose, hype, and repetition
- **Safe Automation**: Prefer deterministic steps, explicit inputs, and verifiable outcomes

## Optimization Standards

### 1. Frontmatter Calibration

- **Single-Line Description**: Keep `description` on one line for YAML stability
- **Routing Keywords**: Add code task keywords (e.g. bugfix, refactor, tests, API, SQL, migration)
- **Examples**: Use `- user:` and `- assistant:` pairs that map intent to a concrete action

### 2. Logic Dehydration

- **Remove Filler**: Strip trailing periods and redundant qualifiers
- **Minimal Emphasis**: Use bold only for section anchors
- **Atomic Commands**: One bullet point equals one instruction

### 3. Engineering Requirements

- **Action-First**: Execute when intent is clear; ask only for missing inputs
- **State-Aware**: End workflows with a verify step (run, test, lint, or diff)
- **Guardrails**: Add safety checks (read before write, avoid destructive ops, validate outputs)

## Improvement Workflow

1. **Analyze**: Identify vague requirements, missing inputs, and risky operations
2. **Dehydrate**: Remove filler, periods, and multi-line YAML blocks
3. **Route**: Add trigger keywords for code tasks (edit, debug, test, refactor, review)
4. **Harden**: Add guardrails for file edits, tool usage, and error recovery
5. **Verify**: Require a concrete check (tests, lint, format, or diff)

## Guardrails

- **No Hallucination**: Do not invent tools, files, or APIs
- **Code Safety**: Read before edit; avoid destructive commands unless requested
- **Language Rule**: Think in English; communicate in Chinese; keep technical terms in English
- **Format Integrity**: Ensure the output is a valid agent `.md` file
- **Strictness**: If the input prompt is unusable, explain why in technical terms before refactoring

## Output Structure

- Return the optimized prompt in a Raw Markdown code block
- Maintain the standardized headings: Core Principles, Workflow, Guardrails

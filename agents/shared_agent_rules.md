# Shared Agent Rules

Use this file as the shared rule source for generated prompts. Embed the relevant bullets when the receiving agent cannot read project files; otherwise reference this file from the generated prompt.

## Grounding

- Inspect the listed files before planning or editing.
- Use code search to discover related files, symbols, commands, and tests.
- Do not invent file paths, APIs, dependencies, requirements, commands, or test results.
- If evidence is missing, say what is unknown and how you tried to verify it.

## Scope Control

- Change only what is required for the mission and acceptance criteria.
- Preserve existing behavior unless a change is explicitly requested.
- Do not refactor, rename, reformat, or reorganize unrelated code.
- Prefer small, reversible diffs over broad rewrites.
- Do not create files outside allowed paths.

## Validation

- Run the specified checks when possible.
- Add or update tests for changed behavior unless explicitly not applicable.
- Report every failed, skipped, or unavailable validation step.
- Do not claim tests pass unless they were run successfully.
- Include manual verification for behavior that automated tests do not cover.

## Assumptions And Questions

- Label assumptions explicitly.
- Ask questions only when ambiguity blocks correctness, security, data integrity, or user-facing behavior.
- For low-risk ambiguity, choose the smallest reasonable interpretation and state it.

## Two-Phase Response Format

Phase 1 must contain:
1. Files inspected and relevant evidence found
2. Proposed approach
3. File-by-file implementation plan
4. Validation plan
5. Risks, assumptions, and blocking questions

Phase 1 must not edit files.

Phase 2 may begin only after explicit approval. Phase 2 must contain:
1. Summary of changes
2. Files changed
3. Validation performed with results
4. Failed or skipped validation, if any
5. Remaining risks or follow-up

## Single-Phase Response Format

Use only when the prompt allows `single_phase`.

The response must contain:
1. Brief approach
2. Changes made
3. Validation performed with results
4. Assumptions, skipped checks, and remaining risks

"""Commit Writer prompt construction and message cleanup (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass

from toolsmith.errors import EmptyCommitMessageError
from toolsmith.git.diff import PreparedDiff


@dataclass(frozen=True)
class CommitMessage:
    """A cleaned, validated commit message ready for user review."""

    subject: str
    body: str
    warnings: tuple[str, ...]


_SUBJECT_LENGTH_LIMIT = 72


_COMMON_PREFIXES = (
    "commit message:",
    "suggested commit message:",
    "message:",
    "git commit -m",
)


def _format_summary(prepared: PreparedDiff) -> str:
    """Render the staged name-status summary in plain text."""
    lines: list[str] = []
    for entry in prepared.summary:
        if entry.status in {"R", "C"} and entry.old_path:
            line = f"{entry.status} {entry.old_path} -> {entry.path}"
        else:
            line = f"{entry.status} {entry.path}"
        if entry.is_binary:
            line += " (binary)"
        lines.append(line)
    return "\n".join(lines)


def build_commit_prompt(prepared: PreparedDiff) -> str:
    """Build a compact, deterministic Commit Writer prompt from staged data.

    The prompt uses only the staged file summary and bounded staged diff. It
    tells the model to produce a plain git commit message without invented
    metadata and without overemphasizing formatting noise, lockfiles,
    generated files, or minified output.
    """
    parts = [
        "Write a plain git commit message for the staged changes below.",
        "Describe the practical intent using only visible evidence.",
        "Use a concise imperative subject line.",
        "Include a body only when it adds useful explanation.",
        "",
        "Do not invent ticket numbers, authors, reviewers, deployment notes, "
        "breaking-change notices, security claims, or test claims.",
        "Do not use markdown, quotes, code fences, or preamble.",
        "Do not wrap the response in 'Commit message:'.",
        "",
        "Avoid overemphasizing formatting noise, lockfiles, generated files, "
        "or minified output.",
        "",
        "Output shape:",
        "<subject>",
        "[blank line]",
        "<optional body>",
        "",
        "Staged file summary:",
        _format_summary(prepared),
        "",
        "Staged diff:",
        prepared.diff,
    ]

    if prepared.truncated:
        parts.append("")
        parts.append(
            "Note: the staged diff is truncated; focus on the file summary "
            "and visible context."
        )

    return "\n".join(parts)


def clean_commit_message(raw: str) -> str:
    """Remove common model wrappers and normalize whitespace.

    This is intentionally conservative: only known boundary wrappers are
    removed, and substantive content is preserved.
    """
    text = raw.strip()

    # Remove matching wrapping quotes around the whole message.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1].strip()

    lines = text.splitlines()

    # Remove leading/trailing code fences.
    while lines and lines[0].lstrip().startswith("```"):
        lines.pop(0)
    while lines and lines[-1].lstrip().startswith("```"):
        lines.pop()

    # Remove common prefixes from the first non-empty line.
    cleaned_lines: list[str] = []
    prefix_removed = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if not prefix_removed:
            lowered = stripped.lower()
            for prefix in _COMMON_PREFIXES:
                if lowered.startswith(prefix):
                    stripped = stripped[len(prefix):].strip()
                    lowered = stripped.lower()
                    if stripped.startswith('"') and stripped.endswith('"'):
                        stripped = stripped[1:-1].strip()
                    elif stripped.startswith("'") and stripped.endswith("'"):
                        stripped = stripped[1:-1].strip()
            cleaned_lines.append(stripped)
            prefix_removed = True
        else:
            cleaned_lines.append(stripped)

    # Trim leading/trailing blank lines and collapse excess blank lines.
    result: list[str] = []
    in_leading = True
    last_was_blank = False
    for line in cleaned_lines:
        is_blank = line == ""
        if in_leading and is_blank:
            continue
        in_leading = False
        if is_blank:
            if not last_was_blank:
                result.append(line)
                last_was_blank = True
            continue
        result.append(line)
        last_was_blank = False

    while result and result[-1] == "":
        result.pop()

    return "\n".join(result)


def validate_commit_message(cleaned: str) -> CommitMessage:
    """Extract the subject and body, rejecting empty output and surfacing warnings.

    A subject longer than 72 characters produces a non-blocking warning; it
    does not reject the message.
    """
    if not cleaned or cleaned.strip() == "":
        raise EmptyCommitMessageError("LLM returned an empty commit message.")

    lines = cleaned.splitlines()
    subject = lines[0].strip()

    body_lines = lines[1:]
    # Trim leading blank lines from the body.
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()
    body = "\n".join(body_lines)

    warnings: list[str] = []
    if len(subject) > _SUBJECT_LENGTH_LIMIT:
        warnings.append(
            f"Warning: subject line is longer than {_SUBJECT_LENGTH_LIMIT} characters."
        )

    return CommitMessage(
        subject=subject,
        body=body,
        warnings=tuple(warnings),
    )

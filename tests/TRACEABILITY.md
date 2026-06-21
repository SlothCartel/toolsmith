# Phase 8 Test Traceability

This document maps Phase 8 reliability/validation requirements and required error
paths to the concrete automated tests that exercise them. It is intended as a
maintenance aid and as evidence for the requirement coverage matrix in
`planning/project_implementation_plan.md`.

## How to read this document

- Requirement coverage is grouped by the matrix in Section 8 of the implementation plan.
- Each entry lists the required behavior, the test file, and the specific test name(s).
- Tests marked `manual` require a running local Ollama-compatible runtime and are excluded
  from the default `pytest` run by `pyproject.toml` (`addopts = "-q -m 'not manual'"`).
- All non-manual tests run without a live provider, without internet access, and without
  mutating the toolsmith worktree.

## Safety invariants (no hidden mutation, no LLM call before gates)

| Requirement | Test file | Test name |
|-------------|-----------|-----------|
| No LLM call for invalid repository | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_outside_repository_raises_before_llm_and_services` |
| No LLM call for no staged changes | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_no_staged_changes_raises_before_llm_and_services` |
| No LLM call for diff failure | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_diff_failure_raises_before_llm_and_services` |
| No LLM call for invalid config | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_invalid_config_raises_before_git_and_llm` |
| No commit or push before acceptance | `tests/unit/test_commit_writer.py` | `TestInteractiveReview::test_reject_raises_cancel_and_makes_no_calls`, `TestInteractiveReview::test_keyboard_interrupt_at_review_makes_no_calls`, `TestDryRun::*`, `TestEditFlow::test_editor_failure_cannot_call_commit` |
| No staged diff in durable logs / telemetry | `tests/unit/test_git_commit.py` | `test_temporary_message_file_contains_only_message` |
| No staged diff persisted in repo during read-only phase | `tests/integration/test_git_repository.py` | `test_prepared_diff_never_persists_to_files` |
| Temp commit-message file cleanup | `tests/unit/test_git_commit.py` | `test_temporary_message_file_is_cleaned_up_on_success`, `test_temporary_message_file_is_cleaned_up_on_failure` |
| No force-push / hook-bypass flags | `tests/unit/test_git_commit.py` | `test_no_hook_bypass_or_signing_flags`, `test_ordinary_push_has_no_force_flags` |
| Push failure does not roll back commit | `tests/integration/test_commit_writer_git.py` | `TestPushPromptFlow::test_push_failure_does_not_roll_back_commit`, `tests/unit/test_cli.py::test_main_cw_push_failure_exits_dependency_error_and_keeps_commit` |
| Ctrl+C at push prompt leaves commit | `tests/integration/test_commit_writer_git.py` | `TestPushPromptFlow::test_keyboard_interrupt_at_push_prompt_leaves_commit_intact` |

## Required error paths (Phase 8 orchestration coverage)

| Required error | Test file | Test name |
|----------------|-----------|-----------|
| git unavailable | `tests/unit/test_cli.py` | `test_main_cw_git_unavailable_exits_dependency_error` |
| outside repository | `tests/unit/test_cli.py` | `test_main_cw_outside_repository_exits_usage_error`, `tests/unit/test_commit_writer.py::TestErrorPaths::test_outside_repository_raises_before_llm_and_services` |
| no staged changes | `tests/unit/test_cli.py` | `test_main_cw_no_staged_changes_exits_usage_error`, `tests/unit/test_commit_writer.py::TestErrorPaths::test_no_staged_changes_raises_before_llm_and_services` |
| diff failure | `tests/unit/test_cli.py` | `test_main_cw_diff_failure_exits_dependency_error`, `tests/unit/test_commit_writer.py::TestErrorPaths::test_diff_failure_raises_before_llm_and_services` |
| invalid config | `tests/unit/test_cli.py` | `test_main_cw_invalid_toml_exit_code`, `test_main_cw_invalid_config_raises_before_llm`, `tests/unit/test_config.py` (multiple) |
| unsupported provider | `tests/unit/test_cli.py` | `test_main_cw_unsupported_provider_exit_code`, `tests/unit/test_llm_contract.py::test_create_client_rejects_unsupported_provider`, `tests/unit/test_config.py::test_unsupported_provider_raises_usage_error` |
| local runtime unavailable / timeout / malformed / empty response | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_llm_failure_variants_block_commit_and_push` (parametrized), `tests/unit/test_ollama_adapter.py::test_connection_refused_maps_to_runtime_unavailable`, `test_timeout_error_maps_to_actionable_timeout`, `test_malformed_json_maps_to_malformed_response`, `test_empty_response_text_maps_to_empty_output` |
| editor unavailable / cancelled | `tests/unit/test_commit_writer.py` | `TestEditFlow::test_editor_failure_cannot_call_commit`, `tests/unit/test_editor.py::test_missing_editor_raises_dependency_error`, `test_signal_termination_raises_cancel`, `test_nonzero_editor_exit_raises_dependency_error` |
| commit failure | `tests/unit/test_commit_writer.py` | `TestErrorPaths::test_commit_service_failure_raises_git_error_and_skips_push`, `tests/unit/test_git_commit.py::test_commit_failure_returns_useful_stderr`, `test_failing_commit_hook_blocks_commit` |
| push failure | `tests/unit/test_cli.py` | `test_main_cw_push_failure_exits_dependency_error_and_keeps_commit`, `tests/unit/test_git_commit.py::test_push_failure_returns_useful_stderr`, `tests/integration/test_commit_writer_git.py::TestPushPromptFlow::test_push_failure_does_not_roll_back_commit` |
| keyboard interrupt | `tests/unit/test_cli.py` | `test_main_cw_keyboard_interrupt_returns_cancel_exit_code`, `tests/unit/test_commit_writer.py::TestInteractiveReview::test_keyboard_interrupt_at_review_makes_no_calls`, `tests/unit/test_ui_prompts.py::test_keyboard_interrupt_propagates` |

## Performance / prompt-efficiency checks

| Check | Test file | Test name | Notes |
|-------|-----------|-----------|-------|
| Prompt size is bounded by configured diff limit | `tests/unit/test_commit_writer_prompt.py` | `test_prompt_size_respects_configured_diff_limit` | Non-flaky structural bound; does not assert provider timing. |
| CLI help starts quickly | `tests/integration/test_package_smoke.py` | `test_installed_entry_point_help_is_fast` | Non-flaky 2-second upper bound on warm hardware. |
| Warm-provider generation time | `tests/integration/test_package_smoke.py` | `test_installed_entry_point_cw_dry_run` | `manual` marker; run only when Ollama is available. Result must be recorded, not claimed without evidence. |

## Optional / manual local-provider smoke tests

The only default-excluded test is:

- `tests/integration/test_package_smoke.py::test_installed_entry_point_cw_dry_run` (`@pytest.mark.manual`)

Run it explicitly with:

```bash
pytest -m manual
```

It requires a running Ollama-compatible runtime and the configured model. Do not
run it in CI without a runtime, and do not download or install a model as part
of the test.

## Requirement coverage matrix linkage

| Requirement group | Primary validation |
|-------------------|-------------------|
| Repository validation/root (FR-004–FR-006; AC-002) | `tests/integration/test_git_repository.py`, `tests/unit/test_commit_writer.py::TestErrorPaths` |
| Staged changes and file summary (FR-007–FR-010; AC-003–AC-004) | `tests/integration/test_git_repository.py::test_staged_text_change_summary_and_diff`, `test_staged_and_unstaged_same_file_isolated`, `tests/unit/test_commit_writer.py::TestErrorPaths` |
| Diff size, binary, rename/delete (FR-011–FR-015) | `tests/unit/test_git_diff.py`, `tests/integration/test_git_repository.py::test_staged_rename`, `test_staged_delete`, `test_staged_binary_is_marked_and_not_opened`, `test_oversized_diff_truncated`, `tests/unit/test_commit_writer_prompt.py::test_prompt_size_respects_configured_diff_limit` |
| Shared LLM/local adapter/failures (FR-016–FR-021; AC-005–AC-006) | `tests/unit/test_llm_contract.py`, `tests/unit/test_ollama_adapter.py`, `tests/unit/test_commit_writer.py::TestErrorPaths::test_llm_failure_variants_block_commit_and_push` |
| Display and accept/edit/reject (FR-031–FR-037; AC-007–AC-010, AC-012) | `tests/unit/test_ui_prompts.py`, `tests/unit/test_commit_writer.py::TestInteractiveReview`, `TestEditFlow`, `TestDryRun` |
| Safe commit creation (FR-038–FR-041; AC-008–AC-009, AC-012) | `tests/unit/test_git_commit.py`, `tests/integration/test_commit_writer_git.py::TestCommitFlow` |
| Optional safe push (FR-042–FR-046; AC-011) | `tests/unit/test_git_commit.py::TestGitPushService`, `tests/integration/test_commit_writer_git.py::TestPushPromptFlow`, `tests/unit/test_cli.py::test_main_cw_push_failure_exits_dependency_error_and_keeps_commit` |
| Configuration and command options (FR-047–FR-055) | `tests/unit/test_config.py`, `tests/unit/test_cli.py` |
| Performance / prompt efficiency (NFR-001–NFR-005; AC-014) | `tests/unit/test_commit_writer_prompt.py::test_prompt_size_respects_configured_diff_limit`, `tests/integration/test_package_smoke.py::test_installed_entry_point_help_is_fast` |
| Reliability / no hidden mutation (NFR-006–NFR-009; AC-012) | All `TestErrorPaths`, temp-cleanup, and no-call-count safety assertions. |
| Privacy / no diff persistence (NFR-010–NFR-015) | `tests/unit/test_git_commit.py::test_temporary_message_file_contains_only_message`, `tests/integration/test_git_repository.py::test_prepared_diff_never_persists_to_files`, `tests/unit/test_editor.py::test_editor_receives_only_message_not_diff` |

## Maintenance note

When adding new error behavior or changing a guardrail, update this file and the
corresponding test name(s) so the traceability matrix stays honest. Additions
should follow the existing convention of naming tests after the observable
behavior, not the implementation detail.

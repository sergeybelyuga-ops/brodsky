# Test Suites Guide

This folder contains all automated tests for the bot.

## Test Files

- `test_bot_handlers.py`
  - Command handler behavior (`/start`, `/help`, `/top`, `/stat`, `/autostatus`) with mocked dependencies.
- `test_bot_utils.py`
  - Pure utility/business logic for intervals, schedule parsing, title extraction, and poll book selection.
- `test_poll_manager.py`
  - SQLite poll lifecycle tests (create/read polls, votes, schedule, final processing).
  - Some tests are marked `integration`.
- `test_sheets_and_ranking.py`
  - Sheets parsing/statistics and ranking logic with mocked worksheet data.
- `test_smoke_live.py`
  - Real external smoke test (Telegram + Sheets test resources).
  - Marked `smoke` and guarded with safety checks.

## Test-by-Test Business Scenarios

### test_bot_handlers.py

- `test_cmd_start_returns_helpful_intro`
  - Verifies that a new user receives a clear onboarding message with the key commands for running and managing club voting.
- `test_cmd_help_lists_supported_commands`
  - Verifies that help content exposes the operational command set members need for day-to-day usage.
- `test_cmd_top_returns_empty_message_when_no_books`
  - Ensures the bot communicates clearly when there is no voting history yet, instead of showing misleading rankings.
- `test_cmd_top_formats_top_list`
  - Ensures top books are presented in a ranked, readable format suitable for sharing club standings.
- `test_cmd_stat_success`
  - Ensures statistics command returns a complete club snapshot: totals, completed books, and current cycle progress.
- `test_cmd_stat_handles_sheet_error`
  - Ensures users receive a safe, friendly failure message when sheet statistics cannot be calculated.
- `test_cmd_autostatus_disabled`
  - Verifies members/admins can see that automatic poll scheduling is currently turned off.
- `test_cmd_autostatus_enabled`
  - Verifies members/admins can see scheduling is active, including next run time and recurrence interval.

### test_bot_utils.py

- `test_get_active_poll_titles_collects_titles_from_rows`
  - Ensures the system correctly extracts all books currently present in active polls to avoid duplicate nominations.
- `test_parse_interval_to_seconds_valid_units`
  - Verifies scheduler interval strings (seconds/minutes/hours/days) are converted into execution timing correctly.
- `test_parse_interval_to_seconds_invalid_values`
  - Verifies invalid interval input is rejected so broken schedules are not saved.
- `test_parse_autoschedule_args_valid`
  - Ensures autoschedule command arguments are parsed into a valid start datetime and repeat interval.
- `test_parse_autoschedule_args_invalid`
  - Ensures malformed autoschedule input is rejected instead of producing incorrect scheduling.
- `test_format_interval_prefers_larger_units`
  - Ensures interval values are displayed in human-friendly units for clearer admin communication.
- `test_get_schedule_interval_seconds_fallback_to_hours`
  - Ensures legacy schedule data using hours still works when seconds field is missing/zero.
- `test_select_books_for_poll_first_cycle_excludes_completed_and_active`
  - Ensures first-cycle poll candidates exclude completed books and books already present in active polls.
- `test_select_books_for_poll_later_cycle_prioritizes_votes`
  - Ensures later-cycle poll candidates are prioritized by community votes so the most requested books surface first.

### test_poll_manager.py

- `test_init_db_and_create_poll_and_get_active_polls`
  - Verifies a newly created poll is persisted and visible as an active poll with its selected books.
- `test_save_poll_vote_and_get_poll_votes`
  - Verifies option vote totals are saved and retrieved correctly for final tally processing.
- `test_process_final_poll_updates_votes_once_and_marks_processed`
  - Verifies finalization applies poll results exactly once and marks the poll as processed to prevent double counting.
- `test_parse_db_datetime_supported_formats`
  - Verifies datetime parsing supports common stored formats to keep schedule and poll records readable.
- `test_schedule_roundtrip`
  - Verifies automatic polling schedule settings can be saved and loaded without data loss.

### test_sheets_and_ranking.py

- `test_parse_cycle_value_handles_empty_and_int`
  - Verifies cycle values from sheets are normalized so blank values do not break cycle analytics.
- `test_parse_cycle_value_raises_on_invalid`
  - Verifies invalid cycle data is surfaced as an explicit domain error instead of silently corrupting stats.
- `test_is_completed_book_supports_completed_and_status`
  - Verifies completion detection works across both supported sheet conventions (`Completed` and `Status`).
- `test_build_cycle_stats_counts_books_above_cycle`
  - Verifies cycle progression stats correctly count books already voted past a given cycle.
- `test_get_book_club_stats_from_mocked_sheet`
  - Verifies full club statistics are computed correctly from sheet data used by the `/stat` command.
- `test_get_top_books_excludes_completed_and_sorts`
  - Verifies ranking excludes completed books and sorts candidates by votes for fair selection.
- `test_ranking_top5_uses_get_top_books`
  - Verifies top-5 ranking endpoint requests exactly five books from the ranking source.

### test_smoke_live.py

- `test_live_create_poll_flow`
  - Verifies a real smoke path can create a Telegram poll, persist it in the database, and confirm active status using test credentials and safety gates.

## Markers

Defined in `pytest.ini`:

- `integration`
  - Tests that validate integration-style behavior (primarily DB flow), but still safe for local runs.
- `smoke`
  - Minimal real external integration test.

## Suites

### Quick Testing

Purpose:

- Fast confidence check before commit.
- Runs all tests except live smoke.

Includes:

- `test_bot_handlers.py`
- `test_bot_utils.py`
- `test_sheets_and_ranking.py`
- `test_poll_manager.py` (including `integration`-marked tests)
- Excludes `test_smoke_live.py`

Direct command:

```bash
ENV_FILE=.env.test pytest tests --ignore tests/test_smoke_live.py -q
```

### Integration Testing

Purpose:

- Focus on integration-marked tests (mainly poll manager DB flow) without live smoke.

Includes:

- Tests marked `@pytest.mark.integration` (currently in `test_poll_manager.py`)
- Excludes smoke test file

Direct command:

```bash
ENV_FILE=.env.test pytest tests -m integration --ignore tests/test_smoke_live.py -q
```

### Smoke Testing

Purpose:

- Validate one real end-to-end external flow against test resources.

Includes:

- `test_smoke_live.py`

Direct command:

```bash
RUN_LIVE_SMOKE=1 ENV_FILE=.env.test pytest tests/test_smoke_live.py -s
```

## Script-based Commands

### Windows (host Python env)

- Quick:

```powershell
.\scripts\run-tests.ps1 -Suite fast -EnvFile .env.test
```

- Integration:

```powershell
.\scripts\run-tests.ps1 -Suite integration -EnvFile .env.test
```

- Smoke:

```powershell
.\scripts\run-tests.ps1 -Suite smoke -EnvFile .env.test
```

### Windows -> WSL Ubuntu 24.04

- Quick:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-tests-wsl.ps1 -Suite fast -Distro Ubuntu-24.04 -EnvFile .env.test
```

- Integration:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-tests-wsl.ps1 -Suite integration -Distro Ubuntu-24.04 -EnvFile .env.test
```

- Smoke:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-tests-wsl.ps1 -Suite smoke -Distro Ubuntu-24.04 -EnvFile .env.test
```

## Notes

- `deselected` in pytest output means tests were discovered but filtered out by marker or ignore rules.
- `skipped` means a selected test was intentionally not executed due to runtime conditions.
- Smoke test may be skipped by guard conditions in `test_smoke_live.py` if environment safety checks fail.

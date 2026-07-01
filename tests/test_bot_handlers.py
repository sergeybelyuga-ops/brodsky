from datetime import datetime
from types import SimpleNamespace

import pytest

import bot


class FakeMessage:
    def __init__(self, text="", chat_id=-1000):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)
        self.answers = []

    async def answer(self, text):
        self.answers.append(text)


@pytest.mark.asyncio
async def test_cmd_start_returns_helpful_intro():
    msg = FakeMessage()

    await bot.cmd_start(msg)

    assert len(msg.answers) == 1
    assert "/voting" in msg.answers[0]
    assert "/autoschedule" in msg.answers[0]
    assert "/help" in msg.answers[0]


@pytest.mark.asyncio
async def test_cmd_help_lists_supported_commands():
    msg = FakeMessage()

    await bot.cmd_help(msg)

    assert len(msg.answers) == 1
    assert "/voting" in msg.answers[0]
    assert "/stat" in msg.answers[0]
    assert "/autostatus" in msg.answers[0]


@pytest.mark.asyncio
async def test_cmd_top_returns_empty_message_when_no_books(monkeypatch):
    msg = FakeMessage()
    monkeypatch.setattr(bot, "top5", lambda: [])

    await bot.cmd_top(msg)

    assert msg.answers == ["No books have been voted yet"]


@pytest.mark.asyncio
async def test_cmd_top_formats_top_list(monkeypatch):
    msg = FakeMessage()
    monkeypatch.setattr(
        bot,
        "top5",
        lambda: [
            {"Title": "Book A", "Author": "Author A", "Votes": 7},
            {"Title": "Book B", "Author": "Author B", "Votes": 3},
        ],
    )

    await bot.cmd_top(msg)

    assert len(msg.answers) == 1
    assert "TOP 5 BOOKS" in msg.answers[0]
    assert "1. Book A" in msg.answers[0]
    assert "2. Book B" in msg.answers[0]


@pytest.mark.asyncio
async def test_cmd_stat_success(monkeypatch):
    msg = FakeMessage()
    monkeypatch.setattr(
        bot,
        "get_book_club_stats",
        lambda: {
            "total_books": 10,
            "completed_books": 2,
            "first_cycle_voted": 6,
            "first_cycle_waiting": 4,
            "current_cycle_number": 2,
            "current_cycle_voted": 3,
            "current_cycle_waiting": 7,
        },
    )

    await bot.cmd_stat(msg)

    assert len(msg.answers) == 1
    assert "Book Club Statistics" in msg.answers[0]
    assert "Total books: 10" in msg.answers[0]
    assert "Current voting cycle #2" in msg.answers[0]


@pytest.mark.asyncio
async def test_cmd_stat_handles_sheet_error(monkeypatch):
    msg = FakeMessage()

    def raise_sheet_error():
        raise bot.SheetStatsError("Missing required columns")

    monkeypatch.setattr(bot, "get_book_club_stats", raise_sheet_error)

    await bot.cmd_stat(msg)

    assert len(msg.answers) == 1
    assert "Unable to calculate statistics" in msg.answers[0]


@pytest.mark.asyncio
async def test_cmd_autostatus_disabled(monkeypatch):
    msg = FakeMessage()

    async def fake_get_poll_schedule():
        return None

    monkeypatch.setattr(bot, "get_poll_schedule", fake_get_poll_schedule)

    await bot.cmd_autostatus(msg)

    assert msg.answers == ["Automatic poll creation: Disabled"]


@pytest.mark.asyncio
async def test_cmd_autostatus_enabled(monkeypatch):
    msg = FakeMessage()

    async def fake_get_poll_schedule():
        return {
            "enabled": 1,
            "next_run": datetime(2026, 7, 5, 20, 0),
            "interval_seconds": 7200,
            "interval_hours": 0,
        }

    monkeypatch.setattr(bot, "get_poll_schedule", fake_get_poll_schedule)

    await bot.cmd_autostatus(msg)

    assert len(msg.answers) == 1
    assert "Automatic poll creation: Enabled" in msg.answers[0]
    assert "2026-07-05 20:00" in msg.answers[0]
    assert "2h" in msg.answers[0]


@pytest.mark.asyncio
async def test_execute_auto_schedule_disables_on_chat_not_found(monkeypatch):
    now = datetime.now()
    disable_calls = []

    class FakeTelegramBadRequest(Exception):
        pass

    async def fake_get_poll_schedule():
        return {
            "enabled": 1,
            "next_run": now,
            "interval_seconds": 7200,
            "interval_hours": 0,
            "chat_id": -123456,
        }

    async def fake_create_voting_poll(chat_id, duration_seconds):
        raise FakeTelegramBadRequest(
            "Telegram server says - Bad Request: chat not found"
        )

    async def fake_disable_poll_schedule():
        disable_calls.append(True)

    async def fake_set_poll_schedule_next_run(_):
        raise AssertionError("next_run must not be updated on chat-not-found")

    monkeypatch.setattr(bot, "TelegramBadRequest", FakeTelegramBadRequest)
    monkeypatch.setattr(bot, "get_poll_schedule", fake_get_poll_schedule)
    monkeypatch.setattr(bot, "create_voting_poll", fake_create_voting_poll)
    monkeypatch.setattr(bot, "disable_poll_schedule", fake_disable_poll_schedule)
    monkeypatch.setattr(
        bot,
        "set_poll_schedule_next_run",
        fake_set_poll_schedule_next_run,
    )

    await bot.execute_auto_schedule_if_due()

    assert disable_calls == [True]


@pytest.mark.asyncio
async def test_cmd_autoschedule_rejects_past_start(monkeypatch):
    msg = FakeMessage(text="/autoschedule 2026-07-01 10:00 5m", chat_id=-999)
    captured = {}

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 1, 10, 0, 30)

    async def fake_upsert_poll_schedule(enabled, next_run, interval_seconds, chat_id=None):
        captured["called"] = True

    monkeypatch.setattr(bot, "datetime", FakeDateTime)
    monkeypatch.setattr(
        bot,
        "parse_autoschedule_args",
        lambda _text: (datetime(2026, 7, 1, 10, 0, 0), 300),
    )
    monkeypatch.setattr(bot, "upsert_poll_schedule", fake_upsert_poll_schedule)

    await bot.cmd_autoschedule(msg)

    assert captured == {}
    assert len(msg.answers) == 1
    assert "Start date must be in the future" in msg.answers[0]

from datetime import datetime

import bot


def test_get_active_poll_titles_collects_titles_from_rows():
    rows = [
        {"books": "Book A|Book B|  Book C  "},
        {"books": "Book B|"},
        {"books": None},
    ]

    titles = bot.get_active_poll_titles(rows)

    assert titles == {"Book A", "Book B", "Book C"}


def test_parse_interval_to_seconds_valid_units():
    assert bot.parse_interval_to_seconds("30s") == 30
    assert bot.parse_interval_to_seconds("15m") == 900
    assert bot.parse_interval_to_seconds("2h") == 7200
    assert bot.parse_interval_to_seconds("1d") == 86400


def test_parse_interval_to_seconds_invalid_values():
    assert bot.parse_interval_to_seconds("0m") is None
    assert bot.parse_interval_to_seconds("10x") is None
    assert bot.parse_interval_to_seconds("abc") is None


def test_parse_autoschedule_args_valid():
    start_dt, interval = bot.parse_autoschedule_args(
        "/autoschedule 2026-07-01 20:00 72h"
    )

    assert start_dt == datetime(2026, 7, 1, 20, 0)
    assert interval == 72 * 3600


def test_parse_autoschedule_args_invalid():
    start_dt, interval = bot.parse_autoschedule_args("/autoschedule bad input")

    assert start_dt is None
    assert interval is None


def test_format_interval_prefers_larger_units():
    assert bot.format_interval(86400) == "1d"
    assert bot.format_interval(7200) == "2h"
    assert bot.format_interval(180) == "3m"
    assert bot.format_interval(59) == "59s"


def test_get_schedule_interval_seconds_fallback_to_hours():
    schedule = {"interval_seconds": 0, "interval_hours": 3}

    assert bot.get_schedule_interval_seconds(schedule) == 10800


def test_get_schedule_chat_id_prefers_schedule_value(monkeypatch):
    monkeypatch.setattr(bot, "CHAT_ID", -111)

    assert bot.get_schedule_chat_id({"chat_id": -222}) == -222


def test_get_schedule_chat_id_fallbacks_to_configured(monkeypatch):
    monkeypatch.setattr(bot, "CHAT_ID", -333)

    assert bot.get_schedule_chat_id({"chat_id": None}) == -333
    assert bot.get_schedule_chat_id({"chat_id": ""}) == -333
    assert bot.get_schedule_chat_id({"chat_id": "invalid"}) == -333


def test_select_books_for_poll_first_cycle_excludes_completed_and_active(monkeypatch):
    books = [
        {
            "Title": "Book A",
            "Author": "A",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 0,
            "Votes": 0,
            "Status": "",
        },
        {
            "Title": "Book B",
            "Author": "B",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 0,
            "Votes": 0,
            "Status": "Completed",
        },
        {
            "Title": "Book C",
            "Author": "C",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 0,
            "Votes": 0,
            "Status": "",
        },
    ]

    monkeypatch.setattr(bot, "BOOKS_PER_POLL", 5)
    monkeypatch.setattr(bot, "get_all_books", lambda: books)

    selected = bot.select_books_for_poll(excluded_titles={"Book C"})

    assert [b["Title"] for b in selected] == ["Book A"]


def test_select_books_for_poll_later_cycle_prioritizes_votes(monkeypatch):
    books = [
        {
            "Title": "Book A",
            "Author": "A",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 2,
            "Votes": 3,
            "Status": "",
        },
        {
            "Title": "Book B",
            "Author": "B",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 1,
            "Votes": 10,
            "Status": "",
        },
        {
            "Title": "Book C",
            "Author": "C",
            "Pages": 100,
            "Genre": "Drama",
            "Description": "desc",
            "Cycles": 1,
            "Votes": 7,
            "Status": "",
        },
    ]

    monkeypatch.setattr(bot, "BOOKS_PER_POLL", 2)
    monkeypatch.setattr(bot, "get_all_books", lambda: books)

    selected = bot.select_books_for_poll(excluded_titles=set())

    assert [b["Title"] for b in selected] == ["Book B", "Book C"]

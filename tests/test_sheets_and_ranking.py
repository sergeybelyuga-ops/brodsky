import pytest

import ranking
import sheets


def test_parse_cycle_value_handles_empty_and_int():
    assert sheets._parse_cycle_value(None) == 0
    assert sheets._parse_cycle_value("") == 0
    assert sheets._parse_cycle_value("3") == 3


def test_parse_cycle_value_raises_on_invalid():
    with pytest.raises(sheets.SheetStatsError):
        sheets._parse_cycle_value("bad")


def test_is_completed_book_supports_completed_and_status():
    assert sheets._is_completed_book({"Completed": "true"}) is True
    assert sheets._is_completed_book({"Completed": "1"}) is True
    assert sheets._is_completed_book({"Status": "Completed"}) is True
    assert sheets._is_completed_book({"Status": "In progress"}) is False


def test_build_cycle_stats_counts_books_above_cycle():
    books = [
        {"Cycles": "0"},
        {"Cycles": "1"},
        {"Cycles": "2"},
        {"Cycles": "3"},
    ]

    stats = sheets._build_cycle_stats(books, cycle_number=1)

    assert stats["cycle_number"] == 1
    assert stats["already_voted"] == 2


def test_get_book_club_stats_from_mocked_sheet(monkeypatch):
    class FakeWorksheet:
        def row_values(self, row):
            assert row == 1
            return ["Title", "Votes", "Cycles", "Status"]

        def get_all_records(self):
            return [
                {"Title": "Book A", "Votes": 4, "Cycles": 1, "Status": ""},
                {"Title": "Book B", "Votes": 1, "Cycles": 2, "Status": "Completed"},
                {"Title": "Book C", "Votes": 0, "Cycles": 0, "Status": ""},
            ]

    monkeypatch.setattr(sheets, "sheet", lambda: FakeWorksheet())

    stats = sheets.get_book_club_stats()

    assert stats["total_books"] == 3
    assert stats["completed_books"] == 1
    assert stats["current_cycle_number"] == 2
    assert stats["first_cycle_voted"] == 2
    assert stats["first_cycle_waiting"] == 1


def test_get_top_books_excludes_completed_and_sorts(monkeypatch):
    books = [
        {"Title": "A", "Status": "", "Votes": "2"},
        {"Title": "B", "Status": "Completed", "Votes": "10"},
        {"Title": "C", "Status": "", "Votes": "6"},
    ]

    monkeypatch.setattr(sheets, "get_all_books", lambda: books)

    top = sheets.get_top_books(5)

    assert [b["Title"] for b in top] == ["C", "A"]


def test_ranking_top5_uses_get_top_books(monkeypatch):
    expected = [{"Title": "A"}]
    monkeypatch.setattr(ranking, "get_top_books", lambda count: expected if count == 5 else [])

    assert ranking.top5() == expected

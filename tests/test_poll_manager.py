from datetime import datetime, timedelta

import pytest

import poll_manager


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "polls_test.db"
    monkeypatch.setattr(poll_manager, "DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
@pytest.mark.integration
async def test_init_db_and_create_poll_and_get_active_polls(isolated_db):
    await poll_manager.init_db()

    books = [{"Title": "Book A"}, {"Title": "Book B"}]
    await poll_manager.create_poll(
        poll_id="poll-1",
        message_id=101,
        chat_id=-1000,
        books=books,
        duration_seconds=60,
    )

    active = await poll_manager.get_active_polls()

    assert len(active) == 1
    assert active[0]["poll_id"] == "poll-1"
    assert active[0]["status"] == "active"
    assert active[0]["books"] == "Book A|Book B"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_poll_vote_and_get_poll_votes(isolated_db):
    await poll_manager.init_db()
    await poll_manager.create_poll(
        poll_id="poll-2",
        message_id=102,
        chat_id=-1000,
        books=[{"Title": "Book A"}, {"Title": "Book B"}],
        duration_seconds=60,
    )

    await poll_manager.save_poll_vote("poll-2", 0, 5)
    await poll_manager.save_poll_vote("poll-2", 1, 2)

    votes = await poll_manager.get_poll_votes("poll-2")

    assert votes == [
        {"option_id": 0, "votes_count": 5},
        {"option_id": 1, "votes_count": 2},
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_final_poll_updates_votes_once_and_marks_processed(
    isolated_db, monkeypatch
):
    await poll_manager.init_db()
    await poll_manager.create_poll(
        poll_id="poll-3",
        message_id=103,
        chat_id=-1000,
        books=[{"Title": "Book A"}, {"Title": "Book B"}],
        duration_seconds=60,
    )

    await poll_manager.save_poll_vote("poll-3", 0, 7)
    await poll_manager.save_poll_vote("poll-3", 1, 1)

    applied = []

    def fake_update_votes(title, votes):
        applied.append((title, votes))
        return True

    monkeypatch.setattr(poll_manager, "update_votes", fake_update_votes)

    await poll_manager.process_final_poll("poll-3")
    await poll_manager.process_final_poll("poll-3")

    info = await poll_manager.get_poll_info("poll-3")

    assert applied == [("Book A", 7), ("Book B", 1)]
    assert info["status"] == "processed"


def test_parse_db_datetime_supported_formats():
    assert poll_manager.parse_db_datetime("2026-07-01 12:00") == datetime(2026, 7, 1, 12, 0)
    assert poll_manager.parse_db_datetime("2026-07-01T12:00:00") == datetime(2026, 7, 1, 12, 0, 0)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_schedule_roundtrip(isolated_db):
    await poll_manager.init_db()
    next_run = datetime.now() + timedelta(hours=1)

    await poll_manager.upsert_poll_schedule(
        enabled=True,
        next_run=next_run,
        interval_seconds=7200,
    )

    schedule = await poll_manager.get_poll_schedule()

    assert schedule is not None
    assert schedule["enabled"] == 1
    assert schedule["interval_seconds"] == 7200
    assert schedule["next_run"].replace(microsecond=0) == next_run.replace(microsecond=0)

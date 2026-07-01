import os
from pathlib import Path

import pytest


@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_SMOKE") != "1",
    reason="Set RUN_LIVE_SMOKE=1 to run real Telegram/Sheets smoke checks",
)
async def test_live_create_poll_flow(monkeypatch, tmp_path):
    env_file = os.getenv("ENV_FILE", ".env")
    env_path = Path(env_file)

    if not env_path.exists():
        pytest.skip(
            f"ENV_FILE '{env_file}' does not exist. "
            "Create .env.test with test credentials first."
        )

    import bot
    import config
    import poll_manager

    # Safety guard: only run smoke against test-like resources unless
    # explicitly overridden.
    if os.getenv("ALLOW_PROD_SMOKE") != "1":
        if not env_path.name.endswith(".test"):
            pytest.skip(
                "Smoke blocked: ENV_FILE must point to a test profile "
                "(for example .env.test)."
            )

        creds_name = Path(str(config.GOOGLE_CREDS_FILE)).name.lower()
        if "test" not in creds_name:
            pytest.skip(
                "Smoke blocked: GOOGLE_CREDS_FILE does not look like "
                "test credentials."
            )

    db_path = tmp_path / "smoke_polls.db"
    monkeypatch.setattr(poll_manager, "DB_PATH", str(db_path))

    await poll_manager.init_db()

    # Keep smoke deterministic and lightweight.
    monkeypatch.setattr(bot, "POLL_DURATION", 30)

    poll = await bot.create_voting_poll(
        chat_id=bot.CHAT_ID,
        duration_seconds=30,
    )

    assert poll is not None

    info = await poll_manager.get_poll_info(poll.poll.id)
    assert info is not None
    assert info["status"] == "active"

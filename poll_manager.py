# Poll manager for Telegram voting
import aiosqlite
from datetime import datetime, timedelta
from config import POLL_DURATION
from sheets import update_votes

import logging

logger = logging.getLogger(__name__)

DB_PATH = "polls.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                poll_id TEXT PRIMARY KEY,
                message_id INTEGER,
                chat_id INTEGER,
                books TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        await db.commit()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS poll_votes (
                poll_id TEXT,
                option_id INTEGER,
                votes_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (poll_id, option_id)
        )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS poll_schedule (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL,
                next_run DATETIME,
                interval_hours INTEGER NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME
            )
        ''')

        # Backward-compatible migration for existing databases.
        async with db.execute("PRAGMA table_info(poll_schedule)") as cursor:
            columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if "interval_seconds" not in column_names:
            await db.execute(
                "ALTER TABLE poll_schedule "
                "ADD COLUMN interval_seconds INTEGER NOT NULL DEFAULT 0"
            )
        await db.commit()

async def create_poll(
    poll_id,
    message_id,
    chat_id,
    books,
    duration_seconds=None
):
    created_at = datetime.now()
    poll_duration = duration_seconds if duration_seconds is not None else POLL_DURATION
    expires_at = created_at + timedelta(seconds=poll_duration + 30)
    books_str = '|'.join([b['Title'] for b in books])

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO polls (
                poll_id, message_id, chat_id,
                books, created_at, expires_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        ''', (
            str(poll_id),
            message_id,
            chat_id,
            books_str,
            created_at,
            expires_at
        ))
        await db.commit()


async def upsert_poll_schedule(enabled, next_run, interval_seconds):
    created_at = datetime.now()
    interval_hours = int(interval_seconds // 3600)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''
            INSERT INTO poll_schedule (
                id, enabled, next_run, interval_hours, interval_seconds, created_at
            )
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                enabled=excluded.enabled,
                next_run=excluded.next_run,
                interval_hours=excluded.interval_hours,
                interval_seconds=excluded.interval_seconds
            ''',
            (
                1 if enabled else 0,
                next_run,
                interval_hours,
                interval_seconds,
                created_at
            )
        )
        await db.commit()


async def get_poll_schedule():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM poll_schedule WHERE id = 1'
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)


async def disable_poll_schedule():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''
            UPDATE poll_schedule
            SET enabled = 0
            WHERE id = 1
            '''
        )
        await db.commit()


async def set_poll_schedule_next_run(next_run):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''
            UPDATE poll_schedule
            SET next_run = ?
            WHERE id = 1
            ''',
            (next_run,)
        )
        await db.commit()

async def get_active_polls():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM polls WHERE status = "active"'
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def close_poll(poll_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE polls SET status='closed' WHERE poll_id=?",
            (str(poll_id),)
        )
        await db.commit()

async def mark_poll_processed(poll_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE polls SET status='processed' WHERE poll_id=?",
            (str(poll_id),)
        )
        await db.commit()

async def get_poll_info(poll_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM polls WHERE poll_id=?',
            (str(poll_id),)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)

async def save_poll_vote(
    poll_id,
    option_id,
    votes_count
):
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            INSERT OR REPLACE INTO poll_votes
            (
                poll_id,
                option_id,
                votes_count
            )
            VALUES (?, ?, ?)
        """, (
            str(poll_id),
            option_id,
            votes_count
        ))

        await db.commit()


async def get_poll_votes(poll_id):

    async with aiosqlite.connect(DB_PATH) as db:

        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT option_id, votes_count
            FROM poll_votes
            WHERE poll_id = ?
            ORDER BY option_id
            """,
            (str(poll_id),)
        ) as cursor:

            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

async def process_final_poll(poll_id):

    try:

        poll_info = await get_poll_info(poll_id)

        if not poll_info:
            logger.warning(
                f"Poll {poll_id} not found"
            )
            return

        if poll_info["status"] == "processed":
            logger.info(
                f"Poll {poll_id} already processed"
            )
            return

        books = poll_info["books"].split("|")
        chat_id = poll_info["chat_id"]

        votes = await get_poll_votes(poll_id)

        for vote in votes:

            option_id = vote["option_id"]

            if option_id >= len(books):
                continue

            book_title = books[option_id]
            votes_count = vote["votes_count"]

            logger.info(
                f"📊 {book_title}: {votes_count}"
            )

            update_votes(
                book_title,
                votes_count
            )

        await mark_poll_processed(
            poll_id
        )

        await close_poll(
            poll_id
        )

        logger.info(
            f"Poll {poll_id} processed"
        )

    except Exception:
        logger.exception(
            f"Error processing poll {poll_id}"
        )
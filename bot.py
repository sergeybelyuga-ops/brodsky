from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, Poll
import asyncio
import logging
import random
import re
from datetime import datetime, timedelta

from config import BOT_TOKEN, POLL_DURATION, BOOKS_PER_POLL, CHAT_ID
from ranking import top5
from sheets import get_all_books, get_book_club_stats, SheetStatsError
from poll_manager import (
    init_db,
    create_poll,
    get_active_polls,
    process_final_poll,
    parse_db_datetime,
    save_poll_vote,
    upsert_poll_schedule,
    get_poll_schedule,
    disable_poll_schedule,
    set_poll_schedule_next_run
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
poll_creation_lock = asyncio.Lock()

AUTOSCHEDULE_USAGE = (
    "Usage:\n"
    "/autoschedule YYYY-MM-DD HH:MM INTERVAL\n"
    "Example:\n"
    "/autoschedule 2026-07-01 20:00 60m\n"
    "Units: s=seconds, m=minutes, h=hours, d=days"
)


def format_scheduler_datetime(value):
    local_value = value.astimezone()
    return local_value.strftime("%Y-%m-%d %H:%M:%S %z")


async def create_voting_poll(chat_id, duration_seconds):
    async with poll_creation_lock:
        active_polls = await get_active_polls()

        active_poll_titles = get_active_poll_titles(active_polls)
        books = select_books_for_poll(active_poll_titles)

        if not books:
            logger.warning(
                "No books available for voting after excluding active poll titles"
            )
            return None

        poll_options = [
            f"{b['Title']}. {b['Author']}({b['Pages']} стр. | "
            f"{b['Genre'].split(',')[0].strip()}) {b['Description']}"
            for b in books
        ]

        poll_options = [
            opt[:100] if len(opt) > 100 else opt
            for opt in poll_options
        ]

        # For the 2nd and other cycles, don't allow multiple answers.
        current_cycle = min((int(b.get('Cycles', 0) or 0) for b in books), default=0)
        multiple_answers = current_cycle == 0

        poll = await bot.send_poll(
            chat_id=chat_id,
            question="📚 Что бы ты почитал?",
            options=poll_options,
            is_anonymous=False,
            allows_multiple_answers=multiple_answers,
            open_period=duration_seconds
        )

        await create_poll(
            poll_id=poll.poll.id,
            message_id=poll.message_id,
            chat_id=chat_id,
            books=books,
            duration_seconds=duration_seconds
        )

        logger.info(
            f"Poll created: {poll.poll.id}, "
            f"chat_id={chat_id}, duration_seconds={duration_seconds}"
        )

        return poll


def get_active_poll_titles(active_polls):
    titles = set()

    for poll_row in active_polls:
        books_raw = str(poll_row.get("books") or "")
        for title in books_raw.split("|"):
            clean_title = title.strip()
            if clean_title:
                titles.add(clean_title)

    return titles


def select_books_for_poll(excluded_titles):
    books = get_all_books()
    current_cycle = min((int(b.get('Cycles', 0) or 0) for b in books), default=0)

    not_completed_books = [
        b for b in books
        if b.get('Status') != "Completed"
    ]
    not_voted_books = [
        b for b in not_completed_books
        if int(b.get('Cycles', 0) or 0) <= current_cycle
    ]

    if excluded_titles:
        not_voted_books = [
            b for b in not_voted_books
            if str(b.get('Title', '')).strip() not in excluded_titles
        ]

    if current_cycle == 0:
        return random.sample(
            not_voted_books,
            min(BOOKS_PER_POLL, len(not_voted_books))
        )

    not_voted_books.sort(
        key=lambda x: int(x.get('Votes', 0) or 0),
        reverse=True
    )
    return not_voted_books[:BOOKS_PER_POLL]


def parse_autoschedule_args(text):
    parts = text.strip().split()
    if len(parts) != 4:
        return None, None

    date_str = parts[1]
    time_str = parts[2]
    interval_str = parts[3].lower()

    try:
        start_dt = datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return None, None

    interval_seconds = parse_interval_to_seconds(interval_str)
    if interval_seconds is None:
        return None, None

    return start_dt, interval_seconds


def parse_interval_to_seconds(interval_str):
    match = re.fullmatch(r"(\d+)([smhd])", interval_str)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if value <= 0:
        return None

    unit_multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    return value * unit_multiplier[unit]


def format_interval(interval_seconds):
    if interval_seconds % 86400 == 0:
        return f"{interval_seconds // 86400}d"
    if interval_seconds % 3600 == 0:
        return f"{interval_seconds // 3600}h"
    if interval_seconds % 60 == 0:
        return f"{interval_seconds // 60}m"
    return f"{interval_seconds}s"


def get_schedule_interval_seconds(schedule):
    interval_seconds = int(schedule.get("interval_seconds") or 0)
    if interval_seconds > 0:
        return interval_seconds

    # Backward compatibility for rows created before interval_seconds.
    interval_hours = int(schedule.get("interval_hours") or 0)
    return interval_hours * 3600


def get_schedule_chat_id(schedule):
    chat_id = schedule.get("chat_id")
    if chat_id is None or str(chat_id).strip() == "":
        return CHAT_ID

    try:
        return int(chat_id)
    except (TypeError, ValueError):
        logger.warning(
            "Scheduler has invalid chat_id=%s, fallback to CHAT_ID=%s",
            chat_id,
            CHAT_ID,
        )
        return CHAT_ID


def is_scheduler_admin(msg: Message):
    return True #msg.chat.id == CHAT_ID


@dp.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(
        "📖 Book Club Bot - Brodsky\n\n"
        "Helps to simplify choose of the next book to read in your club. Runs once a day and save book ratings\n\n"
        "/voting - Create voting poll\n"
        "/stat - Show book club statistics\n"
        "/top - Show top 5 rated books\n"
        "\n"
        "You can automate poll creation:\n"
        "/autoschedule - Enable automatic poll schedule\n"
        "  Example: /autoschedule 2026-07-01 09:00 60m\n"
        "  Units: s=seconds, m=minutes, h=hours, d=days\n"
        "/autostop - Disable automatic poll schedule\n"
        "/autostatus - Show automatic scheduler status\n"
        "\n"
        "/help - Help"
    )


@dp.message(Command("voting"))
async def cmd_voting(msg: Message):
    try:
        poll = await create_voting_poll(
            chat_id=msg.chat.id,
            duration_seconds=POLL_DURATION
        )
        if not poll:
            await msg.answer(
                "❌ Не удалось создать опрос: нет доступных книг для нового опроса"
            )
            return
       # await msg.answer("✅ Poll created")

    except Exception as e:
        logger.exception("Error creating poll")
        await msg.answer(f"❌ Error creating poll: {e}")


@dp.message(Command("autoschedule"))
async def cmd_autoschedule(msg: Message):
    if not is_scheduler_admin(msg):
        await msg.answer("❌ Only configured admin chat can manage autoschedule")
        return

    start_dt, interval_seconds = parse_autoschedule_args(msg.text or "")

    if not start_dt or not interval_seconds:
        await msg.answer(
            "❌ Invalid parameters.\n\n"
            f"{AUTOSCHEDULE_USAGE}"
        )
        return

    if start_dt <= datetime.now():
        await msg.answer(
            "❌ Start date must be in the future.\n\n"
            f"{AUTOSCHEDULE_USAGE}"
        )
        return

    await upsert_poll_schedule(
        enabled=True,
        next_run=start_dt,
        interval_seconds=interval_seconds,
        chat_id=msg.chat.id,
    )

    now = datetime.now()
    logger.info(
        "Scheduler setup: "
        f"system_time={format_scheduler_datetime(now)}, "
        f"scheduled_time={format_scheduler_datetime(start_dt)}, "
        f"interval_seconds={interval_seconds}"
    )

    logger.info(
        "Scheduler enabled: "
        f"next_run={start_dt.isoformat()}, interval_seconds={interval_seconds}"
    )

    await msg.answer(
        "✅ Automatic poll creation enabled\n\n"
        f"Next poll: {start_dt.strftime('%Y-%m-%d %H:%M')}\n"
        f"Interval: {format_interval(interval_seconds)}\n"
        f"Poll lifetime: {format_interval(interval_seconds)}"
    )


@dp.message(Command("autostop"))
async def cmd_autostop(msg: Message):
    if not is_scheduler_admin(msg):
        await msg.answer("❌ Only configured admin chat can manage autoschedule")
        return

    schedule = await get_poll_schedule()
    if not schedule:
        await msg.answer("Automatic poll creation: Disabled")
        return

    await disable_poll_schedule()

    logger.info("Scheduler disabled")
    await msg.answer("✅ Automatic poll creation disabled")


@dp.message(Command("autostatus"))
async def cmd_autostatus(msg: Message):
    schedule = await get_poll_schedule()

    if not schedule or int(schedule.get("enabled", 0)) != 1:
        await msg.answer("Automatic poll creation: Disabled")
        return

    next_run_value = schedule.get("next_run")
    next_run = parse_db_datetime(next_run_value)
    interval_seconds = get_schedule_interval_seconds(schedule)
    schedule_chat_id = get_schedule_chat_id(schedule)

    await msg.answer(
        "Automatic poll creation: Enabled\n\n"
        f"Next poll:\n{next_run.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Interval:\n{format_interval(interval_seconds)}\n\n"
        f"Poll lifetime:\n{format_interval(interval_seconds)}"
    )




@dp.message(Command("top"))
async def cmd_top(msg: Message):
    books = top5()

    if not books:
        await msg.answer("No books have been voted yet")
        return

    text = "🏆 TOP 5 BOOKS\n\n"

    for i, book in enumerate(books, 1):
        votes = book.get("Votes", "0")
        text += (
            f"{i}. {book['Title']} — {book['Author']}\n"
            f"   🎫 {votes} votes\n\n"
        )

    await msg.answer(text)


@dp.message(Command("stat"))
async def cmd_stat(msg: Message):
    try:
        stats = get_book_club_stats()
    except SheetStatsError as exc:
        await msg.answer(f"❌ Unable to calculate statistics: {exc}")
        return
    except Exception:
        logger.exception("Unexpected error calculating statistics")
        await msg.answer(
            "❌ Unable to calculate statistics due to an unexpected error"
        )
        return

    await msg.answer(
        "📚 Book Club Statistics\n\n"
        f"📖 Total books: {stats['total_books']}\n"
        f"✅ Books completed: {stats['completed_books']}\n\n"
        "🗳️ First voting cycle\n"
        f"• Already voted: {stats['first_cycle_voted']}\n"
        f"• Waiting for first vote: {stats['first_cycle_waiting']}\n\n"
        f"🗳️ Current voting cycle #{stats['current_cycle_number']}\n"
        f"• Already voted: {stats['current_cycle_voted']}\n"
        f"• Waiting for vote: {stats['current_cycle_waiting']}"
    )


@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "/voting - Create voting poll\n"
        "/stat - Show book club statistics\n"
        "/top - Show top 5 rated books\n\n"
        "/autoschedule YYYY-MM-DD HH:MM INTERVAL\n"
        "  Example: /autoschedule 2026-07-01 20:00 60m\n"
        "  Units: s=seconds, m=minutes, h=hours, d=days\n"
        "/autostop - Disable automatic poll schedule\n"
        "/autostatus - Show automatic scheduler status\n\n"
        "/help - Help"
    )


async def execute_auto_schedule_if_due():
    schedule = await get_poll_schedule()
    if not schedule:
        return

    if int(schedule.get("enabled", 0)) != 1:
        return

    next_run_value = schedule.get("next_run")
    if not next_run_value:
        return

    now = datetime.now()
    next_run = parse_db_datetime(next_run_value)
    interval_seconds = get_schedule_interval_seconds(schedule)
    schedule_chat_id = get_schedule_chat_id(schedule)

    logger.info(
        "Scheduler execution check: "
        f"system_time={format_scheduler_datetime(now)}, "
        f"scheduled_time={format_scheduler_datetime(next_run)}, "
        f"interval_seconds={interval_seconds}"
    )

    if interval_seconds <= 0:
        logger.error("Scheduler has invalid interval_seconds, disabling")
        await disable_poll_schedule()
        return

    if now < next_run:
        return

    try:
        poll = await create_voting_poll(
            chat_id=schedule_chat_id,
            duration_seconds=interval_seconds
        )

        if not poll:
            logger.info(
                "Automatic poll creation skipped: no books available for new poll"
            )
        else:
            logger.info(
                "Automatic poll created: "
                f"poll_id={poll.poll.id}, next_run_before={next_run.isoformat()}"
            )

        upcoming_next_run = next_run + timedelta(seconds=interval_seconds)
        while upcoming_next_run <= now:
            upcoming_next_run += timedelta(seconds=interval_seconds)

        await set_poll_schedule_next_run(upcoming_next_run)
        logger.info(
            "Scheduler next run updated: "
            f"{upcoming_next_run.isoformat()}"
        )

    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        if "chat not found" in error_text:
            logger.error(
                "Scheduler disabled: target chat not found (chat_id=%s)",
                schedule_chat_id,
            )
            await disable_poll_schedule()
            return

        logger.exception("Error during automatic poll creation")
    except Exception:
        logger.exception("Error during automatic poll creation")

async def poll_watcher():
    """
    Каждую минуту проверяет активные опросы.
    Если время истекло — запускает обработку.
    Обрабатывает два сценария: 
        - если опрос закрыт, но не обработан
        - если нужно создать автоматический опрос по расписанию
    """

    while True:

        try:
            active_polls = await get_active_polls()

            now = datetime.now()

            for poll_list in active_polls:

                expires_at = parse_db_datetime(poll_list["expires_at"])

                if now < expires_at:
                    continue

                if poll_list["status"] != "active":
                    continue

                try:
                    await process_final_poll(poll_list["poll_id"])

                except Exception as e:
                    logger.exception(
                        f"Error processing poll "
                        f"{poll_list['poll_id']}: {e}"
                    )

            # Run scheduler after processing expired polls to reduce
            # chance of selecting the same books again.
            await execute_auto_schedule_if_due()

        except Exception:
            logger.exception(
                "Error in poll_watcher"
            )

        await asyncio.sleep(60)

@dp.poll()
async def on_poll_update(poll: Poll):
    try:

        poll_id = poll.id

        logger.info(
            f"Poll update received - "
            f"Poll: {poll_id}, "
            f"Closed: {poll.is_closed}"
        )

        for option_id, option in enumerate(poll.options):

            votes_count = option.voter_count

            logger.info(
                f"Option #{option_id}: "
                f"{votes_count} votes"
            )

            # здесь сохранение в БД
            await save_poll_vote(
                poll_id=poll_id,
                option_id=option_id,
                votes_count=votes_count
            )

    except Exception as e:
        logger.error(
            f"Error handling poll update: {e}",
            exc_info=True
        )


async def start():
    await init_db()
    logger.info("Bot started")

    asyncio.create_task(
        poll_watcher()
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start())

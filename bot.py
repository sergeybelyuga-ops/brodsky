from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, Update
import asyncio
import logging

from config import BOT_TOKEN, POLL_DURATION, BOOKS_PER_POLL
from ranking import top5
from sheets import get_unread_books
from poll_manager import (
    init_db,
    create_poll,
    get_active_polls,
    process_final_poll,
    save_poll_vote
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(
        "📖 Book Club Bot - Brodsky\n\n"
        "Helps to simplify choose of the next book to read in your club. Runs once a day and save book ratings\n\n"
        "/voting - Create voting poll\n"
        "/top - Show top 5 rated books\n"
        "/help - Help"
    )


@dp.message(Command("voting"))
async def cmd_voting(msg: Message):
    try:
        books = get_unread_books(BOOKS_PER_POLL)

        if not books:
            await msg.answer("❌ Нет книг для голосования")
            return

        poll_options = [
            f"{b['Title']}. {b['Author']}({b['Pages']} стр. | "
            f"{b['Genre'].split(',')[0].strip()}) {b['Description']}"
            for b in books
        ]

        poll_options = [
            opt[:100] if len(opt) > 100 else opt
            for opt in poll_options
        ]
        
        # For the 2nd and other cycles, don't allow multiple answers, so voting will be more fair.
        current_cycle = min((int(b.get('Cycles', 0) or 0) for b in books), default=0)
        if current_cycle == 0:
            multiple_answers=True
        else:
            multiple_answers=False

        poll = await bot.send_poll(
            chat_id=msg.chat.id,
            question="📚 Что бы ты почитал?",
            options=poll_options,
            is_anonymous=False,
            allows_multiple_answers=multiple_answers,
            open_period=POLL_DURATION
        )

        await create_poll(
            poll_id=poll.poll.id,
            message_id=poll.message_id,
            chat_id=msg.chat.id,
            books=books
        )

        logger.info(f"Poll created: {poll.poll.id}")

    except Exception as e:
        logger.exception("Error creating poll")
        await msg.answer(f"❌ Error creating poll: {e}")




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


@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "/voting - Create voting poll\n"
        "/top - Show top 5 rated books\n"
        "/help - Help"
    )

async def poll_watcher():
    """
    Каждую минуту проверяет активные опросы.
    Если время истекло — запускает обработку.
    """

    while True:

        try:

            active_polls = await get_active_polls()

            now = datetime.now()

            for poll_list in active_polls:

                expires_at = datetime.fromisoformat(
                    str(poll_list["expires_at"])
                )

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

        except Exception:
            logger.exception(
                "Error in poll_watcher"
            )

        await asyncio.sleep(60)


from aiogram.types import Poll

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


import asyncio
from datetime import datetime

from poll_manager import (
    get_active_polls
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

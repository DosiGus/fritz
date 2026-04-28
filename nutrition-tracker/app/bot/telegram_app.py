import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.commands import (
    cmd_cancel,
    cmd_delete_last,
    cmd_edit_last,
    cmd_favorites,
    cmd_goal,
    cmd_help,
    cmd_start,
    cmd_today,
)
from app.bot.handlers import handle_callback_query
from app.bot.message_router import route_message
from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


_BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Bot starten"),
    BotCommand("help", "Hilfe & Befehle"),
    BotCommand("today", "Heutiger Überblick"),
    BotCommand("goal", "Tagesziel setzen"),
    BotCommand("delete_last", "Letzten Eintrag löschen"),
    BotCommand("edit_last", "Letzten Eintrag bearbeiten"),
    BotCommand("favorites", "Standardmahlzeiten"),
    BotCommand("cancel", "Aktion abbrechen"),
]


async def register_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(_BOT_COMMANDS)


def build_application() -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(register_bot_commands)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("goal", cmd_goal))
    app.add_handler(CommandHandler("delete_last", cmd_delete_last))
    app.add_handler(CommandHandler("edit_last", cmd_edit_last))
    app.add_handler(CommandHandler("favorites", cmd_favorites))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    app.add_handler(CallbackQueryHandler(handle_callback_query))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, route_message))

    return app


if __name__ == "__main__":
    logger.info("Starting bot in polling mode")
    application = build_application()
    application.run_polling(drop_pending_updates=True)

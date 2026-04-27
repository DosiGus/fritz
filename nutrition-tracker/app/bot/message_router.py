from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers import handle_text_message, handle_voice_message


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    if msg.voice:
        await handle_voice_message(update, context)
    elif msg.text:
        await handle_text_message(update, context)

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, EMBED_BASE_URL
from utils import generate_id, store_stream, remove_stream, get_active_streams, get_screenshot, get_proxy_url
import asyncio

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Stream Manager Bot\n\n"
        "Use:\n"
        "/stream <m3u8_url> <title>\n"
        "/live → See all live streams"
    )

async def stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /stream <m3u8_url> <title>")
        return

    m3u8_url = context.args[0]
    title = " ".join(context.args[1:])
    stream_id = generate_id()

    store_stream(stream_id, m3u8_url, title)

    embed_url = f"{EMBED_BASE_URL}/embed/{stream_id}"
    proxy_used = "Yes" if get_proxy_url(m3u8_url, stream_id) != m3u8_url else "No"

    await update.message.reply_text(
        f"Stream Started!\n\n"
        f"Title: {title}\n"
        f"ID: `{stream_id}`\n"
        f"Embed: {embed_url}\n"
        f"Proxy: {proxy_used}\n\n"
        f"Use /live to manage",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    streams = get_active_streams()
    if not streams:
        await update.message.reply_text("No live streams.")
        return

    for s in streams:
        photo = get_screenshot(s['url'])
        caption = (
            f"<b>{s['title']}</b>\n"
            f"Uptime: {s['uptime']}\n"
            f"Viewers: {s['viewers']}\n"
            f"ID: <code>{s['id']}</code>"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Stop", callback_data=f"stop:{s['id']}"),
                InlineKeyboardButton("Embed", url=f"{EMBED_BASE_URL}/embed/{s['id']}")
            ]
        ])

        if photo:
            await update.message.reply_photo(
                photo=photo, caption=caption, reply_markup=keyboard, parse_mode='HTML'
            )
        else:
            await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('stop:'):
        stream_id = query.data.split(':')[1]
        remove_stream(stream_id)
        await query.edit_message_caption(
            caption="Stream Stopped.\nEmbed link no longer works.",
            parse_mode='HTML'
        )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stream", stream))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == '__main__':
    main()

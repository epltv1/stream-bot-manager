import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, EMBED_BASE_URL
from utils import slugify, store_stream, remove_stream, get_active_streams, get_screenshot
import re

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "m3u8 Proxy Bot\n\n"
        "/stream <m3u8_url> <title>\n"
        "/live → See all links\n"
        "/stop <title> → Remove"
    )

async def stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /stream <m3u8_url> <title>")
        return

    m3u8_url = context.args[0]
    title = " ".join(context.args[1:])
    stream_id = slugify(title)

    for s in get_active_streams():
        if s['id'] == stream_id:
            await update.message.reply_text(f"Title '{title}' already in use!")
            return

    store_stream(stream_id, m3u8_url, title)
    m3u8_link = f"{EMBED_BASE_URL}/{stream_id}.m3u8"

    await update.message.reply_text(
        f"Proxy Link Ready!\n\n"
        f"Title: {title}\n"
        f"Link: `{m3u8_link}`\n\n"
        f"Use /live to manage",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    streams = get_active_streams()
    if not streams:
        await update.message.reply_text("No active streams.")
        return

    for s in streams:
        photo = get_screenshot(s['url'])
        caption = (
            f"<b>{s['title']}</b>\n"
            f"Link: <code>{EMBED_BASE_URL}/{s['id']}.m3u8</code>\n"
            f"Uptime: {s['uptime']}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Stop", callback_data=f"stop:{s['id']}")]
        ])

        if photo:
            await update.message.reply_photo(photo=photo, caption=caption, reply_markup=keyboard, parse_mode='HTML')
        else:
            await update.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop <title>")
        return
    title = " ".join(context.args)
    stream_id = slugify(title)
    if remove_stream(stream_id):
        await update.message.reply_text(f"Stopped: {title}")
    else:
        await update.message.reply_text("Stream not found.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith('stop:'):
        stream_id = query.data.split(':')[1]
        remove_stream(stream_id)
        await query.edit_message_caption(caption="Stream stopped.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stream", stream))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == '__main__':
    main()

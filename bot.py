import logging
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, EMBED_BASE_URL
from utils import slugify, store_stream, remove_stream, get_active_streams, get_screenshot
import re

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Restream Bot (Single VPS)\n\n"
        "Commands:\n"
        "/stream <m3u8_url> <title>\n"
        "/live → See all streams\n"
        "/stop <title> → Remove stream\n\n"
        "Your stream will be fully re-hosted under your domain.\n"
        "Works in VLC, JW Player, MX Player, etc."
    )

async def stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /stream <m3u8_url> <title>")
        return

    m3u8_url = context.args[0].strip()
    title = " ".join(context.args[1:]).strip()
    stream_id = slugify(title)

    # Check for duplicate title
    if any(s['id'] == stream_id for s in get_active_streams()):
        await update.message.reply_text(f"Title '{title}' is already in use! Use a different name.")
        return

    # Store in Redis
    store_stream(stream_id, m3u8_url, title)
    m3u8_link = f"{EMBED_BASE_URL}/{stream_id}.m3u8"

    await update.message.reply_text(
        f"Restream Started!\n\n"
        f"Title: *{title}*\n"
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
        uptime = s['uptime']
        caption = (
            f"<b>{s['title']}</b>\n"
            f"Link: <code>{EMBED_BASE_URL}/{s['id']}.m3u8</code>\n"
            f"Uptime: {uptime}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Stop Stream", callback_data=f"stop:{s['id']}")]
        ])

        if photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                text=caption,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop <title>")
        return

    title = " ".join(context.args).strip()
    stream_id = slugify(title)

    if remove_stream(stream_id):
        await update.message.reply_text(f"Stopped: *{title}*", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"Stream not found: *{title}*", parse_mode='Markdown')

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('stop:'):
        stream_id = query.data.split(':')[1]
        data = r.hgetall(f'stream:{stream_id}')
        if data:
            title = data[b'title'].decode()
            remove_stream(stream_id)
            await query.edit_message_caption(
                caption=f"Stream *{title}* has been stopped.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_caption(caption="Stream already removed.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stream", stream))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

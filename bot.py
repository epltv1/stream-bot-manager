import logging
import io
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, EMBED_BASE_URL
from utils import slugify, store_stream, remove_stream, get_active_streams, r, segment_downloader
import ffmpeg

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Restream Bot – LIVE*\n\n"
        "Commands:\n"
        "• `/stream <m3u8_url> <title>`\n"
        "• `/live` → List active streams\n"
        "• `/stop <title>` → Stop stream\n\n"
        "Your stream is *fully re-hosted* and *continuously updated*.\n"
        "Works in VLC, JW Player, MX Player, Smart TV.",
        parse_mode='Markdown'
    )

async def stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/stream <m3u8_url> <title>`", parse_mode='Markdown')
        return

    m3u8_url = context.args[0].strip()
    title = " ".join(context.args[1:]).strip()
    stream_id = slugify(title)

    # Prevent duplicate titles
    if any(s['id'] == stream_id for s in get_active_streams()):
        await update.message.reply_text(f"Title *{title}* is already in use!", parse_mode='Markdown')
        return

    # Store stream in Redis
    store_stream(stream_id, m3u8_url, title)

    # Start background downloader
    threading.Thread(target=segment_downloader, args=(stream_id,), daemon=True).start()

    # Reply with link
    m3u8_link = f"{EMBED_BASE_URL}/{stream_id}.m3u8"
    await update.message.reply_text(
        f"*Restream Started!*\n\n"
        f"Title: `{title}`\n"
        f"Link: `{m3u8_link}`\n\n"
        f"Use `/live` to manage",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    streams = get_active_streams()
    if not streams:
        await update.message.reply_text("No active streams.")
        return

    for s in streams:
        # Try to get screenshot
        photo = None
        try:
            process = (
                ffmpeg
                .input(s['url'], ss=1)
                .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
                .run(capture_stdout=True, capture_stderr=True, timeout=10)
            )
            photo = io.BytesIO(process[0])
        except Exception as e:
            logging.warning(f"Screenshot failed for {s['url']}: {e}")

        caption = (
            f"<b>{s['title']}</b>\n"
            f"<code>{EMBED_BASE_URL}/{s['id']}.m3u8</code>\n"
            f"Uptime: {s['uptime']}"
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
        await update.message.reply_text("Usage: `/stop <title>`", parse_mode='Markdown')
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
        if data and data.get(b'active') == b'True':
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

    print("Restream Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

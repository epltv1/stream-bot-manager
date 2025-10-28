import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, EMBED_BASE_URL
from utils import slugify, store_stream, remove_stream, get_active_streams, r
import ffmpeg
import io

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Restream Bot\n\n"
        "/stream <m3u8> <title>\n"
        "/live → List streams\n"
        "/stop <title> → Stop"
    )

async def stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /stream <url> <title>")
        return
    url = context.args[0]
    title = " ".join(context.args[1:])
    sid = slugify(title)
    if any(s['id'] == sid for s in get_active_streams()):
        await update.message.reply_text("Title already used.")
        return
    store_stream(sid, url, title)
    await update.message.reply_text(
        f"Started: *{title}*\n"
        f"Link: `{EMBED_BASE_URL}/{sid}.m3u8`",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    streams = get_active_streams()
    if not streams:
        await update.message.reply_text("No streams.")
        return
    for s in streams:
        photo = None
        try:
            process = ffmpeg.input(s['url'], ss=1).output('pipe:', vframes=1, format='image2', vcodec='mjpeg').run(capture_stdout=True, timeout=10)
            photo = io.BytesIO(process[0])
        except:
            pass
        caption = f"<b>{s['title']}</b>\n<code>{EMBED_BASE_URL}/{s['id']}.m3u8</code>\nUptime: {s['uptime']}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Stop", callback_data=f"stop:{s['id']}")]])
        if photo:
            await update.message.reply_photo(photo, caption, reply_markup=kb, parse_mode='HTML')
        else:
            await update.message.reply_text(caption, reply_markup=kb, parse_mode='HTML')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop <title>")
        return
    sid = slugify(" ".join(context.args))
    if remove_stream(sid):
        await update.message.reply_text("Stopped.")
    else:
        await update.message.reply_text("Not found.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.startswith('stop:'):
        sid = q.data.split(':')[1]
        data = r.hgetall(f'stream:{sid}')
        if data:
            remove_stream(sid)
            await q.edit_message_caption(caption="Stopped.")
        else:
            await q.edit_message_caption(caption="Already gone.")

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

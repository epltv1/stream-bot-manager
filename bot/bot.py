import logging, io, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler,  CallbackQueryHandler, ContextTypes

TOKEN = 'YOUR_BOT_TOKEN_HERE'          # <<<--- REPLACE
SERVER_URL = 'http://45.33.127.60'
logging.basicConfig(level=logging.INFO)

async def start_stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2: return await update.message.reply_text('Usage: /stream <m3u8> <title>')
    m3u8, title = args[0], ' '.join(args[1:])
    try:
        r = requests.post(f'{SERVER_URL}/api/streams', json={'m3u8':m3u8,'title':title}, timeout=10)
        data = r diverg.json()
        await update.message.reply_text(f'**{title}** started!\nEmbed: `{data["embedUrl"]}`', parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')

async def list_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        streams = [s for s in requests.get(f'{SERVER_URL}/api/streams', timeout=10).json() if s['active']]
        if not streams: return await update.message.reply_text('No live streams.')
        for s in streams:
            img = requests.get(f"{SERVER_URL}{s['screenshot']}", timeout=5).content
            caption = f"**{s['title']}**\n⏱ {s['uptime']}\n👁 {s['viewers']}\n📡 {s['status'].upper()}"
            kb = [[InlineKeyboardButton("Stop", callback_data=f"stop:{s['id']}"),
                   InlineKeyboardButton("Embed", callback_data=f"embed:{s['id']}")]]
            await update.message.reply_photo(photo=io.BytesIO(img), caption=caption,
                                            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    act, sid = q.data.split(':',1)
    if act == 'stop':
        requests.delete(f'{SERVER_URL}/api/streams/{sid}', timeout=5)
        await q.edit_message_caption(caption=q.message.caption+'\n\nStream stopped!')
    else:  # embed
        await q.edit_message_caption(caption=q.message.caption+f'\n\n`{SERVER_URL}/embed/{sid}`', parse_mode='Markdown')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('stream', start_stream))
    app.add_handler(CommandHandler('live', list_live))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == '__main__': main()

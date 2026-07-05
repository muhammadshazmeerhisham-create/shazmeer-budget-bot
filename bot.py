import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8750781186:AAHGi2hhfkHJUMa2AzawQMka47dfRT1s-9w"

# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang ke Bot Bajet Shazmeer!\n\n"
        "🚀 Bot ini sedang beroperasi."
    )

# Telegram Bot
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

# Web server untuk Render
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot sedang berjalan...")
    app.run_polling(drop_pending_updates=True)

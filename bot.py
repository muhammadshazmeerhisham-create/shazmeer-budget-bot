from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8750781186:AAHGi2hhfkHJUMa2AzawQMka47dfRT1s-9w"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Selamat Datang ke Shazmeer Budget Bot!\n\n"
        "Bot sedang beroperasi. ✅"
    )

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

if __name__ == "__main__":
    print("Bot sedang berjalan...")
    app.run_polling(close_loop=False)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from voucher_service import save_vouchers_with_cookie
from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/ping")
def ping():
    return "pong"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()


# ===== TOKEN BOT =====
TOKEN = "8290570607:AAEBgJV7dsy9gqWhL6QMJRlbqaq-atwgDqg"


# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot lưu voucher Shopee đang hoạt động!\n\n"
        "Gửi COOKIE vào đây, mỗi cookie 1 dòng."
    )


# ===== Nhận cookie =====
async def handle_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cookie_text = update.message.text.strip()

    await update.message.reply_text("⏳ Đang lưu voucher...")

    # chạy tool của bạn
    result = save_vouchers_with_cookie(cookie_text)

    await update.message.reply_text(result)


# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookie))

print("✅ Bot đang chạy...")
app.run_polling()

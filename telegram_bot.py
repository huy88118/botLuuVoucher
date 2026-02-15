import os
import json
import threading
import asyncio
from typing import List, Dict, Any, Optional

from flask import Flask
from telegram import Update
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from voucher_service import save_one_voucher_with_cookie, save_all_vouchers_with_cookie

# ----------------- Web keep-alive -----------------
web_app = Flask(__name__)

@web_app.get("/")
def home():
    return "Bot is running", 200

@web_app.get("/ping")
def ping():
    return "pong", 200

def run_web():
    port = int(os.getenv("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port)

# ----------------- Config -----------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
VOUCHERS_JSON_PATH = os.getenv("VOUCHERS_JSON_PATH", "vouchers.json")

WAIT_COOKIES = 1

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔴 Lưu Voucher"), KeyboardButton("🔁 Convert SPC_F")]],
        resize_keyboard=True
    )

def load_vouchers() -> List[Dict[str, Any]]:
    try:
        with open(VOUCHERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def inline_voucher_buttons(vouchers: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = []
    for v in vouchers:
        name = v.get("display_name") or v.get("voucher_code") or "VOUCHER"
        code = v.get("voucher_code") or name
        rows.append([InlineKeyboardButton(name, callback_data=f"pick:{code}")])

    # thêm nút "lưu tất cả"
    rows.append([InlineKeyboardButton("🧾 Lưu tất cả mã", callback_data="pick_all")])
    return InlineKeyboardMarkup(rows)

def find_voucher_by_code(vouchers: List[Dict[str, Any]], code: str) -> Optional[Dict[str, Any]]:
    for v in vouchers:
        if (v.get("voucher_code") or "") == code:
            return v
    return None

# ----------------- Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Menu:\nChọn chức năng bên dưới:",
        reply_markup=main_menu_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "🔁 Convert SPC_F":
        await update.message.reply_text("🚧 Chức năng đang phát triển.")
        return

    if text == "🔴 Lưu Voucher":
        vouchers = load_vouchers()
        if not vouchers:
            await update.message.reply_text("❌ Không có voucher trong vouchers.json")
            return

        await update.message.reply_text(
            "📌 Chọn mã voucher bạn muốn lưu (hoặc chọn Lưu tất cả):",
            reply_markup=inline_voucher_buttons(vouchers)
        )
        return

    await update.message.reply_text("❓ Bạn hãy bấm nút trong menu.")

async def pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    vouchers = load_vouchers()

    # chọn lưu tất cả
    if data == "pick_all":
        context.user_data["mode"] = "all"
        context.user_data.pop("picked_voucher", None)

        await query.message.reply_text(
            "👉 Gửi cookie vào đây để lưu *TẤT CẢ* voucher ....\n\n"
            "⭐️ Hỗ trợ lưu tối đa 10 cookie\n"
            "💡 Gửi mỗi cookie 1 dòng",
            parse_mode="Markdown"
        )
        return WAIT_COOKIES

    # chọn 1 voucher
    _, code = data.split(":", 1)
    picked = find_voucher_by_code(vouchers, code)
    if not picked:
        await query.message.reply_text("❌ Voucher không còn trong danh sách. Bấm '🔴 Lưu Voucher' để tải lại.")
        return ConversationHandler.END

    context.user_data["mode"] = "one"
    context.user_data["picked_voucher"] = picked

    await query.message.reply_text(
        f"✅ Bạn đã chọn: {picked.get('display_name') or picked.get('voucher_code')}\n\n"
        "👉 Gửi cookie vào đây để lưu voucher ....\n\n"
        "⭐️ Hỗ trợ lưu tối đa 10 cookie\n"
        "💡 Gửi mỗi cookie 1 dòng"
    )
    return WAIT_COOKIES

async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    picked = context.user_data.get("picked_voucher")

    raw = (update.message.text or "").strip()
    if not raw:
        await update.message.reply_text("❌ Cookie trống. Gửi lại (mỗi cookie 1 dòng).")
        return WAIT_COOKIES

    cookies = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(cookies) > 10:
        await update.message.reply_text("❌ Tối đa 10 cookie. Bạn gửi lại giúp mình nhé (<=10 dòng).")
        return WAIT_COOKIES

    await update.message.reply_text("⏳ Đang lưu voucher...")

    results = []
    for i, cookie in enumerate(cookies, start=1):
        try:
            if mode == "all":
                res = await asyncio.to_thread(save_all_vouchers_with_cookie, cookie)
            else:
                if not picked:
                    res = "❌ Bạn chưa chọn voucher."
                else:
                    res = await asyncio.to_thread(save_one_voucher_with_cookie, cookie, picked)
            results.append(f"Cookie {i}: {res}")
        except Exception as e:
            results.append(f"Cookie {i}: ❌ Lỗi {type(e).__name__}: {e}")

    await update.message.reply_text("\n\n".join(results))

    context.user_data.pop("mode", None)
    context.user_data.pop("picked_voucher", None)
    return ConversationHandler.END

def main():
    if not TOKEN:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong Environment Variables")

    threading.Thread(target=run_web, daemon=True).start()

    bot_app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pick_callback, pattern=r"^(pick:|pick_all)")
        ],
        states={
            WAIT_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cookies)]
        },
        fallbacks=[],
        allow_reentry=True,
    )

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(conv)
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print("✅ Bot đang chạy...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()

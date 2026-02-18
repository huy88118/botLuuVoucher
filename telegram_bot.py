import os
import json
import threading
import asyncio
import re
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
from order_service import fetch_orders, format_orders_for_telegram

# =======================
# Flask keep-alive (Render)
# =======================
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

# =======================
# Config
# =======================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
VOUCHERS_JSON_PATH = os.getenv("VOUCHERS_JSON_PATH", "vouchers.json")

# Conversation states
WAIT_COOKIES_VOUCHER = 1
WAIT_COOKIES_ORDER = 2

# =======================
# Menu / Validation
# =======================
MENU_REGEX = r"^(🎟️ Lưu Voucher|📦 Check MVĐ|🔁 Convert SPC_F)$"
menu_filter = filters.Regex(MENU_REGEX)

# Bắt buộc có SPC_ST=... (value đủ dài) dù đứng 1 mình hay nằm trong full cookie
# - group 2: value của SPC_ST
SPC_ST_PATTERN = re.compile(r"(?:^|;\s*)SPC_ST=([^;]{15,})", re.IGNORECASE)

def is_probably_shopee_cookie(s: str) -> bool:
    """
    API này chỉ cần SPC_ST, nhưng phải đúng định dạng:
    - Có 'SPC_ST='
    - Value tối thiểu 15 ký tự (tránh gõ bừa 1-2 ký tự vẫn lọt)
    """
    if not s:
        return False
    t = s.strip()
    if len(t) < 20:
        return False
    return SPC_ST_PATTERN.search(t) is not None

def _get_any(d: Dict[str, Any], keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return default

def is_real_order(order: Dict[str, Any]) -> bool:
    """
    Chặn trường hợp API trả placeholder kiểu "Đang chờ" khi cookie sai/hết hạn.
    Đơn THẬT khi có ít nhất 1 dấu hiệu:
    - order_id
    - tracking_number
    - có products/product_info và product name thật
    """
    if not isinstance(order, dict):
        return False

    order_id = _get_any(order, ["order_id", "orderid", "id"], "")
    tracking = _get_any(order, ["tracking_number", "tracking_no", "tracking"], "")

    products = order.get("product_info") or order.get("products") or []
    has_product = False
    if isinstance(products, list) and products:
        p0 = products[0] if isinstance(products[0], dict) else {}
        pname = _get_any(p0, ["name", "product_name", "title"], "")
        has_product = bool(pname)

    return bool(order_id) or bool(tracking) or has_product

def count_real_orders_from_api(data: Dict[str, Any]) -> int:
    accs = data.get("allOrderDetails") or []
    total = 0
    for a in accs:
        orders = a.get("orderDetails") or []
        for od in orders:
            if is_real_order(od):
                total += 1
    return total

# =======================
# UI
# =======================
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎟️ Lưu Voucher"), KeyboardButton("📦 Check MVĐ")],
            [KeyboardButton("🔁 Convert SPC_F")],
        ],
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
    rows.append([InlineKeyboardButton("🧾 Lưu tất cả mã", callback_data="pick_all")])
    return InlineKeyboardMarkup(rows)

def find_voucher_by_code(vouchers: List[Dict[str, Any]], code: str) -> Optional[Dict[str, Any]]:
    for v in vouchers:
        if (v.get("voucher_code") or "") == code:
            return v
    return None

def reset_user_flow(context: ContextTypes.DEFAULT_TYPE):
    # reset mọi “mode” để không bị kẹt khi đổi chức năng
    context.user_data.pop("mode", None)
    context.user_data.pop("picked_voucher", None)

# =======================
# Handlers
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user_flow(context)
    await update.message.reply_text(
        "✅ Menu:\nChọn chức năng bên dưới:",
        reply_markup=main_menu_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Bấm menu thì reset flow cũ trước (tránh kẹt state)
    reset_user_flow(context)

    if text == "🔁 Convert SPC_F":
        await update.message.reply_text("🚧 Chức năng đang phát triển.")
        return ConversationHandler.END

    if text == "🎟️ Lưu Voucher":
        vouchers = load_vouchers()
        if not vouchers:
            await update.message.reply_text("❌ Không có voucher trong vouchers.json")
            return ConversationHandler.END

        await update.message.reply_text(
            "📌 Chọn mã voucher bạn muốn lưu (hoặc chọn Lưu tất cả):",
            reply_markup=inline_voucher_buttons(vouchers)
        )
        return ConversationHandler.END

    if text == "📦 Check MVĐ":
        context.user_data["mode"] = "order_check"
        await update.message.reply_text(
            "👉 Gửi cookie vào đây để *Check MVĐ / Đơn hàng* ...\n\n"
            "⭐️ Hỗ trợ tối đa 10 cookie\n"
            "💡 Gửi mỗi cookie 1 dòng\n\n"
            "✅ API này chỉ cần `SPC_ST=...` là đủ.",
            parse_mode="Markdown"
        )
        return WAIT_COOKIES_ORDER

    await update.message.reply_text("❓ Bạn hãy bấm nút trong menu.")
    return ConversationHandler.END

# --- Voucher pick callback ---
async def pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == "pick_all":
        context.user_data["mode"] = "voucher_all"
        context.user_data.pop("picked_voucher", None)

        await query.message.reply_text(
            "👉 Gửi cookie vào đây để lưu *TẤT CẢ* voucher ....\n\n"
            "⭐️ Hỗ trợ lưu tối đa 10 cookie\n"
            "💡 Gửi mỗi cookie 1 dòng",
            parse_mode="Markdown"
        )
        return WAIT_COOKIES_VOUCHER

    vouchers = load_vouchers()
    try:
        _, code = data.split(":", 1)
    except ValueError:
        await query.message.reply_text("❌ Lựa chọn không hợp lệ. Bấm '🎟️ Lưu Voucher' để chọn lại.")
        return ConversationHandler.END

    picked = find_voucher_by_code(vouchers, code)
    if not picked:
        await query.message.reply_text("❌ Voucher không còn trong danh sách. Bấm '🎟️ Lưu Voucher' để tải lại.")
        return ConversationHandler.END

    context.user_data["mode"] = "voucher_one"
    context.user_data["picked_voucher"] = picked

    await query.message.reply_text(
        f"✅ Bạn đã chọn: {picked.get('display_name') or picked.get('voucher_code')}\n\n"
        "👉 Gửi cookie vào đây để lưu voucher ....\n\n"
        "⭐️ Hỗ trợ lưu tối đa 10 cookie\n"
        "💡 Gửi mỗi cookie 1 dòng"
    )
    return WAIT_COOKIES_VOUCHER

# --- Receive cookies for voucher ---
async def receive_cookies_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    picked = context.user_data.get("picked_voucher")

    raw = (update.message.text or "").strip()
    cookies = [line.strip() for line in raw.splitlines() if line.strip()]

    if not cookies:
        await update.message.reply_text("❌ Cookie trống. Gửi lại (mỗi cookie 1 dòng).")
        return WAIT_COOKIES_VOUCHER
    if len(cookies) > 10:
        await update.message.reply_text("❌ Tối đa 10 cookie. Bạn gửi lại giúp mình nhé (<=10 dòng).")
        return WAIT_COOKIES_VOUCHER

    await update.message.reply_text("⏳ Đang lưu voucher...")

    results = []
    for i, cookie in enumerate(cookies, start=1):
        try:
            if mode == "voucher_all":
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

    reset_user_flow(context)
    return ConversationHandler.END

# --- Receive cookies for order check ---
async def receive_cookies_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip()
    cookies = [line.strip() for line in raw.splitlines() if line.strip()]

    if not cookies:
        await update.message.reply_text("❌ Cookie trống. Gửi lại (mỗi cookie 1 dòng).")
        return WAIT_COOKIES_ORDER
    if len(cookies) > 10:
        await update.message.reply_text("❌ Tối đa 10 cookie. Bạn gửi lại giúp mình nhé (<=10 dòng).")
        return WAIT_COOKIES_ORDER

    # Validate cookie trước khi gọi API (chặn gõ bừa)
    invalid = []
    for i, c in enumerate(cookies, start=1):
        if not is_probably_shopee_cookie(c):
            invalid.append(f"- Dòng {i}: sai định dạng (phải có `SPC_ST=...`).")

    if invalid:
        await update.message.reply_text(
            "❌ Cookie không hợp lệ:\n" + "\n".join(invalid) +
            "\n\n✅ Gợi ý: gửi `SPC_ST=...` hoặc full cookie nhưng phải chứa `SPC_ST=...`.",
            parse_mode="Markdown"
        )
        return WAIT_COOKIES_ORDER

    await update.message.reply_text("⏳ Đang check đơn hàng...")

    try:
        data = await asyncio.to_thread(fetch_orders, cookies)

        # CHỐT: Nếu không có "đơn thật" => cookie sai/hết hạn/placeholder
        if count_real_orders_from_api(data) == 0:
            await update.message.reply_text(
                "❌ Cookie sai / hết hạn hoặc API không trả dữ liệu đơn hợp lệ.\n"
                "👉 Hãy lấy lại `SPC_ST` mới và thử lại."
            )
            reset_user_flow(context)
            return ConversationHandler.END

        messages = format_orders_for_telegram(data, max_orders_per_cookie=5)
        for msg in messages:
            await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

    reset_user_flow(context)
    return ConversationHandler.END

def main():
    if not TOKEN:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong Environment Variables (Render).")

    threading.Thread(target=run_web, daemon=True).start()

    bot_app = ApplicationBuilder().token(TOKEN).build()

    conv_voucher = ConversationHandler(
        entry_points=[CallbackQueryHandler(pick_callback, pattern=r"^(pick:|pick_all)")],
        states={
            WAIT_COOKIES_VOUCHER: [
                # Không để menu bị coi là cookie
                MessageHandler((filters.TEXT & ~filters.COMMAND & ~menu_filter), receive_cookies_voucher),
                MessageHandler(menu_filter, handle_menu),
            ]
        },
        fallbacks=[],
        allow_reentry=True,
    )

    conv_order = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📦 Check MVĐ$"), handle_menu)],
        states={
            WAIT_COOKIES_ORDER: [
                # Không để menu bị coi là cookie
                MessageHandler((filters.TEXT & ~filters.COMMAND & ~menu_filter), receive_cookies_order),
                MessageHandler(menu_filter, handle_menu),
            ]
        },
        fallbacks=[],
        allow_reentry=True,
    )

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(conv_voucher)
    bot_app.add_handler(conv_order)

    # menu handler chung (cho các nút khác)
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print("✅ Bot đang chạy...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

BASE_URL = "https://us-central1-get-feedback-a0119.cloudfunctions.net/app"
API_ENDPOINT = "/api/shopee/getOrderDetailsForCookie"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://autopee.vercel.app",
    "Referer": "https://autopee.vercel.app/",
}


def fetch_orders(cookies_list: List[str]) -> Dict[str, Any]:
    url = BASE_URL + API_ENDPOINT
    payload = {"cookies": cookies_list}

    response = requests.post(
        url,
        data=json.dumps(payload),
        headers=HEADERS,
        timeout=60,
    )
    if response.status_code != 200:
        raise Exception(response.text)
    return response.json()


# ================= HELPERS =================


def _fmt_ts(ts: Any) -> str:
    if ts in (None, ""):
        return ""
    try:
        ts = int(ts)
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(ts)


def _fmt_money_from_api(v: Any) -> str:
    try:
        return f"{(float(v) / 100000):,.0f} đ"
    except Exception:
        return str(v)


def _build_shopee_link(shop_id: Any, item_id: Any) -> Optional[str]:
    try:
        if shop_id and item_id:
            return f"https://shopee.vn/product/{int(shop_id)}/{int(item_id)}"
    except Exception:
        pass
    return None


def detect_carrier(tracking_number: str) -> str:
    if not tracking_number:
        return ""

    tracking_number = tracking_number.upper()

    if tracking_number.startswith("SPX"):
        return "Shopee Express"
    if tracking_number.startswith("GY") or tracking_number.startswith("GHN"):
        return "Giao Hàng Nhanh"
    if tracking_number.startswith("JNT"):
        return "J&T Express"
    if tracking_number.startswith("VNPOST"):
        return "VNPost"

    return "Không xác định"


# ================= FORMATTER =================


def format_orders_for_telegram(
    data,
    max_orders_per_cookie: int = 10,
    max_products_per_order: int = 5,
):
    messages = []

    accounts = data.get("allOrderDetails", [])
    if not accounts:
        return ["❌ Không có dữ liệu đơn hàng."]

    for account in accounts:
        cookie = account.get("cookie", "")
        orders = account.get("orderDetails", []) or []

        if not orders:
            messages.append(f"🍪 Cookie: `{cookie[:20]}...`\n❌ Không có đơn hàng.")
            continue

        text_blocks = []
        header = f"🍪 Cookie: `{cookie[:20]}...`\n📦 Tổng đơn: {len(orders)}\n"
        text_blocks.append(header)

        for index, order in enumerate(orders[:max_orders_per_cookie], start=1):

            order_id = order.get("order_id", "")
            status = order.get("tracking_info_description", "")
            tracking = order.get("tracking_number", "")
            order_time = _fmt_ts(order.get("create_time"))

            carrier_name = detect_carrier(tracking)

            address = order.get("address", {}) or {}
            name = address.get("shipping_name", "")
            phone = address.get("shipping_phone", "")
            full_address = address.get("shipping_address", "")

            products = order.get("product_info", []) or []

            block = []
            block.append(f"📦 Đơn {index} :")

            # Thời gian đặt
            if order_time:
                block.append(f"⏱ Thời gian đặt hàng: {order_time}")

            block.append(f"🧾 Mã đơn hàng: {order_id}")

            # Địa chỉ
            if name or phone or full_address:
                block.append("\n🏠 ĐỊA CHỈ NHẬN HÀNG")
                if name:
                    block.append(name)
                if phone:
                    block.append(phone)
                if full_address:
                    block.append(full_address)

            # ===== SẢN PHẨM =====
            for i, p in enumerate(products[:max_products_per_order], start=1):

                pname = p.get("name", "")
                amount = p.get("amount", "")
                price = _fmt_money_from_api(p.get("order_price", 0))

                # 🔥 ƯU TIÊN link API trả sẵn
                link = (
                    p.get("link")
                    or p.get("product_url")
                    or p.get("url")
                )

                # Nếu không có link thì tự build
                if not link:
                    shop_id = (
                        p.get("shopid")
                        or p.get("shop_id")
                        or order.get("shopid")
                        or order.get("shop_id")
                    )
                    item_id = p.get("itemid") or p.get("item_id")
                    link = _build_shopee_link(shop_id, item_id)

                block.append(f"\n🎁 SẢN PHẨM {i}")
                block.append(f"Tên sản phẩm: {pname}")
                if link:
                    block.append(f"Liên kết: {link}")
                block.append(f"SL: {amount}")
                block.append(f"Giá: {price}")

            # ===== VẬN CHUYỂN =====
            if tracking:
                block.append("\n🚚 ĐƠN VỊ VẬN CHUYỂN")
                block.append(f"Đơn vị vận chuyển: {carrier_name}")
                block.append(f"Mã vận đơn: {tracking}")

            # ===== THANH TOÁN ĐÚNG TỔNG TIỀN =====
            payable_amount = (
                order.get("payable_amount")
                or order.get("total_amount")
                or order.get("total_price")
                or order.get("amount_to_pay")
                or order.get("cod_amount")
                or order.get("final_price")
            )

            if payable_amount:
                block.append(
                    f"💵 Vui lòng thanh toán {_fmt_money_from_api(payable_amount)} khi nhận hàng"
                )

            # ===== TÌNH TRẠNG LUÔN Ở CUỐI =====
            if status:
                block.append(f"📌 Tình trạng: {status}")

            block.append("\n" + "-" * 30 + "\n")
            text_blocks.append("\n".join(block))

        full_text = "\n".join(text_blocks)

        while len(full_text) > 3500:
            messages.append(full_text[:3500])
            full_text = full_text[3500:]

        messages.append(full_text)

    return messages

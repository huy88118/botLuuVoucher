import json
import html
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

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


def _safe_trim(s: Any, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[:n] + "..."


def detect_carrier(tracking_number: str) -> str:
    if not tracking_number:
        return ""
    t = tracking_number.strip().upper()

    if t.startswith("SPX"):
        return "Shopee Express"
    if t.startswith("GY") or t.startswith("GHN"):
        return "Giao Hàng Nhanh"
    if t.startswith("JNT"):
        return "J&T Express"
    if t.startswith("VNPOST"):
        return "VNPost"
    return "Không xác định"


def build_tracking_url(tracking_number: str) -> Optional[str]:
    if not tracking_number:
        return None
    t = tracking_number.strip().upper()

    if t.startswith("SPX"):
        return f"https://spx.vn/track?trackingNumber={t}"
    if t.startswith("GY") or t.startswith("GHN"):
        return f"https://donhang.ghn.vn/?order_code={t}"

    return None


def _esc(s: Any) -> str:
    """Escape text để dùng trong HTML parse_mode Telegram."""
    return html.escape("" if s is None else str(s), quote=True)


def format_orders_for_telegram(
    data: Dict[str, Any],
    max_orders_per_cookie: int = 10,
    max_products_per_order: int = 10,
) -> List[str]:
    messages: List[str] = []

    accounts = data.get("allOrderDetails", [])
    if not accounts:
        return ["❌ Không có dữ liệu đơn hàng."]

    for account in accounts:
        cookie = account.get("cookie", "") or ""
        orders = account.get("orderDetails", []) or []

        if not orders:
            messages.append(f"🍪 Cookie: {_esc(cookie[:20])}...<br>❌ Không có đơn hàng.")
            continue

        blocks: List[str] = []
        blocks.append(f"🍪 Cookie: {_esc(cookie[:20])}...")
        blocks.append(f"📌 Tổng {_esc(len(orders))} đơn hàng")

        for idx, order in enumerate(orders[:max_orders_per_cookie], start=1):
            order_id = order.get("order_id", "")
            status = order.get("tracking_info_description", "") or ""
            tracking = order.get("tracking_number", "") or ""
            carrier_name = detect_carrier(tracking)

            address = order.get("address", {}) or {}
            name = address.get("shipping_name", "")
            phone = address.get("shipping_phone", "")
            full_address = address.get("shipping_address", "")

            products = order.get("product_info", []) or []

            blocks.append(f"<br><b>ĐƠN HÀNG {idx} : 🧾 Oder ID: {_esc(order_id)}</b>")
            blocks.append("ℹ️ <b>THÔNG TIN</b>")
            if name:
                blocks.append(f"👤 Người nhận: {_esc(name)}")
            if phone:
                blocks.append(f"📞 SĐT: {_esc(phone)}")
            if full_address:
                blocks.append(f"📍 Địa chỉ: {_esc(full_address)}")
            blocks.append("")

            # Sản phẩm
            if products:
                if len(products) == 1:
                    p = products[0]
                    pname = _safe_trim(p.get("name", ""), 90)
                    blocks.append(f"🎁 Sản phẩm: {_esc(pname)}")
                else:
                    for i, p in enumerate(products[:max_products_per_order], start=1):
                        pname = _safe_trim(p.get("name", ""), 90)
                        blocks.append(f"🎁 Sản phẩm {i}: {_esc(pname)}")
            else:
                blocks.append("🎁 Sản phẩm: (không có dữ liệu)")

            blocks.append(f"🚛 Đơn vị vận chuyển: {_esc(carrier_name)}")

            # MVĐ + link tra cứu
            if tracking:
                blocks.append(f"📦 MVĐ: <code>{_esc(tracking)}</code>")

                track_url = build_tracking_url(tracking)
                if track_url:
                    blocks.append(f"🔗 Tra cứu: <a href='{_esc(track_url)}'>Mở trang tra cứu</a>")
            else:
                blocks.append("📦 MVĐ: (không có)")

            if status:
                blocks.append(f"📊 Trạng thái: {_esc(status)}")

            blocks.append("————————————————————--")

        blocks.append("<br>ℹ️ Tap vào MVĐ để copy nhanh.")

        full_text = "<br>".join(blocks).strip()

        while len(full_text) > 3500:
            messages.append(full_text[:3500])
            full_text = full_text[3500:]

        messages.append(full_text)

    return messages

import json
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


def _build_shopee_link(shop_id: Any, item_id: Any) -> Optional[str]:
    try:
        if shop_id and item_id:
            return f"https://shopee.vn/product/{int(shop_id)}/{int(item_id)}"
    except Exception:
        pass
    return None


def _safe_trim(s: Any, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[:n] + "..."


def detect_carrier(tracking_number: str) -> str:
    if not tracking_number:
        return ""

    t = tracking_number.upper()

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
    """Tạo link tra cứu theo hãng dựa trên prefix MVĐ."""
    if not tracking_number:
        return None

    t = tracking_number.strip().upper()

    # Shopee Express (ví dụ bạn đưa)
    if t.startswith("SPX"):
        return f"https://spx.vn/track?trackingNumber={t}"

    # GHN (bạn đưa)
    if t.startswith("GY") or t.startswith("GHN"):
        return f"https://donhang.ghn.vn/?order_code={t}"

    # Các hãng khác bạn có thể bổ sung sau
    return None


# ================= FORMATTER =================


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
        cookie = account.get("cookie", "")
        orders = account.get("orderDetails", []) or []

        if not orders:
            messages.append(f"🍪 Cookie: {cookie[:20]}...\n❌ Không có đơn hàng.")
            continue

        blocks: List[str] = []
        blocks.append(f"🍪 Cookie: {cookie[:20]}...")
        blocks.append(f"📌 Tổng {len(orders)} đơn hàng")

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

            blocks.append(f"\nĐƠN HÀNG {idx} : 🧾 Oder ID: {order_id}")

            # THÔNG TIN (dùng chữ đậm unicode tránh parse_mode)
            blocks.append("ℹ️ 𝐓𝐇Ô𝐍𝐆 𝐓𝐈𝐍")
            if name:
                blocks.append(f"👤 Người nhận: {name}")
            if phone:
                blocks.append(f"📞 SĐT: {phone}")
            if full_address:
                blocks.append(f"📍 Địa chỉ: {full_address}")
            blocks.append("")

            # Sản phẩm
            if products:
                if len(products) == 1:
                    p = products[0]
                    pname = _safe_trim(p.get("name", ""), 90)
                    blocks.append(f"🎁 Sản phẩm: {pname}")
                else:
                    for i, p in enumerate(products[:max_products_per_order], start=1):
                        pname = _safe_trim(p.get("name", ""), 90)
                        blocks.append(f"🎁 Sản phẩm {i}: {pname}")
            else:
                blocks.append("🎁 Sản phẩm: (không có dữ liệu)")

            # Đơn vị vận chuyển
            blocks.append(f"🚛Đơn vị vận chuyển : {carrier_name if carrier_name else 'Không xác định'}")

            # MVĐ + Link tra cứu
            if tracking:
                # MVĐ dạng code để tap/hold copy
                blocks.append(f"📦 MVĐ: `{tracking}`")

                track_url = build_tracking_url(tracking)
                if track_url:
                    blocks.append(f"🔗 Tra cứu: {track_url}")
            else:
                blocks.append("📦 MVĐ: (không có)")

            # Trạng thái
            if status:
                blocks.append(f"📊 Trạng thái: {status}")

            blocks.append("————————————————————--")

        blocks.append("\nℹ️ Tap vào MVĐ để copy nhanh.")

        full_text = "\n".join(blocks).strip()

        # Cắt an toàn theo giới hạn Telegram
        while len(full_text) > 3500:
            messages.append(full_text[:3500])
            full_text = full_text[3500:]

        messages.append(full_text)

    return messages

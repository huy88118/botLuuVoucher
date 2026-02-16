import requests
import json
from typing import List, Dict, Any, Optional, Tuple
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
        timeout=60
    )
    if response.status_code != 200:
        raise Exception(response.text)
    return response.json()


# ---------------- helpers ----------------

def _get(d: Dict[str, Any], keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, "", []):
            return d[k]
    return default


def _fmt_ts(ts: Any) -> str:
    """
    API có thể trả:
    - epoch seconds
    - epoch ms
    - string
    """
    if ts in (None, ""):
        return ""
    try:
        ts = int(ts)
        # ms -> seconds
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        # string
        return str(ts)


def _fmt_money_from_api(v: Any) -> str:
    """
    Code Tkinter của bạn: order_price / 100000
    Nên mình giữ chuẩn đó.
    """
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


def _safe_trim(s: Any, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[:n] + "…"


def _split_address_for_ui(full_address: Any) -> Tuple[str, str]:
    """
    Tách địa chỉ cho UI giống ảnh:
    - Dòng 1: phần địa chỉ chính
    - Dòng 2: phần tỉnh/thành (nếu có)
    """
    s = "" if full_address is None else str(full_address).strip()
    if not s:
        return "", ""

    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2:
        main = ", ".join(parts[:-1]).strip()
        city = parts[-1].strip()
        return main, city

    return s, ""


def _detect_carrier_from_tracking(tracking_id: Any) -> str:
    """
    Tự nhận diện đơn vị vận chuyển từ mã vận đơn (MVĐ).
    Theo ví dụ bạn đưa:
    - SPX... / SPXVN... => Shopee Express
    - GY...            => Giao Hàng Nhanh

    Nếu không nhận diện được thì trả "" để fallback sang carrier từ API.
    """
    t = "" if tracking_id is None else str(tracking_id).strip().upper()
    if not t:
        return ""

    # Ưu tiên prefix dài hơn trước
    prefix_map = [
        ("SPXVN", "Shopee Express"),
        ("SPX", "Shopee Express"),
        ("GY", "Giao Hàng Nhanh"),
    ]

    for pref, name in prefix_map:
        if t.startswith(pref):
            return name

    return ""


# ---------------- formatter ----------------

def format_orders_for_telegram(
    data: Dict[str, Any],
    max_orders_per_cookie: int = 5,
    max_products_per_order: int = 5,
) -> List[str]:
    """
    UI giống ảnh:
    - 🍪 Cookie + Tổng đơn
    - 📌 ĐƠN HÀNG i :  Oder ID
    - ℹ️ THÔNG TIN (Người nhận / SDT / Địa chỉ / TP)
    - 🎁 Sản phẩm (nếu nhiều sp -> Sản phẩm 1,2,...)
    - 🚚 Đơn vị vận chuyển
    - 🧾 MVD: `...` (để dễ bấm copy)
    - 📊 Trạng thái
    - Footer: ℹ️ Tap vào MVD để copy nhanh.
    """
    messages: List[str] = []

    accounts = data.get("allOrderDetails", [])
    if not accounts:
        return ["❌ Không có dữ liệu đơn hàng. (API trả rỗng)"]

    for account in accounts:
        cookie = account.get("cookie", "")
        orders = account.get("orderDetails", []) or []
        if not orders:
            messages.append(f"🍪 Cookie: `{cookie[:20]}...`\n❌ Không có đơn hàng.")
            continue

        blocks: List[str] = []
        header = f"🍪 Cookie: `{cookie[:20]}...`\n📦 Tổng đơn: {len(orders)}"
        blocks.append(header)

        shown = 0
        for idx, order in enumerate(orders, start=1):
            if shown >= max_orders_per_cookie:
                break

            # ----- basic order fields -----
            order_id = _get(order, ["order_id", "orderid", "id"], "")
            status = _get(order, ["tracking_info_description", "status_description", "status", "order_status"], "")
            tracking = _get(order, ["tracking_number", "tracking_no", "tracking"], "")
            # order_time giữ lại nếu bạn muốn bật hiển thị (comment phía dưới)
            order_time = _fmt_ts(_get(order, ["create_time", "order_time", "ctime", "created_at"], ""))

            # ----- address -----
            address = order.get("address", {}) or {}
            name = _get(address, ["shipping_name", "name", "receiver_name"], "")
            phone = _get(address, ["shipping_phone", "phone", "receiver_phone"], "")
            full_address = _get(address, ["shipping_address", "address", "full_address"], "")
            addr_main, addr_city = _split_address_for_ui(full_address)

            # ----- shipping -----
            shipping = order.get("shipping", {}) or {}
            carrier_api = _get(shipping, ["shipping_carrier", "carrier"], "") or _get(order, ["shipping_carrier"], "")
            tracking_id = _get(order, ["tracking_number"], tracking)

            # Auto-detect carrier from tracking (ưu tiên độ chính xác theo MVĐ)
            carrier_detected = _detect_carrier_from_tracking(tracking_id)
            carrier = carrier_detected or carrier_api  # nếu detect được thì dùng detect, không thì fallback API

            # ----- products -----
            products = order.get("product_info", []) or order.get("products", []) or []
            prod_lines: List[str] = []

            for p in products[:max_products_per_order]:
                pname = _safe_trim(_get(p, ["name", "product_name", "title"], ""), 160)
                variation = _safe_trim(_get(p, ["model_name", "variation", "classification", "model"], ""), 80)

                # UI gọn như ảnh: gộp tên + phân loại
                line = pname
                if variation:
                    line += f" [{variation}]"

                prod_lines.append(line)

            if len(products) > max_products_per_order:
                prod_lines.append(f"(… +{len(products) - max_products_per_order} sản phẩm khác)")

            # ----- build UI block like screenshot -----
            block_parts: List[str] = []


            # Title order (tách riêng Order ID ra 1 dòng)
            block_parts.append(f"\n📌 ĐƠN HÀNG {idx} :")

            if order_id:
               block_parts.append(f"🧾 Order ID: {order_id}")

        
            # Info section
            block_parts.append("ℹ️ THÔNG TIN")
            if name:
                block_parts.append(f"👤 Người nhận: {name}")
            if phone:
                block_parts.append(f"📞 SDT: {phone}")
            if addr_main:
                block_parts.append(f"📍 Địa chỉ: {addr_main}")
            if addr_city:
                prefix = "TP. " if not addr_city.lower().startswith(("tp", "thành phố", "tỉnh")) else ""
                block_parts.append(f"{prefix}{addr_city}")

            # Products section
            if prod_lines:
                if len(prod_lines) == 1:
                    block_parts.append(f"\n🎁 Sản phẩm: {prod_lines[0]}")
                else:
                    block_parts.append("\n🎁 Sản phẩm:")
                    for i, pl in enumerate(prod_lines, start=1):
                        block_parts.append(f"Sản phẩm {i} : {pl}")

            # Shipping + tracking + status (đúng thứ tự như ảnh)
            if carrier:
                block_parts.append(f"\n🚚 Đơn vị vận chuyển: {carrier}")
            if tracking_id:
                block_parts.append(f"🧾 MVD: `{tracking_id}`")
            if status:
                block_parts.append(f"📊 Trạng thái: {status}")

            # Nếu bạn muốn hiện "Thời gian đặt hàng" thì bật dòng dưới (để cuối cho gọn)
            # if order_time:
            #     block_parts.append(f"⏱ Thời gian đặt hàng: {order_time}")

            block_text = "\n".join([x for x in block_parts if x]).strip()
            blocks.append(block_text)
            # Nếu có từ 2 đơn trở lên thì thêm gạch phân tách giữa các đơn (trừ đơn cuối đang hiển thị)
            if len(orders) > 1 and shown < max_orders_per_cookie and idx < min(len(orders), max_orders_per_cookie):
                blocks.append("---------------------------------------")
            else:
                blocks.append("")  # giữ dòng trống cho đẹp nếu chỉ có 1 đơn hoặc là đơn cuối
            shown += 1

        if len(orders) > shown:
            blocks.append(f"… (ẩn {len(orders) - shown} đơn, tăng giới hạn nếu muốn)")

        blocks.append("ℹ️ Tap vào MVD để copy nhanh.")

        # split into multiple telegram messages if too long
        full_text = "\n".join(blocks).strip()
        while len(full_text) > 3500:
            messages.append(full_text[:3500])
            full_text = full_text[3500:]
        messages.append(full_text)

    return messages

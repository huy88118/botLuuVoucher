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

# ---------------- formatter ----------------

def format_orders_for_telegram(
    data: Dict[str, Any],
    max_orders_per_cookie: int = 5,
    max_products_per_order: int = 5,
) -> List[str]:
    """
    Format gần giống ảnh:
    - Tình trạng + dự kiến nhận
    - Mã đơn + thời gian đặt
    - Địa chỉ nhận
    - Sản phẩm (tên, phân loại, link)
    - Đơn vị vận chuyển + MVĐ
    - Note thanh toán khi nhận (nếu tính được)
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
        for order in orders:
            if shown >= max_orders_per_cookie:
                break

            # ----- basic order fields -----
            order_id = _get(order, ["order_id", "orderid", "id"], "")
            status = _get(order, ["tracking_info_description", "status_description", "status", "order_status"], "")
            tracking = _get(order, ["tracking_number", "tracking_no", "tracking"], "")
            order_time = _fmt_ts(_get(order, ["create_time", "order_time", "ctime", "created_at"], ""))

            # delivery estimation (nếu có)
            eta = _get(order, ["estimated_delivery", "delivery_estimate", "delivery_window", "shipping_eta"], "")
            eta_text = ""
            if eta:
                eta_text = f"\nTình trạng: {eta}"

            # ----- address -----
            address = order.get("address", {}) or {}
            name = _get(address, ["shipping_name", "name", "receiver_name"], "")
            phone = _get(address, ["shipping_phone", "phone", "receiver_phone"], "")
            full_address = _get(address, ["shipping_address", "address", "full_address"], "")

            # ----- shipping -----
            shipping = order.get("shipping", {}) or {}
            carrier = _get(shipping, ["shipping_carrier", "carrier"], "") or _get(order, ["shipping_carrier"], "")
            tracking_id = _get(order, ["tracking_number"], tracking)

            # ----- products -----
            products = order.get("product_info", []) or order.get("products", []) or []
            prod_lines: List[str] = []
            cod_total = 0.0
            cod_has_value = False

            for p in products[:max_products_per_order]:
                pname = _safe_trim(_get(p, ["name", "product_name", "title"], ""), 120)
                variation = _safe_trim(_get(p, ["model_name", "variation", "classification", "model"], ""), 80)
                amount = _get(p, ["amount", "qty", "quantity"], "")
                price_raw = _get(p, ["order_price", "price", "item_price"], None)

                # link
                shop_id = _get(p, ["shopid", "shop_id"], None) or _get(order, ["shopid", "shop_id"], None)
                item_id = _get(p, ["itemid", "item_id"], None)
                link = _get(p, ["link", "url", "product_url"], None) or _build_shopee_link(shop_id, item_id)

                line = f"🎁 Tên sản phẩm: {pname}"
                if variation:
                    line += f"\nPhân loại: {variation}"
                if link:
                    line += f"\nLiên kết: {link}"
                if amount not in ("", None):
                    line += f"\nSL: {amount}"
                if price_raw is not None:
                    line += f"\nGiá: {_fmt_money_from_api(price_raw)}"
                    try:
                        cod_total += float(price_raw)
                        cod_has_value = True
                    except Exception:
                        pass

                prod_lines.append(line)

            if len(products) > max_products_per_order:
                prod_lines.append(f"(… +{len(products) - max_products_per_order} sản phẩm khác)")

            # COD / payable
            payable_line = ""
            # nếu API có field riêng thì ưu tiên
            payable_raw = _get(order, ["cod_amount", "payable_amount", "total_cod", "amount_to_pay"], None)
            if payable_raw is not None:
                payable_line = f"💵 Vui lòng thanh toán {_fmt_money_from_api(payable_raw)} khi nhận hàng"
            elif cod_has_value:
                payable_line = f"💵 Vui lòng thanh toán {_fmt_money_from_api(cod_total)} khi nhận hàng"

            # ----- build message block like screenshot -----
            block_parts: List[str] = []

            # Tình trạng + ETA
            if status:
                block_parts.append(f"📌 Tình trạng: {status}")
            if eta_text:
                block_parts.append(f"📌 {eta_text.replace('Tình trạng: ', 'Ngày nhận dự kiến: ')}")

            if order_id:
                block_parts.append(f"🧾 Mã đơn hàng: {order_id}")
            if order_time:
                block_parts.append(f"⏱ Thời gian đặt hàng: {order_time}")

            # Address section
            if name or phone or full_address:
                block_parts.append("\n🏠 ĐỊA CHỈ NHẬN HÀNG")
                if name:
                    block_parts.append(f"{name}")
                if phone:
                    block_parts.append(f"{phone}")
                if full_address:
                    block_parts.append(full_address)

            # Product sections
            if prod_lines:
                for i, pl in enumerate(prod_lines, start=1):
                    block_parts.append(f"\n🎁 SẢN PHẨM {i}\n{pl}")

            # Shipping section
            if carrier or tracking_id:
                block_parts.append("\n🚚 ĐƠN VỊ VẬN CHUYỂN")
                if carrier:
                    block_parts.append(f"Đơn vị vận chuyển: {carrier}")
                if tracking_id:
                    block_parts.append(f"Mã vận đơn: {tracking_id}")

            if payable_line:
                block_parts.append(f"\n{payable_line}")

            # divider
            block_text = "\n".join([x for x in block_parts if x is not None and x != ""]).strip()
            blocks.append(block_text)
            blocks.append("—" * 20)

            shown += 1

        if len(orders) > shown:
            blocks.append(f"… (ẩn {len(orders) - shown} đơn, tăng giới hạn nếu muốn)")

        # split into multiple telegram messages if too long
        full_text = "\n".join(blocks).strip()
        while len(full_text) > 3500:
            messages.append(full_text[:3500])
            full_text = full_text[3500:]
        messages.append(full_text)

    return messages

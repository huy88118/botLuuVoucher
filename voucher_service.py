import requests
import json
import os
from typing import Dict, Any, List

BASE_URL = "https://us-central1-get-feedback-a0119.cloudfunctions.net/app/api/shopee/saveVoucherShopee"

ERROR_MAP = {
    "0": "Lưu thành công",
    "5": "Đã lưu trước đó",
    "14": "Voucher không hợp lệ / hết lượt / sai điều kiện",
    "19": "Cookie hết hạn / chưa đăng nhập"
}

def load_vouchers(path: str = "vouchers.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def _save_one(cookie: str, voucher: Dict[str, Any]) -> str:
    """Lưu 1 voucher, trả về 1 dòng log (giữ nguyên style của bạn)."""
    payload = {
        "cookie": cookie,
        "voucher_promotionid": voucher["voucher_promotionid"],
        "signature": voucher["signature"],
        "voucher_code": voucher["voucher_code"],
    }

    res = requests.post(BASE_URL, json=payload, timeout=20)

    try:
        data = res.json()
    except Exception:
        return f"❌ {voucher['voucher_code']} : Response không hợp lệ"

    error_code = str(data.get("error", ""))
    if error_code == "0":
        return f"✅ {voucher['voucher_code']} : {ERROR_MAP['0']}"
    if error_code == "5":
        return f"⚠ {voucher['voucher_code']} : {ERROR_MAP['5']}"

    message = data.get("message")
    if message:
        return f"❌ {voucher['voucher_code']} : {message}"
    if error_code in ERROR_MAP:
        return f"❌ {voucher['voucher_code']} : {ERROR_MAP[error_code]}"
    return f"❌ {voucher['voucher_code']} : {error_code}"

# ================== API MỚI: lưu 1 voucher (dùng cho bot menu chọn mã) ==================
def save_voucher_with_cookie(cookie: str, voucher: Dict[str, Any]) -> str:
    """
    cookie: 1 cookie string
    voucher: object lấy từ vouchers.json
    Trả về text log + tổng kết (giống format bạn đang dùng).
    """
    success_count = 0
    existed_count = 0
    error_count = 0

    logs = []

    try:
        line = _save_one(cookie, voucher)
        logs.append(line)

        if line.startswith("✅"):
            success_count += 1
        elif line.startswith("⚠"):
            existed_count += 1
        else:
            error_count += 1

    except Exception as e:
        error_count += 1
        logs.append(f"❌ {voucher.get('voucher_code','VOUCHER')} : {str(e)}")

    logs.append("\n----- TỔNG KẾT -----")
    logs.append(f"Thành công: {success_count}")
    logs.append(f"Đã lưu trước đó: {existed_count}")
    logs.append(f"Lỗi: {error_count}")
    logs.append("--------------------")

    return "\n".join(logs)

# ================== API CŨ: lưu tất cả voucher trong JSON (giữ lại để tương thích) ==================
def save_vouchers_with_cookie(cookie: str) -> str:
    vouchers = load_vouchers()

    if not vouchers:
        return "❌ Không có voucher trong vouchers.json"

    success_count = 0
    existed_count = 0
    error_count = 0
    logs = []

    for voucher in vouchers:
        try:
            line = _save_one(cookie, voucher)
            logs.append(line)

            if line.startswith("✅"):
                success_count += 1
            elif line.startswith("⚠"):
                existed_count += 1
            else:
                error_count += 1

        except Exception as e:
            error_count += 1
            logs.append(f"❌ {voucher.get('voucher_code','VOUCHER')} : {str(e)}")

    logs.append("\n----- TỔNG KẾT -----")
    logs.append(f"Thành công: {success_count}")
    logs.append(f"Đã lưu trước đó: {existed_count}")
    logs.append(f"Lỗi: {error_count}")
    logs.append("--------------------")

    return "\n".join(logs)

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

def _post_save(cookie: str, voucher: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "cookie": cookie,
        "voucher_promotionid": voucher["voucher_promotionid"],
        "signature": voucher["signature"],
        "voucher_code": voucher["voucher_code"]
    }
    res = requests.post(BASE_URL, json=payload, timeout=20)
    try:
        return res.json()
    except Exception:
        return {"error": "invalid_json"}

def _format_line(voucher_code: str, data: Dict[str, Any]) -> str:
    error_code = str(data.get("error", ""))

    if error_code == "0":
        return f"✅ {voucher_code} : {ERROR_MAP['0']}"
    if error_code == "5":
        return f"⚠ {voucher_code} : {ERROR_MAP['5']}"

    if error_code == "invalid_json":
        return f"❌ {voucher_code} : Response không hợp lệ"

    message = data.get("message")
    if message:
        return f"❌ {voucher_code} : {message}"
    if error_code in ERROR_MAP:
        return f"❌ {voucher_code} : {ERROR_MAP[error_code]}"
    return f"❌ {voucher_code} : {error_code}"

def save_one_voucher_with_cookie(cookie: str, voucher: Dict[str, Any]) -> str:
    """Lưu 1 voucher được chọn."""
    voucher_code = voucher.get("voucher_code", "VOUCHER")

    success_count = 0
    existed_count = 0
    error_count = 0
    logs = []

    try:
        data = _post_save(cookie, voucher)
        line = _format_line(voucher_code, data)
        logs.append(line)

        if line.startswith("✅"):
            success_count += 1
        elif line.startswith("⚠"):
            existed_count += 1
        else:
            error_count += 1
    except Exception as e:
        error_count += 1
        logs.append(f"❌ {voucher_code} : {str(e)}")

    logs.append("\n----- TỔNG KẾT -----")
    logs.append(f"Thành công: {success_count}")
    logs.append(f"Đã lưu trước đó: {existed_count}")
    logs.append(f"Lỗi: {error_count}")
    logs.append("--------------------")
    return "\n".join(logs)

def save_all_vouchers_with_cookie(cookie: str) -> str:
    """Lưu tất cả voucher trong vouchers.json (giữ output như cũ)."""
    vouchers = load_vouchers()
    if not vouchers:
        return "❌ Không có voucher trong vouchers.json"

    success_count = 0
    existed_count = 0
    error_count = 0
    logs = []

    for voucher in vouchers:
        voucher_code = voucher.get("voucher_code", "VOUCHER")
        try:
            data = _post_save(cookie, voucher)
            line = _format_line(voucher_code, data)
            logs.append(line)

            if line.startswith("✅"):
                success_count += 1
            elif line.startswith("⚠"):
                existed_count += 1
            else:
                error_count += 1
        except Exception as e:
            error_count += 1
            logs.append(f"❌ {voucher_code} : {str(e)}")

    logs.append("\n----- TỔNG KẾT -----")
    logs.append(f"Thành công: {success_count}")
    logs.append(f"Đã lưu trước đó: {existed_count}")
    logs.append(f"Lỗi: {error_count}")
    logs.append("--------------------")
    return "\n".join(logs)

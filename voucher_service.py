import requests
import json
import os

BASE_URL = "https://us-central1-get-feedback-a0119.cloudfunctions.net/app/api/shopee/saveVoucherShopee"


# ================= LOAD VOUCHERS =================

def load_vouchers():
    if not os.path.exists("vouchers.json"):
        return []

    with open("vouchers.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ================= MAIN SERVICE =================

def save_vouchers_with_cookie(cookie: str):

    vouchers = load_vouchers()

    if not vouchers:
        return "❌ Không có voucher trong vouchers.json"

    success_count = 0
    existed_count = 0
    error_count = 0

    logs = []

    error_map = {
        "0": "Lưu thành công",
        "5": "Đã lưu trước đó",
        "14": "Voucher không hợp lệ / hết lượt / sai điều kiện",
        "19": "Cookie hết hạn / chưa đăng nhập"
    }

    for voucher in vouchers:

        payload = {
            "cookie": cookie,
            "voucher_promotionid": voucher["voucher_promotionid"],
            "signature": voucher["signature"],
            "voucher_code": voucher["voucher_code"]
        }

        try:
            res = requests.post(BASE_URL, json=payload, timeout=20)

            try:
                data = res.json()
            except:
                error_count += 1
                logs.append(f"❌ {voucher['voucher_code']} : Response không hợp lệ")
                continue

            error_code = str(data.get("error", ""))

            # ===== SUCCESS =====
            if error_code == "0":
                success_count += 1
                logs.append(f"✅ {voucher['voucher_code']} : {error_map['0']}")

            # ===== EXISTED =====
            elif error_code == "5":
                existed_count += 1
                logs.append(f"⚠ {voucher['voucher_code']} : {error_map['5']}")

            # ===== OTHER ERROR =====
            else:
                error_count += 1

                message = data.get("message")

                if message:
                    logs.append(f"❌ {voucher['voucher_code']} : {message}")
                elif error_code in error_map:
                    logs.append(f"❌ {voucher['voucher_code']} : {error_map[error_code]}")
                else:
                    logs.append(f"❌ {voucher['voucher_code']} : {error_code}")

        except Exception as e:
            error_count += 1
            logs.append(f"❌ {voucher['voucher_code']} : {str(e)}")

    # ================= SUMMARY =================

    logs.append("\n----- TỔNG KẾT -----")
    logs.append(f"Thành công: {success_count}")
    logs.append(f"Đã lưu trước đó: {existed_count}")
    logs.append(f"Lỗi: {error_count}")
    logs.append("--------------------")

    return "\n".join(logs)

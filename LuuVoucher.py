import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
import json
import os
import threading

BASE_URL = "https://us-central1-get-feedback-a0119.cloudfunctions.net/app/api/shopee/saveVoucherShopee"


class VoucherTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Autopee - Lưu Voucher Shopee")
        self.root.geometry("540x480")
        self.root.resizable(False, False)

        self.vouchers = []
        self.check_vars = []

        self.load_vouchers_file()
        self.build_ui()

    # ================= UI =================

    def build_ui(self):

        tk.Label(self.root, text="Danh sách Cookie (mỗi cookie 1 dòng):",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 0))

        self.cookie_text = tk.Text(self.root, height=4)
        self.cookie_text.pack(fill="x", padx=8, pady=(0, 6))

        header_frame = tk.Frame(self.root)
        header_frame.pack(fill="x", padx=8)

        tk.Label(header_frame, text="Danh sách Voucher",
                 font=("Arial", 9, "bold")).pack(side="left")

        tk.Button(header_frame,
                  text="Add",
                  width=7,
                  bg="#2196F3",
                  fg="white",
                  activebackground="#1976D2",
                  relief="flat",
                  command=self.open_add_window).pack(side="right")

        self.voucher_frame = tk.Frame(self.root)
        self.voucher_frame.pack(fill="x", padx=8, pady=4)

        self.refresh_voucher_list()

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=8, pady=6)

        tk.Button(btn_frame, text="LƯU CHỌN",
                  height=1,
                  bg="#ff5722",
                  fg="white",
                  relief="flat",
                  command=self.save_selected).pack(side="left", expand=True, fill="x", padx=3)

        tk.Button(btn_frame, text="LƯU TẤT CẢ",
                  height=1,
                  bg="#ff9800",
                  fg="white",
                  relief="flat",
                  command=self.save_all).pack(side="left", expand=True, fill="x", padx=3)

        tk.Button(btn_frame,
                  text="Clear",
                  width=7,
                  bg="#607D8B",
                  fg="white",
                  activebackground="#546E7A",
                  relief="flat",
                  command=self.clear_log).pack(side="right")

        tk.Label(self.root, text="Log:",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=8)

        self.log_text = tk.Text(self.root, height=10)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ================= File =================

    def load_vouchers_file(self):
        if os.path.exists("vouchers.json"):
            with open("vouchers.json", "r", encoding="utf-8") as f:
                self.vouchers = json.load(f)
        else:
            self.vouchers = []

    def save_vouchers_file(self):
        with open("vouchers.json", "w", encoding="utf-8") as f:
            json.dump(self.vouchers, f, indent=4, ensure_ascii=False)

    # ================= Voucher List =================

    def refresh_voucher_list(self):
        for widget in self.voucher_frame.winfo_children():
            widget.destroy()

        self.check_vars = []

        for index, v in enumerate(self.vouchers):
            var = tk.BooleanVar()
            self.check_vars.append(var)

            name = v.get("display_name", v.get("voucher_code"))

            cb = tk.Checkbutton(
                self.voucher_frame,
                text=name,
                variable=var,
                anchor="w"
            )
            cb.pack(fill="x")

            cb.bind("<Button-3>", lambda e, i=index: self.show_context_menu(e, i))

    # ================= Context Menu =================

    def show_context_menu(self, event, index):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self.rename_voucher(index))
        menu.add_command(label="Xóa", command=lambda: self.delete_voucher(index))
        menu.post(event.x_root, event.y_root)

    def rename_voucher(self, index):
        voucher = self.vouchers[index]

        new_name = simpledialog.askstring(
            "Rename",
            "Nhập tên mới:",
            initialvalue=voucher.get("display_name", voucher["voucher_code"])
        )

        if new_name:
            voucher["display_name"] = new_name
            self.save_vouchers_file()
            self.refresh_voucher_list()

    def delete_voucher(self, index):
        confirm = messagebox.askyesno("Xóa", "Bạn có chắc muốn xóa voucher này?")
        if confirm:
            self.vouchers.pop(index)
            self.save_vouchers_file()
            self.refresh_voucher_list()

    # ================= Add Voucher =================

    def open_add_window(self):
        add_win = tk.Toplevel(self.root)
        add_win.title("Thêm Voucher")
        add_win.geometry("300x210")
        add_win.resizable(False, False)

        tk.Label(add_win, text="Mã voucher").pack(pady=(8, 0))
        code_entry = tk.Entry(add_win)
        code_entry.pack(fill="x", padx=15)

        tk.Label(add_win, text="Promotion ID").pack(pady=(6, 0))
        promo_entry = tk.Entry(add_win)
        promo_entry.pack(fill="x", padx=15)

        tk.Label(add_win, text="Signature").pack(pady=(6, 0))
        sign_entry = tk.Entry(add_win)
        sign_entry.pack(fill="x", padx=15)

        def save_new():
            code = code_entry.get().strip()
            promo = promo_entry.get().strip()
            sign = sign_entry.get().strip()

            if not code or not promo or not sign:
                messagebox.showerror("Lỗi", "Nhập đầy đủ thông tin")
                return

            new_voucher = {
                "voucher_code": code,
                "voucher_promotionid": promo,
                "signature": sign,
                "display_name": code
            }

            self.vouchers.append(new_voucher)
            self.save_vouchers_file()
            self.refresh_voucher_list()
            add_win.destroy()

        tk.Button(add_win,
                  text="Thêm",
                  bg="#4CAF50",
                  fg="white",
                  relief="flat",
                  command=save_new).pack(pady=12)

    # ================= Thread Start =================

    def save_selected(self):
        selected = [
            self.vouchers[i]
            for i, var in enumerate(self.check_vars)
            if var.get()
        ]

        if not selected:
            messagebox.showwarning("Chọn voucher", "Chưa tích chọn voucher nào")
            return

        threading.Thread(target=self.run_process, args=(selected,), daemon=True).start()

    def save_all(self):
        threading.Thread(target=self.run_process, args=(self.vouchers,), daemon=True).start()

    # ================= Main Process =================

    def run_process(self, vouchers):

        cookies = self.cookie_text.get("1.0", tk.END).strip().split("\n")
        cookies = [c.strip() for c in cookies if c.strip()]

        if not cookies:
            self.safe_log("❌ Chưa nhập cookie")
            return

        success_count = 0
        existed_count = 0
        error_count = 0

        error_map = {
            "0": "Lưu thành công",
            "5": "Đã lưu trước đó",
            "14": "Voucher không hợp lệ / hết lượt / sai điều kiện"
        }

        for voucher in vouchers:
            for cookie in cookies:

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
                        self.safe_log(f"❌ {voucher['voucher_code']} : Response không hợp lệ")
                        continue

                    error_code = str(data.get("error", ""))

                    if error_code == "0":
                        success_count += 1
                        self.safe_log(f"✅ {voucher['voucher_code']} : {error_map['0']}")

                    elif error_code == "5":
                        existed_count += 1
                        self.safe_log(f"⚠ {voucher['voucher_code']} : {error_map['5']}")

                    else:
                        error_count += 1
                        message = data.get("message")

                        if message:
                            self.safe_log(f"❌ {voucher['voucher_code']} : {message}")
                        elif error_code in error_map:
                            self.safe_log(f"❌ {voucher['voucher_code']} : {error_map[error_code]}")
                        else:
                            self.safe_log(f"❌ {voucher['voucher_code']} : {error_code}")

                except Exception as e:
                    error_count += 1
                    self.safe_log(f"❌ {voucher['voucher_code']} : {str(e)}")

        # ===== TỔNG KẾT =====
        self.safe_log("----- TỔNG KẾT -----")

        if success_count > 0:
            self.safe_log(f"Thành công: {success_count}")

        if existed_count > 0:
            self.safe_log(f"Đã lưu trước đó: {existed_count}")

        if error_count > 0:
            self.safe_log(f"Lỗi: {error_count}")

        self.safe_log("--------------------\n")

    # ================= Helpers =================

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def safe_log(self, text):
        self.root.after(0, lambda: self.log(text))


if __name__ == "__main__":
    root = tk.Tk()
    app = VoucherTool(root)
    root.mainloop()

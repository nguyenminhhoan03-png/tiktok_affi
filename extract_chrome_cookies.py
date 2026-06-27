#!/usr/bin/env python3
"""
extract_chrome_cookies.py
=========================
Đọc cookies Google/Gemini thẳng từ Chrome thật trên máy.
KHÔNG cần đăng nhập lại — dùng phiên Chrome đã đăng nhập sẵn.

Chạy:
    python3 extract_chrome_cookies.py

Lưu ý: Hãy đóng Chrome trước khi chạy (hoặc script sẽ copy DB tạm).
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# ── Cấu hình ──────────────────────────────────────────────────────────────────
OUTPUT_PATH = "./cookies/google_cookies.json"

# Các domain cần lấy cookie (Google login + Gemini)
TARGET_DOMAINS = [
    ".google.com",
    "google.com",
    ".gemini.google.com",
    "gemini.google.com",
    ".accounts.google.com",
    "accounts.google.com",
    ".googleapis.com",
]

# Đường dẫn Chrome profile trên Linux
CHROME_PROFILE_CANDIDATES = [
    Path.home() / ".config/google-chrome/Default",
    Path.home() / ".config/google-chrome/Profile 1",
    Path.home() / ".config/chromium/Default",
    Path.home() / "snap/chromium/common/chromium/Default",
]
# ──────────────────────────────────────────────────────────────────────────────


def find_chrome_cookies_db() -> Path:
    """Tìm file Cookies của Chrome."""
    for profile in CHROME_PROFILE_CANDIDATES:
        cookies_file = profile / "Cookies"
        if cookies_file.exists():
            print(f"✅ Tìm thấy Chrome profile: {profile}")
            return cookies_file
    raise FileNotFoundError(
        "❌ Không tìm thấy file Cookies của Chrome!\n"
        "Hãy kiểm tra Chrome đã cài và đã đăng nhập Google chưa.\n"
        f"Các đường dẫn đã thử: {[str(p / 'Cookies') for p in CHROME_PROFILE_CANDIDATES]}"
    )


def decrypt_cookie_value(encrypted_value: bytes) -> str:
    """
    Giải mã cookie Chrome trên Linux.
    Chrome Linux dùng AES-128-CBC với key từ PBKDF2(password, saltysalt, 1, 16).
    Password thường là 'peanuts' (khi không có keyring) hoặc từ GNOME Keyring.
    """
    if not encrypted_value:
        return ""

    # Nếu không encrypt (không có prefix v10/v11)
    if not encrypted_value.startswith(b"v10") and not encrypted_value.startswith(b"v11"):
        try:
            return encrypted_value.decode("utf-8")
        except Exception:
            return ""

    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2

        # Thử key "peanuts" (Chrome Linux default khi không có keyring)
        password = "peanuts"
        salt = b"saltysalt"
        key = PBKDF2(password, salt, dkLen=16, count=1)

        # Bỏ qua 3 bytes prefix "v10" hoặc "v11"
        raw = encrypted_value[3:]
        iv = b" " * 16  # Chrome Linux dùng space IV

        cipher = AES.new(key, AES.MODE_CBC, IV=iv)
        decrypted = cipher.decrypt(raw)

        # Xóa padding
        padding = decrypted[-1]
        decrypted = decrypted[:-padding]

        return decrypted.decode("utf-8")

    except ImportError:
        # pycryptodome chưa cài — trả về empty string
        print("⚠️  pycryptodome chưa cài, cookie sẽ không được giải mã.")
        print("   Cài bằng: pip install pycryptodome")
        return ""
    except Exception as e:
        return ""


def read_cookies_from_chrome(cookies_db: Path) -> list[dict]:
    """Đọc cookies từ SQLite database của Chrome, lọc theo domain Google."""

    # Copy DB sang temp vì Chrome lock file
    tmp_dir = tempfile.mkdtemp()
    tmp_db = os.path.join(tmp_dir, "Cookies")
    shutil.copy2(str(cookies_db), tmp_db)

    cookies = []
    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Lấy tất cả cookies của các domain Google
        domain_placeholders = ",".join("?" * len(TARGET_DOMAINS))
        cursor.execute(
            f"""
            SELECT
                host_key,
                name,
                encrypted_value,
                value,
                path,
                expires_utc,
                is_secure,
                is_httponly,
                samesite
            FROM cookies
            WHERE host_key IN ({domain_placeholders})
            ORDER BY host_key, name
            """,
            TARGET_DOMAINS,
        )

        rows = cursor.fetchall()
        conn.close()

        print(f"📦 Tìm thấy {len(rows)} cookies từ các domain Google")

        for row in rows:
            # Giải mã value
            if row["encrypted_value"]:
                value = decrypt_cookie_value(row["encrypted_value"])
            else:
                value = row["value"] or ""

            # Convert Chrome's UTC timestamp to Unix timestamp
            # Chrome dùng microseconds từ 1601-01-01, Unix dùng seconds từ 1970-01-01
            expires_utc = row["expires_utc"]
            if expires_utc and expires_utc > 0:
                # Chrome epoch → Unix epoch: subtract 11644473600 seconds (in microseconds)
                expires_unix = (expires_utc / 1_000_000) - 11_644_473_600
            else:
                expires_unix = -1  # Session cookie

            # SameSite mapping
            samesite_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
            samesite = samesite_map.get(row["samesite"], "None")

            # Format theo Playwright cookie format
            cookie = {
                "name": row["name"],
                "value": value,
                "domain": row["host_key"],
                "path": row["path"] or "/",
                "expires": expires_unix,
                "httpOnly": bool(row["is_httponly"]),
                "secure": bool(row["is_secure"]),
                "sameSite": samesite,
            }
            cookies.append(cookie)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return cookies


def main():
    print("🍪 Chrome Cookie Extractor cho Google/Gemini")
    print("=" * 50)

    try:
        # 1. Tìm Chrome cookies DB
        cookies_db = find_chrome_cookies_db()

        # 2. Đọc và giải mã cookies
        cookies = read_cookies_from_chrome(cookies_db)

        if not cookies:
            print("❌ Không tìm thấy cookie Google nào!")
            print("   Hãy chắc chắn rằng bạn đã đăng nhập Google trong Chrome thật.")
            sys.exit(1)

        # 3. Lưu ra file
        output_path = Path(OUTPUT_PATH)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Đã lưu {len(cookies)} cookies vào: {output_path}")
        print("🚀 Bây giờ có thể chạy: python3 main.py run-pipeline")

    except FileNotFoundError as e:
        print(f"\n{e}")
        sys.exit(1)
    except PermissionError:
        print("\n❌ Lỗi quyền truy cập file Cookies!")
        print("   👉 Hãy ĐÓNG Chrome trước khi chạy script này.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Lỗi không xác định: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

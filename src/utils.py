import json
import os
from pathlib import Path
from loguru import logger


def load_config(config_path: str = "config.json") -> dict:
    """Load cấu hình từ file config.json"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cookies(cookies_path: str) -> list:
    """Load cookies từ file JSON"""
    path = Path(cookies_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file cookies: {cookies_path}\n"
            "Hãy chạy lệnh: python main.py export-cookies"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cookies(cookies: list, cookies_path: str) -> None:
    """Lưu cookies vào file JSON"""
    Path(cookies_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Đã lưu cookies vào: {cookies_path}")


def get_video_files(videos_dir: str) -> list[Path]:
    """Lấy danh sách file .mp4 trong thư mục videos"""
    videos_path = Path(videos_dir)
    if not videos_path.exists():
        videos_path.mkdir(parents=True)
        return []
    files = sorted(videos_path.glob("*.mp4"))
    return files


def setup_logger(logs_dir: str = "./logs") -> None:
    """Cấu hình logger"""
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logger.add(
        f"{logs_dir}/tiktok_uploader.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        encoding="utf-8",
    )


def clean_cookies_for_playwright(cookies: list) -> list:
    """
    Chuẩn hóa cookies để Playwright không bị lỗi.
    - sameSite phải là 'Strict', 'Lax', hoặc 'None'. Nếu là null/None hoặc giá trị khác, xóa hẳn field đó.
    """
    cleaned = []
    for c in cookies:
        cookie = c.copy()
        same_site = cookie.get("sameSite")
        if same_site is None or (isinstance(same_site, str) and same_site.lower() not in ["strict", "lax", "none"]):
            cookie.pop("sameSite", None)
        elif isinstance(same_site, str):
            cookie["sameSite"] = same_site.capitalize()
        cleaned.append(cookie)
    return cleaned


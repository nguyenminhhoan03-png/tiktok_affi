#!/usr/bin/env python3
"""
TikTok Auto Uploader
====================
Tool tự động upload video lên TikTok Studio và gán sản phẩm affiliate.

Cách dùng:
  python main.py export-cookies          # Lần đầu: đăng nhập và lưu cookies
  python main.py upload video.mp4        # Upload 1 video cụ thể
  python main.py upload-all              # Upload tất cả video trong thư mục ./videos/
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger
from playwright.sync_api import sync_playwright

from src.cookie_manager import CookieManager
from src.uploader import TikTokUploader
from src.utils import load_config, get_video_files, setup_logger

load_dotenv()

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
COOKIES_PATH = os.getenv("TIKTOK_COOKIES_FILE", "./cookies/cookies.json")
VIDEOS_DIR = os.getenv("VIDEOS_DIR", "./videos")
LOGS_DIR = os.getenv("LOGS_DIR", "./logs")
GOOGLE_COOKIES_PATH = os.getenv("GOOGLE_COOKIES_FILE", "./cookies/google_cookies.json")
JOBS_PATH = os.getenv("JOBS_FILE", "./jobs.json")


@click.group()
def cli():
    """🚀 TikTok Auto Uploader - Tự động upload video và gán sản phẩm affiliate"""
    setup_logger(LOGS_DIR)


# ─────────────────────────────────────────────────────────────
# Lệnh 1: Export cookies TikTok (chỉ cần chạy 1 lần)
# ─────────────────────────────────────────────────────────────
@cli.command("export-cookies")
def export_cookies():
    """Mở trình duyệt để đăng nhập TikTok và lưu cookies"""
    manager = CookieManager(COOKIES_PATH)
    manager.export_cookies_interactively()


# ─────────────────────────────────────────────────────────────
# Lệnh 2: Export cookies Google/Gemini (chỉ cần chạy 1 lần)
# ─────────────────────────────────────────────────────────────
@cli.command("export-google-cookies")
def export_google_cookies():
    """Mở trình duyệt để đăng nhập Google/Gemini và lưu cookies"""
    from src.google_cookie_manager import GoogleCookieManager
    manager = GoogleCookieManager(GOOGLE_COOKIES_PATH)
    manager.export_cookies_interactively()


# ─────────────────────────────────────────────────────────────
# Lệnh 3: Upload 1 video cụ thể
# ─────────────────────────────────────────────────────────────
@cli.command("upload")
@click.argument("video_path")
@click.option("--caption", "-c", default=None, help="Caption tùy chỉnh (nếu không dùng default trong config.json)")
@click.option("--product", "-p", default=None, help="Tên sản phẩm tùy chỉnh (nếu không dùng default trong config.json)")
def upload(video_path: str, caption: str, product: str):
    """Upload 1 file video lên TikTok"""
    config = load_config(CONFIG_PATH)
    manager = CookieManager(COOKIES_PATH)

    with sync_playwright() as playwright:
        browser, context = manager.load_context_with_cookies(
            playwright, headless=config.get("headless", False)
        )
        page = context.new_page()
        uploader = TikTokUploader(page, config)

        success = uploader.run(
            video_path=video_path,
            caption=caption,
            product_name=product,
        )

        if success:
            logger.info("🔔 Trình duyệt sẽ được giữ lại để bạn tự tay chọn sản phẩm và Đăng video.")
            input("⌨️ Nhấn ENTER tại cửa sổ terminal này để đóng trình duyệt sau khi đăng xong...")

        context.close()
        browser.close()

    sys.exit(0 if success else 1)


# ─────────────────────────────────────────────────────────────
# Lệnh 4: Upload tất cả video trong thư mục ./videos/
# ─────────────────────────────────────────────────────────────
@cli.command("upload-all")
@click.option("--caption", "-c", default=None, help="Caption tùy chỉnh")
@click.option("--product", "-p", default=None, help="Tên sản phẩm tùy chỉnh")
def upload_all(caption: str, product: str):
    """Upload tất cả .mp4 trong thư mục ./videos/"""
    config = load_config(CONFIG_PATH)
    videos = get_video_files(VIDEOS_DIR)

    if not videos:
        logger.warning(f"⚠️ Không tìm thấy file .mp4 nào trong: {VIDEOS_DIR}")
        return

    logger.info(f"📋 Tìm thấy {len(videos)} video: {[v.name for v in videos]}")
    manager = CookieManager(COOKIES_PATH)

    success_count = 0
    fail_count = 0

    with sync_playwright() as playwright:
        browser, context = manager.load_context_with_cookies(
            playwright, headless=config.get("headless", False)
        )

        for video in videos:
            logger.info(f"\n{'='*50}")
            logger.info(f"📹 Xử lý: {video.name}")
            page = context.new_page()
            uploader = TikTokUploader(page, config)

            success = uploader.run(
                video_path=str(video),
                caption=caption,
                product_name=product,
            )

            if success:
                logger.info("🔔 Trình duyệt sẽ được giữ lại để bạn tự tay chọn sản phẩm và Đăng video.")
                input("⌨️ Nhấn ENTER tại cửa sổ terminal này để tiếp tục sang video tiếp theo (trang hiện tại sẽ đóng)...")
                success_count += 1
                # Di chuyển video đã upload vào thư mục "done"
                done_dir = Path(VIDEOS_DIR) / "done"
                done_dir.mkdir(exist_ok=True)
                video.rename(done_dir / video.name)
                logger.info(f"📁 Đã chuyển '{video.name}' vào thư mục done/")
            else:
                fail_count += 1
            page.close()

        context.close()
        browser.close()

    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Thành công: {success_count} | ❌ Thất bại: {fail_count}")


def make_hashtag(name: str) -> str:
    """Tạo hashtag không dấu viết liền từ tên sản phẩm"""
    import unicodedata
    import re
    # Chuyển tiếng Việt có dấu thành không dấu
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    # Xóa ký tự đặc biệt và dấu cách
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', only_ascii)
    return cleaned.lower()


# ─────────────────────────────────────────────────────────────
# Lệnh 5: Chạy full pipeline tự động (Gemini -> TikTok)
# ─────────────────────────────────────────────────────────────
@cli.command("run-pipeline")
def run_pipeline():
    """Tự động: Gửi prompt render video ở Gemini -> Tải về -> Đăng TikTok & gán sản phẩm tương ứng"""
    import json
    from src.google_cookie_manager import GoogleCookieManager
    from src.gemini_generator import GeminiVideoGenerator

    config = load_config(CONFIG_PATH)

    # Đọc danh sách công việc cần làm
    jobs_path = Path(JOBS_PATH)
    if not jobs_path.exists():
        logger.error(f"❌ Không tìm thấy file danh sách công việc: {JOBS_PATH}")
        return

    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    # Dọn dẹp các video cũ trong thư mục videos/ để giải phóng dung lượng
    videos_dir = Path(VIDEOS_DIR)
    if videos_dir.exists():
        logger.info("🧹 Đang dọn dẹp các video cũ trong thư mục videos/ để giải phóng dung lượng...")
        for item in videos_dir.iterdir():
            if item.is_file() and item.name.endswith(".mp4"):
                try:
                    os.remove(item)
                except Exception as e:
                    logger.warning(f"⚠️ Không thể xóa video cũ {item}: {e}")

    logger.info(f"📋 Bắt đầu pipeline với {len(jobs)} công việc.")

    google_manager = GoogleCookieManager(GOOGLE_COOKIES_PATH)
    tiktok_manager = CookieManager(COOKIES_PATH)

    for idx, job in enumerate(jobs, 1):
        prompt = job.get("prompt")
        product_name = job.get("product_name")
        product_url = job.get("product_url")
        caption = job.get("caption")

        if not product_name and not product_url:
            logger.warning(f"⚠️ Công việc #{idx} thiếu cả product_name và product_url, bỏ qua.")
            continue

        logger.info(f"\n🚀 [Dự án #{idx}/{len(jobs)}] Đang xử lý sản phẩm...")

        temp_image_path = None
        
        # --- BƯỚC 0: Nếu có product_url, tự động cào ảnh sản phẩm và tên sản phẩm ---
        if product_url:
            logger.info(f"🔍 Đang truy cập TikTok Shop để quét thông tin sản phẩm...")
            try:
                from src.product_scraper import scrape_tiktok_product
                with sync_playwright() as playwright:
                    # Mở bằng cookies TikTok để vào được TikTok Shop không bị block
                    browser, context = tiktok_manager.load_context_with_cookies(
                        playwright, headless=config.get("headless", False)
                    )
                    page = context.new_page()
                    scraped_name, temp_image_path = scrape_tiktok_product(page, product_url)
                    
                    # Cập nhật thông tin nếu crawl thành công
                    if scraped_name and not product_name:
                        product_name = scraped_name
                    
                    context.close()
                    browser.close()
            except Exception as e:
                logger.error(f"❌ Lỗi khi quét thông tin sản phẩm từ TikTok Shop: {e}")

        # Fallback tên sản phẩm nếu không tìm thấy
        if not product_name:
            product_name = "Sản phẩm Affiliate"

        # Tự động sinh Prompt nếu chọn "auto" hoặc để trống
        if not prompt or prompt.lower() == "auto":
            default_prompt = config.get("default_prompt_template", "Create a 5-second cinematic promo video for '{product_name}'.")
            prompt = default_prompt.format(product_name=product_name)
            
        # Tự động sinh Caption nếu chọn "auto" hoặc để trống
        if not caption or caption.lower() == "auto":
            default_caption = config.get("default_caption_template", "🔥 {product_name} cực hot đã có mặt tại giỏ hàng! #{product_hashtag}")
            product_hashtag = make_hashtag(product_name)
            caption = default_caption.format(product_name=product_name, product_hashtag=product_hashtag)

        logger.info(f"📦 Sản phẩm: {product_name}")
        logger.info(f"✍️ Prompt sinh video: {prompt}")
        logger.info(f"📝 Caption đăng bài: {caption}")
        
        video_path = None
        
        # --- BƯỚC 1 & 2: Mở Gemini, gửi prompt kèm ảnh và tải video ---
        logger.info("🤖 Bắt đầu render video qua Google Gemini...")
        try:
            with sync_playwright() as playwright:
                browser, context = google_manager.load_context_with_cookies(
                    playwright, headless=config.get("headless", False)
                )
                page = context.new_page()
                generator = GeminiVideoGenerator(page, config)
                
                generator.open_gemini()
                video_path = generator.generate_video(prompt, image_path=temp_image_path)
                
                # Tự động lưu lại cookie mới (đã rotate) để giữ session Google luôn sống
                try:
                    updated_cookies = context.cookies()
                    from src.utils import save_cookies
                    save_cookies(updated_cookies, google_manager.cookies_path)
                    logger.info("💾 Đã tự động cập nhật Google cookies xoay vòng mới nhất.")
                except Exception as ce:
                    logger.warning(f"⚠️ Không thể lưu cập nhật Google cookies: {ce}")
                
                context.close()
                browser.close()
        except Exception as e:
            logger.error(f"❌ Lỗi khi render video từ Gemini: {e}")
            # Dọn dẹp ảnh tạm
            if temp_image_path and Path(temp_image_path).exists():
                os.remove(temp_image_path)
            continue

        # Dọn dẹp ảnh tạm sau khi Gemini đã nhận
        if temp_image_path and Path(temp_image_path).exists():
            try:
                os.remove(temp_image_path)
                logger.info("🧹 Đã dọn dẹp ảnh tạm sản phẩm.")
            except Exception as e:
                logger.warning(f"⚠️ Không thể xóa ảnh tạm: {e}")

        if not video_path or not Path(video_path).exists():
            logger.error("❌ Không lấy được file video, chuyển sang dự án tiếp theo.")
            continue

        # --- BƯỚC 3 & 4: Upload lên TikTok và gán link sản phẩm ---
        logger.info("📤 Đang tiến hành upload video và gán link lên TikTok...")
        try:
            with sync_playwright() as playwright:
                browser, context = tiktok_manager.load_context_with_cookies(
                    playwright, headless=config.get("headless", False)
                )
                page = context.new_page()
                uploader = TikTokUploader(page, config)

                success = uploader.run(
                    video_path=video_path,
                    caption=caption,
                    product_name=product_name
                )

                if success:
                    logger.info("🔔 Trình duyệt sẽ được giữ lại để bạn tự tay chọn sản phẩm và Đăng video.")
                    input("⌨️ Nhấn ENTER tại cửa sổ terminal này để đóng trình duyệt và chuyển sang dự án tiếp theo...")

                # Tự động lưu lại cookie TikTok mới (đã rotate) để duy trì session đăng nhập
                try:
                    updated_cookies = context.cookies()
                    from src.utils import save_cookies
                    save_cookies(updated_cookies, tiktok_manager.cookies_path)
                    logger.info("💾 Đã tự động cập nhật TikTok cookies xoay vòng mới nhất.")
                except Exception as ce:
                    logger.warning(f"⚠️ Không thể lưu cập nhật TikTok cookies: {ce}")

                context.close()
                browser.close()

                if success:
                    logger.info(f"🎉 Hoàn thành xuất sắc dự án #{idx}!")
                    # Xóa video đã đăng để giải phóng dung lượng
                    try:
                        p_vid = Path(video_path)
                        if p_vid.exists():
                            os.remove(p_vid)
                            logger.info(f"🗑️ Đã xóa video đã đăng để giải phóng dung lượng: {p_vid.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Không thể xóa video: {e}")
                else:
                    logger.error(f"❌ Đăng video thất bại cho dự án #{idx}.")
        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình push TikTok: {e}")


if __name__ == "__main__":
    cli()


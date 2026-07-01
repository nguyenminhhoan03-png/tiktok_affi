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
@click.option("--account", default="", help="Tên tài khoản TikTok (ví dụ: acc1, acc2)")
def export_cookies(account):
    """Mở trình duyệt để đăng nhập TikTok và lưu cookies"""
    if account:
        if not account.endswith(".json"):
            path = f"./cookies/tiktok_accounts/{account}.json"
        else:
            path = f"./cookies/tiktok_accounts/{account}"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    else:
        path = COOKIES_PATH
    manager = CookieManager(path)
    manager.export_cookies_interactively()


# ─────────────────────────────────────────────────────────────
# Lệnh 2: Export cookies Google/Gemini (chỉ cần chạy 1 lần)
# ─────────────────────────────────────────────────────────────
@cli.command("export-google-cookies")
@click.option("--account", default="", help="Tên tài khoản Google (ví dụ: acc1, acc2)")
def export_google_cookies(account):
    """Mở trình duyệt để đăng nhập Google/Gemini và lưu cookies"""
    from src.google_cookie_manager import GoogleCookieManager
    if account:
        if not account.endswith(".json"):
            path = f"./cookies/google_accounts/{account}.json"
        else:
            path = f"./cookies/google_accounts/{account}"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Khởi tạo file trống [] nếu chưa tồn tại
        target_path = Path(path)
        if not target_path.exists() or target_path.stat().st_size == 0:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("[]")
    else:
        path = GOOGLE_COOKIES_PATH
    manager = GoogleCookieManager(path)
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
    """Tạo các hashtag ngắn gọn, không dấu từ tên sản phẩm"""
    import unicodedata
    import re
    
    # Rút gọn tên trước để tránh quá dài
    cleaned_name = clean_product_name(name)
    
    # Chuyển tiếng Việt có dấu thành không dấu
    nfkd_form = unicodedata.normalize('NFKD', cleaned_name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    
    # Thay thế ký tự đặc biệt bằng khoảng trắng
    words_str = re.sub(r'[^a-zA-Z0-9\s]', ' ', only_ascii)
    # Tách từ và lọc từ rỗng
    words = [w.lower() for w in words_str.split() if w.strip()]
    
    if not words:
        return "sanpham"
        
    # Tạo hashtag chính bằng cách nối các từ bằng dấu gạch dưới, ví dụ: rosys12_vay_cong_so
    main_tag = "_".join(words)
    
    # Kiểm tra xem sản phẩm có phải cho nam giới không
    name_lower = name.lower()
    name_for_check = name_lower.replace("việt nam", "").replace("vietnam", "").replace("viet nam", "")
    is_male = False
    for word in ["nam", "men", "man", "mens", "con trai", "mr", "gentleman", "gentlemen"]:
        if re.search(r'\b' + re.escape(word) + r'\b', name_for_check):
            is_male = True
            break

    # Thêm các hashtag phụ liên quan
    sub_tags = []
    if any(w in words for w in ["vay", "dam"]):
        sub_tags.extend(["vaycongso", "vaythietke", "thoitrangnu" if not is_male else "thoitrangnam"])
    elif "ao" in words:
        sub_tags.extend(["aothun", "aokhoac", "thoitrangnam" if is_male else "thoitrangnu"])
    elif any(w in words for w in ["giay", "dep", "sandal"]):
        sub_tags.extend(["giaydep", "giaynam" if is_male else "giayxinh", "depnam" if is_male else "depxinh"])
        
    # Ghép lại. Vì trong template có sẵn dấu '#' trước {product_hashtag},
    # từ đầu tiên sẽ không có dấu '#', các từ tiếp theo có dấu '#'
    result = main_tag
    for tag in sub_tags:
        result += f" #{tag}"
        
    return result

# Helper to generate SEO-friendly caption using product description

def generate_seo_caption(product_name: str, product_description: str | None) -> str:
    """Create a caption that combines product name, a concise description snippet, and relevant hashtags.
    If description is missing, fallback to a simple template.
    """
    product_hashtag = make_hashtag(product_name)
    desc_snippet = ""
    if product_description:
        clean_desc = " ".join(product_description.split())
        desc_snippet = clean_desc[:120]
        if len(clean_desc) > 120:
            desc_snippet += "..."
    if desc_snippet:
        return f"🔥 {product_name}: {desc_snippet} #{product_hashtag}"
    else:
        default_caption = "🔥 {product_name} cực hot đã có mặt tại giỏ hàng! #{product_hashtag}"
        return default_caption.format(product_name=product_name, product_hashtag=product_hashtag)


def determine_product_type(product_name: str) -> str:
    name_lower = product_name.lower()
    clothing_keywords = [
        "váy", "đầm", "áo", "quần", "set bộ", "set đồ", "vest", "khoác", "croptop", "hoodie", 
        "cardigan", "jeans", "jean", "sơ mi", "thun", "phông", "len", "nỉ", "yếm", "đồ lót", 
        "bra", "bikini", "đồ ngủ", "pijama", "tất", "vớ", "mũ", "nón", "thắt lưng", "dây nịt",
        "tutu", "skirt", "dress", "pants", "shirt", "t-shirt", "jacket", "coat"
    ]
    footwear_keywords = [
        "giày", "dép", "sandal", "guốc", "sneaker", "boot", "boots", "slippers", "sục"
    ]
    
    for kw in clothing_keywords:
        if kw in name_lower:
            return "clothing"
    for kw in footwear_keywords:
        if kw in name_lower:
            return "footwear"
    return "general"


def clean_product_name(product_name: str) -> str:
    """Rút gọn tên sản phẩm dài dòng từ TikTok Shop thành tên sản phẩm cốt lõi ngắn gọn để AI tập trung render."""
    if not product_name:
        return "sản phẩm"
    
    name_lower = product_name.lower()
    
    # 1. Tìm các từ khóa thời trang/giày dép, công nghệ, gia dụng phổ biến để lấy cụm từ cốt lõi
    core_keywords = [
        # Thời trang & Giày dép
        "váy dự tiệc", "váy công sở", "váy tiểu thư", "váy dáng dài", "váy xòe", "váy",
        "đầm dự tiệc", "đầm công sở", "đầm tiểu thư", "đầm dáng dài", "đầm",
        "áo sơ mi", "áo thun", "áo phông", "áo khoác", "áo croptop", "áo hoodie", "áo len", "áo nỉ", "áo",
        "quần jeans", "quần jean", "quần tây", "quần short", "quần dài", "quần",
        "set bộ", "set đồ", "bộ quần áo",
        "giày sneaker", "giày cao gót", "giày tây", "giày thể thao", "giày",
        "dép quai ngang", "dép sandal", "dép", "sandal", "guốc",
        # Đồ công nghệ
        "tai nghe bluetooth", "tai nghe không dây", "tai nghe", "loa bluetooth", "loa không dây", "loa",
        "sạc dự phòng", "củ sạc nhanh", "củ sạc", "cáp sạc", "dây sạc", "chuột không dây", "chuột máy tính",
        "bàn phím cơ", "bàn phím bluetooth", "bàn phím", "quạt tích điện", "quạt mini", "quạt",
        "ốp lưng", "kính cường lực", "giá đỡ điện thoại",
        # Mỹ phẩm & Chăm sóc cá nhân
        "kem chống nắng", "sữa rửa mặt", "nước hoa", "son kem", "son thỏi", "son môi", "son",
        "serum dưỡng da", "serum", "kem dưỡng ẩm", "kem dưỡng", "tẩy trang",
        # Gia dụng & Đồ dùng khác
        "nồi chiên không dầu", "máy xay sinh tố", "bình giữ nhiệt", "quạt để bàn", "đèn học chống cận", "đèn học",
        "kệ để đồ", "hộp đựng thức ăn"
    ]
    
    for kw in core_keywords:
        if kw in name_lower:
            idx = name_lower.find(kw)
            words = product_name[idx:].split()
            cleaned = " ".join(words[:3])
            return cleaned.rstrip(",.-/()[]{} ")

    # 2. Nếu không khớp từ khóa đặc biệt nào, lấy 5 từ đầu tiên của tên sản phẩm
    words = product_name.split()
    if len(words) > 5:
        return " ".join(words[:5]).rstrip(",.-/()[]{} ")
    return product_name


def build_auto_prompt(product_name: str, product_description: str | None = None) -> str:
    prod_type = determine_product_type(product_name)
    cleaned_name = clean_product_name(product_name)
    
    # Chuẩn bị thông tin chi tiết sản phẩm nếu có để đưa vào prompt
    detail_prompt = ""
    if product_description:
        clean_desc = " ".join(product_description.split())
        detail_prompt = f" Focus the showcase on these details and features: {clean_desc[:250]}."

    # Kiểm tra xem sản phẩm có phải cho nam giới không
    name_lower = product_name.lower()
    desc_lower = (product_description or "").lower()
    name_for_check = name_lower.replace("việt nam", "").replace("vietnam", "").replace("viet nam", "")
    desc_for_check = desc_lower.replace("việt nam", "").replace("vietnam", "").replace("viet nam", "")
    is_male = False
    import re
    for word in ["nam", "men", "man", "mens", "con trai", "mr", "gentleman", "gentlemen"]:
        if re.search(r'\b' + re.escape(word) + r'\b', name_for_check) or re.search(r'\b' + re.escape(word) + r'\b', desc_for_check):
            is_male = True
            break

    model_gender = "male model" if is_male else "female model"

    if prod_type == "clothing":
        logger.info(f"👕 Sản phẩm thuộc nhóm Thời trang. Áp dụng prompt Review chi tiết sản phẩm.")
        return (
            f"A high-quality fashion showcase video, 9:16 vertical ratio, cinematic aesthetic style. "
            f"Product: '{cleaned_name}' fashion item (use the uploaded reference image).{detail_prompt} "
            f"Show a {model_gender} wearing the outfit and walking in a bright, clean, aesthetic room. "
            "Video style: Focus on the design, fabric texture, seams, fit, and movement of the clothing. "
            "Camera movement: smooth handheld, close-up shots of fabric details and full-body fit shots. "
            "No speech in the video. Silent video. No text overlays, no watermarks. Duration 10 seconds."
        )
    elif prod_type == "footwear":
        logger.info(f"👟 Sản phẩm thuộc nhóm Giày dép. Áp dụng prompt Review chi tiết giày dép.")
        return (
            f"A high-quality footwear showcase video, 9:16 vertical ratio, cinematic aesthetic style. "
            f"Product: '{cleaned_name}' footwear (use the uploaded reference image).{detail_prompt} "
            "Show the shoes in a clean, modern, aesthetic setting. "
            "Video style: Focus on the design details, texture, sole, and style of the footwear. "
            "Camera movement: smooth close-up shots of the shoe features. "
            "No speech in the video. Silent video. No text overlays, no watermarks. Duration 10 seconds."
        )
    else:
        logger.info(f"📦 Sản phẩm thuộc nhóm Đồ vật/Khác. Áp dụng prompt Review chi tiết sản phẩm.")
        return (
            f"A high-quality product presentation video, 9:16 vertical ratio, cinematic aesthetic style. "
            f"Product: '{cleaned_name}' (use the uploaded reference image).{detail_prompt} "
            "Show the product features and quality in a bright, clean, modern room. "
            "Video style: Demonstration of the product utility and details. "
            "Camera movement: smooth focused close-ups of the product. "
            "No speech in the video. Silent video. No text overlays, no watermarks. Duration 10 seconds."
        )




def update_job_in_file(jobs_path: Path, target_job: dict, status: str, error_msg: str | None = None):
    """Cập nhật trạng thái và lỗi của job trực tiếp trong file jobs.json"""
    import json
    try:
        if not jobs_path.exists():
            return
        with open(jobs_path, "r", encoding="utf-8") as f:
            current_jobs = json.load(f)
        
        updated = False
        for c_job in current_jobs:
            if (c_job.get("product_url") == target_job.get("product_url") 
                and c_job.get("product_name") == target_job.get("product_name") 
                and c_job.get("prompt") == target_job.get("prompt")):
                c_job["status"] = status
                if status == "failed":
                    c_job["success"] = False
                else:
                    c_job.pop("success", None)
                
                if error_msg:
                    c_job["error_msg"] = error_msg
                else:
                    c_job.pop("error_msg", None)
                updated = True
                break
        
        if updated:
            with open(jobs_path, "w", encoding="utf-8") as f:
                json.dump(current_jobs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"⚠️ Không thể cập nhật trạng thái job trong jobs.json: {e}")


# ─────────────────────────────────────────────────────────────
# Lệnh 5: Chạy full pipeline tự động (Kling AI / Gemini -> TikTok)
# ─────────────────────────────────────────────────────────────
@cli.command("run-pipeline")
def run_pipeline():
    """Tự động: Render video (Kling AI hoặc Gemini) -> Tải về -> Đăng TikTok & gán sản phẩm"""
    import json

    config = load_config(CONFIG_PATH)

    # Force use of Gemini engine for video generation (Kling removed)
    video_engine = "gemini"
    from src.google_cookie_manager import GoogleCookieManager
    from src.gemini_generator import GeminiVideoGenerator
    google_manager = GoogleCookieManager(GOOGLE_COOKIES_PATH)
    logger.info("🤖 Sử dụng engine: Google Gemini (Kling đã được loại bỏ)")

    # Đọc danh sách công việc cần làm
    jobs_path = Path(JOBS_PATH)
    if not jobs_path.exists():
        logger.error(f"❌ Không tìm thấy file danh sách công việc: {JOBS_PATH}")
        return

    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    # Dọn dẹp các video cũ trong thư mục videos/
    videos_dir = Path(VIDEOS_DIR)
    if videos_dir.exists():
        logger.info("🧹 Đang dọn dẹp các video cũ trong thư mục videos/...")
        for item in videos_dir.iterdir():
            if item.is_file() and item.name.endswith(".mp4"):
                try:
                    os.remove(item)
                except Exception as e:
                    logger.warning(f"⚠️ Không thể xóa video cũ {item}: {e}")

    logger.info(f"📋 Bắt đầu pipeline với {len(jobs)} công việc.")

    tiktok_manager = CookieManager(COOKIES_PATH)

    for idx, job in enumerate(jobs, 1):
        prompt = job.get("prompt")
        product_name = job.get("product_name")
        product_url = job.get("product_url")
        caption = job.get("caption")
        tiktok_account = job.get("tiktok_account")

        # Xác định tài khoản TikTok cho job này
        if tiktok_account:
            if not tiktok_account.endswith(".json"):
                tiktok_cookies_file = f"./cookies/tiktok_accounts/{tiktok_account}.json"
            else:
                tiktok_cookies_file = f"./cookies/tiktok_accounts/{tiktok_account}"
            
            if Path(tiktok_cookies_file).exists():
                job_tiktok_manager = CookieManager(tiktok_cookies_file)
                logger.info(f"👥 Sử dụng tài khoản TikTok: {tiktok_account} ({tiktok_cookies_file})")
            else:
                logger.warning(f"⚠️ Không tìm thấy file cookies cho TikTok account '{tiktok_account}' tại {tiktok_cookies_file}. Dùng mặc định.")
                job_tiktok_manager = tiktok_manager
        else:
            job_tiktok_manager = tiktok_manager

        if not product_name and not product_url:
            logger.warning(f"⚠️ Công việc #{idx} thiếu cả product_name và product_url, bỏ quan.")
            continue

        # Đánh dấu đang xử lý và reset trạng thái cũ (nếu có)
        update_job_in_file(jobs_path, job, "processing")

        logger.info(f"\n🚀 [Dự án #{idx}/{len(jobs)}] Đang xử lý sản phẩm...")

        temp_image_path = None
        product_description = None
        
        # --- BƯỚC 0: Nếu có product_url, tự động cào ảnh sản phẩm và tên sản phẩm ---
        if product_url:
            logger.info(f"🔍 Đang truy cập TikTok Shop để quét thông tin sản phẩm...")
            try:
                from src.product_scraper import scrape_tiktok_product
                with sync_playwright() as playwright:
                    # Mở bằng cookies TikTok để vào được TikTok Shop không bị block
                    browser, context = job_tiktok_manager.load_context_with_cookies(
                        playwright, headless=config.get("headless", False)
                    )
                    page = context.new_page()
                    scraped_name, temp_image_path, product_description = scrape_tiktok_product(page, product_url)
                    
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
            prompt = build_auto_prompt(product_name, product_description)
            
        # Tự động sinh Caption nếu chọn "auto" hoặc để trống
        if not caption or caption.lower() == "auto":
            caption = generate_seo_caption(product_name, product_description)

        logger.info(f"📦 Sản phẩm: {product_name}")
        logger.info(f"📝 Caption đăng bài: {caption}")
        
        video_path = None
        
        # --- BƯỚC 1 & 2: Render video ---
        # Gemini engine (Kling đã được loại bỏ)
        logger.info("🤖 Bắt đầu render video qua Google Gemini...")
        num_segments = job.get("video_segments", 1)
        if num_segments > 1:
            logger.info(f"🎬 Chế độ multi-segment: sẽ render {num_segments} clip rồi ghép lại.")
            
        render_success = False
        max_account_rotations = google_manager.get_accounts_count()
        
        for rot_idx in range(max_account_rotations):
            browser = None
            context = None
            try:
                with sync_playwright() as playwright:
                    browser, context = google_manager.load_context_with_cookies(
                        playwright, headless=config.get("headless", False)
                    )
                    page = context.new_page()
                    generator = GeminiVideoGenerator(page, config)
                    generator.open_gemini()
                    google_manager.mark_session_ready()
                    if num_segments > 1:
                        video_path = generator.generate_multi_segment_video(
                            prompt,
                            product_name=product_name,
                            image_path=temp_image_path,
                            num_segments=num_segments,
                            product_description=product_description,
                        )
                    else:
                        video_path = generator.generate_video(prompt, image_path=temp_image_path, product_name=product_name)
                    
                    try:
                        updated_cookies = context.cookies()
                        google_manager.save_active_cookies(updated_cookies)
                    except Exception as ce:
                        logger.warning(f"⚠️ Không thể lưu cập nhật Google cookies: {ce}")
                    
                    render_success = True
                    break
            except Exception as e:
                err_str = str(e)
                is_expired = (
                    "GEMINI_DAILY_LIMIT_EXCEEDED" in err_str 
                    or "GEMINI_SUBSCRIPTION_REQUIRED" in err_str
                    or "session hết hạn" in err_str 
                    or "chưa đăng nhập" in err_str
                )
                if is_expired:
                    logger.warning(f"⚠️ Tài khoản Google hiện tại hết hạn hoặc hết giới hạn tạo video: {e}")
                    
                    if rot_idx == max_account_rotations - 1:
                        logger.error("❌ Đã thử hết tất cả các tài khoản Google mà không thành công!")
                        update_job_in_file(jobs_path, job, "failed", "Hết tất cả tài khoản Google/Gemini để xoay vòng")
                        raise click.ClickException("Hết tất cả tài khoản Google/Gemini để xoay vòng. Dừng chương trình.")
                    
                    rotated = google_manager.rotate_account()
                    if rotated:
                        logger.info("🔄 Đang thử lại với tài khoản Google tiếp theo...")
                        continue
                    else:
                        logger.error("❌ Không còn tài khoản Google dự phòng nào khác trong thư mục cookies/google_accounts/!")
                        update_job_in_file(jobs_path, job, "failed", "Hết tất cả tài khoản Google/Gemini để xoay vòng")
                        raise click.ClickException("Hết tất cả tài khoản Google/Gemini để xoay vòng. Dừng chương trình.")
                else:
                    logger.error(f"❌ Lỗi khi render video từ Gemini: {e}")
                    break
            finally:
                try:
                    if context:
                        context.close()
                    if browser:
                        browser.close()
                except Exception:
                    pass

        if not render_success:
            if temp_image_path and Path(temp_image_path).exists():
                os.remove(temp_image_path)
            update_job_in_file(jobs_path, job, "failed", "Lỗi render video từ Gemini")
            continue

        # Dọn dẹp ảnh tạm
        if temp_image_path and Path(temp_image_path).exists():
            try:
                os.remove(temp_image_path)
                logger.info("🧹 Đã dọn dẹp ảnh tạm sản phẩm.")
            except Exception as e:
                logger.warning(f"⚠️ Không thể xóa ảnh tạm: {e}")

        if not video_path or not Path(video_path).exists():
            logger.error("❌ Không lấy được file video, chuyển sang dự án tiếp theo.")
            update_job_in_file(jobs_path, job, "failed", "Không tìm thấy file video đã render hoặc lỗi hậu kỳ")
            continue

        # --- BƯỚC HẬU KỲ: Xử lý âm thanh và thuyết minh (TTS) ---
        from src.utils import get_bg_music_track, replace_video_audio, add_voiceover_to_video
        
        bg_music = get_bg_music_track(config.get("bg_music"))
        if bg_music:
            logger.info(f"🎵 Phát hiện nhạc nền tùy chỉnh: {bg_music}")
            processed_video_name = f"processed_{Path(video_path).name}"
            processed_video_path = str(Path(video_path).parent / processed_video_name)
            
            if config.get("voiceover", False):
                logger.info("🎙️ Chế độ Voiceover bật: Tiến hành mix giọng thuyết minh và nhạc nền mới...")
                # Thay nhạc nền trước
                replaced_audio_path = replace_video_audio(video_path, bg_music, processed_video_path)
                # Sau đó chèn giọng thuyết minh đè lên nhạc nền
                final_processed_path = str(Path(video_path).parent / f"final_tts_{Path(video_path).name}")
                video_path = add_voiceover_to_video(replaced_audio_path, caption, final_processed_path)
                # Xóa file trung gian
                if Path(replaced_audio_path).exists() and replaced_audio_path != video_path:
                    try:
                        os.remove(replaced_audio_path)
                    except Exception:
                        pass
            else:
                video_path = replace_video_audio(video_path, bg_music, processed_video_path)
        else:
            if config.get("voiceover", False):
                logger.info("🎙️ Chỉ bật Voiceover (không có nhạc nền tùy chỉnh): Đang chèn thuyết minh...")
                processed_video_name = f"tts_{Path(video_path).name}"
                processed_video_path = str(Path(video_path).parent / processed_video_name)
                video_path = add_voiceover_to_video(video_path, caption, processed_video_path)
            else:
                logger.info(f"🎥 Sử dụng trực tiếp video gốc từ Gemini (giữ nguyên âm thanh): {video_path}")

        # --- BƯỚC 3 & 4: Upload lên TikTok và gán link sản phẩm ---
        logger.info("📤 Đang tiến hành upload video và gán link lên TikTok...")
        try:
            with sync_playwright() as playwright:
                browser, context = job_tiktok_manager.load_context_with_cookies(
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
                    logger.info(f"🎉 Đăng video thành công tự động cho dự án #{idx}!")

                # Tự động lưu lại cookie TikTok mới (đã rotate) để duy trì session đăng nhập
                try:
                    updated_cookies = context.cookies()
                    from src.utils import save_cookies
                    save_cookies(updated_cookies, job_tiktok_manager.cookies_path)
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

                    # Xóa job thành công khỏi jobs.json
                    try:
                        if jobs_path.exists():
                            with open(jobs_path, "r", encoding="utf-8") as f:
                                current_jobs = json.load(f)
                            
                            updated_jobs = []
                            removed = False
                            for c_job in current_jobs:
                                if (not removed 
                                    and c_job.get("product_url") == job.get("product_url") 
                                    and c_job.get("product_name") == job.get("product_name") 
                                    and c_job.get("prompt") == job.get("prompt")):
                                    removed = True
                                    continue
                                updated_jobs.append(c_job)
                            
                            with open(jobs_path, "w", encoding="utf-8") as f:
                                json.dump(updated_jobs, f, indent=2, ensure_ascii=False)
                            logger.info("🗑️ Đã xóa job thành công khỏi jobs.json")
                    except Exception as e:
                        logger.warning(f"⚠️ Không thể cập nhật jobs.json: {e}")
                else:
                    logger.error(f"❌ Đăng video thất bại cho dự án #{idx}.")
                    update_job_in_file(jobs_path, job, "failed", "Đăng video lên TikTok thất bại")
        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình push TikTok: {e}")
            update_job_in_file(jobs_path, job, "failed", f"Lỗi push TikTok: {str(e)}")


if __name__ == "__main__":
    cli()


import os
import requests
from pathlib import Path
from playwright.sync_api import Page
from loguru import logger

def scrape_tiktok_product(page: Page, product_url: str) -> tuple[str | None, str | None]:
    """
    Tru cập link sản phẩm TikTok Shop bằng page hiện tại (đã load cookies),
    lấy tên sản phẩm và tải ảnh chính về.
    
    Trả về: (tên_sản_phẩm, đường_dẫn_ảnh_tải_về)
    """
    logger.info(f"🌐 Đang truy cập link sản phẩm: {product_url}")
    try:
        # Vào trang sản phẩm
        page.goto(product_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)  # Đợi 3 giây để JS render xong ảnh
        
        # Kiểm tra xem có bị Captcha chặn không
        captcha_indicators = ["Verify to continue", "captcha", "verify_container", "sec.tiktok.com"]
        current_title = page.title() or ""
        current_url = page.url or ""
        
        is_captcha = (
            any(ind.lower() in current_title.lower() for ind in captcha_indicators) or
            any(ind.lower() in current_url.lower() for ind in captcha_indicators) or
            page.locator("text=Verify to continue").count() > 0 or
            page.locator("#captcha-verify-image").count() > 0
        )
        
        if is_captcha:
            logger.warning("⚠️ PHÁT HIỆN CAPTCHA BẢO MẬT CỦA TIKTOK SHOP!")
            logger.warning("👉 Hãy chuyển sang cửa sổ trình duyệt Chrome đang mở, thực hiện giải captcha (kéo mảnh ghép/chọn hình).")
            logger.warning("👉 Sau khi giải xong và thấy trang thông tin sản phẩm hiện ra, quay lại đây nhấn ENTER để tiếp tục...")
            input("\n[👉 GIẢI CAPTCHA XONG THÌ NHẤN ENTER TẠI ĐÂY...]")
            page.wait_for_timeout(3000)  # Đợi 3 giây để trang cập nhật dữ liệu sản phẩm mới
        
        # 1. Trích xuất tên sản phẩm
        # TikTok Shop thường dùng thẻ h1 hoặc div lớn chứa text tiêu đề
        title_selectors = [
            "h1", 
            "[class*='title']", 
            "[class*='Title']", 
            "[class*='product_name']"
        ]
        product_title = None
        for selector in title_selectors:
            title_elem = page.locator(selector).first
            if title_elem.is_visible():
                text = title_elem.text_content()
                if text and len(text.strip()) > 5:
                    product_title = text.strip()
                    break
        
        if not product_title:
            product_title = page.title() or "Sản phẩm TikTok Shop"
        
        logger.info(f"🏷️ Phát hiện tên sản phẩm: {product_title}")
        
        # 2. Tìm ảnh đại diện chính của sản phẩm
        # Chúng ta sẽ tìm thẻ img đầu tiên có kích thước lớn hoặc nằm trong vùng gallery
        img_src = None
        
        # Viết script chạy trong browser để tìm ảnh lớn nhất/phù hợp nhất
        js_find_image = """
        () => {
            // Danh sách các selector gallery phổ biến
            const gallerySelector = "[class*='gallery'], [class*='carousel'], [class*='main-image'], [class*='ProductImage']";
            const gallery = document.querySelector(gallerySelector);
            let imgs = [];
            if (gallery) {
                imgs = Array.from(gallery.querySelectorAll("img"));
            } else {
                imgs = Array.from(document.querySelectorAll("img"));
            }
            
            // Lọc ra các ảnh có kích thước lớn (tránh avatar, icon)
            const validImgs = imgs.filter(img => {
                const src = img.src || '';
                // Bỏ qua logo, avatar nhỏ
                if (src.includes('avatar') || src.includes('logo') || src.includes('icon')) return false;
                // Ưu tiên các ảnh từ cdn TikTok
                return src.startsWith('http') && (src.includes('tiktokcdn') || src.includes('tos-alisg') || src.includes('oec'));
            });
            
            if (validImgs.length > 0) {
                return validImgs[0].src;
            }
            
            // Fallback: Lấy ảnh bất kỳ có kích thước lớn nhất
            let maxArea = 0;
            let bestSrc = null;
            document.querySelectorAll("img").forEach(img => {
                const area = img.naturalWidth * img.naturalHeight;
                if (area > maxArea && img.src.startsWith('http')) {
                    maxArea = area;
                    bestSrc = img.src;
                }
            });
            return bestSrc;
        }
        """
        img_src = page.evaluate(js_find_image)
        
        if not img_src:
            # Fallback 2: Thử lấy qua các thẻ img thông thường
            first_img = page.locator("img[src*='tiktokcdn'], img[src*='tos-alisg']").first
            if first_img.is_visible():
                img_src = first_img.get_attribute("src")

        if not img_src:
            logger.warning("⚠️ Không tìm thấy ảnh sản phẩm phù hợp trên trang.")
            return product_title, None

        logger.info(f"📸 Tìm thấy link ảnh sản phẩm: {img_src}")
        
        # 3. Tải ảnh về
        temp_dir = Path("./temp")
        temp_dir.mkdir(exist_ok=True)
        
        # Xác định đuôi file từ URL
        ext = ".png"
        if ".webp" in img_src.lower():
            ext = ".webp"
        elif ".jpg" in img_src.lower() or ".jpeg" in img_src.lower():
            ext = ".jpg"
            
        img_path = temp_dir / f"product_{int(page.evaluate('Date.now()'))}{ext}"
        
        logger.info(f"📥 Đang tải ảnh trực tiếp bằng requests...")
        response = requests.get(img_src, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if response.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(response.content)
            logger.info(f"💾 Đã tải và lưu ảnh sản phẩm tại: {img_path}")
            return product_title, str(img_path)
        else:
            logger.warning(f"⚠️ Không thể tải ảnh trực tiếp, status code: {response.status_code}")
            return product_title, None
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi scrape thông tin sản phẩm: {e}")
        return None, None

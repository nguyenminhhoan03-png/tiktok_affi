import os
import requests
from pathlib import Path
from playwright.sync_api import Page
from loguru import logger

def scrape_tiktok_product(page: Page, product_url: str) -> tuple[str | None, str | None, str | None]:
    """
    Truy cập link sản phẩm TikTok Shop bằng page hiện tại (đã load cookies),
    lấy tên sản phẩm, ảnh chính và mô tả chi tiết sản phẩm.
    
    Trả về: (tên_sản_phẩm, đường_dẫn_ảnh_tải_về, mô_tả_sản_phẩm)
    """
    logger.info(f"🌐 Đang truy cập link sản phẩm: {product_url}")
    try:
        # Vào trang sản phẩm
        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            logger.warning(f"⚠️ Cảnh báo khi truy cập link sản phẩm: {e}. Vẫn tiếp tục trích xuất...")
        page.wait_for_timeout(5000)  # Đợi 5 giây để JS render xong ảnh
        
        # Kiểm tra xem có bị Captcha chặn không
        captcha_indicators = ["Verify to continue", "captcha", "verify_container", "sec.tiktok.com", "security check", "security"]
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

        # 2. Trích xuất mô tả / thông tin chi tiết sản phẩm
        product_description = None
        try:
            js_get_desc = """
            () => {
                // Thử các selector phổ biến cho phần mô tả TikTok Shop
                const descSelectors = [
                    '[class*="description"]',
                    '[class*="Description"]',
                    '[class*="product-detail"]',
                    '[class*="ProductDetail"]',
                    '[class*="detail-content"]',
                    '[class*="spec"]',
                    '[class*="Spec"]',
                    '[class*="attribute"]',
                    '[class*="overview"]'
                ];
                
                let bestText = '';
                for (const sel of descSelectors) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const text = (el.innerText || el.textContent || '').trim();
                        // Lấy đoạn text dài nhất, loại bỏ những đoạn quá ngắn hoặc là bảng size
                        if (text.length > bestText.length && text.length < 2000 
                            && !text.toLowerCase().includes('size chart')
                            && !text.toLowerCase().includes('bảng size')) {
                            bestText = text;
                        }
                    }
                }
                return bestText || null;
            }
            """
            raw_desc = page.evaluate(js_get_desc)
            if raw_desc and len(raw_desc.strip()) > 30:
                # Cắt bớt nếu quá dài, chỉ lấy 500 ký tự đầu để không bloat prompt
                product_description = raw_desc.strip()[:500]
                logger.info(f"📄 Đã trích xuất mô tả sản phẩm ({len(product_description)} ký tự)")
            else:
                logger.info("ℹ️ Không tìm thấy mô tả chi tiết, sẽ dùng tên sản phẩm.")
        except Exception as de:
            logger.warning(f"⚠️ Không thể trích xuất mô tả: {de}")
        
        # 3. Tìm ảnh đại diện chính của sản phẩm
        img_src = None
        
        js_find_image = """
        () => {
            const gallerySelectors = [
                "[class*='gallery']",
                "[class*='carousel']",
                "[class*='main-image']",
                "[class*='ProductImage']",
                "[class*='slider']",
                "[class*='image-view']",
                "[class*='swiper']",
                "[class*='pc-gallery']",
                "[class*='ProductGallery']"
            ];
            
            const excludeKeywords = [
                'avatar', 'logo', 'icon', 'profile', 'user', 'seller', 
                'shop', 'author', 'size', 'chart', 'guide', 'table', 
                'measure', 'bang-size', 'bang_size', 'huong-dan', 
                'specification', 'specs', 'policy', 'chinh-sach'
            ];
            
            const isValiImg = img => {
                const src = (img.src || '').toLowerCase();
                const className = (img.className || '').toLowerCase();
                const id = (img.id || '').toLowerCase();
                const alt = (img.alt || '').toLowerCase();
                
                if (excludeKeywords.some(kw => src.includes(kw) || className.includes(kw) || id.includes(kw) || alt.includes(kw))) {
                    return false;
                }
                
                const isTikTokImg = src.startsWith('http') && (
                    src.includes('tiktokcdn') || 
                    src.includes('tos-alisg') || 
                    src.includes('oec') || 
                    src.includes('tiktok-cdn') || 
                    src.includes('ibyteimg')
                );
                if (!isTikTokImg) return false;
                
                const width = img.naturalWidth || img.width || 0;
                const height = img.naturalHeight || img.height || 0;
                if (width > 0 && height > 0 && (width < 250 || height < 250)) {
                    return false;
                }
                
                const rect = img.getBoundingClientRect();
                if (rect.top < 0 || rect.top > 550 || rect.width < 200) {
                    return false;
                }
                
                return true;
            };
            
            for (const selector of gallerySelectors) {
                const containers = document.querySelectorAll(selector);
                for (const container of containers) {
                    const imgs = Array.from(container.querySelectorAll("img"));
                    const validImgs = imgs.filter(isValiImg);
                    if (validImgs.length > 0) {
                        return validImgs[0].src;
                    }
                }
            }
            
            const allImgs = Array.from(document.querySelectorAll("img"));
            const validAllImgs = allImgs.filter(isValiImg);
            if (validAllImgs.length > 0) {
                validAllImgs.sort((a, b) => {
                    const areaA = (a.naturalWidth || a.width || 0) * (a.naturalHeight || a.height || 0);
                    const areaB = (b.naturalWidth || b.width || 0) * (b.naturalHeight || b.height || 0);
                    return areaB - areaA;
                });
                return validAllImgs[0].src;
            }
            
            let maxArea = 0;
            let bestSrc = null;
            document.querySelectorAll("img").forEach(img => {
                const area = (img.naturalWidth || img.width || 0) * (img.naturalHeight || img.height || 0);
                if (area > maxArea && img.src && img.src.startsWith('http')) {
                    maxArea = area;
                    bestSrc = img.src;
                }
            });
            return bestSrc;
        }
        """
        img_src = page.evaluate(js_find_image)
        
        if not img_src:
            logger.warning("⚠️ Không tìm thấy ảnh sản phẩm phù hợp trên trang.")
            return product_title, None, product_description

        logger.info(f"📸 Tìm thấy link ảnh sản phẩm: {img_src}")
        
        # 4. Tải ảnh về
        temp_dir = Path("./temp")
        temp_dir.mkdir(exist_ok=True)
        
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
            return product_title, str(img_path), product_description
        else:
            logger.warning(f"⚠️ Không thể tải ảnh trực tiếp, status code: {response.status_code}")
            return product_title, None, product_description
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi scrape thông tin sản phẩm: {e}")
        return None, None, None


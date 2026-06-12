import time
import base64
from pathlib import Path
from playwright.sync_api import Page
from loguru import logger

from src.uploader import human_delay


class GeminiVideoGenerator:
    """
    Tự động hóa Google Gemini để tạo video bằng AI (Omni/Veo).
    """

    GEMINI_APP_URL = "https://gemini.google.com/app/video"
 
    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        self.delay_min = config.get("delay_between_actions_min", 1.5)
        self.delay_max = config.get("delay_between_actions_max", 3.5)
        self.type_delay = config.get("type_delay_ms", 80)
 
    def _delay(self) -> None:
        human_delay(self.delay_min, self.delay_max)
 
    def _close_overlays(self) -> None:
        """Đóng các popup quảng cáo, giới thiệu tính năng mới (Try it, Got it, cdk-overlay) của Gemini."""
        try:
            buttons = self.page.locator(
                'button:has-text("Try it"), '
                'button:has-text("Got it"), '
                'button:has-text("Dismiss"), '
                'button:has-text("Close"), '
                'button:has-text("Thử ngay"), '
                'button:has-text("Đã hiểu"), '
                'button:has-text("Bỏ qua"), '
                '.cdk-overlay-container button, '
                '.discovery-card-actions button'
            )
            for i in range(buttons.count()):
                btn = buttons.nth(i)
                if btn.is_visible():
                    button_text = (btn.text_content() or "").strip()
                    logger.info(f"👉 Click nút đóng/chấp nhận overlay: {button_text}")
                    btn.click(timeout=3000)
                    self._delay()
        except Exception as e:
            logger.debug(f"Không thể click đóng overlay: {e}")
 
        try:
            self.page.evaluate('''() => {
                document.querySelectorAll(
                    ".cdk-overlay-backdrop, .cdk-overlay-container, [class*='overlay' i], [class*='backdrop' i], [class*='discovery-card' i]"
                ).forEach(el => {
                    el.style.pointerEvents = "none";
                    el.style.display = "none";
                });
            }''')
        except Exception:
            pass

    def open_gemini(self) -> None:
        logger.info("🌐 Mở Google Gemini App...")
        try:
            self.page.goto(self.GEMINI_APP_URL, wait_until="load", timeout=30000)
        except Exception as e:
            logger.warning(f"⚠️ Cảnh báo khi load trang Gemini: {e}")
        self._delay()
        self._close_overlays()
 
        # Check xem đã login chưa
        is_logged_in = True
        try:
            self.page.wait_for_selector(
                'div[contenteditable="true"], textarea, div[class*="ql-editor"]',
                timeout=20000
            )
            
            # Kiểm tra xem có nút "Sign in" hoặc "Đăng nhập" hiển thị trên màn hình không
            sign_in_visible = False
            for btn in self.page.locator('button, a, div[role="button"]').all():
                try:
                    text = (btn.text_content() or "").strip().lower()
                    if text in ["sign in", "đăng nhập"] and btn.is_visible():
                        sign_in_visible = True
                        break
                except Exception:
                    pass
            
            if sign_in_visible:
                is_logged_in = False
        except Exception as e:
            is_logged_in = False
            
        if not is_logged_in:
            logger.error("❌ Không tìm thấy thông tin đăng nhập của Gemini. Có thể cookies đã hết hạn hoặc chưa đăng nhập!")
            try:
                Path("temp").mkdir(exist_ok=True)
                self.page.screenshot(path="temp/gemini_error.png")
                logger.info("📸 Đã chụp ảnh màn hình lỗi tại temp/gemini_error.png")
            except Exception as se:
                logger.debug(f"Không thể chụp ảnh lỗi: {se}")
            raise RuntimeError("Google session hết hạn hoặc chưa đăng nhập.")
            
        logger.info("✅ Gemini đã sẵn sàng (đã đăng nhập)")
 
    def select_video_mode_if_needed(self) -> None:
        """
        Bấm vào tab 'Videos' ở sidebar hoặc chuyển hướng trực tiếp để kích hoạt giao diện tạo video.
        """
        self._close_overlays()
        if "/video" in self.page.url:
            logger.info("✅ Đã ở sẵn trong giao diện Videos")
            return
        try:
            logger.info("🎬 Bật chế độ Videos...")
            
            # 1. Định vị tab Videos bằng data-test-id (chờ tối đa 5s để trang render xong)
            videos_tab = self.page.locator('[data-test-id="videos-side-nav-entry-button"] a, [data-test-id="videos-side-nav-entry-button"]').first
            
            # Thử chờ xem tab Videos có hiển thị sẵn không
            try:
                videos_tab.wait_for(state="visible", timeout=3000)
            except Exception:
                pass

            # Nếu tab Videos chưa nhìn thấy (có thể sidebar đang đóng), ta mới mở sidebar
            if not videos_tab.is_visible():
                open_sidebar_btn = self.page.locator('button[aria-label*="Open sidebar"], button[aria-label*="Mở thanh bên"], button[aria-label*="Navigation"], [data-test-id="side-nav-sparkle-button"]').first
                if open_sidebar_btn.is_visible():
                    logger.info("🔓 Phát hiện sidebar đang đóng. Đang mở sidebar...")
                    open_sidebar_btn.click()
                    self._delay()
                    
                # Chờ lại tab Videos sau khi mở sidebar
                try:
                    videos_tab.wait_for(state="visible", timeout=5000)
                except Exception:
                    # Fallback sang selector khác
                    videos_tab = self.page.locator("a:has-text('Videos'), a:has-text('Video')").first
                    try:
                        videos_tab.wait_for(state="visible", timeout=2000)
                    except Exception:
                        pass
            
            if videos_tab.is_visible():
                logger.info("👉 Click chọn tab Videos trên thanh bên...")
                videos_tab.click()
                self._delay()
                # Chờ URL đổi sang /video hoặc /videos
                try:
                    self.page.wait_for_url("**/video*", timeout=8000)
                except Exception:
                    pass
                self.page.wait_for_timeout(3000)
                logger.info("✅ Đã chuyển sang chế độ tạo Videos")
            else:
                # Nếu không nhìn thấy trực tiếp, thử chuyển hướng sang URL /app/video
                logger.warning("⚠️ Không thấy nút Videos trên giao diện. Thử chuyển hướng trực tiếp qua URL...")
                self.page.goto("https://gemini.google.com/app/video", wait_until="domcontentloaded")
                self._delay()
                try:
                    self.page.wait_for_url("**/video*", timeout=8000)
                except Exception:
                    pass
                self.page.wait_for_timeout(3000)
                logger.info("✅ Đã chuyển sang chế độ tạo Videos thành công")
        except Exception as e:
            logger.warning(f"⚠️ Bỏ qua chọn chế độ Videos (có thể đã ở đúng chế độ hoặc gặp lỗi): {e}")

    def upload_image_if_provided(self, image_path: str | None) -> None:
        """Upload ảnh lên Gemini trước khi gõ prompt."""
        if not image_path or not Path(image_path).exists():
            return
        
        logger.info(f"📤 Đang upload ảnh sản phẩm lên Gemini: {image_path}")
        self._close_overlays()
        try:
            # 1. Tìm ô nhập liệu (input "Hỏi Gemini") để xác định vị trí nút "+"
            #    Nút "+" nằm ngay bên trái ô input, cùng hàng
            input_box = self.page.locator(
                'div[contenteditable="true"], '
                'textarea[placeholder*="Gemini"], '
                'textarea[placeholder*="Describe"], '
                'textarea[placeholder*="prompt"]'
            ).first
            input_box.wait_for(state="visible", timeout=10000)
            box = input_box.bounding_box()
            
            if not box:
                logger.error("❌ Không tìm thấy ô nhập liệu Gemini để xác định vị trí nút +")
                return
            
            # Click vào nút "+" — nằm ngay bên trái ô input (khoảng 30-40px về bên trái)
            plus_x = box['x'] - 30
            plus_y = box['y'] + box['height'] / 2
            logger.info(f"👉 Click nút + tại tọa độ ({plus_x:.0f}, {plus_y:.0f})...")
            self.page.mouse.click(plus_x, plus_y)
            self._delay()
 
            # 2. Bắt file chooser khi click vào nút "Upload files" / "Tải tệp lên" trong menu popup
            with self.page.expect_file_chooser() as fc_info:
                menu_item = self.page.locator(
                    "button[role='menuitem']:has-text('Upload files'), "
                    "button[role='menuitem']:has-text('Tải tệp lên'), "
                    "button[role='menuitem']:has-text('Upload'), "
                    "li:has-text('Upload files'), "
                    "li:has-text('Tải tệp lên'), "
                    "div[role='menu'] button:has-text('Upload'), "
                    "button:has-text('Upload files')"
                ).first
                try:
                    menu_item.click(timeout=5000)
                except Exception:
                    menu_item.evaluate("el => el.click()")
                
            file_chooser = fc_info.value
            file_chooser.set_files(image_path)
            logger.info("✅ Đã chọn ảnh thành công, chờ upload hoàn tất...")
            # Đợi 5 giây để ảnh được tải lên hoàn toàn
            self.page.wait_for_timeout(5000)
        except Exception as e:
            logger.error(f"❌ Không thể upload ảnh lên Gemini: {e}")
 
    def generate_video(
        self,
        prompt: str,
        image_path: str | None = None,
        timeout_sec: int = 600,
        product_name: str | None = None,
    ) -> str:
        """
        Gửi prompt tạo video, đợi render xong và tải video về.
        Hỗ trợ Safe Fallback và phát hiện video trùng lặp bằng cách theo dõi danh sách video src.
        """
        self.select_video_mode_if_needed()

        video_file_path = None
        max_limit_retries = 12

        # Check for dance/trending keywords or auto mode
        if "auto" in prompt.lower() or "trending" in prompt.lower() or "dance" in prompt.lower():
            prompt = self._build_trending_dance_prompt(prompt, product_name)

        for retry_idx in range(max_limit_retries):
            existing_sources = set(self._get_all_video_sources())

            if image_path and retry_idx == 0:
                self.upload_image_if_provided(image_path)

            self._close_overlays()
            if retry_idx > 0:
                logger.info(f"✍️ Gửi lại prompt (Lần thử {retry_idx + 1}): {prompt}")
            else:
                logger.info(f"✍️ Gửi prompt: {prompt}")

            # Định vị ô chat
            chat_input = self.page.locator(
                'div[contenteditable="true"], textarea[placeholder*="Describe"], textarea[placeholder*="prompt"]'
            ).first
            try:
                chat_input.click(timeout=5000)
            except Exception:
                logger.warning("⚠️ Không thể click bình thường vào chat input, dùng JavaScript click/focus...")
                chat_input.evaluate("el => { el.focus(); el.click(); }")
            self._delay()
            
            try:
                chat_input.fill(prompt)
            except Exception:
                import json
                chat_input.evaluate(f"el => {{ el.innerText = {json.dumps(prompt)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
            self._delay()

            # Đếm số lượng phản hồi hiện tại trước khi gửi
            initial_response_count = self.page.locator(
                'message-content, [data-test-id="response-container"], .model-response, .message-content'
            ).count()

            # Bấm nút gửi (send button)
            send_btn = self.page.locator(
                'button[aria-label*="Send"], button[aria-label*="Gửi"], button[class*="send-button"]'
            ).first
            try:
                send_btn.click(timeout=5000)
            except Exception:
                logger.warning("⚠️ Không thể click bình thường vào send button, dùng JavaScript click...")
                send_btn.evaluate("el => el.click()")
            logger.info("⏳ Đang gửi yêu cầu tạo video...")
            self._delay()

            # Đợi render video
            start_time = time.time()
            safety_blocked = False
            limit_blocked = False

            logger.info("⏳ Chờ Gemini render video (có thể mất 1-3 phút)...")
            while time.time() - start_time < timeout_sec:
                # Check xem có video mới không
                videos = self.page.locator('video')
                count = videos.count()
                has_new_video = count > len(existing_sources)
                
                if has_new_video:
                    new_video = videos.nth(count - 1)
                    src = new_video.get_attribute("src")
                    if src and (src.startswith("http") or src.startswith("blob:")) and src not in existing_sources:
                        logger.info(f"🎥 Đã phát hiện thấy video element mới! source: {src}")
                        video_file_path = self._download_video_content(src)
                        if video_file_path:
                            break

                # Kiểm tra bộ lọc an toàn và giới hạn sau 10 giây (chỉ check khi không có video mới và ĐÃ XUẤT HIỆN BONG BÓNG CHAT MỚI)
                if not has_new_video and time.time() - start_time > 10:
                    current_responses = self.page.locator(
                        'message-content, [data-test-id="response-container"], .model-response, .message-content'
                    )
                    if current_responses.count() > initial_response_count:
                        latest_text = (current_responses.nth(current_responses.count() - 1).text_content() or "").strip()
                        
                        if self._check_daily_limit(latest_text):
                            logger.error("❌ Hết giới hạn tạo video trong ngày cho tài khoản này!")
                            raise RuntimeError("GEMINI_DAILY_LIMIT_EXCEEDED")
                            
                        if self._check_limit_refusal(latest_text):
                            logger.warning(f"⚠️ Phát hiện giới hạn tạo video của Gemini (2 videos song song)!")
                            limit_blocked = True
                            break
                            
                        if self._check_safety_refusal(latest_text):
                            logger.warning("⚠️ Phát hiện Gemini từ chối render! Sẽ tự động gửi lại prompt cũ...")
                            safety_blocked = True
                            break
                
                time.sleep(2)

            if limit_blocked:
                logger.info("⏳ Đang đợi 60 giây để hàng đợi tạo video của tài khoản trống rồi gửi lại...")
                time.sleep(60)
                continue

            # Nếu bị safety block, gửi lại chính prompt cũ (giống copy-paste lại)
            if safety_blocked:
                logger.info("🔄 Gửi lại prompt cũ (retry tự động)...")
                self.page.wait_for_timeout(3000)
                continue

            break

        if not video_file_path:
            raise TimeoutError("❌ Đã quá thời gian chờ (timeout) hoặc Gemini từ chối render sau nhiều lần thử lại.")

        return video_file_path

    def _download_video_content(self, src: str) -> str | None:
        """Tải video qua blob src hoặc nút download và lưu vào thư mục videos/"""
        output_dir = Path(self.config.get("videos_dir", "./videos"))
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gemini_video_{int(time.time())}.mp4"
        file_path = output_dir / filename

        try:
            # Cách 1: Nếu là blob URL, download trực tiếp qua JS Context để tránh lỗi CORS/Session
            if src.startswith("blob:"):
                logger.info("📥 Đang tải video dạng blob qua Browser Context...")
                js_download_blob = """
                async (blobUrl) => {
                    const response = await fetch(blobUrl);
                    const blob = await response.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                }
                """
                base64_data = self.page.evaluate(js_download_blob, src)
                video_bytes = base64.b64decode(base64_data)
                
                with open(file_path, "wb") as f:
                    f.write(video_bytes)
                
                logger.info(f"✅ Tải video thành công: {file_path}")
                return str(file_path)

            # Cách 2: Nếu là link direct URL thông thường
            else:
                logger.info("📥 Đang tải video qua direct link...")
                # Thử tìm nút download trên giao diện của video
                download_btn = self.page.locator(
                    'button[aria-label*="Download"], button[aria-label*="Tải"], a[download]'
                ).last
                
                if download_btn.is_visible():
                    with self.page.expect_download() as download_info:
                        download_btn.click()
                    download = download_info.value
                    download.save_as(str(file_path))
                    logger.info(f"✅ Tải video thành công: {file_path}")
                    return str(file_path)
                
                # Nếu không có nút, fetch trực tiếp bằng JS
                logger.info("⚠️ Không thấy nút download, tải trực tiếp bằng fetch...")
                js_fetch = """
                async (url) => {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    return new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.readAsDataURL(blob);
                    });
                }
                """
                base64_data = self.page.evaluate(js_fetch, src)
                video_bytes = base64.b64decode(base64_data)
                with open(file_path, "wb") as f:
                    f.write(video_bytes)
                logger.info(f"✅ Tải video thành công: {file_path}")
                return str(file_path)

        except Exception as e:
            logger.error(f"❌ Lỗi khi tải video: {e}")
            return None

    def _get_all_video_sources(self) -> list[str]:
        """Lấy tất cả các video src hiện tại trên trang."""
        sources = []
        try:
            videos = self.page.locator('video')
            for i in range(videos.count()):
                src = videos.nth(i).get_attribute("src")
                if src:
                    sources.append(src)
        except Exception:
            pass
        return sources

    def _get_latest_response_text(self) -> str:
        """Lấy văn bản phản hồi mới nhất của Gemini để kiểm tra lỗi hoặc từ chối."""
        try:
            responses = self.page.locator('message-content, [data-test-id="response-container"], .model-response, .message-content')
            count = responses.count()
            if count > 0:
                text = (responses.nth(count - 1).text_content() or "").strip()
                return text
        except Exception as e:
            logger.debug(f"Không thể đọc phản hồi mới nhất: {e}")
        return ""

    def _check_safety_refusal(self, text: str) -> bool:
        """Kiểm tra xem văn bản phản hồi của Gemini có chứa từ khóa từ chối không."""
        refusal_keywords = [
            "can't help", "can't make", "can't create", "can't generate",
            "cannot make", "cannot create", "cannot generate",
            "i can't", "i cannot", "i'm unable",
            "unable to", "not able to",
            "safety policy", "chính sách an toàn", 
            "không thể giúp", "không thể tạo", "không tạo được",
            "an toàn", "nhạy cảm", 
            "vi phạm", "tiếc là", "sorry", "apologize", "tôi không thể",
            "that type of video", "this type of video",
            "can i help you with something else",
        ]
        text_lower = text.lower()
        for kw in refusal_keywords:
            if kw in text_lower:
                return True
        return False

    def _check_limit_refusal(self, text: str) -> bool:
        """Kiểm tra xem Gemini có báo đạt giới hạn tạo video song song không."""
        limit_keywords = [
            "yêu cầu tạo video", "số lượng tối đa", "độ dài tối đa", 
            "limit of video", "maximum number of video", "too many video requests",
            "active video request", "tối đa mà tôi có thể xử lý"
        ]
        text_lower = text.lower()
        for kw in limit_keywords:
            if kw in text_lower:
                return True
        return False

    def _check_daily_limit(self, text: str) -> bool:
        """Kiểm tra xem Gemini có báo hết lượt tạo video trong ngày không."""
        daily_limit_keywords = [
            "can't generate more videos for you today",
            "come back tomorrow",
            "reached your daily limit",
            "hết lượt tạo video",
            "quay lại vào ngày mai",
            "hẹn gặp lại ngày mai",
            "cannot generate more videos",
            "cannot make more videos today",
        ]
        text_lower = text.lower()
        for kw in daily_limit_keywords:
            if kw in text_lower:
                return True
        return False

    def _determine_product_type(self, product_name: str) -> str:
        name_lower = product_name.lower()
        
        # 1. Nhóm thời trang
        clothing_keywords = [
            "váy", "đầm", "áo", "quần", "set bộ", "set đồ", "bộ quần áo", 
            "tutu", "midi", "croptop", "hoodie", "cardigan", "blazer", "jacket"
        ]
        # 2. Nhóm giày dép
        footwear_keywords = [
            "giày", "dép", "sandal", "guốc", "boot", "sneaker", "cao gót"
        ]
        
        for kw in clothing_keywords:
            if kw in name_lower:
                return "clothing"
                
        for kw in footwear_keywords:
            if kw in name_lower:
                return "footwear"
                
        return "other"

    def _clean_product_name(self, product_name: str) -> str:
        if not product_name:
            return "sản phẩm"
        name_lower = product_name.lower()
        
        core_keywords = [
            "váy dự tiệc", "váy công sở", "váy tiểu thư", "váy dáng dài", "váy xòe", "váy",
            "đầm dự tiệc", "đầm công sở", "đầm tiểu thư", "đầm dáng dài", "đầm",
            "áo sơ mi", "áo thun", "áo phông", "áo khoác", "áo croptop", "áo hoodie", "áo len", "áo nỉ", "áo",
            "quần jeans", "quần jean", "quần tây", "quần short", "quần dài", "quần",
            "set bộ", "set đồ", "bộ quần áo",
            "giày sneaker", "giày cao gót", "giày tây", "giày thể thao", "giày",
            "dép quai ngang", "dép sandal", "dép", "sandal", "guốc",
            "tai nghe bluetooth", "tai nghe không dây", "tai nghe", "loa bluetooth", "loa không dây", "loa",
            "sạc dự phòng", "củ sạc nhanh", "củ sạc", "cáp sạc", "dây sạc", "chuột không dây", "chuột máy tính",
            "bàn phím cơ", "bàn phím bluetooth", "bàn phím", "quạt tích điện", "quạt mini", "quạt",
            "ốp lưng", "kính cường lực", "giá đỡ điện thoại",
            "kem chống nắng", "sữa rửa mặt", "nước hoa", "son kem", "son thỏi", "son môi", "son",
            "serum dưỡng da", "serum", "kem dưỡng ẩm", "kem dưỡng", "tẩy trang",
            "nồi chiên không dầu", "máy xay sinh tố", "bình giữ nhiệt", "quạt để bàn", "đèn học chống cận", "đèn học",
            "kệ để đồ", "hộp đựng thức ăn"
        ]
        
        for kw in core_keywords:
            if kw in name_lower:
                idx = name_lower.find(kw)
                words = product_name[idx:].split()
                cleaned = " ".join(words[:3])
                return cleaned.rstrip(",.-/ ")

        words = product_name.split()
        if len(words) > 5:
            return " ".join(words[:5]).rstrip(",.-/ ")
        return product_name

    def _determine_gender(self, product_name: str, product_description: str | None = None) -> str:
        """Xác định giới tính của sản phẩm dựa trên tên và mô tả sản phẩm."""
        import re
        name_lower = product_name.lower()
        desc_lower = (product_description or "").lower()
        
        # Loại bỏ cụm từ "việt nam", "vietnam", "viet nam" trước khi kiểm tra
        name_for_check = name_lower.replace("việt nam", "").replace("vietnam", "").replace("viet nam", "")
        desc_for_check = desc_lower.replace("việt nam", "").replace("vietnam", "").replace("viet nam", "")
        
        # Từ khóa chỉ nam giới
        male_words = ["nam", "men", "man", "mens", "con trai", "mr", "gentleman", "gentlemen"]
        
        for word in male_words:
            pattern = f"\\b{word}\\b"
            if re.search(pattern, name_for_check) or re.search(pattern, desc_for_check):
                return "male"
                
        return "female"

    def _build_trending_dance_prompt(self, original_prompt: str, product_name: str | None) -> str:
        """Xây dựng prompt chuyên biệt cho các yêu cầu nhảy hoặc xu hướng thu hút người mua."""
        cleaned_name = self._clean_product_name(product_name) if product_name else "sản phẩm"
        gender = self._determine_gender(product_name or "")
        
        if gender == "male":
            model_desc = "A handsome and stylish young Vietnamese male model"
            pronoun = "He"
        else:
            model_desc = "A beautiful and stylish young Vietnamese model"
            pronoun = "She"
            
        return (
            f"Aesthetic TikTok fashion styling video, 9:16 vertical, high-energy cinematic style. "
            f"{model_desc} showing how to style '{cleaned_name}' for an everyday look. "
            f"{pronoun} walks confidently towards the camera with a bright smile, strikes a cool pose, and does a fast fashion transition (outfit change or pose shift) synchronized to the beat. "
            "Dynamic camera angles, warm soft studio lighting, high video quality. "
            "REQUIRED: The product must be clearly visible, looking extremely fashionable and attractive. "
            "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending) with a strong upbeat drop, clearly audible. "
            "No text, no watermark. Duration 10 seconds."
        )

    def _build_segment_prompt(self, base_prompt: str, product_name: str, segment_index: int, total_segments: int, product_description: str | None = None) -> str:
        """
        Tạo prompt chi tiết cho từng phân đoạn video.
        """
        if "trending" in base_prompt.lower() or "dance" in base_prompt.lower():
            return self._build_trending_dance_prompt(base_prompt, product_name)

        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        gender = self._determine_gender(product_name, product_description)
        
        if gender == "male":
            subject = "A handsome young Vietnamese man"
            pronoun = "He"
            voice_xinh_qua = "chất quá cả nhà ơi, chất vải mềm mịn thích lắm luôn!"
            voice_xinh_xiu = f"Đôi {cleaned_name} chất xỉu luôn, nhìn là mê ngay á mọi người!"
            voice_xinh_tien = f"Món {cleaned_name} này nhìn là thích luôn, thiết kế đẹp và tiện lắm mọi người ơi!"
            voice_xinh_ky_feet = "chất cực kỳ"
        else:
            subject = "A beautiful young Vietnamese woman"
            pronoun = "She"
            voice_xinh_qua = "xinh quá cả nhà ơi, chất vải mềm mịn thích lắm luôn!"
            voice_xinh_xiu = f"Đôi {cleaned_name} xinh xỉu luôn, nhìn là mê ngay á mọi người!"
            voice_xinh_tien = f"Món {cleaned_name} này nhìn là thích luôn, thiết kế xinh và tiện lắm mọi người ơi!"
            voice_xinh_ky_feet = "xinh cực kỳ"

        desc_hint = f"Thông tin mô tả sản phẩm: {product_description}\n" if product_description else ""

        if segment_index == 0:
            if prod_type == "clothing":
                return (
                    f"Viral TikTok OOTD outfit-check video clip, 9:16 vertical, cinematic aesthetic. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' clothing (reference image provided). "
                    f"{subject} in a bright aesthetic room with warm lighting. "
                    f"{pronoun} holds the clothing item close to camera, showing fabric texture and design details with a natural smile. "
                    f"Quick smooth cuts: close-up of fabric, label, stitching detail. Natural relaxed expression, not scripted. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and energetic, clearly audible. "
                    f"Soft Vietnamese voiceover blended with music: 'Mẫu {cleaned_name} này {voice_xinh_qua}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"Viral TikTok shoe haul video clip, 9:16 vertical, aesthetic style. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' footwear (reference image provided). "
                    f"{subject} in a stylish setting holds the shoes close to camera. "
                    "Quick aesthetic cuts: shoe sole detail, side profile, material close-up. Natural delighted expression. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and catchy, clearly audible. "
                    f"Soft Vietnamese voiceover blended with music: {voice_xinh_xiu} "
                    "No text, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"Viral TikTok product unboxing clip, 9:16 vertical, aesthetic style. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' (reference image provided). "
                    f"{subject} holds the product near camera showing design and features. "
                    "Quick aesthetic cuts: product detail close-ups, packaging, key features. Natural happy expression. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and fun, clearly audible. "
                    f"Soft Vietnamese voiceover blended with music: {voice_xinh_tien} "
                    "No text, no watermark. Duration 10 seconds."
                )

        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                return (
                    f"Viral TikTok OOTD try-on video clip, 9:16 vertical, aesthetic cinematic style. "
                    f"Product: '{cleaned_name}' outfit. "
                    f"{subject} is wearing the outfit in a well-lit aesthetic setting. "
                    f"{pronoun} does a natural 360 spin showing the full outfit, walks gracefully, poses confidently. "
                    "Multiple smooth aesthetic cuts: full body shot, waist detail, side profile. Bright natural smile. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and energetic, clearly audible throughout. "
                    f"Soft Vietnamese voiceover with music: 'Mặc lên phom chuẩn tôn dáng cực kỳ! {cleaned_name} này đáng mua lắm, bấm giỏ hàng ngay nha cả nhà!' "
                    "No text, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"Viral TikTok shoe try-on video clip, 9:16 vertical, aesthetic style. "
                    f"Product: '{cleaned_name}' footwear. "
                    f"{subject} wearing the shoes, walking gracefully in a stylish setting. "
                    "Smooth aesthetic cuts: feet/shoes walking, full outfit from ground up, close-up of shoes in motion. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), catchy and upbeat, clearly audible throughout. "
                    f"Soft Vietnamese voiceover with music: 'Đi vào êm và {voice_xinh_ky_feet}! {cleaned_name} hack dáng dã man luôn, bấm giỏ hàng ngay nhé!' "
                    "No text, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"Viral TikTok product demo clip, 9:16 vertical, aesthetic style. "
                    f"Product: '{cleaned_name}'. "
                    f"{subject} demonstrates using the product with genuine delight and satisfaction. "
                    "Smooth aesthetic cuts: product in use, feature highlights, happy reaction shots. "
                    "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and energetic, clearly audible throughout. "
                    f"Soft Vietnamese voiceover with music: '{cleaned_name} dùng siêu thích, tiện và đáng tiền lắm mọi người! Bấm mua ngay nhé!' "
                    "No text, no watermark. Duration 10 seconds."
                )

        else:
            if gender == "male":
                action_desc = "cậu ấy xoay người nhẹ nhàng khoe chi tiết."
            else:
                action_desc = "cô gái xoay người nhẹ nhàng khoe chi tiết."
            return (
                f"Render video demo bổ sung (tỉ lệ dọc 9:16) cho sản phẩm '{cleaned_name}'. "
                f"Nội dung: Camera quay cận cảnh {action_desc} "
                "QUAN TRỌNG: Nhạc nền phải là bài nhạc Việt đang viral trending trên TikTok Việt Nam (V-pop, nhạc trẻ), sôi động và bắt tai, nghe rõ ràng. "
                "QUAN TRỌNG: Video phải có âm thanh thuyết minh giọng nói tiếng Việt tự nhiên hòa với nhạc nền. "
                "Không chữ, không watermark. Thời lượng 10 giây."
            )

    def _build_safe_fallback_prompt(self, product_name: str, segment_index: int, total_segments: int) -> str:
        """Prompt dự phòng an toàn: chỉ sản phẩm + nhạc nền, không người, đảm bảo qua safety filter."""
        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        duration = 10

        if prod_type == "clothing":
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Fashion item '{cleaned_name}' displayed on a stylish hanger. "
                "Camera slowly pans and rotates around the item, macro close-up of fabric texture and stitching. "
                "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and catchy, clearly audible. "
                f"No people, no text, no watermark. Duration {duration} seconds."
            )
        elif prod_type == "footwear":
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Footwear '{cleaned_name}' displayed on a clean surface with beautiful lighting. "
                "Camera slowly pulls back for a full product reveal, macro close-up of material and sole detail. "
                "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and catchy, clearly audible. "
                f"No people, no text, no watermark. Duration {duration} seconds."
            )
        else:
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Product '{cleaned_name}' displayed on a clean surface with beautiful lighting. "
                "Camera slowly pans around the item, macro close-up of key features and design. "
                "REQUIRED: Background music must be a currently viral Vietnamese TikTok song (V-pop, nhạc Việt trending trên TikTok Việt Nam), upbeat and energetic, clearly audible. "
                f"No people, no text, no watermark. Duration {duration} seconds."
            )

    def generate_multi_segment_video(
        self,
        prompt: str,
        product_name: str,
        image_path: str | None = None,
        num_segments: int = 2,
        timeout_sec: int = 600,
        product_description: str | None = None,
    ) -> str:
        """
        Tạo nhiều clip nối tiếp trong cùng 1 tab Gemini và ghép lại bằng ffmpeg.
        """
        logger.info(f"🎬 Bắt đầu quy trình tạo video đa phân đoạn ({num_segments} clips) cho: {product_name}")
        self.select_video_mode_if_needed()

        segment_videos = []
        
        for i in range(num_segments):
            logger.info(f"📹 [Clip {i+1}/{num_segments}] Đang sinh...")
            
            # Xây dựng prompt cho clip hiện tại
            seg_prompt = self._build_segment_prompt(prompt, product_name, i, num_segments, product_description=product_description)
            
            video_file_path = None
            max_limit_retries = 12
            
            for retry_idx in range(max_limit_retries):
                # Lưu danh sách video src hiện tại để phát hiện video mới
                existing_sources = set(self._get_all_video_sources())
                
                if i == 0 and image_path and retry_idx == 0:
                    self.upload_image_if_provided(image_path)
                
                self._close_overlays()
                if retry_idx > 0:
                    logger.info(f"✍️ Gửi lại prompt phân đoạn {i+1} (Lần thử {retry_idx + 1}): {seg_prompt}")
                else:
                    logger.info(f"✍️ Gửi prompt phân đoạn {i+1}: {seg_prompt}")
                
                # Định vị ô chat và nhập prompt
                chat_input = self.page.locator(
                    'div[contenteditable="true"], textarea[placeholder*="Describe"], textarea[placeholder*="prompt"]'
                ).first
                try:
                    chat_input.click(timeout=5000)
                except Exception:
                    chat_input.evaluate("el => { el.focus(); el.click(); }")
                self._delay()
                
                try:
                    chat_input.fill(seg_prompt)
                except Exception:
                    import json
                    chat_input.evaluate(f"el => {{ el.innerText = {json.dumps(seg_prompt)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
                self._delay()
                
                # Đếm số lượng phản hồi hiện tại trước khi gửi
                initial_response_count = self.page.locator(
                    'message-content, [data-test-id="response-container"], .model-response, .message-content'
                ).count()

                # Bấm nút gửi
                send_btn = self.page.locator(
                    'button[aria-label*="Send"], button[aria-label*="Gửi"], button[class*="send-button"]'
                ).first
                try:
                    send_btn.click(timeout=5000)
                except Exception:
                    send_btn.evaluate("el => el.click()")
                logger.info("⏳ Đang gửi yêu cầu...")
                self._delay()
                
                # Đợi xem video mới xuất hiện, bị safety block hoặc dính giới hạn 2 video song song
                start_wait = time.time()
                safety_blocked = False
                limit_blocked = False
                
                while time.time() - start_wait < timeout_sec:
                    # 1. Kiểm tra xem có video mới không
                    videos = self.page.locator('video')
                    count = videos.count()
                    
                    # Nếu số lượng video lớn hơn số video cũ
                    has_new_video = count > len(existing_sources)
                    if has_new_video:
                        # Lấy video mới nhất
                        new_video = videos.nth(count - 1)
                        src = new_video.get_attribute("src")
                        if src and (src.startswith("http") or src.startswith("blob:")) and src not in existing_sources:
                            logger.info(f"🎥 Đã phát hiện thấy video element phân đoạn mới! source: {src}")
                            video_file_path = self._download_video_content(src)
                            if video_file_path:
                                break
                    
                    # 2. Kiểm tra lỗi giới hạn và safety block (chỉ check sau 10s, khi không có video mới và ĐÃ XUẤT HIỆN BONG BÓNG CHAT MỚI)
                    if not has_new_video and time.time() - start_wait > 10:
                        current_responses = self.page.locator(
                            'message-content, [data-test-id="response-container"], .model-response, .message-content'
                        )
                        if current_responses.count() > initial_response_count:
                            latest_text = (current_responses.nth(current_responses.count() - 1).text_content() or "").strip()
                            
                            if self._check_daily_limit(latest_text):
                                logger.error("❌ Hết giới hạn tạo video trong ngày cho tài khoản này!")
                                raise RuntimeError("GEMINI_DAILY_LIMIT_EXCEEDED")
                                
                            if self._check_limit_refusal(latest_text):
                                logger.warning(f"⚠️ Phát hiện giới hạn tạo video của Gemini (2 videos song song)!")
                                limit_blocked = True
                                break
                                
                            if self._check_safety_refusal(latest_text):
                                logger.warning(f"⚠️ Phát hiện Gemini từ chối render phân đoạn {i+1}! Sẽ tự động gửi lại prompt cũ...")
                                safety_blocked = True
                                break
                    
                    time.sleep(2)
                
                if limit_blocked:
                    logger.info("⏳ Đang đợi 60 giây để hàng đợi tạo video của tài khoản trống rồi gửi lại...")
                    time.sleep(60)
                    continue
                
                # Nếu bị safety block, gửi lại chính prompt cũ (giống copy-paste lại)
                if safety_blocked:
                    logger.info("🔄 Gửi lại prompt cũ cho phân đoạn (retry tự động)...")
                    self.page.wait_for_timeout(3000)
                    continue
                
                # Nếu không bị block, break ra khỏi vòng lặp retry
                break
                
            if not video_file_path:
                raise RuntimeError(f"❌ Không thể tạo video cho phân đoạn {i+1} sau {max_limit_retries} lần thử.")
            
            logger.info(f"✅ Đã tải xong video phân đoạn {i+1}: {video_file_path}")
            segment_videos.append(video_file_path)
            
            # Đợi một chút trước khi chuyển sang segment tiếp theo
            self.page.wait_for_timeout(5000)
            
        # Ghép tất cả các clip phân đoạn lại
        from src.utils import concatenate_videos
        output_dir = Path(self.config.get("videos_dir", "./videos"))
        output_dir.mkdir(parents=True, exist_ok=True)
        final_video_name = f"gemini_final_{int(time.time())}.mp4"
        final_video_path = str(output_dir / final_video_name)
        
        logger.info(f"🔗 Đang ghép {len(segment_videos)} phân đoạn thành video cuối cùng...")
        final_video = concatenate_videos(segment_videos, final_video_path)
        logger.info(f"🎉 Video hoàn chỉnh được tạo tại: {final_video}")
        return final_video

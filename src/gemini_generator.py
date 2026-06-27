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

    def _click_send_button(self) -> None:
        """Tìm và bấm nút gửi tin nhắn một cách thông minh, loại trừ nút Feedback/Phản hồi."""
        selectors = [
            'button[aria-label="Send message"]',
            'button[aria-label="Gửi tin nhắn"]',
            'button[aria-label*="Send"]:visible',
            'button[aria-label*="Gửi"]:visible',
            '.send-button:visible',
            'button[class*="send-button"]:visible'
        ]
        
        send_btn = None
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                count = loc.count()
                for i in range(count):
                    btn = loc.nth(i)
                    label = (btn.get_attribute("aria-label") or "").lower()
                    # Bỏ qua nếu là nút feedback / phản hồi
                    if "feedback" in label or "phản hồi" in label:
                        continue
                    if btn.is_visible():
                        send_btn = btn
                        break
                if send_btn:
                    break
            except Exception:
                continue
                
        if send_btn:
            try:
                send_btn.click(timeout=3000)
                logger.info("✅ Đã bấm nút gửi thành công!")
            except Exception:
                logger.warning("⚠️ Không thể click bình thường vào nút gửi, dùng JS click...")
                try:
                    send_btn.evaluate("el => el.click()")
                    logger.info("✅ Đã bấm nút gửi bằng JS thành công!")
                except Exception as e:
                    logger.error(f"❌ Thất bại khi bấm nút gửi bằng JS: {e}")
                    raise e
        else:
            logger.warning("⚠️ Không tìm thấy nút gửi qua bộ lọc thông minh, thử dùng selector mặc định...")
            fallback_btn = self.page.locator(
                'button[aria-label*="Send"], button[aria-label*="Gửi"], button[class*="send-button"]'
            ).first
            try:
                fallback_btn.click(timeout=3000)
                logger.info("✅ Đã bấm nút gửi (fallback) thành công!")
            except Exception:
                fallback_btn.evaluate("el => el.click()")
                logger.info("✅ Đã bấm nút gửi (fallback JS) thành công!")

    def open_gemini(self) -> None:
        logger.info("🌐 Mở Google Gemini App...")
        try:
            self.page.goto(self.GEMINI_APP_URL, wait_until="load", timeout=30000)
        except Exception as e:
            logger.warning(f"⚠️ Cảnh báo khi load trang Gemini: {e}")
        self._delay()
        self._close_overlays()
 
        # Check xem đã login chưa — thử tối đa 2 lần (lần 2 reload lại trang)
        max_login_checks = 2
        is_logged_in = False
        
        for check_idx in range(max_login_checks):
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
            
            if is_logged_in:
                break
            
            # Nếu chưa login và còn lần thử, reload trang
            if check_idx < max_login_checks - 1:
                logger.warning("⚠️ Chưa phát hiện đăng nhập, thử reload lại trang Gemini...")
                try:
                    self.page.reload(wait_until="load", timeout=30000)
                except Exception:
                    pass
                self._delay()
                self._close_overlays()
            
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
            logger.info("⏳ Đang gửi yêu cầu tạo video...")
            self._click_send_button()
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
                        'message-content, [data-test-id="response-container"], .model-response, .message-content, [role="alert"], .inline-alert, .error-message'
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
            "cannot generate more videos for you today",
            "can't generate any more videos for you today",
            "cannot generate any more videos for you today",
            "come back tomorrow",
            "reached your daily limit",
            "reached the daily limit",
            "daily limit for video",
            "hết lượt tạo video",
            "không thể tạo thêm video",
            "quay lại vào ngày mai",
            "hẹn gặp lại ngày mai",
            "cannot generate more videos",
            "cannot make more videos today",
            "today, but i can still",
            "hôm nay, nhưng tôi vẫn có thể",
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

    def _extract_useful_description(self, product_description: str | None) -> str:
        """Trích xuất thông tin hữu ích từ mô tả sản phẩm, loại bỏ giá, rating, shipping, noise."""
        if not product_description:
            return ""
        import re
        # Loại bỏ các dòng/cụm nhiễu
        noise_patterns = [
            r'Free\s*shipp?ing', r'Deal', r'\d+\.\d+\s*$',  # rating like 4.8
            r'\d+\s*sold', r'₫[\d,.]+', r'\$[\d,.]+',  # price
            r'MUA\s*\d+\s*G[Ii][Ảả][Mm].*', r'KÈM\s*QUÀ',  # promo
            r'Free\s*ship', r'Giảm\s*\d+',
        ]
        lines = product_description.split('\n')
        useful_lines = []
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            is_noise = False
            for pat in noise_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    is_noise = True
                    break
            # Bỏ dòng chỉ có số
            if re.match(r'^[\d,.₫$%\s]+$', line):
                is_noise = True
            if not is_noise:
                useful_lines.append(line)
        # Chỉ lấy tối đa 2 dòng hữu ích nhất (tên + đặc điểm)
        result = ' | '.join(useful_lines[:2])
        # Giới hạn 150 ký tự để prompt không bị quá dài
        return result[:150] if result else ""

    def _pick_consistent_music(self, product_name: str) -> str:
        """Chọn 1 bài nhạc Việt trending cụ thể dựa trên seed từ tên sản phẩm.
        Đảm bảo tất cả segments của cùng 1 sản phẩm dùng cùng 1 bài nhạc."""
        trending_songs = [
            "'Waiting For You' của MONO",
            "'See Tình' của Hoàng Thùy Linh",
            "'Có Hẹn Với Thanh Xuân' của MONSTAR",
            "'Ngắm Hoa Lệ Rơi' phong cách remix TikTok",
            "'Đừng Làm Trái Tim Anh Đau' của Sơn Tùng MTP",
            "'Em Là' của GREY D",
            "'Là Anh' của Phạm Lịch",
            "'Dù Cho Tận Thế' phong cách lofi chill",
            "'Cắt Đôi Nỗi Sầu' của Tăng Duy Tân remix",
            "'Ghé Qua' của Dick x PC",
        ]
        seed = sum(ord(c) for c in (product_name or "product"))
        return trending_songs[seed % len(trending_songs)]

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
                return cleaned.rstrip(",.-/()[]{} ")

        words = product_name.split()
        if len(words) > 5:
            return " ".join(words[:5]).rstrip(",.-/()[]{} ")
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

    def _generate_tiktok_voiceover(
        self,
        product_name: str,
        product_description: str | None,
        gender: str,
        segment_index: int,
        total_segments: int,
        prod_type: str
    ) -> str:
        """Sinh giọng đọc thuyết minh tự nhiên và đa dạng chuẩn TikTok dựa trên loại sản phẩm và giới tính."""
        cleaned_name = self._clean_product_name(product_name)
        
        # Tạo seed từ tên sản phẩm để các clip của cùng sản phẩm có kịch bản nhất quán
        seed = sum(ord(c) for c in cleaned_name)
        
        # Hooks (segment 0)
        if gender == "male":
            hooks_clothing = [
                f"Mẫu {cleaned_name} này chất quá cả nhà ơi, chất vải mềm mịn sờ sướng tay cực kỳ!",
                f"Review thực tế cho anh em mẫu {cleaned_name} siêu hot hit này nha, nhìn cái phom là thấy ưng rồi!",
                f"Anh em nào đang tìm {cleaned_name} đi chơi đi làm thì bơi hết vào đây xem cận cảnh nè!",
                f"Đúng là chân ái của anh em đây rồi, mẫu {cleaned_name} lên đồ là bao ngầu luôn!"
            ]
            hooks_footwear = [
                f"Đôi {cleaned_name} chất xỉu luôn anh em ơi, lên chân bao êm bao ngầu!",
                f"Hé lộ mẫu {cleaned_name} đang làm mưa làm gió trên TikTok, thiết kế cực kỳ thể thao!",
                f"Cận cảnh em {cleaned_name} siêu đẹp cho anh em đây, chất da/vải siêu bền nhé!",
                f"Lần đầu tiên thấy một đôi {cleaned_name} đẹp thế này, phom chuẩn không cần chỉnh luôn!"
            ]
            hooks_other = [
                f"Món {cleaned_name} này cực kỳ xịn sò anh em ơi, thiết kế thông minh và tiện lợi lắm!",
                f"Review thực tế em {cleaned_name} cho cả nhà, cầm trên tay chắc chắn cực kỳ!",
                f"Anh em nào mê công nghệ/đồ tiện ích thì không thể bỏ qua em {cleaned_name} này nha!",
                f"Unboxing siêu phẩm {cleaned_name} đang siêu hot gần đây, dùng là ghiền luôn!"
            ]
        else: # female
            hooks_clothing = [
                f"Mẫu {cleaned_name} này xinh quá cả nhà ơi, chất vải mềm mịn thích lắm luôn!",
                f"Review thực tế cho chị em mẫu {cleaned_name} siêu hot hit này nha, mặc lên là xinh lung linh luôn!",
                f"Chị em nào đang tìm {cleaned_name} đi chơi đi tiệc thì bơi hết vào đây xem cận cảnh nè!",
                f"Đúng là chân ái của chị em mình đây rồi, mẫu {cleaned_name} này mặc tôn dáng dã man!"
            ]
            hooks_footwear = [
                f"Đôi {cleaned_name} xinh xỉu luôn mọi người ơi, nhìn cái là mê ngay á!",
                f"Hé lộ đôi {cleaned_name} đang làm mưa làm gió trên TikTok, hack dáng cực đỉnh luôn!",
                f"Cận cảnh em {cleaned_name} siêu dễ thương cho chị em đây, đi êm chân lắm nhé!",
                f"Lần đầu tiên thấy một đôi {cleaned_name} xinh thế này, phối đồ bánh bèo hay năng động đều hợp!"
            ]
            hooks_other = [
                f"Món {cleaned_name} này xinh và tiện lắm mọi người ơi, nhìn cái là thích ngay luôn!",
                f"Review thực tế em {cleaned_name} cho cả nhà, thiết kế nhỏ gọn xinh xắn lắm!",
                f"Chị em nào thích đồ xinh xịn mịn thì không thể bỏ qua em {cleaned_name} này đâu nha!",
                f"Unboxing siêu phẩm {cleaned_name} đang siêu hot gần đây, decor hay dùng đều mê!"
            ]

        # Mid body reviews
        mid_clothing = [
            "Đường kim mũi chỉ được may cực kỳ tỉ mỉ, sờ vào thấy ngay sự cao cấp.",
            "Chất vải co giãn thoải mái, thấm hút mồ hôi tốt nên mặc cả ngày không sợ nóng bí.",
            "Từng chi tiết cúc áo và đường viền được hoàn thiện rất tốt, phom lên chuẩn chỉ cực kỳ.",
            "Thiết kế trẻ trung, màu sắc tôn da phối đồ siêu dễ luôn mọi người ạ."
        ]
        mid_footwear = [
            "Đế giày được làm từ cao su chống trơn trượt, đi bộ hay chạy nhảy đều cực kỳ thoải mái.",
            "Từng đường keo mũi chỉ rất chắc chắn, lớp lót bên trong êm ái bảo vệ gót chân.",
            "Phom giày ôm chân gọn gàng, tạo cảm giác nhẹ nhàng thanh thoát khi di chuyển.",
            "Màu sắc basic cực dễ phối đồ, đi học đi làm hay đi chơi đều nổi bật."
        ]
        mid_other = [
            "Chất liệu cao cấp, độ hoàn thiện cao, dùng cực kỳ bền bỉ theo thời gian.",
            "Tính năng thông minh giúp tiết kiệm thời gian, cực kỳ tiện lợi cho cuộc sống hàng ngày.",
            "Màu sắc tối giản hiện đại, mang đi học đi làm hay để bàn làm việc đều rất sang.",
            "Cầm cực kỳ đầm tay, các nút bấm và cổng kết nối hoạt động siêu mượt mà."
        ]

        # Call To Action (last segment)
        if gender == "male":
            ctas_clothing = [
                f"Mặc lên phom chuẩn bao đẹp luôn anh em! Mẫu {cleaned_name} này đáng mua lắm, bấm giỏ hàng góc trái săn sale nha!",
                f"Lên đồ cực chất mà giá lại hạt dẻ. Anh em tranh thủ chốt ngay mẫu {cleaned_name} ở giỏ hàng bên dưới nha!",
                f"Nói chung là 10 trên 10 cực kỳ đáng tiền luôn. Link mua em {cleaned_name} ở ngay góc trái màn hình nha anh em!"
            ]
            ctas_footwear = [
                f"Đi vào cực êm cực chất luôn! Mẫu {cleaned_name} này đang có deal hời, anh em bấm giỏ hàng chốt ngay nhé!",
                f"Hack dáng cực kỳ mà giá siêu êm. Nhanh tay click vào giỏ hàng góc trái để rinh em {cleaned_name} này về nha!",
                f"Đẹp từ phom dáng đến chất lượng. Anh em bấm mua ngay em {cleaned_name} ở giỏ hàng bên dưới nha!"
            ]
            ctas_other = [
                f"Dùng siêu thích và tiện lợi lắm luôn. Anh em bấm ngay vào giỏ hàng góc trái để săn deal hời em {cleaned_name} nha!",
                f"Quá chất lượng so với giá tiền luôn. Mua ngay em {cleaned_name} ở link giỏ hàng bên dưới nhé anh em!",
                f"Nói chung là 10 trên 10 không có điểm chê. Anh em nhanh tay bấm mua ở giỏ hàng nha!"
            ]
        else: # female
            ctas_clothing = [
                f"Mặc lên phom chuẩn tôn dáng cực kỳ! Mẫu {cleaned_name} này đáng mua lắm, chị em bấm giỏ hàng góc trái săn sale nha!",
                f"Xinh thế này không mua là tiếc lắm nha. Chị em tranh thủ chốt ngay mẫu {cleaned_name} ở giỏ hàng bên dưới nha!",
                f"Nói chung là 10 trên 10 mặc lên cưng lắm. Link mua em {cleaned_name} ở ngay góc trái màn hình nha mọi người!"
            ]
            ctas_footwear = [
                f"Đi vào cực êm cực xinh luôn! Mẫu {cleaned_name} này đang có deal hời, chị em bấm giỏ hàng chốt ngay nhé!",
                f"Hack dáng cực kỳ mà giá siêu yêu. Nhanh tay click vào giỏ hàng góc trái để rinh em {cleaned_name} này về nha mọi người!",
                f"Đẹp từ phom dáng đến chất lượng. Chị em bấm mua ngay em {cleaned_name} ở giỏ hàng bên dưới nha!"
            ]
            ctas_other = [
                f"Dùng siêu thích và cưng xỉu luôn. Mọi người bấm ngay vào giỏ hàng góc trái để săn deal hời em {cleaned_name} nha!",
                f"Quá chất lượng so với giá tiền luôn. Mua ngay em {cleaned_name} ở link giỏ hàng bên dưới nhé cả nhà!",
                f"Nói chung là 10 trên 10 không có điểm chê. Cả nhà nhanh tay bấm mua ở giỏ hàng nha!"
            ]

        if segment_index == 0:
            if prod_type == "clothing":
                options = hooks_clothing
            elif prod_type == "footwear":
                options = hooks_footwear
            else:
                options = hooks_other
            return options[seed % len(options)]
            
        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                options = ctas_clothing
            elif prod_type == "footwear":
                options = ctas_footwear
            else:
                options = ctas_other
            return options[seed % len(options)]
            
        else:
            if prod_type == "clothing":
                options = mid_clothing
            elif prod_type == "footwear":
                options = mid_footwear
            else:
                options = mid_other
            idx = (seed + segment_index) % len(options)
            return options[idx]

    def _build_segment_prompt(self, base_prompt: str, product_name: str, segment_index: int, total_segments: int, product_description: str | None = None) -> str:
        """
        Tạo prompt chi tiết cho từng phân đoạn video.
        Có kịch bản tổng thể (storyline) xuyên suốt, nhạc nhất quán, description đã lọc sạch.
        """
        if "trending" in base_prompt.lower() or "dance" in base_prompt.lower():
            return self._build_trending_dance_prompt(base_prompt, product_name)

        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        gender = self._determine_gender(product_name, product_description)
        
        # Sinh câu thuyết minh động và tự nhiên cho phân đoạn này
        voiceover_line = self._generate_tiktok_voiceover(
            product_name, product_description, gender, segment_index, total_segments, prod_type
        )
        
        if gender == "male":
            subject = "A handsome young Vietnamese man"
            pronoun = "He"
        else:
            subject = "A beautiful young Vietnamese woman"
            pronoun = "She"

        # Lọc description sạch thay vì dump nguyên khối
        clean_desc = self._extract_useful_description(product_description)
        desc_hint = f"Product info: {clean_desc}. " if clean_desc else ""

        # Chọn 1 bài nhạc cụ thể, nhất quán cho tất cả segments
        music_name = self._pick_consistent_music(product_name)
        music_instruction = (
            f"REQUIRED: Background music must be {music_name} or a similar-style Vietnamese TikTok trending song (V-pop, nhạc trẻ Việt Nam), "
            "upbeat and energetic, clearly audible throughout the entire clip. "
        )

        # === KỊCH BẢN TỔNG THỂ (STORYLINE) ===
        # Clip 1 (segment 0): HOOK + REVIEW CẬN CẢNH - Thu hút, khoe sản phẩm chi tiết
        # Clip 2 (segment cuối): TRY-ON + CTA - Mặc/dùng thử + kêu gọi mua hàng
        # Clip giữa (nếu >2): CHI TIẾT BỔ SUNG - Zoom vào đặc điểm nổi bật

        storyline_context = (
            f"VIDEO STORYLINE: This is clip {segment_index + 1} of {total_segments} in a TikTok product review series. "
        )
        if segment_index == 0:
            storyline_context += "This clip is the HOOK — grab attention and show close-up product details. "
        elif segment_index == total_segments - 1:
            storyline_context += "This clip is the FINALE — show the product being worn/used and end with a confident call-to-action pose. "
        else:
            storyline_context += "This clip shows ADDITIONAL DETAILS — highlight standout features and quality. "
        
        storyline_context += (
            f"IMPORTANT: The same person ({subject.lower()}) appears in ALL clips with consistent appearance, "
            "same setting style, same warm lighting, same fashion aesthetic throughout. "
        )

        if segment_index == 0:
            if prod_type == "clothing":
                return (
                    f"{storyline_context}"
                    f"Viral TikTok OOTD outfit-check video clip, 9:16 vertical, cinematic aesthetic. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' clothing (reference image provided). "
                    f"{subject} in a bright aesthetic room with warm lighting. "
                    f"{pronoun} holds the clothing item close to camera, showing fabric texture and design details with a natural smile. "
                    f"Quick smooth cuts: close-up of fabric, label, stitching detail. Natural relaxed expression, not scripted. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover blended with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"{storyline_context}"
                    f"Viral TikTok shoe haul video clip, 9:16 vertical, aesthetic style. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' footwear (reference image provided). "
                    f"{subject} in a stylish setting holds the shoes close to camera. "
                    "Quick aesthetic cuts: shoe sole detail, side profile, material close-up. Natural delighted expression. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover blended with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"{storyline_context}"
                    f"Viral TikTok product unboxing clip, 9:16 vertical, aesthetic style. "
                    f"{desc_hint}"
                    f"Product: '{cleaned_name}' (reference image provided). "
                    f"{subject} holds the product near camera showing design and features. "
                    "Quick aesthetic cuts: product detail close-ups, packaging, key features. Natural happy expression. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover blended with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )

        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                return (
                    f"{storyline_context}"
                    f"Viral TikTok OOTD try-on video clip, 9:16 vertical, aesthetic cinematic style. "
                    f"Product: '{cleaned_name}' outfit (same item from the previous review clip). "
                    f"{subject} is now WEARING the outfit in the same well-lit aesthetic setting. "
                    f"{pronoun} does a natural 360 spin showing the full outfit, walks gracefully towards camera, poses confidently with a bright smile. "
                    "Multiple smooth aesthetic cuts: full body shot, waist detail, side profile. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"{storyline_context}"
                    f"Viral TikTok shoe try-on video clip, 9:16 vertical, aesthetic style. "
                    f"Product: '{cleaned_name}' footwear (same pair from the previous review clip). "
                    f"{subject} is now WEARING the shoes, walking gracefully in the same stylish setting. "
                    "Smooth aesthetic cuts: feet/shoes walking, full outfit from ground up, close-up of shoes in motion. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"{storyline_context}"
                    f"Viral TikTok product demo clip, 9:16 vertical, aesthetic style. "
                    f"Product: '{cleaned_name}' (same item from the previous review clip). "
                    f"{subject} demonstrates USING the product with genuine delight and satisfaction. "
                    "Smooth aesthetic cuts: product in use, feature highlights, happy reaction shots. "
                    f"{music_instruction}"
                    f"Soft Vietnamese voiceover with music: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )

        else:
            # Segment giữa: chi tiết bổ sung
            if prod_type == "clothing":
                detail_action = f"{pronoun} shows close-up of stitching quality, fabric stretch test, and how the material drapes naturally."
            elif prod_type == "footwear":
                detail_action = f"{pronoun} shows close-up of sole grip, cushioning detail, and how the shoe fits on foot."
            else:
                detail_action = f"{pronoun} shows close-up of product build quality, key feature demonstration, and size/weight in hand."
            return (
                f"{storyline_context}"
                f"TikTok product detail review clip, 9:16 vertical, aesthetic cinematic style. "
                f"Product: '{cleaned_name}' (same item, same person, same setting as other clips). "
                f"{subject} continues the review. {detail_action} "
                "Natural genuine expression showing satisfaction with the quality. "
                f"{music_instruction}"
                f"Soft Vietnamese voiceover with music: '{voiceover_line}' "
                "No text, no watermark. Duration 10 seconds."
            )

    def _build_safe_fallback_prompt(self, product_name: str, segment_index: int, total_segments: int) -> str:
        """Prompt dự phòng an toàn: chỉ sản phẩm + nhạc nền, không người, đảm bảo qua safety filter."""
        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        duration = 10
        music_name = self._pick_consistent_music(product_name)
        music_line = (
            f"REQUIRED: Background music must be {music_name} or a similar-style Vietnamese TikTok trending song (V-pop, nhạc trẻ Việt Nam), "
            "upbeat and catchy, clearly audible. "
        )

        if prod_type == "clothing":
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Fashion item '{cleaned_name}' displayed on a stylish hanger. "
                "Camera slowly pans and rotates around the item, macro close-up of fabric texture and stitching. "
                f"{music_line}"
                f"No people, no text, no watermark. Duration {duration} seconds."
            )
        elif prod_type == "footwear":
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Footwear '{cleaned_name}' displayed on a clean surface with beautiful lighting. "
                "Camera slowly pulls back for a full product reveal, macro close-up of material and sole detail. "
                f"{music_line}"
                f"No people, no text, no watermark. Duration {duration} seconds."
            )
        else:
            return (
                f"Aesthetic product showcase video, 9:16 vertical, cinematic quality. "
                f"Product '{cleaned_name}' displayed on a clean surface with beautiful lighting. "
                "Camera slowly pans around the item, macro close-up of key features and design. "
                f"{music_line}"
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

        # Log kịch bản tổng thể
        music_name = self._pick_consistent_music(product_name)
        cleaned_name = self._clean_product_name(product_name)
        logger.info(f"📋 Kịch bản tổng thể cho '{cleaned_name}':")
        logger.info(f"   🎵 Nhạc nền xuyên suốt: {music_name}")
        for si in range(num_segments):
            if si == 0:
                logger.info(f"   📹 Clip {si+1}: HOOK + Review cận cảnh sản phẩm")
            elif si == num_segments - 1:
                logger.info(f"   📹 Clip {si+1}: Try-on/Demo + CTA kêu gọi mua hàng")
            else:
                logger.info(f"   📹 Clip {si+1}: Chi tiết bổ sung chất lượng sản phẩm")

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
                logger.info("⏳ Đang gửi yêu cầu...")
                self._click_send_button()
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
                            'message-content, [data-test-id="response-container"], .model-response, .message-content, [role="alert"], .inline-alert, .error-message'
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

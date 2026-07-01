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
                        
                        if self._check_subscription_required(latest_text):
                            logger.error("❌ Tài khoản Gemini này chưa có hoặc hết hạn subscription Pro/Advanced!")
                            raise RuntimeError("GEMINI_SUBSCRIPTION_REQUIRED")

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

    def _check_subscription_required(self, text: str) -> bool:
        """Kiểm tra xem Gemini có yêu cầu nâng cấp subscription (hết hạn Pro/Advanced) không."""
        subscription_keywords = [
            "upgrade your subscription",
            "nâng cấp gói",
            "nâng cấp đăng ký",
            "subscription required",
            "need to upgrade",
            "cần nâng cấp",
            "subscribe to",
            "premium feature",
            "tính năng cao cấp",
            "gemini advanced",
            "upgrade to",
            "you'll need to upgrade",
            "bạn cần nâng cấp",
            "yêu cầu nâng cấp",
        ]
        text_lower = text.lower()
        for kw in subscription_keywords:
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
        """Sinh kịch bản voiceover liền mạch cho chuỗi video review TikTok.
        
        Kịch bản 2 phần:
          Clip 1: Hook mở đầu → giới thiệu + review chi tiết (chất liệu, form dáng, cảm nhận)
          Clip 2: Chuyển tiếp mượt → mặc/dùng thử + CTA kêu gọi mua
        
        2 clip đọc liên tiếp phải nghe như 1 bài review hoàn chỉnh.
        """
        cleaned_name = self._clean_product_name(product_name)
        seed = sum(ord(c) for c in cleaned_name)
        
        # ====== KỊCH BẢN HOÀN CHỈNH (mỗi set gồm [clip1, clip2] đọc liền mạch) ======
        if gender == "male":
            addr = "anh em"
            addr2 = "cả nhà"
        else:
            addr = "chị em"
            addr2 = "mọi người"

        if prod_type == "clothing":
            scripts = [
                # Script set 0
                [
                    f"Ê {addr} ơi, hôm nay review thực tế mẫu {cleaned_name} siêu hot này nha! Cầm lên là thấy chất vải mềm mịn, đường may tỉ mỉ, form dáng chuẩn không cần chỉnh luôn.",
                    f"Giờ mặc thử cho {addr} xem nè! Phom lên người cực kỳ tôn dáng, thoải mái di chuyển cả ngày. Đáng mua lắm, {addr} bấm giỏ hàng góc trái chốt ngay nhé!",
                ],
                # Script set 1
                [
                    f"Mẫu {cleaned_name} này {addr2} ơi, vừa mở ra là ưng ngay! Chất vải dày dặn nhưng mặc mát, đường kim mũi chỉ cực kỳ cẩn thận, nhìn phom là biết chuẩn đẹp rồi.",
                    f"Mặc lên người thử nè, nhìn xem tôn dáng cỡ nào! Màu sắc trên người đẹp hơn hình nữa. Thích thì {addr} ơi bấm ngay vào giỏ hàng bên dưới săn sale nha!",
                ],
                # Script set 2
                [
                    f"Review nhanh em {cleaned_name} đang viral này nha {addr2}! Cầm lên sờ thử chất vải cotton cao cấp, co giãn thoải mái, thiết kế trẻ trung hợp xu hướng cực kỳ.",
                    f"Xong rồi mặc thử luôn cho {addr} xem thực tế nè! Form chuẩn đẹp lắm, phối đồ gì cũng hợp. Link mua ở ngay góc trái màn hình, nhanh tay chốt kẻo hết hàng nha!",
                ],
                # Script set 3
                [
                    f"Hôm nay khui hàng mẫu {cleaned_name} cho {addr} xem nha! Ấn tượng đầu tiên là chất vải rất xịn, sờ vào mềm mịn, đường may gọn gàng không chỉ thừa.",
                    f"Thử lên đồ luôn nè, {addr} nhìn xem phom dáng có chuẩn không! Mặc quá thoải mái luôn. Giá lại hạt dẻ nữa, bấm giỏ hàng chốt đơn ngay {addr} nhé!",
                ],
            ]
        elif prod_type == "footwear":
            scripts = [
                [
                    f"Review đôi {cleaned_name} siêu hot cho {addr} nè! Cầm lên là thấy chất da/vải rất tốt, đế dày chắc chắn, phom gọn gàng đẹp mắt cực kỳ.",
                    f"Xỏ vào chân thử luôn nha! Đi vào êm ái lắm, ôm chân vừa vặn không bị rộng hay chật. Quá ưng luôn, {addr} bấm giỏ hàng góc trái rinh ngay nhé!",
                ],
                [
                    f"Đôi {cleaned_name} này {addr2} ơi, mở hộp ra là mê luôn! Từng đường chỉ cực tỉ mỉ, đế cao su chống trượt, kiểu dáng trẻ trung phối đồ gì cũng hợp.",
                    f"Lên chân thử cho {addr} xem nè! Nhẹ lắm mà đi cả ngày không đau chân. Thích thì click ngay vào giỏ hàng bên dưới, đang có deal hời lắm nha!",
                ],
                [
                    f"Hôm nay unbox đôi {cleaned_name} đang gây sốt nè {addr2}! Chất liệu xịn sò, đường keo chắc chắn, thiết kế vừa thể thao vừa thanh lịch luôn.",
                    f"Giờ thử đi vài bước cho {addr} xem nha! Cảm giác êm ái nhẹ nhàng lắm, phom chuẩn hack dáng cực đỉnh. Link mua ngay góc trái, nhanh tay chốt nha {addr}!",
                ],
            ]
        else:
            scripts = [
                [
                    f"Review em {cleaned_name} cho {addr2} nha! Cầm trên tay chắc chắn, thiết kế nhỏ gọn tinh tế, hoàn thiện cực kỳ cao cấp luôn.",
                    f"Dùng thử luôn nè, {addr} xem hiệu quả thực tế nha! Tính năng ngon lành, dùng rất mượt mà. Quá đáng đồng tiền, bấm giỏ hàng góc trái chốt ngay nhé!",
                ],
                [
                    f"Unbox siêu phẩm {cleaned_name} cho {addr2} đây! Mở ra ấn tượng ngay với chất liệu cao cấp, kích thước vừa tay, từng chi tiết đều được làm rất tỉ mỉ.",
                    f"Test thực tế cho {addr} xem luôn nè! Hoạt động mượt mà, đúng như quảng cáo luôn. Thích thì {addr} click giỏ hàng bên dưới săn deal ngay nha!",
                ],
                [
                    f"Hôm nay review thực tế em {cleaned_name} đang hot trend nè {addr2}! Thiết kế thông minh, chất liệu bền đẹp, cầm lên là thấy đáng tiền ngay.",
                    f"Giờ dùng thử cho {addr} xem có ngon như lời đồn không nha! Quá mượt mà và tiện lợi luôn. Link mua ở góc trái màn hình, nhanh tay chốt kẻo hết nha {addr}!",
                ],
            ]

        # Chọn script set dựa trên seed (nhất quán cho cùng sản phẩm)
        script_set = scripts[seed % len(scripts)]
        
        # Trả về đúng phần cho segment tương ứng
        if total_segments == 2:
            # 2 clips: clip 0 = phần 1, clip 1 = phần 2
            return script_set[min(segment_index, 1)]
        elif segment_index == 0:
            return script_set[0]
        elif segment_index == total_segments - 1:
            return script_set[1]
        else:
            # Segments giữa: sinh câu review chi tiết bổ sung
            mid_lines = [
                "Nhìn kỹ từng chi tiết là thấy sự khác biệt, chất lượng thực sự cao cấp hơn hẳn.",
                "Zoom cận cảnh cho mọi người thấy nè, hoàn thiện tỉ mỉ từng milimet luôn.",
                "Sờ vào là biết hàng xịn ngay, chất liệu dày dặn mà vẫn thoải mái lắm.",
                "Chi tiết này là điểm cộng lớn nè, ít sản phẩm nào làm được tốt như vậy.",
            ]
            return mid_lines[(seed + segment_index) % len(mid_lines)]

    def _build_segment_prompt(self, base_prompt: str, product_name: str, segment_index: int, total_segments: int, product_description: str | None = None) -> str:
        """
        Tạo prompt cho từng clip video với kịch bản hành động HOÀN TOÀN KHÁC NHAU giữa các clip.
        
        Clip 1: UNBOXING/HANDS-ON — Tay cầm sản phẩm, macro close-up, sờ chất liệu, lật xem tag
        Clip 2: TRY-ON/STYLING — Mặc/dùng lên người, đi lại, quay 360, full-body shot
        
        2 clip ghép lại = 1 video review hoàn chỉnh từ "mở hộp → mặc thử → kêu gọi mua"
        """
        if "trending" in base_prompt.lower() or "dance" in base_prompt.lower():
            return self._build_trending_dance_prompt(base_prompt, product_name)

        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        gender = self._determine_gender(product_name, product_description)
        
        voiceover_line = self._generate_tiktok_voiceover(
            product_name, product_description, gender, segment_index, total_segments, prod_type
        )
        
        if gender == "male":
            subject = "a handsome young Vietnamese man"
            pronoun = "He"
            possessive = "his"
        else:
            subject = "a beautiful young Vietnamese woman"
            pronoun = "She"
            possessive = "her"

        clean_desc = self._extract_useful_description(product_description)
        desc_hint = f"({clean_desc}) " if clean_desc else ""
        
        music_name = self._pick_consistent_music(product_name)
        music_rule = f"Background music: {music_name} or similar V-pop trending song, upbeat, clearly audible. "

        # ============================================================
        # CLIP 1: UNBOXING + HANDS-ON REVIEW (cầm, sờ, lật, zoom)
        # ============================================================
        if segment_index == 0:
            if prod_type == "clothing":
                return (
                    f"TikTok product review video, 9:16 vertical, warm cinematic lighting. "
                    f"Product: '{cleaned_name}' {desc_hint}(use reference image). "
                    f"Scene: {subject} sitting at a clean aesthetic desk/table. "
                    f"Action sequence: {pronoun} picks up the folded clothing from a minimal box, "
                    f"unfolds it and holds it up to show the full design. "
                    f"Camera zooms into {possessive} hands touching the fabric texture (macro close-up of weaving pattern). "
                    f"Then {pronoun.lower()} flips the collar/tag to show the label, runs fingers along the stitching. "
                    f"Facial expression: genuinely impressed, nodding with a smile. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"TikTok shoe review video, 9:16 vertical, warm cinematic lighting. "
                    f"Product: '{cleaned_name}' {desc_hint}(use reference image). "
                    f"Scene: {subject} sitting, takes the shoes out of the box. "
                    f"Action sequence: {pronoun} holds one shoe close to camera, tilts it to show the side profile and sole. "
                    f"Camera zooms into the sole texture (macro), then {pronoun.lower()} presses the insole with {possessive} thumb showing cushion softness. "
                    f"Runs finger along the stitching/seam for quality check. "
                    f"Facial expression: pleasantly surprised, nodding approvingly. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"TikTok product unboxing review, 9:16 vertical, warm cinematic lighting. "
                    f"Product: '{cleaned_name}' {desc_hint}(use reference image). "
                    f"Scene: {subject} at a clean desk, opens the product packaging. "
                    f"Action sequence: {pronoun} takes the product out, holds it up to camera showing all angles. "
                    f"Camera zooms into key design details (buttons, ports, material texture — macro close-up). "
                    f"{pronoun} tests weight in hand, touches surface finish. "
                    f"Facial expression: genuinely impressed, examining with curiosity. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )

        # ============================================================
        # CLIP 2 (CUỐI): TRY-ON / DEMO IN ACTION + CTA
        # ============================================================
        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                return (
                    f"TikTok outfit try-on video, 9:16 vertical, bright natural lighting. "
                    f"Product: '{cleaned_name}' outfit being worn. "
                    f"Scene: {subject} standing in a well-lit room (full-body mirror visible or clean background). "
                    f"Action sequence: {pronoun} is already WEARING the outfit. "
                    f"Starts with a confident walk towards camera (3 steps), stops, does a smooth 360 spin, "
                    f"then strikes a relaxed fashion pose (hand on hip or adjusting collar). "
                    f"Camera angle: starts medium shot, pulls slightly wider for full body reveal. "
                    f"Facial expression: confident bright smile, looking directly at camera at the end. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"TikTok shoe try-on video, 9:16 vertical, bright natural lighting. "
                    f"Product: '{cleaned_name}' shoes being worn. "
                    f"Scene: {subject} standing, shoes already ON feet. "
                    f"Action sequence: Camera starts LOW at foot level showing the shoes in detail, "
                    f"then slowly tilts up revealing the full outfit. "
                    f"{pronoun} takes a few stylish steps forward, camera follows the walking feet, "
                    f"then {pronoun.lower()} stops and does a small confident bounce/pose. "
                    f"Facial expression: happy and satisfied, looking down at shoes then smiling at camera. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"TikTok product demo video, 9:16 vertical, bright natural lighting. "
                    f"Product: '{cleaned_name}' being USED in action. "
                    f"Scene: {subject} actively using/demonstrating the product in a real setting. "
                    f"Action sequence: {pronoun} powers on/activates the product, shows it working. "
                    f"Camera captures the product in action with genuine reaction shots. "
                    f"Then {pronoun.lower()} holds the product towards camera with a thumbs-up or satisfied nod. "
                    f"Facial expression: delighted, genuinely happy with the result. "
                    f"{music_rule}"
                    f"Vietnamese voiceover (natural, blended with music): '{voiceover_line}' "
                    "No text overlay, no watermark. Duration 10 seconds."
                )

        # ============================================================
        # CLIP GIỮA (nếu >2 clips): CHI TIẾT BỔ SUNG
        # ============================================================
        else:
            if prod_type == "clothing":
                return (
                    f"TikTok clothing detail video, 9:16 vertical, soft studio lighting. "
                    f"Product: '{cleaned_name}'. "
                    f"{subject} stretches the fabric to show elasticity, flips it inside-out showing lining quality. "
                    f"Macro camera shots of button details, zipper quality, collar shape. "
                    f"{music_rule}"
                    f"Vietnamese voiceover: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            elif prod_type == "footwear":
                return (
                    f"TikTok shoe detail video, 9:16 vertical, soft studio lighting. "
                    f"Product: '{cleaned_name}'. "
                    f"{subject} bends the sole to show flexibility, removes insole showing cushion layer. "
                    f"Macro camera shots of sole grip pattern, heel construction, lace/strap quality. "
                    f"{music_rule}"
                    f"Vietnamese voiceover: '{voiceover_line}' "
                    "No text, no watermark. Duration 10 seconds."
                )
            else:
                return (
                    f"TikTok product detail video, 9:16 vertical, soft studio lighting. "
                    f"Product: '{cleaned_name}'. "
                    f"{subject} demonstrates a specific feature of the product, showing build quality and functionality. "
                    f"Macro camera shots of material, buttons, ports, or key differentiating features. "
                    f"{music_rule}"
                    f"Vietnamese voiceover: '{voiceover_line}' "
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
                            
                            if self._check_subscription_required(latest_text):
                                logger.error("❌ Tài khoản Gemini này chưa có hoặc hết hạn subscription Pro/Advanced!")
                                raise RuntimeError("GEMINI_SUBSCRIPTION_REQUIRED")

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

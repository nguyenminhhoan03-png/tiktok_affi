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
        product_description: str | None = None,
    ) -> str:
        """
        Gửi prompt tạo video, đợi render xong và tải video về.
        Hỗ trợ Safe Fallback và phát hiện video trùng lặp bằng cách theo dõi danh sách video src.
        """
        self.select_video_mode_if_needed()

        video_file_path = None
        max_limit_retries = 12
        safety_blocked = False

        if product_name:
            prompt = self._build_segment_prompt(prompt, product_name, 0, 1, product_description=product_description)
        elif "trending" in prompt.lower() or "dance" in prompt.lower():
            prompt = self._build_trending_dance_prompt(prompt, product_name)

        for retry_idx in range(max_limit_retries):
            existing_sources = set(self._get_all_video_sources())

            if image_path and retry_idx == 0:
                self.upload_image_if_provided(image_path)

            clean_p = prompt.replace("(from reference image)", "").replace("(match reference image)", "").replace("  ", " ").strip()
            if image_path and Path(image_path).exists():
                final_prompt = f"Tạo cho tôi video 10s dựa trên hình ảnh đã tải lên về chủ đề: {clean_p}. Không hiển thị chữ hay logo watermark."
            else:
                final_prompt = f"Tạo cho tôi video 10s về chủ đề: {clean_p}. Không hiển thị chữ hay logo watermark."

            self._close_overlays()
            if retry_idx > 0:
                logger.info(f"✍️ Gửi lại prompt (Lần thử {retry_idx + 1}): {final_prompt}")
            else:
                logger.info(f"✍️ Gửi prompt: {final_prompt}")

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
                chat_input.fill(final_prompt)
            except Exception:
                import json
                chat_input.evaluate(f"el => {{ el.innerText = {json.dumps(final_prompt)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
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

            # Nếu bị safety block, chuyển sang Safe Fallback Prompt để đảm bảo qua bộ lọc
            if safety_blocked:
                if product_name:
                    prompt = self._build_safe_fallback_prompt(product_name, 0, 1)
                    logger.info(f"🛡️ Gemini từ chối prompt cũ! Chuyển sang Safe Fallback Prompt: {prompt}")
                else:
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
            "encountered an error", "having a hard time", "fulfilling your request",
            "could you try again", "error doing what you asked", "something else instead",
            "hard time", "fulfilling", "try again"
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
        # 3. Nhóm mỹ phẩm & làm đẹp (Son, Skincare, Makeup)
        cosmetics_keywords = [
            "son", "lip", "balm", "môi", "kem dưỡng", "mỹ phẩm", "serum", "phấn", 
            "cọ", "nước hoa", "lotion", "sữa rửa mặt", "toner", "mascara", "eyeliner", 
            "cushion", "tẩy trang", "chống nắng"
        ]
        # 4. Nhóm công nghệ / điện tử
        electronics_keywords = [
            "tai nghe", "loa", "sạc", "cáp", "ốp lưng", "bàn phím", "chuột", 
            "đồng hồ", "quạt tích điện", "quạt mini", "điện thoại"
        ]
        
        for kw in clothing_keywords:
            if kw in name_lower:
                return "clothing"
                
        for kw in footwear_keywords:
            if kw in name_lower:
                return "footwear"

        for kw in cosmetics_keywords:
            if kw in name_lower:
                return "cosmetics"

        for kw in electronics_keywords:
            if kw in name_lower:
                return "electronics"
                
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
        """Prompt ngắn gọn cho video thời trang năng động/xu hướng."""
        cleaned_name = self._clean_product_name(product_name) if product_name else "sản phẩm"
        gender = self._determine_gender(product_name or "")

        if gender == "male":
            subject = "A handsome stylish young Vietnamese man"
        else:
            subject = "A beautiful stylish young Vietnamese woman"

        return (
            f"Aesthetic TikTok fashion video, 9:16 vertical. "
            f"{subject} styling '{cleaned_name}' walks confidently toward camera, strikes a cool pose "
            "and does a fast fashion transition synchronized to a viral Vietnamese V-pop beat. "
            "Dynamic angles, warm studio lighting. Product clearly visible. No text, no watermark."
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
        
        Kịch bản 2 phần cuốn hút, vui nhộn, hợp xu hướng TikTok:
          Clip 1: Hook bắt mắt/gây tò mò → Giới thiệu + cảm nhận thực tế
          Clip 2: Dùng/Mặc thử cực mê → Chốt deal giỏ hàng góc trái
        """
        cleaned_name = self._clean_product_name(product_name)
        seed = sum(ord(c) for c in cleaned_name)
        
        if gender == "male":
            addr = "anh em"
            addr2 = "cả nhà"
        else:
            addr = "chị em"
            addr2 = "mọi người"

        if prod_type == "clothing":
            scripts = [
                [
                    f"Ê {addr} ơi, review thực tế mẫu {cleaned_name} đang siêu hot này nha! Cầm lên sờ thử chất vải mềm mịn, đường may tỉ mỉ form chuẩn đét luôn.",
                    f"Giờ mặc thử cho {addr} xem nè! Phom lên người tôn dáng cực kỳ, mặc mát rượi cả ngày. Bấm giỏ hàng góc trái săn sale ngay nhé!",
                ],
                [
                    f"Mẫu {cleaned_name} này {addr2} ơi, vừa mở hộp ra là mê xỉu! Chất vải dày dặn đường kim mũi chỉ cẩn thận, nhìn phom là biết xịn rồi.",
                    f"Mặc lên người thử nè, nhìn xem sang đỉnh chưa! Thích em này thì {addr} bấm ngay giỏ hàng góc trái kẻo hết size nha!",
                ],
                [
                    f"Review nhanh {cleaned_name} đang viral này nha {addr2}! Vải co giãn thoải mái, lên dáng chuẩn chỉnh hợp xu hướng năm nay cực kỳ.",
                    f"Mặc lên thực tế cho {addr} xem nè! Phối đồ gì cũng xinh xuất sắc. Link mua ở góc trái màn hình, rinh ngay thôi!",
                ],
                [
                    f"Hôm nay khui hàng mẫu {cleaned_name} siêu ngọt này! Ấn tượng đầu tiên là vải mát tay, không chỉ thừa, phom xịn hơn ảnh chụp luôn.",
                    f"Thử đồ luôn nè, {addr} thấy chuẩn không! Giá lại đang hời nữa, quẹo lựa giỏ hàng ngay thôi nào!",
                ],
            ]
        elif prod_type == "footwear":
            scripts = [
                [
                    f"Review đôi {cleaned_name} siêu cháy cho {addr} nè! Cầm lên là thấy da mịn, đế chắc chắn, form gọn gàng tôn dáng cực kỳ.",
                    f"Xỏ vào chân thử luôn nha! Đi vào êm ái nhẹ hẫng, ôm chân vừa đét. Bấm ngay giỏ hàng góc trái rinh em nó về nhé!",
                ],
                [
                    f"Đôi {cleaned_name} này {addr2} ơi, mở hộp ra là ưng liền! Tỉ mỉ từng đường chỉ, đế chống trượt phối đồ gì cũng đỉnh.",
                    f"Lên chân đi thử nè! Nhẹ nhàng êm chân cực kỳ. Thích thì click ngay vào giỏ hàng góc trái đang có deal tốt nha!",
                ],
                [
                    f"Hôm nay unbox đôi {cleaned_name} đang gây sốt nè! Chất liệu xịn sò, phom chuẩn thể thao vừa thanh lịch vừa năng động.",
                    f"Giờ thử đi vài bước cho {addr} xem nha! Cảm giác đi siêu êm, lên dáng cực hack height. Chốt đơn ngay ở giỏ hàng góc trái nha!",
                ],
                [
                    f"Ai bảo mua giày online là rủi ro? Đôi {cleaned_name} này làm tôi bất ngờ thật sự!",
                    f"Mê nhất cái cảm giác xỏ chân vào vừa khít êm ru, {addr} nhấp giỏ hàng góc trái chốt lẹ nhé!",
                ],
            ]
        elif prod_type == "cosmetics":
            scripts = [
                [
                    f"Tôi cầm cái {cleaned_name} này lên mà thấy đáng tiền ngay — thiết kế gọn, chất son mượt đỉnh cao!",
                    f"Thoa thử lên mướt rượt luôn {addr2} ơi! Lên màu vừa xinh lại dưỡng tốt, nhấp ngay giỏ hàng góc trái múc liền nha!",
                ],
                [
                    f"Ê {addr} ơi, unbox em {cleaned_name} này với tâm trạng hoài nghi — mà sờ vỏ với xem chất son là hết nghi ngay!",
                    f"Đánh thử siêu êm môi, mềm mịn không dính rít tí nào. Link mua ngay ở giỏ hàng góc trái nhé {addr2}!",
                ],
                [
                    f"Review chân thực {cleaned_name} đang viral rầm rộ nè! Cầm chắc tay, vỏ xinh xắn mà chất lượng bên trong vượt mong đợi!",
                    f"Mọi người nhìn chất mượt chưa này, siêu ưng luôn! Bấm giỏ hàng góc trái săn ngay giá hời hôm nay nha!",
                ],
                [
                    f"Hôm nay unbox thử em {cleaned_name} xinh xỉu này! Thiết kế nhỏ gọn sang xịn, mang đi đâu cũng tiện.",
                    f"Test thử độ mượt đỉnh kề luôn! {addr2} quẹo lựa giỏ hàng góc trái rinh ngay một em về dùng nhé!",
                ],
            ]
        elif prod_type == "electronics":
            scripts = [
                [
                    f"Unbox em {cleaned_name} công nghệ siêu nét này {addr2}! Thiết kế hiện đại, cầm chắc tay, độ hoàn thiện tỉ mỉ cực kỳ.",
                    f"Dùng thử mượt mà không độ trễ luôn! Trải nghiệm đáng tiền thật sự, bấm giỏ hàng góc trái chốt ngay em nó nha!",
                ],
                [
                    f"Ê {addr}, chiếc {cleaned_name} này đang cực hot nè! Nhìn ngoại hình thôi đã thấy chất sang đỉnh rồi.",
                    f"Test tính năng xong là muốn giới thiệu cho mọi người liền. Đáng mua lắm, nhấp giỏ hàng góc trái nhận ưu đãi nha!",
                ],
            ]
        else:
            scripts = [
                [
                    f"Tôi cầm cái {cleaned_name} này lên mà thấy đáng tiền ngay — thiết kế gọn, chất tốt cực kỳ!",
                    f"Dùng thử xong rồi tôi xác nhận: ngon hơn quảng cáo nhiều, {addr2} chốt đơn ngay giỏ hàng góc trái nha!",
                ],
                [
                    f"Unbox em {cleaned_name} này với tâm trạng hoài nghi — cầm lên sờ tận tay là hài lòng ngay!",
                    f"Trải nghiệm thực tế quá mượt {addr} ơi, link mua chuẩn ngay ở giỏ hàng góc trái nhé!",
                ],
                [
                    f"Review thật: em {cleaned_name} này về tay đẹp hơn hình, chất lượng vượt kỳ vọng thật sự!",
                    f"Dùng thử quá ưng luôn, {addr2} bấm giỏ hàng góc trái múc liền kẻo hết nhé!",
                ],
            ]

        script_set = scripts[seed % len(scripts)]

        if total_segments == 2:
            return script_set[min(segment_index, 1)]
        elif segment_index == 0:
            return script_set[0]
        elif segment_index == total_segments - 1:
            return script_set[1]
        else:
            mid_lines = [
                "Nhìn kỹ chi tiết này xem — cái này mới là điểm làm tôi ưng nhất!",
                "Zoom cận cảnh vào đây nè, hoàn thiện tỉ mỉ mà giá lại cực hợp lý!",
                "Chi tiết nhỏ này thôi mà đã thấy chất lượng xịn sò rồi!",
                "Sờ vào là biết chuẩn đét ra sao — em này đáng đồng tiền bát gạo!",
            ]
            return mid_lines[(seed + segment_index) % len(mid_lines)]

    def _build_segment_prompt(
        self,
        base_prompt: str,
        product_name: str,
        segment_index: int,
        total_segments: int,
        product_description: str | None = None
    ) -> str:
        """
        Sinh prompt ngắn gọn (3-4 câu) cho từng clip chuẩn 9:16 vertical cinematic.
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
            subject = "a stylish young Vietnamese man"
        else:
            subject = "a stylish young Vietnamese woman"

        music_name = self._pick_consistent_music(product_name)
        music_rule = f"Background music: {music_name} (upbeat, clearly audible). "
        voiceover = f"Vietnamese voiceover (natural, warm): '{voiceover_line}'"

        # ============================================================
        # CLIP 1: UNBOXING + HANDS-ON REVIEW
        # ============================================================
        if segment_index == 0:
            if prod_type == "clothing":
                return (
                    f"TikTok product review, 9:16 vertical, warm cinematic lighting. "
                    f"{subject.capitalize()} holds up '{cleaned_name}' (from reference image), unfolds it and shows fabric texture with a genuinely impressed smile. "
                    f"Macro close-up on stitching detail, then pulls back to reveal full design. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "footwear":
                return (
                    f"TikTok shoe review, 9:16 vertical, warm cinematic lighting. "
                    f"{subject.capitalize()} holds '{cleaned_name}' (from reference image) close to camera, tilts it showing sole and material texture. "
                    f"Macro close-up on stitching and heel construction, reaction: pleasantly surprised. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "cosmetics":
                return (
                    f"TikTok product unboxing, 9:16 vertical, warm cinematic lighting, cozy beauty vlog style. "
                    f"{subject.capitalize()} gently takes '{cleaned_name}' (from reference image) out of packaging onto a rustic display stand. "
                    f"Macro extreme close-up on packaging and texture details, reaction: genuinely impressed, nodding with a natural smile. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "electronics":
                return (
                    f"TikTok tech unboxing, 9:16 vertical, sleek modern studio lighting. "
                    f"{subject.capitalize()} unboxes '{cleaned_name}' (from reference image) on a clean wooden desk, holding it up to reveal build quality. "
                    f"Macro close-up on buttons, finish and sleek design details. "
                    f"{music_rule}{voiceover}"
                )
            else:
                return (
                    f"TikTok product unboxing, 9:16 vertical, warm cinematic lighting. "
                    f"{subject.capitalize()} takes '{cleaned_name}' (from reference image) out of packaging and holds it up showing all angles. "
                    f"Macro close-up on key design details, reaction: genuinely impressed, nodding with a smile. "
                    f"{music_rule}{voiceover}"
                )

        # ============================================================
        # CLIP LAST: TRY-ON / DEMO IN ACTION + CTA
        # ============================================================
        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                return (
                    f"TikTok outfit try-on, 9:16 vertical, bright natural lighting. "
                    f"{subject.capitalize()} already WEARING '{cleaned_name}', walks confidently toward camera, "
                    "does a smooth 360 spin, then strikes a relaxed fashion pose with a bright smile at the camera. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "footwear":
                return (
                    f"TikTok shoe try-on, 9:16 vertical, bright natural lighting. "
                    f"Camera starts at floor level on '{cleaned_name}' shoes worn by {subject}, slowly tilts up revealing full outfit. "
                    f"{subject.capitalize()} takes a few stylish steps, looks down at shoes with a satisfied happy smile. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "cosmetics":
                return (
                    f"TikTok beauty review, 9:16 vertical, warm golden hour lighting. "
                    f"{subject.capitalize()} holds uncapped '{cleaned_name}' beside her cheek, showing texture and swatch up close, "
                    "then tilts product toward camera with an authentic approving smile and friendly nod. "
                    f"{music_rule}{voiceover}"
                )
            elif prod_type == "electronics":
                return (
                    f"TikTok tech demo, 9:16 vertical, modern bright studio lighting. "
                    f"{subject.capitalize()} actively demonstrates '{cleaned_name}' in action, showing smooth functionality. "
                    "Gives a thumbs-up to camera with a satisfied smile. "
                    f"{music_rule}{voiceover}"
                )
            else:
                return (
                    f"TikTok product demo, 9:16 vertical, bright natural lighting. "
                    f"{subject.capitalize()} actively uses '{cleaned_name}' and demonstrates it working smoothly. "
                    f"Holds product toward camera with a thumbs-up and genuine happy smile. "
                    f"{music_rule}{voiceover}"
                )

        # ============================================================
        # MIDDLE CLIPS: DETAIL CLOSE-UP
        # ============================================================
        else:
            return (
                f"TikTok product detail, 9:16 vertical, soft studio lighting. "
                f"{subject.capitalize()} examines '{cleaned_name}' closely, showing specific quality features with a curious impressed expression. "
                f"Macro close-up on material texture and construction detail. "
                f"{music_rule}{voiceover}"
            )

    def _build_safe_fallback_prompt(self, product_name: str, segment_index: int, total_segments: int) -> str:

        """Prompt dự phòng an toàn: chỉ sản phẩm + nhạc nền, không người, đảm bảo qua safety filter."""
        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        music_name = self._pick_consistent_music(product_name)
        music_line = f"Background music: {music_name} (upbeat V-pop, clearly audible). "

        if prod_type == "clothing":
            return (
                f"Aesthetic 9:16 product showcase. '{cleaned_name}' displayed on a stylish hanger. "
                f"Camera slowly pans and zooms into fabric texture and design details, cinematic commercial lighting. "
                f"{music_line}No text, no watermark."
            )
        elif prod_type == "footwear":
            return (
                f"Aesthetic 9:16 product showcase. '{cleaned_name}' on a clean surface, camera pulls back for full reveal. "
                f"Macro close-up of sole grip and material, beautiful studio lighting. "
                f"{music_line}No text, no watermark."
            )
        else:
            return (
                f"Aesthetic 9:16 product showcase. '{cleaned_name}' on a minimalist wooden surface. "
                f"Camera slowly rotates revealing design from all angles, macro close-up of key features. "
                f"{music_line}No text, no watermark."
            )

    def generate_multi_segment_video(
        self,
        prompt: str,
        product_name: str,
        image_path: str | None = None,
        num_segments: int = 2,
        timeout_sec: int = 600,
        product_description: str | None = None,
        custom_prompts: list[str] | None = None,
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
            video_file_path = None
            max_limit_retries = 12
            safety_blocked = False
            
            for retry_idx in range(max_limit_retries):
                # Nếu lần thử trước bị Gemini từ chối (safety refusal), dùng Safe Fallback Prompt cho clip này
                if retry_idx > 0 and safety_blocked:
                    seg_prompt = self._build_safe_fallback_prompt(product_name, i, num_segments)
                    logger.info(f"🛡️ Gemini từ chối clip {i+1}! Chuyển sang Safe Fallback Prompt: {seg_prompt}")
                elif custom_prompts and i < len(custom_prompts):
                    seg_prompt = custom_prompts[i]
                else:
                    seg_prompt = self._build_segment_prompt(prompt, product_name, i, num_segments, product_description=product_description)
                
                # Loại bỏ chuỗi (from reference image) để tránh làm Gemini hiểu nhầm bắt tải ảnh khi chưa có ảnh
                clean_p = seg_prompt.replace("(from reference image)", "").replace("(match reference image)", "").replace("  ", " ").strip()
                
                # Thêm câu lệnh kích hoạt tạo video 10s trực tiếp Tiếng Việt cho Gemini Web UI
                if image_path and Path(image_path).exists() and i == 0:
                    final_seg_prompt = f"Tạo cho tôi video 10s dựa trên hình ảnh đã tải lên về chủ đề: {clean_p}. Không hiển thị chữ hay logo watermark."
                else:
                    final_seg_prompt = f"Tạo cho tôi video 10s về chủ đề: {clean_p}. Không hiển thị chữ hay logo watermark."

                # Lưu danh sách video src hiện tại để phát hiện video mới
                existing_sources = set(self._get_all_video_sources())
                
                if i == 0 and image_path and retry_idx == 0:
                    self.upload_image_if_provided(image_path)
                
                self._close_overlays()
                if retry_idx > 0:
                    logger.info(f"✍️ Gửi lại prompt phân đoạn {i+1} (Lần thử {retry_idx + 1}): {final_seg_prompt}")
                else:
                    logger.info(f"✍️ Gửi prompt phân đoạn {i+1}: {final_seg_prompt}")
                
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
                    chat_input.fill(final_seg_prompt)
                except Exception:
                    import json
                    chat_input.evaluate(f"el => {{ el.innerText = {json.dumps(final_seg_prompt)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
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
                                
                            if self._check_safety_refusal(latest_text) or (len(latest_text) > 15 and time.time() - start_wait > 12):
                                logger.warning(f"⚠️ Phát hiện Gemini phản hồi bằng văn bản ('{latest_text[:60]}...') ở phân đoạn {i+1}! Chuyển sang Safe Fallback Prompt.")
                                safety_blocked = True
                                break
                    
                    time.sleep(2)
                
                if limit_blocked:
                    logger.info("⏳ Đang đợi 60 giây để hàng đợi tạo video của tài khoản trống rồi gửi lại...")
                    time.sleep(60)
                    continue
                
                # Nếu bị safety block, vòng lặp sau sẽ chuyển sang Safe Fallback Prompt
                if safety_blocked:
                    logger.warning(f"🔄 Phân đoạn {i+1} bị từ chối! Sẽ gửi Safe Fallback ở lần thử tiếp theo...")
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

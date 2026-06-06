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
                    logger.info(f"👉 Click nút đóng/chấp nhận overlay: {btn.text_content().strip()}")
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
 
        # Check xem đã login chưa bằng cách tìm ô input prompt
        try:
            self.page.wait_for_selector(
                'div[contenteditable="true"], textarea, div[class*="ql-editor"]',
                timeout=20000
            )
            logger.info("✅ Gemini đã sẵn sàng (đã đăng nhập)")
        except Exception as e:
            logger.error(f"❌ Không tìm thấy ô nhập liệu của Gemini. Có thể cookies đã hết hạn hoặc chưa đăng nhập! Chi tiết: {e}")
            try:
                Path("temp").mkdir(exist_ok=True)
                self.page.screenshot(path="temp/gemini_error.png")
                logger.info("📸 Đã chụp ảnh màn hình lỗi tại temp/gemini_error.png")
            except Exception as se:
                logger.debug(f"Không thể chụp ảnh lỗi: {se}")
            raise RuntimeError("Google session hết hạn hoặc chưa đăng nhập.")
 
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
            # 1. Click nút Upload ở dưới thanh chat
            upload_btn = self.page.locator('button[aria-label*="Upload"], button[aria-label*="Add"], button[aria-label*="Thêm"]').first
            try:
                upload_btn.click(timeout=5000)
            except Exception:
                upload_btn.evaluate("el => el.click()")
            self._delay()
 
            # 2. Bắt file chooser khi click vào nút "Upload files" (hoặc "Tải tệp lên") trong menu
            with self.page.expect_file_chooser() as fc_info:
                menu_item = self.page.locator(
                    "button[role='menuitem']:has-text('Upload files'), "
                    "button[role='menuitem']:has-text('Tải tệp lên'), "
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
 
    def generate_video(self, prompt: str, image_path: str | None = None, timeout_sec: int = 300) -> str:
        """
        Gửi prompt tạo video, đợi render xong và tải video về.
        Trả về đường dẫn tới file video .mp4 đã tải.
        """
        self.select_video_mode_if_needed()
 
        # Upload ảnh nếu có trước khi điền text
        if image_path:
            self.upload_image_if_provided(image_path)
 
        self._close_overlays()
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
 
        # Chờ tối đa 10s xem video có được tạo ngay không
        logger.info("⏳ Chờ xem video có được tạo ngay từ prompt đầu tiên không...")
        video_found = False
        start_wait = time.time()
        while time.time() - start_wait < 10:
            videos = self.page.locator('video')
            if videos.count() > 0:
                last_video = videos.last
                src = last_video.get_attribute("src")
                if src and (src.startswith("http") or src.startswith("blob:")):
                    video_found = True
                    break
            time.sleep(2)
  
        if not video_found:
            logger.info("⚠️ Không thấy video tạo ngay. Gửi thêm lệnh ép buộc tạo video: 'Hãy render video cho tôi từ thông tin trên.'")
            try:
                # Chờ cho đến khi nút Send hiển thị trở lại (Gemini đã trả lời xong kịch bản văn bản)
                send_btn = self.page.locator(
                    'button[aria-label*="Send"], button[aria-label*="Gửi"], button[class*="send-button"]'
                ).first
                logger.info("⏳ Đang chờ Gemini hoàn thành phản hồi chữ...")
                send_btn.wait_for(state="visible", timeout=90000)
                
                chat_input = self.page.locator(
                    'div[contenteditable="true"], textarea[placeholder*="Describe"], textarea[placeholder*="prompt"]'
                ).first
                self._close_overlays()
                try:
                    chat_input.click(timeout=5000)
                except Exception:
                    chat_input.evaluate("el => { el.focus(); el.click(); }")
                self._delay()
                
                try:
                    chat_input.fill("Hãy render video cho tôi đi")
                except Exception:
                    chat_input.evaluate("el => { el.innerText = 'Hãy render video cho tôi đi'; el.dispatchEvent(new Event('input', {bubbles: true})); }")
                self._delay()
                
                try:
                    send_btn.click(timeout=5000)
                except Exception:
                    send_btn.evaluate("el => el.click()")
                logger.info("⏳ Đã gửi prompt phụ: 'Hãy render video cho tôi'. Chờ kết xuất video...")
                self._delay()
            except Exception as e:
                logger.warning(f"⚠️ Gặp lỗi khi gửi prompt phụ: {e}")
 
        # Đợi quá trình render video hoàn tất.
        # Ta sẽ poll liên tục để phát hiện thẻ <video> xuất hiện trong tin nhắn phản hồi mới nhất.
        start_time = time.time()
        video_file_path = None
 
        logger.info("⏳ Chờ Gemini render video (có thể mất 1-3 phút)...")
        while time.time() - start_time < timeout_sec:
            # Check xem có video tag nào xuất hiện không
            videos = self.page.locator('video')
            if videos.count() > 0:
                logger.info("🎥 Đã phát hiện thấy video element xuất hiện trên màn hình!")
                # Lấy thẻ video cuối cùng
                last_video = videos.last
                
                # Chờ cho đến khi video có source hoặc src không trống
                src = last_video.get_attribute("src")
                if src and (src.startswith("http") or src.startswith("blob:")):
                    logger.info(f"🔗 Video source: {src}")
                    
                    # Thử download bằng 2 cách:
                    # Cách 1: Download qua click nút tải xuống nếu có
                    # Cách 2: Tự download blob bằng JavaScript và lưu thành file
                    video_file_path = self._download_video_content(src)
                    if video_file_path:
                        break
            
            # Đợi thêm một chút trước khi check tiếp
            time.sleep(2)
 
        if not video_file_path:
            raise TimeoutError("❌ Đã quá thời gian chờ (timeout) nhưng vẫn chưa thấy video được tạo xong.")
 
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

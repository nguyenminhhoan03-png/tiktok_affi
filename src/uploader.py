import time
import random
from pathlib import Path
from playwright.sync_api import Page
from loguru import logger


def human_delay(min_s: float = 1.5, max_s: float = 3.5) -> None:
    """Sleep ngẫu nhiên để giả lập hành vi người dùng thật"""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


class TikTokUploader:
    """
    Tự động upload video lên TikTok Studio và gán sản phẩm affiliate.
    """

    UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"

    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        self.delay_min = config.get("delay_between_actions_min", 1.5)
        self.delay_max = config.get("delay_between_actions_max", 3.5)
        self.type_delay = config.get("type_delay_ms", 80)

    def _delay(self) -> None:
        human_delay(self.delay_min, self.delay_max)

    # ------------------------------------------------------------------
    # Bước 1: Mở trang upload
    # ------------------------------------------------------------------
    def open_upload_page(self) -> None:
        logger.info("🌐 Mở TikTok Studio Upload...")
        self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
        # Thay vì networkidle (dễ bị treo do theo dõi nền), ta chờ input file được gắn vào DOM (attached)
        # Vì input file type=file thường được ẩn bằng CSS (display: none/opacity: 0), ta chờ state="attached"
        try:
            self.page.wait_for_selector('input[type="file"]', state="attached", timeout=30000)
        except Exception:
            # Fallback chờ nút Select files visible
            self.page.wait_for_selector('button:has-text("Select files"), button:has-text("Chọn file")', state="visible", timeout=10000)
        self._delay()
        logger.info("✅ Đã mở trang upload")

    # ------------------------------------------------------------------
    # Bước 2: Upload file video
    # ------------------------------------------------------------------
    def upload_video(self, video_path: str) -> None:
        logger.info(f"📤 Đang upload video: {video_path}")
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

        # Tìm input file ẩn và set file
        file_input = self.page.locator('input[type="file"]').first
        file_input.set_input_files(str(path))

        logger.info("⏳ Chờ video bắt đầu upload...")
        try:
            # Chờ thanh tiến trình upload xuất hiện (tối đa 1.5s)
            self.page.wait_for_selector(
                'div[class*="upload-progress"], div[class*="uploading"], div[class*="progress"]',
                state="visible",
                timeout=1500
            )
            logger.info("⏳ Đang upload video...")
        except Exception:
            logger.info("⏳ Tiến trình upload nhanh hoặc đang xử lý tiếp...")

        # Chờ upload hoàn tất bằng cách phát hiện chữ "Uploaded" / "Đã tải lên" hoặc nút "Replace" / "Thay thế" xuất hiện
        try:
            self.page.wait_for_selector(
                'text="Uploaded", text="Đã tải lên", text="Upload complete", text="Tải lên hoàn tất", '
                'button:has-text("Replace"), button:has-text("Thay thế"), '
                'button:has-text("Change"), button:has-text("Thay đổi"), '
                '[class*="replace" i], [class*="change" i]',
                state="visible",
                timeout=self.config.get("upload_timeout_ms", 120000),
            )
            logger.info("✅ Upload video hoàn tất")
        except Exception as e:
            logger.warning(f"⚠️ Gặp lỗi khi chờ upload hoàn tất: {e}")
        self._delay()

    def _close_popups(self) -> None:
        """Đóng các popup/modal thông báo của TikTok Studio nếu xuất hiện"""
        try:
            popups = [
                'button:has-text("Got it")',
                'button:has-text("Đã hiểu")',
                'button:has-text("Close")',
                'button:has-text("Đóng")',
                'div[class*="close"]',
                'svg[class*="close"]',
                '.tiktok-modal-close'
            ]
            for selector in popups:
                btn = self.page.locator(selector).first
                if btn.is_visible():
                    logger.info(f"🧹 Phát hiện và đang đóng popup: {selector}")
                    btn.click()
                    self._delay()
        except Exception as e:
            logger.debug(f"Không có popup hoặc gặp lỗi khi đóng popup: {e}")

    # ------------------------------------------------------------------
    # Bước 3: Điền caption + hashtag
    # ------------------------------------------------------------------
    def fill_caption(self, caption: str | None = None, product_name: str | None = None) -> None:
        # Tự động dọn dẹp các popup cản trở trước khi điền caption
        self._close_popups()
        
        text = caption or self.config.get("default_caption", "")
        if not text:
            logger.warning("⚠️ Không có caption, bỏ qua bước này")
            return

        # 1. Thử tìm ô nhập Title (Tiêu đề) nếu có trên giao diện
        try:
            title_box = self.page.locator(
                'input[placeholder*="Title"], input[placeholder*="title"], '
                'input[placeholder*="Tiêu đề"], div[class*="title-input"] input, '
                'div[class*="title"] input'
            ).first
            if title_box.is_visible(timeout=3000):
                title_text = product_name or "Video Review"
                if len(title_text) > 80:
                    title_text = title_text[:77] + "..."
                logger.info(f"✏️ Phát hiện ô Title riêng biệt, điền: {title_text}")
                title_box.click()
                self._delay()
                self.page.keyboard.press("Control+A")
                self._delay()
                self.page.keyboard.press("Backspace")
                self._delay()
                title_box.type(title_text, delay=self.type_delay, timeout=90000)
                self._delay()
        except Exception as te:
            logger.debug(f"Không có ô Title riêng biệt hoặc bỏ qua: {te}")

        # 2. Điền Description / Caption
        logger.info(f"✏️ Điền caption: {text[:50]}...")
        caption_box = self.page.locator(
            'div[contenteditable="true"], textarea[placeholder*="caption"], '
            'div[data-e2e="caption-input"], div[class*="editor"] div[contenteditable="true"]'
        ).first
        caption_box.click()
        self._delay()
        
        # Xóa toàn bộ nội dung mặc định (ví dụ tên file video tự động sinh) trước khi nhập caption
        self.page.keyboard.press("Control+A")
        self._delay()
        self.page.keyboard.press("Backspace")
        self._delay()
        
        caption_box.type(text, delay=self.type_delay, timeout=90000)
        self._delay()
        logger.info("✅ Điền caption xong")

    # ------------------------------------------------------------------
    # Bước 4: Gán sản phẩm Affiliate
    # ------------------------------------------------------------------
    def tag_affiliate_product(self, product_name: str | None = None) -> bool:
        name = product_name or self.config.get("product_name", "")
        if not name:
            logger.warning("⚠️ Chưa cấu hình tên sản phẩm trong config.json")
            return False

        logger.info(f"🛍️ Bắt đầu gắn sản phẩm affiliate: {name}")

        try:
            # ── BƯỚC 1: Click nút "+ Add" trong phần "Add link" ──
            logger.info("👆 Bước 1: Click nút '+ Add' trong phần Add link...")
            add_btn = self.page.locator(
                'div[class*="anchor-tag"] button, '
                'button:has-text("+ Add"), '
                'button:has-text("+ Thêm")'
            ).first
            add_btn.wait_for(state="visible", timeout=10000)
            try:
                add_btn.click(timeout=5000)
            except Exception:
                add_btn.evaluate("el => el.click()")
            self._delay()

            # ── BƯỚC 2: Trong modal "Add link" – click "Products" rồi "Next" ──
            logger.info("👆 Bước 2: Chọn 'Products' trong modal Add link...")
            products_btn = self.page.locator(
                'button.TUXSelect-button--large, '
                'button[class*="TUXSelect-button"], '
                'button[role="combobox"]'
            ).first
            products_btn.wait_for(state="visible", timeout=10000)
            try:
                products_btn.click(timeout=3000)
            except Exception:
                products_btn.evaluate("el => el.click()")
            self._delay()

            # Click "Next" trong dialog "Add link"
            next_in_addlink = self.page.locator(
                'div[role="dialog"] button:has-text("Next"), '
                'div[role="dialog"] button:has-text("Tiếp theo")'
            ).first
            next_in_addlink.wait_for(state="visible", timeout=5000)
            try:
                next_in_addlink.click(timeout=3000)
            except Exception:
                next_in_addlink.evaluate("el => el.click()")
            self._delay()

            # ── BƯỚC 3: Modal "Add product links" – search tên sản phẩm ──
            logger.info("🔍 Bước 3: Tìm kiếm sản phẩm trong modal Add product links...")
            search_input = self.page.locator(
                'input[placeholder*="Search products"], '
                'input[placeholder*="Tìm kiếm"], '
                'input.TUXTextInputCore-input[type="text"]'
            ).first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.click()
            # Chỉ dùng 20 ký tự đầu để search cho chính xác
            search_input.fill(name[:20])
            self._delay()
            self.page.wait_for_timeout(2000)  # Chờ kết quả tìm kiếm load

            # ── BƯỚC 4: Click radio button chọn sản phẩm đầu tiên ──
            logger.info("☑️  Bước 4: Chọn sản phẩm đầu tiên trong danh sách...")
            first_row = self.page.locator('tbody tr').first
            first_row.wait_for(state="visible", timeout=10000)

            # Thử click trực tiếp vào span TUXRadio
            radio = first_row.locator(
                'span[class*="TUXRadio"], '
                'input[type="radio"], '
                '[class*="radio" i]'
            ).first
            try:
                radio.click(timeout=3000)
            except Exception:
                # Fallback: dispatch mouse events lên cả row
                first_row.evaluate("""el => {
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                    el.dispatchEvent(new MouseEvent('mouseup',   {bubbles: true, cancelable: true}));
                    el.click();
                }""")
            logger.info("✅ Đã chọn sản phẩm")
            self.page.wait_for_timeout(1000)  # Chờ React cập nhật nút Next

            # ── BƯỚC 5: Click "Next" (đã active sau khi chọn sản phẩm) ──
            logger.info("👆 Bước 5: Click Next sau khi chọn sản phẩm...")
            next_after_select = self.page.locator(
                'button.TUXButton--primary:has-text("Next"), '
                'button[class*="TUXButton--primary"]:has-text("Next"), '
                'button[class*="TUXButton-primary"]:has-text("Next")'
            ).first
            next_after_select.wait_for(state="visible", timeout=5000)
            try:
                next_after_select.click(timeout=3000)
            except Exception:
                next_after_select.evaluate("el => el.click()")
            self._delay()

            # ── BƯỚC 6: Click "Add" để xác nhận tên sản phẩm ──
            logger.info("✅ Bước 6: Click 'Add' để xác nhận và hoàn tất gắn sản phẩm...")
            add_confirm = self.page.locator(
                'button.TUXButton--primary:has-text("Add"), '
                'button[class*="TUXButton--primary"]:has-text("Add"), '
                'button[class*="TUXButton-primary"]:has-text("Add")'
            ).first
            add_confirm.wait_for(state="visible", timeout=5000)
            try:
                add_confirm.click(timeout=3000)
            except Exception:
                add_confirm.evaluate("el => el.click()")
            self._delay()

            logger.info("🎉 Gắn sản phẩm affiliate thành công!")
            return True

        except Exception as e:
            logger.error(f"❌ Lỗi khi gán sản phẩm: {e}")
            logger.warning("⚠️ Bỏ qua bước gán sản phẩm, vẫn tiếp tục")
            return False

    # ------------------------------------------------------------------
    # Bước 5: Đăng video
    # ------------------------------------------------------------------
    def post_video(self) -> bool:
        logger.info("🚀 Đang đăng video...")
        try:
            post_btn = self.page.locator(
                'button[data-e2e="post_video_button"], '
                'button:has-text("Post"), '
                'button:has-text("Đăng"), '
                'button[data-e2e="post-btn"]'
            ).first
            post_btn.wait_for(state="visible", timeout=10000)
            
            try:
                post_btn.click(timeout=5000)
            except Exception:
                logger.warning("⚠️ Không thể click bình thường vào nút Post, dùng JavaScript click...")
                post_btn.evaluate("el => el.click()")
 
            # Chờ trang chuyển hướng hoặc thông báo thành công
            try:
                self.page.wait_for_url("**/manage**", timeout=15000)
                logger.info("🎉 Đăng video thành công!")
            except Exception:
                logger.info("ℹ️ Đã click nút Post thành công. Video đang được xử lý và đăng tải.")
            return True
 
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng video: {e}")
            return False

    # ------------------------------------------------------------------
    # Chạy toàn bộ pipeline
    # ------------------------------------------------------------------
    def run(self, video_path: str, caption: str | None = None, product_name: str | None = None) -> bool:
        """
        Chạy pipeline: Upload → Điền caption → Gắn sản phẩm → Dừng lại để người dùng tự nhấn Post.
        """
        try:
            self.open_upload_page()
            self.upload_video(video_path)
            self.fill_caption(caption, product_name)
            self.tag_affiliate_product(product_name)
            logger.info("✅ Đã điền caption và gắn sản phẩm xong. Dừng lại để bạn tự nhấn nút Post.")
            return True
        except Exception as e:
            logger.error(f"❌ Pipeline thất bại: {e}")
            return False

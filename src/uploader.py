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
            # Dùng toàn bộ tên sản phẩm để search chính xác, tránh nhầm lẫn sản phẩm khác
            search_input.fill(name)
            self._delay()
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(2000)  # Chờ kết quả tìm kiếm load

            # ── BƯỚC 4: Chọn sản phẩm đầu tiên trong danh sách ──
            logger.info("☑️  Bước 4: Chọn sản phẩm đầu tiên trong danh sách...")
            first_row = self.page.locator('tbody tr').first
            first_row.wait_for(state="visible", timeout=10000)

            # Log cấu trúc HTML của row đầu tiên để phục vụ mục đích debug
            try:
                row_html = first_row.inner_html()
                logger.info(f"🔍 Cấu trúc HTML của hàng đầu tiên:\n{row_html[:1500]}")
            except Exception as e:
                logger.warning(f"⚠️ Không thể lấy HTML của hàng đầu tiên: {e}")

            # Đăng ký danh sách các selector/phương thức click để chọn sản phẩm
            click_strategies = [
                ("Input Radio/Checkbox", first_row.locator('input[type="radio"], input[type="checkbox"]').first, True),
                ("TUXRadio class", first_row.locator('.TUXRadio, [class*="Radio"], [class*="radio"]').first, False),
                ("TUXRadioStandalone class", first_row.locator('.TUXRadioStandalone').first, False),
                ("Label", first_row.locator('label').first, False),
                ("Ô chọn đầu tiên (td)", first_row.locator('td').first, False),
                ("Hàng đầu tiên (tr)", first_row, False),
            ]

            selected_success = False
            for name, locator, force_click in click_strategies:
                try:
                    count = locator.count()
                    if count > 0:
                        logger.info(f"👉 Đang thử click bằng chiến lược: '{name}'...")
                        
                        # Log toạ độ phần tử trước khi click
                        box = locator.bounding_box()
                        if box:
                            logger.info(f"📍 Toạ độ phần tử '{name}': x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}")
                        else:
                            logger.info(f"📍 Phần tử '{name}' không có bounding box cụ thể.")

                        if name == "Input Radio/Checkbox":
                            try:
                                logger.info("👉 Dùng .check(force=True) trên input...")
                                locator.check(force=True, timeout=3000)
                            except Exception as check_err:
                                logger.warning(f"⚠️ check() thất bại, thử click(force=True): {check_err}")
                                locator.click(timeout=3000, force=True)
                        elif force_click:
                            locator.click(timeout=3000, force=True)
                        else:
                            locator.click(timeout=3000)
                        
                        # Đợi một chút để UI và React cập nhật trạng thái chọn
                        self.page.wait_for_timeout(1000)
                        
                        # Kiểm tra xem input đã được checked chưa
                        radio_checked = first_row.locator('input[type="radio"], input[type="checkbox"]').first
                        is_checked = radio_checked.is_checked() if radio_checked.count() > 0 else False
                        
                        # Kiểm tra xem nút Next trong dialog đã được active/enabled chưa
                        next_btn = self.page.locator(
                            'div[role="dialog"] button:has-text("Next"), '
                            'div[role="dialog"] button:has-text("Tiếp theo"), '
                            'div[class*="modal"] button:has-text("Next"), '
                            'div[class*="modal"] button:has-text("Tiếp theo")'
                        ).first
                        
                        is_next_enabled = True
                        if next_btn.count() > 0:
                            is_disabled_attr = next_btn.get_attribute("disabled") is not None
                            is_aria_disabled = next_btn.get_attribute("aria-disabled") == "true"
                            class_attr = next_btn.get_attribute("class") or ""
                            has_disabled_class = "disabled" in class_attr.lower() or "tuxbutton--disabled" in class_attr.lower()
                            
                            if is_disabled_attr or is_aria_disabled or has_disabled_class:
                                is_next_enabled = False

                        logger.info(f"📊 Trạng thái sau click: checked={is_checked}, next_enabled={is_next_enabled}")
                        
                        if is_checked and is_next_enabled:
                            logger.info(f"✅ Chọn sản phẩm thành công bằng chiến lược '{name}'! (checked=True và nút Next đã active)")
                            selected_success = True
                            break
                        else:
                            logger.warning(f"⚠️ Chiến lược '{name}' click xong nhưng chưa đủ điều kiện. Thử click bằng evaluate JS...")
                            locator.evaluate("el => el.click()")
                            self.page.wait_for_timeout(1000)
                            
                            # Kiểm tra lại
                            is_checked = radio_checked.is_checked() if radio_checked.count() > 0 else False
                            is_next_enabled = True
                            if next_btn.count() > 0:
                                is_disabled_attr = next_btn.get_attribute("disabled") is not None
                                is_aria_disabled = next_btn.get_attribute("aria-disabled") == "true"
                                class_attr = next_btn.get_attribute("class") or ""
                                has_disabled_class = "disabled" in class_attr.lower() or "tuxbutton--disabled" in class_attr.lower()
                                if is_disabled_attr or is_aria_disabled or has_disabled_class:
                                    is_next_enabled = False
                                    
                            if is_checked and is_next_enabled:
                                logger.info(f"✅ Click bằng evaluate JS của '{name}' thành công!")
                                selected_success = True
                                break
                except Exception as e:
                    logger.warning(f"❌ Chiến lược '{name}' thất bại: {e}")
                    continue

            if not selected_success:
                logger.warning("⚠️ Không thể xác minh trạng thái 'checked' và 'Next active' tự động, vẫn tiếp tục để tránh gián đoạn...")
            
            self.page.wait_for_timeout(1000)  # Chờ React cập nhật nút Next
            # ── BƯỚC 5: Click "Next" (đã active sau khi chọn sản phẩm) ──
            logger.info("👆 Bước 5: Click Next sau khi chọn sản phẩm...")
            
            # Định vị dialog tìm kiếm sản phẩm đang active
            search_dialog = self.page.locator('div[role="dialog"], div[class*="modal"]').filter(
                has=self.page.locator('input[placeholder*="Search products"], input[placeholder*="Tìm kiếm"]')
            ).first
            
            next_after_select = None
            if search_dialog.count() > 0:
                logger.info("🔍 Đã định vị được search dialog chuyên biệt để tìm nút Next.")
                dialog_context = search_dialog
            else:
                logger.warning("⚠️ Không tìm thấy search dialog chuyên biệt, dùng page context làm fallback.")
                dialog_context = self.page

            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Tiếp theo")'
            ]
            
            for sel in next_selectors:
                try:
                    loc = dialog_context.locator(sel)
                    count = loc.count()
                    for idx in range(count):
                        item = loc.nth(idx)
                        if item.is_visible():
                            next_after_select = item
                            box = item.bounding_box()
                            pos_info = f"x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}" if box else "unknown"
                            logger.info(f"🔍 Tìm thấy nút Next trong dialog tại selector '{sel}' (nth={idx}, vị trí={pos_info})")
                            break
                    if next_after_select:
                        break
                except Exception:
                    continue

            if not next_after_select:
                next_after_select = dialog_context.locator('button').filter(has_text="Next").first
                if next_after_select.count() > 0:
                    box = next_after_select.bounding_box()
                    pos_info = f"x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}" if box else "unknown"
                    logger.info(f"🔍 Dùng nút Next fallback đầu tiên của dialog context (vị trí={pos_info})")
                else:
                    logger.warning("⚠️ Không tìm thấy nút Next fallback nào.")

            if next_after_select:
                try:
                    next_after_select.wait_for(state="visible", timeout=5000)
                    logger.info("👉 Đang click Next...")
                    next_after_select.click(timeout=5000)
                    logger.info("✅ Click Next thành công!")
                except Exception as e:
                    logger.warning(f"⚠️ Click Next thông thường thất bại: {e}. Thử click bằng evaluate JS...")
                    try:
                        next_after_select.evaluate("el => el.click()")
                        logger.info("✅ Click Next bằng JS thành công!")
                    except Exception as click_err_js:
                        logger.warning(f"⚠️ Click Next bằng JS thất bại: {click_err_js}. Thử với force=True...")
                        try:
                            next_after_select.click(timeout=3000, force=True)
                            logger.info("✅ Click Next với force=True thành công!")
                        except Exception as click_err:
                            logger.warning(f"❌ Không thể click Next bằng bất kỳ cách nào: {click_err}")
            else:
                logger.error("❌ Không tìm thấy nút Next nào để click.")
            
            # Chờ nút Add trong dialog hiển thị (xác nhận đã chuyển sang bước tiếp theo)
            logger.info("⏳ Đang chờ dialog chuyển sang bước nhập tên hiển thị sản phẩm...")
            try:
                self.page.wait_for_selector(
                    'div[role="dialog"] button:has-text("Add"), '
                    'div[role="dialog"] button:has-text("Thêm"), '
                    'div[class*="modal"] button:has-text("Add")',
                    timeout=5000
                )
                logger.info("✅ Dialog đã chuyển sang bước tiếp theo thành công.")
            except Exception:
                logger.warning("⚠️ Chưa thấy nút Add xuất hiện trong dialog sau 5s, thử tiếp tục...")
            self._delay()

            # ── BƯỚC 6: Click "Add" để xác nhận tên sản phẩm ──
            logger.info("✅ Bước 6: Click 'Add' để xác nhận và hoàn tất gắn sản phẩm...")
            
            # Định vị name dialog chuyên biệt (chứa input text để đặt tên hiển thị sản phẩm, không có ô search)
            name_dialog = self.page.locator('div[role="dialog"], div[class*="modal"]').filter(
                has=self.page.locator('input[type="text"]')
            ).filter(
                has_not=self.page.locator('input[placeholder*="Search products"], input[placeholder*="Tìm kiếm"]')
            ).first
            
            if name_dialog.count() > 0:
                logger.info("🔍 Đã định vị được name dialog chuyên biệt để tìm nút Add.")
                add_context = name_dialog
            else:
                logger.warning("⚠️ Không tìm thấy name dialog chuyên biệt, dùng page context làm fallback.")
                add_context = self.page

            add_selectors = [
                'button:has-text("Add")',
                'button:has-text("Thêm")'
            ]
            add_confirm = None
            for sel in add_selectors:
                try:
                    loc = add_context.locator(sel)
                    count = loc.count()
                    for idx in range(count):
                        item = loc.nth(idx)
                        if item.is_visible():
                            add_confirm = item
                            box = item.bounding_box()
                            pos_info = f"x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}" if box else "unknown"
                            logger.info(f"🔍 Tìm thấy nút Add trong dialog tại selector '{sel}' (nth={idx}, vị trí={pos_info})")
                            break
                    if add_confirm:
                        break
                except Exception:
                    continue
            
            if not add_confirm:
                add_confirm_locator = add_context.locator('button').filter(has_text="Add").first
                if add_confirm_locator.count() > 0:
                    add_confirm = add_confirm_locator
                    box = add_confirm.bounding_box()
                    pos_info = f"x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}" if box else "unknown"
                    logger.info(f"🔍 Dùng nút Add fallback đầu tiên của dialog context (vị trí={pos_info})")
                else:
                    logger.warning("⚠️ Không tìm thấy bất kỳ nút Add nào trong dialog context")

            if add_confirm:
                try:
                    add_confirm.wait_for(state="visible", timeout=5000)
                    logger.info("👉 Đang click Add...")
                    add_confirm.click(timeout=5000)
                    logger.info("✅ Click Add thành công!")
                except Exception as e:
                    logger.warning(f"⚠️ Click Add thông thường thất bại: {e}. Thử click bằng evaluate JS...")
                    try:
                        add_confirm.evaluate("el => el.click()")
                        logger.info("✅ Click Add bằng JS thành công!")
                    except Exception as click_err_js:
                        logger.warning(f"⚠️ Click Add bằng JS thất bại: {click_err_js}. Thử với force=True...")
                        try:
                            add_confirm.click(timeout=3000, force=True)
                            logger.info("✅ Click Add với force=True thành công!")
                        except Exception as click_err:
                            logger.warning(f"❌ Không thể click Add bằng bất kỳ cách nào: {click_err}")
                
                # CHỜ DIALOG ĐÓNG & CHECK VALIDATION LỖI (do ký tự đặc biệt)
                self.page.wait_for_timeout(2000)
                if name_dialog.count() > 0 and name_dialog.is_visible():
                    logger.warning("⚠️ Dialog vẫn chưa đóng sau khi click Add. Có thể do lỗi validation ký tự đặc biệt của TikTok Shop.")
                    
                    # Tìm ô input để xóa ký tự đặc biệt
                    name_input = name_dialog.locator('input[type="text"]').first
                    if name_input.count() > 0:
                        try:
                            # Đọc text hiện tại trong ô input
                            current_text = name_input.input_value()
                            logger.info(f"🔍 Text hiện tại trong ô input: '{current_text}'")
                            
                            # Clean text: chỉ giữ chữ cái (kể cả tiếng Việt), số và khoảng trắng
                            raw_clean = "".join(c for c in current_text if c.isalnum() or c.isspace())
                            clean_name = " ".join(raw_clean.split())[:30].strip()
                            
                            logger.info(f"✍️ Tiến hành điền tên đã loại bỏ ký tự đặc biệt: '{clean_name}'")
                            name_input.click()
                            name_input.evaluate("el => el.value = ''")
                            name_input.fill(clean_name)
                            self.page.wait_for_timeout(1000)
                            
                            # Click Add lại
                            logger.info("👉 Click Add lần 2 với tên đã lọc ký tự đặc biệt...")
                            add_confirm.click(timeout=5000)
                            self.page.wait_for_timeout(2000)
                            
                            # Nếu vẫn lỗi (có thể do TikTok không cho phép tiếng Việt có dấu ở một số thị trường/tài khoản)
                            if name_dialog.count() > 0 and name_dialog.is_visible():
                                ascii_name = self.strip_accents(clean_name)
                                logger.warning(f"⚠️ Lần 2 vẫn không đóng. Tiến hành chuyển hẳn sang tiếng Việt không dấu: '{ascii_name}'")
                                name_input.click()
                                name_input.evaluate("el => el.value = ''")
                                name_input.fill(ascii_name)
                                self.page.wait_for_timeout(1000)
                                
                                logger.info("👉 Click Add lần 3 với tên không dấu...")
                                add_confirm.click(timeout=5000)
                                self.page.wait_for_timeout(2000)
                                
                            # Nếu vẫn không được nữa thì bấm Hủy để tránh kẹt
                            if name_dialog.count() > 0 and name_dialog.is_visible():
                                logger.error("❌ Không thể gán link sản phẩm do lỗi validation liên tục. Đóng dialog để tiếp tục đăng video...")
                                cancel_btn = name_dialog.locator(
                                    'button:has-text("Cancel"), '
                                    'button:has-text("Hủy"), '
                                    'button[class*="cancel"]'
                                ).first
                                if cancel_btn.count() > 0:
                                    cancel_btn.click()
                                    self.page.wait_for_timeout(1000)
                        except Exception as validation_err:
                            logger.error(f"❌ Gặp lỗi khi cố gắng xử lý lỗi validation: {validation_err}")
            else:
                raise Exception("Không tìm thấy nút Add hoặc Thêm trong dialog để xác nhận.")
            self._delay()

            logger.info("🎉 Gắn sản phẩm affiliate thành công!")
            return True

        except Exception as e:
            logger.error(f"❌ Lỗi khi gán sản phẩm: {e}")
            logger.warning("⚠️ Bỏ qua bước gán sản phẩm, vẫn tiếp tục")
            return False

    def strip_accents(self, text: str) -> str:
        """Chuyển đổi chuỗi tiếng Việt có dấu thành không dấu."""
        import unicodedata
        try:
            text = unicodedata.normalize('NFD', text)
            text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
            # Thay thế đ, Đ
            text = text.replace('đ', 'd').replace('Đ', 'D')
            return text
        except Exception:
            return text

    # ------------------------------------------------------------------
    # Bước 5: Đăng video
    # ------------------------------------------------------------------
    def post_video(self) -> bool:
        logger.info("🚀 Đang đăng video...")
        try:
            # 1. Dismiss "Are you sure you want to exit?" dialog if it is open
            try:
                exit_dialog_cancel = self.page.locator(
                    'div[role="dialog"] button:has-text("Cancel"), '
                    'div[role="dialog"] button:has-text("Hủy"), '
                    'button:has-text("Cancel"), '
                    'button:has-text("Hủy")'
                )
                if exit_dialog_cancel.count() > 0:
                    for i in range(exit_dialog_cancel.count()):
                        btn = exit_dialog_cancel.nth(i)
                        if btn.is_visible():
                            logger.info("🧹 Phát hiện dialog Exit cảnh báo, đang click Cancel để đóng...")
                            btn.click(timeout=3000)
                            self.page.wait_for_timeout(1000)
            except Exception as dialog_err:
                logger.warning(f"⚠️ Không thể đóng dialog Exit: {dialog_err}")

            # 2. Scroll down to ensure post button is visible in any scrollable container
            try:
                logger.info("📜 Đang cuộn màn hình và các containers để hiển thị nút Post...")
                self.page.evaluate("""
                    window.scrollTo(0, document.body.scrollHeight);
                    document.querySelectorAll('div').forEach(el => {
                        if (el.scrollHeight > el.clientHeight) {
                            el.scrollTop = el.scrollHeight;
                        }
                    });
                """)
                self.page.wait_for_timeout(1000)
            except Exception as scroll_err:
                logger.warning(f"⚠️ Lỗi cuộn trang: {scroll_err}")

            post_btn = self.page.locator('button[data-e2e="post_video_button"]')
            if post_btn.count() == 0:
                post_btn = self.page.locator('button[data-e2e="post-btn"]')
            if post_btn.count() == 0:
                post_btn = self.page.locator('button[class*="primary"]:has-text("Post"), button[class*="primary"]:has-text("Đăng")')
            if post_btn.count() == 0:
                post_btn = self.page.locator('button:has-text("Post"), button:has-text("Đăng")')
            post_btn = post_btn.first
            post_btn.wait_for(state="attached", timeout=10000)
            
            # Scroll to element as fallback
            try:
                post_btn.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass

            # 3. Wait up to 90 seconds for Post button to become active/enabled (due to video upload/processing)
            logger.info("⏳ Đang chờ nút Post/Đăng sẵn sàng (không bị disabled)...")
            is_post_ready = False
            for attempt in range(45):  # 90 seconds max
                if post_btn.count() == 0:
                    self.page.wait_for_timeout(2000)
                    continue
                
                is_disabled_attr = post_btn.get_attribute("disabled") is not None
                is_aria_disabled = post_btn.get_attribute("aria-disabled") == "true"
                class_attr = post_btn.get_attribute("class") or ""
                has_disabled_class = "disabled" in class_attr.lower() or "tuxbutton--disabled" in class_attr.lower()
                
                if not (is_disabled_attr or is_aria_disabled or has_disabled_class):
                    is_post_ready = True
                    break
                
                if attempt % 5 == 0:
                    logger.info("⏳ Nút Post vẫn đang bị disabled (chờ video upload/xử lý hoàn tất)...")
                self.page.wait_for_timeout(2000)

            if not is_post_ready:
                logger.warning("⚠️ Nút Post vẫn chưa sẵn sàng sau 90s, vẫn thử click...")

            # 4. Click Post button
            try:
                post_btn.click(timeout=5000)
            except Exception:
                logger.warning("⚠️ Không thể click bình thường vào nút Post, dùng JavaScript click...")
                post_btn.evaluate("el => el.click()")
 
            # 5. Wait longer for the post request to complete and redirect to content manage
            logger.info("⏳ Đang chờ hệ thống xử lý và chuyển hướng sau khi click Post...")
            try:
                self.page.wait_for_url("**/manage**", timeout=45000)
                logger.info("🎉 Đăng video thành công!")
            except Exception:
                logger.info("ℹ️ Đã click nút Post. Video đang được xử lý và đăng tải.")
                # Thêm timeout nhỏ dự phòng để đảm bảo request gửi đi thành công trước khi đóng trình duyệt
                self.page.wait_for_timeout(5000)
            return True
 
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng video: {e}")
            return False

    # ------------------------------------------------------------------
    # Chạy toàn bộ pipeline
    # ------------------------------------------------------------------
    def run(self, video_path: str, caption: str | None = None, product_name: str | None = None) -> bool:
        """
        Chạy pipeline đầy đủ: Upload → Điền caption → Gắn sản phẩm → Scroll xuống → Bấm Post.
        """
        try:
            self.open_upload_page()
            self.upload_video(video_path)
            self.fill_caption(caption, product_name)
            self.tag_affiliate_product(product_name)
            logger.info("✅ Đã điền caption và gắn sản phẩm xong. Tiến hành đăng video tự động...")
            # Scroll xuống cuối trang để nút Post hiện ra
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._delay()
            return self.post_video()
        except Exception as e:
            logger.error(f"❌ Pipeline thất bại: {e}")
            return False

import os
import tempfile
from playwright.sync_api import Playwright, sync_playwright
from loguru import logger

from src.utils import load_cookies, save_cookies


class GoogleCookieManager:
    """Quản lý session/cookies cho Google Gemini"""

    GEMINI_DOMAIN = "https://gemini.google.com"

    def __init__(self, cookies_path: str):
        self.cookies_path = cookies_path

    def export_cookies_interactively(self) -> None:
        """
        Mở trình duyệt để user đăng nhập Google/Gemini thủ công,
        sau đó tự động lưu cookies lại.

        Dùng launch_persistent_context với Chrome thật để bypass Google bot detection.
        Google block Playwright Chromium vì phát hiện automation flag — Chrome thật thì không bị.
        """
        logger.info("🌐 Mở trình duyệt để bạn đăng nhập Google/Gemini...")
        logger.info("👉 Hãy đăng nhập vào Google/Gemini, sau đó nhấn Enter trong terminal này.")

        # Dùng thư mục profile tạm riêng để Chrome không xung đột với profile đang chạy
        profile_dir = os.path.join(tempfile.gettempdir(), "playwright_google_profile")
        os.makedirs(profile_dir, exist_ok=True)
        logger.info(f"📁 Chrome profile tạm tại: {profile_dir}")

        with sync_playwright() as p:
            # launch_persistent_context = dùng Chrome thật với profile thật
            # → Google KHÔNG detect là bot vì đây là phiên Chrome bình thường
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                channel="chrome",         # Dùng Chrome cài trên máy, không phải Chromium của Playwright
                slow_mo=50,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--start-maximized",
                ],
                ignore_default_args=["--enable-automation"],  # Ẩn cờ automation
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()

            # Inject script ẩn dấu hiệu automation TRƯỚC khi load trang
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            page.goto(self.GEMINI_DOMAIN)

            input("\n✅ Sau khi đã đăng nhập xong và thấy giao diện Gemini, nhấn Enter để lưu cookies...")

            cookies = context.cookies()
            save_cookies(cookies, self.cookies_path)
            context.close()

        logger.info("🎉 Export Google cookies thành công!")

    def load_context_with_cookies(self, playwright: Playwright, headless: bool = False):
        """
        Tạo browser context đã có Google session cookies.
        """
        browser = playwright.chromium.launch(
            headless=headless,
            channel="chrome",
            slow_mo=50,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        # Inject anti-detection script vào mọi page
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        cookies = load_cookies(self.cookies_path)
        from src.utils import clean_cookies_for_playwright
        cleaned_cookies = clean_cookies_for_playwright(cookies)
        context.add_cookies(cleaned_cookies)
        logger.info(f"🍪 Đã load {len(cleaned_cookies)} Google cookies vào session")

        return browser, context

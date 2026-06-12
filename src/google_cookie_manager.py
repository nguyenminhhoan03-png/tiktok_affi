import os
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright
from loguru import logger

from src.utils import load_cookies, save_cookies

# Thư mục profile Chrome cố định — session Google được lưu vĩnh viễn ở đây
GOOGLE_PROFILE_DIR = str(Path("./profiles/google").resolve())


class GoogleCookieManager:
    """Quản lý session/cookies cho Google Gemini.

    Chiến lược:
    - Dùng launch_persistent_context với profile Chrome cố định (./profiles/google/).
    - Session Google được lưu trong profile giống trình duyệt thật → không cần nhập
      lại cookie hay đăng nhập lại mỗi lần chạy.
    - Fallback inject cookie JSON nếu profile chưa tồn tại.
    """

    GEMINI_DOMAIN = "https://gemini.google.com"

    def __init__(self, cookies_path: str):
        self.cookies_path = cookies_path

    # ------------------------------------------------------------------
    # Args chung cho mọi lần launch persistent context
    # ------------------------------------------------------------------
    @staticmethod
    def _common_launch_args() -> dict:
        return dict(
            headless=False,
            channel="chrome",
            slow_mo=50,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

    @staticmethod
    def _anti_detection_script() -> str:
        return """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
        """

    def export_cookies_interactively(self) -> None:
        """Mở trình duyệt để user đăng nhập Google/Gemini thủ công.

        Lưu session vào profile Chrome cố định (./profiles/google/) VÀ
        đồng thời xuất cookies ra file JSON (dự phòng).
        Sau lần đầu này, load_context_with_cookies() sẽ dùng profile đó
        và KHÔNG cần nhập lại cookie nữa.
        """
        logger.info("🌐 Mở trình duyệt để bạn đăng nhập Google/Gemini...")
        logger.info("👉 Hãy đăng nhập vào Google/Gemini, sau đó nhấn Enter trong terminal này.")
        logger.info(f"📁 Session sẽ được lưu vĩnh viễn tại: {GOOGLE_PROFILE_DIR}")

        Path(GOOGLE_PROFILE_DIR).mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=GOOGLE_PROFILE_DIR,
                **self._common_launch_args(),
            )

            page = context.new_page()
            page.add_init_script(self._anti_detection_script())
            page.goto(self.GEMINI_DOMAIN)

            input("\n✅ Sau khi đã đăng nhập xong và thấy giao diện Gemini, nhấn Enter để lưu...")

            # Lưu cookies vào file JSON (dự phòng)
            cookies = context.cookies()
            save_cookies(cookies, self.cookies_path)
            context.close()

        logger.info("🎉 Export Google cookies thành công! Session đã được lưu vào profile Chrome cố định.")
        logger.info(f"📌 Lần sau khi chạy pipeline sẽ KHÔNG cần đăng nhập lại — profile: {GOOGLE_PROFILE_DIR}")

    def get_active_account_info(self) -> str:
        """Trả về tên file account đang hoạt động nếu sử dụng thư mục tài khoản."""
        accounts_dir = Path("./cookies/google_accounts")
        if not accounts_dir.exists():
            accounts_dir.mkdir(parents=True, exist_ok=True)
            return "google_cookies.json"
        
        json_files = sorted([f for f in accounts_dir.glob("*.json")])
        if not json_files:
            return "google_cookies.json"
            
        index_file = accounts_dir / "current_index.txt"
        index = 0
        if index_file.exists():
            try:
                index = int(index_file.read_text().strip())
            except ValueError:
                pass
        
        if index >= len(json_files):
            index = 0
            
        return json_files[index].name

    def get_profile_dir(self) -> str:
        """Lấy đường dẫn thư mục profile Chrome tương ứng với tài khoản đang hoạt động."""
        active_acc = self.get_active_account_info()
        acc_name = Path(active_acc).stem
        return str(Path(f"./profiles/{acc_name}").resolve())

    def rotate_account(self) -> bool:
        """
        Xoay vòng sang tài khoản Google tiếp theo nếu có thư mục google_accounts.
        Copy nội dung từ file json của tài khoản mới đè vào google_cookies.json.
        Trả về True nếu xoay vòng thành công, False nếu không có tài khoản khác để xoay.
        """
        import shutil
        accounts_dir = Path("./cookies/google_accounts")
        if not accounts_dir.exists():
            logger.warning("⚠️ Không tìm thấy thư mục cookies/google_accounts/ để xoay vòng tài khoản.")
            return False
            
        json_files = sorted([f for f in accounts_dir.glob("*.json")])
        if len(json_files) <= 1:
            logger.warning("⚠️ Thư mục cookies/google_accounts/ cần chứa từ 2 file JSON trở lên để xoay vòng.")
            return False
            
        index_file = accounts_dir / "current_index.txt"
        index = 0
        if index_file.exists():
            try:
                index = int(index_file.read_text().strip())
            except ValueError:
                pass
                
        new_index = (index + 1) % len(json_files)
        index_file.write_text(str(new_index))
        
        next_account_file = json_files[new_index]
        shutil.copy(next_account_file, self.cookies_path)
        logger.info(f"🔄 [COOKIE ROTATION] Đã chuyển sang tài khoản mới: {next_account_file.name}")
        return True

    def load_context_with_cookies(self, playwright: Playwright, headless: bool = False):
        """Tạo browser context với Google session.

        Hỗ trợ xoay vòng tài khoản nếu thư mục google_accounts tồn tại.
        """
        # Đồng bộ file cookie trước khi load nếu dùng google_accounts
        accounts_dir = Path("./cookies/google_accounts")
        if accounts_dir.exists():
            json_files = sorted([f for f in accounts_dir.glob("*.json")])
            if json_files:
                index_file = accounts_dir / "current_index.txt"
                index = 0
                if index_file.exists():
                    try:
                        index = int(index_file.read_text().strip())
                    except ValueError:
                        pass
                if index >= len(json_files):
                    index = 0
                
                import shutil
                shutil.copy(json_files[index], self.cookies_path)
                logger.info(f"👤 Tài khoản Google hiện tại: {json_files[index].name}")

        active_profile_dir = self.get_profile_dir()
        profile_path = Path(active_profile_dir)
        profile_exists = profile_path.exists() and any(profile_path.iterdir())

        if profile_exists:
            logger.info(f"✅ Dùng Chrome profile cố định (session được giữ nguyên): {active_profile_dir}")
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=active_profile_dir,
                headless=headless,
                channel="chrome",
                slow_mo=50,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            context.add_init_script(self._anti_detection_script())
            
            # Luôn nạp cookies mới từ file JSON để đảm bảo session hoạt động tốt
            try:
                cookies = load_cookies(self.cookies_path)
                from src.utils import clean_cookies_for_playwright
                cleaned_cookies = clean_cookies_for_playwright(cookies)
                context.add_cookies(cleaned_cookies)
                logger.info(f"🍪 Đã nạp thêm {len(cleaned_cookies)} Google cookies vào profile từ {self.get_active_account_info()}")
            except Exception as e:
                logger.warning(f"⚠️ Không thể nạp cookies bổ sung vào profile: {e}")
                
            return None, context

        # ── Fallback: inject cookies JSON ──
        active_acc_name = self.get_active_account_info()
        logger.warning(
            f"⚠️ Chưa có Chrome profile cố định cho tài khoản {active_acc_name}. Dùng cookies JSON làm fallback."
        )
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
        context.add_init_script(self._anti_detection_script())

        try:
            cookies = load_cookies(self.cookies_path)
            from src.utils import clean_cookies_for_playwright
            cleaned_cookies = clean_cookies_for_playwright(cookies)
            context.add_cookies(cleaned_cookies)
            logger.info(f"🍪 Đã load {len(cleaned_cookies)} Google cookies vào session từ {active_acc_name}")
        except FileNotFoundError:
            logger.error(
                f"❌ Không tìm thấy file cookies: {self.cookies_path}\n"
                "Hãy chạy: python main.py export-google-cookies"
            )

        return browser, context

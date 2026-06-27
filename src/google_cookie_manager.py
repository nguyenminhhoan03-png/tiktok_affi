import os
import time
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

        Lưu session vào profile Chrome cố định VÀ
        đồng thời xuất cookies ra file JSON.
        """
        active_profile_dir = self.get_profile_dir()
        active_acc = self.get_active_account_info()
        
        logger.info(f"🌐 Mở trình duyệt để bạn đăng nhập Google/Gemini cho tài khoản: {active_acc}...")
        logger.info("👉 Hãy đăng nhập vào Google/Gemini, sau đó nhấn Enter trong terminal này.")
        logger.info(f"📁 Session sẽ được lưu vĩnh viễn tại: {active_profile_dir}")

        Path(active_profile_dir).mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=active_profile_dir,
                **self._common_launch_args(),
            )

            page = context.new_page()
            page.add_init_script(self._anti_detection_script())
            page.goto(self.GEMINI_DOMAIN)

            input("\n✅ Sau khi đã đăng nhập xong và thấy giao diện Gemini, nhấn Enter để lưu...")

            cookies = context.cookies()
            self.save_active_cookies(cookies)
            self.mark_session_ready()
            context.close()

        logger.info(f"🎉 Export Google cookies thành công cho {active_acc}! Session đã được lưu vào profile Chrome cố định.")

    def get_active_account_info(self) -> str:
        """Trả về tên file account đang hoạt động nếu sử dụng thư mục tài khoản."""
        accounts_dir = Path("./cookies/google_accounts")
        if not accounts_dir.exists():
            accounts_dir.mkdir(parents=True, exist_ok=True)
            return "google_cookies.json"
        
        # Nếu cookies_path nằm trong thư mục google_accounts và là một file cụ thể, dùng luôn file đó
        cookies_file_path = Path(self.cookies_path)
        json_files = sorted([f for f in accounts_dir.glob("*.json")])
        
        if cookies_file_path.parent.resolve() == accounts_dir.resolve():
            target_name = cookies_file_path.name
            # Đồng bộ index luôn nếu file nằm trong danh sách
            if json_files and target_name in [f.name for f in json_files]:
                try:
                    idx = [f.name for f in json_files].index(target_name)
                    (accounts_dir / "current_index.txt").write_text(str(idx))
                except Exception:
                    pass
            return target_name

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

    def get_accounts_count(self) -> int:
        """Trả về số lượng tài khoản Google có trong thư mục cookies/google_accounts/."""
        accounts_dir = Path("./cookies/google_accounts")
        if not accounts_dir.exists():
            return 1
        json_files = [f for f in accounts_dir.glob("*.json")]
        return len(json_files) if json_files else 1

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

    def save_active_cookies(self, cookies: list) -> None:
        """Lưu cookies cập nhật vào cả file cookies chính và file account hiện tại."""
        save_cookies(cookies, self.cookies_path)
        accounts_dir = Path("./cookies/google_accounts")
        if accounts_dir.exists():
            active_acc = self.get_active_account_info()
            if active_acc and active_acc != "google_cookies.json":
                active_path = accounts_dir / active_acc
                # Tránh lưu trùng lặp nếu self.cookies_path đã chính là active_path
                if Path(self.cookies_path).resolve() != active_path.resolve():
                    save_cookies(cookies, str(active_path))
                    logger.info(f"💾 Đã tự động cập nhật vào file tài khoản hoạt động: {active_acc}")
                else:
                    logger.info(f"💾 Đã lưu cookies trực tiếp vào tài khoản: {active_acc}")
                
                # Cập nhật injected_at.txt để tránh reset profile ở lần chạy sau do mtime thay đổi
                try:
                    profile_dir = self.get_profile_dir()
                    profile_path = Path(profile_dir)
                    if profile_path.exists():
                        time.sleep(0.1)  # Đợi HĐH cập nhật metadata file
                        json_mtime = active_path.stat().st_mtime
                        (profile_path / "injected_at.txt").write_text(str(json_mtime + 1.0))
                except Exception:
                    pass

    def load_context_with_cookies(self, playwright: Playwright, headless: bool = False):
        """Tạo browser context với Google session.

        Chiến lược mới: Giữ profile Chrome vĩnh viễn như trình duyệt thật.
        - Profile đã có session → dùng trực tiếp, KHÔNG inject cookies, KHÔNG reset.
        - Profile chưa tồn tại → tạo mới và inject cookies từ file JSON lần đầu.
        - Session tự refresh trong profile giống Chrome thật.
        """
        # Xác định tài khoản hiện tại nếu dùng google_accounts
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
        
        # Kiểm tra profile đã có session chưa (có file "session_ready" đánh dấu đã login thành công)
        is_new_profile = not profile_path.exists() or not (profile_path / "session_ready").exists()
        
        if is_new_profile:
            logger.info(f"🆕 Profile mới hoặc chưa có session: {active_profile_dir}")
        else:
            logger.info(f"✅ Dùng Chrome profile có sẵn session (như trình duyệt thật): {active_profile_dir}")
        
        # Đảm bảo thư mục profile tồn tại
        profile_path.mkdir(parents=True, exist_ok=True)
        
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
        
        # Chỉ inject cookies khi profile MỚI (chưa từng login thành công)
        if is_new_profile:
            try:
                cookies = load_cookies(self.cookies_path)
                from src.utils import clean_cookies_for_playwright
                cleaned_cookies = clean_cookies_for_playwright(cookies)
                context.add_cookies(cleaned_cookies)
                logger.info(f"🍪 Đã nạp {len(cleaned_cookies)} Google cookies vào profile mới từ {self.get_active_account_info()}")
            except Exception as e:
                logger.warning(f"⚠️ Không thể nạp cookies vào profile: {e}")
        else:
            logger.info("🔒 Profile đã có session sẵn — không cần inject cookies từ file JSON")
            
        return None, context

    def mark_session_ready(self):
        """Đánh dấu profile hiện tại đã login thành công.
        Gọi hàm này sau khi Gemini xác nhận đã đăng nhập.
        """
        try:
            profile_dir = Path(self.get_profile_dir())
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "session_ready").write_text(str(time.time()))
        except Exception:
            pass


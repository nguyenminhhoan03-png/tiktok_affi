import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.utils import load_cookies, clean_cookies_for_playwright

GOOGLE_COOKIES_PATH = "./cookies/google_cookies.json"

def test_browser(browser_type="chromium", channel=None):
    logger.info(f"Testing browser: {browser_type}, channel: {channel}")
    try:
        with sync_playwright() as p:
            launch_args = {
                "headless": False,
                "slow_mo": 50,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ]
            }
            if channel:
                launch_args["channel"] = channel
                
            if browser_type == "chromium":
                browser = p.chromium.launch(**launch_args)
            elif browser_type == "firefox":
                # Firefox doesn't use channels
                if "channel" in launch_args:
                    del launch_args["channel"]
                browser = p.firefox.launch(**launch_args)
            elif browser_type == "webkit":
                if "channel" in launch_args:
                    del launch_args["channel"]
                browser = p.webkit.launch(**launch_args)
            else:
                logger.error(f"Unknown browser type: {browser_type}")
                return False

            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            
            # Inject anti-detection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            # Load cookies
            if os.path.exists(GOOGLE_COOKIES_PATH):
                cookies = load_cookies(GOOGLE_COOKIES_PATH)
                cleaned_cookies = clean_cookies_for_playwright(cookies)
                context.add_cookies(cleaned_cookies)
                logger.info(f"Loaded {len(cleaned_cookies)} cookies")
            else:
                logger.warning("No cookies found!")

            page = context.new_page()
            logger.info("Navigating to https://gemini.google.com/app ...")
            page.goto("https://gemini.google.com/app", wait_until="load", timeout=30000)
            
            page.wait_for_timeout(5000)
            
            # Check for chat input or Sign in
            url = page.url
            title = page.title()
            logger.info(f"Page URL: {url}")
            logger.info(f"Page Title: {title}")
            
            # Look for sign in element or chat input
            has_chat = page.locator('div[contenteditable="true"], textarea, div[class*="ql-editor"]').count() > 0
            has_signin = page.locator('a:has-text("Sign in"), button:has-text("Sign in"), a:has-text("Đăng nhập")').count() > 0
            
            logger.info(f"Has chat input: {has_chat}")
            logger.info(f"Has Sign in button: {has_signin}")
            
            # Take a screenshot to verify visually
            screenshot_path = f"scratch/test_{browser_type}_{channel or 'default'}.png"
            page.screenshot(path=screenshot_path)
            logger.info(f"Saved screenshot to {screenshot_path}")
            
            context.close()
            browser.close()
            return has_chat and not has_signin
    except Exception as e:
        logger.error(f"Error testing browser: {e}")
        return False

if __name__ == "__main__":
    logger.info("--- Testing default Playwright Chromium ---")
    test_browser("chromium", channel=None)
    
    logger.info("--- Testing Playwright Chrome ---")
    test_browser("chromium", channel="chrome")
    
    logger.info("--- Testing Playwright Firefox ---")
    test_browser("firefox")

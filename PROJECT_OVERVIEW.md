# 📖 PROJECT OVERVIEW — TikTok Auto Uploader & Gemini Pipeline

> File này mô tả **toàn bộ dự án** để bất kỳ ai (hoặc AI) đọc vào là hiểu ngay, không cần hỏi thêm.
> Cập nhật lần cuối: 2026-06-06

---

## 🎯 Mục tiêu dự án

Tự động hóa **toàn bộ pipeline** marketing affiliate trên TikTok:

1. **Tự động tạo video** bằng Google Gemini AI (Veo/Omni) thông qua browser automation
2. **Tự động tải video về** từ Gemini sau khi render xong
3. **Tự động upload lên TikTok Studio** và gán đúng sản phẩm Affiliate tương ứng
4. **Tự động đăng bài** — không cần thao tác tay bất cứ bước nào

---

## 🗂️ Cấu trúc thư mục

```
tiktok/
├── main.py                      # CLI chính — điểm khởi đầu duy nhất
├── config.json                  # Cấu hình toàn cục (tốc độ, caption mặc định, product...)
├── jobs.json                    # Danh sách jobs: prompt → sản phẩm → caption
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker image dùng playwright official image
├── docker-compose.yml           # Docker Compose với volumes và X11 forwarding
├── .env / .env.example          # Biến môi trường (đường dẫn cookies, videos, logs)
├── pyrightconfig.json           # Cấu hình type checker (srcDir = ["src", "."])
│
├── src/                         # Package Python chính
│   ├── __init__.py
│   ├── uploader.py              # Class TikTokUploader — upload lên TikTok Studio
│   ├── gemini_generator.py      # Class GeminiVideoGenerator — tạo video qua Gemini
│   ├── cookie_manager.py        # Class CookieManager — quản lý session TikTok
│   ├── google_cookie_manager.py # Class GoogleCookieManager — quản lý session Google
│   ├── product_scraper.py       # Tự động tải ảnh & lấy tên từ link TikTok Shop
│   └── utils.py                 # Hàm tiện ích chung
│
├── cookies/                     # Lưu session cookies (auto-generated, gitignored)
│   ├── cookies.json             # Session TikTok
│   └── google_cookies.json      # Session Google/Gemini
│
├── videos/                      # Thư mục chứa video
│   └── done/                    # Video đã upload xong tự động chuyển vào đây
│
└── logs/                        # File log (rotation 10MB, giữ 7 ngày)
    └── tiktok_uploader.log
```

---

## ⚙️ Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python 3.14 |
| Browser automation | **Playwright** (`playwright==1.44.0`) |
| CLI framework | **Click** (`click==8.1.7`) |
| Logging | **Loguru** (`loguru==0.7.2`) |
| Env management | **python-dotenv** (`python-dotenv==1.0.0`) |
| Containerization | Docker + Docker Compose |
| Base Docker image | `mcr.microsoft.com/playwright/python:v1.44.0-jammy` |
| Browser dùng | Chromium (via Playwright) |

---

## 🔧 Cấu hình

### `config.json` — Cấu hình chạy

```json
{
  "product_name": "Tên sản phẩm affiliate mặc định",
  "default_caption": "Caption mặc định #tiktok #affiliate",
  "tiktok_studio_url": "https://www.tiktok.com/tiktokstudio/upload",
  "headless": false,
  "delay_between_actions_min": 1.5,
  "delay_between_actions_max": 3.5,
  "type_delay_ms": 80,
  "upload_timeout_ms": 120000
}
```

| Key | Mô tả |
|---|---|
| `headless` | `false` = mở trình duyệt hiển thị (để tránh bot detection), `true` = chạy ngầm |
| `delay_between_actions_min/max` | Khoảng nghỉ ngẫu nhiên giữa các action (giả lập người thật) |
| `type_delay_ms` | Delay giữa mỗi ký tự khi gõ (ms), giả lập tốc độ gõ người thật |
| `upload_timeout_ms` | Timeout chờ video upload xong (mặc định 2 phút) |

### `jobs.json` — Danh sách việc cần làm

```json
[
  {
    "product_url": "Link sản phẩm TikTok Shop để tự động cào ảnh (Tùy chọn)",
    "product_name": "Tên chính xác sản phẩm để gán (Nếu bỏ trống sẽ lấy từ product_url)",
    "prompt": "Mô tả video Gemini sẽ tạo (Nên yêu cầu vẽ dựa trên ảnh đã upload)",
    "caption": "Caption bài đăng #hashtag1 #hashtag2"
  }
]
```

### `.env` — Biến môi trường

```env
TIKTOK_COOKIES_FILE=./cookies/cookies.json
GOOGLE_COOKIES_FILE=./cookies/google_cookies.json
VIDEOS_DIR=./videos
LOGS_DIR=./logs
JOBS_FILE=./jobs.json
CONFIG_PATH=config.json
```

---

## 🚀 CLI Commands — Các lệnh chạy

Tất cả lệnh chạy qua `python main.py <lệnh>`:

| Lệnh | Mô tả | Khi nào dùng |
|---|---|---|
| `export-cookies` | Mở browser, cho user đăng nhập TikTok thủ công, lưu cookies | **Chỉ cần 1 lần** khi setup |
| `export-google-cookies` | Mở browser, cho user đăng nhập Google/Gemini, lưu cookies | **Chỉ cần 1 lần** khi setup |
| `upload <video.mp4>` | Upload 1 file video cụ thể lên TikTok | Khi có sẵn file video |
| `upload-all` | Upload tất cả `.mp4` trong thư mục `./videos/` | Batch upload |
| `run-pipeline` | **Full auto**: Gemini tạo video → tải về → upload TikTok | Chạy hàng ngày |

**Options cho `upload` và `upload-all`:**
- `--caption / -c`: Override caption (nếu không dùng thì lấy từ `config.json`)
- `--product / -p`: Override tên sản phẩm (nếu không dùng thì lấy từ `config.json`)

---

## 🏛️ Kiến trúc & Luồng xử lý

### Full Pipeline (`run-pipeline`)

```
jobs.json (danh sách)
    │
    ▼ Với mỗi job:
┌──────────────────────────────────────────┐
│  BƯỚC 1 & 2: GEMINI GENERATOR            │
│  ┌─────────────────────────────────────┐ │
│  │ GoogleCookieManager.load_context() │ │
│  │    → Load google_cookies.json       │ │
│  │ GeminiVideoGenerator.open_gemini()  │ │
│  │    → Điều hướng tới Gemini App      │ │
│  │    → Kiểm tra login còn hạn không   │ │
│  │ GeminiVideoGenerator.generate_video(prompt) │
│  │    → Chọn chế độ Videos nếu cần    │ │
│  │    → Nhập prompt vào chat input     │ │
│  │    → Bấm Send                       │ │
│  │    → Poll mỗi 5s chờ <video> tag   │ │
│  │    → _download_video_content(src)   │ │
│  │         blob URL → JS fetch → base64 → file │
│  │         direct URL → click download btn  │ │
│  │    → Lưu vào ./videos/gemini_video_{timestamp}.mp4 │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
    │
    ▼ video_path = ./videos/gemini_video_xxx.mp4
┌──────────────────────────────────────────┐
│  BƯỚC 3 & 4: TIKTOK UPLOADER             │
│  ┌─────────────────────────────────────┐ │
│  │ CookieManager.load_context()        │ │
│  │    → Load cookies.json TikTok       │ │
│  │ TikTokUploader.run(video, caption,  │ │
│  │                    product_name)    │ │
│  │    → open_upload_page()             │ │
│  │         → tiktok.com/tiktokstudio/upload │
│  │    → upload_video(path)             │ │
│  │         → set_input_files() trên    │ │
│  │           input[type="file"]        │ │
│  │         → chờ progress bar ẩn đi   │ │
│  │    → fill_caption(text)             │ │
│  │         → type vào contenteditable │ │
│  │    → tag_affiliate_product(name)    │ │
│  │         → click "Commercial content"│ │
│  │         → click "Product link"      │ │
│  │         → search sản phẩm theo tên │ │
│  │         → click "Add"               │ │
│  │    → post_video()                   │ │
│  │         → click "Post/Đăng"         │ │
│  │         → chờ redirect về /manage  │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
    │
    ▼ Thành công → video chuyển vào ./videos/done/
```

---

## 📦 Chi tiết từng Module

### `src/uploader.py` — `TikTokUploader`

**Mục đích:** Upload video lên TikTok Studio và gán sản phẩm Affiliate.

**Anti-bot measures:**
- `human_delay(min, max)` — sleep ngẫu nhiên giữa các action
- `type_delay_ms` — gõ từng ký tự với delay để giả lập người thật
- User-agent giả Chrome thật, disable `AutomationControlled` flag

**Flow của `run()`:**
```
open_upload_page() → upload_video() → fill_caption() → tag_affiliate_product() → post_video()
```

**Selectors quan trọng:**
- Upload input: `input[type="file"]` (first)
- Caption: `div[contenteditable="true"]` hoặc `div[data-e2e="caption-input"]`
- Commercial toggle: `button:has-text("Commercial content")` hoặc `data-e2e="commercial-content-toggle"`
- Product search: `input[data-e2e="product-search-input"]`
- Post button: `button:has-text("Post")` hoặc `button[data-e2e="post-btn"]`
- Thành công khi: URL redirect sang `**/manage**`

---

### `src/gemini_generator.py` — `GeminiVideoGenerator`

**Mục đích:** Điều khiển Google Gemini App để tạo video AI và tải về.

**URL target:** `https://gemini.google.com/app`

**Logic tải video:**
- Nếu `src` là **blob URL** → dùng JS `FileReader` → lấy base64 → decode → ghi file `.mp4`
- Nếu `src` là **direct URL** → tìm nút download, nếu không có → JS `fetch` → base64 → file
- Poll mỗi **5 giây**, timeout mặc định **180 giây** (3 phút)
- File lưu tại: `./videos/gemini_video_{unix_timestamp}.mp4`

---

### `src/cookie_manager.py` — `CookieManager`

**Mục đích:** Quản lý phiên đăng nhập TikTok qua file cookies JSON.

**`export_cookies_interactively()`:**
- Mở Chrome headful tới `tiktok.com`
- Đợi user đăng nhập thủ công
- Lưu toàn bộ cookies sang `cookies/cookies.json`

**`load_context_with_cookies(playwright, headless)`:**
- Launch Chromium với `--disable-blink-features=AutomationControlled`
- Inject cookies từ file vào context → không cần đăng nhập lại

---

### `src/google_cookie_manager.py` — `GoogleCookieManager`

**Tương tự `CookieManager`** nhưng cho Google/Gemini. Domain target: `https://gemini.google.com`. File lưu: `cookies/google_cookies.json`.

---

### `src/utils.py` — Utility Functions

| Hàm | Mô tả |
|---|---|
| `load_config(path)` | Load `config.json` → dict |
| `load_cookies(path)` | Load cookies JSON → list |
| `save_cookies(cookies, path)` | Ghi cookies list ra file JSON |
| `get_video_files(dir)` | Glob `*.mp4` trong thư mục, sort theo tên |
| `setup_logger(logs_dir)` | Cấu hình loguru: rotation 10MB, giữ 7 ngày |

---

## 🐳 Docker

### Build & chạy

```bash
# Build image
docker compose build

# Export cookies TikTok (cần GUI)
xhost +local:docker
docker compose run --rm tiktok-uploader export-cookies

# Chạy full pipeline
docker compose run --rm tiktok-uploader run-pipeline

# Upload thủ công 1 file
docker compose run --rm tiktok-uploader upload /app/videos/my_video.mp4
```

### Volumes được mount:
| Host | Container | Mục đích |
|---|---|---|
| `./videos` | `/app/videos` | Video input/output |
| `./cookies` | `/app/cookies` | Session cookies |
| `./logs` | `/app/logs` | Log files |
| `./config.json` | `/app/config.json` | Config file |
| `/tmp/.X11-unix` | `/tmp/.X11-unix` | X11 GUI forwarding |

### Lưu ý Docker:
- `shm_size: "2gb"` — Chromium cần shared memory lớn để không crash
- `seccomp:unconfined` — Chromium cần sandbox đặc biệt
- `DISPLAY=${DISPLAY}` — Forward màn hình host để xem browser

---

## 🔑 Quy trình Setup Lần Đầu

```bash
# 1. Cài dependencies
pip install -r requirements.txt --break-system-packages

# 2. Cài Playwright Chromium
python3 -m playwright install chromium

# 3. Copy và điền .env
cp .env.example .env

# 4. Export cookies TikTok (làm 1 lần, cookies lưu lại dùng mãi)
python3 main.py export-cookies
# → Trình duyệt mở ra → đăng nhập TikTok → nhấn Enter

# 5. Export cookies Google/Gemini
python3 main.py export-google-cookies
# → Trình duyệt mở ra → đăng nhập Google → nhấn Enter

# 6. Cấu hình jobs.json với danh sách việc muốn làm

# 7. Chạy!
python3 main.py run-pipeline
```

---

## ⚠️ Các Lưu ý Quan Trọng & Gotchas

### Cookies hết hạn
- Cookies TikTok và Google **có thể hết hạn** sau vài tuần/tháng
- Khi pipeline báo lỗi "session hết hạn" → chạy lại `export-cookies` / `export-google-cookies`

### TikTok UI thay đổi
- Selectors dùng nhiều `data-e2e` attributes và text-based locators để bền hơn
- Nhưng TikTok vẫn thỉnh thoảng thay đổi UI → cần cập nhật selectors trong `uploader.py`

### Gemini Blob URL
- Gemini trả về video dưới dạng **blob URL** (`blob:https://...`) 
- Blob URL không thể fetch từ bên ngoài → phải dùng JS trong context trình duyệt để đọc
- Giải pháp: `page.evaluate()` với `FileReader` để convert blob → base64 → file

### Giả lập người thật (Anti-bot)
- Tất cả actions đều có delay ngẫu nhiên: `delay_between_actions_min` đến `max`
- Gõ chữ mỗi ký tự delay `type_delay_ms` ms
- User-agent giả Chrome thật
- Flag `--disable-blink-features=AutomationControlled` để Playwright không bị phát hiện

### `pyrightconfig.json`
```json
{
  "venvPath": ".",
  "venv": ".venv",
  "pythonVersion": "3.14",
  "include": ["src", "."]
}
```
Cần thiết để Pyright resolve được `from src.uploader import ...` trong các file.

---

## 📊 Luồng dữ liệu tóm tắt

```
jobs.json
  ↓ (đọc danh sách)
main.py run-pipeline
  ↓
[Gemini Phase]
  prompt → GeminiVideoGenerator → video file (./videos/*.mp4)
  ↓
[TikTok Phase]  
  video file + caption + product_name → TikTokUploader → bài đăng TikTok
  ↓
  video → ./videos/done/*.mp4 (đánh dấu đã xong)
```

---

## 🔮 Cải tiến có thể làm trong tương lai

- [ ] **Retry logic** — Tự động thử lại nếu 1 job thất bại thay vì bỏ qua
- [ ] **Schedule cron** — Đặt lịch chạy pipeline tự động mỗi ngày
- [ ] **Multi-account** — Hỗ trợ nhiều tài khoản TikTok xoay vòng
- [ ] **Telegram/Discord notification** — Thông báo khi xong hoặc lỗi
- [ ] **Dashboard web** — Giao diện xem trạng thái các jobs
- [ ] **Gemini API** — Dùng Gemini API thay vì browser automation (ổn định hơn)
- [ ] **Video queue** — Hệ thống hàng đợi để xử lý nhiều video song song

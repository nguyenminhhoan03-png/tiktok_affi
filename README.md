# 🚀 TikTok Auto Uploader & Gemini Video Generator

Tool tự động hóa toàn diện:
1. Gửi prompt tạo video lên **Google Gemini App** (Omni/Veo).
2. Tự động chờ render hoàn tất và tải file `.mp4` về.
3. Tự động upload video lên **TikTok Studio** và gán đúng **sản phẩm Affiliate** mong muốn.

---

## 📁 Cấu trúc dự án

```
tiktok/
├── src/
│   ├── __init__.py
│   ├── uploader.py              # Logic upload TikTok Studio + gán affiliate
│   ├── gemini_generator.py      # Logic tự động hóa Gemini tạo/tải video
│   ├── cookie_manager.py        # Quản lý cookies cho TikTok
│   ├── google_cookie_manager.py # Quản lý cookies cho Google/Gemini
│   └── utils.py                 # Tiện ích chung
├── videos/                      # Chứa video tải về từ Gemini (hoặc tự bỏ vào)
│   └── done/                    # Video đã đăng xong tự động di chuyển vào đây
├── cookies/                     # Lưu session cookies (tự động tạo khi export)
├── logs/                        # File log hoạt động
├── config.json                  # Cấu hình cài đặt chung
├── jobs.json                    # Cấu hình danh sách việc (Prompt -> Sản phẩm -> Caption)
├── main.py                      # CLI chạy tool
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## ⚙️ Cài đặt lần đầu

### Cách 1: Chạy trực tiếp trên máy host

> **Yêu cầu:** Máy đã cài Python và có trình duyệt Chrome/Chromium.

```bash
# 1. Cài đặt pip cho Python 3.14 (nếu chưa có pip)
curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py --user --break-system-packages

# 2. Cài đặt dependencies dự án
~/.local/bin/pip install -r requirements.txt --break-system-packages

# 3. Cài đặt trình duyệt Playwright Chromium
python3 -m playwright install chromium
```

### Cách 2: Chạy qua Docker

```bash
docker compose build
```

---

## 🍪 Bước 1: Đăng nhập và lưu Cookies (Chỉ cần làm 1 lần)

Hệ thống cần lưu lại phiên đăng nhập (session) của cả **TikTok** và **Google/Gemini** để chạy tự động không bị dính mã CAPTCHA/Xác minh.

### 1. Lưu Cookies TikTok
```bash
# Chạy trực tiếp
python3 main.py export-cookies

# Chạy bằng Docker
xhost +local:docker
docker compose run --rm tiktok-uploader export-cookies
```
*(Trình duyệt Chromium sẽ mở ra -> Bạn đăng nhập TikTok thủ công -> Quay lại terminal nhấn **Enter**).*

### 2. Lưu Cookies Google/Gemini
```bash
# Chạy trực tiếp
python3 main.py export-google-cookies

# Chạy bằng Docker
docker compose run --rm tiktok-uploader export-google-cookies
```
*(Trình duyệt Chromium sẽ mở ra -> Bạn đăng nhập tài khoản Google của bạn -> Quay lại terminal nhấn **Enter**).*

---

## 📋 Bước 2: Thiết lập danh sách công việc (Prompt & Sản phẩm)

Mở file `jobs.json` lên và điền danh sách các video bạn muốn tạo cùng sản phẩm muốn gắn:

```json
[
  {
    "prompt": "Mô tả video bạn muốn Gemini tạo (ví dụ: A cinematic aesthetic shot of a cute dog wearing a colorful collar, 3d style)",
    "product_name": "Tên chính xác của sản phẩm trong giỏ hàng TikTok để tool tìm kiếm",
    "caption": "Caption hay ho cho video này #thucung #vongco #affiliate"
  },
  {
    "prompt": "Prompt thứ hai...",
    "product_name": "Sản phẩm affiliate thứ hai...",
    "caption": "Caption thứ hai..."
  }
]
```

---

## 🚀 Bước 3: Chạy tự động toàn bộ Pipeline

Chạy lệnh dưới đây, tool sẽ tự động chạy qua từng công việc trong `jobs.json`:
1. Mở Gemini, nhập prompt, chờ render video xong (thường mất 1-3 phút).
2. Tải video `.mp4` đó về máy lưu vào `./videos/`.
3. Mở TikTok Studio, upload video, điền caption.
4. Bật nội dung thương mại, tìm đúng tên sản phẩm affiliate và thêm vào video.
5. Bấm Đăng!

```bash
# Chạy trực tiếp
python3 main.py run-pipeline

# Chạy bằng Docker
docker compose run --rm tiktok-uploader run-pipeline
```

---

## ⚠️ Các tùy chọn khác

### 1. Chỉ upload các file video có sẵn trong thư mục `./videos/`
Nếu bạn đã tự tải video về trước đó, chỉ cần copy chúng vào thư mục `./videos/` rồi chạy:
```bash
python3 main.py upload-all
```

### 2. Cấu hình tốc độ chạy
Trong file `config.json`, bạn có thể tùy chỉnh:
- `headless`: `false` (mặc định mở trình duyệt để theo dõi trực quan và tránh robot quét) hoặc `true` (chạy ngầm).
- `delay_between_actions_min` / `max`: Khoảng thời gian nghỉ ngẫu nhiên giữa các cú click (giả lập giống người thật).
- `type_delay_ms`: Tốc độ gõ phím mô phỏng người dùng gõ thật.

# Hướng dẫn thêm tài khoản Google Gemini mới để xoay vòng tự động

Khi tài khoản Google Gemini hiện tại bị hết giới hạn (Daily Limit Exceeded), hệ thống sẽ tự động chuyển sang tài khoản Google tiếp theo có trong thư mục `cookies/google_accounts/` để tiếp tục render video mà không bị gián đoạn.

Dưới đây là các bước chi tiết để bạn thêm một tài khoản Google Gemini mới (ví dụ: tài khoản thứ 3 - `acc3`):

---

### Bước 1: Tạo file cấu hình tài khoản mới
1. Truy cập thư mục `cookies/google_accounts/`.
2. Tạo một file mới tên là `acc3.json` (hoặc tên bất kỳ kết thúc bằng đuôi `.json`, ví dụ: `acc3.json`).
3. Mở file đó lên và ghi vào nội dung là một cặp ngoặc vuông trống:
   ```json
   []
   ```

---

### Bước 2: Chuyển tài khoản kích hoạt sang tài khoản vừa tạo
Bạn có 2 cách để đổi tài khoản hiện tại:

#### Cách 2.1: Chuyển trực tiếp qua số Index (Chính xác và Nhanh nhất)
Các file JSON được sắp xếp theo thứ tự chữ cái:
* `acc1.json` -> Chỉ số `0`
* `acc2.json` -> Chỉ số `1`
* `acc3.json` -> Chỉ số `2`

Để đổi kích hoạt sang `acc3.json`, chạy lệnh:
```bash
echo "2" > cookies/google_accounts/current_index.txt
```

#### Cách 2.2: Chạy lệnh xoay vòng tài khoản (Tự động chuyển sang tài khoản tiếp theo)
Chạy lệnh python sau để xoay tua:
```bash
python3 -c "from src.google_cookie_manager import GoogleCookieManager; GoogleCookieManager('./cookies/google_cookies.json').rotate_account()"
```

---

### Bước 3: Mở trình duyệt để Login tài khoản mới & lưu session
Chạy lệnh sau để mở trình duyệt Chrome thật:
```bash
python3 main.py export-google-cookies
```
1. Một cửa sổ trình duyệt Chrome sẽ tự động mở lên.
2. Tiến hành đăng nhập tài khoản Google của bạn vào.
3. Truy cập vào trang Gemini (nếu trình duyệt chưa tự chuyển).
4. Khi đã thấy giao diện chính của Gemini (chỗ nhập chat), hãy quay lại terminal của bạn và nhấn nút **`Enter`**.

Hệ thống sẽ tự động lưu session đăng nhập vĩnh viễn vào profile tương ứng (ví dụ: `profiles/acc3`) và lưu cookies. Bạn chỉ cần làm bước này đúng 1 lần duy nhất cho mỗi tài khoản!

---

### Bước 4: Kiểm tra và chạy thử
Bây giờ thư mục của bạn đã có các tài khoản sẵn sàng (`acc1`, `acc2`, `acc3`,...). Hãy chạy pipeline:
```bash
python3 main.py run-pipeline
```
Hệ thống sẽ tự động sử dụng Chrome Profile đã đăng nhập sẵn để render video, khi tài khoản này hết lượt sẽ tự động chuyển sang tài khoản tiếp theo mà không cần bạn phải thao tác lại nữa!

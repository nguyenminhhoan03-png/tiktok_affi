# Dùng image Playwright chính thức (có sẵn Chromium)
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Cài dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài Playwright Chromium browser
RUN playwright install chromium

# Copy source code
COPY . .

# Tạo các thư mục cần thiết
RUN mkdir -p /app/videos /app/cookies /app/logs

# Mount points cho volumes
VOLUME ["/app/videos", "/app/cookies", "/app/logs"]

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

import requests

urls = [
    "https://vt.tiktok.com/ZS96225FSYMaB-BS1MQ/",
    "https://vt.tiktok.com/ZS9622975T2UT-SCEXF/",
    # Let's test both lowercase l and uppercase I
    "https://vt.tiktok.com/ZS9622QXe2xpE-plFGz/",
    "https://vt.tiktok.com/ZS9622QXe2xpE-pIFGz/",
    "https://vt.tiktok.com/ZS9622VVptM1R-vybVF/",
    "https://vt.tiktok.com/ZS9622gRoBULx-fOtoQ/",
    "https://vt.tiktok.com/ZS9622Vw5gjL2-VYVue/",
    "https://vt.tiktok.com/ZS9622t52MBAY-10njQ/",
]

for url in urls:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        print(f"{url} -> status: {resp.status_code}, final_url: {resp.url}")
    except Exception as e:
        print(f"{url} -> error: {e}")

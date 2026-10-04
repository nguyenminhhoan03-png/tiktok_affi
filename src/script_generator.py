import os
import json
import requests
from typing import Dict, Any, Optional
from loguru import logger

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.vilao.ai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-6ef064007dc14c8b8df7a8b3a187f081bbdf829cd8a20a00338e0729e09d1bef")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")

SYSTEM_PROMPT = """Bạn là một Chuyên gia Đạo diễn Kịch bản TikTok Affiliate hàng đầu Việt Nam.
Nhiệm vụ của bạn: Tạo kịch bản video TikTok ngắn hấp dẫn, sáng tạo, thu hút người xem ngay trong 3 giây đầu tiên (Hook) dựa trên thông tin sản phẩm.

YÊU CẦU QUAN TRỌNG:
1. TRÁNH kịch bản bán hàng rập khuôn, nhàm chán. Bắt đầu bằng HOOK gây tò mò, bất ngờ hoặc vấn đề thực tế.
2. Giọng đọc (Voiceover): Tiếng Việt cực kỳ tự nhiên, truyền cảm, cuốn hút (tổng cộng khoảng 30 - 60 từ).
3. Phân cảnh hình ảnh (Visual Prompts): Mô tả hoàn toàn bằng TIẾNG ANH (English) chuyên nghiệp chuẩn điện ảnh và video AI (Google Veo/Omni/Sora).
   - Định dạng: `Cinematic 9:16 vertical TikTok commercial video`.
   - Bắt buộc bao gồm các từ khóa chuyển động camera và môi trường điện ảnh mượt mà: `fluid natural movement`, `handheld camera panning`, `smooth slow-motion tracking shot`, `soft volumetric studio lighting`, `shallow depth of field`, `photorealistic 4k 60fps`, `commercial aesthetic`.
   - Giữ tính nhất quán với ảnh sản phẩm đã tải lên: `"Animate this exact uploaded product with fluid natural motion. Maintain 100% visual fidelity, shape, color, and design of the reference product photo."`
   - KHÔNG đưa lời thoại tiếng Việt hay văn bản vào trong visual prompt tiếng Anh.

Trả về DUY NHẤT một định dạng JSON thuần túy với cấu trúc như sau:
{
  "voiceover": "Lời thoại thuyết minh Tiếng Việt ngắn gọn và hấp dẫn...",
  "visual_prompts": [
    "Cinematic 9:16 vertical TikTok commercial video of...",
    "Cinematic 9:16 vertical TikTok review video..."
  ],
  "caption": "Caption TikTok hấp dẫn kèm hashtag #hashtag1 #hashtag2"
}
"""

def generate_script_with_llm(
    product_name: str,
    product_description: Optional[str] = None,
    num_segments: int = 2
) -> Dict[str, Any]:
    """
    Sử dụng LLM API (Gemini 3.6 Flash / Vilao AI) để tạo kịch bản, visual prompts và caption chất lượng cao.
    """
    api_key = os.getenv("LLM_API_KEY", LLM_API_KEY)
    base_url = os.getenv("LLM_BASE_URL", LLM_BASE_URL).rstrip("/")
    model_name = os.getenv("LLM_MODEL", LLM_MODEL)

    if not api_key:
        logger.warning("⚠️ Không tìm thấy LLM_API_KEY, bỏ qua việc sinh kịch bản qua AI LLM.")
        return {}

    user_content = f"Sản phẩm: {product_name}\n"
    if product_description:
        user_content += f"Mô tả chi tiết sản phẩm: {product_description[:800]}\n"
    user_content += f"Số phân đoạn video cần tạo: {num_segments}\n"

    endpoint = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"} if "gemini" in model_name.lower() or "gpt" in model_name.lower() else None
    }

    # Bỏ response_format nếu API không hỗ trợ
    if payload["response_format"] is None:
        del payload["response_format"]

    try:
        logger.info(f"🧠 Đang gọi LLM API ({model_name}) để sáng tạo kịch bản cho: '{product_name}'...")
        res = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        
        if res.status_code != 200:
            logger.warning(f"⚠️ Gọi LLM API thất bại (Status {res.status_code}): {res.text[:200]}")
            return {}

        res_data = res.json()
        content = res_data["choices"][0]["message"]["content"].strip()

        # Dọn dẹp JSON markdown block nếu có
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)
        logger.info("✨ Đã tạo thành công kịch bản đỉnh cao từ LLM API!")
        logger.info(f"🎙️ Voiceover: {parsed.get('voiceover', '')}")
        logger.info(f"📝 Caption: {parsed.get('caption', '')}")
        return parsed

    except Exception as e:
        logger.warning(f"⚠️ Lỗi khi xử lý response từ LLM API: {e}")
        return {}

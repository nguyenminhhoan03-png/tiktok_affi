"""
Kling AI Video Generator
========================
Tạo video TikTok thời trang từ ảnh sản phẩm qua Kling AI API.
Style: OOTD / outfit-check aesthetic + nhạc trending TikTok Việt Nam.
"""

import base64
import os
import time
from pathlib import Path

import requests
from loguru import logger


KLING_API_BASE = "https://api.klingai.com"
KLING_IMAGE2VIDEO = "/v1/videos/image2video"
KLING_TEXT2VIDEO = "/v1/videos/text2video"
KLING_TASK_QUERY_I2V = "/v1/videos/image2video/{task_id}"
KLING_TASK_QUERY_T2V = "/v1/videos/text2video/{task_id}"

# Default model — đổi sang kling-v2-master hoặc kling-v3-0 nếu tài khoản hỗ trợ
DEFAULT_MODEL = "kling-v1-6"


def _encode_image_base64(image_path: str) -> str:
    """Đọc ảnh và encode sang base64 (không kèm data URI prefix)."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_prompt(product_name: str, product_type: str, segment: str = "intro") -> str:
    """
    Sinh prompt theo xu hướng TikTok Shop VN hiện tại:
    - OOTD / outfit-check aesthetic
    - Nhạc trending TikTok Việt Nam (KHÔNG voiceover, KHÔNG scripted speech)
    - 15 giây (2 segment x 5s hoặc 1 segment x 10s)
    """
    if product_type == "clothing":
        if segment == "intro":
            return (
                f"Cinematic TikTok OOTD fashion reel, 9:16 vertical. "
                f"Beautiful young Vietnamese woman in a bright, minimal aesthetic room. "
                f"She holds '{product_name}' clothing item close to camera — macro close-up of fabric texture, "
                f"stitching detail, label — then steps back revealing the full outfit on her body. "
                f"Smooth confident 360 spin showing waist, silhouette, and drape. "
                f"Camera: smooth handheld, quick aesthetic cuts, warm golden-hour lighting. "
                f"IMPORTANT: Background must have upbeat viral Vietnamese TikTok trending pop music "
                f"clearly audible throughout. Absolutely NO voiceover, NO talking, NO narration — "
                f"pure visuals with trending music only. "
                f"No text overlays, no watermarks. Duration 5 seconds."
            )
        else:  # outro / CTA
            return (
                f"Cinematic TikTok OOTD fashion reel ending, 9:16 vertical. "
                f"Beautiful Vietnamese woman confidently walking toward camera wearing '{product_name}', "
                f"smiling naturally. Quick aesthetic cuts: full-body shot, close-up waist detail, "
                f"side profile pose. She points playfully at the lower-left corner of screen (CTA gesture). "
                f"Bright aesthetic indoor lighting, clean minimal background. "
                f"IMPORTANT: Upbeat viral Vietnamese TikTok trending pop/R&B music clearly audible. "
                f"Absolutely NO voiceover, NO talking. "
                f"No text overlays, no watermarks. Duration 5 seconds."
            )

    elif product_type == "footwear":
        if segment == "intro":
            return (
                f"Cinematic TikTok shoe haul reel, 9:16 vertical. "
                f"Beautiful young Vietnamese woman holds '{product_name}' shoes close to camera. "
                f"Macro close-up of sole, material texture, side profile. "
                f"She places shoes on floor and her feet smoothly slide into them. "
                f"Camera: smooth aesthetic cuts, warm soft lighting. "
                f"IMPORTANT: Upbeat viral Vietnamese TikTok trending music clearly audible throughout. "
                f"NO voiceover, NO talking. "
                f"No text, no watermarks. Duration 5 seconds."
            )
        else:
            return (
                f"Cinematic TikTok shoe styling reel ending, 9:16 vertical. "
                f"Beautiful Vietnamese woman walks gracefully wearing '{product_name}', "
                f"camera captures feet/shoes from ground level then pans up to full outfit. "
                f"Confident stylish pose, bright aesthetic setting. "
                f"IMPORTANT: Upbeat viral Vietnamese TikTok trending music clearly audible. "
                f"NO voiceover, NO talking. "
                f"No text, no watermarks. Duration 5 seconds."
            )

    else:  # general product
        if segment == "intro":
            return (
                f"Cinematic TikTok aesthetic product reveal, 9:16 vertical. "
                f"Beautiful young Vietnamese woman unboxes '{product_name}' in a clean aesthetic setting. "
                f"She holds it close to camera showing design details with a natural delighted expression. "
                f"Quick smooth aesthetic cuts between product detail and reaction shots. "
                f"Warm soft studio lighting. "
                f"IMPORTANT: Upbeat viral Vietnamese TikTok trending music clearly audible. "
                f"NO voiceover, NO talking. "
                f"No text, no watermarks. Duration 5 seconds."
            )
        else:
            return (
                f"Cinematic TikTok product demo ending, 9:16 vertical. "
                f"Beautiful Vietnamese woman demonstrates '{product_name}' with genuine satisfaction, "
                f"smiling and pointing at lower-left corner of screen. "
                f"Clean aesthetic background, warm lighting. "
                f"IMPORTANT: Upbeat viral Vietnamese TikTok trending music clearly audible. "
                f"NO voiceover, NO talking. "
                f"No text, no watermarks. Duration 5 seconds."
            )


class KlingVideoGenerator:
    """Tạo video TikTok thời trang qua Kling AI image2video API."""

    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.config = config
        self.videos_dir = Path(config.get("videos_dir", "./videos"))
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.model = config.get("kling_model", DEFAULT_MODEL)
        self.mode = config.get("kling_mode", "std")  # std hoặc pro
        self.duration = str(config.get("kling_duration", 5))  # "5" hoặc "10"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _determine_product_type(self, product_name: str) -> str:
        name_lower = product_name.lower()
        clothing_kw = [
            "váy", "đầm", "áo", "quần", "set bộ", "vest", "khoác", "hoodie",
            "cardigan", "jean", "sơ mi", "thun", "phông", "len", "nỉ", "yếm",
            "dress", "pants", "shirt", "jacket", "coat", "skirt"
        ]
        footwear_kw = ["giày", "dép", "sandal", "guốc", "sneaker", "boot", "sục"]
        for kw in clothing_kw:
            if kw in name_lower:
                return "clothing"
        for kw in footwear_kw:
            if kw in name_lower:
                return "footwear"
        return "other"

    def _clean_product_name(self, product_name: str) -> str:
        if not product_name:
            return "sản phẩm"
        name_lower = product_name.lower()
        core_keywords = [
            "váy dự tiệc", "váy công sở", "váy dáng dài", "váy xòe", "váy",
            "đầm dự tiệc", "đầm công sở", "đầm dáng dài", "đầm",
            "áo sơ mi", "áo thun", "áo phông", "áo khoác", "áo croptop",
            "áo hoodie", "áo len", "áo nỉ", "áo",
            "quần jeans", "quần jean", "quần tây", "quần short", "quần dài", "quần",
            "set bộ", "set đồ",
            "giày sneaker", "giày cao gót", "giày tây", "giày thể thao", "giày",
            "dép quai ngang", "dép sandal", "dép", "sandal", "guốc",
        ]
        for kw in core_keywords:
            if kw in name_lower:
                idx = name_lower.find(kw)
                words = product_name[idx:].split()
                return " ".join(words[:3]).rstrip(",.-/ ")
        words = product_name.split()
        return " ".join(words[:5]).rstrip(",.-/ ") if len(words) > 5 else product_name

    def _submit_task(self, prompt: str, image_path: str | None) -> tuple[str | None, str]:
        """
        Gửi task tạo video lên Kling API.
        - Có ảnh → dùng image2video endpoint
        - Không có ảnh → dùng text2video endpoint
        Trả về (task_id, endpoint_type) để poll đúng endpoint.
        """
        has_image = image_path and Path(image_path).exists()

        payload: dict = {
            "model_name": self.model,
            "prompt": prompt,
            "duration": self.duration,
            "mode": self.mode,
            "aspect_ratio": "9:16",
            "cfg_scale": 0.5,
        }

        if has_image:
            payload["image"] = _encode_image_base64(image_path)
            endpoint = KLING_IMAGE2VIDEO
            endpoint_type = "i2v"
            logger.info(f"📤 Encode ảnh → dùng image2video: {image_path}")
        else:
            endpoint = KLING_TEXT2VIDEO
            endpoint_type = "t2v"
            logger.info("📝 Không có ảnh → dùng text2video")

        # Retry với backoff cho 429
        max_retries = 4
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{KLING_API_BASE}{endpoint}",
                    json=payload,
                    headers=self.headers,
                    timeout=30,
                )

                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    logger.warning(f"⏳ Rate limit (429), chờ {wait}s rồi thử lại ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue

                if not resp.ok:
                    logger.error(f"❌ Kling API lỗi HTTP {resp.status_code}: {resp.text[:200]}")
                    return None, endpoint_type

                data = resp.json()
                if data.get("code") != 0:
                    logger.error(f"❌ Kling API lỗi: {data.get('message')} (code={data.get('code')})")
                    return None, endpoint_type

                task_id = data["data"]["task_id"]
                logger.info(f"✅ Đã gửi task thành công. Task ID: {task_id}")
                return task_id, endpoint_type

            except requests.RequestException as e:
                logger.error(f"❌ Lỗi kết nối Kling API (lần {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)

        logger.error("❌ Hết số lần thử, bỏ qua task này.")
        return None, endpoint_type

    def _poll_task(self, task_id: str, endpoint_type: str = "i2v", timeout_sec: int = 300) -> str | None:
        """Poll Kling API cho đến khi video xong. Trả về URL video."""
        query_tpl = KLING_TASK_QUERY_I2V if endpoint_type == "i2v" else KLING_TASK_QUERY_T2V
        url = f"{KLING_API_BASE}{query_tpl.format(task_id=task_id)}"
        start = time.time()
        poll_interval = 5

        logger.info(f"⏳ Đang chờ Kling render video (task: {task_id})...")

        while time.time() - start < timeout_sec:
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"❌ Lỗi poll task: {data.get('message')}")
                    return None

                task_data = data["data"]
                status = task_data.get("task_status", "")

                if status == "succeed":
                    videos = task_data.get("task_result", {}).get("videos", [])
                    if videos:
                        video_url = videos[0]["url"]
                        logger.info(f"🎉 Kling render xong! URL: {video_url[:60]}...")
                        return video_url
                    logger.error("❌ Task succeed nhưng không có video URL")
                    return None

                elif status == "failed":
                    logger.error(f"❌ Kling task thất bại: {task_data.get('task_status_msg', '')}")
                    return None

                elapsed = int(time.time() - start)
                logger.info(f"🔄 Đang render... ({elapsed}s) status={status}")
                time.sleep(poll_interval)

            except requests.RequestException as e:
                logger.warning(f"⚠️ Lỗi poll, thử lại: {e}")
                time.sleep(poll_interval)

        logger.error(f"❌ Timeout sau {timeout_sec}s, task chưa xong.")
        return None

    def _download_video(self, video_url: str, filename: str) -> str | None:
        """Tải video từ URL về thư mục videos/."""
        output_path = self.videos_dir / filename
        try:
            logger.info(f"📥 Đang tải video về: {output_path}")
            resp = requests.get(video_url, timeout=60, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"✅ Đã tải video: {output_path} ({output_path.stat().st_size // 1024}KB)")
            return str(output_path)
        except Exception as e:
            logger.error(f"❌ Lỗi tải video: {e}")
            return None

    def generate_video(
        self,
        product_name: str,
        image_path: str | None = None,
        num_segments: int = 3,
    ) -> str | None:
        """
        Sinh video TikTok 15s bằng cách ghép nhiều segment Kling lại.
        Mặc định: 3 segment x 5s = 15s
        """
        from src.utils import concatenate_videos

        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)

        logger.info(f"🎬 Bắt đầu tạo video Kling AI cho: {cleaned_name} (type={prod_type}, {num_segments} segments)")

        segment_paths = []

        for i in range(num_segments):
            # Xác định segment loại nào
            if i == 0:
                seg_type = "intro"
            elif i == num_segments - 1:
                seg_type = "outro"
            else:
                seg_type = "intro"

            prompt = _build_prompt(cleaned_name, prod_type, segment=seg_type)
            logger.info(f"📹 [Segment {i+1}/{num_segments}] ({seg_type}) Đang gửi task...")
            logger.debug(f"   Prompt: {prompt[:120]}...")

            # Segment đầu có ảnh → image2video; các segment sau → text2video
            img = image_path if i == 0 else None

            task_id, ep_type = self._submit_task(prompt, img)
            if not task_id:
                logger.error(f"❌ Không thể gửi task segment {i+1}, bỏ qua.")
                continue

            video_url = self._poll_task(task_id, endpoint_type=ep_type)
            if not video_url:
                logger.error(f"❌ Không lấy được video segment {i+1}")
                continue

            filename = f"kling_seg_{int(time.time())}_{i}.mp4"
            local_path = self._download_video(video_url, filename)
            if local_path:
                segment_paths.append(local_path)
                logger.info(f"✅ Segment {i+1} xong: {local_path}")

            # Đợi nhẹ giữa các request để không bị rate limit
            if i < num_segments - 1:
                time.sleep(3)

        if not segment_paths:
            logger.error("❌ Không có segment nào thành công, hủy bỏ.")
            return None

        if len(segment_paths) == 1:
            logger.info("ℹ️ Chỉ có 1 segment, dùng trực tiếp không ghép.")
            return segment_paths[0]

        # Ghép các segment lại
        final_name = f"kling_final_{int(time.time())}.mp4"
        final_path = str(self.videos_dir / final_name)
        logger.info(f"🔗 Ghép {len(segment_paths)} segment → {final_name}")

        result = concatenate_videos(segment_paths, final_path)
        if result:
            logger.info(f"🎉 Video hoàn chỉnh: {result}")
            # Xóa segment tạm
            for p in segment_paths:
                try:
                    Path(p).unlink()
                except Exception:
                    pass
        return result

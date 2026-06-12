import json
import os
import subprocess
import tempfile
from pathlib import Path
from loguru import logger


def load_config(config_path: str = "config.json") -> dict:
    """Load cấu hình từ file config.json"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cookies(cookies_path: str) -> list:
    """Load cookies từ file JSON"""
    path = Path(cookies_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file cookies: {cookies_path}\n"
            "Hãy chạy lệnh: python main.py export-cookies"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cookies(cookies: list, cookies_path: str) -> None:
    """Lưu cookies vào file JSON"""
    Path(cookies_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Đã lưu cookies vào: {cookies_path}")


def get_video_files(videos_dir: str) -> list[Path]:
    """Lấy danh sách file .mp4 trong thư mục videos"""
    videos_path = Path(videos_dir)
    if not videos_path.exists():
        videos_path.mkdir(parents=True)
        return []
    files = sorted(videos_path.glob("*.mp4"))
    return files


def setup_logger(logs_dir: str = "./logs") -> None:
    """Cấu hình logger"""
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logger.add(
        f"{logs_dir}/tiktok_uploader.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        encoding="utf-8",
    )


def clean_cookies_for_playwright(cookies: list) -> list:
    """
    Chuẩn hóa cookies để Playwright không bị lỗi.
    - sameSite phải là 'Strict', 'Lax', hoặc 'None'. Nếu là null/None hoặc giá trị khác, xóa hẳn field đó.
    - Chuyển expirationDate thành expires.
    - Xóa các trường không cần thiết mà Playwright không hỗ trợ.
    """
    cleaned = []
    for c in cookies:
        cookie = c.copy()
        
        # 1. Chuyển expirationDate sang expires
        if "expirationDate" in cookie and "expires" not in cookie:
            cookie["expires"] = cookie["expirationDate"]
            
        # 2. Chuẩn hóa sameSite
        same_site = cookie.get("sameSite")
        if same_site is not None:
            same_site_str = str(same_site).lower()
            if same_site_str in ["strict", "lax", "none"]:
                cookie["sameSite"] = same_site_str.capitalize()
            elif same_site_str == "no_restriction":
                cookie["sameSite"] = "None"
            else:
                cookie.pop("sameSite", None)
        else:
            cookie.pop("sameSite", None)
            
        # 3. Loại bỏ các field không hợp lệ trong Playwright để tránh warning/error
        valid_keys = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
        keys_to_remove = [k for k in cookie.keys() if k not in valid_keys]
        for k in keys_to_remove:
            cookie.pop(k, None)
            
        cleaned.append(cookie)
    return cleaned


def concatenate_videos(video_paths: list[str], output_path: str) -> str:
    """
    Ghép nhiều file MP4 thành 1 video duy nhất bằng ffmpeg.
    - Thử stream copy (-c copy) trước: nhanh, không mất chất lượng.
    - Nếu thất bại (codec khác nhau), fallback sang re-encode libx264.
    Trả về đường dẫn file output đã ghép.
    """
    if not video_paths:
        raise ValueError("Danh sách clip rỗng, không có gì để ghép.")
    if len(video_paths) == 1:
        logger.info("ℹ️ Chỉ có 1 clip, không cần ghép — trả về trực tiếp.")
        return video_paths[0]

    # Tìm ffmpeg binary: ưu tiên system ffmpeg, fallback về imageio-ffmpeg
    ffmpeg_exe = "ffmpeg"
    system_check = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if system_check.returncode != 0:
        try:
            import imageio_ffmpeg  # type: ignore
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info(f"ℹ️ Dùng ffmpeg từ imageio-ffmpeg: {ffmpeg_exe}")
        except ImportError:
            raise RuntimeError(
                "❌ Không tìm thấy ffmpeg!\n"
                "  Cách 1: sudo apt install ffmpeg\n"
                "  Cách 2: python3 -m pip install imageio-ffmpeg --break-system-packages"
            )

    logger.info(f"🔗 Ghép {len(video_paths)} clip → {output_path}")

    # Tạo file danh sách clip tạm thời (định dạng ffmpeg concat demuxer)
    # Dùng đường dẫn tuyệt đối để ffmpeg không bị lỗi relative path
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for path in video_paths:
            abs_path = str(Path(path).resolve())
            # ffmpeg concat demuxer format: file '/absolute/path.mp4'
            f.write(f"file '{abs_path}'\n")
        concat_file = f.name

    try:
        # --- Lần thử 1: Stream copy (nhanh, không re-encode) ---
        cmd_copy = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ]
        logger.info("⚡ Thử ghép bằng stream copy (không re-encode)...")
        result = subprocess.run(cmd_copy, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"✅ Ghép video thành công (stream copy): {output_path}")
            return output_path

        # --- Lần thử 2: Re-encode libx264 (chậm hơn nhưng chắc chắn hơn) ---
        logger.warning(f"⚠️ Stream copy thất bại, fallback re-encode libx264...\n{result.stderr[-500:]}")
        cmd_encode = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            output_path,
        ]
        result2 = subprocess.run(cmd_encode, capture_output=True, text=True)

        if result2.returncode == 0:
            logger.info(f"✅ Ghép video thành công (re-encode): {output_path}")
            return output_path

        raise RuntimeError(f"ffmpeg ghép thất bại:\n{result2.stderr[-800:]}")

    finally:
        # Xóa file concat tạm
        try:
            Path(concat_file).unlink(missing_ok=True)
        except Exception:
            pass


def add_voiceover_to_video(video_path: str, text: str, output_path: str, voice: str = "vi-VN-HoaiMyNeural") -> str:
    """
    Tạo giọng nói tiếng Việt từ text và chèn vào video.
    - Dùng edge-tts tạo giọng đọc cực kỳ tự nhiên, truyền cảm (HoaiMy hoặc NamMinh).
    - Giữ lại nhạc nền gốc của video (giảm âm lượng) nếu có.
    - Nếu video gốc không có âm thanh, chỉ chèn giọng thuyết minh.
    """
    if not text:
        logger.warning("⚠️ Không có nội dung văn bản để tạo giọng thuyết minh.")
        return video_path

    # Clean text: loại bỏ emoji, hashtag, ký tự lạ
    import re
    cleaned_text = re.sub(r'#[a-zA-Z0-9_]+', '', text)  # xóa hashtag
    # Chỉ giữ chữ, số, dấu câu cơ bản
    cleaned_text = re.sub(r'[^\w\s,.\-!\?]', '', cleaned_text)
    cleaned_text = " ".join(cleaned_text.split())
    if not cleaned_text:
        cleaned_text = "Chào mừng bạn đến với review sản phẩm."

    logger.info(f"🎙️ Tạo giọng đọc thuyết minh (Edge-TTS voice={voice}): '{cleaned_text[:100]}...'")
    
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        voice_mp3 = fp.name

    try:
        # Chạy edge-tts CLI để lấy giọng nói tự nhiên giống người thật
        cmd_tts = [
            "python3", "-m", "edge_tts",
            "--voice", voice,
            "--text", cleaned_text,
            "--write-media", voice_mp3
        ]
        res = subprocess.run(cmd_tts, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi chạy edge-tts CLI: {res.stderr}")
            
    except Exception as e:
        logger.error(f"❌ Không thể tạo giọng thuyết minh qua Edge-TTS: {e}. Fallback về gTTS...")
        # Fallback về gTTS nếu Edge-TTS bị lỗi
        try:
            from gtts import gTTS
            tts = gTTS(text=cleaned_text, lang='vi')
            tts.save(voice_mp3)
        except Exception as gtts_err:
            logger.error(f"❌ Fallback gTTS cũng thất bại: {gtts_err}")
            try:
                Path(voice_mp3).unlink(missing_ok=True)
            except Exception:
                pass
            return video_path

    # Tìm ffmpeg binary
    ffmpeg_exe = "ffmpeg"
    system_check = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if system_check.returncode != 0:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass

    try:
        # Cách 1: Thử mix âm thanh thuyết minh và nhạc nền gốc
        cmd_mix = [
            ffmpeg_exe, "-y",
            "-i", video_path,
            "-i", voice_mp3,
            "-filter_complex", "[0:a]volume=0.25[bg];[1:a]volume=1.8[voice];[bg][voice]amix=inputs=2:duration=first[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]
        logger.info("⚡ Đang chèn thuyết minh (TTS) và trộn với nhạc nền gốc...")
        result = subprocess.run(cmd_mix, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Đã thêm thuyết minh thành công: {output_path}")
            return output_path
            
        # Cách 2: Nếu thất bại (có thể do video gốc không có nhạc), chỉ chèn thuyết minh
        logger.warning("⚠️ Mix âm thanh thất bại (có thể video gốc không có nhạc), thử chèn trực tiếp thuyết minh...")
        cmd_direct = [
            ffmpeg_exe, "-y",
            "-i", video_path,
            "-i", voice_mp3,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]
        result2 = subprocess.run(cmd_direct, capture_output=True, text=True)
        if result2.returncode == 0:
            logger.info(f"✅ Đã chèn trực tiếp thuyết minh thành công: {output_path}")
            return output_path
            
        logger.error(f"❌ Lỗi ffmpeg khi chèn thuyết minh: {result2.stderr}")
        return video_path
        
    finally:
        # Xóa file mp3 tạm
        try:
            Path(voice_mp3).unlink(missing_ok=True)
        except Exception:
            pass


def get_video_duration(video_path: str) -> float:
    """Lấy thời lượng video bằng ffprobe"""
    ffmpeg_exe = "ffmpeg"
    system_check = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if system_check.returncode != 0:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
            
    ffprobe_exe = "ffprobe"
    if ffmpeg_exe != "ffmpeg":
        ffprobe_exe = str(Path(ffmpeg_exe).parent / "ffprobe")
        if not Path(ffprobe_exe).exists():
            ffprobe_exe = "ffprobe"
            
    cmd = [
        ffprobe_exe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            return float(res.stdout.strip())
        except ValueError:
            pass
    return 10.0


def replace_video_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """
    Thay thế hoàn toàn âm thanh của video bằng file audio bên ngoài.
    Tự động loop nếu audio ngắn hơn và trim + fadeout 1.5s cuối để khớp video.
    """
    # Tìm ffmpeg binary
    ffmpeg_exe = "ffmpeg"
    system_check = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if system_check.returncode != 0:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass

    duration = get_video_duration(video_path)
    fade_start = max(0.0, duration - 1.5)
    
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", audio_path,
        "-filter_complex", f"[1:a]atrim=0:{duration},afade=t=out:st={fade_start}:d=1.5[outa]",
        "-map", "0:v",
        "-map", "[outa]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    
    logger.info(f"🎵 Thay thế nhạc nền video: {audio_path} (Trim {duration}s + Fadeout 1.5s)")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"✅ Đã thay nhạc nền thành công: {output_path}")
        return output_path
    else:
        logger.error(f"❌ Lỗi ffmpeg khi thay nhạc nền: {result.stderr}")
        return video_path


def get_bg_music_track(config_music_path: str | None = None) -> str | None:
    """Lấy đường dẫn file nhạc nền từ thư mục music/"""
    if config_music_path and Path(config_music_path).exists():
        return config_music_path
        
    music_dir = Path("./music")
    if not music_dir.exists():
        music_dir.mkdir(parents=True, exist_ok=True)
        return None
        
    music_files = sorted([f for f in music_dir.glob("*.mp3")])
    if music_files:
        return str(music_files[0])
    return None

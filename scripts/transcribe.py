"""
语音转文字 — faster-whisper 本地推理

用法:
  python transcribe.py <视频路径>
  python transcribe.py <视频路径> --output <输出目录> --model medium

首次使用需下载模型（自动缓存到 ~/.cache/huggingface）。
后续用 --offline 跳过网络检查。
"""
import os, sys, subprocess, tempfile, argparse
from pathlib import Path
from faster_whisper import WhisperModel

SCRIPT_ROOT = Path(__file__).resolve().parent.parent


def resolve_model_id(model_size: str) -> str:
    """Use a configured local model path, otherwise let faster-whisper resolve the cache."""
    explicit_path = os.environ.get("WHISPER_MODEL_PATH")
    if explicit_path and Path(explicit_path).exists():
        return str(Path(explicit_path))

    model_dir = os.environ.get("WHISPER_MODEL_DIR")
    candidates = []
    if model_dir:
        base = Path(model_dir)
        candidates.extend([base / model_size, base / f"faster-whisper-{model_size}"])
    candidates.extend([
        SCRIPT_ROOT / "models" / model_size,
        SCRIPT_ROOT / "models" / f"faster-whisper-{model_size}",
    ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return model_size


def transcribe(video_path: str, output_dir: str | None = None, model_size: str = "small",
               offline: bool = True, language: str | None = None) -> str:
    """转录音频为文字，返回纯文本。"""

    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"视频不存在: {video_path}")

    # 输出目录
    out_dir = Path(output_dir) if output_dir else video.parent.parent / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 加载模型
    print(f"[转录] 加载模型 '{model_size}'...")
    model_kwargs = {"device": "cpu", "compute_type": "int8"}
    model_id = resolve_model_id(model_size)
    if Path(model_id).exists():
        model_kwargs["local_files_only"] = True
        print(f"  使用本地模型: {model_id}")
        model = WhisperModel(model_id, **model_kwargs)
    elif offline:
        model_kwargs["local_files_only"] = True
        print("  使用 HuggingFace 本机缓存（离线模式）")
        model = WhisperModel(model_id, **model_kwargs)
    else:
        print("  允许在线下载/更新模型")
        model = WhisperModel(model_id, **model_kwargs)

    print("  OK")

    # 提取音频（ffmpeg → 16kHz mono WAV）
    print("[转录] 提取音频...")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            tmp.name
        ], capture_output=True, check=True)
        print("  OK")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ ffmpeg 错误: {e.stderr.decode()[:200]}")
        os.unlink(tmp.name)
        raise

    # 转录
    print("[转录] 识别中...")
    segments, info = model.transcribe(tmp.name, beam_size=3, language=language)

    lines = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            lines.append(text)
            print(f"  [{seg.start:.0f}s] {text[:100]}")

    full_text = "".join(lines)

    os.unlink(tmp.name)

    name = video.stem[:50]
    txt_path = out_dir / f"{name}.txt"
    txt_path.write_text(full_text, encoding='utf-8')

    print(f"\n[转录] 完成! 时长={info.duration:.0f}s, 文字={len(full_text)}字")
    print(f"  保存: {txt_path}")

    return full_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="语音转文字 — faster-whisper")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("--output", "-o", default=None, help="输出目录")
    parser.add_argument("--model", "-m", default="small", choices=["tiny", "small", "medium"],
                        help="模型大小 (默认: small)")
    parser.add_argument("--offline", action="store_true", default=True,
                        help="仅使用本地缓存模型")
    parser.add_argument("--online", action="store_true", default=False,
                        help="允许在线下载模型")
    parser.add_argument("--language", "-l", default=None, help="语言代码 (默认: 自动检测)。常见: zh/en/ja/ko")
    args = parser.parse_args()

    offline = not args.online  # --online overrides --offline
    text = transcribe(args.video, args.output, args.model, offline, args.language)
    print(f"\n=== 转录结果 ===\n{text}")

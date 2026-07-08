"""
图文帖子提取器 — 处理没有视频的图文内容

支持: X (文字+图片) / 小红书 / B站专栏

用法:
  python extract_post.py <URL>
  python extract_post.py <URL> -o extraction.json

输出 extraction.json 格式:
{
  "title": "...",
  "text": "完整文字内容",
  "images": ["img1.jpg", ...],
  "author": "...",
  "platform": "x",
  "url": "...",
  "date": "...",
  "stats": {"likes": 0, "views": 0}  // optional
}
"""
import subprocess, sys, json, re, os, argparse, shutil
from pathlib import Path
from urllib.request import urlretrieve

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "extracted_posts"
OUTPUT_DIR.mkdir(exist_ok=True)

PLATFORM_PATTERNS = [
    ("x",         ["x.com", "twitter.com", "t.co"]),
    ("xiaohongshu",["xiaohongshu.com", "xhslink.com"]),
    ("bilibili",   ["bilibili.com", "b23.tv"]),
    ("douyin",     ["douyin.com", "v.douyin.com"]),
]

def ytdlp_cmd() -> list[str]:
    """Return a portable yt-dlp command."""
    env_path = os.environ.get("YTDLP_PATH")
    if env_path:
        return [env_path]
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def detect_platform(url: str) -> str:
    url_l = url.lower()
    for p, domains in PLATFORM_PATTERNS:
        for d in domains:
            if d in url_l:
                return p
    return "unknown"


def extract_with_ytdlp(url: str, platform: str) -> dict | None:
    """用 yt-dlp --dump-json 提取元数据"""
    print(f"[{platform.upper()}] 提取中...")

    cmd = [
        *ytdlp_cmd(), url,
        "--dump-json", "--no-playlist",
        "--no-warnings", "--quiet",
    ]

    # X/B站/小红书 需要 Cookie
    if platform in ("x", "bilibili", "xiaohongshu"):
        cmd.extend(["--cookies-from-browser", "chrome"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                cwd=str(SCRIPT_DIR),
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        print("❌ 提取超时")
        return None

    if result.returncode != 0:
        # Fallback: try without cookies for X (public posts)
        if platform == "x" and "--cookies-from-browser" in str(cmd):
            print("  Cookie 失败，尝试无 Cookie...")
            cmd2 = [a for a in cmd if a not in ("--cookies-from-browser", "chrome")]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=60,
                                     cwd=str(SCRIPT_DIR))
            if result2.returncode != 0:
                print(f"❌ 提取失败: {result2.stderr[:200]}")
                return None
            result = result2
        else:
            print(f"❌ 提取失败: {result.stderr[:200]}")
            return None

    try:
        data = json.loads(result.stdout.strip().split("\n")[-1])
    except (json.JSONDecodeError, IndexError):
        print(f"❌ JSON 解析失败")
        return None

    return data


def download_images(image_urls: list[str], post_dir: Path) -> list[str]:
    """下载图片到帖子目录"""
    downloaded = []
    for i, img_url in enumerate(image_urls):
        try:
            ext = ".jpg"
            if ".png" in img_url.lower():
                ext = ".png"
            elif ".webp" in img_url.lower():
                ext = ".webp"
            path = post_dir / f"image_{i+1}{ext}"
            urlretrieve(img_url, str(path))
            downloaded.append(str(path))
            print(f"  📷 图片 {i+1}: {path.name}")
        except Exception as e:
            print(f"  ⚠️ 图片 {i+1} 下载失败: {e}")
    return downloaded


def extract_x(data: dict) -> dict:
    """解析 X/Twitter JSON"""
    title = data.get("title", "") or data.get("description", "")
    # title 通常是 "username on X: tweet text"
    # 去掉 "username on X: " 前缀
    title = re.sub(r'^[^:]+ on X:\s*', '', title)

    text = data.get("description", "") or title
    # 去掉重复的 "username on X: "
    text = re.sub(r'^[^:]+ on X:\s*', '', text) if text.startswith(data.get("uploader", "")) else text

    # 提取图片
    images = []
    if "thumbnails" in data:
        for thumb in data["thumbnails"]:
            url = thumb.get("url", "")
            # 用 original 尺寸
            if "name=orig" in url or url.endswith(("jpg", "png", "webp")):
                images.append(url)
            elif "name=" in url:
                # 替换为 orig 尺寸
                orig = re.sub(r'(name=)[\w]+', r'\1orig', url)
                images.append(orig)
            else:
                images.append(url)

    return {
        "title": title[:120] if title else "Untitled",
        "text": text,
        "images": images,
        "author": data.get("uploader", ""),
        "platform": "x",
        "url": data.get("webpage_url", ""),
        "date": data.get("upload_date", ""),
        "stats": {
            "likes": data.get("like_count", 0),
            "views": data.get("view_count", 0),
        },
    }


def extract_bilibili(data: dict) -> dict:
    """解析 B站 专栏/动态 JSON"""
    return {
        "title": data.get("title", "Untitled")[:120],
        "text": data.get("description", ""),
        "images": [t.get("url", "") for t in data.get("thumbnails", [])],
        "author": data.get("uploader", ""),
        "platform": "bilibili",
        "url": data.get("webpage_url", ""),
        "date": data.get("upload_date", ""),
        "stats": {},
    }


def extract_xiaohongshu(data: dict) -> dict:
    """解析 小红书 笔记 JSON"""
    return {
        "title": data.get("title", "Untitled")[:120],
        "text": data.get("description", ""),
        "images": [t.get("url", "") for t in data.get("thumbnails", [])],
        "author": data.get("uploader", ""),
        "platform": "xiaohongshu",
        "url": data.get("webpage_url", ""),
        "date": data.get("upload_date", ""),
        "stats": {},
    }


EXTRACTORS = {
    "x": extract_x,
    "bilibili": extract_bilibili,
    "xiaohongshu": extract_xiaohongshu,
    "douyin": extract_x,  # 类似 X
}


def main():
    parser = argparse.ArgumentParser(description="图文帖子提取器")
    parser.add_argument("url", help="帖子 URL")
    parser.add_argument("-o", "--output", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    url = args.url.strip()
    platform = detect_platform(url)

    if platform == "unknown":
        print(f"❌ 无法识别平台: {url}")
        sys.exit(1)

    print("=" * 50)
    print(f"📝 图文提取器")
    print(f"   URL: {url[:80]}")
    print(f"   平台: {platform.upper()}")
    print("=" * 50)

    # Step 1: Extract metadata
    data = extract_with_ytdlp(url, platform)
    if not data:
        print("\n💡 提示: 如果 X 提取失败，尝试关闭 Chrome 后重试（Cookie 锁定问题）")
        sys.exit(1)

    # Step 2: Parse
    extractor = EXTRACTORS.get(platform)
    if not extractor:
        print(f"❌ 不支持的平台: {platform}")
        sys.exit(1)

    post = extractor(data)

    # Step 3: Download images
    post_dir = OUTPUT_DIR / f"{platform}_{post['title'][:40]}"
    post_dir.mkdir(exist_ok=True)
    post["images"] = download_images(post["images"], post_dir)
    post["post_dir"] = str(post_dir)

    # Step 4: Save
    output_path = args.output or str(OUTPUT_DIR / f"{platform}_extract.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)

    print(f"\n📝 文字: {len(post['text'])} 字符")
    print(f"📷 图片: {len(post['images'])} 张")
    print(f"💾 保存: {output_path}")
    print("✅ 提取完成!")

    return post


if __name__ == "__main__":
    main()

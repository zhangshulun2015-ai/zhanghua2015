"""
统一视频下载器 — 支持 抖音 / B站 / X(Twitter) / 小红书

用法:
  python download_video.py <URL>
  python download_video.py <URL> --output <自定义文件名>

自动识别平台并选择最优下载方案。
"""
import sys
import re
import json
import os
import urllib.request
import subprocess
import argparse
import shutil
from pathlib import Path
from urllib.parse import urlparse, parse_qs

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "videos"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---- Platform Detection ----

def detect_platform(url: str) -> str:
    """根据URL识别视频平台"""
    url_lower = url.lower()
    patterns = [
        ("douyin",    ["douyin.com", "v.douyin.com", "iesdouyin.com"]),
        ("bilibili",  ["bilibili.com", "b23.tv"]),
        ("xiaohongshu", ["xiaohongshu.com", "xhslink.com"]),
        ("x",         ["x.com", "twitter.com", "t.co"]),
    ]
    for platform, domains in patterns:
        for domain in domains:
            if domain in url_lower:
                return platform
    return "unknown"


# ---- Douyin: Playwright ----

async def download_douyin(url: str, output_name: str | None = None) -> str | None:
    from playwright.async_api import async_playwright

    # Extract video ID from URL
    vid_match = re.search(r'(?:video/|modal_id=)(\d+)', url)
    if not vid_match:
        print("❌ 无法从URL提取抖音视频ID")
        return None
    video_id = vid_match.group(1)
    page_url = f"https://www.douyin.com/video/{video_id}"

    print(f"[抖音] 视频ID: {video_id}")
    print("[1/5] 启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        all_media = []

        async def on_response(response):
            rt = response.request.resource_type
            url_l = response.url.lower()
            if rt == "media" or (".mp4" in url_l and "douyinvod" in url_l):
                size = response.headers.get("content-length", "?")
                all_media.append((response.url, size))

        page.on("response", on_response)

        print("[2/5] 打开抖音页面...")
        await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(10)  # Wait for video to load

        title = await page.title()
        title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60] if title else f"douyin_{video_id}"
        print(f"  标题: {title}")

        # Find vod video
        video_url = None
        for url_m, size in all_media:
            if "douyinvod.com" in url_m.lower():
                try:
                    sz = int(size) if size != "?" else 0
                except ValueError:
                    sz = 0
                if sz > 1000000:
                    video_url = url_m
                    break
                elif sz == 0:
                    # Unknown size but vod domain — likely the video
                    video_url = url_m
                    break

        # Fallback: API
        if not video_url:
            print("  [备用] API 提取...")
            api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
            resp = await page.goto(api_url, wait_until="domcontentloaded", timeout=15000)
            if resp and resp.status == 200:
                text = await resp.text()
                if text.strip():
                    try:
                        data = json.loads(text)
                        aweme = data.get("aweme_detail", {})
                        video_info = aweme.get("video", {})
                        for key in ["play_addr", "download_addr"]:
                            addr = video_info.get(key, {})
                            for u in addr.get("url_list", []):
                                if u:
                                    video_url = u
                                    break
                            if video_url:
                                break
                    except Exception as e:
                        print(f"  JSON解析失败: {e}")

        await browser.close()

        if not video_url:
            print("❌ 无法获取视频URL")
            return None

        # Download
        safe_name = output_name or re.sub(r'[\\/:*?"<>|]+', '_', title)[:60]
        output_path = OUTPUT_DIR / f"[douyin]_{safe_name}.mp4"

        return _download_http(video_url, output_path, referer="https://www.douyin.com/")


def _download_http(video_url: str, output_path: Path, referer: str = "") -> str | None:
    """通用 HTTP 下载"""
    video_url = video_url.replace("\\u0026", "&")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if referer:
        headers["Referer"] = referer

    print(f"[下载] {video_url[:100]}...")
    try:
        req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = min(downloaded / total * 100, 100)
                        print(f"\r  下载: {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({pct:.0f}%)", end="")
            print()
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

    if output_path.exists() and output_path.stat().st_size > 100000:
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"✅ 成功! {output_path.name} ({size_mb:.1f}MB)")
        return str(output_path)
    else:
        print(f"❌ 文件太小: {output_path.stat().st_size} bytes")
        return None


# ---- yt-dlp platforms (B站 / 小红书 / X) ----


def ytdlp_cmd() -> list[str]:
    """Return a portable yt-dlp command."""
    env_path = os.environ.get("YTDLP_PATH")
    if env_path:
        return [env_path]
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def run_ytdlp_command(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(SCRIPT_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

YTDLP_PLATFORM_CONFIG = {
    "bilibili": {
        "name": "B站",
        "extra_args": ["--extractor-args", "bilibili:prefer-flv=0"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "extra_args": [],
    },
    "x": {
        "name": "X",
        "extra_args": [],
    },
}


def download_ytdlp(
    url: str,
    platform: str,
    output_name: str | None = None,
    proxy: str | None = None,
    cookies: str | None = None,
    cookies_from_browser: str | None = "chrome",
) -> str | None:
    """使用 yt-dlp 下载视频"""
    import hashlib

    config = YTDLP_PLATFORM_CONFIG.get(platform, {})
    platform_name = config.get("name", platform)
    extra_args = config.get("extra_args", [])

    print(f"[{platform_name}] 下载中...")

    # Build output template
    if output_name:
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', output_name)[:60]
    else:
        safe_name = "%(title).80s"

    output_template = str(OUTPUT_DIR / f"[{platform}]_{safe_name}.%(ext)s" if output_name
                          else OUTPUT_DIR / f"[{platform}]_%(title).80s.%(ext)s")

    cmd = [
        *ytdlp_cmd(),
        url,
        "-o", output_template,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ] + extra_args

    if cookies:
        cmd.extend(["--cookies", cookies])
    elif cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])

    proxy = proxy or os.environ.get("YTDLP_PROXY")
    if proxy:
        cmd.extend(["--proxy", proxy])

    # Remove empty extra_args
    cmd = [a for a in cmd if a]

    auth_hint = f"cookies={cookies}" if cookies else f"cookies from {cookies_from_browser or 'none'}"
    proxy_hint = f", proxy={proxy}" if proxy else ""
    print(f"  命令: yt-dlp -o '{output_template}' [{auth_hint}{proxy_hint}]")
    try:
        result = run_ytdlp_command(cmd)
    except subprocess.TimeoutExpired:
        print("❌ 下载超时（5分钟）")
        return None

    # Parse output to find downloaded file
    output_text = result.stdout + result.stderr

    cookie_failed = (
        result.returncode != 0
        and not cookies
        and cookies_from_browser
        and platform in ("bilibili", "xiaohongshu", "x")
        and (
            "Could not copy Chrome cookie database" in output_text
            or "Failed to decrypt with DPAPI" in output_text
            or "could not find chrome cookies database" in output_text
        )
    )
    if cookie_failed:
        print("  Cookie 读取失败，尝试无 Cookie 下载公开视频...")
        retry_cmd = []
        skip_next = False
        for item in cmd:
            if skip_next:
                skip_next = False
                continue
            if item == "--cookies-from-browser":
                skip_next = True
                continue
            retry_cmd.append(item)
        try:
            result = run_ytdlp_command(retry_cmd)
            output_text = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            print("❌ 无 Cookie 下载超时（5分钟）")
            return None

    if result.returncode != 0:
        # Check for common errors
        if " consent" in output_text.lower():
            print("⚠️ 平台需要确认 Cookie 同意 — 请先在 Chrome 中访问对应网站")
        if "login" in output_text.lower() or "sign in" in output_text.lower():
            print(f"⚠️ {platform_name} 需要登录 — 请确保 Chrome 已登录{platform_name}")
        if "Private video" in output_text or "private" in output_text.lower():
            print("⚠️ 该视频为私密视频，无法下载")
        if "This video is unavailable" in output_text:
            print("⚠️ 视频不可用（可能已删除或地区限制）")
        print(f"  yt-dlp 输出:\n{output_text[-500:]}")
        return None

    # Find downloaded file
    downloaded_files = []
    for line in output_text.split('\n'):
        # yt-dlp output formats:
        # [download] Destination: path/to/file.mp4
        # [Merger] Merging formats into "path/to/file.mp4"
        # [download] 100% of ...
        if 'Destination:' in line:
            fpath = line.split('Destination:', 1)[1].strip()
            if Path(fpath).exists():
                downloaded_files.append(Path(fpath))
        elif 'Merging formats into' in line:
            fpath = line.split('Merging formats into', 1)[1].strip().strip('"')
            if Path(fpath).exists():
                downloaded_files.append(Path(fpath))

    # Fallback: find newest mp4 in output dir. Avoid glob("[platform]") because
    # square brackets are special glob characters.
    if not downloaded_files:
        prefix = f"[{platform}]_"
        mp4_files = sorted(
            [p for p in OUTPUT_DIR.iterdir() if p.is_file() and p.name.startswith(prefix) and p.suffix.lower() == ".mp4"],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if mp4_files:
            downloaded_files = [mp4_files[0]]

    if downloaded_files:
        f = downloaded_files[0]
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"✅ 成功! {f.name} ({size_mb:.1f}MB)")
        return str(f)

    print("❌ 下载失败：未找到输出文件")
    print(f"  yt-dlp 输出:\n{output_text[-500:]}")
    return None


# ---- Main entry ----

def main():
    parser = argparse.ArgumentParser(description="统一视频下载器 — 抖音/B站/小红书/X")
    parser.add_argument("url", help="视频URL")
    parser.add_argument("--output", "-o", default=None, help="自定义输出文件名（不含扩展名）")
    parser.add_argument("--proxy", default=None, help="yt-dlp 代理，例如 http://127.0.0.1:7890")
    parser.add_argument("--cookies", default=None, help="Netscape cookies.txt 文件路径，适合 X 等必须登录的平台")
    parser.add_argument(
        "--cookies-from-browser",
        default="chrome",
        help="从浏览器读取 Cookie，默认 chrome；如 DPAPI 解密失败，请改用 --cookies cookies.txt",
    )
    args = parser.parse_args()

    url = args.url.strip()
    platform = detect_platform(url)

    print(f"=" * 50)
    print(f"🎬 视频下载器")
    print(f"   URL: {url[:80]}")
    print(f"   平台: {platform.upper()}")
    print(f"=" * 50)

    if platform == "douyin":
        import asyncio
        result = asyncio.run(download_douyin(url, args.output))
    elif platform in ("bilibili", "xiaohongshu", "x"):
        result = download_ytdlp(
            url,
            platform,
            args.output,
            proxy=args.proxy,
            cookies=args.cookies,
            cookies_from_browser=args.cookies_from_browser,
        )
    else:
        print(f"❌ 无法识别平台: {url}")
        print("   支持的平台: 抖音(douyin.com), B站(bilibili.com), 小红书(xiaohongshu.com), X(x.com)")
        sys.exit(1)

    if result:
        print(f"\n✅ 下载完成: {result}")
    else:
        print(f"\n❌ 下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

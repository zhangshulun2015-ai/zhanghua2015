"""
追加内容本地 HTTP 服务器 — 接收 Dashboard 发来的追加请求，自动保存图片和写入笔记

启动: python append_server.py --vault "<你的知识库路径>"
端口: 18999

接口:
  POST /append  — 追加内容（含图片 base64）
  GET  /ping    — 健康检查
"""
import os, sys, re, json, base64, argparse, subprocess, shutil
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from vault_config import resolve_vault_path, save_vault_path

DOMAIN_DIR = "图文视频知识库"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
VAULT = None
IMAGE_DIR = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def build_append_block(data: dict, today: str) -> str:
    """构建追加内容区块。"""
    parts = []
    parts.append(f"\n---\n\n## 📝 追加内容（{today}）\n")
    parts.append(f"> 以下内容于 {today} 追加，不修改原始笔记。\n")

    content = data.get("content", "").strip()
    if content:
        parts.append(f"### 💬 补充文字\n\n{content}\n")

    kps = data.get("knowledge_points", [])
    if kps:
        parts.append("### 🧠 新增知识点\n")
        for i, kp in enumerate(kps):
            idx = CIRCLED[i] if i < len(CIRCLED) else str(i + 1)
            kp_title = kp.get("title", f"知识点{i+1}")
            concept = kp.get("concept", "")
            points = kp.get("points", [])
            parts.append(f"#### 知识点{idx}：{kp_title}\n\n")
            parts.append(f"**概念**：{concept}\n\n")
            if points:
                parts.append("**要点**：\n")
                for p in points:
                    parts.append(f"- {p}\n")
                parts.append("\n")
            else:
                parts.append("**要点**：\n- （待补充）\n\n")

    images = data.get("images", [])
    saved_images = data.get("_saved_images", [])
    if images:
        parts.append("### 🖼️ 新增图片\n\n")
        for i, img in enumerate(images):
            # 优先使用已保存的本地路径
            if i < len(saved_images) and saved_images[i]:
                rel_path = f"../../raw/图片文件/{saved_images[i]}"
                desc = img.get("desc", img.get("name", ""))
                parts.append(f"![{desc}]({rel_path})\n\n")
            else:
                url = img.get("url", "")
                desc = img.get("desc", "")
                if url:
                    parts.append(f"![{desc}]({url})\n\n")

    links = data.get("links", [])
    if links:
        parts.append("### 🔗 新增链接\n")
        for link in links:
            ltitle = link.get("title", link.get("url", ""))
            lurl = link.get("url", "")
            if lurl:
                parts.append(f"- [{ltitle}]({lurl})\n")
        parts.append("\n")

    quotes = data.get("quotes", [])
    if quotes:
        parts.append("### 💡 新增金句\n")
        for q in quotes:
            parts.append(f"> {q}\n\n")

    return ''.join(parts)


def save_images(images: list, note_id: str) -> list:
    """保存 base64 图片到 raw/图片文件/ 目录，返回保存的文件名列表。"""
    saved = []
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images):
        b64 = img.get("base64", "")
        name = img.get("name", f"image_{i+1}.png")
        if not b64:
            saved.append("")
            continue
        # 去掉 data:image/...;base64, 前缀
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        ext = name.rsplit(".", 1)[-1] if "." in name else "png"
        saved_name = f"append_{note_id}_{i + 1}.{ext}"
        filepath = IMAGE_DIR / saved_name
        try:
            filepath.write_bytes(base64.b64decode(b64))
            saved.append(saved_name)
            print(f"  💾 图片已保存: {saved_name}")
        except Exception as e:
            print(f"  ❌ 图片保存失败: {e}")
            saved.append("")
    return saved


def append_to_note(note_path: str, append_block: str):
    """将追加区块插入到笔记末尾（footer 行之前）。"""
    p = Path(note_path)
    content = p.read_text(encoding='utf-8')

    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(r'(updated:\s*)["\']?\d{4}-\d{2}-\d{2}["\']?', f'\\1"{today}"', content)

    # 查找 footer 行（*由 [video-knowledge] ...），插入到它前面
    footer_pattern = r'(\n---\n\n\*由 \[video-knowledge\])'
    if re.search(footer_pattern, content):
        content = re.sub(footer_pattern, '\n' + append_block.strip() + r'\1', content)
    else:
        # 尝试更宽松的匹配
        footer_pattern2 = r'(\*由 \[video-knowledge\])'
        if re.search(footer_pattern2, content):
            content = re.sub(footer_pattern2, '\n' + append_block.strip() + '\n\n' + r'\1', content)
        else:
            content = content.rstrip() + '\n' + append_block

    p.write_text(content, encoding='utf-8')
    print(f"  ✅ 内容已写入: {p.name}")


def delete_append_block(note_path: str, block_date: str, block_index=None):
    """删除指定追加内容区块。优先按页面传来的 index 删除，兼容旧的按日期删除。"""
    p = Path(note_path)
    content = p.read_text(encoding='utf-8')

    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(r'(updated:\s*)["\']?\d{4}-\d{2}-\d{2}["\']?', f'\\1"{today}"', content)

    pattern = r'\n---\n\n## 📝 追加内容（(?P<date>\d{4}-\d{2}-\d{2})）\n>.*?(?=\n---\n\n##\s*📝\s*追加内容（|\n---\n\n\*由|\n\n\*由|\Z)'
    matches = list(re.finditer(pattern, content, flags=re.DOTALL))

    target = None
    if block_index is not None:
        try:
            idx = int(block_index)
            if 0 <= idx < len(matches):
                candidate = matches[idx]
                if not block_date or candidate.group("date") == block_date:
                    target = candidate
        except (TypeError, ValueError):
            target = None

    if target is None:
        target = next((m for m in matches if m.group("date") == block_date), None)

    if target is None:
        print(f"  WARN: append block not found for date {block_date}")
        return False

    new_content = content[:target.start()] + content[target.end():]
    p.write_text(new_content, encoding='utf-8')
    print(f"  DELETE: removed append block dated {target.group('date')}")
    return True


def regenerate_dashboard():
    """调用 regenerate_dashboard.py 刷新首页。"""
    script = Path(__file__).parent / "regenerate_dashboard.py"
    python = Path(sys.executable)
    if script.exists():
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [str(python), str(script), "--vault", str(VAULT)],
            capture_output=True, text=True, encoding='utf-8', env=env
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)


def safe_vault_path(path_text: str) -> Path:
    """Resolve a dashboard path inside the current vault."""
    raw = Path(path_text)
    candidate = raw if raw.is_absolute() else VAULT / path_text
    resolved = candidate.resolve()
    vault_resolved = VAULT.resolve()
    if not str(resolved).lower().startswith(str(vault_resolved).lower()):
        raise ValueError("Path is outside vault")
    return resolved


def get_storage_status() -> dict:
    """Return disk and local video usage for reminders."""
    usage = shutil.disk_usage(VAULT)
    video_dir = VAULT / DOMAIN_DIR / "raw" / "视频文件"
    videos = []
    total_bytes = 0
    if video_dir.exists():
        for item in video_dir.rglob("*"):
            if item.is_file() and item.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                size = item.stat().st_size
                total_bytes += size
                videos.append({
                    "path": str(item),
                    "name": item.name,
                    "size": size,
                })
    videos.sort(key=lambda x: x["size"], reverse=True)
    return {
        "free": usage.free,
        "total": usage.total,
        "used": usage.used,
        "videoTotal": total_bytes,
        "videoCount": len(videos),
        "largestVideos": videos[:10],
    }


def delete_local_video(video_path: str) -> tuple[bool, str]:
    """Delete a local source video while keeping notes and thumbnails."""
    video = safe_vault_path(video_path)
    if video.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        raise ValueError("Only local video files can be deleted")
    if not video.exists():
        regenerate_dashboard()
        return True, "视频文件已不存在，已刷新页面数据"
    size = video.stat().st_size
    video.unlink()
    regenerate_dashboard()
    return True, f"已删除本地视频：{video.name}（释放 {size / 1024 / 1024:.1f} MB）"


def trash_note(note_path: str) -> tuple[bool, str]:
    """Move a note Markdown file to the vault trash."""
    note = safe_vault_path(note_path)
    wiki_dir = (VAULT / DOMAIN_DIR / "wiki").resolve()
    if not str(note.resolve()).lower().startswith(str(wiki_dir).lower()):
        raise ValueError("Only notes inside wiki/ can be deleted")
    if note.suffix.lower() != ".md":
        raise ValueError("Only Markdown notes can be deleted")
    if note.name in {"index.md", "log.md", "WIKI-SCHEMA.md"}:
        raise ValueError("System notes cannot be deleted from the dashboard")
    if not note.exists():
        regenerate_dashboard()
        return True, "笔记文件已不存在，已刷新页面数据"

    rel_parent = note.parent.relative_to(wiki_dir)
    trash_dir = VAULT / DOMAIN_DIR / ".trash" / "notes" / rel_parent
    trash_dir.mkdir(parents=True, exist_ok=True)
    target = trash_dir / note.name
    if target.exists():
        stem = note.stem
        suffix = note.suffix
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = trash_dir / f"{stem}_{stamp}{suffix}"

    note.replace(target)
    regenerate_dashboard()
    return True, f"已移动到回收站：{target}"


def list_trashed_notes() -> list[dict]:
    """List soft-deleted notes."""
    trash_root = VAULT / DOMAIN_DIR / ".trash" / "notes"
    if not trash_root.exists():
        return []
    items = []
    for note in sorted(trash_root.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        rel = note.relative_to(trash_root)
        category = rel.parts[0] if len(rel.parts) > 1 else "其他"
        title = note.stem
        try:
            text = note.read_text(encoding="utf-8")
            title_match = re.search(r'#\s*(?:🎬\s*)?(.+?)(?:\n|$)', text)
            if title_match:
                title = title_match.group(1).strip()
        except Exception:
            pass
        stat = note.stat()
        items.append({
            "title": title,
            "category": category,
            "path": str(note),
            "relativePath": str(rel),
            "size": stat.st_size,
            "deletedAt": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return items


def restore_note(trash_path: str) -> tuple[bool, str]:
    """Restore a note from vault trash back to wiki/."""
    note = safe_vault_path(trash_path)
    trash_root = (VAULT / DOMAIN_DIR / ".trash" / "notes").resolve()
    if not str(note.resolve()).lower().startswith(str(trash_root).lower()):
        raise ValueError("Only notes inside .trash/notes/ can be restored")
    if note.suffix.lower() != ".md":
        raise ValueError("Only Markdown notes can be restored")
    if not note.exists():
        regenerate_dashboard()
        return True, "回收站文件已不存在，已刷新页面数据"

    rel = note.relative_to(trash_root)
    restore_target = VAULT / DOMAIN_DIR / "wiki" / rel
    restore_target.parent.mkdir(parents=True, exist_ok=True)
    if restore_target.exists():
        stem = restore_target.stem
        suffix = restore_target.suffix
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        restore_target = restore_target.parent / f"{stem}_{stamp}{suffix}"

    note.replace(restore_target)
    regenerate_dashboard()
    return True, f"已恢复笔记：{restore_target.name}"


class AppendHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  🌐 {args[0]}")

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/ping":
            self.send_response(200)
            self._set_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "vault": str(VAULT)}).encode())
        elif parsed.path == "/storage":
            self.send_response(200)
            self._set_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(get_storage_status(), ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/trash":
            self.send_response(200)
            self._set_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"notes": list_trashed_notes()}, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self._set_cors()
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/delete-append":
            self._handle_delete_append()
            return
        if parsed.path == "/delete-video":
            self._handle_delete_video()
            return
        if parsed.path == "/delete-note":
            self._handle_delete_note()
            return
        if parsed.path == "/restore-note":
            self._handle_restore_note()
            return
        if parsed.path != "/append":
            self.send_response(404)
            self._set_cors()
            self.end_headers()
            return

        # 读取请求体（先读字节再尝试解码）
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body = raw_body.decode("gbk")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        note_path = data.get("filePath", "")
        note_title = data.get("title", "")

        if not note_path:
            self.send_response(400)
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing filePath"}).encode())
            return

        print(f"\n{'='*50}")
        print(f"✏️ 收到追加请求: {note_title}")
        print(f"   路径: {note_path}")
        print(f"{'='*50}")

        today = datetime.now().strftime("%Y-%m-%d")

        # 1. 保存图片
        images = data.get("images", [])
        note_id = data.get("noteId", re.sub(r'[^a-zA-Z0-9]', '', Path(note_path).stem)[:20])
        saved_images = save_images(images, note_id)
        data["_saved_images"] = saved_images

        # 2. 构建追加区块
        append_block = build_append_block(data, today)

        # 3. 写入笔记
        try:
            append_to_note(note_path, append_block)
        except Exception as e:
            self.send_response(500)
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # 4. 刷新 Dashboard
        print(f"\n  🔄 刷新 Dashboard...")
        regenerate_dashboard()

        print(f"\n✅ 追加完成!\n")

        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "title": note_title,
            "images_saved": len([s for s in saved_images if s]),
            "message": f"已追加到《{note_title}》"
        }).encode())

    def _handle_delete_append(self):
        """处理删除追加内容请求。"""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body = raw_body.decode("gbk")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        note_path = data.get("filePath", "")
        block_date = data.get("date", "")
        block_index = data.get("index", None)
        if not note_path or not block_date:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing filePath or date"}).encode())
            return

        print(f"\n{'='*50}")
        print("DELETE append block request")
        print(f"   路径: {note_path}")
        print(f"   日期: {block_date}")
        print(f"   序号: {block_index}")
        print(f"{'='*50}")

        try:
            ok = delete_append_block(note_path, block_date, block_index)
        except Exception as e:
            self.send_response(500); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        if ok:
            regenerate_dashboard()
            print("DELETE complete\n")

        self.send_response(200); self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": ok,
            "message": f"已删除 {block_date} 的追加内容" if ok else "未找到对应追加内容"
        }).encode())

    def _handle_delete_video(self):
        """处理删除本地视频请求。"""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body = raw_body.decode("gbk")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Invalid JSON"}).encode())
            return

        video_path = data.get("video", "")
        if not video_path:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Missing video path"}).encode())
            return

        print("\nDELETE local video request")
        print(f"   视频: {video_path}")

        try:
            ok, message = delete_local_video(video_path)
        except Exception as e:
            self.send_response(500); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(200); self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"success": ok, "message": message}, ensure_ascii=False).encode("utf-8"))

    def _handle_restore_note(self):
        """处理回收站恢复请求。"""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body = raw_body.decode("gbk")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Invalid JSON"}).encode())
            return

        trash_path = data.get("path", "")
        if not trash_path:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Missing trash path"}).encode())
            return

        print("\nRESTORE note request")
        print(f"   笔记: {trash_path}")

        try:
            ok, message = restore_note(trash_path)
        except Exception as e:
            self.send_response(500); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(200); self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"success": ok, "message": message}, ensure_ascii=False).encode("utf-8"))

    def _handle_delete_note(self):
        """处理整篇笔记软删除请求。"""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body = raw_body.decode("gbk")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Invalid JSON"}).encode())
            return

        note_path = data.get("filePath", "")
        if not note_path:
            self.send_response(400); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Missing filePath"}).encode())
            return

        print("\nTRASH note request")
        print(f"   笔记: {note_path}")

        try:
            ok, message = trash_note(note_path)
        except Exception as e:
            self.send_response(500); self._set_cors(); self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(200); self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"success": ok, "message": message}, ensure_ascii=False).encode("utf-8"))


def main():
    global VAULT, IMAGE_DIR

    parser = argparse.ArgumentParser(description="追加内容本地服务器")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库根路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    parser.add_argument("--port", type=int, default=18999, help="监听端口")
    args = parser.parse_args()

    VAULT = resolve_vault_path(args.vault)
    save_vault_path(VAULT)
    IMAGE_DIR = VAULT / DOMAIN_DIR / "raw" / "图片文件"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    server = HTTPServer(("127.0.0.1", args.port), AppendHandler)
    print(f"🚀 追加内容服务器已启动: http://127.0.0.1:{args.port}")
    print(f"   Vault: {VAULT}")
    print(f"   图片目录: {IMAGE_DIR}")
    print(f"   按 Ctrl+C 停止\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()

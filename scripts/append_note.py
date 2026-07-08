"""
给已有笔记追加内容 — 在笔记底部插入新的补充区块

支持追加：补充文字、知识点、链接、图片、金句。
追加区块带有日期标记，不修改原始内容。

Usage:
  python append_note.py --vault "<你的知识库路径>" \\
    --file "<你的知识库路径>\\图文视频知识库\\wiki\\AI教程资料\\笔记标题.md" \\
    --content "新补充的文字内容" \\
    --kp '[{"title":"新知识点","concept":"概念","points":["要点1"]}]' \\
    --links '[{"title":"网站名","url":"https://..."}]' \\
    --quotes '["新金句"]'
"""
import os, sys, re, json, argparse, subprocess
from pathlib import Path
from datetime import datetime
from vault_config import resolve_vault_path, save_vault_path

DOMAIN_DIR = "图文视频知识库"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"


def find_note_by_title(vault: Path, title: str) -> Path | None:
    """按标题模糊匹配查找笔记文件。"""
    wiki_dir = vault / DOMAIN_DIR / "wiki"
    if not wiki_dir.exists():
        return None
    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
    for md in wiki_dir.rglob("*.md"):
        if md.name in ('index.md', 'log.md'):
            continue
        if md.stem == safe_title or md.stem == title:
            return md
    for md in wiki_dir.rglob("*.md"):
        if md.name in ('index.md', 'log.md'):
            continue
        if title in md.stem or md.stem in title:
            return md
    return None


def build_append_block(data: dict) -> str:
    """构建追加内容区块。"""
    today = datetime.now().strftime("%Y-%m-%d")
    parts = []

    parts.append(f"\n---\n\n## 📝 追加内容（{today}）\n")
    parts.append(f"> 以下内容于 {today} 追加，不修改原始笔记。\n")

    # 补充文字
    content = data.get("content", "").strip()
    if content:
        parts.append(f"### 💬 补充文字\n\n{content}\n")

    # 知识点
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

    # 图片
    images = data.get("images", [])
    if images:
        parts.append("### 🖼️ 新增图片\n")
        for img in images:
            url = img.get("url", "")
            desc = img.get("desc", "")
            if url:
                parts.append(f"![{desc}]({url})\n")
                if desc:
                    parts.append(f"*{desc}*\n")
                parts.append("\n")

    # 链接
    links = data.get("links", [])
    if links:
        parts.append("### 🔗 新增链接\n")
        for link in links:
            ltitle = link.get("title", link.get("url", ""))
            lurl = link.get("url", "")
            if lurl:
                parts.append(f"- [{ltitle}]({lurl})\n")
        parts.append("\n")

    # 金句
    quotes = data.get("quotes", [])
    if quotes:
        parts.append("### 💡 新增金句\n")
        for q in quotes:
            parts.append(f"> {q}\n\n")

    return ''.join(parts)


def append_to_note(note_path: Path, append_block: str):
    """将追加区块插入到笔记末尾（footer 行之前）。"""
    content = note_path.read_text(encoding='utf-8')

    # 更新 frontmatter 中的 updated 日期
    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(r'(updated:\s*)["\']?\d{4}-\d{2}-\d{2}["\']?', f'\\1"{today}"', content)

    # 找到 footer 行 "*由 [video-knowledge]"
    footer_pattern = r'(\n---\n\n\*由 \[video-knowledge\])'
    if re.search(footer_pattern, content):
        # 在 footer 之前插入追加区块
        content = re.sub(footer_pattern, append_block + r'\1', content)
    else:
        # 没有找到 footer，直接追加到末尾
        content = content.rstrip() + '\n' + append_block

    note_path.write_text(content, encoding='utf-8')


def append_log_append(vault: Path, note_title: str):
    """追加操作日志。"""
    log_path = vault / DOMAIN_DIR / "wiki" / "log.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"""
## [{today}] append | {note_title}

- 操作：追加内容
- 笔记：`{note_title}.md`
"""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f"  ✅ log.md 已记录追加")


def regenerate_dashboard(vault: Path):
    """调用 regenerate_dashboard.py 刷新首页。"""
    script = Path(__file__).parent / "regenerate_dashboard.py"
    python = Path(sys.executable)
    if script.exists():
        result = subprocess.run(
            [str(python), str(script), "--vault", str(vault)],
            capture_output=True, text=True, encoding='utf-8'
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)


def main():
    parser = argparse.ArgumentParser(description="给已有笔记追加内容")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库根路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    parser.add_argument("--file", help="笔记文件完整路径")
    parser.add_argument("--title", help="笔记标题（模糊匹配）")
    parser.add_argument("--content", default="", help="补充文字")
    parser.add_argument("--kp", default="", help="知识点 JSON: [{title,concept,points:[]}]")
    parser.add_argument("--links", default="", help="链接 JSON: [{title,url}]")
    parser.add_argument("--images", default="", help="图片 JSON: [{url,desc}]")
    parser.add_argument("--quotes", default="", help="金句 JSON: [\"quote1\"]")
    parser.add_argument("--input", help="JSON 数据文件路径（可选，优先使用）")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)

    # 确定目标笔记
    if args.file:
        note_path = Path(args.file)
        if not note_path.exists():
            print(f"❌ 文件不存在: {note_path}")
            sys.exit(1)
    elif args.title:
        note_path = find_note_by_title(vault, args.title)
        if not note_path:
            print(f"❌ 找不到标题包含 '{args.title}' 的笔记")
            sys.exit(1)
    else:
        print("❌ 请提供 --file 或 --title 参数")
        sys.exit(1)

    # 加载数据
    if args.input:
        data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    else:
        data = {}
        if args.content:
            data["content"] = args.content
        if args.kp:
            data["knowledge_points"] = json.loads(args.kp)
        if args.links:
            data["links"] = json.loads(args.links)
        if args.images:
            data["images"] = json.loads(args.images)
        if args.quotes:
            data["quotes"] = json.loads(args.quotes)

    if not any(data.get(k) for k in ["content", "knowledge_points", "links", "images", "quotes"]):
        print("❌ 没有提供任何追加内容")
        sys.exit(1)

    note_title = note_path.stem

    print(f"\n{'='*50}")
    print(f"✏️ 追加内容到: {note_title}")
    print(f"   路径: {note_path}")
    print(f"{'='*50}\n")

    # 构建追加区块
    append_block = build_append_block(data)

    # 插入到笔记中
    append_to_note(note_path, append_block)
    print(f"  ✅ 内容已追加到笔记")

    # 追加日志
    append_log_append(vault, note_title)

    # 刷新 Dashboard
    print(f"\n  🔄 刷新 Dashboard...")
    regenerate_dashboard(vault)

    print(f"\n{'='*50}")
    print(f"✅ 追加完成!")
    print(f"   📄 {note_path}")
    print(f"   🌐 index.html 已刷新")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

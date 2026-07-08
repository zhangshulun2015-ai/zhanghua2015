"""
手动添加知识笔记 — 支持知识点/链接/图片/自定义文字

不依赖视频提取流程，直接生成标准格式 Markdown 笔记，
自动更新 index.md / log.md / Dashboard。

Usage (命令行):
  python add_note.py --vault "<你的知识库路径>" \\
    --title "标题" \\
    --category "AI教程资料" \\
    --summary "一句话摘要" \\
    --content "核心内容文字" \\
    --kp '[{"title":"知识点1","concept":"概念说明","points":["要点1","要点2"]}]' \\
    --links '[{"title":"网站名","url":"https://..."}]' \\
    --images '[{"url":"https://...","desc":"图片说明"}]' \\
    --tags '["标签1","标签2"]' \\
    --quotes '["金句1","金句2"]' \\
    --notes "补充文字"

Usage (JSON 文件):
  python add_note.py --vault "<你的知识库路径>" --input note_data.json

note_data.json 格式:
  {
    "title": "标题",
    "category": "AI教程资料",
    "summary": "一句话摘要",
    "content": "核心内容",
    "knowledge_points": [{"title":"...","concept":"...","points":["...","..."]}],
    "links": [{"title":"...","url":"..."}],
    "images": [{"url":"...","desc":"..."}],
    "tags": ["标签1"],
    "quotes": ["金句1"],
    "notes": "补充文字"
  }
"""
import os, sys, re, json, argparse, subprocess
from pathlib import Path
from datetime import datetime
from vault_config import resolve_vault_path, save_vault_path
from knowledge_schema import (
    CATEGORIES,
    DOMAIN,
    DOMAIN_DIR,
    normalize_category,
    render_ai_reference,
    render_index,
    render_schema,
)

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"

SOURCE_LABELS = {
    "manual": "手动添加",
    "pdf": "PDF文档",
    "pdf_ocr": "扫描PDF",
    "word": "Word文档",
    "spreadsheet": "表格文件",
    "ppt": "PPT文档",
    "image": "图片文件",
    "image_ocr": "图片OCR",
    "text": "文本文件",
    "markdown": "Markdown文件",
}


def _safe_name(s: str, max_len: int = 50) -> str:
    return re.sub(r'[\\/*?:"<>|]', '', s)[:max_len]


def build_note(data: dict) -> str:
    """从用户输入构建标准格式 Markdown 笔记。"""
    today = datetime.now().strftime("%Y-%m-%d")

    title = data.get("title", "未命名笔记")
    category = normalize_category(data.get("category", "素材与案例库"))
    source_type = data.get("source_type", "manual")
    source_label = SOURCE_LABELS.get(source_type, "本地资料")
    source = data.get("source", "")
    summary = data.get("summary", "")
    content = data.get("content", "")
    knowledge_points = data.get("knowledge_points", [])
    links = data.get("links", [])
    images = data.get("images", [])
    tags = data.get("tags", [])
    quotes = data.get("quotes", [])
    notes = data.get("notes", "")

    tags_str = "[" + ", ".join(tags) + "]" if tags else "[]"
    word_count = len(content) + len(notes)
    ai_reference_md = render_ai_reference({
        **data,
        "category": category,
        "tags": tags,
        "core_content": content,
        "ai_refs": data.get("ai_refs") or [link.get("title", link.get("url", "")) for link in links],
    })

    # ---- 知识点 ----
    kp_md = ""
    if knowledge_points:
        for i, kp in enumerate(knowledge_points):
            idx = CIRCLED[i] if i < len(CIRCLED) else str(i + 1)
            kp_title = kp.get("title", f"知识点{i+1}")
            concept = kp.get("concept", "")
            points = kp.get("points", [])
            kp_md += f"### 知识点{idx}：{kp_title}\n\n"
            kp_md += f"**概念**：{concept}\n\n"
            if points:
                kp_md += "**要点**：\n"
                for p in points:
                    kp_md += f"- {p}\n"
                kp_md += "\n"
            else:
                kp_md += "**要点**：\n- （待补充）\n\n"

    # ---- 图片 ----
    images_md = ""
    if images:
        for img in images:
            url = img.get("url", "")
            desc = img.get("desc", "")
            if url:
                images_md += f"![{desc}]({url})\n"
                if desc:
                    images_md += f"*{desc}*\n"
                images_md += "\n"

    # ---- 链接 ----
    links_md = ""
    if links:
        for link in links:
            ltitle = link.get("title", link.get("url", ""))
            lurl = link.get("url", "")
            if lurl:
                links_md += f"- [{ltitle}]({lurl})\n"
    links_md += "- 知识库规范：[[../WIKI-SCHEMA]]\n"
    links_md += "- 总目录：[[../index]]\n"
    links_md += "- 操作日志：[[../log]]\n"

    # ---- 金句 ----
    quotes_md = ""
    if quotes:
        for q in quotes:
            quotes_md += f"> {q}\n\n"

    # ---- 补充内容 ----
    notes_md = notes if notes else "（无）"

    # ---- 组装 ----
    note = f"""---
title: {title}
type: manual-note
domain: {DOMAIN}
source_type: {source_type}
category: {category}
created: {today}
updated: {today}
source: {source}
duration: ""
word_count: {word_count}
tags: {tags_str}
---

# 🎬 {title}

> *{category}类笔记 · 来源：{source_label} · 个人知识补充*
>
> {summary}

---

{ai_reference_md}

---

## 📌 核心内容

{content}

---

## 🧠 知识点

{kp_md if kp_md else '（暂无知识点）'}

---

## 🖼️ 图片

{images_md if images_md else '（暂无图片）'}

---

## 💬 补充内容

> 以下为个人补充的文字内容。

{notes_md}

---

## 💡 金句摘录

{quotes_md if quotes_md else '（暂无）'}

---

## 🔗 参考

{links_md}

---

*由 [video-knowledge] Skill 手动添加 · {today} · 遵循 [[../WIKI-SCHEMA|WIKI-SCHEMA]] 规范*
"""
    return note


def init_vault(vault: Path) -> bool:
    """初始化知识库（如果不存在则创建完整结构）。"""
    domain_dir = vault / DOMAIN_DIR
    wiki_dir = domain_dir / "wiki"

    if wiki_dir.exists():
        required = [
            domain_dir / "WIKI-SCHEMA.md",
            wiki_dir / "index.md",
            wiki_dir / "log.md",
        ]
        missing = [f for f in required if not f.exists()]
        if not missing:
            print(f"  ✅ 知识库已存在: {domain_dir}")
            return False

    print(f"\n  🆕 知识库不存在，自动初始化...")
    for cat in CATEGORIES:
        (wiki_dir / cat).mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "视频文件").mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "图片文件").mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "文档文件").mkdir(parents=True, exist_ok=True)

    schema_path = domain_dir / "WIKI-SCHEMA.md"
    if not schema_path.exists():
        schema_path.write_text(render_schema(), encoding='utf-8')

    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        index_path.write_text(render_index(), encoding='utf-8')

    log_path = wiki_dir / "log.md"
    if not log_path.exists():
        log_path.write_text(f"""# 操作日志

> 追加记录，每条格式：`## [日期] 操作类型 | 标题`

---

## [{datetime.now().strftime('%Y-%m-%d')}] init | 知识库自动初始化

- 由 video-knowledge skill 自动创建
- Karpathy LLM Wiki 三层架构
""", encoding='utf-8')

    print(f"  ✅ 知识库初始化完成")
    return True


def update_index(vault: Path, title: str, category: str, summary: str, date: str, source_type: str = "manual"):
    """更新 wiki/index.md。"""
    index_path = vault / DOMAIN_DIR / "wiki" / "index.md"
    if not index_path.exists():
        return

    content = index_path.read_text(encoding='utf-8')
    safename = _safe_name(title)

    section_markers = {cat: f"## {cat}" for cat in CATEGORIES}
    marker = section_markers.get(category, f"## {CATEGORIES[0]}")
    source_label = SOURCE_LABELS.get(source_type, "手动")
    new_row = f"| — | [{source_label}] [[{category}/{safename}]] | {summary} | — | {date} |"

    if marker not in content:
        index_path.write_text(render_index(), encoding='utf-8')
        content = index_path.read_text(encoding='utf-8')

    sections = content.split(marker)
    if len(sections) < 2:
        return

    before = sections[0]
    section_body = sections[1]
    next_section_idx = len(section_body)
    for m in section_markers.values():
        idx = section_body.find(m)
        if 0 < idx < next_section_idx:
            next_section_idx = idx

    target = section_body[:next_section_idx]
    rest = section_body[next_section_idx:]

    if "| — | 暂无" in target:
        target = target.replace("| — | 暂无 | — | — | — |", new_row, 1)
    else:
        lines = target.split('\n')
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if '|---' in line and not inserted:
                new_lines.append(new_row)
                inserted = True
        if inserted:
            target = '\n'.join(new_lines)
        else:
            target = target.rstrip() + '\n' + new_row + '\n'

    new_content = before + marker + target + rest
    today = datetime.now().strftime("%Y-%m-%d")
    new_content = re.sub(r'最后更新\*\*：\d{4}-\d{2}-\d{2}', f'最后更新**：{today}', new_content)
    index_path.write_text(new_content, encoding='utf-8')
    print(f"  ✅ index.md 已更新")


def append_log(vault: Path, title: str, category: str, source_type: str = "manual"):
    """追加操作日志。"""
    log_path = vault / DOMAIN_DIR / "wiki" / "log.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    safename = _safe_name(title)
    entry = f"""
## [{today}] manual | {title}

- 来源：{SOURCE_LABELS.get(source_type, source_type)}
- 分类：{category}
- 笔记路径：`wiki/{category}/{safename}.md`
"""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f"  ✅ log.md 已更新")


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
    parser = argparse.ArgumentParser(description="手动添加知识笔记到图文视频知识库")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库根路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    parser.add_argument("--input", help="JSON 数据文件路径（可选，优先使用）")
    parser.add_argument("--title", default="未命名笔记", help="笔记标题")
    parser.add_argument("--category", default="素材与案例库", help="分类")
    parser.add_argument("--summary", default="", help="一句话摘要")
    parser.add_argument("--content", default="", help="核心内容")
    parser.add_argument("--kp", default="", help="知识点 JSON: [{title,concept,points:[]}]")
    parser.add_argument("--links", default="", help="链接 JSON: [{title,url}]")
    parser.add_argument("--images", default="", help="图片 JSON: [{url,desc}]")
    parser.add_argument("--tags", default="", help="标签 JSON: [\"tag1\"]")
    parser.add_argument("--quotes", default="", help="金句 JSON: [\"quote1\"]")
    parser.add_argument("--notes", default="", help="补充文字")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)

    # 加载数据
    if args.input:
        data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    else:
        data = {
            "title": args.title,
            "category": args.category,
            "summary": args.summary,
            "content": args.content,
        }
        if args.kp:
            data["knowledge_points"] = json.loads(args.kp)
        if args.links:
            data["links"] = json.loads(args.links)
        if args.images:
            data["images"] = json.loads(args.images)
        if args.tags:
            data["tags"] = json.loads(args.tags)
        if args.quotes:
            data["quotes"] = json.loads(args.quotes)
        if args.notes:
            data["notes"] = args.notes

    # 自动初始化知识库
    init_vault(vault)

    title = data.get("title", "未命名笔记")
    category = normalize_category(data.get("category", "素材与案例库"))
    data["category"] = category
    source_type = data.get("source_type", "manual")
    summary = data.get("summary", "")

    print(f"\n{'='*50}")
    print(f"📝 手动添加笔记: {title}")
    print(f"   分类: {category} | 摘要: {summary[:40]}")
    print(f"{'='*50}\n")

    # 生成笔记
    note = build_note(data)
    safename = _safe_name(title)
    wiki_dir = vault / DOMAIN_DIR / "wiki"
    note_path = wiki_dir / category / f"{safename}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding='utf-8')
    print(f"  ✅ 笔记: wiki/{category}/{safename}.md")

    today = datetime.now().strftime("%Y-%m-%d")

    # 更新 index + log
    update_index(vault, title, category, summary, today, source_type)
    append_log(vault, title, category, source_type)

    # 刷新 Dashboard
    print(f"\n  🔄 刷新 Dashboard...")
    regenerate_dashboard(vault)

    print(f"\n{'='*50}")
    print(f"✅ 笔记添加完成!")
    print(f"   📄 {note_path}")
    print(f"   🏷️ {category} | {SOURCE_LABELS.get(source_type, source_type)}")
    print(f"   🌐 index.html 已刷新")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

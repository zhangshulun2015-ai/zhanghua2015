"""
重新生成知识库 Dashboard (index.html) — 多平台图文视频知识库

读取 wiki/ 下所有分类目录的 Markdown 笔记，生成可搜索/过滤的知识浏览页面。
支持抖音/B站/小红书/YouTube/X 多平台来源。

用法:
  python regenerate_dashboard.py --vault <你的知识库路径>
"""
import re
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from vault_config import resolve_vault_path, save_vault_path
from knowledge_schema import CATEGORIES, DOMAIN_DIR, build_ai_reference, normalize_category

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SOURCE_BADGES = {
    "douyin": "🎵 抖音",
    "bilibili": "📺 B站",
    "xiaohongshu": "📕 小红书",
    "youtube": "▶️ YouTube",
    "x": "🐦 X",
    "manual": "✍️ 手动",
    "pdf": "📄 PDF",
    "pdf_ocr": "🔎 扫描PDF",
    "word": "📝 Word",
    "spreadsheet": "📊 表格",
    "ppt": "📽️ PPT",
    "image": "🖼️ 图片",
    "image_ocr": "🔎 图片OCR",
    "text": "📃 文本",
    "markdown": "Ⓜ️ Markdown",
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r'^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n', text, re.DOTALL)
    if not match:
        return {}, text
    fm_text = match.group(1)
    body = text[match.end():]

    meta = {}
    tags_list = []
    for line in fm_text.strip().split('\n'):
        line = line.rstrip()
        if line.strip().startswith('tags:') and '[' in line:
            tag_text = line.split(':', 1)[1].strip()
            tags_list = [t.strip().strip('"').strip("'") for t in tag_text.strip('[]').split(',')]
        elif ':' in line and not line.strip().startswith('-'):
            key, val = line.split(':', 1)
            val = val.strip().strip('"').strip("'")
            if val:
                meta[key.strip()] = val
    if tags_list:
        meta['tags_parsed'] = tags_list

    return meta, body


def extract_summary(body: str) -> str:
    match = re.search(r'>\s*\*.*?(?:视频|笔记)\*\s*\n>\s*\n>\s*(.+?)(?:\n\n|\n#)', body, re.DOTALL)
    if match:
        return ' '.join(match.group(1).strip().split('\n')).strip()[:150]
    match = re.search(r'##\s*📌\s*核心内容\s*\n+(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if match:
        text = match.group(1).strip()
        lines = [l.strip('- ').strip() for l in text.split('\n') if l.strip()]
        return '；'.join(lines[:3]) if lines else text[:150]
    return ""


def extract_ai_reference(body: str, fallback: dict) -> dict:
    """Extract the AI quick-reference section from Markdown."""
    match = re.search(r'##\s*🤖\s*AI快速参考\s*\n+(.*?)(?:\n---\n|\n##|\Z)', body, re.DOTALL)
    data = {}
    if match:
        section = match.group(1)
        label_map = {
            "适合回答的问题": "questions",
            "可直接引用的结论": "conclusions",
            "关键术语": "terms",
            "适用场景": "scenarios",
            "关联资料": "refs",
        }
        for line in section.splitlines():
            clean = line.strip().lstrip("-").strip()
            if "：" not in clean:
                continue
            label, value = clean.split("：", 1)
            key = label_map.get(label.strip())
            if not key:
                continue
            items = [v.strip() for v in re.split(r'[；;、]', value) if v.strip() and v.strip() != "（待补充）"]
            data[key] = items

    ref = build_ai_reference({
        **fallback,
        "ai_questions": data.get("questions", []),
        "ai_conclusions": data.get("conclusions", []),
        "key_terms": data.get("terms", []),
        "use_cases": data.get("scenarios", []),
        "ai_refs": data.get("refs", []),
    })
    return ref


def extract_knowledge_points(body: str) -> list[dict]:
    pattern = r'###\s*知识点\s*[①②③④⑤⑥⑦⑧⑨⑩\d]+[：:]\s*(.+?)\n\n\*\*概念\*\*[：:]\s*(.+?)\n\n\*\*要点\*\*[：:]\s*\n((?:\s*-.*?\n)*)'
    matches = re.findall(pattern, body, re.DOTALL)
    if matches:
        return [
            {"title": t.strip(), "concept": c.strip(),
             "points": [p.strip() for p in re.findall(r'-\s+(.+?)(?:\n|$)', pt)]}
            for t, c, pt in matches
        ]

    pattern2 = r'###\s*知识点\s*[①②③④⑤⑥⑦⑧⑨⑩\d]+[：:]\s*(.+?)\n\n\*\*概念\*\*[：:]\s*(.+?)\n\n\*\*启示\*\*[：:]\s*(.+?)(?:\n###|\n---|\Z)'
    matches2 = re.findall(pattern2, body, re.DOTALL)
    return [
        {"title": t.strip(), "concept": c.strip(), "points": [i.strip()]}
        for t, c, i in matches2
    ]


def extract_tools(body: str) -> list[dict]:
    pattern = r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|'
    matches = re.findall(pattern, body)
    return [{"name": m[0].strip(), "usage": m[1].strip()} for m in matches]


def extract_images(body: str, note_path: Path = None, vault_root: Path = None) -> list[dict]:
    """从 ## 🖼️ 图片 区提取图片，解析本地相对路径。"""
    img_section = re.search(r'##\s*🖼️\s*图片\s*\n+(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if not img_section:
        return []
    section_text = img_section.group(1)
    images = []
    for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', section_text):
        url = m.group(2).strip()
        desc = m.group(1).strip()
        # 将相对路径（../../raw/图片文件/xxx.jpg）转为绝对文件路径
        if url.startswith('../') and note_path and vault_root:
            resolved = (note_path.parent / url).resolve()
            if resolved.exists():
                url = str(resolved)
        images.append({"desc": desc, "url": url})
    return images


def extract_links(body: str) -> list[dict]:
    """从 ## 🔗 参考 区提取参考链接。"""
    link_section = re.search(r'##\s*🔗\s*参考.*?\n+(.*?)(?:\n---\n|\n\n\*由|\Z)', body, re.DOTALL)
    if not link_section:
        return []
    section_text = link_section.group(1)
    links = []
    for m in re.finditer(r'-\s+\[([^\]]+)\]\(([^)]+)\)', section_text):
        title = m.group(1).strip()
        url = m.group(2).strip()
        # 排除 Obsidian 内部链接
        if not url.startswith('../') and not url.startswith('['):
            links.append({"title": title, "url": url})
    return links


def parse_note(filepath: Path, vault_root: Path) -> dict:
    text = filepath.read_text(encoding='utf-8')
    fm, body = parse_frontmatter(text)

    title_match = re.search(r'#\s*🎬\s*(.+?)(?:\n|$)', body)
    title = title_match.group(1).strip() if title_match else filepath.stem

    tags = fm.get('tags_parsed', [])
    if not tags:
        tag_section = False
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped == 'tags:':
                tag_section = True
                continue
            if tag_section:
                if stripped.startswith('- ') and not stripped.startswith('---'):
                    tags.append(stripped[2:].strip())
                elif stripped == '---' or (stripped and not stripped.startswith('-')):
                    tag_section = False

    summary = extract_summary(body)
    kps = extract_knowledge_points(body)
    tools = extract_tools(body)

    # 适用人群
    audience = []
    audience_match = re.search(r'##\s*🎯\s*适用人群\s*\n+(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if audience_match:
        audience = re.findall(r'-\s+(.+?)(?:\n|$)', audience_match.group(1))

    # 金句
    quotes = []
    quotes_match = re.search(r'##\s*💡\s*金句摘录\s*\n+(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if quotes_match:
        quotes = [l.strip('> " \n') for l in quotes_match.group(1).split('\n')
                  if l.strip().startswith('>')]

    # 追加内容区块 — 支持多次追加
    append_blocks = []
    for app_match in re.finditer(
        r'##\s*📝\s*追加内容（(\d{4}-\d{2}-\d{2})）\s*\n>.*?\n(.*?)(?=\n---\n\n\*由|\n---\n\n##\s*📝|\n\n\*由|\Z)',
        body, re.DOTALL):
        app_date = app_match.group(1)
        app_body = app_match.group(2)

        app_content = ""
        app_kps = []
        app_images = []
        app_quotes = []

        # 补充文字
        text_section = re.search(r'###\s*💬\s*补充文字\s*\n+(.*?)(?=\n###|\Z)', app_body, re.DOTALL)
        if text_section:
            app_content = text_section.group(1).strip()

        # 新增知识点
        kp_section = re.search(r'###\s*🧠\s*新增知识点\s*\n+(.*?)(?=\n###|\Z)', app_body, re.DOTALL)
        if kp_section:
            kp_text = kp_section.group(1)
            for kp_match in re.finditer(r'####\s*知识点[①②③④⑤⑥⑦⑧⑨⑩]*[：:]\s*(.*?)\n+(.*?)(?=\n####|\Z)', kp_text, re.DOTALL):
                kp_title = kp_match.group(1).strip()
                kp_detail = kp_match.group(2).strip()
                # 提取概念 — 匹配 **概念**： 后面的非空内容，到下一个 ** 标签为止
                concept_match = re.search(r'\*\*概念\*\*[：:]\s*\n?(.*?)(?=\n\*\*|\Z)', kp_detail, re.DOTALL)
                raw_concept = concept_match.group(1).strip() if concept_match else ""
                # 如果概念内容以 ** 开头说明是空概念（抓到了下一个标签），清空
                concept = "" if (not raw_concept or raw_concept.startswith('**') or raw_concept == '（待补充）') else raw_concept
                # 提取要点 — 匹配 - 开头的行，过滤掉 （待补充）
                points = [l.strip('- \n') for l in kp_detail.split('\n') if l.strip().startswith('-') and l.strip() != '- （待补充）']
                app_kps.append({
                    "title": kp_title,
                    "concept": concept,
                    "points": points,
                })

        # 图片
        img_section = re.search(r'###\s*🖼️\s*新增图片\s*\n+(.*?)(?=\n###|\Z)', app_body, re.DOTALL)
        if img_section:
            for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', img_section.group(1)):
                url = m.group(2).strip()
                desc = m.group(1).strip()
                if url.startswith('../') and filepath and vault_root:
                    resolved = (filepath.parent / url).resolve()
                    if resolved.exists():
                        url = str(resolved)
                app_images.append({"desc": desc, "url": url})

        # 金句
        quotes_section = re.search(r'###\s*💡\s*新增金句\s*\n+(.*?)(?=\n###|\Z)', app_body, re.DOTALL)
        if quotes_section:
            app_quotes = [l.strip('> " \n') for l in quotes_section.group(1).split('\n')
                          if l.strip().startswith('>')]

        append_blocks.append({
            "date": app_date,
            "content": app_content,
            "kps": app_kps,
            "images": app_images,
            "quotes": app_quotes,
        })

    # 转录
    transcript = ""
    t_match = re.search(
        r'##\s*💬\s*完整转录\s*\n+(.*?)(?:\n---\n|\n##\s*🔗|\n##\s*💡|\n\n\*由|\Z)',
        body, re.DOTALL)
    if t_match:
        transcript = t_match.group(1).strip()
    else:
        extracted_match = re.search(
            r'##\s*提取正文\s*\n+(.*?)(?:\n##\s*表格内容|\n---\n\n##\s*🧠|\n---\n\n##\s*💬|\Z)',
            body, re.DOTALL)
        if extracted_match:
            transcript = extracted_match.group(1).strip()

    # 视频路径
    video_match = re.search(r'\[\[\.\./\.\./raw/视频文件/(.*?\.mp4)\]\]', body)
    if not video_match:
        video_match = re.search(r'raw/视频文件/(.*?\.mp4)', body)
    video_path = ""
    video_name = video_match.group(1) if video_match else ""
    if video_name:
        video_file = vault_root / DOMAIN_DIR / "raw" / "视频文件" / video_name
        if video_file.exists():
            video_path = f"{DOMAIN_DIR}/raw/视频文件/{video_name}"

    # 缩略图路径（与视频同目录的 .thumb.jpg）
    thumb_path = ""
    if video_name:
        thumb_name = Path(video_name).stem + ".thumb.jpg"
        thumb_file = vault_root / DOMAIN_DIR / "raw" / "视频文件" / thumb_name
        if thumb_file.exists():
            thumb_path = f"{DOMAIN_DIR}/raw/视频文件/{thumb_name}"

    # 文件夹路径（.md 所在目录）
    folder_path = str(filepath.parent.absolute())

    category = normalize_category(fm.get('category', '其他'))
    source_type = fm.get('source_type', 'douyin')
    source_badge = SOURCE_BADGES.get(source_type, "")
    ai_reference = extract_ai_reference(body, {
        "summary": summary,
        "core_content": summary,
        "tags": tags,
        "audience": audience,
        "cross_refs": [l.get("title", "") for l in extract_links(body)],
    })

    return {
        "id": f"note-{hash(str(filepath.absolute())) % 100000:05d}",
        "title": title,
        "summary": summary or extract_summary(body),
        "tags": tags,
        "category": category,
        "date": fm.get('date', fm.get('created', datetime.now().strftime('%Y-%m-%d'))),
        "duration": fm.get('duration', ''),
        "source": fm.get('source', ''),
        "sourceType": source_type,
        "sourceBadge": source_badge,
        "video": video_path,
        "thumbnail": thumb_path,
        "transcript": transcript,
        "knowledgePoints": kps,
        "goldenQuotes": quotes,
        "audience": audience,
        "tools": tools,
        "images": extract_images(body, filepath, vault_root),
        "links": extract_links(body),
        "aiReference": ai_reference,
        "filePath": str(filepath.absolute()),
        "folderPath": folder_path,
        "appendBlocks": append_blocks,
    }


def regenerate(vault_path: Path):
    wiki_dir = vault_path / DOMAIN_DIR / "wiki"

    if not wiki_dir.exists():
        print(f"❌ 知识库 wiki/ 目录不存在: {wiki_dir}")
        return

    notes = []
    for md_file in sorted(wiki_dir.rglob("*.md")):
        if md_file.name in ('index.md', 'log.md'):
            continue
        try:
            note = parse_note(md_file, vault_path)
            notes.append(note)
            print(f"  ✅ {md_file.relative_to(wiki_dir)} → {note['title']} [{note.get('sourceBadge', '')}]")
        except Exception as e:
            print(f"  ⚠️ {md_file.name} 解析失败: {e}")

    notes_json = json.dumps(notes, ensure_ascii=False, indent=2)

    template_path = Path(__file__).parent.parent / "assets" / "dashboard-template.html"
    if not template_path.exists():
        print(f"❌ 模板不存在: {template_path}")
        return

    template = template_path.read_text(encoding='utf-8')

    html = template.replace('{{NOTES_DATA}}', notes_json)
    html = html.replace('{{GENERATED_AT}}', datetime.now().strftime('%Y-%m-%d %H:%M'))
    html = html.replace('{{VAULT_PATH_JSON}}', json.dumps(str(vault_path), ensure_ascii=False))
    html = html.replace('{{SKILL_ROOT_JSON}}', json.dumps(str(Path(__file__).parent.parent), ensure_ascii=False))

    output_path = vault_path / "index.html"
    output_path.write_text(html, encoding='utf-8')
    print(f"\n✅ Dashboard 已生成: {output_path}")
    print(f"   📊 {len(notes)} 篇笔记")
    print(f"   📂 分类: {', '.join(sorted(set(n['category'] for n in notes)))}")
    print(f"   🌐 双击 index.html 查看")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="重新生成图文视频知识库 Dashboard")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    args = parser.parse_args()
    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)
    regenerate(vault)

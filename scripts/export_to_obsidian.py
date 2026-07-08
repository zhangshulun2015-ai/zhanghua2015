"""
导出分析结果到 Obsidian — Karpathy LLM Wiki 架构，多平台支持。

=== 支持平台 ===
抖音 / B站 / 小红书 / X (Twitter)

Usage:
  python export_to_obsidian.py transcript.txt \
      --vault "<你的知识库路径>" \
      --analysis analysis.json \
      --video <本地视频路径>

analysis.json 格式:
{
  "title": "视频标题",
  "category": "AI教程资料",
  "tags": ["Obsidian", "AI助手"],
  "summary": "AI摘要",
  "audience": "适用人群",
  "concepts_table": "| 工具 | 说明 |\n...",
  "core_content": "核心内容",
  "steps": "操作步骤",
  "knowledge_points": "知识点Markdown",
  "golden_quotes": "金句",
  "cross_refs": ["相关笔记路径"],
  "link": "源链接",
  "duration": "时长",
  "source_type": "douyin|bilibili|xiaohongshu|x"
}
"""
import os, sys, shutil, argparse, json, re, subprocess
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ffmpeg 路径（自动检测）
FFMPEG = shutil.which("ffmpeg")

PLATFORM_LABELS = {
    "douyin": "抖音",
    "bilibili": "B站",
    "xiaohongshu": "小红书",
    "x": "X",
}

SOURCE_LABELS = {
    "douyin": "抖音链接",
    "bilibili": "B站链接",
    "xiaohongshu": "小红书链接",
    "x": "X链接",
}


def _safe_name(s: str, max_len: int = 50) -> str:
    return re.sub(r'[\\/*?:"<>|]', '', s)[:max_len]


# ---- Video Copy ----

def copy_video(video_path: str, vault: Path) -> Path | None:
    src = Path(video_path)
    if not src.exists():
        print(f"  ⚠️ 视频不存在: {video_path}")
        return None
    dst_dir = vault / DOMAIN_DIR / "raw" / "视频文件"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
        print(f"  ✅ 视频: raw/视频文件/{src.name}")
    else:
        print(f"  ⏭️ 视频已存在: {src.name}")
    # 自动生成缩略图
    generate_thumbnail(dst)
    return dst


# ---- Thumbnail ----

def generate_thumbnail(video_file: Path) -> Path | None:
    """用 ffmpeg 从视频中提取一帧作为缩略图。"""
    if not video_file or not video_file.exists():
        return None
    thumb = video_file.with_suffix(".thumb.jpg")
    if thumb.exists():
        print(f"  ⏭️ 缩略图已存在: {thumb.name}")
        return thumb
    if not FFMPEG:
        print(f"  ⚠️ ffmpeg 未安装，跳过缩略图生成")
        return None
    try:
        result = subprocess.run(
            [FFMPEG, "-y", "-ss", "1", "-i", str(video_file),
             "-frames:v", "1", "-q:v", "5", "-vf", "scale=640:-1",
             str(thumb)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        if thumb.exists() and thumb.stat().st_size > 0:
            print(f"  ✅ 缩略图: {thumb.name}")
            return thumb
        else:
            print(f"  ⚠️ 缩略图生成失败: {result.stderr[:200]}")
            return None
    except Exception as e:
        print(f"  ⚠️ 缩略图生成异常: {e}")
        return None


# ---- Note Builder ----

def build_note(analysis: dict, transcript: str, video_name: str) -> str:
    """从 AI 分析结果 + 原始转录构建完整笔记。"""
    today = datetime.now().strftime("%Y-%m-%d")

    title = analysis.get("title", "未命名")
    category = normalize_category(analysis.get("category", "工具与效率"))
    tags = analysis.get("tags", [])
    summary = analysis.get("summary", "")
    audience = analysis.get("audience", "")
    concepts_table = analysis.get("concepts_table", "")
    core_content = analysis.get("core_content", "")
    steps = analysis.get("steps", "")
    knowledge_points = analysis.get("knowledge_points", "")
    golden_quotes = analysis.get("golden_quotes", "")
    # 金句可能是字符串或列表，统一转为列表
    if isinstance(golden_quotes, str):
        if golden_quotes.strip():
            try:
                golden_quotes = json.loads(golden_quotes)
            except (json.JSONDecodeError, TypeError):
                golden_quotes = [golden_quotes]
        else:
            golden_quotes = []
    if not isinstance(golden_quotes, list):
        golden_quotes = []

    golden_quotes_md = "\n".join(f"> {str(q).strip()}" for q in golden_quotes if str(q).strip()) if golden_quotes else ""
    cross_refs = analysis.get("cross_refs", [])
    link = analysis.get("link", "")
    duration = analysis.get("duration", "")
    source_type = analysis.get("source_type", "douyin")
    platform_label = PLATFORM_LABELS.get(source_type, "视频")
    source_label = SOURCE_LABELS.get(source_type, "链接")

    word_count = len(transcript.replace('\n', '').replace(' ', ''))
    tags_str = "[" + ", ".join(tags) + "]"
    ai_reference_md = render_ai_reference({
        **analysis,
        "category": category,
        "tags": tags,
        "ai_refs": analysis.get("ai_refs") or analysis.get("cross_refs") or [],
    })

    # 交叉引用链接
    ref_links = ""
    if cross_refs:
        ref_links = "\n".join(f"- [[{ref}]]" for ref in cross_refs)

    note = f"""---
title: {title}
type: source-summary
domain: {DOMAIN}
source_type: {source_type}
category: {category}
created: {today}
updated: {today}
source: {link}
duration: {duration}
word_count: {word_count}
tags: {tags_str}
---

# 🎬 {title}

> *{category}类视频 · 来源：{platform_label} · AI 自动提取笔记*
>
> {summary}

---

{ai_reference_md}

---

## 📌 核心内容

{core_content}

---

## 🎯 适用人群

{audience}

---

## 🛠 涉及工具 / 概念

{concepts_table}

---

## 📋 操作步骤

{steps}

---

## 🧠 知识点

{knowledge_points}

---

## 💬 完整转录

> 以下为视频语音的完整转录，保留口语化表达。

{transcript}

---

## 💡 金句摘录

{golden_quotes_md}

---

## 🔗 参考

- 原视频：[{source_label}]({link})
- 本地视频：[[../../raw/视频文件/{video_name}]]{' - 点击播放' if video_name else ''}
{f'- 相关笔记：{chr(10)}{ref_links}' if ref_links else ''}
- 知识库规范：[[../WIKI-SCHEMA]]
- 总目录：[[../index]]
- 操作日志：[[../log]]

---

*由 [video-knowledge] Skill 生成 · {today} · 遵循 [[../WIKI-SCHEMA|WIKI-SCHEMA]] 规范*
"""
    return note


def init_vault(vault: Path) -> bool:
    """初始化知识库（如果不存在则创建完整结构），返回是否为新创建。"""
    domain_dir = vault / DOMAIN_DIR
    wiki_dir = domain_dir / "wiki"

    if wiki_dir.exists():
        # 验证关键文件
        required = [
            domain_dir / "WIKI-SCHEMA.md",
            wiki_dir / "index.md",
            wiki_dir / "log.md",
        ]
        missing = [f for f in required if not f.exists()]
        if not missing:
            print(f"  ✅ 知识库已存在: {domain_dir}")
            return False
        print(f"  ⚠️ 知识库存在但缺少文件: {[m.name for m in missing]}")
        # 继续并补建缺失的
    else:
        print(f"\n  🆕 知识库不存在，自动初始化...")

    # 创建目录
    for cat in CATEGORIES:
        (wiki_dir / cat).mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "视频文件").mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "图片文件").mkdir(parents=True, exist_ok=True)
    (domain_dir / "raw" / "文档文件").mkdir(parents=True, exist_ok=True)

    # WIKI-SCHEMA.md
    schema_path = domain_dir / "WIKI-SCHEMA.md"
    if not schema_path.exists():
        schema_path.write_text(render_schema(), encoding='utf-8')

    # wiki/index.md
    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        index_path.write_text(render_index(), encoding='utf-8')

    # wiki/log.md
    log_path = wiki_dir / "log.md"
    if not log_path.exists():
        log_path.write_text(f"""# 操作日志

> 追加记录，每条格式：`## [日期] 操作类型 | 标题`

---

## [{datetime.now().strftime('%Y-%m-%d')}] init | 知识库自动初始化

- 由 video-knowledge skill 自动创建
- Karpathy LLM Wiki 三层架构
- 使用 10 个目录栏 + AI快速参考区
""", encoding='utf-8')

    print(f"  ✅ 知识库初始化完成: {domain_dir}")
    print(f"     WIKI-SCHEMA.md · index.md · log.md · 10 个分类目录")
    return True


# ---- Index Update ----

def update_index(vault: Path, title: str, category: str, summary: str,
                 duration: str, date: str, source_type: str) -> None:
    """更新 wiki/index.md。"""
    index_path = vault / DOMAIN_DIR / "wiki" / "index.md"
    if not index_path.exists():
        return

    content = index_path.read_text(encoding='utf-8')
    safename = _safe_name(title)
    platform_label = PLATFORM_LABELS.get(source_type, "")

    section_markers = {cat: f"## {cat}" for cat in CATEGORIES}
    marker = section_markers.get(category, f"## {CATEGORIES[0]}")

    source_badge = f"[{platform_label}] " if platform_label else ""
    new_row = f"| — | {source_badge}[[{category}/{safename}]] | {summary} | {duration} | {date} |"

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
        for i, line in enumerate(lines):
            new_lines.append(line)
            if '|---' in line and not inserted:
                new_lines.append(new_row)
                inserted = True
        if inserted:
            target = '\n'.join(new_lines)
        else:
            target = target.rstrip() + '\n' + new_row + '\n'

    new_content = before + marker + target + rest

    # 更新日期
    today = datetime.now().strftime("%Y-%m-%d")
    new_content = re.sub(r'最后更新\*\*：\d{4}-\d{2}-\d{2}', f'最后更新**：{today}', new_content)

    index_path.write_text(new_content, encoding='utf-8')
    print(f"  ✅ index.md 已更新")


# ---- Log Append ----

def append_log(vault: Path, title: str, category: str, duration: str,
               source_type: str, link: str) -> None:
    """追加操作日志。"""
    log_path = vault / DOMAIN_DIR / "wiki" / "log.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    safename = _safe_name(title)
    platform_label = PLATFORM_LABELS.get(source_type, source_type)

    entry = f"""
## [{today}] ingest | {title}

- 来源：{platform_label}（{link}）
- 分类：{category}
- 时长：{duration}
- 笔记路径：`wiki/{category}/{safename}.md`
- 视频路径：`raw/视频文件/`
"""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f"  ✅ log.md 已更新")


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(description="导出分析结果到 Obsidian 图文视频知识库")
    parser.add_argument("transcript", help="转录文本 (.txt)")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库根路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    parser.add_argument("--analysis", required=True, help="AI 分析结果 JSON 文件")
    parser.add_argument("--video", default="", help="本地视频路径")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)

    # 自动检测并初始化知识库
    is_new = init_vault(vault)
    wiki_dir = vault / DOMAIN_DIR / "wiki"

    # 加载数据
    transcript = Path(args.transcript).read_text(encoding='utf-8').strip()
    analysis = json.loads(Path(args.analysis).read_text(encoding='utf-8'))

    if not transcript:
        print("❌ 转录为空")
        sys.exit(1)

    title = analysis.get("title", "未命名")
    category = normalize_category(analysis.get("category", "工具与效率"))
    source_type = analysis.get("source_type", "douyin")
    platform_label = PLATFORM_LABELS.get(source_type, source_type)

    print(f"\n{'='*50}")
    print(f"📝 图文视频知识库 Ingest: {title}")
    print(f"   转录: {len(transcript)} 字 | 分类: {category} | 来源: {platform_label}")
    print(f"{'='*50}\n")

    # 1. 复制视频到 raw/
    video_name = Path(args.video).name if args.video else ""
    if args.video:
        copy_video(args.video, vault)

    # 2. 生成笔记
    note = build_note(analysis, transcript, video_name)
    safename = _safe_name(title)
    note_path = vault / DOMAIN_DIR / "wiki" / category / f"{safename}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding='utf-8')
    print(f"  ✅ 笔记: wiki/{category}/{safename}.md")

    today = datetime.now().strftime("%Y-%m-%d")

    # 3. 更新 index
    update_index(vault, title, category, analysis.get("summary", ""),
                 analysis.get("duration", ""), today, source_type)

    # 4. 追加 log
    append_log(vault, title, category, analysis.get("duration", ""),
               source_type, analysis.get("link", ""))

    print(f"\n{'='*50}")
    print(f"✅ Ingest 完成!")
    print(f"   📄 {note_path}")
    print(f"   🏷️ {category} | 来源: {platform_label}")
    print(f"   💡 运行 regenerate_dashboard.py 刷新首页")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

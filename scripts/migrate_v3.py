"""Migrate an existing 图文视频知识库 vault to the current 10-category schema."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from knowledge_schema import (
    CATEGORIES,
    DOMAIN_DIR,
    VERSION_LABEL,
    normalize_category,
    render_ai_reference,
    render_index,
    render_schema,
)
from vault_config import resolve_vault_path, save_vault_path

LEGACY_DIRS = [
    "AI技术资料", "质量管理资料", "AI视频脚本学习", "文学文献",
    "一般软件学习", "社会热点", "工具与效率", "认知与思维",
    "技术与编程", "生活与成长", "其他", "软件工具资料",
    "认知方法资料", "项目案例资料",
]


def read_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", text, re.DOTALL)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.strip().startswith("-"):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[match.end():]


def write_frontmatter(text: str, category: str) -> str:
    match = re.match(r"^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", text, re.DOTALL)
    if not match:
        return text
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    seen_category = False
    seen_updated = False
    for line in match.group(1).splitlines():
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key == "category":
            lines.append(f"category: {category}")
            seen_category = True
        elif key == "updated":
            lines.append(f"updated: {today}")
            seen_updated = True
        else:
            lines.append(line)
    if not seen_category:
        lines.append(f"category: {category}")
    if not seen_updated:
        lines.append(f"updated: {today}")
    fm = "\n".join(lines)
    return f"---\n{fm}\n---\n" + text[match.end():]


def extract_summary(body: str) -> str:
    match = re.search(r">\s*(?!\*)(.+?)(?:\n\n|\n---)", body, re.DOTALL)
    if match:
        return " ".join(match.group(1).split())[:120]
    match = re.search(r"##\s*📌\s*核心内容\s*\n+(.*?)(?:\n---|\n##|\Z)", body, re.DOTALL)
    if match:
        return " ".join(match.group(1).split())[:120]
    return ""


def extract_tags(meta: dict) -> list[str]:
    raw = meta.get("tags", "")
    if raw.startswith("[") and raw.endswith("]"):
        return [t.strip().strip('"').strip("'") for t in raw.strip("[]").split(",") if t.strip()]
    return []


def choose_category(title: str, old_category: str) -> str:
    if "手把手教你创建个人知识库" in title:
        return "AI教程资料"
    if "AI视频制作" in title or "多模型组合工作流" in title:
        return "视频解说资料"
    if "GPT Image 2" in title or "Seedance" in title or "奇幻旅程" in title:
        return "提示词专项资料"
    return normalize_category(old_category)


def ensure_ai_reference(text: str, meta: dict, category: str) -> str:
    if "## 🤖 AI快速参考" in text:
        return text
    _, body = read_frontmatter(text)
    summary = extract_summary(body)
    tags = extract_tags(meta)
    ai_md = render_ai_reference({
        "summary": summary,
        "category": category,
        "tags": tags,
        "use_cases": [category],
        "ai_questions": [meta.get("title", "")] if meta.get("title") else [],
    })
    insert = f"\n---\n\n{ai_md}\n\n"
    marker = "\n---\n\n## 📌 核心内容"
    if marker in text:
        return text.replace(marker, insert + "## 📌 核心内容", 1)
    heading = re.search(r"(#\s*🎬.*?\n)", text)
    if heading:
        idx = heading.end()
        return text[:idx] + insert + text[idx:]
    return text + insert


def rewrite_index(vault: Path, notes: list[dict]) -> None:
    wiki_dir = vault / DOMAIN_DIR / "wiki"
    sections = []
    for cat in CATEGORIES:
        rows = [n for n in notes if n["category"] == cat]
        table_rows = [
            f"| — | {n['badge']}[[{cat}/{n['name']}]] | {n['summary']} | {n['duration']} | {n['date']} |"
            for n in rows
        ] or ["| — | 暂无 | — | — | — |"]
        sections.append(
            f"## {cat}\n\n| # | 笔记 | 摘要 | 时长 | 日期 |\n|---|------|------|------|------|\n" + "\n".join(table_rows)
        )
    today = datetime.now().strftime("%Y-%m-%d")
    text = f"""# {VERSION_LABEL} — 总目录

> 本文件由 AI 自动维护。优先按 10 个目录栏组织资料，并为 AI 投喂保留短摘要入口。

---

{chr(10).join(sections)}

---

## 统计

- **总笔记数**：{len(notes)}
- **总视频时长**：—
- **知识点总数**：—
- **最后更新**：{today}

---

*由 [video-knowledge] Skill 自动维护 · 遵循 [[../WIKI-SCHEMA]]*
"""
    (wiki_dir / "index.md").write_text(text, encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="升级图文视频知识库到当前 10 分类结构")
    parser.add_argument("--vault", default=None, help="知识库根路径，默认读取配置")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)
    domain = vault / DOMAIN_DIR
    wiki = domain / "wiki"
    if not wiki.exists():
        raise SystemExit(f"知识库不存在: {wiki}")

    (domain / "WIKI-SCHEMA.md").write_text(render_schema(), encoding="utf-8")
    (domain / "raw" / "视频文件").mkdir(parents=True, exist_ok=True)
    (domain / "raw" / "图片文件").mkdir(parents=True, exist_ok=True)
    (domain / "raw" / "文档文件").mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (wiki / cat).mkdir(parents=True, exist_ok=True)

    notes = []
    moved = 0
    touched = 0
    for md in sorted(wiki.rglob("*.md")):
        if md.name in {"index.md", "log.md", "WIKI-SCHEMA.md"}:
            continue
        text = md.read_text(encoding="utf-8")
        meta, body = read_frontmatter(text)
        title = meta.get("title") or md.stem
        category = choose_category(title, meta.get("category", md.parent.name))
        text = write_frontmatter(text, category)
        text = re.sub(r">\s*\*.+?类(视频|笔记)\s*·", f"> *{category}类\\1 ·", text, count=1)
        text = ensure_ai_reference(text, {**meta, "title": title}, category)

        target = wiki / category / md.name
        if md.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}_{datetime.now().strftime('%H%M%S')}{target.suffix}")
            target.write_text(text, encoding="utf-8")
            md.unlink()
            moved += 1
            note_path = target
        else:
            md.write_text(text, encoding="utf-8")
            note_path = md
        touched += 1
        notes.append({
            "category": category,
            "name": note_path.stem,
            "summary": extract_summary(read_frontmatter(text)[1]),
            "duration": meta.get("duration", ""),
            "date": meta.get("created", meta.get("date", "")) or datetime.now().strftime("%Y-%m-%d"),
            "badge": "[手动] " if meta.get("source_type") == "manual" else "",
        })

    for legacy in LEGACY_DIRS:
        if legacy in CATEGORIES:
            continue
        path = wiki / legacy
        if path.exists() and path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    rewrite_index(vault, notes)
    log = wiki / "log.md"
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n## [{datetime.now().strftime('%Y-%m-%d')}] migrate | 10 分类目录与 AI快速参考升级\n\n")
        f.write(f"- 迁移/检查笔记：{touched} 篇\n- 移动到新目录：{moved} 篇\n- 分类体系：10 个目录栏\n")

    script = Path(__file__).parent / "regenerate_dashboard.py"
    subprocess.run([sys.executable, str(script), "--vault", str(vault)], check=True)
    print(f"✅ 迁移完成: {vault}")
    print(f"   笔记检查: {touched} | 移动: {moved}")


if __name__ == "__main__":
    main()

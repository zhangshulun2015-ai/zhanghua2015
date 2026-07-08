"""
本地文件一键入库。

把 PDF、Word、表格、PPT、图片、txt/md 提取为标准知识库笔记：
文件 -> extract_document.py -> note_data.json -> add_note.py -> Dashboard。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from extract_document import IMAGE_EXTS, extract_file
from knowledge_schema import CATEGORIES, DOMAIN_DIR, normalize_category
from vault_config import resolve_vault_path, save_vault_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SOURCE_LABELS = {
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

CATEGORY_KEYWORDS = {
    "质量控制资料": ["iso", "qc", "质量", "检验", "审核", "流程", "工厂", "体系", "标准", "改善"],
    "文学资料": ["小说", "散文", "诗歌", "文学", "写作", "叙事", "人物", "作品", "评论"],
    "AI教程资料": ["ai", "gpt", "模型", "自动化", "工作流", "教程", "生成式", "智能体", "agent"],
    "视频解说资料": ["解说", "口播", "分镜", "脚本", "账号", "爆款", "影视", "短视频"],
    "提示词专项资料": ["prompt", "提示词", "seedance", "midjourney", "mj", "镜头", "角色设定"],
    "工具与效率": ["obsidian", "工具", "效率", "软件", "办公", "剪辑", "系统", "方法"],
    "商业与运营": ["商业", "运营", "营销", "产品", "变现", "案例", "增长", "销售"],
    "认知与方法论": ["学习", "认知", "思维", "方法论", "成长", "表达", "决策", "复盘"],
    "素材与案例库": ["素材", "案例", "样片", "参考", "拆解", "风格"],
}


def safe_name(text: str, max_len: int = 80) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", text).strip()[:max_len] or "未命名文档"


def guess_category(text: str) -> str:
    lower = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(lower.count(k.lower()) for k in keywords)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "其他"


def make_summary(text: str, title: str, source_label: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if compact:
        limit = 180
        if len(compact) <= limit:
            return compact
        window = compact[:limit]
        cut_points = [window.rfind(mark) for mark in ("。", "；", ";", ".", "！", "？")]
        cut = max(cut_points)
        if cut >= 40:
            return window[:cut + 1]
        return window.rstrip() + "..."
    return f"{source_label}《{title}》已入库，正文需要后续补充或 OCR。"


def copy_source_file(source: Path, vault: Path) -> Path:
    raw_root = vault / DOMAIN_DIR / "raw"
    if source.suffix.lower() in IMAGE_EXTS:
        dst_dir = raw_root / "图片文件"
    else:
        dst_dir = raw_root / "文档文件"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / source.name
    if dst.exists():
        stem = dst.stem
        suffix = dst.suffix
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = dst_dir / f"{stem}_{stamp}{suffix}"
    shutil.copy2(source, dst)
    return dst


def render_content(data: dict, archived_file: Path | None) -> str:
    source_label = SOURCE_LABELS.get(data.get("source_type"), data.get("source_type", "本地文件"))
    parts = [
        "## 来源文件",
        "",
        f"- 文件名：{data.get('file_name', '')}",
        f"- 文件类型：{source_label}",
        f"- 原始路径：`{data.get('file_path', '')}`",
    ]
    if archived_file:
        parts.append(f"- 知识库归档：`{archived_file}`")
    if data.get("page_count"):
        parts.append(f"- 页数/页码：{data.get('page_count')}")
    if data.get("warnings"):
        parts.append("")
        parts.append("## 提取提示")
        parts.extend(f"- {w}" for w in data["warnings"])

    text = data.get("text") or ""
    if text.strip():
        parts.extend(["", "## 提取正文", "", text.strip()])
    else:
        parts.extend(["", "## 提取正文", "", "（未提取到正文。若为扫描 PDF 或图片，请安装 OCR 依赖后重试。）"])

    tables = data.get("tables") or []
    if tables:
        parts.extend(["", "## 表格内容"])
        for table in tables:
            parts.extend(["", table])

    return "\n".join(parts).strip()


def build_note_data(data: dict, category: str | None, tags: list[str], archived_file: Path | None) -> dict:
    source_label = SOURCE_LABELS.get(data.get("source_type"), data.get("source_type", "本地文件"))
    title = safe_name(data.get("title") or Path(data.get("file_name", "未命名文档")).stem)
    combined_text = "\n".join([data.get("text", ""), "\n".join(data.get("tables", []))])
    final_category = normalize_category(category) if category else guess_category(title + "\n" + combined_text)
    summary = make_summary(combined_text, title, source_label)
    content = render_content(data, archived_file)
    base_tags = [source_label, data.get("file_ext", "").lstrip(".")]
    final_tags = [t for t in base_tags + tags if t]

    questions = [
        f"{title} 的核心内容是什么？",
        f"{title} 中有哪些可直接引用的结论？",
        f"{title} 适合用于哪些工作场景？",
    ]
    conclusions = [summary] if summary else []
    key_terms = final_tags[:8]
    use_cases = ["资料整理", "AI投喂", "知识库检索"]

    return {
        "title": title,
        "category": final_category,
        "summary": summary,
        "content": content,
        "knowledge_points": [
            {
                "title": "文档提取要点",
                "concept": f"从{source_label}中提取正文、表格和可投喂 AI 的上下文。",
                "points": [
                    f"来源文件：{data.get('file_name', '')}",
                    f"正文长度：{data.get('text_length', 0)} 字",
                    f"表格数量：{len(data.get('tables', []))}",
                ],
            }
        ],
        "tags": final_tags,
        "quotes": [],
        "notes": "本笔记由本地文件入库脚本自动生成，可继续追加人工理解、金句和案例。",
        "source_type": data.get("source_type", "document"),
        "source": str(archived_file or data.get("file_path", "")),
        "ai_questions": questions,
        "ai_conclusions": conclusions,
        "key_terms": key_terms,
        "use_cases": use_cases,
        "ai_refs": [str(archived_file)] if archived_file else [],
    }


def run_add_note(vault: Path, note_json: Path) -> None:
    script = Path(__file__).resolve().parent / "add_note.py"
    result = subprocess.run(
        [sys.executable, str(script), "--vault", str(vault), "--input", str(note_json)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)
        raise SystemExit(result.returncode)
    if result.stderr:
        print(result.stderr)


def parse_tags(text: str) -> list[str]:
    if not text:
        return []
    return [t.strip() for t in re.split(r"[,，、]", text) if t.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF/Word/表格/PPT/图片/txt/md 一键入库")
    parser.add_argument("file", help="本地文件路径")
    parser.add_argument("--vault", default=None, help="知识库根路径；未提供时读取配置")
    parser.add_argument("--category", default="", help=f"分类，可选：{', '.join(CATEGORIES)}")
    parser.add_argument("--tags", default="", help="额外标签，逗号分隔")
    parser.add_argument("--ocr", choices=["auto", "always", "never"], default="auto", help="OCR 策略")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="Tesseract OCR 语言")
    parser.add_argument("--no-copy", action="store_true", help="不复制原文件到 raw/")
    parser.add_argument("--keep-json", action="store_true", help="保留中间 extraction/note JSON")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)
    source = Path(args.file).expanduser().resolve()

    print(f"\n{'='*50}")
    print(f"📄 本地文件入库: {source.name}")
    print(f"{'='*50}\n")

    data = extract_file(source, ocr=args.ocr, ocr_lang=args.ocr_lang)
    archived_file = None if args.no_copy else copy_source_file(source, vault)
    note_data = build_note_data(data, args.category or None, parse_tags(args.tags), archived_file)

    work_dir = vault / DOMAIN_DIR / "raw" / "_document_ingest"
    work_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extraction_json = work_dir / f"{safe_name(source.stem)}_{stamp}.extraction.json"
    note_json = work_dir / f"{safe_name(source.stem)}_{stamp}.note.json"
    extraction_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    note_json.write_text(json.dumps(note_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 提取类型: {data.get('source_type')} | 正文 {data.get('text_length', 0)} 字 | 表格 {len(data.get('tables', []))}")
    if archived_file:
        print(f"  ✅ 原文件归档: {archived_file}")
    if data.get("warnings"):
        print("  ⚠️ 提取提示:")
        for warning in data["warnings"]:
            print(f"     - {warning}")

    run_add_note(vault, note_json)

    if not args.keep_json:
        for p in (extraction_json, note_json):
            try:
                p.unlink()
            except OSError:
                pass

    print(f"\n{'='*50}")
    print("✅ 本地文件入库完成")
    print(f"   标题: {note_data['title']}")
    print(f"   分类: {note_data['category']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

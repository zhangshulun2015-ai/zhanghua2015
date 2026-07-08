"""
删除知识笔记 — 将指定笔记移到知识库回收站

移动 .md 文件到 .trash/notes/，更新 index.md（移除对应行），追加 log.md（记录删除），刷新 Dashboard。

Usage:
  python delete_note.py --vault "<你的知识库路径>" --file "<你的知识库路径>\\图文视频知识库\\wiki\\AI教程资料\\笔记标题.md"

  也可以只传标题：
  python delete_note.py --vault "<你的知识库路径>" --title "笔记标题"
"""
import os, sys, re, argparse, subprocess
from pathlib import Path
from datetime import datetime
from vault_config import resolve_vault_path, save_vault_path

DOMAIN_DIR = "图文视频知识库"


def find_note_by_title(vault: Path, title: str) -> Path | None:
    """按标题模糊匹配查找笔记文件。"""
    wiki_dir = vault / DOMAIN_DIR / "wiki"
    if not wiki_dir.exists():
        return None

    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
    # 精确匹配
    for md in wiki_dir.rglob("*.md"):
        if md.name in ('index.md', 'log.md'):
            continue
        if md.stem == safe_title or md.stem == title:
            return md
    # 模糊匹配
    for md in wiki_dir.rglob("*.md"):
        if md.name in ('index.md', 'log.md'):
            continue
        if title in md.stem or md.stem in title:
            return md
    return None


def update_index_remove(vault: Path, note_path: Path):
    """从 index.md 中移除对应笔记行。"""
    index_path = vault / DOMAIN_DIR / "wiki" / "index.md"
    if not index_path.exists():
        return

    content = index_path.read_text(encoding='utf-8')
    stem = note_path.stem

    # 移除包含该笔记标题的表格行
    lines = content.split('\n')
    new_lines = []
    removed = 0
    for line in lines:
        if stem in line and ('|' in line) and ('[[' in line or '[手动]' in line):
            removed += 1
            continue
        new_lines.append(line)

    new_content = '\n'.join(new_lines)
    today = datetime.now().strftime("%Y-%m-%d")
    new_content = re.sub(r'最后更新\*\*：\d{4}-\d{2}-\d{2}', f'最后更新**：{today}', new_content)
    index_path.write_text(new_content, encoding='utf-8')
    if removed:
        print(f"  ✅ index.md 移除了 {removed} 行")


def append_log_delete(vault: Path, note_title: str):
    """追加删除日志。"""
    log_path = vault / DOMAIN_DIR / "wiki" / "log.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"""
## [{today}] delete | {note_title}

- 操作：移到回收站
- 删除时间：{today}
"""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f"  ✅ log.md 已记录删除")


def move_to_trash(vault: Path, note_path: Path) -> Path:
    """Move a note under wiki/ to .trash/notes/, preserving its category path."""
    wiki_dir = (vault / DOMAIN_DIR / "wiki").resolve()
    resolved_note = note_path.resolve()
    if not str(resolved_note).lower().startswith(str(wiki_dir).lower()):
        raise ValueError("只能删除 wiki/ 目录内的笔记")
    if resolved_note.suffix.lower() != ".md":
        raise ValueError("只能删除 Markdown 笔记")
    if resolved_note.name in {"index.md", "log.md", "WIKI-SCHEMA.md"}:
        raise ValueError("系统笔记不能删除")

    rel_parent = resolved_note.parent.relative_to(wiki_dir)
    trash_dir = vault / DOMAIN_DIR / ".trash" / "notes" / rel_parent
    trash_dir.mkdir(parents=True, exist_ok=True)
    target = trash_dir / resolved_note.name
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = trash_dir / f"{resolved_note.stem}_{stamp}{resolved_note.suffix}"

    resolved_note.replace(target)
    return target


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
    parser = argparse.ArgumentParser(description="删除知识笔记")
    parser.add_argument("--vault", default=None, help="Obsidian 仓库根路径；未提供时读取 VIDEO_KNOWLEDGE_VAULT 或 config.json")
    parser.add_argument("--file", help="笔记文件完整路径")
    parser.add_argument("--title", help="笔记标题（模糊匹配）")
    args = parser.parse_args()

    vault = resolve_vault_path(args.vault)
    save_vault_path(vault)

    # 确定要删除的文件
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

    note_title = note_path.stem

    print(f"\n{'='*50}")
    print(f"🗑️ 移到回收站: {note_title}")
    print(f"   路径: {note_path}")
    print(f"{'='*50}\n")

    # 1. 移到回收站
    trash_path = move_to_trash(vault, note_path)
    print(f"  ✅ 已移到回收站: {trash_path}")

    # 2. 更新 index.md
    update_index_remove(vault, note_path)

    # 3. 追加日志
    append_log_delete(vault, note_title)

    # 4. 刷新 Dashboard
    print(f"\n  🔄 刷新 Dashboard...")
    regenerate_dashboard(vault)

    print(f"\n{'='*50}")
    print(f"✅ 笔记已移到回收站!")
    print(f"   🗑️ {note_title}")
    print(f"   🌐 index.html 已刷新")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

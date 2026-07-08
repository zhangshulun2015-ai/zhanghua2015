"""Shared schema for 图文视频知识库 中文专享版."""
from __future__ import annotations

from datetime import datetime

DOMAIN = "图文视频知识库"
DOMAIN_DIR = "图文视频知识库"
VERSION_LABEL = "图文视频知识库 v4.0 中文专享版（张华制作）"

CATEGORY_DEFS = [
    ("质量控制资料", "ISO、QC七大手法、质量体系、工厂管理、检验标准、流程改善"),
    ("文学资料", "小说、散文、诗歌、写作技巧、文学评论、人物作品分析"),
    ("AI教程资料", "AI工具教程、模型使用、工作流、自动化、图像/视频/音频AI教程"),
    ("视频解说资料", "影视解说、文案结构、口播脚本、账号拆解、爆款叙事"),
    ("提示词专项资料", "Prompt、Seedance提示词、MJ提示词、角色设定、镜头语言、提示词模板"),
    ("工具与效率", "Obsidian、剪辑工具、办公软件、效率系统、知识库方法"),
    ("商业与运营", "变现、账号运营、产品、营销、商业案例"),
    ("认知与方法论", "学习方法、思维模型、个人成长、表达、决策"),
    ("素材与案例库", "可复用案例、参考视频、风格样片、拆解素材"),
    ("其他", "暂时判断不清的内容，后续人工整理"),
]

CATEGORIES = [name for name, _ in CATEGORY_DEFS]

LEGACY_CATEGORY_MAP = {
    "AI技术资料": "AI教程资料",
    "质量管理资料": "质量控制资料",
    "AI视频脚本学习": "视频解说资料",
    "文学文献": "文学资料",
    "一般软件学习": "工具与效率",
    "社会热点": "商业与运营",
    "工具与效率": "工具与效率",
    "认知与思维": "认知与方法论",
    "技术与编程": "AI教程资料",
    "生活与成长": "认知与方法论",
    "软件工具资料": "工具与效率",
    "认知方法资料": "认知与方法论",
    "项目案例资料": "素材与案例库",
    "其他": "其他",
}


def normalize_category(category: str | None) -> str:
    """Return a v3.0 category, mapping old v2.0 names when needed."""
    if category in CATEGORIES:
        return category
    return LEGACY_CATEGORY_MAP.get(category or "", "其他")


def build_ai_reference(data: dict) -> dict:
    """Create an AI quick-reference payload from analysis or manual-note data."""
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
    questions = data.get("ai_questions") or data.get("suitable_questions") or []
    conclusions = data.get("ai_conclusions") or data.get("quotable_conclusions") or []
    terms = data.get("key_terms") or data.get("keywords") or tags[:8]
    scenarios = data.get("use_cases") or data.get("scenarios") or data.get("audience") or []
    refs = data.get("ai_refs") or data.get("cross_refs") or []

    def as_list(value):
        if not value:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [line.strip("- \t") for line in str(value).splitlines() if line.strip("- \t")]

    if not conclusions:
        summary = data.get("summary") or data.get("core_content") or data.get("content") or ""
        conclusions = [summary] if summary else []

    return {
        "questions": as_list(questions),
        "conclusions": as_list(conclusions),
        "terms": as_list(terms),
        "scenarios": as_list(scenarios),
        "refs": as_list(refs),
    }


def render_ai_reference(data: dict) -> str:
    ref = build_ai_reference(data)

    def line(label: str, values: list[str]) -> str:
        text = "；".join(values) if values else "（待补充）"
        return f"- {label}：{text}"

    return "\n".join([
        "## 🤖 AI快速参考",
        "",
        line("适合回答的问题", ref["questions"]),
        line("可直接引用的结论", ref["conclusions"]),
        line("关键术语", ref["terms"]),
        line("适用场景", ref["scenarios"]),
        line("关联资料", ref["refs"]),
    ])


def render_schema() -> str:
    categories_tree = "\n".join(f"    ├── {name}/" for name in CATEGORIES[:-1])
    categories_tree += f"\n    └── {CATEGORIES[-1]}/"
    category_table = "\n".join(f"| {name} | {keywords} |" for name, keywords in CATEGORY_DEFS)
    return f"""# WIKI-SCHEMA — {VERSION_LABEL}规范

## 仓库结构

```
{DOMAIN_DIR}/
├── WIKI-SCHEMA.md      ← 本文件（架构规范）
├── raw/                 ← 不可变层（原始素材）
│   ├── 视频文件/       ← 原始视频与缩略图
│   ├── 图片文件/       ← 本地图片与图文素材
│   └── 文档文件/       ← PDF、Word、表格、PPT、txt/md 原文件
└── wiki/               ← AI 维护层
    ├── index.md         ← 总目录（自动更新）
    ├── log.md           ← 操作日志（自动追加）
{categories_tree}
```

## 分类规则

| 分类 | 匹配关键词 |
|------|-----------|
{category_table}

## AI快速参考规则

每条笔记必须在正文靠前位置包含 `## 🤖 AI快速参考`，用于投喂 AI 时快速复制短上下文。

推荐字段：
- 适合回答的问题
- 可直接引用的结论
- 关键术语
- 适用场景
- 关联资料

## 操作原则

- `raw/` 保留原始素材，只追加，不随笔记删除自动清空。
- `wiki/` 放结构化笔记，默认使用 10 个目录栏。
- Dashboard 默认优先展示摘要、AI快速参考、标签和路径，完整转录只在需要追溯原文时读取。
- 每次 ingest 后自动更新 index.md、log.md 和 Dashboard。

---
*遵循 Karpathy LLM Wiki 方法论 · v4.0*
"""


def render_index(notes_count: int = 0) -> str:
    cat_sections = "\n\n".join(
        f"## {cat}\n\n| # | 笔记 | 摘要 | 时长 | 日期 |\n|---|------|------|------|------|\n| — | 暂无 | — | — | — |"
        for cat in CATEGORIES
    )
    return f"""# {VERSION_LABEL} — 总目录

> 本文件由 AI 自动维护。优先按 10 个目录栏组织资料，并为 AI 投喂保留短摘要入口。

---

{cat_sections}

---

## 统计

- **总笔记数**：{notes_count}
- **总视频时长**：—
- **知识点总数**：0
- **最后更新**：{datetime.now().strftime('%Y-%m-%d')}

---

*由 [video-knowledge] Skill 自动维护 · 遵循 [[../WIKI-SCHEMA]]*
"""

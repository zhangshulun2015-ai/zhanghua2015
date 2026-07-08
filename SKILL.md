---
name: video-knowledge
description: "Process video links, local videos, PDFs, Word documents, spreadsheets, PPTs, images, text/Markdown files, image-text posts, or manual notes into 图文视频知识库 v4.0 中文专享版（张华制作）: download or ingest media, extract text/tables/OCR, transcribe speech, generate AI-ready structured notes with AI快速参考, organize into 10 category folders, export Markdown, migrate older vaults, and regenerate a Dashboard with AI投喂/copy features."
---

# 图文视频知识库 Skill

**素材摄入 → 转录/提取 → AI 深度分析 → 结构化笔记 → Dashboard AI投喂**

内部名称继续使用 `video-knowledge`；面向用户、Dashboard 和文档统一称为 **图文视频知识库 v4.0 中文专享版（张华制作）**。

英文用户入口：查看 `README_EN.md`。本版可以处理英文素材，但 Dashboard、目录栏和笔记结构默认保持中文；如果需要纯英文体验，应单独维护英文版。

## 核心目标

这个知识库同时服务两件事：

1. 用户自己在工作和账号运营中快速查资料。
2. 把整理好的资料短而准地投喂给 AI，让 AI 快速参考、引用和进入上下文。

因此不要只保存完整转录。每篇笔记必须优先产出：分类、标签、一句话摘要、核心内容、知识点、适用场景、可直接引用结论、本地文件路径和 `AI快速参考`。

## 启动与路径规则

首次使用、换电脑、或当前对话没有明确知识库路径时，先询问知识库根目录。根目录通常是包含 `index.html` 的目录；如果用户给的是 `图文视频知识库` 子目录，脚本会自动归一。

所有脚本调用都使用：

```bash
python scripts/configure_vault.py "<知识库根路径>"
```

或在每次命令中传：

```bash
--vault "<知识库根路径>"
```

不要写死用户目录、盘符或电脑专属路径。已配置路径失效时，必须重新询问用户。

## v4.0 目录栏

所有新笔记必须归入以下 10 类之一。旧分类由脚本自动映射到新目录。

| 目录栏 | 适用内容 |
|---|---|
| 质量控制资料 | ISO、QC七大手法、质量体系、工厂管理、检验标准、流程改善 |
| 文学资料 | 小说、散文、诗歌、写作技巧、文学评论、人物作品分析 |
| AI教程资料 | AI工具教程、模型使用、工作流、自动化、图像/视频/音频AI教程 |
| 视频解说资料 | 影视解说、文案结构、口播脚本、账号拆解、爆款叙事 |
| 提示词专项资料 | Prompt、Seedance提示词、MJ提示词、角色设定、镜头语言、提示词模板 |
| 工具与效率 | Obsidian、剪辑工具、办公软件、效率系统、知识库方法 |
| 商业与运营 | 变现、账号运营、产品、营销、商业案例 |
| 认知与方法论 | 学习方法、思维模型、个人成长、表达、决策 |
| 素材与案例库 | 可复用案例、参考视频、风格样片、拆解素材 |
| 其他 | 暂时判断不清的内容，后续人工整理 |

## AI 快速参考

每篇 v4.0 笔记正文靠前位置必须包含：

```markdown
## 🤖 AI快速参考

- 适合回答的问题：
- 可直接引用的结论：
- 关键术语：
- 适用场景：
- 关联资料：
```

当用户让 AI 基于知识库回答、找资料、整理资料或投喂资料时：

1. 先读 `图文视频知识库/wiki/index.md` 和相关分类目录。
2. 优先读取标题、分类、标签、摘要、`AI快速参考`、核心内容、知识点和本地路径。
3. 只有用户明确要求完整原文或转录时，才读取完整转录。
4. 输出资料包使用：资料标题、路径、摘要、关键结论、适用场景、相关标签。

## 工作流

### 1. 网络视频入库

```bash
python scripts/download_video.py <URL> [-o 自定义文件名]
python scripts/transcribe.py <视频路径> [-m small|medium] -o <输出目录>
python scripts/export_to_obsidian.py <transcript.txt> --vault <知识库根路径> --analysis analysis.json --video <视频路径>
python scripts/regenerate_dashboard.py --vault <知识库根路径>
```

支持抖音、B站、小红书、YouTube、X。抖音依赖 Playwright 拦截视频流；其他平台优先用 yt-dlp 和 Chrome Cookie。

### 2. 本地视频快捷入库

用户给出 `.mp4/.mov/.mkv/.webm/.avi` 等本地视频时，不要下载，直接转录：

```bash
python scripts/transcribe.py "<本地视频路径>" -o "<输出目录>"
python scripts/export_to_obsidian.py "<transcript.txt>" --vault "<知识库根路径>" --analysis analysis.json --video "<本地视频路径>"
python scripts/regenerate_dashboard.py --vault "<知识库根路径>"
```

导出时会把视频复制到 `图文视频知识库/raw/视频文件/`。硬盘紧张时，让用户在 Dashboard 点“删除本地视频”；该操作只删本地视频，不删笔记、缩略图或图片素材。

### 3. 图文帖入库

当链接只有文字和图片、没有视频时：

```bash
python scripts/extract_post.py <URL>
```

然后读取 `extraction.json` 做 AI 深度分析，生成 `analysis.json`，再走导出和刷新 Dashboard。

### 4. 手动添加笔记

```bash
python scripts/add_note.py --vault <知识库根路径> \
  --title "标题" \
  --category "AI教程资料" \
  --summary "一句话摘要" \
  --content "核心内容" \
  --kp '[{"title":"知识点","concept":"概念","points":["要点1"]}]' \
  --tags '["标签1","标签2"]'
```

也可以使用 Dashboard 右上角“添加笔记”表单。新笔记会自动刷新 Dashboard。

### 5. 本地文档入库

用户给出 PDF、Word、表格、PPT、图片、txt 或 md 文件时，优先走文档入库流程：

```bash
python scripts/ingest_document.py "<本地文件路径>" --vault "<知识库根路径>" --ocr auto
```

支持格式：
- PDF：文字 PDF 直接提取；扫描版 PDF 在 OCR 依赖可用时自动识别。
- Word：`.docx` 段落和表格。
- 表格：`.xlsx`、`.csv` 转 Markdown 表格。
- PPT：`.pptx` 幻灯片文本、表格、备注；老 `.ppt` 建议先另存为 `.pptx`。
- 图片：`.jpg/.png/.webp/.bmp/.tif` 在 OCR 依赖可用时提取图片文字。
- 文本：`.txt/.md` 直接入库。

底层提取命令为：

```bash
python scripts/extract_document.py "<本地文件路径>" --ocr auto
```

`ingest_document.py` 会复制原文件到 `图文视频知识库/raw/文档文件/`，图片复制到 `raw/图片文件/`，再生成标准笔记、更新 index/log 并刷新 Dashboard。

OCR 是可选增强能力。若缺少 Tesseract、pytesseract、Poppler 等依赖，普通文字 PDF、Word、表格、PPT、txt/md 仍可正常入库；扫描 PDF 和图片 OCR 会在笔记中提示需要安装 OCR。

换电脑或给别人安装时，必须提醒：扫描 PDF/图片 OCR 需要额外安装 Tesseract OCR、中文语言包 `chi_sim`、Python 包 `pytesseract` 和 Poppler。若 Windows 用户名含中文，建议把语言包和 Poppler 放到纯英文路径，例如 `C:\Tesseract-OCR\tessdata` 与 `C:\Poppler\bin`。

### 6. 追加、删除、恢复

追加内容：

```bash
python scripts/append_note.py --vault <知识库根路径> --file "<笔记完整路径>" --content "补充文字"
```

删除笔记：

```bash
python scripts/delete_note.py --vault <知识库根路径> --file "<笔记完整路径>"
```

删除会移动到 `.trash/notes/`，Dashboard 回收站支持恢复。视频和图片素材默认不随笔记删除。

### 7. v3.0 迁移

升级旧知识库时运行：

```bash
python scripts/migrate_v3.py --vault "<知识库根路径>"
```

迁移会重写 `WIKI-SCHEMA.md`、创建 10 个目录栏、把旧分类映射到新分类、给旧笔记补 `AI快速参考`、重建 `wiki/index.md` 并刷新 `index.html`。

## AI 深度分析要求

生成 `analysis.json` 时至少包含：

```json
{
  "title": "标题",
  "category": "AI教程资料",
  "tags": ["标签"],
  "summary": "50字以内摘要",
  "audience": "适用人群",
  "core_content": "核心内容",
  "concepts_table": "| 工具 | 说明 |\\n|---|---|",
  "steps": "操作步骤",
  "knowledge_points": "知识点 Markdown",
  "golden_quotes": ["金句"],
  "cross_refs": ["相关笔记"],
  "ai_questions": ["适合回答的问题"],
  "ai_conclusions": ["可直接引用的结论"],
  "key_terms": ["关键术语"],
  "use_cases": ["适用场景"],
  "link": "源链接",
  "duration": "时长",
  "source_type": "douyin|bilibili|xiaohongshu|youtube|x"
}
```

英文原句后紧跟中文翻译；中文文本补全标点；金句使用 Markdown 引用块或 JSON 数组，导出脚本会统一处理。

## Dashboard v4.0

`scripts/regenerate_dashboard.py --vault <知识库根路径>` 会生成 `index.html`。Dashboard 支持：

- 10 个目录栏筛选。
- 卡片、列表、AI参考三种视图。
- “复制当前筛选给AI”。
- “按目录投喂”。
- “按主题投喂”。
- 单篇笔记“复制给AI”。
- 本地视频空间提醒和“删除本地视频”。
- 本地文件入库命令生成入口。
- 回收站查看与恢复。

## 依赖

```bash
pip install faster-whisper playwright yt-dlp pdfplumber python-docx openpyxl pandas python-pptx pillow pdf2image pytesseract
python -m playwright install-deps
```

还需要 Chrome 和 ffmpeg。Chrome 用于 Cookie/登录态，ffmpeg 用于音频提取和缩略图。扫描 PDF/图片 OCR 还需要额外安装 Tesseract OCR；PDF 转图片 OCR 可能需要 Poppler。

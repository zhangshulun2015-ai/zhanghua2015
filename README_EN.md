# Visual Video Knowledge Base v4.0 Chinese Edition

This skill is a Chinese-first personal knowledge-base workflow created by Zhang Hua.

It can still process English videos, English articles, and mixed-language material. The default vault structure, Dashboard labels, note sections, and AI feeding fields are in Chinese because this edition is optimized for Chinese users.

## What It Does

- Ingest video links, local video files, PDFs, Word documents, spreadsheets, PPTs, images, text/Markdown files, image-text posts, and manual notes.
- Transcribe speech with local Whisper tooling.
- Extract text, tables, slide notes, and optional OCR text before turning the material into structured Markdown notes.
- Organize notes into 10 Chinese categories.
- Generate a local Dashboard with search, category filters, and one-click AI feeding.
- Copy a short AI-ready context package for each note instead of copying full transcripts.

## For English Users

Use this edition if you are comfortable with a Chinese Dashboard and Chinese note schema.

You can ask the AI assistant to keep English content in one of these modes:

```text
Use $video-knowledge to ingest this English video.
Keep the original English transcript, and write the summary and AI quick reference in Chinese.
```

```text
Use $video-knowledge to ingest this English video.
Keep the original English transcript, and write the summary, tags, and AI quick reference bilingually.
```

```text
Use $video-knowledge to ingest this English article.
Generate a Chinese note, but preserve important English terms and quotes.
```

## Category Mapping

The 10 categories are intentionally Chinese:

- 质量控制资料: quality control, ISO, factory management, inspection standards
- 文学资料: fiction, essays, poetry, writing craft, literary criticism
- AI教程资料: AI tools, model usage, workflows, automation, image/video/audio AI tutorials
- 视频解说资料: video narration, scripts, account breakdowns, viral storytelling
- 提示词专项资料: prompts, Seedance prompts, Midjourney prompts, character setup, shot language
- 工具与效率: Obsidian, editing tools, office software, productivity systems, knowledge methods
- 商业与运营: monetization, account operations, products, marketing, business cases
- 认知与方法论: learning methods, mental models, personal growth, expression, decision-making
- 素材与案例库: reusable cases, reference videos, style samples, breakdown materials
- 其他: unclear items for later manual sorting

## Recommended English Workflow

1. Configure the vault path:

```bash
python scripts/configure_vault.py "<vault-root>"
```

2. Ingest a local video:

```bash
python scripts/transcribe.py "<video-file>" -o "<output-folder>"
python scripts/export_to_obsidian.py "<transcript.txt>" --vault "<vault-root>" --analysis analysis.json --video "<video-file>"
python scripts/regenerate_dashboard.py --vault "<vault-root>"
```

3. Ingest a local document:

```bash
python scripts/ingest_document.py "<local-file>" --vault "<vault-root>" --ocr auto
```

Supported formats: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.pptx`, common image files, `.txt`, and `.md`. Legacy `.ppt` files should be saved as `.pptx` first.

4. Open:

```text
<vault-root>/index.html
```

## If You Need a Native English Version

Create a separate English edition instead of changing this Chinese edition in place.

Suggested name:

```text
Visual Video Knowledge Base v4.0
```

Suggested folder/repo name:

```text
video-knowledge-en
```

That version should use English categories, English Dashboard labels, and English note templates.

# v4.0 Setup Guide

Use this reference when configuring or migrating a local vault.

## Configure

```bash
python scripts/configure_vault.py "<vault root>"
```

The vault root is the folder containing `index.html`.

## Migrate

```bash
python scripts/migrate_v3.py --vault "<vault root>"
```

Migration creates the 10 category folders, rewrites `WIKI-SCHEMA.md`, adds `AI快速参考` to existing notes, rebuilds `wiki/index.md`, and regenerates `index.html`.

## v4.0 Folders

- 质量控制资料
- 文学资料
- AI教程资料
- 视频解说资料
- 提示词专项资料
- 工具与效率
- 商业与运营
- 认知与方法论
- 素材与案例库
- 其他

## Local Document Ingest

```bash
python scripts/ingest_document.py "<local-file>" --vault "<vault root>" --ocr auto
```

Supported formats: PDF, DOCX, XLSX, CSV, PPTX, common image files, TXT, and Markdown.

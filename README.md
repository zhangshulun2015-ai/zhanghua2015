# 图文视频知识库 v4.0 中文专享版

把视频链接、本地视频、PDF、Word、表格、PPT、图片、txt/md 和手动笔记整理成一个本地 Markdown 知识库，并生成可搜索、可筛选、可一键投喂 AI 的 Dashboard。

> 中文专享版，默认使用中文目录栏、中文笔记结构和中文 Dashboard。

## 主要能力

- 10 个目录栏：质量控制资料、文学资料、AI教程资料、视频解说资料、提示词专项资料、工具与效率、商业与运营、认知与方法论、素材与案例库、其他。
- 每篇笔记自动生成 `AI快速参考`，方便复制给 AI。
- Dashboard 支持搜索、目录筛选、标签筛选、卡片/列表/AI参考视图。
- 支持单篇“投喂AI”、当前筛选投喂、按目录投喂、按主题投喂。
- 本地文件入库支持 PDF、扫描 PDF OCR、Word `.docx`、Excel/CSV、PPT `.pptx`、图片 OCR、txt、md。
- 支持本地视频和网络视频转录入库。

## 平台验证结论

- 小红书：公开视频不用登录，直接分享链接可下载视频或提取图文。
- B站：公开视频不用登录，直接复制链接可下载。
- 抖音：已验证可用；遇到登录、滑块或风控验证时，需要先在浏览器完成。
- X：已验证可用；公开内容可尝试直接提取，登录可见内容需要 Cookie。

## 安装依赖

基础依赖：

```bash
pip install faster-whisper playwright yt-dlp pdfplumber python-docx openpyxl pandas python-pptx pillow pdf2image pytesseract
python -m playwright install-deps
```

还需要：

- Chrome：用于登录态/Cookie。
- ffmpeg：用于视频音频提取和缩略图。
- Tesseract OCR：用于扫描 PDF 和图片文字识别。
- Poppler：用于把扫描 PDF 转成图片再 OCR。

Windows 可参考：

```powershell
winget install --id tesseract-ocr.tesseract
winget install --id oschwartz10612.Poppler
```

中文 OCR 需要 `chi_sim.traineddata`。如果 Windows 用户名包含中文，建议把语言包和 Poppler 放到纯英文路径，例如：

```text
C:\Tesseract-OCR\tessdata
C:\Poppler\bin
```

## 配置知识库路径

第一次使用先配置本地知识库根目录：

```bash
python scripts/configure_vault.py "<你的知识库根路径>"
```

知识库根目录是存放 `index.html` 的目录。脚本会自动创建：

- `图文视频知识库/WIKI-SCHEMA.md`
- `图文视频知识库/wiki/`
- `图文视频知识库/raw/视频文件/`
- `图文视频知识库/raw/图片文件/`
- `图文视频知识库/raw/文档文件/`

## 本地文件入库

```bash
python scripts/ingest_document.py "<本地文件路径>" --vault "<你的知识库根路径>" --ocr auto
```

支持：

- `.pdf`
- `.docx`
- `.xlsx`
- `.csv`
- `.pptx`
- `.jpg/.png/.webp/.bmp/.tif`
- `.txt`
- `.md`

老版 `.ppt` 建议先另存为 `.pptx`。

## 视频入库

本地视频：

```bash
python scripts/transcribe.py "<本地视频路径>" -o "<输出目录>"
python scripts/export_to_obsidian.py "<transcript.txt>" --vault "<你的知识库根路径>" --analysis analysis.json --video "<本地视频路径>"
python scripts/regenerate_dashboard.py --vault "<你的知识库根路径>"
```

网络视频：

```bash
python scripts/download_video.py "<视频链接>"
python scripts/transcribe.py "<视频路径>" -o "<输出目录>"
python scripts/export_to_obsidian.py "<transcript.txt>" --vault "<你的知识库根路径>" --analysis analysis.json --video "<视频路径>"
python scripts/regenerate_dashboard.py --vault "<你的知识库根路径>"
```

## 手动添加笔记

```bash
python scripts/add_note.py --vault "<你的知识库根路径>" --title "标题" --category "工具与效率" --summary "摘要" --content "正文"
```

## 刷新 Dashboard

```bash
python scripts/regenerate_dashboard.py --vault "<你的知识库根路径>"
```

生成的网页在：

```text
<你的知识库根路径>\index.html
```

## 不要提交到 Git 的内容

仓库已通过 `.gitignore` 排除：

- `config.json`：本机知识库路径配置。
- `scripts/videos/`：本地视频缓存。
- `__pycache__/` 和 `*.pyc`。
- 本机开发交接文档。

## English Users

See `README_EN.md`.

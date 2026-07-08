# 图文视频知识库 v4.0 中文专享版（张华制作）操作指南

## 一句话

把视频、图文帖、本地文档、图片和手动资料变成可检索、可引用、可投喂 AI 的本地知识库。

## 处理顺序

```text
素材/链接/本地视频/本地文件
  -> 下载或直接读取
  -> 转码/音频提取
  -> 转录/提取文字/提取表格/OCR
  -> AI 深度分析
  -> 生成带 AI快速参考 的 Markdown
  -> 刷新 Dashboard
```

## 自动知识库识别

AI助手会先确认知识库根路径。若知识库不存在，脚本会自动创建 `wiki/`、`raw/`、`WIKI-SCHEMA.md`、`index.md`、`log.md` 和 10 个分类目录。

## 链接视频处理

收到视频链接后，流程为：识别平台 -> 抓取/下载视频 -> 转码或提取音频 -> 转录文字 -> AI 总结提炼 -> 导出笔记 -> 刷新 Dashboard。

导出笔记时默认原样保留转录文本；AI 语义校对稿或人工整理稿不要再二次自动断句。只有原始单行稿需要初步整理时，才使用 `--format-transcript`。长视频默认在笔记中展示 AI 语义整理稿，并挂上完整字幕文件链接；Dashboard 提供“全文投喂AI”复制完整字幕给 AI。只有明确要求全文展示时，才把逐字完整版直接写入笔记。

处理 X 链接时，先检查 `duration`、`formats`、`subtitles` 等元数据；如果有视频时长或视频格式，就按视频入库。只有确认没有视频时，才按图文帖提取文字和图片。

## 本地文件处理

收到 PDF、Word、表格、PPT、图片、txt 或 md 文件后，流程为：识别文件类型 -> 提取正文/表格/备注/OCR -> 归档原文件 -> 生成结构化笔记 -> 刷新 Dashboard。

```bash
python scripts/ingest_document.py "<本地文件路径>" --vault "<知识库根路径>" --ocr auto
```

支持 `.pdf`、`.docx`、`.xlsx`、`.csv`、`.pptx`、`.jpg/.png/.webp`、`.txt`、`.md`。老 `.ppt` 建议先另存为 `.pptx`。

## OCR 换电脑提醒

扫描 PDF 和图片文字识别不是 Python 脚本单独能完成的，换电脑要安装：

- Tesseract OCR
- 中文语言包 `chi_sim`
- Python 包 `pytesseract`
- PDF 转图片工具 Poppler

本机已配置纯英文路径：

- `C:\Tesseract-OCR\tessdata`
- `C:\Poppler\bin`

如果新电脑用户名也是中文，建议继续用纯英文路径放语言包和 Poppler，避免 OCR 找不到文件。

## 10 个目录栏

质量控制资料、文学资料、AI教程资料、视频解说资料、提示词专项资料、工具与效率、商业与运营、认知与方法论、素材与案例库、其他。

## 常用命令

配置知识库：

```bash
python scripts/configure_vault.py "<知识库根路径>"
```

迁移旧库到 v3.0：

```bash
python scripts/migrate_v3.py --vault "<知识库根路径>"
```

刷新 Dashboard：

```bash
python scripts/regenerate_dashboard.py --vault "<知识库根路径>"
```

手动添加：

```bash
python scripts/add_note.py --vault "<知识库根路径>" --title "标题" --category "素材与案例库" --summary "摘要" --content "内容"
```

本地文件入库：

```bash
python scripts/ingest_document.py "<本地文件路径>" --vault "<知识库根路径>" --ocr auto
```

## 给 AI 使用

优先让 AI 读取：

- `图文视频知识库/wiki/index.md`
- 相关分类目录下的笔记
- 每篇笔记的 `## 🤖 AI快速参考`
- 本地文件路径

只有需要追溯原文时再读完整转录。

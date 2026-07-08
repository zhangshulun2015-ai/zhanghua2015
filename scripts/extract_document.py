"""
本地文档内容提取层。

支持：
- PDF：文字 PDF；扫描 PDF 可选 OCR。
- Word：.docx 段落与表格。
- 表格：.xlsx / .csv。
- PPT：.pptx 幻灯片文本、表格、备注。
- 图片：jpg/png/webp/bmp/tiff 可选 OCR。
- 文本：.txt / .md。

输出统一 JSON，供 ingest_document.py 或 AI 深度分析继续使用。
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEXT_EXTS = {".txt", ".md"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTS = TEXT_EXTS | IMAGE_EXTS | {".pdf", ".docx", ".xlsx", ".csv", ".pptx"}
DEFAULT_TESSDATA_DIR = Path("C:/Tesseract-OCR/tessdata")
DEFAULT_POPPLER_BIN = Path("C:/Poppler/bin")
TESSERACT_CANDIDATES = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
]


def optional_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def configure_tesseract(pytesseract_module) -> None:
    """Make OCR work even when the current terminal PATH was not refreshed."""
    if not pytesseract_module:
        return
    for candidate in TESSERACT_CANDIDATES:
        if candidate.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(candidate)
            break
    else:
        found = shutil.which("tesseract")
        if found:
            pytesseract_module.pytesseract.tesseract_cmd = found

    if DEFAULT_TESSDATA_DIR.exists() and "TESSDATA_PREFIX" not in os.environ:
        os.environ["TESSDATA_PREFIX"] = str(DEFAULT_TESSDATA_DIR)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def table_to_markdown(rows: list[list[Any]], max_rows: int = 120) -> str:
    cleaned: list[list[str]] = []
    for row in rows:
        values = ["" if cell is None else str(cell).replace("\n", " ").strip() for cell in row]
        if any(values):
            cleaned.append(values)
    if not cleaned:
        return ""

    width = max(len(row) for row in cleaned)
    normalized = [row + [""] * (width - len(row)) for row in cleaned[:max_rows]]
    header = normalized[0]
    body = normalized[1:] or [[""] * width]

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"

    lines = [fmt(header), "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend(fmt(row) for row in body)
    if len(cleaned) > max_rows:
        lines.append(f"\n> 表格过长，已截取前 {max_rows} 行，原表共 {len(cleaned)} 行。")
    return "\n".join(lines)


def first_nonempty_line(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip(" #\t")
        if line:
            return line[:80]
    return fallback


def extract_text_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "source_type": "markdown" if path.suffix.lower() == ".md" else "text",
        "title": first_nonempty_line(text, path.stem),
        "text": clean_text(text),
        "tables": [],
        "sections": [],
        "warnings": [],
    }


def extract_pdf(path: Path, ocr: str, ocr_lang: str) -> dict:
    warnings: list[str] = []
    text_parts: list[str] = []
    tables: list[str] = []
    page_count = 0

    pdfplumber = optional_import("pdfplumber")
    if not pdfplumber:
        warnings.append("缺少 pdfplumber，无法提取文字 PDF。")
    else:
        try:
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"## 第 {i} 页\n\n{page_text.strip()}")
                    for table in page.extract_tables() or []:
                        md = table_to_markdown(table)
                        if md:
                            tables.append(f"### PDF 第 {i} 页表格\n\n{md}")
        except Exception as exc:
            warnings.append(f"PDF 文字提取失败：{exc}")

    text = clean_text("\n\n".join(text_parts))
    needs_ocr = ocr == "always" or (ocr == "auto" and len(text) < 80)
    source_type = "pdf"

    if needs_ocr:
        ocr_text, ocr_warnings = ocr_pdf(path, ocr_lang)
        warnings.extend(ocr_warnings)
        if ocr_text.strip():
            source_type = "pdf_ocr"
            text = clean_text((text + "\n\n" + ocr_text).strip())

    if not text and ocr != "never":
        warnings.append("未提取到有效正文；如果这是扫描版 PDF，请安装 Tesseract OCR 与 Poppler 后重试。")

    return {
        "source_type": source_type,
        "title": path.stem,
        "text": text,
        "tables": tables,
        "sections": [],
        "page_count": page_count,
        "warnings": warnings,
    }


def ocr_pdf(path: Path, ocr_lang: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    pdf2image = optional_import("pdf2image")
    pytesseract = optional_import("pytesseract")
    if not pdf2image or not pytesseract:
        return "", ["扫描 PDF OCR 需要安装 pdf2image、pytesseract、Tesseract OCR 和 Poppler。"]
    configure_tesseract(pytesseract)
    try:
        kwargs = {"dpi": 200}
        if DEFAULT_POPPLER_BIN.exists():
            kwargs["poppler_path"] = str(DEFAULT_POPPLER_BIN)
        pages = pdf2image.convert_from_path(str(path), **kwargs)
    except Exception as exc:
        return "", [f"PDF 转图片失败，可能缺少 Poppler：{exc}"]

    parts = []
    for i, image in enumerate(pages, 1):
        try:
            page_text = pytesseract.image_to_string(image, lang=ocr_lang)
            if page_text.strip():
                parts.append(f"## OCR 第 {i} 页\n\n{page_text.strip()}")
        except Exception as exc:
            warnings.append(f"OCR 第 {i} 页失败：{exc}")
    return clean_text("\n\n".join(parts)), warnings


def extract_docx(path: Path) -> dict:
    docx = optional_import("docx")
    if not docx:
        return {
            "source_type": "word",
            "title": path.stem,
            "text": "",
            "tables": [],
            "sections": [],
            "warnings": ["缺少 python-docx，无法提取 Word 文档。"],
        }
    document = docx.Document(str(path))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    tables = []
    for idx, table in enumerate(document.tables, 1):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        md = table_to_markdown(rows)
        if md:
            tables.append(f"### Word 表格 {idx}\n\n{md}")
    text = clean_text("\n\n".join(paragraphs))
    return {
        "source_type": "word",
        "title": first_nonempty_line(text, path.stem),
        "text": text,
        "tables": tables,
        "sections": [],
        "warnings": [],
    }


def extract_xlsx(path: Path) -> dict:
    openpyxl = optional_import("openpyxl")
    if not openpyxl:
        return {
            "source_type": "spreadsheet",
            "title": path.stem,
            "text": "",
            "tables": [],
            "sections": [],
            "warnings": ["缺少 openpyxl，无法提取 Excel 表格。"],
        }
    workbook = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    tables = []
    text_parts = []
    for ws in workbook.worksheets:
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        md = table_to_markdown(rows)
        if md:
            tables.append(f"### 工作表：{ws.title}\n\n{md}")
            text_parts.append(f"{ws.title}：{ws.max_row} 行，{ws.max_column} 列")
    return {
        "source_type": "spreadsheet",
        "title": path.stem,
        "text": "\n".join(text_parts),
        "tables": tables,
        "sections": [],
        "warnings": [],
    }


def extract_csv(path: Path) -> dict:
    warnings: list[str] = []
    rows: list[list[str]] = []
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            warnings.append(f"CSV 读取失败：{exc}")
            break
    md = table_to_markdown(rows)
    return {
        "source_type": "spreadsheet",
        "title": path.stem,
        "text": f"CSV 表格：{len(rows)} 行。",
        "tables": [f"### CSV 表格\n\n{md}"] if md else [],
        "sections": [],
        "warnings": warnings,
    }


def extract_pptx(path: Path) -> dict:
    pptx = optional_import("pptx")
    if not pptx:
        return {
            "source_type": "ppt",
            "title": path.stem,
            "text": "",
            "tables": [],
            "sections": [],
            "warnings": ["缺少 python-pptx，无法提取 PPT。"],
        }
    prs = pptx.Presentation(str(path))
    sections = []
    tables = []
    for index, slide in enumerate(prs.slides, 1):
        lines = []
        slide_tables = []
        image_count = 0
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                text = clean_text(shape.text or "")
                if text:
                    lines.append(text)
            if getattr(shape, "has_table", False):
                rows = [[cell.text.strip() for cell in row.cells] for row in shape.table.rows]
                md = table_to_markdown(rows)
                if md:
                    slide_tables.append(md)
            if getattr(shape, "shape_type", None) == 13:
                image_count += 1

        notes = ""
        try:
            if getattr(slide, "has_notes_slide", False):
                notes = clean_text(slide.notes_slide.notes_text_frame.text or "")
        except Exception:
            notes = ""

        title = first_nonempty_line("\n".join(lines), f"第 {index} 页")
        section_text = "\n\n".join(lines)
        if notes:
            section_text += f"\n\n备注：\n{notes}"
        if image_count:
            section_text += f"\n\n图片数量：{image_count}"
        sections.append({"page": index, "title": title, "text": section_text})
        for t_idx, md in enumerate(slide_tables, 1):
            tables.append(f"### PPT 第 {index} 页表格 {t_idx}\n\n{md}")

    text = "\n\n".join(
        f"## 第 {s['page']} 页：{s['title']}\n\n{s['text']}" for s in sections if s.get("text")
    )
    return {
        "source_type": "ppt",
        "title": sections[0]["title"] if sections else path.stem,
        "text": clean_text(text),
        "tables": tables,
        "sections": sections,
        "page_count": len(sections),
        "warnings": [],
    }


def extract_image(path: Path, ocr: str, ocr_lang: str) -> dict:
    warnings: list[str] = []
    text = ""
    source_type = "image"
    if ocr != "never":
        pytesseract = optional_import("pytesseract")
        image_module = optional_import("PIL.Image")
        if not pytesseract or not image_module:
            warnings.append("图片 OCR 需要安装 pytesseract、Pillow 和 Tesseract OCR。")
        else:
            configure_tesseract(pytesseract)
            try:
                image = image_module.open(str(path))
                text = pytesseract.image_to_string(image, lang=ocr_lang, config="--psm 6")
                if text.strip():
                    source_type = "image_ocr"
            except Exception as exc:
                warnings.append(f"图片 OCR 失败：{exc}")

    return {
        "source_type": source_type,
        "title": path.stem,
        "text": clean_text(text),
        "tables": [],
        "sections": [],
        "warnings": warnings,
    }


def extract_file(path: str | Path, ocr: str = "auto", ocr_lang: str = "chi_sim+eng") -> dict:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"暂不支持的文件类型：{ext}")

    if ext in TEXT_EXTS:
        data = extract_text_file(file_path)
    elif ext == ".pdf":
        data = extract_pdf(file_path, ocr, ocr_lang)
    elif ext == ".docx":
        data = extract_docx(file_path)
    elif ext == ".xlsx":
        data = extract_xlsx(file_path)
    elif ext == ".csv":
        data = extract_csv(file_path)
    elif ext == ".pptx":
        data = extract_pptx(file_path)
    elif ext in IMAGE_EXTS:
        data = extract_image(file_path, ocr, ocr_lang)
    else:
        raise ValueError(f"暂不支持的文件类型：{ext}")

    data.update({
        "file_path": str(file_path),
        "file_name": file_path.name,
        "file_ext": ext,
        "text_length": len(data.get("text", "")),
    })
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="提取 PDF/Word/表格/PPT/图片/txt/md 内容")
    parser.add_argument("file", help="本地文件路径")
    parser.add_argument("-o", "--output", help="输出 JSON 路径；默认输出到文件同目录 extraction.json")
    parser.add_argument("--ocr", choices=["auto", "always", "never"], default="auto", help="OCR 策略")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="Tesseract OCR 语言，例如 chi_sim+eng")
    args = parser.parse_args()

    data = extract_file(args.file, ocr=args.ocr, ocr_lang=args.ocr_lang)
    input_path = Path(args.file)
    out = Path(args.output) if args.output else input_path.with_name(input_path.name + ".extraction.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 提取完成：{data['file_name']}")
    print(f"   类型：{data['source_type']} | 正文：{data.get('text_length', 0)} 字 | 表格：{len(data.get('tables', []))}")
    if data.get("warnings"):
        print("   提示：")
        for warning in data["warnings"]:
            print(f"   - {warning}")
    print(f"   输出：{out}")


if __name__ == "__main__":
    main()

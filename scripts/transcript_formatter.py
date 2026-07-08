"""
Transcript readability helpers.

Whisper Chinese transcripts often lack punctuation and may produce long segments.
These helpers keep the raw wording, split by common Chinese spoken-discourse
markers, add conservative terminal punctuation, and wrap text for notes.
"""
from __future__ import annotations

import re


SENTENCE_ENDINGS = tuple("。！？!?；;：:.")
EDGE_PUNCTUATION = " \t\r\n，,、；;：:。！？!?."
QUESTION_HINTS = [
    "吗", "呢", "为什么", "怎么", "怎样", "如何", "什么", "哪个", "哪一个",
    "哪种", "哪类", "是不是", "能不能", "要不要", "难道", "对吧", "对不对",
]
STRONG_BREAK_MARKERS = [
    "第一招", "第二招", "第三招", "第四招",
    "第一步", "第二步", "第三步", "第四步",
    "第一个", "第二个", "第三个",
    "首先", "然后", "最后", "但是", "所以", "那么", "比如",
    "这里", "好那", "好我们", "我们来看", "我们再看",
    "正确写法", "错误写法", "核心原则", "具体怎么做", "具体表现",
    "本期视频", "我们正式开始", "换一个思路", "原理讲完了",
    "今天我", "这个问题", "他们怎么解决的", "不要小看", "你想想",
    "当你的 Skill", "当你的skill",
]
SOFT_BREAK_MARKERS = [
    "结果", "老板说", "不是", "而是", "其实", "当", "如果", "因为", "也就是说",
    "这就像", "你看", "大家看", "我们以前", "很多人", "模型会",
    "用户问", "用户说", "模型看到", "它会", "这一步", "这句话",
    "这套逻辑", "区别只是", "本质上", "换句话说",
]


def normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def looks_like_question(text: str) -> bool:
    cleaned = normalize_spaces(text)
    if not cleaned:
        return False
    if cleaned.endswith(("？", "?")):
        return True
    if cleaned.endswith(("吗", "呢", "对吧", "对不对", "是不是", "能不能", "要不要")):
        return True
    if re.search(r"(是不是|能不能|要不要|对不对).{0,14}$", cleaned):
        return True
    if re.search(r"(为什么|怎么|怎样|如何|什么|哪[个种类]?).{0,18}(呢|吗|的)$", cleaned):
        return True
    return bool(re.search(r"^(为什么|怎么|怎样|如何|什么|哪[个种类]?|能不能|要不要).{0,42}(呢|吗|的)?$", cleaned))


def add_terminal_punctuation(text: str) -> str:
    cleaned = normalize_spaces(text)
    if not cleaned:
        return ""
    if cleaned.endswith(SENTENCE_ENDINGS):
        return cleaned
    if looks_like_question(cleaned):
        return f"{cleaned}？"
    return f"{cleaned}。"


def split_before_markers(text: str, markers: list[str]) -> list[str]:
    chunks = [normalize_spaces(text)]
    for marker in sorted(markers, key=len, reverse=True):
        next_chunks: list[str] = []
        for chunk in chunks:
            if not chunk:
                continue
            pieces = chunk.split(marker)
            if len(pieces) == 1:
                next_chunks.append(chunk)
                continue
            if pieces[0].strip():
                next_chunks.append(pieces[0].strip())
            for piece in pieces[1:]:
                rebuilt = f"{marker}{piece}".strip()
                if rebuilt:
                    next_chunks.append(rebuilt)
        chunks = next_chunks
    return [chunk for chunk in chunks if chunk]


def best_cut_position(text: str, max_chars: int) -> int:
    search_start = max(8, int(max_chars * 0.25))
    search_end = min(len(text), max_chars)
    best = -1
    for marker in sorted(SOFT_BREAK_MARKERS, key=len, reverse=True):
        idx = text.rfind(marker, search_start, search_end)
        if idx > best:
            best = idx
    if best > search_start:
        return best

    for punct in "，,、；;：:":
        idx = text.rfind(punct, search_start, search_end)
        if idx > best:
            best = idx + 1
    if best > search_start:
        return best
    return len(text)


def split_long_chunk(text: str, max_chars: int = 56) -> list[str]:
    """Split a chunk by Chinese spoken syntax, falling back to length limits."""
    cleaned = normalize_spaces(text)
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [add_terminal_punctuation(cleaned)]

    parts: list[str] = []
    rest = cleaned
    while len(rest) > max_chars:
        cut = best_cut_position(rest, max_chars)
        chunk = rest[:cut].strip(EDGE_PUNCTUATION)
        if chunk:
            parts.append(add_terminal_punctuation(chunk))
        rest = rest[cut:].strip(EDGE_PUNCTUATION)

    if rest:
        parts.append(add_terminal_punctuation(rest))
    return parts


def split_long_line(text: str, max_chars: int = 56) -> list[str]:
    """Split one transcript segment using Chinese discourse markers first."""
    cleaned = normalize_spaces(text)
    if not cleaned:
        return []

    output: list[str] = []
    for strong_chunk in split_before_markers(cleaned, STRONG_BREAK_MARKERS):
        for chunk in split_long_chunk(strong_chunk, max_chars=max_chars):
            output.append(chunk)
    return output


def format_transcript_lines(lines: list[str], max_chars: int = 56) -> str:
    """Format Whisper segment texts into readable transcript paragraphs."""
    output: list[str] = []
    for raw_line in lines:
        cleaned = normalize_spaces(raw_line)
        if not cleaned:
            continue
        output.extend(split_long_line(cleaned, max_chars=max_chars))

    return "\n".join(output)


def format_transcript_text(text: str, max_chars: int = 56) -> str:
    """Format an existing transcript string; safe to call before note export."""
    source_lines = [line for line in re.split(r"[\r\n]+", str(text or "")) if line.strip()]
    if len(source_lines) <= 1:
        source_lines = [str(text or "")]
    return format_transcript_lines(source_lines, max_chars=max_chars)

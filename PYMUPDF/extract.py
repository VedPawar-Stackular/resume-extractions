"""
PyMuPDF (raw) — Resume Extraction Baseline Script
===================================================
Tool:    PyMuPDF (import pymupdf / fitz)
Version: 1.24.0+
Repo:    resume-extraction-eval / 04_pymupdf/

What this script does
---------------------
This is the BASELINE tool. It runs PyMuPDF at the raw level — directly calling
page.get_text("dict") to access every span's font name, font size, bold/italic
flags, bounding box, and text content.

It produces TWO outputs per resume:

  1. RAW mode  — plain text exactly as PyMuPDF returns it, zero post-processing.
                 This is the floor: what you get with one line of code.

  2. INFERRED mode — we reconstruct heading structure ourselves using font size
                     frequency analysis and bold flag detection, then emit proper
                     Markdown. This shows what you'd build without pymupdf4llm.

Having both outputs lets you see:
  a) How bad the raw output is without any processing  (RAW)
  b) How much you can recover with ~100 lines of logic (INFERRED)
  c) How much pymupdf4llm adds on top of that          (compare with 03_pymupdf4llm)

Supported formats
-----------------
  Native PDF   — full raw + inferred extraction
  Scanned PDF  — detected and flagged; raw text will be empty (no built-in OCR)
  DOCX / images — not supported; flagged with clear error

Usage
-----
  python extract.py path/to/resume.pdf
  python extract.py path/to/folder/
  python extract.py path/to/folder/ --verbose   # show span-level debug info
"""

import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

try:
    import pymupdf
except ImportError:
    print("[ERROR] PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR     = Path(__file__).parent / "outputs"
METRICS_FILE    = Path(__file__).parent / "metrics.json"
SUPPORTED_EXTS  = {".pdf"}
UNSUPPORTED_EXTS = {".docx", ".doc", ".jpg", ".jpeg", ".png"}
EMPTY_THRESHOLD = 80
VERBOSE = "--verbose" in sys.argv

# Font flag bitmasks (from PyMuPDF docs)
FLAG_ITALIC     = 1 << 1   # bit 1
FLAG_BOLD       = 1 << 4   # bit 4 (also check font name for "Bold")


# ── PDF type detection ────────────────────────────────────────────────────────
def detect_pdf_type(path: Path) -> str:
    try:
        doc = pymupdf.open(str(path))
        types = []
        for page in doc:
            chars = len(page.get_text().strip())
            types.append("native" if chars > 30 else "scanned")
        doc.close()
        unique = set(types)
        if unique == {"native"}:  return "native"
        if unique == {"scanned"}: return "scanned"
        return "mixed"
    except Exception as e:
        return f"error:{e}"


# ── Span-level extraction via dict mode ───────────────────────────────────────
def extract_spans(path: Path) -> tuple[list[dict], dict]:
    """
    Extract every text span from every page using get_text("dict").

    Returns:
        spans     : flat list of span dicts with text + metadata
        page_meta : {page_num: {width, height, block_count}}

    Each span dict:
        {
          page, block_num, line_num, span_num,
          text, font, size, is_bold, is_italic,
          color, bbox: (x0, y0, x1, y1)
        }
    """
    doc = pymupdf.open(str(path))
    all_spans = []
    page_meta = {}

    for page_num, page in enumerate(doc):
        page_meta[page_num] = {
            "width":       page.rect.width,
            "height":      page.rect.height,
            "block_count": 0,
        }

        # sort=True: top-left → bottom-right reading order
        data = page.get_text(
            "dict",
            sort=True,
            flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES,
        )

        page_meta[page_num]["block_count"] = len(data.get("blocks", []))

        for block in data.get("blocks", []):
            if block.get("type") != 0:   # skip image blocks
                continue
            for li, line in enumerate(block.get("lines", [])):
                for si, span in enumerate(line.get("spans", [])):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    flags    = span.get("flags", 0)
                    font     = span.get("font", "")
                    size     = round(span.get("size", 0), 1)
                    is_bold  = bool(flags & FLAG_BOLD) or "bold" in font.lower()
                    is_italic = bool(flags & FLAG_ITALIC) or "italic" in font.lower() or "oblique" in font.lower()
                    color    = span.get("color", 0)

                    all_spans.append({
                        "page":      page_num,
                        "block_num": block.get("number", 0),
                        "line_num":  li,
                        "span_num":  si,
                        "text":      text,
                        "font":      font,
                        "size":      size,
                        "is_bold":   is_bold,
                        "is_italic": is_italic,
                        "color":     color,
                        "bbox":      list(span.get("bbox", [])),
                    })

    doc.close()
    return all_spans, page_meta


# ── Heading inference from font metadata ──────────────────────────────────────
def infer_heading_map(spans: list[dict]) -> dict[float, str]:
    """
    Analyse font size frequency across all spans.
    The most common size = body text.
    Larger sizes get mapped to # heading levels (up to 3 levels).

    Returns: {font_size: markdown_prefix}
    e.g. {14.0: '# ', 12.0: '## ', 10.0: ''}
    """
    size_counter = Counter(s["size"] for s in spans if s["text"].strip())
    if not size_counter:
        return {}

    # Body = most frequent size
    body_size = size_counter.most_common(1)[0][0]

    # Sizes strictly larger than body, sorted descending
    larger_sizes = sorted(
        [sz for sz in size_counter if sz > body_size],
        reverse=True
    )

    heading_levels = ["# ", "## ", "### "]
    heading_map = {body_size: ""}

    for i, sz in enumerate(larger_sizes[:3]):
        heading_map[sz] = heading_levels[i]

    return heading_map


# ── Build outputs ─────────────────────────────────────────────────────────────
def build_raw_text(path: Path) -> str:
    """
    Absolute raw extraction — get_text("text") with sort.
    Zero post-processing. The honest floor.
    """
    doc = pymupdf.open(str(path))
    pages = []
    for page in doc:
        pages.append(page.get_text("text", sort=True))
    doc.close()
    return "\n".join(pages)


def build_inferred_markdown(spans: list[dict], heading_map: dict) -> str:
    """
    Reconstruct Markdown from span data using our inferred heading map.
    Groups spans by (page, block_num, line_num) → lines → blocks → markdown.
    """
    if not spans:
        return ""

    # Group spans into lines: key = (page, block_num, line_num)
    from itertools import groupby
    lines_out = []
    prev_block = None

    def line_key(s):
        return (s["page"], s["block_num"], s["line_num"])

    def block_key(s):
        return (s["page"], s["block_num"])

    for bk, block_spans in groupby(spans, key=block_key):
        block_lines = []
        for lk, line_spans in groupby(list(block_spans), key=line_key):
            line_parts = []
            for span in line_spans:
                text = span["text"]
                # Apply bold/italic markdown
                if span["is_bold"] and span["is_italic"]:
                    text = f"***{text}***"
                elif span["is_bold"]:
                    text = f"**{text}**"
                elif span["is_italic"]:
                    text = f"*{text}*"
                line_parts.append(text)

            line_text = " ".join(line_parts).strip()
            if line_text:
                block_lines.append(line_text)

        if not block_lines:
            continue

        # Determine heading level for this block
        # Use the dominant font size of this block's spans
        block_span_list = [s for s in spans if block_key(s) == bk]
        dominant_size = Counter(s["size"] for s in block_span_list).most_common(1)[0][0]
        prefix = heading_map.get(dominant_size, "")

        # Combine lines in block
        block_text = " ".join(block_lines)

        # Add blank line before headings for readability
        if prefix:
            lines_out.append(f"\n{prefix}{block_text}")
        else:
            lines_out.append(block_text)

    return "\n".join(lines_out)


# ── Core extraction entry ─────────────────────────────────────────────────────
def extract_resume(file_path: Path) -> dict:
    ext = file_path.suffix.lower()

    result = {
        "file":               file_path.name,
        "format":             ext,
        "pdf_type":           None,
        "tool":               "pymupdf_raw",
        "tool_version":       pymupdf.__version__,
        "extracted_at":       datetime.now(timezone.utc).isoformat(),
        "duration_seconds":   None,
        # RAW output
        "raw_text":           "",
        "raw_char_count":     0,
        "raw_line_count":     0,
        # INFERRED markdown output
        "inferred_markdown":  "",
        "inferred_char_count": 0,
        "inferred_heading_count": 0,
        # Span metadata
        "span_count":         0,
        "unique_font_sizes":  [],
        "body_font_size":     None,
        "heading_map":        {},
        "page_count":         0,
        "warnings":           [],
        "error":              None,
    }

    if ext in UNSUPPORTED_EXTS:
        result["error"] = (
            f"{ext.upper()} is not supported by raw PyMuPDF. "
            "DOCX → use MarkItDown. Images → use Marker or MinerU."
        )
        return result

    if ext != ".pdf":
        result["error"] = f"Unsupported extension: {ext}"
        return result

    pdf_type = detect_pdf_type(file_path)
    result["pdf_type"] = pdf_type

    if pdf_type in ("scanned", "mixed"):
        result["warnings"].append(
            f"PDF type '{pdf_type}' — scanned pages have no text layer. "
            "Raw PyMuPDF has NO built-in OCR. Those pages will be empty. "
            "Use pymupdf4llm (with Tesseract) or Marker for scanned support."
        )

    t_start = time.perf_counter()
    try:
        # 1. Raw text (zero processing)
        raw_text = build_raw_text(file_path)

        # 2. Span-level extraction for inferred markdown
        spans, page_meta = extract_spans(file_path)

        # 3. Heading inference
        heading_map = infer_heading_map(spans)

        # 4. Inferred markdown
        inferred_md = build_inferred_markdown(spans, heading_map)

    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.perf_counter() - t_start, 4)
        return result

    result["duration_seconds"] = round(time.perf_counter() - t_start, 4)

    # Store outputs
    result["raw_text"]       = raw_text
    result["raw_char_count"] = len(raw_text)
    result["raw_line_count"] = len(raw_text.splitlines())

    result["inferred_markdown"]     = inferred_md
    result["inferred_char_count"]   = len(inferred_md)
    inferred_lines = inferred_md.splitlines()
    result["inferred_heading_count"] = sum(1 for l in inferred_lines if l.startswith("#"))

    result["span_count"]        = len(spans)
    result["page_count"]        = len(page_meta)
    result["heading_map"]       = {str(k): v for k, v in heading_map.items()}
    result["unique_font_sizes"] = sorted(set(s["size"] for s in spans), reverse=True)

    size_counter = Counter(s["size"] for s in spans)
    result["body_font_size"] = size_counter.most_common(1)[0][0] if size_counter else None

    _run_quality_checks(result, spans, inferred_md)

    if VERBOSE:
        _print_span_debug(spans, heading_map)

    return result


# ── Quality checks ────────────────────────────────────────────────────────────
def _run_quality_checks(result: dict, spans: list[dict], md: str) -> None:
    if result["raw_char_count"] < EMPTY_THRESHOLD:
        result["warnings"].append(
            f"Raw output near-empty ({result['raw_char_count']} chars). "
            "Scanned PDF — no text layer found. OCR required."
        )

    if result["inferred_heading_count"] == 0 and result["raw_char_count"] > EMPTY_THRESHOLD:
        result["warnings"].append(
            "Heading inference found 0 headings. Resume may use uniform font sizes — "
            "IdentifyHeaders (and our inference) depend on font-size contrast."
        )

    if len(result["unique_font_sizes"]) == 1:
        result["warnings"].append(
            f"Only one font size detected ({result['unique_font_sizes'][0]}pt). "
            "Cannot infer heading levels — all text treated as body."
        )

    if "(cid:" in result["raw_text"]:
        result["warnings"].append(
            "CID glyph codes in raw text — embedded custom font has no CMAP. "
            "Affected characters will be unreadable. No fix at the PyMuPDF raw level."
        )


def _print_span_debug(spans: list[dict], heading_map: dict) -> None:
    print("\n  ── Span-level debug (first 10 spans) ──")
    for s in spans[:10]:
        prefix = heading_map.get(s["size"], "body")
        bold_tag = " [BOLD]" if s["is_bold"] else ""
        print(f"  p{s['page']+1} | {s['size']}pt{bold_tag} | {prefix!r:6} | {s['text'][:60]}")
    print(f"  ... {len(spans)} total spans\n")


# ── Output writing ─────────────────────────────────────────────────────────────
def save_outputs(result: dict) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(result["file"]).stem

    # 1. Raw text file — the honest floor
    raw_path = OUTPUTS_DIR / f"{stem}.raw.txt"
    raw_content = _build_raw_file(result)
    raw_path.write_text(raw_content, encoding="utf-8")

    # 2. Inferred markdown file — our manual reconstruction attempt
    md_path = OUTPUTS_DIR / f"{stem}.inferred.md"
    md_path.write_text(_build_md_file(result), encoding="utf-8")

    # 3. Per-file metadata JSON
    meta = {k: v for k, v in result.items() if k not in ("raw_text", "inferred_markdown")}
    meta_path = OUTPUTS_DIR / f"{stem}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # ── Console output ─────────────────────────────────────────────────────
    status = "✗" if result["error"] else ("⚠" if result["warnings"] else "✓")
    print(f"  {status} {result['file']}")
    print(f"    Format     : {result['format']} ({result.get('pdf_type', 'n/a')})")
    print(f"    Time       : {result['duration_seconds']}s")
    print(f"    Raw output : {result['raw_char_count']} chars | {result['raw_line_count']} lines")
    print(f"    Inferred md: {result['inferred_char_count']} chars | {result['inferred_heading_count']} headings")
    print(f"    Font sizes : {result['unique_font_sizes']} (body={result['body_font_size']}pt)")
    print(f"    Heading map: {result['heading_map']}")
    print(f"    Spans      : {result['span_count']} | Pages: {result['page_count']}")
    for w in result["warnings"]:
        print(f"    ⚠  {w}")
    if result["error"]:
        print(f"    ✗  {result['error']}")
    print()


def _build_raw_file(result: dict) -> str:
    header = (
        f"# PyMuPDF RAW Extraction — {result['file']}\n"
        f"# Mode   : get_text('text', sort=True) — zero post-processing\n"
        f"# Format : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}\n"
        f"# Tool   : {result['tool']} {result['tool_version']}\n"
        f"# Time   : {result['duration_seconds']}s | Chars: {result['raw_char_count']}\n"
        f"# NOTE   : This is the FLOOR — raw output with no structure recovery.\n"
        f"#          Compare with .inferred.md for our manual reconstruction.\n"
        f"{'─'*70}\n\n"
    )
    warn_block = ""
    if result["warnings"]:
        warn_block = "\n".join(f"WARNING: {w}" for w in result["warnings"]) + "\n\n"
    err_block = f"ERROR: {result['error']}\n\n" if result["error"] else ""
    content = result["raw_text"] or "(no content extracted)"
    return header + warn_block + err_block + content


def _build_md_file(result: dict) -> str:
    header = (
        f"<!-- PyMuPDF INFERRED Markdown — {result['file']}\n"
        f"     Mode    : Span dict extraction + font-size heading inference\n"
        f"     Format  : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}\n"
        f"     Tool    : {result['tool']} {result['tool_version']}\n"
        f"     Time    : {result['duration_seconds']}s\n"
        f"     Chars   : {result['inferred_char_count']} | Headings: {result['inferred_heading_count']}\n"
        f"     Heading map (size→level): {result['heading_map']}\n"
        f"     NOTE    : Heading structure was inferred from font sizes,\n"
        f"               not provided natively. Compare with 03_pymupdf4llm\n"
        f"               to see what IdentifyHeaders adds.\n"
        f"-->\n\n"
    )
    warn_block = ""
    if result["warnings"]:
        warn_block = "\n".join(f"> ⚠ {w}" for w in result["warnings"]) + "\n\n---\n\n"
    err_block = f"> ✗ {result['error']}\n\n" if result["error"] else ""
    content = result["inferred_markdown"] or "_No content extracted._"
    return header + warn_block + err_block + content


# ── Metrics ────────────────────────────────────────────────────────────────────
def save_metrics(all_results: list[dict]) -> None:
    summary = []
    for r in all_results:
        summary.append({
            "file":                   r["file"],
            "format":                 r["format"],
            "pdf_type":               r.get("pdf_type"),
            "duration_seconds":       r["duration_seconds"],
            "raw_char_count":         r["raw_char_count"],
            "inferred_char_count":    r["inferred_char_count"],
            "inferred_heading_count": r["inferred_heading_count"],
            "span_count":             r["span_count"],
            "unique_font_sizes":      r["unique_font_sizes"],
            "body_font_size":         r["body_font_size"],
            "heading_map":            r["heading_map"],
            "page_count":             r["page_count"],
            "warning_count":          len(r["warnings"]),
            "warnings":               r["warnings"],
            "error":                  r["error"],
            "status": (
                "error" if r["error"] else
                "empty" if r["raw_char_count"] < EMPTY_THRESHOLD else
                "ok"
            ),
        })

    ok  = [s for s in summary if s["status"] == "ok"]
    avg_t = round(sum(s["duration_seconds"] or 0 for s in summary) / max(len(summary), 1), 4)

    metrics = {
        "tool":             "pymupdf_raw",
        "tool_version":     pymupdf.__version__,
        "run_at":           datetime.now(timezone.utc).isoformat(),
        "total_files":      len(all_results),
        "successful":       len(ok),
        "empty_outputs":    sum(1 for s in summary if s["status"] == "empty"),
        "errors":           sum(1 for s in summary if s["status"] == "error"),
        "avg_duration_seconds": avg_t,
        "role_in_eval": (
            "BASELINE — shows what PyMuPDF provides with zero post-processing, "
            "and what our own font-size inference can recover. "
            "pymupdf4llm (03) is built on top of this exact engine."
        ),
        "what_raw_gives_you": [
            "Full text content (native PDFs)",
            "Word-level bounding boxes (bbox per span)",
            "Font name, size, bold/italic flags per span",
            "Reading order control via sort=True",
            "Page dimensions and block structure",
        ],
        "what_raw_does_not_give_you": [
            "Markdown headings (must infer from font sizes yourself)",
            "Markdown tables (must detect from bounding boxes yourself)",
            "OCR for scanned PDFs (must add Tesseract separately)",
            "Multi-column ordering (sort=True helps but is not perfect)",
            "Bold/italic Markdown syntax (must map flags yourself)",
            "DOCX / image support",
        ],
        "files": summary,
    }

    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"📊 Metrics saved → {METRICS_FILE}")
    print(f"   Total: {metrics['total_files']} | OK: {metrics['successful']} | "
          f"Empty: {metrics['empty_outputs']} | Errors: {metrics['errors']}")
    print(f"   Avg time: {avg_t}s")


# ── Entry point ────────────────────────────────────────────────────────────────
def collect_files(target: Path) -> list[Path]:
    all_exts = SUPPORTED_EXTS | UNSUPPORTED_EXTS
    if target.is_file():
        return [target] if target.suffix.lower() in all_exts else []
    files = []
    for ext in all_exts:
        files.extend(target.glob(f"*{ext}"))
        files.extend(target.glob(f"*{ext.upper()}"))
    return sorted(set(files))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        print("Usage: python extract.py <file_or_folder> [--verbose]")
        sys.exit(1)

    target = Path(args[0]).resolve()
    files  = collect_files(target)

    if not files:
        print(f"[ERROR] No supported files found at: {target}")
        sys.exit(1)

    print(f"\n{'='*62}")
    print(f"  PyMuPDF Raw Baseline Extractor")
    print(f"  Target  : {target}")
    print(f"  Files   : {len(files)} resume(s) found")
    print(f"  Engine  : PyMuPDF {pymupdf.__version__}")
    print(f"  Outputs : {OUTPUTS_DIR}")
    print(f"  Modes   : RAW (.raw.txt) + INFERRED (.inferred.md)")
    print(f"{'='*62}\n")

    all_results = []
    for file_path in files:
        result = extract_resume(file_path)
        save_outputs(result)
        all_results.append(result)

    save_metrics(all_results)

    print(f"\n{'='*62}")
    print(f"  Done. Outputs:")
    print(f"    *.raw.txt      — zero-processing floor")
    print(f"    *.inferred.md  — our manual heading reconstruction")
    print(f"    *.meta.json    — span metadata, font map, timing")
    print(f"    metrics.json   — scorecard for compare.py")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
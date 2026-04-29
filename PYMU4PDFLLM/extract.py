"""
pymupdf4llm — Resume Extraction Script
========================================
Tool:    pymupdf4llm (by Artifex / PyMuPDF team)
Version: 0.0.20+
Repo:    resume-extraction-eval / 03_pymupdf4llm/

What this script does
---------------------
Runs pymupdf4llm against one or more resume files and produces:
  - outputs/<stem>.md        : full extracted markdown
  - outputs/<stem>.chunks.json: per-page chunks with metadata
  - outputs/<stem>.meta.json : per-file timing, quality signals, warnings
  - metrics.json             : summary scorecard (read by compare.py)

Why pymupdf4llm is different from MarkItDown
--------------------------------------------
MarkItDown uses pdfminer.six for PDFs — a raw text stripper that loses all
structure. pymupdf4llm reads the actual PDF drawing commands (vectors, fonts,
bounding boxes) and reconstructs semantic structure:

  - Headings detected by font-size mapping (IdentifyHeaders)
  - Multi-column layouts read in correct column order
  - Tables converted to Markdown pipe syntax
  - Bold / italic / code spans preserved
  - Scanned pages automatically OCR'd (Tesseract) — no config needed
  - Page chunks with metadata for RAG pipelines

Supported input formats
-----------------------
  Native PDF   (.pdf with text layer)  — best quality, very fast
  Scanned PDF  (.pdf image-only)       — OCR triggered automatically (needs Tesseract)
  DOCX/XLSX/PPTX                       — only with PyMuPDF Pro (not tested here)
  Images (.jpg/.png)                   — NOT natively supported; flagged & skipped

Usage
-----
  # Single file
  python extract.py path/to/resume.pdf

  # Entire sample folder
  python extract.py ../sample_resumes/

  # With verbose output per page
  python extract.py ../sample_resumes/ --verbose
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# ── pymupdf4llm ──────────────────────────────────────────────────────────────
try:
    import pymupdf4llm
    import pymupdf  # comes bundled with pymupdf4llm
except ImportError:
    print("[ERROR] pymupdf4llm not installed. Run: pip install pymupdf4llm")
    sys.exit(1)

# ── OCR check (Tesseract) ────────────────────────────────────────────────────
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR    = Path(__file__).parent / "outputs"
METRICS_FILE   = Path(__file__).parent / "metrics.json"
SUPPORTED_EXTS = {".pdf"}                # pymupdf4llm natively handles PDFs
IMAGE_EXTS     = {".jpg", ".jpeg", ".png"}  # flagged but not extracted
DOCX_EXTS      = {".docx", ".doc"}      # needs PyMuPDF Pro — flagged
EMPTY_THRESHOLD = 80                    # chars below which output is "empty"
VERBOSE = "--verbose" in sys.argv


# ── Scanned PDF pre-check ────────────────────────────────────────────────────
def detect_pdf_type(path: Path) -> str:
    """
    Returns 'native', 'scanned', or 'mixed'.
    pymupdf4llm handles all three automatically if Tesseract is installed,
    but we log the type for our comparison metrics.
    """
    try:
        doc = pymupdf.open(str(path))
        page_types = []
        for page in doc:
            chars = len(page.get_text().strip())
            page_types.append("native" if chars > 30 else "scanned")
        doc.close()
        unique = set(page_types)
        if unique == {"native"}:
            return "native"
        if unique == {"scanned"}:
            return "scanned"
        return "mixed"
    except Exception as e:
        return f"detection_error:{e}"


# ── Core extraction ───────────────────────────────────────────────────────────
def extract_resume(file_path: Path) -> dict:
    """
    Run pymupdf4llm on one resume file.
    Returns a structured result dict.
    """
    ext = file_path.suffix.lower()

    result = {
        "file":             file_path.name,
        "file_path":        str(file_path),
        "format":           ext,
        "pdf_type":         None,
        "tool":             "pymupdf4llm",
        "tool_version":     pymupdf4llm.__version__ if hasattr(pymupdf4llm, "__version__") else "0.0.20+",
        "tesseract":        TESSERACT_AVAILABLE,
        "extracted_at":     datetime.now(timezone.utc).isoformat(),
        "duration_seconds": None,
        "char_count":       0,
        "line_count":       0,
        "page_count":       0,
        "heading_count":    0,
        "table_count":      0,
        "markdown":         "",
        "chunks":           [],
        "warnings":         [],
        "error":            None,
    }

    # ── Unsupported format gates ──────────────────────────────────────────
    if ext in IMAGE_EXTS:
        result["error"] = (
            "Image files are not directly supported by pymupdf4llm. "
            "Convert to PDF first, or use Marker/MinerU which have native image OCR."
        )
        return result

    if ext in DOCX_EXTS:
        result["error"] = (
            "DOCX requires PyMuPDF Pro (paid). "
            "For this evaluation, DOCX is handled by the MarkItDown and Marker tools."
        )
        return result

    if ext != ".pdf":
        result["error"] = f"Unsupported extension: {ext}"
        return result

    # ── Pre-check PDF type ────────────────────────────────────────────────
    pdf_type = detect_pdf_type(file_path)
    result["pdf_type"] = pdf_type

    if pdf_type in ("scanned", "mixed") and not TESSERACT_AVAILABLE:
        result["warnings"].append(
            f"PDF type is '{pdf_type}' (image-based pages detected) but Tesseract "
            "is not installed. OCR will be skipped — scanned pages will produce empty output. "
            "Install: sudo apt-get install tesseract-ocr"
        )

    # ── Run extraction ────────────────────────────────────────────────────
    t_start = time.perf_counter()
    try:
        # PRIMARY call — full markdown with heading detection + layout analysis
        # IdentifyHeaders maps font sizes → # levels automatically
        md_text: str = pymupdf4llm.to_markdown(
            str(file_path),
            show_progress=False,
            # table_strategy="lines_strict"  # default; catches ruled tables well
        )

        # SECONDARY call — per-page chunks with metadata (for RAG / comparison)
        chunks: list[dict] = pymupdf4llm.to_markdown(
            str(file_path),
            page_chunks=True,
            show_progress=False,
        )

    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.perf_counter() - t_start, 4)
        return result

    result["duration_seconds"] = round(time.perf_counter() - t_start, 4)

    # ── Store results ─────────────────────────────────────────────────────
    result["markdown"]    = md_text
    result["char_count"]  = len(md_text)
    result["line_count"]  = len(md_text.splitlines())
    result["page_count"]  = len(chunks)

    # Count headings (# markers) and table rows (| markers)
    lines = md_text.splitlines()
    result["heading_count"] = sum(1 for l in lines if l.startswith("#"))
    result["table_count"]   = sum(1 for l in lines if l.startswith("|") and "---" not in l)

    # Store lightweight chunk summary (text preview + page metadata)
    result["chunks"] = [
        {
            "page":       i + 1,
            "char_count": len(c.get("text", "")),
            "metadata":   {k: v for k, v in c.items() if k != "text"},
            "preview":    c.get("text", "")[:200].replace("\n", " "),
        }
        for i, c in enumerate(chunks)
    ]

    _run_quality_checks(result, md_text)

    if VERBOSE:
        _print_chunk_preview(result)

    return result


# ── Quality checks ────────────────────────────────────────────────────────────
def _run_quality_checks(result: dict, md: str) -> None:
    """Append meaningful warnings for comparison scoring."""

    # 1. Near-empty output
    if result["char_count"] < EMPTY_THRESHOLD:
        result["warnings"].append(
            f"Output near-empty ({result['char_count']} chars). "
            "Likely a fully scanned PDF without Tesseract installed."
        )

    # 2. No headings — means font-size detection didn't find hierarchy
    if result["heading_count"] == 0 and result["char_count"] > EMPTY_THRESHOLD:
        result["warnings"].append(
            "No Markdown headings detected. Resume may use uniform font sizes "
            "across all sections — IdentifyHeaders needs font-size contrast to "
            "assign # levels. All text may appear as body."
        )

    # 3. Multi-column detection hint
    if "(cid:" in md:
        result["warnings"].append(
            "CID glyph codes detected in output — some characters may be garbled. "
            "This can happen with embedded custom fonts not included in the PDF."
        )

    # 4. Very short output despite native PDF
    if (
        result.get("pdf_type") == "native"
        and EMPTY_THRESHOLD <= result["char_count"] < 400
    ):
        result["warnings"].append(
            "Native PDF yielded unusually short output (<400 chars). "
            "May be a heavily graphic resume where text is inside images."
        )

    # 5. Scanned but Tesseract missing
    if result.get("pdf_type") in ("scanned", "mixed") and not TESSERACT_AVAILABLE:
        result["warnings"].append(
            "Scanned pages will be blank in output — install Tesseract to fix this."
        )


def _print_chunk_preview(result: dict) -> None:
    print(f"\n  ── Page chunks ({result['page_count']} pages) ──")
    for chunk in result["chunks"][:3]:  # show first 3 pages
        print(f"  Page {chunk['page']} ({chunk['char_count']} chars): {chunk['preview'][:100]}...")
    if result["page_count"] > 3:
        print(f"  ... {result['page_count'] - 3} more pages")


# ── Output writing ────────────────────────────────────────────────────────────
def save_outputs(result: dict) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(result["file"]).stem

    # 1. Full markdown output with self-documenting header
    md_path = OUTPUTS_DIR / f"{stem}.md"
    md_path.write_text(_build_md_output(result), encoding="utf-8")

    # 2. Page chunks JSON
    chunks_path = OUTPUTS_DIR / f"{stem}.chunks.json"
    chunks_path.write_text(
        json.dumps(result["chunks"], indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # 3. Per-file metadata (no full markdown — keep it readable)
    meta = {k: v for k, v in result.items() if k not in ("markdown", "chunks")}
    meta_path = OUTPUTS_DIR / f"{stem}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # ── Console summary ───────────────────────────────────────────────────
    status_icon = "✗" if result["error"] else ("⚠" if result["warnings"] else "✓")
    print(f"  {status_icon} {result['file']}")
    print(f"    Format   : {result['format']} ({result.get('pdf_type', 'n/a')})")
    print(f"    Time     : {result['duration_seconds']}s")
    print(f"    Output   : {result['char_count']} chars | {result['line_count']} lines | {result['page_count']} pages")
    print(f"    Headings : {result['heading_count']} | Tables: {result['table_count']} rows")
    print(f"    Tesseract: {'✓ available' if result['tesseract'] else '✗ not installed'}")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"    ⚠  {w}")
    if result["error"]:
        print(f"    ✗  ERROR: {result['error']}")
    print()


def _build_md_output(result: dict) -> str:
    warn_block = ""
    if result["warnings"]:
        warn_block = (
            "\n\n---\n**Extraction Warnings**\n\n"
            + "\n".join(f"> ⚠ {w}" for w in result["warnings"])
            + "\n\n---\n\n"
        )

    err_block = ""
    if result["error"]:
        err_block = f"\n\n---\n**Extraction Error**\n\n> ✗ {result['error']}\n\n---\n\n"

    content = result["markdown"] if result["markdown"] else "_No content extracted._"

    return (
        f"<!-- pymupdf4llm Extraction Output\n"
        f"     File     : {result['file']}\n"
        f"     Format   : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}\n"
        f"     Tool     : {result['tool']} {result['tool_version']}\n"
        f"     Time     : {result['duration_seconds']}s\n"
        f"     Chars    : {result['char_count']} | Headings: {result['heading_count']} | Tables: {result['table_count']}\n"
        f"     Tesseract: {result['tesseract']}\n"
        f"     Extracted: {result['extracted_at']}\n"
        f"-->"
        f"{warn_block}{err_block}\n\n"
        f"{content}\n"
    )


# ── Metrics summary ────────────────────────────────────────────────────────────
def save_metrics(all_results: list[dict]) -> None:
    summary = []
    for r in all_results:
        summary.append({
            "file":             r["file"],
            "format":           r["format"],
            "pdf_type":         r.get("pdf_type"),
            "duration_seconds": r["duration_seconds"],
            "char_count":       r["char_count"],
            "line_count":       r["line_count"],
            "page_count":       r["page_count"],
            "heading_count":    r["heading_count"],
            "table_count":      r["table_count"],
            "has_headings":     r["heading_count"] > 0,
            "has_tables":       r["table_count"] > 0,
            "tesseract":        r["tesseract"],
            "warning_count":    len(r["warnings"]),
            "warnings":         r["warnings"],
            "error":            r["error"],
            "status": (
                "error" if r["error"] else
                "empty" if r["char_count"] < EMPTY_THRESHOLD else
                "ok"
            ),
        })

    ok    = [s for s in summary if s["status"] == "ok"]
    empty = [s for s in summary if s["status"] == "empty"]
    errs  = [s for s in summary if s["status"] == "error"]
    avg_t = round(sum(s["duration_seconds"] or 0 for s in summary) / max(len(summary), 1), 4)

    metrics = {
        "tool":           "pymupdf4llm",
        "tool_version":   summary[0]["status"] and "0.0.20+",
        "run_at":         datetime.now(timezone.utc).isoformat(),
        "tesseract":      TESSERACT_AVAILABLE,
        "total_files":    len(all_results),
        "successful":     len(ok),
        "empty_outputs":  len(empty),
        "errors":         len(errs),
        "avg_duration_seconds": avg_t,
        "avg_heading_count":    round(sum(s["heading_count"] for s in ok) / max(len(ok), 1), 1),
        "avg_table_count":      round(sum(s["table_count"] for s in ok) / max(len(ok), 1), 1),
        "strengths": [
            "Font-size based heading detection (IdentifyHeaders) — real # ## ### in output",
            "Multi-column layout reading in correct order",
            "Table detection → Markdown pipe tables",
            "Automatic hybrid OCR — only pages that need it",
            "Page chunks with metadata for RAG pipelines",
            "Bold / italic / code formatting preserved",
            "No cloud API needed — fully local",
            "Very fast for native PDFs (~0.1s/page)",
        ],
        "limitations": [
            "DOCX/XLSX/PPTX require paid PyMuPDF Pro",
            "Heading detection depends on font-size contrast — uniform-font resumes get no headings",
            "Scanned PDFs require Tesseract installed separately",
            "Custom/embedded fonts may produce CID glyph codes",
            "Image-only resumes (JPG/PNG) not directly supported",
        ],
        "files": summary,
    }

    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"📊 Metrics saved → {METRICS_FILE}")
    print(f"   Total: {metrics['total_files']} | OK: {metrics['successful']} | "
          f"Empty: {metrics['empty_outputs']} | Errors: {metrics['errors']}")
    print(f"   Avg time     : {avg_t}s")
    print(f"   Avg headings : {metrics['avg_heading_count']} | Avg table rows: {metrics['avg_table_count']}")


# ── Entry point ───────────────────────────────────────────────────────────────
def collect_files(target: Path) -> list[Path]:
    all_exts = SUPPORTED_EXTS | IMAGE_EXTS | DOCX_EXTS
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
    print(f"  pymupdf4llm Resume Extractor")
    print(f"  Target    : {target}")
    print(f"  Files     : {len(files)} resume(s) found")
    print(f"  Tesseract : {'✓ available (OCR enabled)' if TESSERACT_AVAILABLE else '✗ not installed (OCR disabled)'}")
    print(f"  Outputs   : {OUTPUTS_DIR}")
    print(f"{'='*62}\n")

    all_results = []
    for file_path in files:
        result = extract_resume(file_path)
        save_outputs(result)
        all_results.append(result)

    save_metrics(all_results)

    print(f"\n{'='*62}")
    print(f"  Done. Check outputs/ for .md, .chunks.json, .meta.json files.")
    print(f"  Compare with other tools using: python ../compare.py")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
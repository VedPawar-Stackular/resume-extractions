"""
MarkItDown — Resume Extraction Script
======================================
Tool:     Microsoft MarkItDown (markitdown[pdf,docx,image])
Version:  0.1.4+
Repo:     resume-extraction-eval / 05_markitdown/

What this script does
---------------------
Runs MarkItDown against one or more resume files and produces:
  - outputs/<stem>.md       : the extracted markdown text
  - outputs/<stem>.meta.json: per-file metadata (timing, detected type, warnings)
  - metrics.json            : summary scorecard across all files

Supported input formats
-----------------------
  Native PDF   (.pdf with text layer)   — uses pdfminer.six internally
  DOCX         (.docx)                   — uses mammoth internally (best quality)
  Images       (.jpg / .jpeg / .png)    — basic extraction; no LLM OCR here
  Scanned PDF  (.pdf image-only)        — DETECTED and flagged; MarkItDown will
                                          produce empty/garbage output, which is
                                          exactly what we want to document.

Usage
-----
  # Single file
  python extract.py path/to/resume.pdf

  # Whole folder of resumes
  python extract.py path/to/resumes/

  # Use shared sample folder from repo root
  python extract.py ../sample_resumes/

Outputs land in: 05_markitdown/outputs/
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# ── MarkItDown ──────────────────────────────────────────────────────────────
try:
    from markitdown import MarkItDown
except ImportError:
    print("[ERROR] MarkItDown not installed. Run: pip install markitdown[pdf,docx,image]")
    sys.exit(1)

# ── PyMuPDF (only for scanned-PDF detection — not for extraction) ────────────
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("[WARN] PyMuPDF not found. Scanned PDF detection disabled. Run: pip install pymupdf")

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR = Path(__file__).parent / "outputs"
METRICS_FILE = Path(__file__).parent / "metrics.json"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png"}

# Minimum character count below which we consider a PDF extraction "empty"
# (catches scanned PDFs that MarkItDown silently returns blank for)
EMPTY_THRESHOLD = 100


# ── Scanned PDF detection ─────────────────────────────────────────────────────
def detect_pdf_type(file_path: Path) -> str:
    """
    Returns one of:
      'native'  — PDF has a proper text layer (MarkItDown can handle it)
      'scanned' — PDF is image-only (MarkItDown will produce empty output)
      'unknown' — PyMuPDF not available, can't check
    """
    if not PYMUPDF_AVAILABLE:
        return "unknown"

    try:
        doc = fitz.open(str(file_path))
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        doc.close()
        return "native" if total_chars >= EMPTY_THRESHOLD else "scanned"
    except Exception as e:
        return f"detection_error: {e}"


# ── Core extraction ───────────────────────────────────────────────────────────
def extract_resume(file_path: Path, md_converter: MarkItDown) -> dict:
    """
    Run MarkItDown on a single resume file.
    Returns a result dict with content + metadata.
    """
    ext = file_path.suffix.lower()
    result = {
        "file": file_path.name,
        "file_path": str(file_path),
        "format": ext,
        "pdf_type": None,
        "tool": "markitdown",
        "tool_version": "0.1.4+",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": None,
        "char_count": 0,
        "line_count": 0,
        "markdown": "",
        "warnings": [],
        "error": None,
    }

    # Pre-check: detect scanned PDFs before wasting time on them
    if ext == ".pdf":
        pdf_type = detect_pdf_type(file_path)
        result["pdf_type"] = pdf_type
        if pdf_type == "scanned":
            result["warnings"].append(
                "Scanned PDF detected (no text layer). MarkItDown will produce "
                "empty output. This is a known limitation — MarkItDown requires "
                "markitdown-ocr plugin + LLM vision client for scanned files."
            )

    # Run extraction and time it
    t_start = time.perf_counter()
    try:
        conversion = md_converter.convert(str(file_path))
        markdown_text = conversion.text_content or ""
    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.perf_counter() - t_start, 4)
        return result
    t_end = time.perf_counter()

    result["duration_seconds"] = round(t_end - t_start, 4)
    result["markdown"] = markdown_text
    result["char_count"] = len(markdown_text)
    result["line_count"] = len(markdown_text.splitlines())

    # Post-extraction quality checks
    _run_quality_checks(result)

    return result


def _run_quality_checks(result: dict) -> None:
    """
    Append warnings for common MarkItDown extraction issues.
    Mutates result["warnings"] in place.
    """
    md = result["markdown"]

    # 1. Near-empty output (scanned PDF or completely garbled)
    if result["char_count"] < EMPTY_THRESHOLD:
        result["warnings"].append(
            f"Output is near-empty ({result['char_count']} chars). "
            "Likely a scanned PDF or unsupported layout."
        )

    # 2. No markdown headings detected (flat output — MarkItDown's PDF weakness)
    if result["format"] == ".pdf" and "# " not in md and "## " not in md:
        result["warnings"].append(
            "No Markdown headings found in PDF output. MarkItDown's pdfminer.six "
            "backend strips heading structure from PDFs. Section detection will be "
            "degraded for the LLM scoring step."
        )

    # 3. No table syntax found (may indicate table extraction failure)
    if "|" not in md and result["char_count"] > EMPTY_THRESHOLD:
        result["warnings"].append(
            "No Markdown table syntax (|) found. If this resume has a skills table "
            "or education grid, it was likely extracted as plain text rows."
        )

    # 4. Very short output for a supposedly native PDF
    if (
        result.get("pdf_type") == "native"
        and result["char_count"] < 500
        and result["char_count"] >= EMPTY_THRESHOLD
    ):
        result["warnings"].append(
            "Native PDF produced unexpectedly short output (<500 chars). "
            "Possible complex layout (multi-column, heavy graphics) confusing pdfminer.six."
        )


# ── Output writing ────────────────────────────────────────────────────────────
def save_outputs(result: dict) -> None:
    """Save the markdown and metadata files for a single result."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(result["file"]).stem

    # Markdown output
    md_path = OUTPUTS_DIR / f"{stem}.md"
    md_content = build_markdown_output(result)
    md_path.write_text(md_content, encoding="utf-8")

    # Per-file metadata JSON (without the full markdown to keep it readable)
    meta = {k: v for k, v in result.items() if k != "markdown"}
    meta_path = OUTPUTS_DIR / f"{stem}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"  ✓ {result['file']}")
    print(f"    Format : {result['format']} ({result.get('pdf_type') or 'n/a'})")
    print(f"    Time   : {result['duration_seconds']}s")
    print(f"    Output : {result['char_count']} chars, {result['line_count']} lines")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"    ⚠ {w}")
    if result["error"]:
        print(f"    ✗ ERROR: {result['error']}")
    print()


def build_markdown_output(result: dict) -> str:
    """
    Wrap the raw extraction in a header block so the output file is
    self-documenting — useful when reviewing outputs across tools.
    """
    warnings_block = ""
    if result["warnings"]:
        warnings_block = "\n".join(f"> ⚠ {w}" for w in result["warnings"])
        warnings_block = f"\n\n---\n**Extraction Warnings**\n\n{warnings_block}\n\n---"

    errors_block = ""
    if result["error"]:
        errors_block = f"\n\n---\n**Extraction Error**\n\n> ✗ {result['error']}\n\n---"

    extracted_section = result["markdown"] if result["markdown"] else "_No content extracted._"

    return f"""<!-- MarkItDown Extraction Output
     File    : {result['file']}
     Format  : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}
     Tool    : {result['tool']} {result['tool_version']}
     Time    : {result['duration_seconds']}s
     Chars   : {result['char_count']}
     Extracted: {result['extracted_at']}
-->
{warnings_block}{errors_block}

{extracted_section}
"""


# ── Metrics summary ────────────────────────────────────────────────────────────
def save_metrics(all_results: list[dict]) -> None:
    """
    Write a summary metrics.json with scores per file and aggregates.
    This is the file compare.py will read across all tools.
    """
    summary = []
    for r in all_results:
        summary.append({
            "file": r["file"],
            "format": r["format"],
            "pdf_type": r.get("pdf_type"),
            "duration_seconds": r["duration_seconds"],
            "char_count": r["char_count"],
            "line_count": r["line_count"],
            "has_headings": ("# " in r["markdown"] or "## " in r["markdown"]),
            "has_tables": ("|" in r["markdown"]),
            "warning_count": len(r["warnings"]),
            "warnings": r["warnings"],
            "error": r["error"],
            "status": "error" if r["error"] else (
                "empty" if r["char_count"] < EMPTY_THRESHOLD else "ok"
            ),
        })

    metrics = {
        "tool": "markitdown",
        "tool_version": "0.1.4+",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(all_results),
        "successful": sum(1 for s in summary if s["status"] == "ok"),
        "empty_outputs": sum(1 for s in summary if s["status"] == "empty"),
        "errors": sum(1 for s in summary if s["status"] == "error"),
        "avg_duration_seconds": (
            round(sum(s["duration_seconds"] or 0 for s in summary) / len(summary), 4)
            if summary else 0
        ),
        "known_limitations": [
            "No built-in OCR — scanned PDFs produce empty output",
            "pdfminer.six backend strips heading structure from PDFs",
            "Complex multi-column PDF layouts may merge into garbled text",
            "Table extraction from PDFs is unreliable",
            "DOCX quality is significantly better than PDF quality",
        ],
        "files": summary,
    }

    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"📊 Metrics saved → {METRICS_FILE}")
    print(f"   Total: {metrics['total_files']} | OK: {metrics['successful']} | "
          f"Empty: {metrics['empty_outputs']} | Errors: {metrics['errors']}")
    print(f"   Avg extraction time: {metrics['avg_duration_seconds']}s")


# ── Entry point ───────────────────────────────────────────────────────────────
def collect_files(target: Path) -> list[Path]:
    """Collect all supported resume files from a path (file or directory)."""
    if target.is_file():
        if target.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [target]
        else:
            print(f"[WARN] Unsupported file type: {target.suffix}. Skipping.")
            return []
    elif target.is_dir():
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(target.glob(f"*{ext}"))
            files.extend(target.glob(f"*{ext.upper()}"))
        files = sorted(set(files))
        if not files:
            print(f"[WARN] No supported resume files found in: {target}")
        return files
    else:
        print(f"[ERROR] Path does not exist: {target}")
        return []


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python extract.py <file_or_folder>")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    files = collect_files(target)

    if not files:
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  MarkItDown Resume Extractor")
    print(f"  Target  : {target}")
    print(f"  Files   : {len(files)} resume(s) found")
    print(f"  Outputs : {OUTPUTS_DIR}")
    print(f"{'='*60}\n")

    # Single MarkItDown instance — reused across all files for efficiency
    md_converter = MarkItDown(enable_plugins=False)

    all_results = []
    for file_path in files:
        result = extract_resume(file_path, md_converter)
        save_outputs(result)
        all_results.append(result)

    save_metrics(all_results)
    print(f"\n{'='*60}")
    print(f"  Done. Check outputs/ for .md files and metrics.json for scores.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
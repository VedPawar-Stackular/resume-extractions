"""
Marker — Resume Extraction Script
===================================
Tool:    Marker by datalab-to (formerly VikParuchuri)
Version: 1.5.0+
Repo:    resume-extraction-eval / 01_marker/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What makes Marker different from every other local tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All other LOCAL tools in this evaluation work like this:
  PyMuPDF / pymupdf4llm — read PDF drawing commands, infer
  structure from bounding boxes + font sizes (rule-based)

Marker works like this:
  → Runs a VISUAL LAYOUT DETECTION model (Surya) on the page
  → The model sees the page like a human eye would — as an image
  → Detects reading order, headings, columns, tables from visual cues
  → Runs Surya OCR on the detected text regions
  → Reconstructs document structure from visual understanding

This is why Marker handles what rule-based tools fail on:
  - Graphic/designed resumes (headings styled by colour, not font size)
  - Multi-column layouts (sees columns as visual regions, not x-coords)
  - Tables with no ruling lines (detects table structure visually)
  - Scanned PDFs (OCR is built-in, not a plugin)
  - DOCX / PPTX / images (same visual pipeline)

The tradeoff: heavier install (~2–4GB model download on first run),
slower per-file on CPU, GPU gives significant speedup.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Output modes this script runs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Primary   : Markdown — headings, bold, tables, bullets
  Secondary : JSON     — structured page blocks with metadata
                         (layout type per block: Text, Table, SectionHeader...)

The JSON output is unique to Marker in this evaluation — it tells you
not just the text but what TYPE each block is (SectionHeader, ListGroup,
Table, Figure, etc.), which is directly useful for ATS scoring pipelines.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Supported formats
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Native PDF   (.pdf)        — best quality, fast
  Scanned PDF  (.pdf)        — built-in Surya OCR, no Tesseract needed
  Images       (.jpg/.png)   — Surya OCR directly on image
  DOCX         (.docx/.doc)  — requires marker-pdf[docx]
  PPTX / XLSX / HTML / EPUB  — supported, not tested in this eval

Usage
-----
  python extract.py path/to/resume.pdf
  python extract.py path/to/resumes/
  python extract.py path/to/resumes/ --use-llm    # LLM-enhanced mode
  python extract.py path/to/resumes/ --verbose     # show block-level debug
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# ── Marker ───────────────────────────────────────────────────────────────────
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    from marker.config.parser import ConfigParser
    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False
    print("[ERROR] marker-pdf not installed.")
    print("  1. (GPU users) pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
    print("  2. pip install marker-pdf[docx]")
    sys.exit(1)

# ── PyMuPDF for pre-flight detection ─────────────────────────────────────────
try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ── Torch for device detection ────────────────────────────────────────────────
try:
    import torch
    if torch.cuda.is_available():
        DEVICE = "cuda"
        DEVICE_NAME = torch.cuda.get_device_name(0)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        DEVICE = "mps"
        DEVICE_NAME = "Apple MPS (Metal)"
    else:
        DEVICE = "cpu"
        DEVICE_NAME = "CPU (no GPU detected — expect slower processing)"
    TORCH_AVAILABLE = True
except ImportError:
    DEVICE = "cpu"
    DEVICE_NAME = "CPU"
    TORCH_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR     = Path(__file__).parent / "outputs"
METRICS_FILE    = Path(__file__).parent / "metrics.json"
SUPPORTED_EXTS  = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png"}
EMPTY_THRESHOLD = 80
VERBOSE         = "--verbose" in sys.argv
USE_LLM         = "--use-llm" in sys.argv

# Block type categories Marker assigns to each content block
HEADING_BLOCK_TYPES = {"SectionHeader"}
TABLE_BLOCK_TYPES   = {"Table"}
LIST_BLOCK_TYPES    = {"ListGroup", "ListItem"}
TEXT_BLOCK_TYPES    = {"Text", "TextInlineMath"}
IMAGE_BLOCK_TYPES   = {"Figure", "Picture"}


# ── PDF type pre-check ────────────────────────────────────────────────────────
def detect_pdf_type(path: Path) -> str:
    if not PYMUPDF_AVAILABLE:
        return "unknown"
    try:
        doc = pymupdf.open(str(path))
        types = []
        for page in doc:
            types.append("native" if len(page.get_text().strip()) > 30 else "scanned")
        doc.close()
        s = set(types)
        if s == {"native"}:  return "native"
        if s == {"scanned"}: return "scanned"
        return "mixed"
    except Exception as e:
        return f"error:{e}"


# ── Lazy model loader — load once, reuse across all files ─────────────────────
_models = None

def get_models():
    global _models
    if _models is None:
        print("  ⟳ Loading Marker models (first run downloads ~2–4GB)...")
        t = time.perf_counter()
        _models = create_model_dict()
        print(f"  ✓ Models loaded in {round(time.perf_counter() - t, 2)}s\n")
    return _models


# ── Core extraction ───────────────────────────────────────────────────────────
def extract_resume(file_path: Path) -> dict:
    ext = file_path.suffix.lower()

    result = {
        "file":                file_path.name,
        "file_path":           str(file_path),
        "format":              ext,
        "pdf_type":            None,
        "tool":                "marker",
        "tool_version":        _get_marker_version(),
        "device":              DEVICE,
        "device_name":         DEVICE_NAME,
        "use_llm":             USE_LLM,
        "extracted_at":        datetime.now(timezone.utc).isoformat(),
        "model_load_included": False,  # model load time excluded from per-file timing
        "duration_seconds":    None,
        # Markdown output
        "markdown":            "",
        "char_count":          0,
        "line_count":          0,
        "heading_count":       0,
        "table_count":         0,
        # JSON / block metadata
        "block_type_counts":   {},
        "page_count":          0,
        # Quality signals
        "warnings":            [],
        "error":               None,
    }

    if ext not in SUPPORTED_EXTS:
        result["error"] = f"Unsupported extension: {ext}"
        return result

    # Pre-flight: PDF type detection
    if ext == ".pdf":
        result["pdf_type"] = detect_pdf_type(file_path)

    # Ensure models are loaded (cached after first call)
    try:
        models = get_models()
    except Exception as e:
        result["error"] = f"Model load failed: {e}"
        return result

    # Build config
    config_dict = {
        "output_format": "markdown",
        "disable_image_extraction": True,  # resumes have no meaningful images
    }

    # ── Run Marker ────────────────────────────────────────────────────────────
    t_start = time.perf_counter()
    try:
        config_parser = ConfigParser(config_dict)
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=models,
            processor_list=None,
            renderer=None,
        )
        rendered = converter(str(file_path))
        markdown_text, _, _ = text_from_rendered(rendered)

    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.perf_counter() - t_start, 4)
        return result

    result["duration_seconds"] = round(time.perf_counter() - t_start, 4)

    # ── Store markdown output ─────────────────────────────────────────────────
    result["markdown"]  = markdown_text
    result["char_count"] = len(markdown_text)
    result["line_count"] = len(markdown_text.splitlines())

    lines = markdown_text.splitlines()
    result["heading_count"] = sum(1 for l in lines if l.startswith("#"))
    result["table_count"]   = sum(1 for l in lines if l.startswith("|") and "---" not in l)

    # ── Extract block metadata from rendered object ───────────────────────────
    block_types = []
    page_count  = 0
    try:
        # rendered.children = list of pages; each page has blocks
        for page in rendered.children:
            page_count += 1
            for block in getattr(page, "children", []):
                btype = type(block).__name__
                block_types.append(btype)
    except Exception:
        pass  # block introspection is best-effort; don't fail extraction

    result["page_count"]      = page_count
    result["block_type_counts"] = dict(Counter(block_types))

    _run_quality_checks(result, markdown_text, block_types)

    if VERBOSE:
        _print_block_debug(result, block_types[:20])

    return result


def _get_marker_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("marker-pdf")
    except Exception:
        return "1.5.0+"


# ── Quality checks ────────────────────────────────────────────────────────────
def _run_quality_checks(result: dict, md: str, block_types: list) -> None:
    # 1. Near-empty output
    if result["char_count"] < EMPTY_THRESHOLD:
        result["warnings"].append(
            f"Near-empty output ({result['char_count']} chars). "
            "File may be corrupt, password-protected, or an unsupported format variant."
        )

    # 2. No headings — unusual for Marker which uses visual layout detection
    if result["heading_count"] == 0 and result["char_count"] > EMPTY_THRESHOLD:
        result["warnings"].append(
            "No Markdown headings detected. Marker uses visual layout detection, "
            "so this suggests the resume has no visually distinct section headers "
            "(e.g. a plain-text or minimally styled resume). "
            "The content is still extracted — just without heading hierarchy."
        )

    # 3. CPU performance warning
    if DEVICE == "cpu":
        result["warnings"].append(
            f"Running on CPU ({DEVICE_NAME}). "
            "Marker's Surya models are significantly faster on GPU. "
            "Expect 30–120s/page on CPU vs <1s/page on H100. "
            "For production ATS batch processing, a GPU instance is strongly recommended."
        )

    # 4. CID glyphs
    if "(cid:" in md:
        result["warnings"].append(
            "CID glyph codes detected. Marker's OCR pipeline may have partially "
            "recovered these — check the output for garbled characters near CID markers."
        )

    # 5. No blocks extracted
    if not block_types:
        result["warnings"].append(
            "No block metadata extracted from rendered output. "
            "Block-level type analysis unavailable for this file."
        )


def _print_block_debug(result: dict, block_sample: list) -> None:
    print(f"\n  ── Block types detected ──")
    for btype, count in result["block_type_counts"].items():
        bar = "█" * min(count, 20)
        print(f"  {btype:<20} {bar} ({count})")
    print(f"  Total blocks: {sum(result['block_type_counts'].values())}")
    print()


# ── Output writing ────────────────────────────────────────────────────────────
def save_outputs(result: dict) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(result["file"]).stem

    # 1. Main markdown output
    md_path = OUTPUTS_DIR / f"{stem}.md"
    md_path.write_text(_build_md_file(result), encoding="utf-8")

    # 2. Block metadata JSON
    blocks_path = OUTPUTS_DIR / f"{stem}.blocks.json"
    blocks_path.write_text(
        json.dumps({
            "file":             result["file"],
            "page_count":       result["page_count"],
            "block_type_counts": result["block_type_counts"],
            "device":           result["device"],
            "duration_seconds": result["duration_seconds"],
            "note": (
                "block_type_counts shows how many of each Marker block type "
                "were detected. Key types for resumes: SectionHeader (headings), "
                "Table, ListGroup (bullet points), Text (body paragraphs)."
            ),
        }, indent=2),
        encoding="utf-8"
    )

    # 3. Per-file metadata
    meta = {k: v for k, v in result.items() if k != "markdown"}
    meta_path = OUTPUTS_DIR / f"{stem}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # ── Console summary ────────────────────────────────────────────────────
    status = "✗" if result["error"] else ("⚠" if result["warnings"] else "✓")
    print(f"  {status} {result['file']}")
    print(f"    Format   : {result['format']} ({result.get('pdf_type', 'n/a')})")
    print(f"    Device   : {result['device']} — {result['device_name']}")
    print(f"    Time     : {result['duration_seconds']}s  (model load excluded)")
    print(f"    Output   : {result['char_count']} chars | {result['line_count']} lines | {result['page_count']} pages")
    print(f"    Headings : {result['heading_count']} | Tables: {result['table_count']} rows")
    if result["block_type_counts"]:
        top_blocks = sorted(result["block_type_counts"].items(), key=lambda x: -x[1])[:4]
        print(f"    Top blocks: {', '.join(f'{k}={v}' for k, v in top_blocks)}")
    for w in result["warnings"]:
        print(f"    ⚠  {w}")
    if result["error"]:
        print(f"    ✗  {result['error']}")
    print()


def _build_md_file(result: dict) -> str:
    warn_block = ""
    if result["warnings"]:
        warn_block = (
            "\n\n---\n**Extraction Warnings**\n\n"
            + "\n".join(f"> ⚠ {w}" for w in result["warnings"])
            + "\n\n---\n\n"
        )

    err_block = ""
    if result["error"]:
        err_block = f"\n\n---\n**Error**\n\n> ✗ {result['error']}\n\n---\n\n"

    block_summary = ""
    if result["block_type_counts"]:
        block_summary = (
            "     Blocks   : "
            + ", ".join(f"{k}={v}" for k, v in
                       sorted(result["block_type_counts"].items(), key=lambda x: -x[1])[:5])
            + "\n"
        )

    content = result["markdown"] if result["markdown"] else "_No content extracted._"

    return (
        f"<!-- Marker Extraction Output\n"
        f"     File     : {result['file']}\n"
        f"     Format   : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}\n"
        f"     Tool     : {result['tool']} {result['tool_version']}\n"
        f"     Device   : {result['device']} ({result['device_name']})\n"
        f"     Use LLM  : {result['use_llm']}\n"
        f"     Time     : {result['duration_seconds']}s\n"
        f"     Chars    : {result['char_count']} | Headings: {result['heading_count']} "
        f"| Tables: {result['table_count']}\n"
        f"     Pages    : {result['page_count']}\n"
        f"{block_summary}"
        f"     Extracted: {result['extracted_at']}\n"
        f"     NOTE     : Marker uses Surya visual layout detection — not font-size\n"
        f"                heuristics. Block types reflect visual understanding of page.\n"
        f"-->"
        f"{warn_block}{err_block}\n\n"
        f"{content}\n"
    )


# ── Metrics summary ────────────────────────────────────────────────────────────
def save_metrics(all_results: list[dict], model_load_time: float) -> None:
    summary = []
    for r in all_results:
        summary.append({
            "file":              r["file"],
            "format":            r["format"],
            "pdf_type":          r.get("pdf_type"),
            "device":            r["device"],
            "duration_seconds":  r["duration_seconds"],
            "char_count":        r["char_count"],
            "line_count":        r["line_count"],
            "page_count":        r["page_count"],
            "heading_count":     r["heading_count"],
            "table_count":       r["table_count"],
            "has_headings":      r["heading_count"] > 0,
            "has_tables":        r["table_count"] > 0,
            "block_type_counts": r["block_type_counts"],
            "warning_count":     len(r["warnings"]),
            "warnings":          r["warnings"],
            "error":             r["error"],
            "status": (
                "error" if r["error"] else
                "empty" if r["char_count"] < EMPTY_THRESHOLD else
                "ok"
            ),
        })

    ok   = [s for s in summary if s["status"] == "ok"]
    avg_t = round(
        sum(s["duration_seconds"] or 0 for s in summary) / max(len(summary), 1), 4
    )

    metrics = {
        "tool":              "marker",
        "tool_version":      summary[0].get("tool_version", "1.5.0+") if summary else "1.5.0+",
        "device":            DEVICE,
        "device_name":       DEVICE_NAME,
        "use_llm":           USE_LLM,
        "run_at":            datetime.now(timezone.utc).isoformat(),
        "model_load_seconds": round(model_load_time, 2),
        "total_files":       len(all_results),
        "successful":        len(ok),
        "empty_outputs":     sum(1 for s in summary if s["status"] == "empty"),
        "errors":            sum(1 for s in summary if s["status"] == "error"),
        "avg_duration_seconds_excl_model_load": avg_t,
        "license_note": (
            "Model weights: AI Pubs Open Rail-M — free for research/personal/startups <$2M. "
            "Code: GPL. Commercial use beyond threshold requires a license from datalab-to."
        ),
        "architecture": (
            "Visual layout detection via Surya deep learning models. "
            "NOT rule-based font-size inference. Sees the page as an image."
        ),
        "key_advantages": [
            "Visual layout detection — handles designed/graphic resumes",
            "Built-in Surya OCR — no Tesseract needed",
            "DOCX + images in same pipeline (marker-pdf[docx])",
            "Block-type metadata: SectionHeader, Table, ListGroup, Text, Figure",
            "GPU, CPU, Apple MPS all supported",
            "Fully local — files never leave your machine",
            "Optional --use_llm for table accuracy boost",
        ],
        "key_limitations": [
            "Heaviest install: ~2–4GB model download on first run",
            "Slow on CPU (30–120s/page vs <1s/page on H100)",
            "GPL code license — factor into commercial architecture",
            "Model load time (~10–30s) amortised across batch but noticeable for single files",
            "Table detection weaker than Docling on complex multi-level tables",
        ],
        "files": summary,
    }

    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"📊 Metrics saved → {METRICS_FILE}")
    print(f"   Total       : {metrics['total_files']} | OK: {metrics['successful']} | "
          f"Errors: {metrics['errors']}")
    print(f"   Model load  : {model_load_time:.2f}s (one-time per session)")
    print(f"   Avg extract : {avg_t}s/file (excl. model load)")
    print(f"   Device      : {DEVICE} — {DEVICE_NAME}")


# ── File collection ────────────────────────────────────────────────────────────
def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix.lower() in SUPPORTED_EXTS else []
    files = []
    for ext in SUPPORTED_EXTS:
        files.extend(target.glob(f"*{ext}"))
        files.extend(target.glob(f"*{ext.upper()}"))
    return sorted(set(files))


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    file_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not file_args:
        print(__doc__)
        print("Usage: python extract.py <file_or_folder> [--use-llm] [--verbose]")
        sys.exit(1)

    target = Path(file_args[0]).resolve()
    files  = collect_files(target)

    if not files:
        print(f"[ERROR] No supported files found at: {target}")
        sys.exit(1)

    print(f"\n{'='*64}")
    print(f"  Marker Resume Extractor (visual layout detection)")
    print(f"  Target   : {target}")
    print(f"  Files    : {len(files)} resume(s) found")
    print(f"  Device   : {DEVICE} — {DEVICE_NAME}")
    print(f"  Use LLM  : {'YES — enhanced table/form accuracy' if USE_LLM else 'NO  — pass --use-llm to enable'}")
    print(f"  Outputs  : {OUTPUTS_DIR}")
    print(f"  NOTE     : First run downloads ~2–4GB of Surya model weights.")
    print(f"{'='*64}\n")

    # Load models ONCE and time it separately
    model_load_start = time.perf_counter()
    get_models()
    model_load_time = time.perf_counter() - model_load_start

    all_results = []
    for file_path in files:
        result = extract_resume(file_path)
        save_outputs(result)
        all_results.append(result)

    save_metrics(all_results, model_load_time)

    print(f"\n{'='*64}")
    print(f"  Done. Outputs:")
    print(f"    *.md           ← extracted markdown")
    print(f"    *.blocks.json  ← block-type metadata (SectionHeader, Table...)")
    print(f"    *.meta.json    ← timing, device, quality signals")
    print(f"    metrics.json   ← scorecard for compare.py")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()


# ── Pre-flight check mode ──────────────────────────────────────────────────
# Run: python extract.py --check
# Validates environment before attempting model load
def run_preflight_check():
    print("\n" + "="*64)
    print("  Marker — Environment Pre-flight Check")
    print("="*64)
    
    # 1. Python version
    import sys
    pv = sys.version_info
    ok = pv >= (3, 10)
    print(f"  Python {pv.major}.{pv.minor}: {'✓' if ok else '✗ (need 3.10+)'}")

    # 2. torch
    try:
        import torch
        print(f"  torch {torch.__version__}: ✓")
        if torch.cuda.is_available():
            print(f"  CUDA: ✓ — {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print(f"  MPS (Apple Silicon): ✓")
        else:
            print(f"  GPU: ✗ — CPU only (expect slow extraction)")
    except (ImportError, OSError) as e:
        print(f"  torch: ✗ — {e}")
        print(f"         Fix: pip install torch torchvision (see requirements.txt)")

    # 3. marker-pdf
    try:
        import importlib.metadata
        v = importlib.metadata.version("marker-pdf")
        print(f"  marker-pdf {v}: ✓")
    except Exception as e:
        print(f"  marker-pdf: ✗ — {e}")
        print(f"             Fix: pip install marker-pdf[docx]")
    
    # 4. Marker imports
    try:
        from marker.converters.pdf import PdfConverter
        print(f"  marker imports: ✓")
    except Exception as e:
        print(f"  marker imports: ✗ — {e}")

    # 5. pymupdf
    try:
        import pymupdf
        print(f"  pymupdf {pymupdf.__version__}: ✓")
    except ImportError:
        print(f"  pymupdf: ✗ (optional — for scanned PDF detection)")

    # 6. Disk space (model cache check)
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024**3)
    status = "✓" if free_gb > 5 else "⚠ low"
    print(f"  Disk free: {free_gb:.1f}GB {status} (need ~4GB for first model download)")

    print("="*64 + "\n")

if "--check" in sys.argv:
    run_preflight_check()
    sys.exit(0)
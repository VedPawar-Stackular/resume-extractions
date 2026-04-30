"""
LlamaParse — Resume Extraction Script
=======================================
Tool:    LlamaParse by LlamaIndex (cloud API)
Version: 0.6.0+
Repo:    resume-extraction-eval / 06_llamaparse/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT — READ BEFORE RUNNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LlamaParse is a CLOUD API. Unlike every other tool in this evaluation:

  1. Your resume files are UPLOADED to LlamaIndex's servers.
     For an HR/ATS product with real candidate data, evaluate
     their privacy policy and data retention terms before using
     in production: https://www.llamaindex.ai/privacy-policy

  2. You need an API key:
       export LLAMA_CLOUD_API_KEY="llx-xxxxxxxxxxxxxxxxxxxx"
     Get one free at: https://cloud.llamaindex.ai

  3. Parsing costs credits. This script uses cost_effective mode
     (3 credits/page). A typical 2-page resume = 6 credits.
     New accounts get 10,000 free credits.

  4. Processing is NOT instant — API round-trip + LLM inference
     typically takes 10–30s per file. This is expected.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What makes LlamaParse different from local tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All other tools in this evaluation (PyMuPDF, pymupdf4llm, MarkItDown,
Marker, MinerU) use rule-based or model-based layout analysis running
LOCALLY. They read PDF drawing commands and infer structure from
bounding boxes and font sizes.

LlamaParse uses an LLM to UNDERSTAND the document semantically —
the same way a human would. It doesn't need to detect font sizes
to know "WORK EXPERIENCE" is a heading. It reads the content and
reconstructs structure from meaning. This is the key architectural
difference and the reason it handles the hardest layouts.

Output formats this script tests:
  - Markdown (our primary: headings, bold, tables, bullets)
  - Text     (plain — for direct comparison with raw tools)

Custom instructions: LlamaParse accepts a natural language prompt
to guide extraction. We use an ATS-specific prompt that tells it
to preserve section structure critical for resume scoring.

Supported formats
-----------------
  Native PDF  (.pdf)  — primary use case, best quality
  Scanned PDF (.pdf)  — handled via built-in vision model
  DOCX        (.docx) — full support
  Images      (.jpg/.png) — vision model OCR

Usage
-----
  # Single file
  python extract.py path/to/resume.pdf

  # Entire sample folder
  python extract.py path/to/resumes/

  # Test both markdown AND text output
  python extract.py path/to/resume.pdf --both-modes

  # Use a different parse mode (cost_effective | agentic | parse_without_llm)
  python extract.py path/to/resume.pdf --mode agentic
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timezone

# ── LlamaParse ───────────────────────────────────────────────────────────────
try:
    from llama_cloud_services import LlamaParse
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("[ERROR] llama-parse not installed. Run: pip install llama-parse nest-asyncio")
    sys.exit(1)

# ── PyMuPDF for pre-flight scanned detection ─────────────────────────────────
try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR    = Path(__file__).parent / "outputs"
METRICS_FILE   = Path(__file__).parent / "metrics.json"
SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png"}
EMPTY_THRESHOLD = 80

# ── Parse mode from CLI args ─────────────────────────────────────────────────
args = sys.argv[1:]
PARSE_MODE = "cost_effective"
for a in args:
    if a.startswith("--mode="):
        PARSE_MODE = a.split("=", 1)[1]
    elif a == "--mode" and args.index(a) + 1 < len(args):
        PARSE_MODE = args[args.index(a) + 1]

BOTH_MODES = "--both-modes" in args

# Credits/page reference (approximate, check LlamaIndex pricing for latest)
CREDITS_PER_PAGE = {
    "parse_without_llm": 1,
    "cost_effective":    3,
    "agentic":           20,
}

# ── ATS-specific parsing instruction ─────────────────────────────────────────
# This is one of LlamaParse's key advantages: natural language instructions
# that guide the LLM to produce output shaped for our specific use case.
ATS_PARSING_INSTRUCTION = """
You are parsing a resume / curriculum vitae for an Applicant Tracking System (ATS).

Your goal is to extract ALL information with perfect fidelity. Follow these rules:

STRUCTURE:
- Use ## for major section headings (Work Experience, Education, Skills, etc.)
- Use ### for subsection headings (individual job titles, degree names)
- Preserve all bullet points as Markdown list items (-)
- Preserve bold text for emphasis (company names, job titles, degree names)

CONTENT — never omit or summarise:
- Full name, all contact details (email, phone, LinkedIn, GitHub, portfolio)
- Every job: exact title, company, location, date range, ALL bullet points
- Every education entry: degree, institution, year, GPA/CGPA if present
- ALL skills exactly as listed — do not group or rephrase
- Every certification with issuer and year
- Every project with technologies used
- Languages, publications, awards, volunteer work if present

TABLES:
- Convert any skills table, education table, or comparison table to Markdown pipe table format
- Preserve all rows and columns exactly

DO NOT:
- Summarise or condense any section
- Add information that is not in the document
- Reorder sections from the original document
- Skip any bullet point or line item
"""

# ── PDF type detection ────────────────────────────────────────────────────────
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


# ── Credit cost estimator ────────────────────────────────────────────────────
def estimate_credits(page_count: int, mode: str) -> dict:
    cpp = CREDITS_PER_PAGE.get(mode, 3)
    credits = page_count * cpp
    usd = credits * (1.25 / 1000)
    return {
        "mode":           mode,
        "credits_per_page": cpp,
        "estimated_credits": credits,
        "estimated_usd":  round(usd, 5),
    }


# ── Core extraction ───────────────────────────────────────────────────────────
def extract_resume(file_path: Path, parse_mode: str, result_type: str = "markdown") -> dict:
    ext = file_path.suffix.lower()

    result = {
        "file":             file_path.name,
        "file_path":        str(file_path),
        "format":           ext,
        "pdf_type":         None,
        "tool":             "llamaparse",
        "parse_mode":       parse_mode,
        "result_type":      result_type,
        "cloud_api":        True,
        "privacy_note":     "File uploaded to LlamaIndex cloud servers for processing",
        "extracted_at":     datetime.now(timezone.utc).isoformat(),
        "duration_seconds": None,
        "page_count":       None,
        "char_count":       0,
        "line_count":       0,
        "heading_count":    0,
        "table_count":      0,
        "cost_estimate":    None,
        "content":          "",
        "warnings":         [],
        "error":            None,
    }

    # Pre-flight: check API key
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
    if not api_key:
        result["error"] = (
            "LLAMA_CLOUD_API_KEY environment variable not set.\n"
            "  Get a free key at: https://cloud.llamaindex.ai\n"
            "  Then: export LLAMA_CLOUD_API_KEY='llx-xxxx'"
        )
        return result

    # Pre-flight: PDF type detection
    if ext == ".pdf":
        pdf_type = detect_pdf_type(file_path)
        result["pdf_type"] = pdf_type
        if pdf_type == "scanned":
            result["warnings"].append(
                "Scanned PDF detected — LlamaParse will use its built-in vision model "
                "for OCR. This may use more credits than a native PDF."
            )

    # Build the parser
    parser = LlamaParse(
        api_key=api_key,
        result_type=result_type,
        parsing_instruction=ATS_PARSING_INSTRUCTION,
        verbose=False,
        language="en",
        # Use the mode that maps to our parse_mode arg
        # cost_effective = 3 credits/page (good LLM quality)
        # parse_without_llm = 1 credit/page (no AI)
        # agentic = ~20 credits/page (best quality, slowest)
        **({"use_vendor_multimodal_model": True} if parse_mode == "agentic" else {}),
    )

    # Run extraction and time it
    t_start = time.perf_counter()
    try:
        documents = parser.load_data(str(file_path))
    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.perf_counter() - t_start, 4)
        return result
    t_end = time.perf_counter()

    result["duration_seconds"] = round(t_end - t_start, 4)

    if not documents:
        result["error"] = "LlamaParse returned 0 documents — file may be empty or corrupt."
        return result

    # Combine all document pages into single output
    full_content = "\n\n".join(doc.text for doc in documents if doc.text)
    result["content"]     = full_content
    result["char_count"]  = len(full_content)
    result["line_count"]  = len(full_content.splitlines())
    result["page_count"]  = len(documents)

    lines = full_content.splitlines()
    result["heading_count"] = sum(1 for l in lines if l.startswith("#"))
    result["table_count"]   = sum(1 for l in lines if l.startswith("|") and "---" not in l)

    # Cost estimate (after we know page count)
    result["cost_estimate"] = estimate_credits(result["page_count"], parse_mode)

    _run_quality_checks(result)
    return result


# ── Quality checks ────────────────────────────────────────────────────────────
def _run_quality_checks(result: dict) -> None:
    content = result["content"]

    if result["char_count"] < EMPTY_THRESHOLD:
        result["warnings"].append(
            f"Near-empty output ({result['char_count']} chars). "
            "Check if the file uploaded correctly and is readable."
        )

    if result["result_type"] == "markdown" and result["heading_count"] == 0 and result["char_count"] > EMPTY_THRESHOLD:
        result["warnings"].append(
            "No Markdown headings found despite markdown mode. "
            "The resume may have no clear section structure recognisable to the LLM, "
            "or the ATS parsing instruction may need tuning."
        )

    if result["duration_seconds"] and result["duration_seconds"] < 2:
        result["warnings"].append(
            f"Suspiciously fast response ({result['duration_seconds']}s). "
            "LlamaParse API calls typically take 10–30s. "
            "Check if the result is a cached or fallback response."
        )

    if "(cid:" in content:
        result["warnings"].append(
            "CID glyph codes found in output — LlamaParse's LLM may have "
            "partially recovered these, but some characters could be wrong. "
            "Check the output carefully."
        )


# ── Output writing ────────────────────────────────────────────────────────────
def save_outputs(result: dict, mode_suffix: str = "") -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(result["file"]).stem
    suffix = f".{mode_suffix}" if mode_suffix else ""

    # Main content file
    ext = ".md" if result["result_type"] == "markdown" else ".txt"
    content_path = OUTPUTS_DIR / f"{stem}{suffix}{ext}"
    content_path.write_text(_build_content_file(result), encoding="utf-8")

    # Per-file metadata
    meta = {k: v for k, v in result.items() if k != "content"}
    meta_path = OUTPUTS_DIR / f"{stem}{suffix}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Console output
    status = "✗" if result["error"] else ("⚠" if result["warnings"] else "✓")
    print(f"  {status} {result['file']}  [{result['result_type']} / {result['parse_mode']}]")
    print(f"    Format    : {result['format']} ({result.get('pdf_type', 'n/a')})")
    print(f"    Time      : {result['duration_seconds']}s  ← cloud API round-trip")
    print(f"    Output    : {result['char_count']} chars | {result['line_count']} lines | {result['page_count']} pages")
    print(f"    Headings  : {result['heading_count']} | Tables: {result['table_count']} rows")
    if result["cost_estimate"]:
        c = result["cost_estimate"]
        print(f"    Cost est. : ~{c['estimated_credits']} credits (~${c['estimated_usd']}) @ {c['credits_per_page']} credits/page")
    for w in result["warnings"]:
        print(f"    ⚠  {w}")
    if result["error"]:
        print(f"    ✗  {result['error']}")
    print()


def _build_content_file(result: dict) -> str:
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

    cost = ""
    if result["cost_estimate"]:
        c = result["cost_estimate"]
        cost = (
            f"     Cost     : ~{c['estimated_credits']} credits "
            f"(~${c['estimated_usd']}) — {c['credits_per_page']} credits/page\n"
        )

    content = result["content"] if result["content"] else "_No content extracted._"

    return (
        f"<!-- LlamaParse Extraction Output\n"
        f"     File     : {result['file']}\n"
        f"     Format   : {result['format']} | PDF type: {result.get('pdf_type', 'n/a')}\n"
        f"     Tool     : {result['tool']} (cloud API)\n"
        f"     Mode     : {result['parse_mode']} | Output: {result['result_type']}\n"
        f"     Time     : {result['duration_seconds']}s\n"
        f"     Chars    : {result['char_count']} | Headings: {result['heading_count']} "
        f"| Tables: {result['table_count']}\n"
        f"{cost}"
        f"     Privacy  : {result['privacy_note']}\n"
        f"     Extracted: {result['extracted_at']}\n"
        f"     NOTE     : Output shaped by ATS_PARSING_INSTRUCTION prompt.\n"
        f"                Compare prompt vs no-prompt to see instruction effect.\n"
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
            "parse_mode":       r["parse_mode"],
            "result_type":      r["result_type"],
            "duration_seconds": r["duration_seconds"],
            "char_count":       r["char_count"],
            "heading_count":    r["heading_count"],
            "table_count":      r["table_count"],
            "page_count":       r["page_count"],
            "cost_estimate":    r["cost_estimate"],
            "has_headings":     r["heading_count"] > 0,
            "has_tables":       r["table_count"] > 0,
            "warning_count":    len(r["warnings"]),
            "warnings":         r["warnings"],
            "error":            r["error"],
            "status": (
                "error" if r["error"] else
                "empty" if r["char_count"] < EMPTY_THRESHOLD else
                "ok"
            ),
        })

    ok = [s for s in summary if s["status"] == "ok"]
    avg_t = round(
        sum(s["duration_seconds"] or 0 for s in summary if s["duration_seconds"]) /
        max(len([s for s in summary if s["duration_seconds"]]), 1), 4
    )
    total_credits = sum(
        s["cost_estimate"]["estimated_credits"]
        for s in summary if s.get("cost_estimate")
    )

    metrics = {
        "tool":                 "llamaparse",
        "cloud_api":            True,
        "run_at":               datetime.now(timezone.utc).isoformat(),
        "parse_mode":           PARSE_MODE,
        "total_files":          len(all_results),
        "successful":           len(ok),
        "empty_outputs":        sum(1 for s in summary if s["status"] == "empty"),
        "errors":               sum(1 for s in summary if s["status"] == "error"),
        "avg_duration_seconds": avg_t,
        "total_credits_used":   total_credits,
        "total_cost_usd":       round(total_credits * 1.25 / 1000, 5),
        "privacy_consideration": (
            "LlamaParse sends files to LlamaIndex cloud servers. "
            "Review their DPA/privacy policy before using with real candidate PII data."
        ),
        "key_advantages_over_local_tools": [
            "LLM understands document semantics — not just font sizes and bounding boxes",
            "Custom ATS parsing instruction shapes output for our exact use case",
            "Handles scanned PDFs, DOCX, images in one unified API",
            "Best-in-class table reconstruction from complex layouts",
            "No GPU, no model weights, no complex local setup",
            "Markdown output directly usable as LLM context without post-processing",
        ],
        "key_disadvantages": [
            "Cloud-only — files leave your infrastructure",
            "Costs money at scale (3 credits/page = $0.00375 per page)",
            "10–30s latency per file — not suitable for real-time single-resume UX",
            "Rate limits on free tier",
            "No local/on-premise option (LlamaCloud VPC exists at enterprise tier)",
        ],
        "files": summary,
    }

    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"📊 Metrics saved → {METRICS_FILE}")
    print(f"   Total : {metrics['total_files']} | OK: {metrics['successful']} | "
          f"Errors: {metrics['errors']}")
    print(f"   Avg API time    : {avg_t}s")
    print(f"   Total credits   : ~{total_credits} (~${metrics['total_cost_usd']})")


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
    file_args = [a for a in args if not a.startswith("--")]
    if not file_args:
        print(__doc__)
        print("Usage: python extract.py <file_or_folder> [--mode cost_effective|agentic|parse_without_llm] [--both-modes]")
        sys.exit(1)

    target = Path(file_args[0]).resolve()
    files  = collect_files(target)

    if not files:
        print(f"[ERROR] No supported files found at: {target}")
        sys.exit(1)

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
    api_status = "✓ set" if api_key else "✗ NOT SET — extraction will fail"

    print(f"\n{'='*64}")
    print(f"  LlamaParse Resume Extractor (cloud API)")
    print(f"  Target     : {target}")
    print(f"  Files      : {len(files)} resume(s) found")
    print(f"  Parse mode : {PARSE_MODE}  ({CREDITS_PER_PAGE.get(PARSE_MODE, '?')} credits/page)")
    print(f"  API key    : {api_status}")
    print(f"  Outputs    : {OUTPUTS_DIR}")
    print(f"  ⚠  Files will be uploaded to LlamaIndex cloud servers")
    print(f"{'='*64}\n")

    if not api_key:
        print("[ERROR] Set LLAMA_CLOUD_API_KEY first. Get one free at https://cloud.llamaindex.ai")
        sys.exit(1)

    all_results = []

    for file_path in files:
        print(f"→ Processing: {file_path.name}")

        if BOTH_MODES:
            # Run markdown AND plain text for direct comparison
            for rtype, suffix in [("markdown", "md"), ("text", "txt")]:
                result = extract_resume(file_path, PARSE_MODE, result_type=rtype)
                save_outputs(result, mode_suffix=suffix)
                all_results.append(result)
        else:
            # Default: markdown only (best for LLM context)
            result = extract_resume(file_path, PARSE_MODE, result_type="markdown")
            save_outputs(result)
            all_results.append(result)

    save_metrics(all_results)

    print(f"\n{'='*64}")
    print(f"  Done. Outputs:")
    print(f"    *.md / *.txt       ← extracted content")
    print(f"    *.meta.json        ← timing, cost, quality signals")
    print(f"    metrics.json       ← scorecard for compare.py")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
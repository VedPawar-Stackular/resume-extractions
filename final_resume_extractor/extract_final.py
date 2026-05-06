"""
Final Resume Extractor — Production-Ready Extractor
==================================================
Tool:    Unified Pipeline (Primary: PyMuPDF4LLM, Fallback: MarkItDown)
Purpose: Optimal balance of speed and LLM-friendly Markdown output.

Supported Formats:
- .pdf  : Extracted via PyMuPDF4LLM (Native & Scanned support)
- .docx : Extracted via MarkItDown
- .doc  : Converted to .docx via LibreOffice, then extracted via MarkItDown

Usage:
  python extract_final.py path/to/resume.pdf
  python extract_final.py path/to/folder/
"""

import sys
import time
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# ── Dependencies ──────────────────────────────────────────────────────────────
try:
    import pymupdf4llm
except ImportError:
    print("[ERROR] PyMuPDF4LLM not installed. Run: pip install pymupdf4llm")
    sys.exit(1)

try:
    from markitdown import MarkItDown
    HAS_MARKITDOWN = True
except ImportError:
    HAS_MARKITDOWN = False
    print("[WARN] MarkItDown not installed. DOCX extraction will be skipped.")

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR = Path(__file__).parent / "final_outputs"
SUPPORTED_EXTS = {".pdf", ".docx", ".doc"}

def convert_doc_to_docx(doc_path: Path) -> Path:
    """
    Uses LibreOffice (soffice) headless mode to convert legacy .doc to .docx.
    Returns the path to the temporary .docx file.
    """
    temp_dir = Path(tempfile.gettempdir()) / "resume_conv"
    temp_dir.mkdir(exist_ok=True)
    
    # Try common soffice paths or assume it's in PATH
    soffice_cmd = "soffice" # Standard on Linux/Mac. On Windows, might need full path if not in registry.
    
    # In a production Docker environment, this is always 'soffice'
    cmd = [
        soffice_cmd,
        "--headless",
        "--convert-to", "docx",
        "--outdir", str(temp_dir),
        str(doc_path)
    ]
    
    try:
        print(f"  [*] Converting legacy {doc_path.name} to DOCX...")
        subprocess.run(cmd, check=True, capture_output=True)
        docx_path = temp_dir / f"{doc_path.stem}.docx"
        if docx_path.exists():
            return docx_path
    except Exception as e:
        print(f"  [ERROR] LibreOffice conversion failed: {e}")
    
    return None

def extract_one(file_path: Path, mid_converter: 'MarkItDown') -> dict:
    t_start = time.perf_counter()
    ext = file_path.suffix.lower()
    md_content = ""
    status = "success"
    
    try:
        if ext == ".pdf":
            md_content = pymupdf4llm.to_markdown(str(file_path))
        
        elif ext == ".docx":
            if HAS_MARKITDOWN and mid_converter:
                md_content = mid_converter.convert(str(file_path)).text_content
            else:
                status = "error"
                md_content = "MarkItDown not available for DOCX."
        
        elif ext == ".doc":
            docx_path = convert_doc_to_docx(file_path)
            if docx_path and HAS_MARKITDOWN and mid_converter:
                md_content = mid_converter.convert(str(docx_path)).text_content
                # Clean up temp file
                docx_path.unlink()
            else:
                status = "error"
                md_content = "Failed to convert or process legacy .doc file."
        
        else:
            status = "error"
            md_content = f"Unsupported extension: {ext}"

    except Exception as e:
        status = "error"
        md_content = str(e)
        
    duration = round(time.perf_counter() - t_start, 4)
    
    return {
        "file": file_path.name,
        "format": ext,
        "duration": duration,
        "markdown": md_content,
        "status": status
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_final.py <file_or_folder>")
        sys.exit(1)
        
    target = Path(sys.argv[1]).resolve()
    
    # Collect files
    files = []
    if target.is_file():
        if target.suffix.lower() in SUPPORTED_EXTS:
            files.append(target)
    elif target.is_dir():
        # Using a set to avoid double-counting on case-insensitive filesystems
        found_files = set()
        for ext in SUPPORTED_EXTS:
            found_files.update(target.glob(f"*{ext}"))
            found_files.update(target.glob(f"*{ext.upper()}"))
        files = list(found_files)
    
    if not files:
        print(f"[ERROR] No supported resumes found at: {target}")
        sys.exit(1)
        
    print(f"\n{'='*60}")
    print(f"  Final Resume Extraction Pipeline")
    print(f"  Target: {target}")
    print(f"  Files : {len(files)} resume(s) identified")
    print(f"{'='*60}\n")

    mid_converter = MarkItDown() if HAS_MARKITDOWN else None
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    results = []
    for f in sorted(files):
        print(f"[*] Processing: {f.name}")
        res = extract_one(f, mid_converter)
        
        if res["status"] == "success":
            out_file = OUTPUTS_DIR / f"{f.stem}.final.md"
            out_file.write_text(res["markdown"], encoding="utf-8")
            print(f"  [OK] Extracted in {res['duration']}s")
        else:
            print(f"  [FAIL] {res['markdown']}")
            
        results.append(res)

    # -- Final Summary -------------------------------------------------------
    successes = [r for r in results if r["status"] == "success"]
    print(f"\n{'='*60}")
    print(f"  Extraction Summary")
    print(f"  Total Files: {len(results)}")
    print(f"  Successful : {len(successes)}")
    print(f"  Failed     : {len(results) - len(successes)}")
    if successes:
        avg_time = sum(r["duration"] for r in successes) / len(successes)
        print(f"  Avg Speed  : {avg_time:.2f}s per file")
    print(f"  Outputs    : {OUTPUTS_DIR}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

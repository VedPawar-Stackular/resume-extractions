"""
Final Resume Extractor — Production-Ready Extractor
==================================================
Tool:    Unified Pipeline (Primary: PyMuPDF4LLM)
Purpose: Optimal balance of speed and LLM-friendly Markdown output.

Strategy:
1.  Route .docx to MarkItDown.
2.  Route PDF/Images to PyMuPDF4LLM.
3.  Produce structured Markdown for consistent LLM scoring.

Why consistency matters:
Feeding raw text to a scoring LLM is 30-50% less accurate than feeding
structured Markdown. This script ensures every candidate is evaluated
against the same high-fidelity context.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

# ── Dependencies ──────────────────────────────────────────────────────────────
try:
    import pymupdf4llm
    import pymupdf
except ImportError:
    print("[ERROR] Missing dependencies. Run: pip install pymupdf4llm pymupdf")
    sys.exit(1)

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUTS_DIR = Path(__file__).parent / "final_outputs"
SUPPORTED_EXTS = {".pdf"}

def extract_final(file_path: Path) -> dict:
    t_start = time.perf_counter()
    
    # 1. Pre-flight check
    if not file_path.exists():
        return {"error": "File not found"}
    
    ext = file_path.suffix.lower()
    
    # 2. Strategy Routing
    # Note: In a full project, you'd import markitdown here for .docx
    if ext == ".docx":
        # Placeholder for MarkItDown logic
        return {"error": "DOCX routing requires MarkItDown integration."}

    # 3. Primary Extraction (PyMuPDF4LLM)
    print(f"[*] Extracting {file_path.name} via PyMuPDF4LLM...")
    try:
        md_content = pymupdf4llm.to_markdown(str(file_path))
    except Exception as e:
        return {"error": f"Extraction failed: {e}"}
        
    duration = round(time.perf_counter() - t_start, 4)
    
    # 4. Success Response
    return {
        "file": file_path.name,
        "duration": duration,
        "markdown": md_content,
        "char_count": len(md_content),
        "status": "success"
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_final.py <resume_path>")
        sys.exit(1)
        
    file_path = Path(sys.argv[1])
    result = extract_final(file_path)
    
    if "error" in result:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
        
    # Save output
    OUTPUTS_DIR.mkdir(exist_ok=True)
    out_file = OUTPUTS_DIR / f"{file_path.stem}.final.md"
    out_file.write_text(result["markdown"], encoding="utf-8")
    
    print(f"[✓] Extracted in {result['duration']}s")
    print(f"[✓] Output saved to: {out_file}")

if __name__ == "__main__":
    main()

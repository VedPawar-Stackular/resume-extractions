# 01 — Marker

**Tool:** [Marker](https://github.com/datalab-to/marker) by datalab-to  
**Type:** Local ML model (fully offline after first model download)  
**Version:** 1.5.0+  
**Python:** 3.10+  
**GPU:** Optional but strongly recommended (CUDA, Apple MPS, or CPU fallback)

---

## What Marker Is

Marker is the only tool in this evaluation that uses **visual layout detection** —
running actual deep learning models (Surya) that look at the page as an image and
understand its structure, rather than inferring it from PDF metadata.

Every other local tool in this evaluation works like this:
```
PDF drawing commands → bounding boxes + font sizes → rule-based inference
```

Marker works like this:
```
PDF page → rendered as image → Surya layout model → detected regions
  → Surya OCR on each region → structured markdown
```

This is the reason Marker handles what rule-based tools fail on:
- Resumes with **headings styled by colour, not font size**
- **Graphic/Canva-style resumes** with image backgrounds
- **Multi-column layouts** (sees columns as visual zones, not x-coordinate ranges)
- **Tables without ruling lines** (visual table detection)
- **Scanned PDFs** (OCR is built-in, no Tesseract plugin needed)

---

## Architecture

```
Input file (PDF / DOCX / image)
        ↓
  [Pre-processor] — detects PDF type, prepares pages
        ↓
  [Surya Layout Model] — identifies block types per page:
      SectionHeader | Text | Table | ListGroup | Figure | ...
        ↓
  [Surya OCR] — extracts text within each detected block
        ↓
  [Post-processor] — cleans, orders, reconstructs reading flow
        ↓
  Markdown + JSON block metadata
```

This pipeline downloads on first run:
- Surya layout detection model (~1.5GB)
- Surya OCR model (~1.5GB)
- Total: ~2–4GB cached in `~/.cache/huggingface/hub/`

---

## License (Read This)

| Component | License | Implication |
|-----------|---------|-------------|
| Model weights | AI Pubs Open Rail-M | Free for research, personal use, startups < $2M revenue/funding |
| Code | GPL | Must open-source derivative works under GPL |
| Commercial beyond threshold | Paid license required | Contact datalab-to |

For your ATS product: if revenue/funding exceeds $2M, a commercial license is needed.
Contact [datalab-to pricing](https://www.datalab.to/pricing) before production deployment.

---

## Setup

```bash
# ── GPU users (CUDA) — install PyTorch FIRST ──────────────────────────────
# Check your CUDA version: nvidia-smi
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# Adjust cu121 to: cu118 (CUDA 11.8), cu121 (CUDA 12.1), cu124 (CUDA 12.4)

# ── CPU / Apple Silicon — no extra PyTorch step needed ───────────────────

# ── Install Marker ────────────────────────────────────────────────────────
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

pip install -r requirements.txt
# This installs: marker-pdf[docx], pymupdf, tabulate
# PyTorch CPU is installed automatically if not already present

# ── Verify ────────────────────────────────────────────────────────────────
python -c "from marker.converters.pdf import PdfConverter; print('Marker ready')"
```

**First run downloads ~2–4GB.** Subsequent runs use the cached models.
Ensure disk space and internet on first run.

---

## Running Extraction

```bash
# Single resume (native PDF)
python extract.py ../sample_resumes/resume.pdf

# Whole sample folder
python extract.py ../sample_resumes/

# With block-level debug output (shows SectionHeader, Table, ListGroup per page)
python extract.py ../sample_resumes/ --verbose

# LLM-enhanced mode (improves table accuracy significantly)
# Uses Gemini Flash by default — set GOOGLE_API_KEY or configure Ollama
python extract.py ../sample_resumes/ --use-llm

# Outputs:
#   outputs/<stem>.md           ← extracted markdown
#   outputs/<stem>.blocks.json  ← block-type metadata per page
#   outputs/<stem>.meta.json    ← timing, device, quality signals
#   metrics.json                ← scorecard for compare.py
```

---

## Speed Expectations by Device

| Device | Pages/sec | 2-page resume |
|--------|-----------|---------------|
| H100 GPU | 122 | ~0.02s |
| A6000 GPU | ~24 | ~0.08s |
| RTX 3080 | ~8 | ~0.25s |
| Apple M2 (MPS) | ~2 | ~1s |
| CPU only | ~0.03 | ~60–120s |

**Model load time** (~10–30s) is a one-time cost per session, then amortised
across all files. The `metrics.json` reports model load and per-file time separately.

---

## Output Format

### Markdown (`.md`)
Standard heading hierarchy, bold/italic, Markdown pipe tables, bullet lists.
Marker detects these from visual layout — not font sizes:

```markdown
## Work Experience

### Lead Backend Engineer — CloudStack Solutions
**March 2021 – Present**

- Led migration of monolithic Django app to FastAPI microservices
- **Technologies:** Python, FastAPI, Kafka

## Skills

| Category  | Technologies          |
|-----------|----------------------|
| Languages | Python, Go, SQL       |
| Cloud     | AWS, Docker, Kubernetes |
```

### Block metadata (`.blocks.json`)
Shows what Marker detected on each page. Useful for ATS scoring pipelines:

```json
{
  "block_type_counts": {
    "SectionHeader": 6,
    "ListGroup": 4,
    "Text": 8,
    "Table": 1
  }
}
```

A resume with `SectionHeader: 0` is a signal the layout is flat — the ATS
scoring LLM should treat it with lower section-boundary confidence.

---

## Comparing with Other Tools

| Signal | MarkItDown | pymupdf4llm | PyMuPDF (inferred) | Marker |
|--------|-----------|-------------|-------------------|--------|
| Heading detection | None (PDF) | Font-size freq | Font-size freq | **Visual layout model** |
| Scanned PDF | ✗ | Tesseract opt. | ✗ | ✓ Built-in Surya |
| DOCX support | ✓ (mammoth) | ✗ (Pro only) | ✗ | ✓ |
| Table detection | Poor | Ruled lines only | None | **Visual + `--use_llm`** |
| Setup weight | Minimal | Minimal | Minimal | **Heavy (2–4GB)** |
| Files leave machine | No | No | No | **No — fully local** |
| GPU needed | No | No | No | Recommended |

---

## Observations Log

| Resume file | Format | PDF type | Time | Device | Headings | Tables | Block types | Notes |
|-------------|--------|----------|------|--------|----------|--------|-------------|-------|
|             |        |          |      |        |          |        |             |       |

---

## When Marker is the Right Choice for Your ATS

**Use Marker when:**
- Your candidate pool submits graphic/designed resumes (Canva, Adobe templates)
- You need to handle scanned PDF resumes without setting up Tesseract separately
- You need DOCX + PDF + image support from a single local tool
- Privacy is critical and files cannot leave your infrastructure
- You have GPU available (batch processing becomes very fast)

**Consider alternatives when:**
- All resumes are clean native PDFs → `pymupdf4llm` is faster and simpler
- No GPU available and volume is high → CPU Marker is too slow for production
- Commercial licensing cost is a constraint
- Install complexity is a problem for your deployment environment
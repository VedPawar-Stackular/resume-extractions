# 03 — pymupdf4llm

**Tool:** [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm) by Artifex / PyMuPDF  
**Type:** Library (local, no API key, no GPU needed)  
**Version:** 0.0.20+  
**Python:** 3.10+

---

## What pymupdf4llm Is

A high-level wrapper around PyMuPDF (fitz) built specifically for LLM pipelines. 
Unlike MarkItDown which uses `pdfminer.six` (a text stripper), pymupdf4llm reads 
the actual PDF drawing instructions — vectors, fonts, bounding boxes — and 
reconstructs semantic document structure from them.

This is the **direct answer to MarkItDown's PDF weakness**.

---

## How It Differs From MarkItDown (PDF)

| Capability              | MarkItDown (pdfminer.six) | pymupdf4llm          |
|-------------------------|--------------------------|----------------------|
| Heading detection       | ✗ None                   | ✓ Font-size mapping  |
| Multi-column layout     | ✗ Merges columns         | ✓ Reads column order |
| Table → Markdown table  | ✗ Flat text rows         | ✓ Pipe table syntax  |
| Scanned PDF (OCR)       | ✗ Empty output           | ✓ Auto Tesseract OCR |
| Bold / italic           | ✗ Stripped               | ✓ Preserved          |
| Page chunks + metadata  | ✗ Not supported          | ✓ Built-in           |
| DOCX support            | ✓ (mammoth)              | ✗ Pro only           |
| Speed (native PDF)      | ~0.12s/page              | ~0.10–0.15s/page     |

---

## How Heading Detection Works

pymupdf4llm uses an `IdentifyHeaders` module that scans the entire document 
first, builds a frequency map of font sizes, and assigns Markdown heading levels:

```
Most common (body) font size: 10pt  →  regular text
12pt  →  ## (h2)
14pt  →  # (h1)
```

**Implication for resumes:** Resumes that use the same font size for section 
headings and body text will get NO heading detection. This is a real limitation 
for graphic/designed resumes where headings are differentiated by color or 
position rather than size.

---

## How OCR Works

pymupdf4llm analyzes each page before extracting. If a page has no selectable text, OCR is triggered automatically for that page. Pages with clean native text are never sent through OCR. The hybrid approach reduces OCR processing time by around 50% compared to full-document OCR.

Tesseract must be installed separately as a system binary:

```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Then install Python binding
pip install pytesseract
```
# For windows, use this link to get steps to install 
[Tesseract](https://gemini.google.com/share/b8699619e39c)
---

## Setup

```bash
# 1. Install Tesseract (system-level, see above)

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Verify
python -c "import pymupdf4llm; print('pymupdf4llm ready')"
```

---

## Running Extraction

```bash
# Single resume
python extract.py ../sample_resumes/resume_native.pdf

# Whole sample folder
python extract.py ../sample_resumes/

# With per-page chunk preview in console
python extract.py ../sample_resumes/ --verbose

# Output files:
#   outputs/<stem>.md             ← full markdown (self-documenting header)
#   outputs/<stem>.chunks.json   ← per-page chunks with metadata
#   outputs/<stem>.meta.json     ← timing + quality signals per file
#   metrics.json                 ← scorecard (used by compare.py)
```

---

## Output Format

### `.md` file
Full markdown with heading hierarchy, tables, bold/italic:
```markdown
# Rahul Sharma

rahul@email.com | Hyderabad

## Work Experience

### Lead Backend Engineer — CloudStack Solutions

- Led migration to FastAPI microservices...
- **Technologies:** Python, FastAPI, Kafka

## Skills

| Category  | Skills                          |
|-----------|----------------------------------|
| Languages | Python, Go, SQL                 |
| Cloud     | AWS, Docker, Kubernetes         |
```

### `.chunks.json` file
Per-page structured output for RAG pipelines:
```json
[
  {
    "page": 1,
    "char_count": 1823,
    "metadata": { "page": 0, "file_path": "...", ... },
    "preview": "Rahul Sharma rahul@email.com..."
  }
]
```

---

## Known Limitations

| Limitation | Impact on ATS |
|-----------|--------------|
| DOCX not supported (free version) | Need separate tool for Word resumes |
| Heading detection needs font-size contrast | Graphic/designed resumes may produce flat output |
| Tesseract must be installed separately | Extra setup step for scanned PDF support |
| CID glyphs from embedded fonts | Occasional garbled characters in designer resumes |
| Image resumes (.jpg/.png) not supported | Route to Marker or MinerU |

---

## Observations Log

*(Fill in as you run tests)*

| Resume file           | Format | PDF type         | Headings | Tables | Time      | Notes |
|-------------          |--------|----------        |----------|--------|------     |-------|
|Sample_Image_resume.pdf|.pdf     |.png image inside|          |        |~2 seconds|       |

---

## vs MarkItDown — Key Verdict

For **PDF resumes**, pymupdf4llm is clearly superior: headings, columns, and 
tables all survive. The only area where MarkItDown wins is **DOCX** support, 
since pymupdf4llm doesn't handle Word documents in the free version. In 
production, pair pymupdf4llm (for PDFs) with MarkItDown or python-docx 
(for DOCX) to cover both cases.
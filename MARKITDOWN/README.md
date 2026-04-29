# 05 — MarkItDown

**Tool:** [Microsoft MarkItDown](https://github.com/microsoft/markitdown)  
**Type:** Library (local, no API key needed)  
**Version:** 0.1.4+  
**Python:** 3.10+

---

## What MarkItDown Is

Microsoft's open-source universal document-to-Markdown converter. Launched late 2024, it wraps existing parsing libraries into a single unified API. It is **not** a novel extraction engine — it is a smart router that delegates to the right library per format.

| Format | MarkItDown uses internally |
|--------|---------------------------|
| PDF    | `pdfminer.six`            |
| DOCX   | `mammoth`                 |
| XLSX   | `pandas`                  |
| PPTX   | `python-pptx`             |
| Images | LLM vision (optional)     |
| HTML   | `BeautifulSoup`           |

---

## Setup

```bash
# 1. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify
python -c "from markitdown import MarkItDown; print('MarkItDown ready')"
```

---

## Running Extraction

```bash
# Single resume file
python extract.py ../sample_resumes/resume_native.pdf

# Entire sample folder (recommended — runs all at once)
python extract.py ../sample_resumes/

# Output will appear in:
#   outputs/<filename>.md          ← the extracted markdown
#   outputs/<filename>.meta.json   ← timing + warnings per file
#   metrics.json                   ← summary scorecard (read by compare.py)
```

---

## What to Expect Per Format

### Native PDF ⚠ Weak
MarkItDown uses `pdfminer.six` under the hood. This means:
- Text content is extracted but **heading structure is lost** — no `#`, `##` in output
- Multi-column layouts often **merge into garbled text** (columns read left-to-right across the page, not top-to-bottom per column)
- Tables in PDFs come out as **plain text rows**, not Markdown tables
- The output is essentially a flat dump of the text content

### Scanned PDF ✗ Not supported
MarkItDown has **no built-in OCR**. Scanned PDFs (image-only, no text layer) produce empty or garbage output. The script detects this before extraction and logs a warning.

*The `markitdown-ocr` plugin exists and adds LLM vision OCR, but it requires an OpenAI/Azure API key and is not tested here — we want to evaluate the baseline tool.*

### DOCX ✓ Best format for this tool
MarkItDown delegates to `mammoth`, which is specifically built to preserve semantic document structure. Headings, bold/italic, lists, and tables all survive the conversion in reasonable shape. This is where MarkItDown genuinely shines.

### Images (JPG/PNG) ⚠ Limited without LLM
Without an LLM vision client configured, image resumes will produce minimal or no output. The script will run and log the result honestly.

---

## Output File Format

Each `.md` output file includes a comment header with metadata, followed by the raw extracted content:

```
<!-- MarkItDown Extraction Output
     File    : resume.pdf
     Format  : .pdf | PDF type: native
     Tool    : markitdown 0.1.4+
     Time    : 0.43s
     Chars   : 1823
-->
> ⚠ No Markdown headings found in PDF output...

[extracted text here]
```

---

## Known Limitations (documented for the comparison)

| Limitation | Impact on ATS |
|-----------|--------------|
| No heading detection in PDFs | LLM may miss section boundaries (Experience vs Education) |
| No multi-column PDF support | Skills and experience columns merge — high confusion risk |
| No built-in OCR | Scanned CVs completely fail |
| Table extraction unreliable for PDFs | Skills matrices, education tables lost |
| DOCX quality >> PDF quality | Inconsistent results depending on how the candidate submitted |

---

## Observations Log

*(Fill this in as you run the tests — use it for your team's compare.py notes)*

| Resume file | Format | Status | Notes |
|-------------|--------|--------|-------|
|             |        |        |       |

---

## When MarkItDown Makes Sense

- Your ATS **primarily receives DOCX** resumes
- You need a **zero-config, no-API-key** solution
- You are doing quick prototyping and can tolerate PDF limitations
- You pair it with a separate OCR step for scanned files

## When to pick a different tool

- Most resumes come as PDFs → use **pymupdf4llm** or **Marker** instead
- You need heading/section detection from PDFs → use **pymupdf4llm**
- You need scanned PDF support → use **Marker** or **MinerU**
- You need the absolute best quality and can pay per page → use **LlamaParse**
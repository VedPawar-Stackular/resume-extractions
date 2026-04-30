# 04 — PyMuPDF (Raw Baseline)

**Tool:** [PyMuPDF](https://pymupdf.readthedocs.io/) (`import pymupdf`)  
**Type:** Library (local, no API key, no GPU)  
**Version:** 1.24.0+  
**Python:** 3.10+

---

## Role in This Evaluation

This folder is the **baseline**. It answers: *"what does PyMuPDF give you with zero
post-processing, and how far can you get by writing your own structure inference?"*

pymupdf4llm (folder `03_pymupdf4llm`) is built directly on top of this same engine.
Comparing these two folders tells you exactly what pymupdf4llm adds on top of raw PyMuPDF.

---

## Extraction Modes

This script runs **two passes** per resume and produces separate output files for each:

### Mode 1 — RAW (`.raw.txt`)
```python
page.get_text("text", sort=True)
```
One call per page. Zero post-processing. This is the honest floor — exactly what
you get if you write a 5-line PyMuPDF script.

**What it gives you:** text content, roughly in reading order.  
**What it doesn't give you:** headings, tables, bold/italic, column ordering.

### Mode 2 — INFERRED (`.inferred.md`)
```python
page.get_text("dict", sort=True, flags=...)
```
Extracts every span with its font name, font size, bold/italic flags, and
bounding box. Then applies our own logic to reconstruct Markdown:

- **Heading inference** — builds a font-size frequency map across the whole
  document; the most common size = body text; larger sizes get `#`, `##`, `###`
- **Bold/italic** — reads font flags and maps them to `**bold**`, `*italic*`
- **Block grouping** — groups spans into lines and blocks for paragraph structure

**What it gives you:** a credible Markdown with headings and formatting.  
**What it still can't do:** table detection, multi-column splitting, OCR.

---

## Understanding `get_text()` Modes

<cite index="15-1">PyMuPDF's `page.get_text()` accepts several output modes:</cite>

| Mode | What you get | Use case |
|------|-------------|----------|
| `"text"` | Plain text, reading order | Quickest baseline |
| `"blocks"` | Text blocks with bounding boxes | Paragraph detection |
| `"words"` | Individual words with positions | Spatial analysis |
| `"dict"` | Blocks → lines → spans with font, size, flags, bbox | **Our inferred mode** |
| `"rawdict"` | Like dict but with per-character positions | Deep analysis |

We use `"dict"` because it gives us the font metadata needed for heading inference.

---

## Font Flags (how bold/italic is detected)

```python
FLAG_ITALIC = 1 << 1   # bit 1 of the flags integer
FLAG_BOLD   = 1 << 4   # bit 4 of the flags integer

is_bold   = bool(flags & FLAG_BOLD)   or "bold"    in font_name.lower()
is_italic = bool(flags & FLAG_ITALIC) or "italic"  in font_name.lower()
#                                      or "oblique" in font_name.lower()
```

Both the flags bitmask AND the font name string are checked because some PDFs
encode bold/italic in the font name string instead of the flags field.

---

## Heading Inference — How It Works

```
1. Collect all span font sizes from the entire document
2. Find the most common font size → this is the body text size
3. Any size > body size gets assigned a heading level:
      largest  → #
      second   → ##
      third    → ###
      (more levels → still ###)
4. Apply prefix when building Markdown output
```

**When this works:** Most standard resume templates have visibly larger section headers.  
**When it fails:** Resumes where headings are the same font size as body but
differentiated by ALL-CAPS, colour, or spacing — the inference assigns them no heading level.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python -c "import pymupdf; print('PyMuPDF', pymupdf.__version__, 'ready')"
```

---

## Running Extraction

```bash
# Single file
python extract.py ../sample_resumes/resume.pdf

# Folder
python extract.py ../sample_resumes/

# Show span-level debug (font size, bold flag, inferred heading level per span)
python extract.py ../sample_resumes/ --verbose

# Output files per resume:
#   outputs/<stem>.raw.txt        ← Mode 1: zero-processing floor
#   outputs/<stem>.inferred.md   ← Mode 2: our manual reconstruction
#   outputs/<stem>.meta.json     ← span metadata, font map, timing
#   metrics.json                 ← scorecard for compare.py
```

---

## Reading the Outputs

### `*.raw.txt` — the floor
Plain text. Use this to answer: *"does the text content come through at all?"*
Expect no headings, no formatting, possibly garbled order on multi-column layouts.

### `*.inferred.md` — our reconstruction
Markdown with `##` headings and `**bold**`. Use this to answer:
*"how far can you get without pymupdf4llm?"*
The header comment block shows the heading_map that was inferred:
```
# Heading map (size→level): {'14.0': '# ', '12.0': '## ', '10.0': ''}
```

### `*.meta.json` — span analysis
Full per-span metadata including all font sizes detected, which size was
inferred as body, and the complete heading map. Useful for debugging why
a resume's headings did or didn't get detected.

---

## Observations Log

| Resume file | PDF type | Raw chars | Inferred headings | Font sizes found | Notes |
|-------------|----------|-----------|-------------------|-----------------|-------|
|             |          |           |                   |                 |       |

---

## What This Tells You About pymupdf4llm

After running both `04_pymupdf` and `03_pymupdf4llm` on the same files, compare:

| Signal | 04_pymupdf raw | 03_pymupdf4llm |
|--------|---------------|----------------|
| Heading count | Our inference | IdentifyHeaders (more accurate) |
| Table rows | 0 (not implemented) | Pipe table syntax |
| Multi-column | Partial (sort=True) | Full column reconstruction |
| Speed | Fastest | Slightly slower (layout analysis pass) |
| Code required | ~200 lines to get structure | 1 line (`to_markdown()`) |

The gap between raw inferred markdown and pymupdf4llm output is the value that
pymupdf4llm's layout analysis module adds.
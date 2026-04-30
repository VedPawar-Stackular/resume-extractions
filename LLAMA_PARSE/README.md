# 06 — LlamaParse

**Tool:** [LlamaParse](https://github.com/run-llama/llama_parse) by LlamaIndex  
**Type:** Cloud API (files sent to LlamaIndex servers — NOT local)  
**Version:** 0.6.0+  
**Python:** 3.10+  
**Requires:** API key from [cloud.llamaindex.ai](https://cloud.llamaindex.ai)

---

## ⚠ Before You Run This

**LlamaParse is fundamentally different from every other tool in this evaluation.**

All other tools (PyMuPDF, pymupdf4llm, MarkItDown, Marker, MinerU) run
100% locally. Your documents never leave your machine.

LlamaParse **uploads your files to LlamaIndex's cloud servers** for processing.
For a production HR/ATS system handling real candidate PII (names, addresses,
contact details), you must:

1. Review their [Privacy Policy](https://www.llamaindex.ai/privacy-policy)
2. Review their [Terms of Service](https://www.llamaindex.ai/terms-of-service)
3. Confirm data retention policies with their sales team
4. Check if a VPC/on-premise deployment (LlamaCloud enterprise) is needed

For **this evaluation** with synthetic test resumes, there is no concern.
For **production deployment** with real candidate data, this is a critical decision.

---

## Why LlamaParse Is In This Evaluation

LlamaParse uses an **LLM to semantically understand** the document — not rule-based
layout analysis. This is a fundamentally different architecture from every other tool:

| Approach | How it works |
|---|---|
| PyMuPDF, MarkItDown | Read PDF drawing commands; detect text by coordinates |
| pymupdf4llm | Same + font-size frequency analysis for headings |
| Marker, MinerU | Visual layout models (computer vision) |
| **LlamaParse** | **LLM reads and understands document meaning** |

The practical implication: LlamaParse doesn't need font-size contrast to detect
headings, or ruling lines to detect tables, or `sort=True` to get column order right.
It understands that "WORK EXPERIENCE" is a section heading because it knows what
a resume looks like — not because the font is 14pt instead of 10pt.

---

## Parse Modes & Cost

LlamaParse uses a credit system. **1,000 credits = $1.25.**

| Mode flag | Credits/page | What it uses | Best for |
|---|---|---|---|
| `parse_without_llm` | 1 | No AI, rule-based only | Cost comparison baseline |
| `cost_effective` | 3 | Lightweight LLM | **Default in this eval** |
| `agentic` | ~20 | Stronger LLM + multi-pass | Complex layouts |
| `agentic` + Sonnet | ~90 | Anthropic Sonnet | Maximum quality |

A typical 2-page resume at `cost_effective` = **6 credits = $0.0075**.

New accounts get **10,000 free credits** — enough to test ~1,600 pages.

---

## The ATS Parsing Instruction

One of LlamaParse's unique features: you can provide **natural language instructions**
that guide the LLM's extraction. This script uses an ATS-specific prompt that tells it:

- Use `##` for major sections, `###` for job titles/degrees
- Never omit or summarise any bullet point
- Convert skill tables to Markdown pipe tables
- Preserve all contact details, certifications, project details

This is something no local tool can do. The instruction directly shapes the output
quality for our ATS use case. Test with and without the instruction to see the delta.

---

## Setup

```bash
# 1. Get API key from: https://cloud.llamaindex.ai (free account, 10k credits)

# 2. Set environment variable
export LLAMA_CLOUD_API_KEY="llx-xxxxxxxxxxxxxxxxxxxx"

# 3. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify
python -c "from llama_parse import LlamaParse; print('LlamaParse ready')"
```

---

## Running Extraction

```bash
# Single resume — markdown output (default, recommended)
python extract.py ../sample_resumes/resume.pdf

# Whole sample folder
python extract.py ../sample_resumes/

# Compare markdown vs plain text output side by side
python extract.py ../sample_resumes/resume.pdf --both-modes

# Use agentic mode for hardest layouts (costs more)
python extract.py ../sample_resumes/ --mode agentic

# No-AI mode — baseline for cost comparison (similar quality to MarkItDown)
python extract.py ../sample_resumes/ --mode parse_without_llm
```

**Expected speed:** 10–30 seconds per file. This is normal — it's a cloud API call
with LLM inference on the other end. Not suitable for synchronous single-resume UX.

---

## Output Files

```
outputs/
  <stem>.md            ← LLM-structured markdown (default)
  <stem>.meta.json     ← timing, cost estimate, quality signals
  [<stem>.md.md]       ← when --both-modes: markdown output
  [<stem>.txt.txt]     ← when --both-modes: plain text output
metrics.json           ← scorecard for compare.py
```

### Expected output quality (markdown mode)

Because of the ATS parsing instruction, output should look like:

```markdown
## Contact Information
**Rahul Sharma** | rahul.sharma@email.com | +91-9988776655 | Hyderabad

## Professional Summary
Backend engineer with 5 years of experience...

## Work Experience

### Lead Backend Engineer — CloudStack Solutions
**March 2021 – Present**

- Led migration of monolithic Django app to FastAPI microservices (12 services)
- Designed event-driven pipeline with Kafka processing 4M events/day
- **Technologies:** Python, FastAPI, Kafka, PostgreSQL

## Skills

| Category  | Technologies                              |
|-----------|-------------------------------------------|
| Languages | Python, Go, SQL, Bash                     |
| Cloud     | AWS (ECS, RDS, SQS), Docker, Kubernetes  |
```

Compare this against what PyMuPDF raw and MarkItDown produce from the same file.

---

## Observations Log

| Resume file | Format | Mode | Time | Headings | Tables | Cost | Notes |
|-------------|--------|------|------|----------|--------|------|-------|
|             |        |      |      |          |        |      |       |

---

## What This Tells You for Your ATS Architecture

**Use LlamaParse when:**
- Resume quality and information completeness are the top priority
- You're processing resumes in batch (async — the latency is acceptable)
- You can accept per-page cost at your volume
- You need the same tool to handle PDF + DOCX + images uniformly
- You want custom extraction instructions without writing any code

**Use local tools (pymupdf4llm + python-docx) when:**
- Resume data cannot leave your infrastructure
- You need sub-second extraction for real-time UX
- Volume is high enough that per-page costs are prohibitive
- You want zero dependency on a third-party cloud service

**The hybrid pattern (recommended for production ATS):**
```
Incoming resume
      ↓
  pymupdf4llm (local, fast, free) — native PDFs
      ↓
  Falls back to LlamaParse — if local extraction quality is low
  (detected by heading_count < 2 or char_count < 300 heuristics)
      ↓
  Store canonical extracted markdown in your DB
      ↓
  Score against JD via your LLM
```
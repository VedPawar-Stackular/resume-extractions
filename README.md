# Resume Extraction Evaluation

This repository evaluates multiple resume extraction tools to identify the best pipeline for an AI-powered ATS.

## Evaluated Tools

1.  **[PyMuPDF4LLM](file:///c:/Stackular-Project-1/resume-extractions/PYMU4PDFLLM)**: **Recommended engine.** Best balance of speed (4.4s) and Markdown quality.
2.  **[Marker](file:///c:/Stackular-Project-1/resume-extractions/MARKER)**: Elite layout detection and OCR. Best for complex resumes (requires GPU).
3.  **[LlamaParse](file:///c:/Stackular-Project-1/resume-extractions/LLAMA_PARSE)**: Semantic, LLM-based cloud extraction. Best for accuracy.
4.  **[PyMuPDF](file:///c:/Stackular-Project-1/resume-extractions/PYMUPDF)**: High-speed raw text baseline.
5.  **[MarkItDown](file:///c:/Stackular-Project-1/resume-extractions/MARKITDOWN)**: Optimized for `.docx` and office formats.

## Conclusion

For a high-volume ATS processing 1000s of resumes, the optimal pipeline is:
**Native PDFs/OCR PDFs** → [PyMuPDF4LLM](file:///c:/Stackular-Project-1/resume-extractions/PYMU4PDFLLM) → **Markdown Output** → **LLM Scoring**.

For a detailed analysis, see the [Final Extraction Report](file:///C:\Stackular-Project-1\resume-extractions\resume_extraction_analysis_report.md).

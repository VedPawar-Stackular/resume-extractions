## MY Inference about the tool



### 1. For Native PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\AKSHAY_KUCHHAL_2-Copy-Copy.pdf

==============================================================
  pymupdf4llm Resume Extractor
  Target    : C:\Stackular-Project-1\resume-extractions\sample_resumes\AKSHAY_KUCHHAL_2-Copy-Copy.pdf
  Files     : 1 resume(s) found
  Tesseract : ✓ available (OCR enabled)
  Outputs   : C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM\outputs
==============================================================

=== Document parser messages ===
Using Tesseract for OCR processing.

=== Document parser messages ===
Using Tesseract for OCR processing.

  ✓ AKSHAY_KUCHHAL_2-Copy-Copy.pdf
    Format   : .pdf (native)
    Time     : 4.3873s
    Output   : 6637 chars | 114 lines | 1 pages
    Headings : 9 | Tables: 8 rows
    Tesseract: ✓ available

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM\metrics.json
   Total: 1 | OK: 1 | Empty: 0 | Errors: 0
   Avg time     : 4.3873s
   Avg headings : 9.0 | Avg table rows: 8.0

==============================================================
  Done. Check outputs/ for .md, .chunks.json, .meta.json files.
  Compare with other tools using: python ../compare.py
==============================================================



### 2. For OCR PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\Himanshu_Vishwakarma_2.pdf    

==============================================================
  pymupdf4llm Resume Extractor
  Target    : C:\Stackular-Project-1\resume-extractions\sample_resumes\Himanshu_Vishwakarma_2.pdf
  Files     : 1 resume(s) found
  Tesseract : ✓ available (OCR enabled)
  Outputs   : C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM\outputs
==============================================================

=== Document parser messages ===
Using Tesseract for OCR processing.
OCR on page.number=0/1.
OCR on page.number=1/2.

=== Document parser messages ===
Using Tesseract for OCR processing.
OCR on page.number=0/1.
OCR on page.number=1/2.

  ✓ Himanshu_Vishwakarma_2.pdf
    Format   : .pdf (scanned)
    Time     : 12.6008s
    Output   : 8121 chars | 114 lines | 2 pages
    Headings : 10 | Tables: 0 rows
    Tesseract: ✓ available

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM\metrics.json
   Total: 1 | OK: 1 | Empty: 0 | Errors: 0
   Avg time     : 12.6008s
   Avg headings : 10.0 | Avg table rows: 0.0

==============================================================
  Done. Check outputs/ for .md, .chunks.json, .meta.json files.
  Compare with other tools using: python ../compare.py
==============================================================

(venv) PS C:\Stackular-Project-1\resume-extractions\PYMU4PDFLLM> 
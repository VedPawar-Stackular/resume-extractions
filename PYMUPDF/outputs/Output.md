## MY Inference about the tool



### 1. For Native PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\PYMUPDF> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\AKSHAY_KUCHHAL_2-Copy-Copy.pdf          

==============================================================
  PyMuPDF Raw Baseline Extractor
  Target  : C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\AKSHAY_KUCHHAL_2-Copy-Copy.pdf
  Files   : 1 resume(s) found
  Engine  : PyMuPDF 1.27.2.3
  Outputs : C:\Stackular-Project-1\resume-extractions\PYMUPDF\outputs
  Modes   : RAW (.raw.txt) + INFERRED (.inferred.md)
==============================================================

  ✓ AKSHAY_KUCHHAL_2-Copy-Copy.pdf
    Format     : .pdf (native)
    Time       : 0.2027s
    Raw output : 6588 chars | 69 lines
    Inferred md: 6476 chars | 1 headings
    Font sizes : [13.0, 11.0, 10.7, 10.6, 10.0] (body=10.0pt)
    Heading map: {'10.0': '', '13.0': '# ', '11.0': '## ', '10.7': '### '}
    Spans      : 203 | Pages: 1

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\PYMUPDF\metrics.json
   Total: 1 | OK: 1 | Empty: 0 | Errors: 0
   Avg time: 0.2027s

==============================================================
  Done. Outputs:
    *.raw.txt      — zero-processing floor
    *.inferred.md  — our manual heading reconstruction
    *.meta.json    — span metadata, font map, timing
    metrics.json   — scorecard for compare.py
==============================================================

(venv) PS C:\Stackular-Project-1\resume-extractions\PYMUPDF> 


### 2. For OCR PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\PYMUPDF> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\Himanshu_Vishwakarma_2.pdf    

==============================================================
  PyMuPDF Raw Baseline Extractor
  Target  : C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\Himanshu_Vishwakarma_2.pdf
  Files   : 1 resume(s) found
  Engine  : PyMuPDF 1.27.2.3
  Outputs : C:\Stackular-Project-1\resume-extractions\PYMUPDF\outputs
  Modes   : RAW (.raw.txt) + INFERRED (.inferred.md)
==============================================================

  ⚠ Himanshu_Vishwakarma_2.pdf
    Format     : .pdf (scanned)
    Time       : 0.3775s
    Raw output : 1 chars | 1 lines
    Inferred md: 0 chars | 0 headings
    Font sizes : [] (body=Nonept)
    Heading map: {}
    Spans      : 0 | Pages: 2
    ⚠  PDF type 'scanned' — scanned pages have no text layer. Raw PyMuPDF has NO built-in OCR. Those pages will be empty. Use pymupdf4llm (with Tesseract) or Marker for scanned support.
    ⚠  Raw output near-empty (1 chars). Scanned PDF — no text layer found. OCR required.

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\PYMUPDF\metrics.json
   Total: 1 | OK: 0 | Empty: 1 | Errors: 0
   Avg time: 0.3775s

==============================================================
  Done. Outputs:
    *.raw.txt      — zero-processing floor
    *.inferred.md  — our manual heading reconstruction
    *.meta.json    — span metadata, font map, timing
    metrics.json   — scorecard for compare.py
==============================================================

(venv) PS C:\Stackular-Project-1\resume-extractions\PYMUPDF> 
## MY Inference about the tool
The tool is very slow for a CPU usage, this tool will take many hours to process 100s to 500s of resumes at once


### 1. For Native PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\MARKER> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\AKSHAY_KUCHHAL_2-Copy-Copy.pdf 

================================================================
  Marker Resume Extractor (visual layout detection)
  Target   : C:\Stackular-Project-1\resume-extractions\sample_resumes\AKSHAY_KUCHHAL_2-Copy-Copy.pdf
  Files    : 1 resume(s) found
  Device   : cpu — CPU (no GPU detected — expect slower processing)
  Use LLM  : NO  — pass --use-llm to enable
  Outputs  : C:\Stackular-Project-1\resume-extractions\MARKER\outputs
  NOTE     : First run downloads ~2–4GB of Surya model weights.
================================================================

  ⟳ Loading Marker models (first run downloads ~2–4GB)...
  ✓ Models loaded in 5.1s

Recognizing Layout:   0%|                                                                                                                                                        | 0/1 [Recognizing Layout: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:27<00Recognizing Layout: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:27<00:00, 27.91s/it]
Running OCR Error Detection: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  5.07it/s]
Detecting bboxes: 0it [00:00, ?it/s]
Detecting bboxes: 0it [00:00, ?it/s]
  ⚠ AKSHAY_KUCHHAL_2-Copy-Copy.pdf
    Format   : .pdf (native)
    Device   : cpu — CPU (no GPU detected — expect slower processing)
    Time     : 30.7263s  (model load excluded)
    Output   : 6431 chars | 76 lines | 0 pages
    Headings : 12 | Tables: 0 rows
    ⚠  Running on CPU (CPU (no GPU detected — expect slower processing)). Marker's Surya models are significantly faster on GPU. Expect 30–120s/page on CPU vs <1s/page on H100. For production ATS batch processing, a GPU instance is strongly recommended.
    ⚠  No block metadata extracted from rendered output. Block-level type analysis unavailable for this file.

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\MARKER\metrics.json
   Total       : 1 | OK: 1 | Errors: 0
   Model load  : 5.10s (one-time per session)
   Avg extract : 30.7263s/file (excl. model load)
   Device      : cpu — CPU (no GPU detected — expect slower processing)

================================================================
  Done. Outputs:
    *.md           ← extracted markdown
    *.blocks.json  ← block-type metadata (SectionHeader, Table...)
    *.meta.json    ← timing, device, quality signals
    metrics.json   ← scorecard for compare.py
================================================================

(venv) PS C:\Stackular-Project-1\resume-extractions\MARKER> 


### 2. For OCR PDFs
(venv) PS C:\Stackular-Project-1\resume-extractions\MARKER> python .\extract.py C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\Himanshu_Vishwakarma_2.pdf    

================================================================
  Marker Resume Extractor (visual layout detection)
  Target   : C:\Stackular-Project-1\resume-extractions\sample_resumes\PDFs\Himanshu_Vishwakarma_2.pdf
  Files    : 1 resume(s) found
  Device   : cpu — CPU (no GPU detected — expect slower processing)
  Use LLM  : NO  — pass --use-llm to enable
  Outputs  : C:\Stackular-Project-1\resume-extractions\MARKER\outputs
  NOTE     : First run downloads ~2–4GB of Surya model weights.
================================================================

  ⟳ Loading Marker models (first run downloads ~2–4GB)...
  ✓ Models loaded in 5.43s

Recognizing Layout: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2/2 [00:45<00:00, 22.83s/it]
Running OCR Error Detection: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 41.27it/s]
Detecting bboxes: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:03<00:00,  3.79s/it]
Recognizing Text:  38%|██████████████████████████████████████████████████▊                                                                                  | 42/110 [04:25<02:51,  2.Recognizing Text: Recognizing Text: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 110/110 [10:49<00:00,  5.90s/it]
Detecting bboxes: 0it [00:00, ?it/s]
  ⚠ Himanshu_Vishwakarma_2.pdf
    Format   : .pdf (scanned)
    Device   : cpu — CPU (no GPU detected — expect slower processing)
    Time     : 705.2757s  (model load excluded)
    Output   : 8092 chars | 160 lines | 0 pages
    Headings : 13 | Tables: 0 rows
    ⚠  Running on CPU (CPU (no GPU detected — expect slower processing)). Marker's Surya models are significantly faster on GPU. Expect 30–120s/page on CPU vs <1s/page on H100. For production ATS batch processing, a GPU instance is strongly recommended.
    ⚠  No block metadata extracted from rendered output. Block-level type analysis unavailable for this file.

📊 Metrics saved → C:\Stackular-Project-1\resume-extractions\MARKER\metrics.json
   Total       : 1 | OK: 1 | Errors: 0
   Model load  : 5.43s (one-time per session)
   Avg extract : 705.2757s/file (excl. model load)
   Device      : cpu — CPU (no GPU detected — expect slower processing)

================================================================
  Done. Outputs:
    *.md           ← extracted markdown
    *.blocks.json  ← block-type metadata (SectionHeader, Table...)
    *.meta.json    ← timing, device, quality signals
    metrics.json   ← scorecard for compare.py
================================================================

(venv) PS C:\Stackular-Project-1\resume-extractions\MARKER> 
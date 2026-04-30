This is the folder where we combine all the resume extraction tools to make the final tool compatible with PDF, Docx, and Images

For eg: MarkItDown is very good for .docx documents, whereas PyMu4PDF is good for PDFs. In this way we need to find a balance between speed and accuracy among tools for each resume format type (.docx, .pdf, .png etc).

As of now these are the following inferences that are made:
1. MarkItDown is perfect for .docx file, not compatible with .pdf and images
2. PyMu4PDFLLM is perfect for Native PDFs(raw text) and Image PDFs(OCR capability is offered). The tool first checks each PDF if it has retrieable text inside, if yes, it does not use OCR functionality, if not, then it uses Tesseract to use OCR and gets the content from the PDF within 2 seconds into a proper .md(Markdown file) with proper headings, sub headings, table analysis, etc
3. PyMy4PDF is perfect for Native PDFs(raw text) only. They **do not** have OCR capabilities, and the output format for the extraction is raw .txt files. They consume 1% less tokens as compared to PyMy4PDFLLM tool. 
4. **LlamaParse** is a cloud-based LLM parser that excels at semantic understanding and handling "impossible" layouts. It uses a vision-based approach and supports custom ATS instructions to shape the output. However, it involves API costs ($3.75/1k pages) and cloud privacy considerations.
5. **Marker** is a powerful visual layout detector that produces high-quality Markdown. It is excellent at bullet preservation and section detection but is extremely slow on CPU (requires GPU for production-ready speeds).

## Tool Comparison Summary

| Tool | Speed (Native) | OCR Support | Output Quality | Recommended Use |
| :--- | :--- | :--- | :--- | :--- |
| **PyMuPDF** | 0.2s | No | Raw Text | Fast indexing |
| **PyMuPDF4LLM** | 4.4s | Yes (Tesseract) | Good Markdown | **Primary Engine** |
| **Marker** | 30s (CPU) | Yes (Surya) | Elite Markdown | Complex Layouts (GPU) |
| **LlamaParse** | 10-30s | Yes (Cloud) | Semantic MD | Managed API / Best Quality |


## Workflow for resume extraction

PDF input -> Convert to Markdown via the final selected tool -> Structring -> Scoring

## Why Markdown, why not raw text
Our pipeline follows a two-stage transformation: Raw File → Markdown → Structured **JSON**. 
This isn't just an extra step; it is a strategic choice to maximize **LLM** accuracy while minimizing costs.
1. Why Markdown is Superior to Raw Text: When we extract text from a resume, we aren't just looking for words; we are looking for context. - Semantic Anchors (Headings): In raw text, *Python* looks the same whether it is under *Skills* or *Hobbies.* Markdown uses # and ## tags to act as anchors. This tells the **LLM** exactly where one section ends and another begins, preventing *context bleed.*
- Visual Weighting: Markdown preserves bolding and * bullets. LLMs are trained to recognize that bolded text (often job titles or key technologies) carries more weight. Bullets help the model distinguish between discrete achievements rather than reading one giant, confusing paragraph.
- Token Efficiency: Unlike **HTML** or **XML**, which are *noisy* with tags like <div> or <span>, Markdown uses the absolute minimum number of characters to convey structure. This keeps our **API** costs low and ensures the **LLM**'s *attention* is on the candidate's experience, not the code.
- The *Two-Column* Fix: Modern tools like pymupdf4llm use Markdown to reconstruct the reading order of complex two-column resumes. Raw text extraction often merges columns, creating *gibberish* sentences that cause LLMs to hallucinate.

Deterministic Scoring: To generate an **ATS** score, we need to compare specific fields (e.g., resume.total_years_exp vs. jd.required_years_exp). **JSON** allows our code to *grab* exactly what it needs without searching through a document. 
Database Readiness: We store the final extraction as a **JSONB** object in our database. This allows us to build a searchable talent pool where HR can filter by specific skills or locations without re-running expensive **LLM** extractions.
*Extract Once, Score Many*: By converting to a standardized **JSON** schema, we only pay for the *Extraction* **LLM** call once. If the Job Description changes, we simply compare the new JD against the existing **JSON** data—saving time and money.


The Bottom Line: We use Markdown to give the **LLM** the best possible *vision* of the resume, and we use **JSON** to turn that vision into a *data point* that can be mathematically scored against a Job Description.
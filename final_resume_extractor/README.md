This is the folder where we combine all the resume extraction tools to make the final tool compatible with PDF, Docx, and Images

For eg: MarkItDown is very good for .docx documents, whereas PyMu4PDF is good for PDFs. In this way we need to find a balance between speed and accuracy among tools for each resume format type (.docx, .pdf, .png etc).

As of now these are the following inferences that are made:
1. MarkItDown is perfect for .docx file, not compatible with .pdf and images
2. PyMu4PDFLLM is perfect for Native PDFs(raw text) and Image PDFs(OCR capability is offered). The tool first checks each PDF if it has retrieable text inside, if yes, it does not use OCR functionality, if not, then it uses Tesseract to use OCR and gets the content from the PDF within 2 seconds into a proper .md(Markdown file) with proper headings, sub headings, table analysis, etc
 
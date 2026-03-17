# Output Examples

Reference for expected output formats by content type.
Claude should use these as targets when deciding how to structure extracted content.

---

## Type 1: Pure Text Page

**Example source**: A blog post, news article, or documentation page with no images or tables.

**Expected output** (saved as Markdown in `content.markdown`):

```markdown
# How Retrieval-Augmented Generation Works

Retrieval-Augmented Generation (RAG) is a technique that combines a language
model with an external knowledge base...

## Why it matters

Traditional language models are limited by their training data cutoff.
RAG addresses this by...

## How it works

1. The user submits a query
2. The system retrieves relevant documents from a vector store
3. The retrieved documents are injected into the model's context
4. The model generates a response grounded in the retrieved content
```

**Notes**:
- Preserve heading hierarchy (H1, H2, H3)
- Keep numbered and bulleted lists intact
- Remove navigation menus, footers, cookie banners — only keep main content
- No screenshots needed for pure text pages

---

## Type 2: Text + Images Page

**Example source**: A product page, tutorial with diagrams, or news article with embedded photos.

**Expected output**:

- Text portions → Markdown (same as Type 1)
- Images → downloaded to `files/` if directly accessible via `<img src>`
- If image content is critical to understanding (e.g. a diagram, chart, infographic) and cannot be downloaded → take a screenshot of that section and save to `screenshots/`

```markdown
# Transformer Architecture Explained

The transformer model introduced the attention mechanism as its core building block.

## Encoder-Decoder Structure

[Image: transformer_diagram.png — saved to files/]

The encoder processes the input sequence while the decoder generates the output...

## Self-Attention

Self-attention allows each token to attend to all other tokens in the sequence...
```

**Notes**:
- Insert a placeholder line `[Image: filename — saved to files/]` in the Markdown where an image appeared
- Do not attempt to describe image content unless OCR/vision was used as fallback
- Tables found on the page → see Type 4

---

## Type 3: Pure Image Page (or Canvas-Rendered)

**Example source**: A page where all content is rendered as images, canvas elements, or SVG (e.g. some dashboards, interactive maps, certain paywalled articles).

**Expected output**:

- Full-page screenshot → saved to `screenshots/`
- OCR text extracted from screenshot → saved as Markdown in `content.markdown`

```markdown
<!-- Extracted via OCR from screenshot_20240101_120000.png -->

Q3 2024 Financial Results

Total Revenue: $4.2B
Operating Income: $890M
Net Margin: 21%

Key highlights:
- Cloud segment grew 34% year-over-year
- International revenue now represents 41% of total
```

**Notes**:
- OCR output is imperfect — preserve it as-is, do not try to clean up or infer missing words
- Always note in the Markdown header that content was extracted via OCR and from which screenshot file
- If OCR yields nothing useful (e.g. the page is purely graphical with no text), record `status = "restricted"` in the DB and note it in the final report

---

## Type 4: Page with Tables

**Example source**: A comparison page, data report, pricing table, or any page with `<table>` elements.

**Expected output**:

Tables are extracted separately by `parse._extract_tables()` and converted to Markdown table format.

```markdown
## Pricing Comparison

| Plan       | Price/month | Storage | Users    | Support      |
|------------|-------------|---------|----------|--------------|
| Free       | $0          | 5 GB    | 1        | Community    |
| Pro        | $12         | 50 GB   | 5        | Email        |
| Business   | $49         | 500 GB  | Unlimited| Priority     |
| Enterprise | Custom      | Custom  | Unlimited| Dedicated    |
```

**Notes**:
- Tables are appended at the end of the page's Markdown content, after the main text
- If a table is the primary content of the page (e.g. a data export), it should be the main body of the Markdown
- Nested tables (tables inside tables) — flatten to the outer table structure, inner content as plain text in cells

---

## Type 5: Direct File Download

**Example source**: A URL pointing directly to a PDF, CSV, zip, image, or other binary file.

**Expected output**:

- File downloaded directly to `files/`
- No Markdown content extracted
- DB record: `page_type = "file"`, `status = "success"`, path recorded in `files` table

**Notes**:
- File type is inferred from `Content-Type` header, not just the URL extension
- For PDFs: do not attempt text extraction — download the raw file. Text extraction from PDFs is out of scope for this skill.
- Filename: use the last segment of the URL path. If ambiguous, use `file_<timestamp>.<ext>`

---

## Type 6: Mixed Page (Text + Tables + Images)

**Example source**: A research report page, Wikipedia article, or detailed product spec page.

**Expected output**: combine all of the above in document order:

```markdown
# NVIDIA H100 GPU Specifications

The H100 is NVIDIA's flagship data center GPU based on the Hopper architecture...

## Performance

| Workload        | H100 SXM | H100 PCIe | A100 SXM  |
|-----------------|----------|-----------|-----------|
| FP32            | 60 TFLOPS| 51 TFLOPS | 19.5 TFLOPS|
| FP16 Tensor     | 1979 TFLOPS| 1513 TFLOPS | 312 TFLOPS|
| Memory Bandwidth| 3.35 TB/s| 2 TB/s    | 2 TB/s    |

## Architecture Diagram

[Image: hopper_architecture.png — saved to files/]

## Memory

The H100 features 80GB of HBM3 memory...
```

**Notes**:
- Preserve the original document order (text, then table, then image placeholder, as they appeared on the page)
- Each section should flow naturally — don't group all tables at the end if they appeared mid-article

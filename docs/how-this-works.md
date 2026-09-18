# How it Works

Legi-Assist operates as a multi-stage data pipeline designed to transform raw legislative documents into structured, actionable insights. Each stage is managed by an idempotent state tracker to ensure efficiency and reliability.

## Pipeline Stages

### 1. Download
The pipeline begins by fetching the master legislation list from the Maryland General Assembly (MGA) website. It identifies new or updated bills and downloads the associated PDF files, including:
- The main bill text.
- Any adopted amendments.
- Fiscal and policy notes.

### 2. Convert
Raw PDFs are converted into high-quality Markdown. A specialized conversion process identifies and preserves formatting, particularly tracking strikeouts (marked as `~~text~~`). This ensures that the LLMs in later stages can accurately distinguish between proposed and removed language.

### 3. Amend
Maryland legislation is often updated via amendments. In this stage, the pipeline uses an LLM to merge adopted amendments into the original bill text. This creates a "current" version of the bill that reflects its most recent state, providing a more accurate basis for analysis.

### 4. QA (Quality Assurance & Analysis)
The "current" bill text and its fiscal note are analyzed by an LLM to extract policy-relevant information. This includes:
- **Plain-English Summary**: A brief, accessible explanation of the bill's intent.
- **Fiscal Impact**: Estimation of financial allocations, mandates, or revenue changes.
- **Agency Relevance**: Identifying which Maryland State agencies are most impacted by the bill, assigned a relevance rating from 1 to 5.
- **Stakeholders**: Identifying populations or entities affected by the legislation.

### 5. Export
The final results are aggregated into a unified JSON file (`frontend_data.json`). This file serves as the data source for the Vue.js frontend, allowing users to browse, filter, and search through the processed legislative data.

## State Management
The pipeline's progress is tracked in `pipeline_state.json` for each session. This file stores hashes of the source documents and the results of each stage. If a source file hasn't changed, the pipeline skips the corresponding stages, significantly reducing processing time and LLM API usage.

## Technical Stack
- **Language**: Python 3.10+
- **PDF Processing**: PyMuPDF
- **LLM Integration**: Google Gemini, OpenAI GPT, and Ollama
- **Frontend**: Vue.js with Tailwind CSS and the Maryland Web Design System (MDWDS)

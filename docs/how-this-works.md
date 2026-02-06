# How This Works

Legi-Assist automates the lifecycle of legislative data analysis for the Maryland General Assembly. The process involves several key stages, from data acquisition to AI-powered insights.

## Workflow Overview

The following steps outline the typical workflow of the toolkit:

### 1. Data Acquisition
The process begins with **`download_legislation.py`**. This script:
- Fetches bill metadata (numbers, titles, sponsors, etc.) from the Maryland General Assembly website for a specified session year.
- Downloads the official PDF documents for each bill.
- Identifies and downloads any adopted amendments in PDF format.
- Saves the metadata into a structured CSV file (`legislation.csv`).

### 2. Text and Markdown Extraction
Once the PDFs are downloaded, they need to be converted into machine-readable formats for analysis.
- **`leg_to_basic_txt.py`**: Converts bill PDFs into plain text files. This is useful for simple keyword searches and token counting.
- **`leg_to_md.py`**: Converts PDFs into Markdown format. Crucially, this script attempts to preserve document structure and formatting, such as identifying struck-through text (often used in legislation to indicate removed language).

### 3. Amendment Processing
Legislation often changes during a session. **`amend_leg_md.py`** leverages Large Language Models (specifically Google Gemini) to:
- Take the original bill's Markdown text.
- Analyze the Markdown of adopted amendments.
- Produce an updated "amended" Markdown file that reflects the changes proposed in the amendments.

### 4. Cost and Token Estimation
Before performing large-scale AI analysis, **`count_tokens.py`** can be used to:
- Scan all processed text files.
- Calculate the total number of tokens.
- Estimate the cost of processing these files using various LLM providers (like OpenAI's `o3`).

### 5. AI-Powered Analysis (QA)
The final stage of the pipeline is **`leg_qa.py`**. This script uses LLMs (Gemini, OpenAI, or Ollama) to:
- Read the processed Markdown of each bill.
- Answer a set of predefined, policy-relevant questions (e.g., "What is the funding allocated?", "Who are the stakeholders?").
- Output these answers into a comprehensive CSV file (`legislation_model_responses.csv`).

## Data Storage
All data is organized by session year within the `data/` directory:
- `pdf/`: Original PDF files.
- `basic_txt/`: Plain text versions.
- `md/`: Markdown versions (original and amended).
- `csv/`: Metadata and AI-generated responses.

## Frontend Visualization
The `index.html` file in the root directory provides a web-based interface to browse the results of the analysis, allowing users to search bills and view the AI-generated summaries and answers.

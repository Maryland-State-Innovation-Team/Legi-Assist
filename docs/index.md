# Legi-Assist

Legi-Assist is an automated toolkit for collecting, processing, and analyzing Maryland General Assembly legislation. It transforms legislative PDFs into structured, machine-readable data and leverages Large Language Models (LLMs) to extract policy-relevant insights, such as funding impacts and stakeholder analysis.

## Core Features

- **Automated Data Sync**: Connects nightly to the Maryland General Assembly (MGA) to download and index the latest bill texts, adopted amendments, and fiscal notes.
- **AI-Enhanced Analysis**: Uses LLMs to interpret complex legislative PDFs—specifically handling strikethroughs and amendments—to generate plain-language summaries and fiscal impact analyses.
- **Agency Relevance Scoring**: Evaluates every introduced bill against grounded descriptions of state entities to help agencies filter relevant legislation.
- **Idempotent Pipeline**: A robust state-tracking system ensures that only new or updated bills are processed, saving time and API costs.

## Getting Started

To get started with Legi-Assist, please refer to the [Installation](index.md#installation) and [Usage](index.md#usage) sections below.

## Installation

1. Clone the repository and navigate to the root directory.
2. Create and activate a virtual environment:

   **On Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   **On macOS/Linux:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in a `.env` file (see `.env-example`):
   ```
   GEMINI_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ```

## Usage

### Running the Pipeline

The main entry point is `run_pipeline.py`. It manages all stages of the process.

```bash
python run_pipeline.py --year 2026 --model-family gemini
```

**Arguments:**
- `--year`: The legislative session year (default: 2026).
- `--model-family`: The LLM provider to use (`gemini`, `gpt`, or `ollama`).
- `--model`: Specific model name (default: `gemini-3-flash-preview`).
- `--debug`: Limits processing to the first 10 bills for testing.

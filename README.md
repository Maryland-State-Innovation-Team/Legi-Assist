# Legi-Assist

Legi-Assist is an automated toolkit for collecting, processing, and analyzing Maryland General Assembly legislation. It transforms legislative PDFs into structured, machine-readable data and leverages LLMs to extract policy-relevant insights, such as funding impacts and stakeholder analysis.

## Architecture Overview

The repository is structured as a robust data pipeline, managed by an idempotent state tracker.

- **Download**: Scrapes bill metadata and downloads PDFs from the MGA website.
- **Convert**: Processes PDFs into high-quality Markdown, preserving formatting and tracking strikeouts.
- **Amend**: Uses LLMs to merge adopted amendments into the original bill text, creating a "current" version of the bill.
- **QA**: Analyzes the final bill text using LLMs to answer specific policy questions.
- **Export**: Generates a unified JSON file (`frontend_data.json`) for visualization.

## Installation

1. Clone the repository and navigate to the root directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate # Linux/Mac
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

The main entry point is `run_pipeline.py`. It manages all stages of the process and skips bills that have already been processed unless they have updated.

```bash
python run_pipeline.py --year 2026 --model-family gemini
```

**Arguments:**
- `--year`: The legislative session year (default: 2026).
- `--model-family`: The LLM provider to use (`gemini`, `gpt`, or `ollama`).
- `--model`: Specific model name (default: `gemini-3-flash-preview`).
- `--debug`: Limits processing to the first 10 bills for testing.

### Project Structure

- `pipeline/`: Core modules for each stage (download, convert, amend, qa).
- `data/{year}rs/`: Contains session-specific data.
  - `pdf/`: Original legislative documents.
  - `md/`: Converted and amended bill text.
  - `legislation.json`: Bill metadata.
  - `pipeline_state.json`: Tracking file for the pipeline's progress.
- `llm_utils.py`: Shared utilities for LLM communication and schema validation.
- `index.html`: A Vue.js frontend for browsing the processed results.

### Utility Scripts

- `describe_agencies.py`: Scrapes Maryland agency information and uses Gemini with Google Search grounding to generate summaries in `data/maryland_agencies.csv`.

## Requirements

The project requires Python 3.10+ and API keys for the selected LLM providers. See `requirements.txt` for the full list of dependencies.
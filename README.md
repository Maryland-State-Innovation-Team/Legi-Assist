# Legi-Assist

Legi-Assist is an automated toolkit for collecting, processing, and analyzing Maryland General Assembly legislation. It transforms legislative PDFs into structured, machine-readable data and leverages LLMs to extract policy-relevant insights, such as funding impacts and stakeholder analysis.

## Installation

```bash
pip install virtualenv
python -m virtualenv venv

# On Windows:
.\venv\Scripts\activate

# On Unix or MacOS:
source venv/bin/activate

pip install -r requirements.txt
```

## Python Scripts Overview

Below are descriptions of each script in the `code` directory, including their purpose, arguments, defaults, and usage examples.

---

### `download_legislation.py`

**Purpose:**  
Downloads Maryland legislative data and associated PDFs for a given session year, processes cross-filed bills, and saves metadata as CSV.

**Arguments:**  
- `session_year` (int, required): The regular session year.

**Usage:**  
```bash
python code/download_legislation.py 2025
```
- Downloads bill metadata from the Maryland General Assembly website.
- Downloads main bill PDFs and adopted amendment PDFs to `data/{session_year}rs/pdf/`.
- Outputs a CSV file with bill metadata to `data/{session_year}rs/csv/legislation.csv`.

**Note:** For future sessions (currently set as 2026), this script filters for bills that have passed (rather than those with a chapter number) and applies special logic to capture incremental amendments as they are adopted.

---

### `leg_to_basic_txt.py`

**Purpose:**  
Converts all bill PDFs for a session year into plain text files, one per bill.

**Arguments:**  
- `session_year` (int, required): The regular session year.

**Usage:**  
```bash
python code/leg_to_basic_txt.py 2025
```
- Reads PDFs from `data/{session_year}rs/pdf/`.
- Outputs `.txt` files to `data/{session_year}rs/basic_txt/`.
- Prints the total page count processed.

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

All dependencies are listed in `requirements.txt`.  
You will need API keys for Gemini and/or OpenAI if using those LLMs.  
Some scripts require a `.env` file with the appropriate API keys.

# Plain Language Evaluation - Quick Start

## What This Does

Automatically scores all bill summaries (human + AI) across 4 legislative sessions against Maryland's Plain Language Initiative standards. Produces Excel and JSON reports comparing human vs AI summaries.

## Installation

```bash
# Install new dependencies
pip install textstat spacy openpyxl

# Download spaCy language model
python -m spacy download en_core_web_sm
```

## Run the Evaluation

### Quick Test (Debug Mode)
```bash
python run_evaluation.py --debug
```
This evaluates only the first 10 bills per session (~40 bills total) for testing.

### Full Evaluation (All 4 Sessions)
```bash
python run_evaluation.py
```
This evaluates all 3,743 bills. **Takes 10-15 hours** due to LLM API calls.

### Specific Sessions Only
```bash
python run_evaluation.py --years 2025 2026
```

## What You Get

### 1. Console Summary Report
Immediately see:
- Average plain language scores (Human vs AI)
- Component breakdowns (everyday words, active voice, etc.)
- Accuracy scores (AI summaries)

### 2. Excel File (`evaluation/results/evaluation-YYYYMMDD-{model}.xlsx`)
**Best for human review panel:**
- Sheet 1: Plain Language Scores by bill
- Sheet 2: Accuracy Scores with LLM justifications
- Sortable, filterable, ready for review
- Timestamped and tagged by model (e.g., `evaluation-20260917-gemini.xlsx`)

### 3. JSON File (`evaluation/results/evaluation-YYYYMMDD-{model}.json`)
**Best for programmatic analysis:**
- Machine-readable detailed results
- Track scores over time
- Compare across models (Gemini vs Claude)
- Timestamped and tagged by model (e.g., `evaluation-20260917-gemini.json`)

## Example Output

```
================================================================================
MARYLAND PLAIN LANGUAGE EVALUATION REPORT
================================================================================

HUMAN SYNOPSES (n=3736)
  Average Total Score: 72.3/100
  
AI SUMMARIES (n=3736)
  Average Total Score: 81.7/100
  
  COMPARISON:
    AI vs Human Difference: +9.4 points
    → AI summaries score HIGHER on plain language

### ACCURACY SCORES (AI Summaries only)
  Groundedness:      4.32/5.0
  Relevance:         4.18/5.0
  Interpretation:    4.25/5.0
================================================================================
```

## Scoring Breakdown

### Plain Language (100 points)
- **(a) Everyday words** - 30 pts: Flesch Reading Ease, jargon, complexity
- **(b) Present/Active** - 20 pts: Passive voice, past tense rates
- **(c) Short sentences** - 25 pts: Length metrics
- **(d) Definitions** - 10 pts: LLM evaluation
- **(e) Organization** - 15 pts: LLM evaluation

### Accuracy (5-point scale each)
- **Groundedness**: Grounded in source material?
- **Relevance**: Covers material provisions?
- **Interpretation**: Accurate without overstatement?

## Workflow for Review Panel

1. **Run evaluation** to generate Excel file
2. **Sort by lowest scores** to find problematic summaries
3. **Review LLM justifications** in Accuracy sheet
4. **Flag patterns** for pipeline improvement
5. **Re-run evaluation** after changes to measure improvement

## Troubleshooting

### "Missing GEMINI_API_KEY"
Add to your `.env` file:
```
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### "No data found for YEAR"
Ensure you've run the main pipeline first:
```bash
python run_pipeline.py --year 2026
```

### spaCy model not found
```bash
python -m spacy download en_core_web_sm
```

## Next Steps

1. ✅ Install dependencies
2. ✅ Run debug mode to verify setup
3. ✅ Run full evaluation (plan for 2-4 hours)
4. ✅ Review Excel output
5. ✅ Share results with review panel


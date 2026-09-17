# Maryland Plain Language Evaluation System

## Summary

Adds an automated evaluation system that scores legislative bill summaries against Maryland's Plain Language Initiative standards. This system compares human-written synopses (from Maryland General Assembly) with AI-generated summaries (from Legi-Assist) to measure plain language adherence and accuracy.

## What This PR Adds

### New Files
- **`evaluation/`** - Core evaluation package
  - `evaluators.py` - PlainLanguageEvaluator and AccuracyEvaluator classes
  - `__init__.py` - Package exports
- **`run_evaluation.py`** - Main execution script
- **`test_evaluation.py`** - Setup verification script
- **`check_ai_summaries.py`** - Helper to check data availability
- **Documentation:**
  - `EVALUATION_QUICKSTART.md` - Getting started guide
  - `IMPLEMENTATION_SUMMARY.md` - Requirements mapping
  - `docs/evaluation.md` - Complete technical documentation

### Dependencies Added
- `textstat` - Readability metrics (Flesch Reading Ease, complex word counting)
- `spacy` - Grammar analysis (passive voice, verb tenses, sentence structure)
- `openpyxl` - Excel export for review panel

## What It Does

### Plain Language Scoring (100 points)
Evaluates bill summaries on 5 components based on Maryland's Executive Order E(4):
1. **(a) Everyday Words (30 pts)** - Readability, jargon density, complex words
2. **(b) Present Tense & Active Voice (20 pts)** - Passive voice rate, past tense density
3. **(c) Short, Simple Sentences (25 pts)** - Sentence length, long sentence percentage
4. **(d) Necessary-Only Definitions (10 pts)** - LLM evaluation of definition appropriateness
5. **(e) Well-Organized (15 pts)** - LLM evaluation of structure and clarity

### Accuracy Scoring (AI summaries only, 1-5 scale)
- **Groundedness** - No fabricated information
- **Relevance** - Covers material provisions
- **Correct Interpretation** - Accurate without overstatement

## How to Use

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Verify setup
python test_evaluation.py
```

### Basic Usage
```bash
# Evaluate all years (2023-2026)
python run_evaluation.py

# Evaluate specific year
python run_evaluation.py --years 2026

# Debug mode (10 bills per session)
python run_evaluation.py --debug
```

## Outputs

1. **`evaluation_results.xlsx`** - Sortable spreadsheet with all scores (for review panel)
2. **`evaluation_results.json`** - Machine-readable complete data (for tracking over time)
3. **Console summary report** - Average scores, human vs AI comparison, component breakdowns

## Key Features

- ✅ **Automated baseline metrics** - Components (a), (b), (c) use deterministic formulas
- ✅ **LLM-based subjective evaluation** - Components (d), (e) and accuracy use Gemini
- ✅ **Comprehensive coverage** - Evaluates all 3,736 bills across 4 sessions
- ✅ **Actionable outputs** - Excel designed for review panel workflow
- ✅ **Iterative improvement** - Run → identify issues → fix → re-run → measure progress

## Technical Details

- **Processing time:** ~10-15 hours for full evaluation of all sessions
- **Rate:** ~20-25 seconds per bill (includes LLM API calls for accuracy scoring)
- **Error handling:** Automatic retries with exponential backoff for API rate limits

## Testing

Tested with:
- Debug mode (10 bills per session) - All evaluations working correctly
- Verified field name compatibility with pipeline output (`bill_summary`)
- Confirmed JSON parsing handles Gemini markdown code blocks

## Related

- Implements requirements from Plain Language Initiative evaluation discussion
- Designed for Lauren Maffeo's review panel workflow
- Supports Maryland's Executive Order E(4) compliance assessment

---

**Ready for review!** This system provides the automated scoring infrastructure to evaluate and improve legislative summaries against Maryland's plain language standards.

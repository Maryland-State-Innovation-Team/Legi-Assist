# Plain Language Evaluation System

This evaluation system scores bill summaries against Maryland's Plain Language Initiative standards and assesses AI-generated summaries for accuracy.

## Overview

The evaluation system provides:
1. **Plain Language Scoring** - Automated metrics aligned with Maryland's EO E(4) standards
2. **Accuracy Assessment** - LLM-based evaluation of groundedness, relevance, and interpretation
3. **Comparative Analysis** - Human synopsis vs AI summary comparison across all sessions

## Scoring Framework

### Plain Language Score (100 points total)

Based on Maryland's Executive Order E(4) standards:

| Standard | Weight | Components |
|----------|--------|------------|
| **(a) Everyday words** | 30 pts | Flesch Reading Ease (15), Jargon density (10), Complex words (5) |
| **(b) Present tense & active voice** | 20 pts | Passive voice rate (12), Past tense density (8) |
| **(c) Short, simple sentences** | 25 pts | Avg sentence length (15), % over 20 words (10) |
| **(d) Necessary-only definitions** | 10 pts | LLM rubric 1-5 (scaled to 10) |
| **(e) Well-organized** | 15 pts | LLM rubric 1-5 (scaled to 15) |

### Accuracy Score (AI summaries only)

Three dimensions rated 1-5 each:

- **Groundedness**: Response grounded in source bill text, metadata, or taxonomy
- **Relevance**: Surfaces material provisions (what, who, when, funding, penalties, sunset)
- **Correct Interpretation**: Accurate explanation without overstated certainty

## Usage

### Basic Evaluation

Evaluate all 4 session years (2023-2026):

```bash
python run_evaluation.py
```

### Specific Sessions

```bash
python run_evaluation.py --years 2025 2026
```

### With Custom Model

```bash
python run_evaluation.py --model-family gpt --model gpt-4o
```

### Debug Mode (First 10 bills per session)

```bash
python run_evaluation.py --debug
```

## Outputs

### 1. JSON Results (`evaluation_results.json`)

Detailed machine-readable results:

```json
{
  "plain_language_scores": [
    {
      "bill_number": "HB0001",
      "text_source": "human",
      "total_score": 78.5,
      "flesch_score": 12.3,
      "jargon_score": 8.5,
      ...
    }
  ],
  "accuracy_scores": [...],
  "metadata": {
    "evaluated_at": "2026-09-14T...",
    "session_years": [2023, 2024, 2025, 2026],
    "model": "gemini/gemini-3-flash-preview",
    "total_bills": 3736
  }
}
```

### 2. Excel Report (`evaluation_results.xlsx`)

Two sheets:
- **Plain Language Scores**: All component scores by bill
- **Accuracy Scores**: Groundedness, relevance, interpretation with justifications

### 3. Summary Report (Console)

```
================================================================================
MARYLAND PLAIN LANGUAGE EVALUATION REPORT
================================================================================

Generated: 2026-09-14T10:30:00
Sessions: 2023, 2024, 2025, 2026
Model: gemini/gemini-3-flash-preview
Bills Evaluated: 3736

================================================================================

### PLAIN LANGUAGE SCORES (out of 100)

HUMAN SYNOPSES (n=3736)
  Average Total Score: 72.3/100
  
  Component Breakdown:
    (a) Everyday Words:        23.4/30
    (b) Present/Active:        14.8/20
    (c) Short Sentences:       19.2/25
    (d) Definitions:           7.1/10
    (e) Organization:          10.8/15

AI SUMMARIES (n=3736)
  Average Total Score: 81.7/100
  
  Component Breakdown:
    (a) Everyday Words:        26.8/30
    (b) Present/Active:        17.2/20
    (c) Short Sentences:       21.5/25
    (d) Definitions:           8.4/10
    (e) Organization:          12.3/15
  
  COMPARISON:
    AI vs Human Difference: +9.4 points
    → AI summaries score HIGHER on plain language

================================================================================
### ACCURACY SCORES (AI Summaries only)

AI SUMMARIES (n=3736)
  Groundedness:      4.32/5.0
  Relevance:         4.18/5.0
  Interpretation:    4.25/5.0

================================================================================
```

## Technical Details

### Plain Language Metrics Implementation

#### (a) Everyday Words

- **Flesch Reading Ease**: Uses `textstat.flesch_reading_ease()`
  - Target: 60-70 (fairly easy to read)
  - Optimal score = 15 points
  - Penalized proportionally above/below target

- **Jargon Density**: Checks against legal jargon wordlist
  - Words like: "aforementioned", "herein", "pursuant", "notwithstanding"
  - Target: 0% jargon
  - 5%+ jargon = 0 points

- **Complex Words**: Words with 3+ syllables
  - Target: <10% complex words
  - 20%+ = 0 points

#### (b) Present Tense & Active Voice

Uses spaCy for linguistic analysis:

- **Passive Voice**: Detects auxiliary passive constructions
  - Target: <10% passive
  - 20%+ passive = 0 points

- **Past Tense**: Identifies VBD/VBN tags
  - Target: <20% past tense
  - 30%+ = 0 points

#### (c) Sentence Structure

- **Average Length**: Compares to 15-20 word target
- **Long Sentences**: Percentage over 20 words
  - Target: 0% long sentences
  - 30%+ = 0 points

#### (d) & (e) LLM-Based Rubrics

Uses structured prompts to get 1-5 ratings on:
- Definition appropriateness
- Organization and clarity

Scores are scaled to weight (10 and 15 points respectively).

### Accuracy Evaluation

LLM evaluates AI summaries against:
- Original bill markdown text
- Bill metadata (sponsor, dates, etc.)
- Fiscal notes (when available)

Returns structured ratings with justifications.

## Dependencies

New packages required:

```bash
pip install textstat spacy pandas openpyxl
python -m spacy download en_core_web_sm
```

## Extending the System

### Adding Custom Jargon Terms

Edit `evaluate_plain_language.py`:

```python
self.legal_jargon = {
    'aforementioned', 'herein', 'thereof',
    # Add your terms here
    'custom_term_1', 'custom_term_2'
}
```

### Adjusting Scoring Weights

Modify the `PlainLanguageScore` class or scoring functions to change weights.

### Custom LLM Prompts

Edit `_score_definitions_llm()` and `_score_organization_llm()` methods to refine evaluation criteria.

## Next Steps

1. **Run Initial Evaluation**: Get baseline scores for all 4 sessions
2. **Human Review Panel**: Review sample of flagged low-scoring summaries
3. **Iterate on Pipeline**: Use scores to improve AI summary generation
4. **Re-evaluate**: Measure improvement against baseline

## Notes

- Processing ~3700 bills will take approximately 2-4 hours (with LLM API calls)
- Use `--debug` mode first to verify setup
- Excel output is optimized for human review panel workflow
- JSON output enables programmatic analysis and tracking over time

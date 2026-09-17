"""
Maryland Plain Language Scorer
Evaluates bill summaries against MD Plain Language Initiative standards
"""

import json
import os
import re
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass
import textstat
import spacy
from collections import Counter
from tqdm import tqdm

# Import LLM utilities
from llm_utils import query_llm_with_retries


@dataclass
class PlainLanguageScore:
    """Container for plain language evaluation results"""
    bill_number: str
    text_source: str  # 'human' or 'ai'

    # (a) Everyday words - 30 points
    flesch_score: float  # 0-15
    jargon_score: float  # 0-10
    complex_word_score: float  # 0-5

    # (b) Present tense & active voice - 20 points
    passive_score: float  # 0-12
    past_tense_score: float  # 0-8

    # (c) Short, simple sentences - 25 points
    sentence_length_score: float  # 0-15
    long_sentence_score: float  # 0-10

    # (d) Necessary-only definitions - 10 points
    definition_score: float  # 0-10 (LLM rubric 1-5 scaled to 10)

    # (e) Well-organized / leads with point - 15 points
    organization_score: float  # 0-15 (LLM rubric 1-5 scaled to 15)

    @property
    def total_plain_language_score(self) -> float:
        """Total plain language score out of 100"""
        return (
            self.flesch_score + self.jargon_score + self.complex_word_score +
            self.passive_score + self.past_tense_score +
            self.sentence_length_score + self.long_sentence_score +
            self.definition_score + self.organization_score
        )


@dataclass
class AccuracyScore:
    """Container for accuracy evaluation results"""
    bill_number: str
    text_source: str

    # Accuracy metrics (1-5 scale each)
    groundedness: float  # Is response grounded in source material?
    relevance: float  # Does it surface material provisions?
    interpretation: float  # Accurate explanation without overstatement?

    # LLM justifications
    groundedness_reason: str
    relevance_reason: str
    interpretation_reason: str


class PlainLanguageEvaluator:
    """Evaluates text against Maryland Plain Language Initiative standards"""

    def __init__(self, llm_client, model_name: str, model_family: str):
        self.llm_client = llm_client
        self.model_name = model_name
        self.model_family = model_family

        # Load spaCy for linguistic analysis
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Downloading spaCy model...")
            os.system("python -m spacy download en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Maryland-specific jargon list (extend based on legislative domain)
        self.legal_jargon = {
            'aforementioned', 'herein', 'thereof', 'whereby', 'heretofore',
            'therein', 'hereafter', 'pursuant', 'notwithstanding', 'whereas',
            'aforesaid', 'hereby', 'thereto', 'forthwith', 'insofar',
            'promulgate', 'effectuate', 'evidencing', 'supersede', 'rescind'
        }

    def evaluate_text(self, text: str, bill_number: str, text_source: str,
                     bill_context: Optional[Dict] = None) -> PlainLanguageScore:
        """
        Evaluate a single text against all plain language criteria

        Args:
            text: The summary text to evaluate
            bill_number: Bill identifier (e.g., "HB0001")
            text_source: 'human' or 'ai'
            bill_context: Original bill data for context (optional)
        """

        # (a) Everyday words - 30 points
        flesch_score = self._score_flesch_ease(text)
        jargon_score = self._score_jargon_density(text)
        complex_word_score = self._score_complex_words(text)

        # (b) Present tense & active voice - 20 points
        passive_score = self._score_passive_voice(text)
        past_tense_score = self._score_past_tense(text)

        # (c) Short, simple sentences - 25 points
        sentence_length_score, long_sentence_score = self._score_sentence_structure(text)

        # (d) Necessary-only definitions - 10 points (LLM-based)
        definition_score = self._score_definitions_llm(text, bill_context)

        # (e) Well-organized / leads with point - 15 points (LLM-based)
        organization_score = self._score_organization_llm(text, bill_context)

        return PlainLanguageScore(
            bill_number=bill_number,
            text_source=text_source,
            flesch_score=flesch_score,
            jargon_score=jargon_score,
            complex_word_score=complex_word_score,
            passive_score=passive_score,
            past_tense_score=past_tense_score,
            sentence_length_score=sentence_length_score,
            long_sentence_score=long_sentence_score,
            definition_score=definition_score,
            organization_score=organization_score
        )

    # ========== (a) Everyday Words Scoring ==========

    def _score_flesch_ease(self, text: str) -> float:
        """
        Score Flesch Reading Ease (max 15 points)
        Target: 60-70 (fairly easy to read)

        Scale: 90-100 (very easy) → 0-30 (very difficult)
        """
        try:
            flesch = textstat.flesch_reading_ease(text)

            # Scoring: 60-70 is optimal (15 points)
            if 60 <= flesch <= 70:
                return 15.0
            elif flesch > 70:
                # Too simple is also penalized slightly
                excess = flesch - 70
                return max(10.0, 15.0 - (excess * 0.1))
            else:
                # Below 60 is penalized proportionally
                deficit = 60 - flesch
                return max(0.0, 15.0 - (deficit * 0.25))
        except:
            return 7.5  # Default middle score if calculation fails

    def _score_jargon_density(self, text: str) -> float:
        """
        Score legal jargon density (max 10 points)
        Lower jargon = higher score
        """
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 10.0

        jargon_count = sum(1 for word in words if word in self.legal_jargon)
        jargon_pct = (jargon_count / len(words)) * 100

        # Scoring: 0% jargon = 10 points, 5%+ = 0 points
        if jargon_pct == 0:
            return 10.0
        elif jargon_pct >= 5:
            return 0.0
        else:
            return 10.0 - (jargon_pct * 2)

    def _score_complex_words(self, text: str) -> float:
        """
        Score complex word percentage (max 5 points)
        Complex = 3+ syllables
        Target: <10% complex words
        """
        try:
            complex_pct = textstat.difficult_words(text) / len(text.split()) * 100

            # Scoring: <10% = 5 points, >20% = 0 points
            if complex_pct <= 10:
                return 5.0
            elif complex_pct >= 20:
                return 0.0
            else:
                return 5.0 - ((complex_pct - 10) * 0.5)
        except:
            return 2.5

    # ========== (b) Present Tense & Active Voice Scoring ==========

    def _score_passive_voice(self, text: str) -> float:
        """
        Score passive voice usage (max 12 points)
        Lower passive = higher score
        Target: <10% passive constructions
        """
        doc = self.nlp(text)
        total_verbs = 0
        passive_count = 0

        for token in doc:
            if token.pos_ == "VERB":
                total_verbs += 1
                # Check for passive voice patterns
                if any(child.dep_ == "auxpass" for child in token.children):
                    passive_count += 1

        if total_verbs == 0:
            return 12.0

        passive_pct = (passive_count / total_verbs) * 100

        # Scoring: 0% = 12 points, 20%+ = 0 points
        if passive_pct == 0:
            return 12.0
        elif passive_pct >= 20:
            return 0.0
        else:
            return 12.0 - (passive_pct * 0.6)

    def _score_past_tense(self, text: str) -> float:
        """
        Score past tense density (max 8 points)
        Prefer present tense
        Target: <20% past tense
        """
        doc = self.nlp(text)
        total_verbs = 0
        past_tense_count = 0

        for token in doc:
            if token.pos_ == "VERB":
                total_verbs += 1
                if token.tag_ in ["VBD", "VBN"]:  # Past tense tags
                    past_tense_count += 1

        if total_verbs == 0:
            return 8.0

        past_pct = (past_tense_count / total_verbs) * 100

        # Scoring: 0% = 8 points, 30%+ = 0 points
        if past_pct <= 10:
            return 8.0
        elif past_pct >= 30:
            return 0.0
        else:
            return 8.0 - ((past_pct - 10) * 0.4)

    # ========== (c) Short, Simple Sentences Scoring ==========

    def _score_sentence_structure(self, text: str) -> tuple[float, float]:
        """
        Score sentence structure (max 25 points total)
        Returns: (sentence_length_score, long_sentence_score)
        """
        doc = self.nlp(text)
        sentences = list(doc.sents)

        if not sentences:
            return 15.0, 10.0

        # Calculate sentence lengths
        sentence_lengths = [len(sent.text.split()) for sent in sentences]
        avg_length = sum(sentence_lengths) / len(sentence_lengths)
        long_sentences = sum(1 for length in sentence_lengths if length > 20)
        long_pct = (long_sentences / len(sentences)) * 100

        # Score 1: Average sentence length vs 15-20 target (max 15 points)
        if 15 <= avg_length <= 20:
            length_score = 15.0
        elif avg_length < 15:
            # Too short is also penalized slightly
            length_score = max(10.0, 15.0 - (15 - avg_length) * 0.5)
        else:
            # Over 20 words penalized more heavily
            length_score = max(0.0, 15.0 - (avg_length - 20) * 0.75)

        # Score 2: Percentage of sentences over 20 words (max 10 points)
        if long_pct == 0:
            long_score = 10.0
        elif long_pct >= 30:
            long_score = 0.0
        else:
            long_score = 10.0 - (long_pct * 0.33)

        return length_score, long_score

    # ========== (d) & (e) LLM-Based Scoring ==========

    def _score_definitions_llm(self, text: str, bill_context: Optional[Dict]) -> float:
        """
        Score definitions appropriateness using LLM (max 10 points)
        LLM returns 1-5 score, scaled to 0-10
        """
        prompt = """You are evaluating legislative bill summaries against Maryland's Plain Language Initiative.

Assess whether technical terms are handled appropriately:
- Technical terms that need explanation ARE explained clearly
- Common terms are NOT over-defined
- Definitions are concise and placed appropriately

Rate from 1-5:
1 = Many undefined technical terms OR excessive over-defining
2 = Several issues with definitions
3 = Adequate but could improve
4 = Good balance, minor issues only
5 = Excellent - technical terms explained, no over-defining

Return ONLY a JSON object with your rating and brief justification."""

        try:
            response = query_llm_with_retries(
                self.llm_client,
                prompt,
                f"Text to evaluate:\n\n{text}",
                None,  # No schema, get text response
                self.model_name,
                model_family=self.model_family
            )

            # Parse response for rating
            rating_match = re.search(r'"rating":\s*(\d)', response)
            if rating_match:
                rating = int(rating_match.group(1))
                return (rating / 5.0) * 10.0  # Scale to 0-10

            return 5.0  # Default middle score
        except:
            return 5.0

    def _score_organization_llm(self, text: str, bill_context: Optional[Dict]) -> float:
        """
        Score organization using LLM (max 15 points)
        LLM returns 1-5 score, scaled to 0-15
        """
        prompt = """You are evaluating legislative bill summaries against Maryland's Plain Language Initiative.

Assess the organization and structure:
- Does it lead with what the bill DOES (the main action)?
- Is information ordered logically (most important first)?
- Can readers quickly understand the bill's purpose?

Rate from 1-5:
1 = Buries the main point, poor structure
2 = Main point delayed or unclear
3 = Adequate structure
4 = Good - mostly leads with the point
5 = Excellent - immediately clear what the bill does

Return ONLY a JSON object with your rating and brief justification."""

        try:
            response = query_llm_with_retries(
                self.llm_client,
                prompt,
                f"Text to evaluate:\n\n{text}",
                None,
                self.model_name,
                model_family=self.model_family
            )

            rating_match = re.search(r'"rating":\s*(\d)', response)
            if rating_match:
                rating = int(rating_match.group(1))
                return (rating / 5.0) * 15.0  # Scale to 0-15

            return 7.5
        except:
            return 7.5


class AccuracyEvaluator:
    """Evaluates summaries for groundedness, relevance, and interpretation"""

    def __init__(self, llm_client, model_name: str, model_family: str):
        self.llm_client = llm_client
        self.model_name = model_name
        self.model_family = model_family

    def evaluate_accuracy(self, summary: str, bill_text: str, bill_metadata: Dict,
                         bill_number: str, text_source: str) -> AccuracyScore:
        """
        Evaluate summary accuracy against source bill

        Args:
            summary: The bill summary to evaluate
            bill_text: Original bill text (markdown)
            bill_metadata: Bill metadata (sponsor, dates, etc.)
            bill_number: Bill identifier
            text_source: 'human' or 'ai'
        """

        prompt = """You are evaluating a legislative bill summary for accuracy against the source material.

Evaluate on three dimensions (rate each 1-5):

1. GROUNDEDNESS: Is the summary grounded in the source bill text and metadata?
   - 1 = Contains fabricated specifics not in source
   - 3 = Mostly grounded with minor unsupported claims
   - 5 = Entirely grounded in source material

2. RELEVANCE: Does it surface the material provisions?
   - What the bill does
   - Who it applies to
   - When it takes effect
   - Funding amounts, penalties, sunset terms
   - 1 = Omits critical provisions
   - 3 = Covers main points but misses some details
   - 5 = Comprehensive coverage of material provisions

3. CORRECT INTERPRETATION: Is the explanation accurate?
   - No conflating "authorizes" with "requires"
   - No treating proposal as enacted law
   - Acknowledges internal tensions if present
   - Appropriate level of certainty
   - 1 = Significant misinterpretations
   - 3 = Mostly accurate with minor issues
   - 5 = Completely accurate interpretation

Return ONLY a valid JSON object, with no markdown formatting or additional text:
{
  "groundedness": <1-5>,
  "groundedness_reason": "<brief explanation>",
  "relevance": <1-5>,
  "relevance_reason": "<brief explanation>",
  "interpretation": <1-5>,
  "interpretation_reason": "<brief explanation>"
}

Do not wrap the JSON in markdown code blocks. Do not add any text before or after the JSON."""

        context = f"""SUMMARY TO EVALUATE:
{summary}

BILL METADATA:
- Bill Number: {bill_metadata.get('BillNumber', 'N/A')}
- Sponsor: {bill_metadata.get('Sponsor', 'N/A')}
- Title: {bill_metadata.get('Synopsis', 'N/A')}

BILL TEXT (first 3000 chars):
{bill_text[:3000]}
"""

        try:
            response = query_llm_with_retries(
                self.llm_client,
                prompt,
                context,
                None,
                self.model_name,
                model_family=self.model_family
            )

            # Parse JSON response (strip markdown if present)
            response_text = response.strip()
            if response_text.startswith('```'):
                # Extract JSON from markdown code block
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            result = json.loads(response_text)

            return AccuracyScore(
                bill_number=bill_number,
                text_source=text_source,
                groundedness=float(result.get('groundedness', 3)),
                relevance=float(result.get('relevance', 3)),
                interpretation=float(result.get('interpretation', 3)),
                groundedness_reason=result.get('groundedness_reason', ''),
                relevance_reason=result.get('relevance_reason', ''),
                interpretation_reason=result.get('interpretation_reason', '')
            )
        except Exception as e:
            print(f"Error evaluating accuracy for {bill_number}: {e}")
            # Return default middle scores
            return AccuracyScore(
                bill_number=bill_number,
                text_source=text_source,
                groundedness=3.0,
                relevance=3.0,
                interpretation=3.0,
                groundedness_reason="Evaluation failed",
                relevance_reason="Evaluation failed",
                interpretation_reason="Evaluation failed"
            )


def main():
    parser = argparse.ArgumentParser(description='Maryland Plain Language Scorer')
    parser.add_argument('--year', type=int, default=2026, help='Session Year')
    parser.add_argument('--model-family', default='gemini', choices=['gemini', 'gpt', 'ollama'])
    parser.add_argument('--model', default='gemini-3-flash-preview')
    parser.add_argument('--debug', action='store_true', help='Limit to first 10 bills')
    parser.add_argument('--output', default='evaluation_results.json', help='Output file')
    args = parser.parse_args()

    print(f"=== Maryland Plain Language Scorer ===")
    print(f"Session: {args.year}")
    print(f"Model: {args.model_family}/{args.model}\n")

    # TODO: Initialize LLM client (copy from run_pipeline.py)
    # TODO: Load frontend_data.json
    # TODO: Load bill markdown files
    # TODO: Run evaluations
    # TODO: Generate report

    print("Scorer framework ready. Implement main() with your data loading logic.")


if __name__ == "__main__":
    main()

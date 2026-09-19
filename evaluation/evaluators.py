"""
Maryland Plain Language Scorer
Evaluates bill summaries against MD Plain Language Initiative standards
"""

import json
import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel
import textstat
import spacy

# Import LLM utilities
from llm_utils import query_llm_with_retries


class _RatingResponse(BaseModel):
    """LLM judge response for single-dimension 1-5 ratings (everyday words, definitions, organization)."""
    rating: int
    justification: str


class _AccuracyLLMResponse(BaseModel):
    """LLM judge response for three-dimension accuracy evaluation."""
    groundedness: float
    groundedness_reason: str
    relevance: float
    relevance_reason: str
    interpretation: float
    interpretation_reason: str


@dataclass
class PlainLanguageScore:
    """Container for plain language evaluation results"""
    bill_number: str
    text_source: str  # 'human' or 'ai'

    # (a) Everyday words - 30 points
    #   Flesch was removed — its 1948 target range (60-70 "fairly easy") is
    #   calibrated for magazine prose and cannot be reached by legislative
    #   content regardless of writing quality. Its 10 pts moved to the LLM
    #   judge, which measures the EO E(4)(a) criterion far more faithfully.
    jargon_score: float  # 0-10
    everyday_words_score: float  # 0-20 (LLM judge — primary signal for EO E(4)(a))

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
            self.jargon_score + self.everyday_words_score +
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

        # Jargon list compiled from actual MGA synopsis + AI-summary corpus and
        # cross-referenced against federal plain-language guidance (plainlanguage.gov).
        # Includes archaic legalese (rare) and the bureaucratic tics that actually
        # appear at frequency in Maryland legislative writing.
        self.legal_jargon = {
            # Archaic here-/there-/where- constructions
            'aforementioned', 'aforesaid', 'herein', 'hereby', 'hereto', 'hereof',
            'hereunder', 'herewith', 'heretofore', 'hereinafter', 'hereafter',
            'therein', 'thereof', 'thereto', 'thereunder', 'therefrom', 'thereafter',
            'whereas', 'whereby', 'wherein', 'wherefor', 'wherewith',
            # Formal legal connectors — bureaucratic when plain word exists
            'notwithstanding', 'pursuant', 'forthwith', 'insofar',
            'accordance', 'regarding', 'concerning', 'pertaining', 'respecting',
            # Archaic verbs
            'effectuate', 'promulgate', 'supersede', 'rescind',
            'deem', 'deems', 'deemed', 'utilize', 'utilizes', 'utilized',
            'ascertain', 'commence', 'commences', 'commenced',
            'endeavor', 'endeavors',
            # Demonstrative legalese
            'aforesaid', 'said', 'same',
            # Common bureaucratic replacements — use everyday word instead
            'prior',        # "prior to" → "before"
            'subsequent',   # "subsequent to" → "after"
            'certain',      # legalese demonstrative pattern in synopses
            'such',         # legalese demonstrative pattern
            'provided',     # "provided that" → "if"
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
        jargon_score = self._score_jargon_density(text)
        everyday_words_score = self._score_everyday_words_llm(text, bill_context)

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
            jargon_score=jargon_score,
            everyday_words_score=everyday_words_score,
            passive_score=passive_score,
            past_tense_score=past_tense_score,
            sentence_length_score=sentence_length_score,
            long_sentence_score=long_sentence_score,
            definition_score=definition_score,
            organization_score=organization_score
        )

    # ========== (a) Everyday Words Scoring ==========

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

    def _score_everyday_words_llm(self, text: str, bill_context: Optional[Dict]) -> float:
        """
        LLM judge (max 20 points) — EO 01.01.2024.25 E(4)(a):
        "Everyday words that convey meanings clearly and directly".

        Primary signal for E(4)(a). Flesch was dropped from the rubric (its 1948
        target range is calibrated for magazine prose, not policy documents);
        Jargon (10 pts) remains as the deterministic anchor. This LLM judge
        carries the remaining 20 pts because it measures the criterion's actual
        intent — direct, familiar vocabulary vs. abstract or bureaucratic
        constructions — far more faithfully than a syllable formula.
        """
        prompt = (
            "You are evaluating a Maryland legislative bill summary against the state's "
            "Plain Language Initiative (EO 01.01.2024.25), criterion (a): 'Everyday words "
            "that convey meanings clearly and directly'.\n\n"
            "Rate how well the summary uses EVERYDAY, DIRECT language:\n"
            "- Prefers concrete verbs over nominalizations (e.g. 'decides' over 'makes a determination').\n"
            "- Uses familiar policy vocabulary the general public can follow.\n"
            "- Avoids abstract or bureaucratic constructions.\n"
            "- Domain-necessary terms (agency names, statute references) DO NOT count against the score.\n\n"
            "1 = Heavy nominalization or bureaucratic phrasing throughout\n"
            "2 = Several indirect or abstract constructions\n"
            "3 = Mixed — some direct, some indirect\n"
            "4 = Mostly direct, minor issues\n"
            "5 = Consistently direct and concrete language\n\n"
            "Return only a rating (1-5) and a brief justification."
        )
        try:
            result = query_llm_with_retries(
                self.llm_client,
                prompt,
                f"Summary to evaluate:\n\n{text}",
                _RatingResponse,
                self.model_name,
                model_family=self.model_family,
            )
            if result and 'rating' in result:
                return (int(result['rating']) / 5.0) * 20.0
            return 10.0
        except Exception as e:
            print(f"Error scoring everyday-words: {e}")
            return 10.0

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
                # Only count simple past (VBD). VBN (past participle) is not
                # a tense marker in isolation — it's often used adjectivally
                # ("the designated agent") or in passive/perfect constructions
                # (which are separately scored). Counting VBN as past tense
                # double-penalizes and misfires on standard descriptive prose.
                if token.tag_ == "VBD":
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
            result = query_llm_with_retries(
                self.llm_client,
                prompt,
                f"Text to evaluate:\n\n{text}",
                _RatingResponse,
                self.model_name,
                model_family=self.model_family,
            )
            if result and 'rating' in result:
                return (int(result['rating']) / 5.0) * 10.0
            return 5.0
        except Exception as e:
            print(f"Error scoring definitions: {e}")
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
            result = query_llm_with_retries(
                self.llm_client,
                prompt,
                f"Text to evaluate:\n\n{text}",
                _RatingResponse,
                self.model_name,
                model_family=self.model_family,
            )
            if result and 'rating' in result:
                return (int(result['rating']) / 5.0) * 15.0
            return 7.5
        except Exception as e:
            print(f"Error scoring organization: {e}")
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

2. RELEVANCE: Does the summary correctly PRIORITIZE the material provisions?
   Plain-language summaries are inherently selective — a 3-5 sentence summary
   cannot list every provision of a multi-page bill and should not try to.
   Judge the summary on how well it identifies and emphasizes the highest-value
   information for a general reader:
   - The bill's central action (what it does, who it applies to)
   - Any provision that materially changes what someone must, may, or cannot do
   - Numeric anchors when material (dollar figures, effective dates, sunset dates)
   Secondary provisions (procedural mechanics, minor definitional cleanups,
   technical cross-references) may be omitted without penalty when a
   reasonable editor would consider them non-essential.

   - 1 = Misses the central action or a materially important provision that
         a reasonable reader would need to understand the bill.
   - 2 = Central action present but a material provision is omitted or buried.
   - 3 = Central action clear; some material provisions covered but
         prioritization is uneven (top-level items skipped in favor of minor
         ones, or vice versa).
   - 4 = Central action and the most important provisions are covered and
         well-prioritized; any omissions are genuinely non-essential.
   - 5 = The summary is well-prioritized — it emphasizes the highest-value
         provisions a general reader needs, and any omitted content is
         legitimately non-essential (procedural detail, minor cross-references,
         technical language). A 5/5 does NOT require exhaustive coverage;
         it requires correct editorial judgment about what to include.

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

BILL TEXT:
{bill_text}
"""

        try:
            result = query_llm_with_retries(
                self.llm_client,
                prompt,
                context,
                _AccuracyLLMResponse,
                self.model_name,
                model_family=self.model_family,
            )
            if not result:
                raise ValueError("LLM returned no structured response")

            return AccuracyScore(
                bill_number=bill_number,
                text_source=text_source,
                groundedness=float(result.get('groundedness', 3)),
                relevance=float(result.get('relevance', 3)),
                interpretation=float(result.get('interpretation', 3)),
                groundedness_reason=result.get('groundedness_reason', ''),
                relevance_reason=result.get('relevance_reason', ''),
                interpretation_reason=result.get('interpretation_reason', ''),
            )
        except Exception as e:
            print(f"Error evaluating accuracy for {bill_number}: {e}")
            return AccuracyScore(
                bill_number=bill_number,
                text_source=text_source,
                groundedness=3.0,
                relevance=3.0,
                interpretation=3.0,
                groundedness_reason="Evaluation failed",
                relevance_reason="Evaluation failed",
                interpretation_reason="Evaluation failed",
            )

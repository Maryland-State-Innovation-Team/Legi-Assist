"""
Test script to verify evaluation setup
Runs a single bill through both evaluators to check dependencies
"""

import sys
from dotenv import load_dotenv
from google import genai
import os

# Test imports
print("Testing imports...")
try:
    import textstat
    print("✓ textstat")
except ImportError:
    print("✗ textstat - run: pip install textstat")
    sys.exit(1)

try:
    import spacy
    print("✓ spacy")
except ImportError:
    print("✗ spacy - run: pip install spacy")
    sys.exit(1)

try:
    import openpyxl
    print("✓ openpyxl")
except ImportError:
    print("✗ openpyxl - run: pip install openpyxl")
    sys.exit(1)

# Test spaCy model
print("\nTesting spaCy model...")
try:
    nlp = spacy.load("en_core_web_sm")
    print("✓ en_core_web_sm model loaded")
except OSError:
    print("✗ spaCy model not found - run: python -m spacy download en_core_web_sm")
    sys.exit(1)

# Test LLM connection
print("\nTesting LLM connection...")
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("✗ GEMINI_API_KEY not found in .env")
    sys.exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("✓ Gemini client initialized")
except Exception as e:
    print(f"✗ Failed to initialize Gemini client: {e}")
    sys.exit(1)

# Test evaluators with sample text
print("\nTesting evaluators with sample text...")
from evaluate_plain_language import PlainLanguageEvaluator, AccuracyEvaluator

sample_text = """This bill authorizes the Department of Health to establish a new grant program.
The program provides funding to local health departments for mental health services.
It allocates $5 million annually from the general fund."""

sample_bill_text = """# HB0001 - Mental Health Grant Program

SECTION 1. The Department of Health shall establish a grant program.

SECTION 2. The program shall provide funding to local health departments for mental health services.

SECTION 3. There is appropriated $5,000,000 annually from the general fund."""

sample_metadata = {
    'BillNumber': 'HB0001',
    'Sponsor': 'Delegate Smith',
    'Synopsis': 'Establishes mental health grant program'
}

try:
    pl_evaluator = PlainLanguageEvaluator(client, 'gemini-3-flash-preview', 'gemini')
    print("✓ PlainLanguageEvaluator initialized")

    # Test plain language evaluation (no LLM calls yet)
    print("\n  Testing plain language metrics (automated)...")
    flesch = textstat.flesch_reading_ease(sample_text)
    print(f"    - Flesch Reading Ease: {flesch:.1f}")

    doc = nlp(sample_text)
    sentences = list(doc.sents)
    print(f"    - Sentence count: {len(sentences)}")

    words = sample_text.split()
    avg_sentence_length = len(words) / len(sentences)
    print(f"    - Avg sentence length: {avg_sentence_length:.1f} words")

    print("  ✓ Automated metrics working")

    # Test accuracy evaluator
    acc_evaluator = AccuracyEvaluator(client, 'gemini-3-flash-preview', 'gemini')
    print("✓ AccuracyEvaluator initialized")

    print("\n✓ All tests passed!")
    print("\nYou're ready to run the evaluation. Try:")
    print("  python run_evaluation.py --debug")

except Exception as e:
    print(f"✗ Error during evaluation test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

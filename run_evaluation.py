"""
Complete Maryland Plain Language Evaluation Pipeline
Loads data, runs evaluations, generates comparative reports
"""

import json
import os
import argparse
from datetime import datetime
from typing import Dict, List
from tqdm import tqdm
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
import ollama
import pandas as pd

from evaluation.evaluators import (
    PlainLanguageEvaluator,
    AccuracyEvaluator,
    PlainLanguageScore,
    AccuracyScore
)


def setup_client(family, model_name):
    """Initialize LLM client (copied from run_pipeline.py)"""
    load_dotenv()
    if family == 'gemini':
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Missing GEMINI_API_KEY")
        return genai.Client(api_key=key)
    elif family == 'gpt':
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("Missing OPENAI_API_KEY")
        return OpenAI(api_key=key)
    else:
        ollama.pull(model_name)
        return ollama.chat


def load_frontend_data(session_year: int) -> List[Dict]:
    """Load frontend_data.json for a session"""
    path = f"data/{session_year}rs/frontend_data.json"
    if not os.path.exists(path):
        print(f"Warning: {path} not found")
        return []

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_bill_markdown(session_year: int, bill_number: str) -> str:
    """Load the converted markdown for a bill"""
    md_path = f"data/{session_year}rs/md/{bill_number}.md"

    if not os.path.exists(md_path):
        return ""

    with open(md_path, 'r', encoding='utf-8') as f:
        return f.read()


def evaluate_session(session_years: List[int], llm_client, model_name: str,
                     model_family: str, debug: bool = False) -> Dict:
    """
    Evaluate all bills across specified session years

    Returns:
        {
            'plain_language_scores': List[PlainLanguageScore],
            'accuracy_scores': List[AccuracyScore],
            'metadata': {...}
        }
    """
    print("Initializing evaluators...")
    pl_evaluator = PlainLanguageEvaluator(llm_client, model_name, model_family)
    acc_evaluator = AccuracyEvaluator(llm_client, model_name, model_family)

    all_pl_scores = []
    all_acc_scores = []

    for year in session_years:
        print(f"\n=== Evaluating {year} Session ===")

        # Load data
        bills = load_frontend_data(year)
        if not bills:
            print(f"No data found for {year}, skipping")
            continue

        if debug:
            print(f"Debug mode: limiting to first 10 bills")
            bills = bills[:10]

        print(f"Loaded {len(bills)} bills from {year}rs/frontend_data.json")

        # Evaluate each bill
        for bill in tqdm(bills, desc=f"Evaluating {year} bills"):
            bill_number = bill.get('BillNumber')
            if not bill_number:
                continue

            # Get both human and AI summaries
            human_synopsis = bill.get('Synopsis', '')  # Official synopsis
            ai_summary = bill.get('bill_summary', '')  # AI-generated summary from QA stage (field name is bill_summary, not summary)

            # Load bill text for context
            bill_text = load_bill_markdown(year, bill_number)

            # Skip if no summaries to compare
            if not human_synopsis and not ai_summary:
                continue

            # Evaluate Human Synopsis (Plain Language only)
            if human_synopsis:
                try:
                    human_pl_score = pl_evaluator.evaluate_text(
                        text=human_synopsis,
                        bill_number=bill_number,
                        text_source='human',
                        bill_context=bill
                    )
                    all_pl_scores.append(human_pl_score)
                except Exception as e:
                    print(f"Error evaluating human synopsis for {bill_number}: {e}")

            # Evaluate AI Summary (Both Plain Language and Accuracy)
            if ai_summary:
                try:
                    # Plain Language
                    ai_pl_score = pl_evaluator.evaluate_text(
                        text=ai_summary,
                        bill_number=bill_number,
                        text_source='ai',
                        bill_context=bill
                    )
                    all_pl_scores.append(ai_pl_score)

                    # Accuracy (only for AI, as human synopsis is ground truth)
                    if bill_text:
                        ai_acc_score = acc_evaluator.evaluate_accuracy(
                            summary=ai_summary,
                            bill_text=bill_text,
                            bill_metadata=bill,
                            bill_number=bill_number,
                            text_source='ai'
                        )
                        all_acc_scores.append(ai_acc_score)
                except Exception as e:
                    print(f"Error evaluating AI summary for {bill_number}: {e}")

    return {
        'plain_language_scores': all_pl_scores,
        'accuracy_scores': all_acc_scores,
        'metadata': {
            'evaluated_at': datetime.now().isoformat(),
            'session_years': session_years,
            'model': f"{model_family}/{model_name}",
            'total_bills': len(all_pl_scores) // 2  # Divide by 2 (human + AI per bill)
        }
    }


def generate_summary_report(results: Dict) -> str:
    """Generate a human-readable summary report"""
    pl_scores = results['plain_language_scores']
    acc_scores = results['accuracy_scores']
    metadata = results['metadata']

    report = []
    report.append("=" * 80)
    report.append("MARYLAND PLAIN LANGUAGE EVALUATION REPORT")
    report.append("=" * 80)
    report.append(f"\nGenerated: {metadata['evaluated_at']}")
    report.append(f"Sessions: {', '.join(map(str, metadata['session_years']))}")
    report.append(f"Model: {metadata['model']}")
    report.append(f"Bills Evaluated: {metadata['total_bills']}")
    report.append("\n" + "=" * 80)

    # Separate human vs AI scores
    human_scores = [s for s in pl_scores if s.text_source == 'human']
    ai_scores = [s for s in pl_scores if s.text_source == 'ai']

    report.append("\n### PLAIN LANGUAGE SCORES (out of 100)")
    report.append("\n" + "-" * 40)

    # Human Synopsis Statistics
    if human_scores:
        human_total_avg = sum(s.total_plain_language_score for s in human_scores) / len(human_scores)
        report.append(f"\nHUMAN SYNOPSES (n={len(human_scores)})")
        report.append(f"  Average Total Score: {human_total_avg:.1f}/100")

        # Component averages
        report.append(f"\n  Component Breakdown:")
        report.append(f"    (a) Everyday Words:        {sum(s.flesch_score + s.jargon_score + s.complex_word_score for s in human_scores) / len(human_scores):.1f}/30")
        report.append(f"    (b) Present/Active:        {sum(s.passive_score + s.past_tense_score for s in human_scores) / len(human_scores):.1f}/20")
        report.append(f"    (c) Short Sentences:       {sum(s.sentence_length_score + s.long_sentence_score for s in human_scores) / len(human_scores):.1f}/25")
        report.append(f"    (d) Definitions:           {sum(s.definition_score for s in human_scores) / len(human_scores):.1f}/10")
        report.append(f"    (e) Organization:          {sum(s.organization_score for s in human_scores) / len(human_scores):.1f}/15")

    # AI Summary Statistics
    if ai_scores:
        ai_total_avg = sum(s.total_plain_language_score for s in ai_scores) / len(ai_scores)
        report.append(f"\n\nAI SUMMARIES (n={len(ai_scores)})")
        report.append(f"  Average Total Score: {ai_total_avg:.1f}/100")

        report.append(f"\n  Component Breakdown:")
        report.append(f"    (a) Everyday Words:        {sum(s.flesch_score + s.jargon_score + s.complex_word_score for s in ai_scores) / len(ai_scores):.1f}/30")
        report.append(f"    (b) Present/Active:        {sum(s.passive_score + s.past_tense_score for s in ai_scores) / len(ai_scores):.1f}/20")
        report.append(f"    (c) Short Sentences:       {sum(s.sentence_length_score + s.long_sentence_score for s in ai_scores) / len(ai_scores):.1f}/25")
        report.append(f"    (d) Definitions:           {sum(s.definition_score for s in ai_scores) / len(ai_scores):.1f}/10")
        report.append(f"    (e) Organization:          {sum(s.organization_score for s in ai_scores) / len(ai_scores):.1f}/15")

    # Comparison
    if human_scores and ai_scores:
        diff = ai_total_avg - human_total_avg
        report.append(f"\n  COMPARISON:")
        report.append(f"    AI vs Human Difference: {diff:+.1f} points")
        if diff > 0:
            report.append(f"    → AI summaries score HIGHER on plain language")
        else:
            report.append(f"    → Human synopses score HIGHER on plain language")

    # Accuracy Scores (AI only)
    if acc_scores:
        report.append("\n\n" + "=" * 80)
        report.append("### ACCURACY SCORES (AI Summaries only)")
        report.append("-" * 40)

        avg_groundedness = sum(s.groundedness for s in acc_scores) / len(acc_scores)
        avg_relevance = sum(s.relevance for s in acc_scores) / len(acc_scores)
        avg_interpretation = sum(s.interpretation for s in acc_scores) / len(acc_scores)

        report.append(f"\nAI SUMMARIES (n={len(acc_scores)})")
        report.append(f"  Groundedness:      {avg_groundedness:.2f}/5.0")
        report.append(f"  Relevance:         {avg_relevance:.2f}/5.0")
        report.append(f"  Interpretation:    {avg_interpretation:.2f}/5.0")

    report.append("\n" + "=" * 80)
    report.append("\nSee detailed results in the JSON output file.")
    report.append("=" * 80)

    return "\n".join(report)


def export_to_excel(results: Dict, output_path: str):
    """Export results to Excel for easier human review"""
    pl_scores = results['plain_language_scores']
    acc_scores = results['accuracy_scores']

    # Convert to DataFrames
    pl_df = pd.DataFrame([
        {
            'Bill Number': s.bill_number,
            'Source': s.text_source,
            'Total Score': s.total_plain_language_score,
            'Flesch': s.flesch_score,
            'Jargon': s.jargon_score,
            'Complex Words': s.complex_word_score,
            'Passive Voice': s.passive_score,
            'Past Tense': s.past_tense_score,
            'Sentence Length': s.sentence_length_score,
            'Long Sentences': s.long_sentence_score,
            'Definitions': s.definition_score,
            'Organization': s.organization_score
        }
        for s in pl_scores
    ])

    acc_df = pd.DataFrame([
        {
            'Bill Number': s.bill_number,
            'Source': s.text_source,
            'Groundedness': s.groundedness,
            'Groundedness Reason': s.groundedness_reason,
            'Relevance': s.relevance,
            'Relevance Reason': s.relevance_reason,
            'Interpretation': s.interpretation,
            'Interpretation Reason': s.interpretation_reason
        }
        for s in acc_scores
    ])

    # Write to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pl_df.to_excel(writer, sheet_name='Plain Language Scores', index=False)
        if not acc_df.empty:
            acc_df.to_excel(writer, sheet_name='Accuracy Scores', index=False)

    print(f"Excel report exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Maryland Plain Language Evaluation')
    parser.add_argument('--years', nargs='+', type=int,
                       default=[2023, 2024, 2025, 2026],
                       help='Session years to evaluate')
    parser.add_argument('--model-family', default='gemini', choices=['gemini', 'gpt', 'ollama'])
    parser.add_argument('--model', default='gemini-3.8-flash')
    parser.add_argument('--debug', action='store_true', help='Limit to first 10 bills per session')
    parser.add_argument('--output-json', default=None, help='Output JSON path (default: evaluation/results/evaluation-YYYYMMDD-{model}.json)')
    parser.add_argument('--output-excel', default=None, help='Output Excel path (default: evaluation/results/evaluation-YYYYMMDD-{model}.xlsx)')
    args = parser.parse_args()

    # Create output directory
    output_dir = 'evaluation/results'
    os.makedirs(output_dir, exist_ok=True)

    # Generate timestamped filenames if not specified
    timestamp = datetime.now().strftime('%Y%m%d')
    model_tag = args.model_family  # Use model family (gemini, gpt, ollama) as tag

    if args.output_json is None:
        args.output_json = f'{output_dir}/evaluation-{timestamp}-{model_tag}.json'
    if args.output_excel is None:
        args.output_excel = f'{output_dir}/evaluation-{timestamp}-{model_tag}.xlsx'

    print(f"=== Maryland Plain Language Evaluation ===")
    print(f"Sessions: {args.years}")
    print(f"Model: {args.model_family}/{args.model}")
    print(f"Debug: {args.debug}")
    print(f"Output: {args.output_json}\n")

    # Initialize LLM client
    print("Initializing LLM client...")
    client = setup_client(args.model_family, args.model)

    # Run evaluation
    results = evaluate_session(
        session_years=args.years,
        llm_client=client,
        model_name=args.model,
        model_family=args.model_family,
        debug=args.debug
    )

    # Convert dataclass objects to dicts for JSON serialization
    results_serializable = {
        'plain_language_scores': [
            {
                'bill_number': s.bill_number,
                'text_source': s.text_source,
                'total_score': s.total_plain_language_score,
                'flesch_score': s.flesch_score,
                'jargon_score': s.jargon_score,
                'complex_word_score': s.complex_word_score,
                'passive_score': s.passive_score,
                'past_tense_score': s.past_tense_score,
                'sentence_length_score': s.sentence_length_score,
                'long_sentence_score': s.long_sentence_score,
                'definition_score': s.definition_score,
                'organization_score': s.organization_score
            }
            for s in results['plain_language_scores']
        ],
        'accuracy_scores': [
            {
                'bill_number': s.bill_number,
                'text_source': s.text_source,
                'groundedness': s.groundedness,
                'groundedness_reason': s.groundedness_reason,
                'relevance': s.relevance,
                'relevance_reason': s.relevance_reason,
                'interpretation': s.interpretation,
                'interpretation_reason': s.interpretation_reason
            }
            for s in results['accuracy_scores']
        ],
        'metadata': results['metadata']
    }

    # Save JSON
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(results_serializable, f, indent=2)
    print(f"\nDetailed results saved to {args.output_json}")

    # Export Excel
    export_to_excel(results, args.output_excel)

    # Print summary report
    print("\n" + generate_summary_report(results))


if __name__ == "__main__":
    main()

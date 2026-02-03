import os
import argparse
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
import ollama

# Import our new modules
from pipeline.state import PipelineState
from pipeline.download import download_session_data
from pipeline.convert import convert_pdfs_to_md
from pipeline.amend import apply_amendments
from pipeline.qa import run_qa, export_qa_to_csv

def setup_client(family, model_name):
    load_dotenv()
    if family == 'gemini':
        key = os.getenv("GEMINI_API_KEY")
        if not key: raise ValueError("Missing GEMINI_API_KEY")
        return genai.Client(api_key=key)
    elif family == 'gpt':
        key = os.getenv("OPENAI_API_KEY")
        if not key: raise ValueError("Missing OPENAI_API_KEY")
        return OpenAI(api_key=key)
    else:
        ollama.pull(model_name)
        return ollama.chat

def main():
    parser = argparse.ArgumentParser(description='Maryland Legislation Pipeline')
    parser.add_argument('--year', type=int, default=2026, help='Session Year')
    parser.add_argument('--model-family', default='gemini', choices=['gemini', 'gpt', 'ollama'])
    parser.add_argument('--model', default='gemini-3-flash-preview', help='Model Name')
    args = parser.parse_args()

    print(f"--- Starting Pipeline for {args.year} ---")
    
    # 1. Initialize State
    state = PipelineState(args.year)
    
    # 2. Initialize LLM Client (used for Amend and QA)
    client = setup_client(args.model_family, args.model)

    # 3. Download Stage
    # This returns all bills, but updates state for new ones
    all_bills = download_session_data(args.year, state)
    
    # 4. Process Loop
    # We iterate through all known bills and check their 'needs_*' flags
    for bill_number in all_bills:
        bill_data = state.get_bill(bill_number)

        # Convert Stage
        if bill_data.get('needs_convert'):
            print(f"[{bill_number}] Converting...")

            convert_pdfs_to_md(args.year, bill_number, state)
            # Refresh state
            bill_data = state.get_bill(bill_number)

        # Amend Stage
        if bill_data.get('needs_convert'):
            # Double check logic: if convert happened, we might need amend
            pass 
        
        if bill_data.get('needs_amend'):
            print(f"[{bill_number}] Amending...")
            apply_amendments(args.year, bill_number, state, client, args.model, args.model_family)
            bill_data = state.get_bill(bill_number)

        # QA Stage
        if bill_data.get('needs_qa'):
            print(f"[{bill_number}] Running QA...")
            run_qa(args.year, bill_number, state, client, args.model, args.model_family)

    # 5. Final Export
    export_qa_to_csv(args.year, state)
    print("--- Pipeline Complete ---")

if __name__ == "__main__":
    main()

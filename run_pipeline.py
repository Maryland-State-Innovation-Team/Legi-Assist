import os
import argparse
import json
from tqdm import tqdm
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
import ollama

# Import our new modules
from pipeline.state import PipelineState
from pipeline.download import download_session_data
from pipeline.convert import convert_pdfs_to_md
from pipeline.amend import apply_amendments
from pipeline.qa import run_qa

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
    parser.add_argument('--debug', action='store_true', help='Limit processing to first 10 bills')
    args = parser.parse_args()

    print(f"--- Starting Pipeline for {args.year} ---")
    
    # 1. Initialize State
    state = PipelineState(args.year)
    
    # 2. Initialize LLM Client (used for Amend and QA)
    client = setup_client(args.model_family, args.model)

    # 3. Download Stage
    # This returns all bills, but updates state for new ones
    all_bills = download_session_data(args.year, state)
    
    if args.debug:
        print("Debug mode: Limiting processing to first 10 bills.")
        all_bills = all_bills[:10]
    
    # 4. Process Loop
    # We iterate through all known bills and check their 'needs_*' flags
    for bill_number in tqdm(all_bills, desc="Processing Bills"):
        bill_data = state.get_bill(bill_number)

        # Convert Stage
        if bill_data.get('needs_convert'):
            convert_pdfs_to_md(args.year, bill_number, state)
            # Refresh state
            bill_data = state.get_bill(bill_number)

        # Amend Stage
        if bill_data.get('needs_amend'):
            apply_amendments(args.year, bill_number, state, client, args.model, args.model_family)
            bill_data = state.get_bill(bill_number)

        # QA Stage
        if bill_data.get('needs_qa'):
            run_qa(args.year, bill_number, state, client, args.model, args.model_family)

    # 5. Final Export
    export_frontend_data(args.year, state)
    print("--- Pipeline Complete ---")

def export_frontend_data(session_year, state_manager):
    print(f"Exporting frontend data for {session_year}...")
    
    # 1. Load legislation.json
    leg_path = os.path.join(f"data/{session_year}rs", "legislation.json")
    if not os.path.exists(leg_path):
        print(f"Warning: {leg_path} not found. Skipping frontend export.")
        return

    with open(leg_path, 'r', encoding='utf-8') as f:
        legislation_list = json.load(f)

    # 2. Combine with QA results from state
    combined_data = []
    for bill in legislation_list:
        bill_number = bill.get('BillNumber')
        bill_state = state_manager.get_bill(bill_number)
        
        # Add timestamps for frontend sorting
        bill['first_seen'] = bill_state.get('first_seen')
        bill['last_updated'] = bill_state.get('last_updated')

        # Add fiscal note status
        files = bill_state.get('files', {})
        bill['has_fiscal_note'] = bool(files.get('fiscal_note'))
        
        # Merge QA results if they exist
        qa_results = bill_state.get('qa_results')
        if qa_results:
            bill.update(qa_results)
        
        combined_data.append(bill)

    # 3. Save to frontend_data.json
    out_path = os.path.join(f"data/{session_year}rs", "frontend_data.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"Frontend data exported to {out_path}")

if __name__ == "__main__":
    main()

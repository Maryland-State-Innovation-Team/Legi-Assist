import os
import pandas as pd
import json
from pydantic import BaseModel
from typing import Optional, List, Literal
from llm_utils import query_llm_with_retries
import csv

# Load agencies for validation
agencies_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'maryland_agencies.csv')
agencies_df = pd.read_csv(agencies_path)
unique_agencies = sorted(agencies_df['Agency Name'].dropna().unique().tolist())

# Define Schema
class AnswersToQuestions(BaseModel):
    bill_summary: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    funding: Optional[float] = None
    responsible_party: str
    stakeholders: str
    fiscal_impact_summary: Optional[str] = None

class AgencyRelevance(BaseModel):
    agency_name: Literal[tuple(unique_agencies)]
    is_relevant: bool
    relevance_explanation: str

class AgencyAnalysis(BaseModel):
    relevant_agencies: List[AgencyRelevance]

question_dict = {
    'bill_summary': 'Write a brief, plain-English summary of the bill.',
    'start_year': 'What year does the bill take effect?',
    'end_year': 'What year does the bill expire or sunset?',
    'funding': 'How much funding is allocated or mandated by the bill? (if millions, write out full number. E.g. "1 million" should be 1000000)',
    'responsible_party': 'What Maryland State agency, department, office, or role is responsible for implementing the bill?',
    'stakeholders': 'What population will be impacted by the bill?',
    'fiscal_impact_summary': 'Summarize the state and local fiscal impact as described in the Fiscal Note. Include estimates for revenues and expenditures if available.',
}

SYSTEM_PROMPT = (
    "You are reading markdown generated from the text of a bill passed by the Maryland General Assembly, "
    "and its associated Fiscal and Policy Note (appended at the end). "
    "Note that ~ syntax means text has been stricken. "
    "Answer the following questions:\n"
    "{}\n"
    "Please respond with only valid JSON in the specified format."
).format("\n".join([f"- {key}: {value}" for key, value in question_dict.items()]))


def get_agency_prompt(agencies_text):
    return (
        "You are an expert policy analyst. Review the provided bill text and fiscal note. "
        "We have a list of Maryland State Agencies and their summaries. "
        "For EACH agency in the list, determine if the bill is relevant to their work or has a notable fiscal impact on them, "
        "based on the provided Agency Summary.\n\n"
        "Return a list of ONLY the agencies that are relevant or impacted.\n\n"
        "AGENCIES LIST:\n"
        f"{agencies_text}\n\n"
        "Analyze the bill's content against each agency's summary to make your determination."
    )

def load_agencies(csv_path):
    agencies = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                agencies.append(f"Agency: {row.get('Agency Name', 'Unknown')}\nSummary: {row.get('Summary', 'N/A')}")
    return "\n---\n".join(agencies)



def run_qa(session_year: int, bill_number: str, state_manager, client, model_name, model_family):
    md_dir = os.path.abspath(f'data/{session_year}rs/md')
    
    # Prefer amended text, fall back to original
    bill_path = os.path.join(md_dir, f"{bill_number}_amended.md")
    if not os.path.exists(bill_path):
        bill_path = os.path.join(md_dir, f"{bill_number}.md")
    
    if not os.path.exists(bill_path):
        print(f"No text available for QA: {bill_number}")
        return

    with open(bill_path, 'r', encoding='utf-8') as f:
        bill_md = f.read()

    # Load Fiscal Note if available
    fn_path = os.path.join(md_dir, f"{bill_number}_fn.md")
    if os.path.exists(fn_path):
        with open(fn_path, 'r', encoding='utf-8') as f:
            fn_md = f.read()
        bill_md += f"\n\nFISCAL NOTE:\n{fn_md}"

    print(f"Running QA on {bill_number}...")
    try:
        # 1. General QA
        response = query_llm_with_retries(
            client=client,
            prompt=SYSTEM_PROMPT,
            value=bill_md,
            response_format=AnswersToQuestions,
            model_name=model_name,
            max_retries=3,
            model_family=model_family
        )
        
        qa_data = {}
        if response:
            qa_data = response.model_dump()
        
        # 2. Agency Relevance Analysis
        agencies_csv = os.path.abspath('data/maryland_agencies.csv')
        agencies_text = load_agencies(agencies_csv)
        
        if agencies_text:
            print(f"Running Agency Analysis on {bill_number}...")
            agency_prompt = get_agency_prompt(agencies_text)
            agency_response = query_llm_with_retries(
                client=client,
                prompt=agency_prompt,
                value=bill_md,
                response_format=AgencyAnalysis,
                model_name=model_name,
                max_retries=3,
                model_family=model_family
            )
            
            if agency_response:
                # Store as a list of dicts
                qa_data['agency_relevance'] = [a.model_dump() for a in agency_response.relevant_agencies]

        if qa_data:
            state_manager.update_bill(bill_number, {
                "qa_results": qa_data,
                "needs_qa": False
            })
            
    except Exception as e:
        print(f"QA Failed for {bill_number}: {e}")

def export_qa_to_csv(session_year: int, state_manager):
    """Generates the final CSV from the state file."""
    data = []
    for bill_num, info in state_manager.data.items():
        res = info.get('qa_results')
        if res:
            row = {'BillNumber': bill_num}
            row.update(res)
            data.append(row)
            
    if data:
        # Also export as JSON for easier web consumption
        json_out_path = os.path.abspath(f'data/{session_year}rs/legislation_qa.json')
        with open(json_out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Exported QA JSON to {json_out_path}")

        # Export to CSV
        csv_data = []
        for item in data:
            row = item.copy()
            if 'agency_relevance' in row and isinstance(row['agency_relevance'], list):
                row['agency_relevance'] = json.dumps(row['agency_relevance'])
            csv_data.append(row)

        df = pd.DataFrame(csv_data)
        out_path = os.path.abspath(f'data/{session_year}rs/csv/legislation_model_responses.csv')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Exported QA results to {out_path}")

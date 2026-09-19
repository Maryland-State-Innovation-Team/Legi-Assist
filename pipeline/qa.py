import os
import pandas as pd
import json
import hashlib
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from llm_utils import query_llm_with_retries
import csv

_legislation_json_cache = {}

def get_bill_json_info(session_year, bill_number):
    """Retrieves bill info from the master legislation.json file, with caching."""
    if session_year not in _legislation_json_cache:
        json_path = os.path.abspath(f'data/{session_year}rs/legislation.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    _legislation_json_cache[session_year] = {b['BillNumber']: b for b in data}
            except Exception as e:
                print(f"Error loading {json_path}: {e}")
                _legislation_json_cache[session_year] = {}
        else:
            _legislation_json_cache[session_year] = {}
    return _legislation_json_cache[session_year].get(bill_number)

# Load agencies for validation
agencies_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'maryland_agencies.csv')
agencies_df = pd.read_csv(agencies_path)
unique_agencies = sorted(agencies_df['Agency Name'].dropna().unique().tolist())

# Define Schema
class AnswersToQuestions(BaseModel):
    bill_summary: str = Field(description=(
        "Plain-English summary of the bill in 4–6 short sentences. "
        "Open with the verb that names the bill's central action — e.g. 'Exempts survivors of fallen public safety workers…' or 'Authorizes the Sheriff…'. "
        "Do NOT open with 'This bill', 'This act', or 'The bill'; start with the verb.\n\n"

        "SELECT, DO NOT ENUMERATE. Pick the highest-value provisions for a general reader; do not list everything. "
        "Priority order: (1) the bill's central action, (2) provisions that materially change what someone must/may/cannot do, "
        "(3) numeric anchors (dollar figures, effective dates, sunset dates, phase-in years, funding tiers), "
        "(4) enumerated sub-categories ONLY when the specific items are the substantive point of the bill. "
        "Omit procedural mechanics and minor cross-references.\n\n"

        "SCOPE PRECISION. Name scope exactly — WHO and WHAT. Do not narrow scope. "
        "If the bill covers 'all public institutions of higher education', do not write 'community colleges'.\n\n"

        "COORDINATED CATEGORIES. When a bill regulates coordinated items ('trees of heaven AND invasive bamboo', "
        "'all public institutions AND community colleges'), preserve every category by name. Do not compress 'X and Y' into 'X'. "
        "Defined terms that get their own section must appear.\n\n"

        "CONDITIONAL TRIGGERS. Preserve triggers on requirements: 'must report incidents WHEN there is a substantial change'. "
        "A requirement without its trigger reads as universal, which misrepresents the bill.\n\n"

        "MODAL AND MECHANISM PRECISION. Modal verbs verbatim: 'authorizes' for permissive authority, 'requires' for mandates, "
        "'establishes' for new programs, 'prohibits' for bans, 'repeals' for removals. "
        "Verbs of authority verbatim: 'determined by X' is not 'provided by X' or 'set by X'.\n\n"

        "CONCRETE EXAMPLES OF DEFECTS TO AVOID:\n"
        "Bill text: 'incidents motivated in whole or in substantial part by actual or perceived personal characteristics'\n"
        "  WRONG: 'incidents motivated by actual personal characteristics' (dropped 'or perceived')\n"
        "  RIGHT: 'incidents motivated by actual or perceived personal characteristics'\n"
        "Bill text: 'each public institution of higher education and community college shall adopt a plan'\n"
        "  WRONG: 'requires community colleges to adopt a plan'\n"
        "  RIGHT: 'requires each public institution of higher education and community college to adopt a plan'\n"
        "Bill text: 'the County Council may determine the salary'\n"
        "  WRONG: 'the Council provides the salary'\n"
        "  RIGHT: 'the Council determines the salary'\n"
        "Bill text: 'trees of heaven, listed invasive trees, and invasive bamboo'\n"
        "  WRONG: 'trees of heaven and listed invasive trees' (dropped 'invasive bamboo')\n"
        "  RIGHT: 'trees of heaven, listed invasive trees, and invasive bamboo'\n"
        "Bill text: 'may not exceed 80% of the maximum approved rate for medium-duty towing'\n"
        "  WRONG: 'capped at 80%' (loses the reference basis)\n"
        "  RIGHT: 'may not exceed 80% of the maximum medium-duty rate'\n\n"

        "STYLE. Present tense, active voice. Every sentence 20 words or fewer; aim for 12–15.\n\n"

        "AMENDMENT DIRECTION. When the bill AMENDS existing law, describe what changes — added, "
        "removed, expanded, narrowed, repealed. A subsection stricken from the bill (shown with ~strikethrough~) "
        "is REMOVED from law, and provisions that reference it must reflect that removal. Do not present the "
        "removed language as still in force. If a provision is CONDITIONALLY EXCLUDED (e.g. 'this obligation "
        "does not apply to X'), say so — do not describe a broader obligation than the amended law actually creates.\n\n"

        "GROUND every claim in the bill text or Fiscal Note. Do not attribute a standard to any agency, "
        "institution, or document unless the bill names it explicitly. When in doubt, omit rather than invent."
    ))
    start_year: Optional[int] = Field(default=None, description=(
        "Four-digit calendar year the bill takes effect, taken from the bill's effective-date clause. "
        "Do not infer; leave null if the bill states no effective date."
    ))
    end_year: Optional[int] = Field(default=None, description=(
        "Four-digit calendar year the bill expires or sunsets, if explicitly stated. Leave null when there is no sunset."
    ))
    funding: Optional[float] = Field(default=None, description=(
        "Estimated dollar impact as a plain number (write 1000000, not '1 million'). "
        "Prefer the Fiscal Note's dollar figure; if only the bill text specifies, use that. "
        "Use a positive number for new spending or new revenue and a negative number for revenue loss or spending reductions. "
        "Leave null when the impact is described only qualitatively."
    ))
    responsible_party: str = Field(description=(
        "Full name of the Maryland State agency, department, office, board, or role responsible for implementing "
        "the bill (e.g. 'Maryland Higher Education Commission'). If multiple, list them separated by semicolons."
    ))
    stakeholders: str = Field(description=(
        "Specific population(s) directly affected by the bill — who benefits, who is regulated, who pays. "
        "Be concrete (e.g. 'volunteer firefighters in Anne Arundel County', not 'residents')."
    ))
    fiscal_impact_summary: Optional[str] = Field(default=None, description=(
        "Concise state and local fiscal impact. Use the Fiscal Note's revenue and expenditure estimates when present. "
        "If only qualitative language is available, describe the direction and mechanism "
        "(e.g. 'Indeterminate increase in local costs from new record-keeping mandate') and note that specific figures are unavailable."
    ))

class AgencyRelevance(BaseModel):
    agency_name: Literal[tuple(unique_agencies)]
    is_relevant: bool
    relevance_explanation: str
    relevance_rating: int = Field(description="Relevance rating from 1 to 5, with 5 being the most relevant")

class AgencyAnalysis(BaseModel):
    relevant_agencies: List[AgencyRelevance]


SYSTEM_PROMPT = (
    "You are analyzing a chaptered bill from the Maryland General Assembly. "
    "The input is markdown extracted from the bill text; a Fiscal and Policy Note follows the marker 'FISCAL NOTE:'. "
    "Text wrapped in ~ ~ has been stricken and is not enacted. "
    "Populate every required field of the schema using facts supported by the bill text or the Fiscal Note. "
    "Use null for optional fields only when the information is genuinely absent."
)


def get_agency_prompt(agencies_text):
    return (
        "You are an expert policy analyst. Review the provided bill text and fiscal note. "
        "We have a list of Maryland State Agencies and their summaries. "
        "For EACH agency in the list, determine if the bill is relevant to their work or has a notable fiscal impact on them, "
        "based on the provided Agency Summary.\n\n"
        "Return a list of ONLY the agencies that are relevant or impacted.\n\n"
        "For each relevant agency, provide a relevance_rating from 1 to 5, where 5 is the most relevant (e.g., they are the primary implementing agency) and 1 is low relevance (e.g., they are minimally impacted or mentioned).\n\n"
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
    
    bill_md = ""
    if os.path.exists(bill_path):
        with open(bill_path, 'r', encoding='utf-8') as f:
            bill_md = f.read()
    else:
        # Fallback to legislation.json
        bill_info = get_bill_json_info(session_year, bill_number)
        if bill_info:
            title = bill_info.get('Title') or ''
            synopsis = bill_info.get('Synopsis') or ''
            
            # Use 'or []' to handle cases where the key exists but value is None
            broad_list = bill_info.get('BroadSubjects') or []
            broad = [s.get('Name') for s in broad_list if s]
            
            narrow_list = bill_info.get('NarrowSubjects') or []
            narrow = [s.get('Name') for s in narrow_list if s]
            
            bill_md = f"# {title}\n\n"
            bill_md += f"## Synopsis\n{synopsis}\n\n"
            if broad:
                bill_md += f"Broad Subjects: {', '.join(broad)}\n"
            if narrow:
                bill_md += f"Narrow Subjects: {', '.join(narrow)}\n"

    # Load Fiscal Note if available (always try to append it)
    fn_path = os.path.join(md_dir, f"{bill_number}_fn.md")
    if os.path.exists(fn_path):
        with open(fn_path, 'r', encoding='utf-8') as f:
            fn_md = f.read()
        if bill_md:
            bill_md += f"\n\nFISCAL NOTE:\n{fn_md}"
        else:
            bill_md = f"FISCAL NOTE:\n{fn_md}"

    if not bill_md:
        print(f"No text, JSON info, or Fiscal Note available for QA: {bill_number}")
        return

    # Check hash to see if input changed
    current_hash = hashlib.sha256(bill_md.encode('utf-8')).hexdigest()
    bill_state = state_manager.get_bill(bill_number)
    
    if bill_state.get('qa_input_hash') == current_hash and bill_state.get('qa_results'):
        state_manager.update_bill(bill_number, {"needs_qa": False})
        return

    # 1. General QA
    response = query_llm_with_retries(
        client=client,
        prompt=SYSTEM_PROMPT,
        value=bill_md,
        response_format=AnswersToQuestions,
        model_name=model_name,
        model_family=model_family
    )
    
    qa_data = {}
    if response:
        qa_data = response
    
    # 2. Agency Relevance Analysis
    agencies_csv = os.path.abspath('data/maryland_agencies.csv')
    agencies_text = load_agencies(agencies_csv)
    
    if agencies_text:
        agency_prompt = get_agency_prompt(agencies_text)
        agency_response = query_llm_with_retries(
            client=client,
            prompt=agency_prompt,
            value=bill_md,
            response_format=AgencyAnalysis,
            model_name=model_name,
            model_family=model_family
        )
        
        if agency_response:
            # Store as a list of dicts
            qa_data['agency_relevance'] = agency_response.get('relevant_agencies', [])

    if qa_data:
        state_manager.update_bill(bill_number, {
            "qa_results": qa_data,
            "needs_qa": False,
            "qa_input_hash": current_hash
        })

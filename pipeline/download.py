import os
import requests
import re
import hashlib
import json
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from typing import List, Dict, Optional

def download_session_data(session_year: int, state_manager) -> List[str]:
    """
    Downloads master list, updates state, and returns list of BillNumbers to process.
    """
    base_url = "https://mgaleg.maryland.gov"
    json_url = f'{base_url}/{session_year}rs/misc/billsmasterlist/legislation.json'
    headers = {'User-Agent': 'Mozilla/5.0 (Custom Pipeline)'}

    print(f"Fetching master list from {json_url}...")
    resp = requests.get(json_url, headers=headers)
    resp.raise_for_status()
    leg_data = resp.json()

    # Save master list for reference
    master_list_path = os.path.abspath(f'data/{session_year}rs/legislation.json')
    os.makedirs(os.path.dirname(master_list_path), exist_ok=True)
    with open(master_list_path, 'w', encoding='utf-8') as f:
        json.dump(leg_data, f, indent=2)

    # Filter invalid entries
    if session_year != 2026:
        leg_data = [l for l in leg_data if l.get('ChapterNumber')]

    leg_data_map = {l['BillNumber']: l for l in leg_data}

    df = pd.DataFrame.from_records(leg_data)
    # Sort to prioritize HB over SB (Dedup logic)
    df.sort_values(by='BillNumber', inplace=True)
    
    seen_crossfiles = set()
    bills_to_process = []

    pdf_dir = os.path.abspath(f'data/{session_year}rs/pdf')
    os.makedirs(pdf_dir, exist_ok=True)

    for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="Scanning Bill List"):
        bill_number = row['BillNumber']
        crossfile = row.get('CrossfileBillNumber')

        # Crossfile Dedup
        if bill_number in seen_crossfiles:
            continue
        if crossfile:
            seen_crossfiles.add(crossfile)

        # Check State
        bill_state = state_manager.get_bill(bill_number)
        
        # Calculate Hash
        raw_bill_data = leg_data_map.get(bill_number, {})
        data_to_hash = raw_bill_data.copy()
        data_to_hash.pop('StatusCurrentAsOf', None)
        
        # Use consistent JSON serialization for hashing
        current_hash = hashlib.md5(json.dumps(data_to_hash, sort_keys=True).encode('utf-8')).hexdigest()
        stored_hash = bill_state.get('bill_hash')

        should_check_html = False
        if current_hash != stored_hash:
            should_check_html = True
        
        # We always return the bill to the pipeline, the pipeline decides to run specific stages
        # But we perform the scraping here if 'needs_download' is True or if we want to refresh
        
        if should_check_html or bill_state.get('needs_download'):
            # tqdm.write(f"Checking HTML for {bill_number}...") # Optional: log if needed without breaking bar
            files_downloaded = scrape_and_download(session_year, bill_number, pdf_dir, headers)
            
            # If check was successful (returned dict, even if empty)
            if files_downloaded is not None:
                updates = {
                    "needs_download": False, 
                    "last_seen": pd.Timestamp.now().isoformat(),
                    "bill_hash": current_hash
                }
                
                # If new files were downloaded, mark downstream dirty
                if files_downloaded:
                    updates["files"] = files_downloaded
                    state_manager.mark_dirty(bill_number, 'convert')
                
                state_manager.update_bill(bill_number, updates)
        
        bills_to_process.append(bill_number)

    return bills_to_process

def scrape_and_download(session_year, bill_number, output_dir, headers) -> Optional[Dict[str, str]]:
    """Scrapes the specific bill page and downloads PDFs. Returns dict of file paths or None on failure."""
    url = f'https://mgaleg.maryland.gov/mgawebsite/Legislation/Details/{bill_number}?ys={session_year}rs'
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(r.content, 'html.parser')
    downloaded_files = {}

    # 1. Fiscal and Policy Note
    # We search globally for the URL prefix as requested
    fn_prefix = f'/{session_year}RS/fnotes/'
    fn_link = None
    for anchor in soup.find_all('a', href=True):
        if anchor['href'].startswith(fn_prefix):
            fn_link = anchor['href']
            break  # Take the first matching one
    
    if fn_link:
        fn_path = os.path.join(output_dir, f"{bill_number}_fn.pdf")
        try:
            if _download_file(f"https://mgaleg.maryland.gov{fn_link}", fn_path, headers):
                downloaded_files['fiscal_note'] = fn_path
        except Exception as e:
            print(f"Error downloading fiscal note for {bill_number}: {e}")
            # Decide if fiscal note failure is critical. Usually yes if it's there.
            return None

    # 2. Main Bill PDF & Amendments
    # Look for the second table usually containing bill text links
    tables = soup.find_all('table')
    bill_link = None
    amendments = {}

    if len(tables) > 1:
        target = tables[1]
        for anchor in target.find_all('a', href=True):
            href = anchor['href']
            # Find Bill Text
            if href.startswith(f'/{session_year}RS/bills/') or href.startswith(f'/{session_year}RS/Chapters'):
                bill_link = href
                amendments = {} # Reset if we find a newer bill version
            
            # Find Adopted Amendments
            elif href.startswith(f'/{session_year}RS/amds/'):
                if bill_link and 'Adopted' in anchor.parent.text and 'Withdrawn' not in anchor.parent.text:
                    amd_id = anchor.text.replace("/", "_").strip()
                    amendments[amd_id] = href

    # Download Main Bill
    try:
        if bill_link:
            fname = f"{bill_number}.pdf"
            fpath = os.path.join(output_dir, fname)
            if _download_file(f"https://mgaleg.maryland.gov{bill_link}", fpath, headers):
                downloaded_files['bill_pdf'] = fpath

        # Download Amendments
        downloaded_files['amendments'] = []
        for amd_id, amd_href in amendments.items():
            fname = f"{bill_number}_amd{amd_id}.pdf"
            fpath = os.path.join(output_dir, fname)
            if _download_file(f"https://mgaleg.maryland.gov{amd_href}", fpath, headers):
                 downloaded_files['amendments'].append(fpath)
    except Exception as e:
        print(f"Error downloading files for {bill_number}: {e}")
        return None

    return downloaded_files

def _download_file(url, path, headers) -> bool:
    """
    Returns True if file was downloaded (new/changed), False if existed.
    Raises Exception on failure.
    """
    if os.path.exists(path):
        return False # Skip if exists (Basic Idempotency)
    
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    return True
import os
import sys
import argparse
import csv
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pandas as pd
from tqdm import tqdm
from pydantic import BaseModel, Field

# Reconfigure stdout to always use utf-8 to prevent encoding errors
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables (Expects GEMINI_API_KEY)
load_dotenv()

# --- Configuration ---
MD_GOV_URL = "https://www.maryland.gov/your-government/state-agencies-and-departments"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def scrape_agencies():
    """Scrapes Maryland.gov for agency names and URLs."""
    print(f"Scraping Agency Directory: {MD_GOV_URL}")
    try:
        response = requests.get(MD_GOV_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Target the specific container div.usa-prose
        container = soup.select_one('div.usa-prose')
        agencies = []
        
        if container:
            links = container.find_all('a', href=True)
            for link in links:
                name = link.get_text(strip=True)
                url = link['href']
                
                # Filter out obvious noise
                if url.startswith('http') and len(name) > 3:
                    agencies.append({"name": name, "url": url})
        
        print(f"Found {len(agencies)} total entities.")
        return agencies

    except Exception as e:
        print(f"Error scraping agencies: {e}")
        return []

class AgencyMetadata(BaseModel):
    summary: str = Field(description="A concise summary paragraph describing exactly what this agency does, its primary responsibilities, and the type of work it performs for Maryland residents.")
    acronym: str = Field(description="The most common acronym by which the agency is described, if it is described by an acronym commonly. If not, this should be left blank.")
    aliases: str = Field(description="Semi-colon separated list of aliases or former names for the agency or program if they have changed over time. If there are multiple aliases, semi-colon separate them.")

def get_agency_summary(client, agency_name):
    """
    Uses Gemini with Google Search grounding to summarize the agency and extract metadata.
    """
    prompt = f"""
    Search for the Maryland state agency named "{agency_name}". 
    Provide a summary, acronym, and aliases for the agency.
    """

    # configure the tool
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        response_mime_type="application/json",
        response_schema=AgencyMetadata
    )

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=config
        )
        # Parse the JSON response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback if valid JSON isn't returned
            print(f"Warning: Could not parse JSON for {agency_name}")
            return {"summary": response.text.strip(), "acronym": "", "aliases": ""}
            
    except Exception as e:
        print(f"Error generating summary for {agency_name}: {e}")
        return {"summary": f"Error: {e}", "acronym": "", "aliases": ""}

def main():
    # 1. Setup Arguments & Check API Key
    parser = argparse.ArgumentParser(description="Scrape and summarize Maryland agencies.")
    parser.add_argument("--rerun", action="store_true", help="Rerun processing for agencies with missing acronyms/aliases.")
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    # 2. Configuration & Sideloading
    # Add manual agencies here. Use empty string for URL if unknown.
    SIDELOADED_AGENCIES = [
        {"name": "Maryland State Innovation Team", "url": "https://innovation.maryland.gov/Pages/default.aspx"},
    ]
    
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "maryland_agencies.csv")

    # 3. Load Existing Data
    if os.path.exists(output_file):
        try:
            df = pd.read_csv(output_file)
            # Ensure new columns exist if they don't
            for col in ['Acronym', 'Alias']:
                if col not in df.columns:
                    df[col] = ""
            print(f"Loaded {len(df)} existing records from {output_file}.")
        except Exception as e:
            print(f"Warning: Could not read existing CSV ({e}). Starting fresh.")
            df = pd.DataFrame(columns=['Agency Name', 'URL', 'Summary', 'Acronym', 'Alias'])
    else:
        df = pd.DataFrame(columns=['Agency Name', 'URL', 'Summary', 'Acronym', 'Alias'])

    # Fill NaN values to avoid issues
    df = df.fillna("")

    # 4. Scrape & Merge
    scraped_agencies = scrape_agencies()
    all_candidates = scraped_agencies + SIDELOADED_AGENCIES

    # Create a set of existing names for fast lookup
    existing_names = set(df['Agency Name'].str.strip())
    
    new_rows = []
    for agency in all_candidates:
        name = agency['name'].strip()
        
        # Noise Filter
        if "county" in name.lower() or "baltimore city" in name.lower():
            continue
            
        # Add if not exists
        if name not in existing_names:
            new_rows.append({
                'Agency Name': agency['name'], 
                'URL': agency['url'], 
                'Summary': "", 
                'Acronym': "", 
                'Alias': ""
            })
            existing_names.add(name) # Prevent duplicates within the scrape list itself if any

    if new_rows:
        print(f"Adding {len(new_rows)} new agencies to the list...")
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # 5. Identify Rows to Process
    to_process_indices = []
    
    for idx, row in df.iterrows():
        summary = str(row['Summary']).strip()
        acronym = str(row['Acronym']).strip()
        alias = str(row['Alias']).strip()
        
        should_process = False
        
        # Always process if summary is missing
        if not summary:
            should_process = True
        # If rerun is requested, check if we need to backfill metadata
        elif args.rerun:
             # Process if Acronym or Alias are empty (and we want to fill them)
             # Note: Some agencies might genuinely not have them, but we'll retry.
             if not acronym and not alias: 
                 should_process = True
        
        if should_process:
            to_process_indices.append(idx)

    print(f"\n--- Processing {len(to_process_indices)} Agencies (Updating {output_file}) ---\n")

    if to_process_indices:
        # 6. Initialize GenAI Client
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        count = 0
        for idx in tqdm(to_process_indices):
            name = df.at[idx, 'Agency Name']
            
            # Using tqdm.write prevents the progress bar from breaking visually when printing
            tqdm.write(f"Processing: {name}...")

            # Generate Summary and Metadata
            metadata = get_agency_summary(client, name)

            # Update DataFrame
            df.at[idx, 'Summary'] = metadata.get('summary', '')
            df.at[idx, 'Acronym'] = metadata.get('acronym', '')
            df.at[idx, 'Alias'] = metadata.get('aliases', '')

            # Save incrementally (in case of crash)
            df.to_csv(output_file, index=False)
            count += 1

        print(f"Finished processing {count} agencies.")
    else:
        print("No agencies need processing.")

    # 8. Generate JSON Mirror
    json_output_file = os.path.join(output_dir, "maryland_agencies.json")
    try:
        print(f"Updating JSON mirror at {json_output_file}...")
        # Read clean DF from file or use current
        df = pd.read_csv(output_file).fillna("")
        
        # Convert to dictionary keyed by Agency Name
        # We use drop=False to keep the 'Agency Name' inside the value object too
        json_data = df.set_index('Agency Name', drop=False).to_dict(orient='index')
        
        with open(json_output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        print("JSON output generated successfully.")
    except Exception as e:
        print(f"Error generating JSON: {e}")

if __name__ == "__main__":
    main()
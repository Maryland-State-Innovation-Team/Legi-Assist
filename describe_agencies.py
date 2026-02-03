import os
import sys
import csv
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pandas as pd
from tqdm import tqdm

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

def get_agency_summary(client, agency_name):
    """
    Uses Gemini with Google Search grounding to summarize the agency.
    """
    prompt = f"""
    Search for the Maryland state agency named "{agency_name}". 
    Write a concise summary paragraph describing exactly what this agency does, 
    its primary responsibilities, and the type of work it performs for Maryland residents.
    """

    # configure the tool
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        response_mime_type="text/plain"
    )

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        return f"Error generating summary: {e}"

def main():
    # 1. Check API Key
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

    # 3. Load Existing Data (Idempotence)
    processed_agencies = set()
    file_exists = os.path.exists(output_file)
    
    if file_exists:
        try:
            # We read the CSV to see what we have already finished.
            # We check for rows where 'Summary' is not empty/null.
            df = pd.read_csv(output_file)
            if 'Agency Name' in df.columns and 'Summary' in df.columns:
                # Normalize names for comparison (strip whitespace)
                finished_df = df[df['Summary'].notna() & (df['Summary'] != "")]
                processed_agencies = set(finished_df['Agency Name'].str.strip())
            print(f"Loaded {len(processed_agencies)} existing records from {output_file}.")
        except Exception as e:
            print(f"Warning: Could not read existing CSV ({e}). Starting fresh.")

    # 4. Scrape & Merge
    scraped_agencies = scrape_agencies()
    all_candidates = scraped_agencies + SIDELOADED_AGENCIES

    # 5. Filter Candidates
    # We filter out agencies that are:
    #   a) Already processed
    #   b) 'County' or 'Baltimore City' (Noise filter)
    agencies_to_process = []
    
    for agency in all_candidates:
        name = agency['name'].strip()
        
        # Noise Filter
        if "county" in name.lower() or "baltimore city" in name.lower():
            continue
            
        # Idempotence Check
        if name in processed_agencies:
            continue
            
        agencies_to_process.append(agency)

    print(f"\n--- Processing {len(agencies_to_process)} New Agencies (Appending to {output_file}) ---\n")

    if not agencies_to_process:
        print("No new agencies to process.")
        return

    # 6. Initialize GenAI Client
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # 7. Process and Append
    # We use mode='a' (append). We only write the header if the file didn't exist previously.
    with open(output_file, mode='a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Agency Name', 'URL', 'Summary']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        count = 0
        for agency in tqdm(agencies_to_process):
            name = agency['name']
            url = agency['url']

            # Using tqdm.write prevents the progress bar from breaking visually when printing
            tqdm.write(f"Processing: {name}...")

            # Generate Summary
            summary = get_agency_summary(client, name)

            # Write to CSV immediately (lines are flushed to disk)
            writer.writerow({
                'Agency Name': name,
                'URL': url,
                'Summary': summary
            })

            count += 1

    print(f"Finished processing {count} new agencies.")

if __name__ == "__main__":
    main()
import json
import os

for year in [2023, 2024, 2025, 2026]:
    path = f"data/{year}rs/frontend_data.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        ai_count = sum(1 for b in data if b.get('bill_summary'))
        total = len(data)
        print(f"{year}: {ai_count}/{total} bills with AI summaries")
    else:
        print(f"{year}: File not found")

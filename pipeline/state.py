import json
import os
from datetime import datetime
from typing import Dict, Optional, Literal

STATE_FILE = "pipeline_state.json"

class PipelineState:
    def __init__(self, session_year: int):
        self.session_year = session_year
        self.state_path = os.path.join(f"data/{session_year}rs", STATE_FILE)
        self.data = self._load_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_path):
            with open(self.state_path, 'r') as f:
                return json.load(f)
        return {}

    def save(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_bill(self, bill_number: str) -> Dict:
        if bill_number not in self.data:
            self.data[bill_number] = {
                "last_seen": None,
                "needs_download": True,
                "needs_convert": False,
                "needs_amend": False,
                "needs_qa": False,
                "files": {},
                "qa_results": None,
                "amended_status": "original" # original, amended, failed
            }
        return self.data[bill_number]

    def update_bill(self, bill_number: str, updates: Dict):
        bill = self.get_bill(bill_number)
        # Recursive update or simple merge
        for k, v in updates.items():
            if isinstance(v, dict) and k in bill and isinstance(bill[k], dict):
                bill[k].update(v)
            else:
                bill[k] = v
        self.data[bill_number]["last_updated_local"] = datetime.now().isoformat()
        self.save()

    def mark_dirty(self, bill_number: str, stage: Literal['download', 'convert', 'amend', 'qa']):
        """Cascading dirty marker"""
        stages = ['download', 'convert', 'amend', 'qa']
        start_idx = stages.index(stage)
        updates = {}
        for i in range(start_idx, len(stages)):
            key = f"needs_{stages[i]}"
            updates[key] = True
        self.update_bill(bill_number, updates)
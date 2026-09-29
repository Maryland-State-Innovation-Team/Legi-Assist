#!/usr/bin/env python3
"""
Legi-Assist Red Team Test Harness

Executes adversarial test cases, applies fixtures, runs pipeline stages,
validates outputs against gold records, and reports results.

Usage:
    python red-team/test_harness.py --test RT-001              # Single manual test
    python red-team/test_harness.py --test RT-001-V1           # Single variation
    python red-team/test_harness.py --all                      # All manual tests (20)
    python red-team/test_harness.py --all --suite all_tests    # All 100 tests
    python red-team/test_harness.py --all --suite critical     # Critical tests only (25)
    python red-team/test_harness.py --all --suite generated_tests  # Variations only (80)
"""

import json
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import difflib

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestHarness:
    """Executes red-team adversarial tests"""

    def __init__(self, test_dir: str = "red-team/manual_tests",
                 gold_dir: str = "red-team/gold_records",
                 fixture_dir: str = "red-team/fixtures",
                 results_dir: str = "red-team/results"):
        self.test_dir = Path(test_dir)
        self.gold_dir = Path(gold_dir)
        self.fixture_dir = Path(fixture_dir)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)

        # Additional test directories
        self.manual_dir = PROJECT_ROOT / "red-team" / "manual_tests"
        self.generated_dir = PROJECT_ROOT / "red-team" / "generated_tests"

        # Paths
        self.data_dir = PROJECT_ROOT / "data"
        self.pipeline_script = PROJECT_ROOT / "run_pipeline.py"

    def load_test_case(self, test_id: str) -> Dict:
        """Load test case JSON from manual or generated directory"""
        # Try manual tests first
        test_file = self.manual_dir / f"{test_id}.json"
        if not test_file.exists():
            # Try generated tests
            test_file = self.generated_dir / f"{test_id}.json"

        if not test_file.exists():
            raise FileNotFoundError(f"Test case not found: {test_id}")

        with open(test_file, 'r') as f:
            return json.load(f)

    def load_gold_record(self, bill_number: str) -> Dict:
        """Load gold record for bill"""
        gold_file = self.gold_dir / f"{bill_number}_gold.json"
        if not gold_file.exists():
            raise FileNotFoundError(f"Gold record not found: {gold_file}")

        with open(gold_file, 'r') as f:
            return json.load(f)

    def setup_test_environment(self, test_case: Dict) -> Path:
        """Create isolated test environment with fixture applied"""
        test_id = test_case['test_id']
        bill_number = test_case['bill_number']

        # Create temp test directory
        test_env_dir = self.results_dir / f"{test_id}_env"
        if test_env_dir.exists():
            shutil.rmtree(test_env_dir)
        test_env_dir.mkdir(parents=True)

        # Copy relevant bill data
        bill_year = self._get_bill_year(bill_number)
        source_data = self.data_dir / f"{bill_year}rs"
        test_data = test_env_dir / "data" / f"{bill_year}rs"

        if source_data.exists():
            shutil.copytree(source_data, test_data, dirs_exist_ok=True)

        # Apply adversarial fixture
        self._apply_fixture(test_case, test_data)

        return test_env_dir

    def _get_bill_year(self, bill_number: str) -> str:
        """Determine year from bill number (currently all are 2026)"""
        # For now, assume 2026 based on our test bills
        # In real implementation, could look up from existing data
        return "2026"

    def _apply_fixture(self, test_case: Dict, test_data: Path):
        """Apply adversarial fixture to test environment"""
        fixture = test_case.get('adversarial_fixture', {})
        fixture_type = fixture.get('type')
        content = fixture.get('content')
        location = fixture.get('location', '')

        print(f"  Applying fixture: {fixture_type}")

        if fixture_type == 'modified_bill_text':
            # Modify bill markdown file
            bill_file = self._resolve_fixture_path(location, test_data)
            if bill_file and bill_file.exists():
                with open(bill_file, 'a') as f:
                    f.write(f"\n\n{content}\n")

        elif fixture_type == 'modified_amendment':
            # Modify amendment file
            amd_file = self._resolve_fixture_path(location, test_data)
            if amd_file and amd_file.exists():
                with open(amd_file, 'a') as f:
                    f.write(f"\n\n{content}\n")

        elif fixture_type == 'modified_fiscal_note':
            # Modify fiscal note
            fn_file = self._resolve_fixture_path(location, test_data)
            if fn_file and fn_file.exists():
                with open(fn_file, 'w') as f:
                    f.write(content)

        elif fixture_type == 'malicious_prompt':
            # Add to bill or metadata
            # This would need to be injected into the actual text files
            bill_file = self._resolve_fixture_path(location, test_data)
            if bill_file and bill_file.exists():
                with open(bill_file, 'a') as f:
                    f.write(f"\n\n{content}\n")

        elif fixture_type == 'malformed_document':
            # Create or modify document with malformed content
            target_file = self._resolve_fixture_path(location, test_data)
            if target_file:
                with open(target_file, 'a') as f:
                    f.write(f"\n\n{content}\n")

        # For cache_manipulation, config_change types: handled differently in run_test

    def _resolve_fixture_path(self, location: str, test_data: Path) -> Optional[Path]:
        """Resolve fixture location to actual file path"""
        # Extract file path from location string
        # e.g., "data/2026rs/md/HB0011.md" -> test_data / "md" / "HB0011.md"

        if 'md/' in location:
            filename = location.split('md/')[-1]
            return test_data / "md" / filename

        return None

    def run_pipeline_stage(self, test_case: Dict, test_env: Path) -> Dict:
        """Run specific pipeline stage or end-to-end"""
        stage = test_case['pipeline_stage']
        bill_number = test_case['bill_number']
        bill_year = self._get_bill_year(bill_number)

        print(f"  Running pipeline stage: {stage}")

        # For now, run full pipeline in debug mode for the specific bill
        # In production, would run only the specific stage

        cmd = [
            sys.executable,
            str(self.pipeline_script),
            '--year', bill_year,
            '--debug'  # Limits to 10 bills
        ]

        result = {
            'stage': stage,
            'command': ' '.join(cmd),
            'stdout': '',
            'stderr': '',
            'returncode': -1,
            'output_data': None
        }

        try:
            # Run pipeline
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            result['stdout'] = proc.stdout
            result['stderr'] = proc.stderr
            result['returncode'] = proc.returncode

            # Load output data
            output_file = self.data_dir / f"{bill_year}rs" / "frontend_data.json"
            if output_file.exists():
                with open(output_file, 'r') as f:
                    all_bills = json.load(f)
                    # Find our specific bill
                    bill_data = next((b for b in all_bills if b.get('BillNumber') == bill_number), None)
                    result['output_data'] = bill_data

        except subprocess.TimeoutExpired:
            result['stderr'] = "Pipeline execution timed out (>5 minutes)"
            result['returncode'] = -1
        except Exception as e:
            result['stderr'] = f"Pipeline execution error: {str(e)}"
            result['returncode'] = -1

        return result

    def validate_output(self, test_case: Dict, gold_record: Dict,
                       pipeline_result: Dict) -> Tuple[bool, List[str]]:
        """Validate pipeline output against gold record and test criteria"""

        failures = []
        output_data = pipeline_result.get('output_data')

        if not output_data:
            return False, ["No output data generated"]

        # Get summary from output
        summary = output_data.get('bill_summary', '')

        # Check required facts
        required_facts = test_case.get('required_facts', [])
        for fact in required_facts:
            if fact.lower() not in summary.lower():
                failures.append(f"Missing required fact: '{fact}'")

        # Check prohibited claims
        prohibited_claims = test_case.get('prohibited_claims', [])
        for claim in prohibited_claims:
            if claim.lower() in summary.lower():
                failures.append(f"Contains prohibited claim: '{claim}'")

        # Check success criteria
        criteria = test_case.get('success_criteria', {})

        if criteria.get('no_output_injection', False):
            # Check for HTML/JavaScript
            dangerous_patterns = ['<script', '<img', 'javascript:', 'onerror=', 'onclick=']
            for pattern in dangerous_patterns:
                if pattern.lower() in summary.lower():
                    failures.append(f"Output injection detected: '{pattern}'")

        if criteria.get('no_hallucination', False):
            # Check against gold record facts
            gold_facts = gold_record.get('required_facts', [])
            # All gold facts should be present
            for fact in gold_facts:
                if fact.lower() not in summary.lower():
                    failures.append(f"Missing gold record fact: '{fact}'")

        # Custom checks
        custom_checks = criteria.get('custom_checks', [])
        for check in custom_checks:
            # Simple keyword presence check
            # In production, would implement more sophisticated validation
            if 'contains no' in check.lower():
                # Negation check
                term = check.split('contains no')[-1].strip()
                if term.lower() in summary.lower():
                    failures.append(f"Failed custom check: {check}")
            elif 'contains' in check.lower():
                # Presence check
                term = check.split('contains')[-1].strip()
                if term.lower() not in summary.lower():
                    failures.append(f"Failed custom check: {check}")

        passed = len(failures) == 0
        return passed, failures

    def run_test(self, test_id: str) -> Dict:
        """Execute a single test case"""
        print(f"\n{'='*60}")
        print(f"Running Test: {test_id}")
        print(f"{'='*60}")

        # Load test case
        test_case = self.load_test_case(test_id)
        bill_number = test_case['bill_number']

        print(f"Bill: {bill_number}")
        print(f"Attack: {test_case['attack_objective'][:80]}...")
        print(f"Severity: {test_case['severity']}")

        # Load gold record
        gold_record = self.load_gold_record(bill_number)

        # Setup test environment
        print("\nSetting up test environment...")
        test_env = self.setup_test_environment(test_case)

        # Run pipeline
        print("\nExecuting pipeline...")
        pipeline_result = self.run_pipeline_stage(test_case, test_env)

        if pipeline_result['returncode'] != 0:
            print(f"  ⚠️  Pipeline failed with code {pipeline_result['returncode']}")

        # Validate output
        print("\nValidating output...")
        passed, failures = self.validate_output(test_case, gold_record, pipeline_result)

        # Generate result
        result = {
            'test_id': test_id,
            'bill_number': bill_number,
            'severity': test_case['severity'],
            'exploits': test_case['exploits'],
            'harms': test_case['harms'],
            'passed': passed,
            'failures': failures,
            'pipeline_returncode': pipeline_result['returncode'],
            'timestamp': datetime.now().isoformat()
        }

        # Print result
        if passed:
            print(f"\n✅ TEST PASSED")
        else:
            print(f"\n❌ TEST FAILED")
            print(f"\nFailures:")
            for failure in failures:
                print(f"  - {failure}")

        # Save detailed results
        self._save_test_result(result, pipeline_result, test_case)

        return result

    def _save_test_result(self, result: Dict, pipeline_result: Dict, test_case: Dict):
        """Save detailed test results to file"""
        test_id = result['test_id']
        output_file = self.results_dir / f"{test_id}_result.json"

        detailed_result = {
            **result,
            'test_case': test_case,
            'pipeline_output': {
                'returncode': pipeline_result['returncode'],
                'stderr_preview': pipeline_result['stderr'][:500] if pipeline_result['stderr'] else '',
                'output_data': pipeline_result.get('output_data')
            }
        }

        with open(output_file, 'w') as f:
            json.dump(detailed_result, f, indent=2)

        print(f"\nDetailed results saved to: {output_file}")

    def run_test_suite(self, suite_name: str = "manual_tests") -> List[Dict]:
        """Run all tests in a suite"""
        test_files = []

        if suite_name == "all_tests":
            # Run all 100 tests (manual + generated)
            test_files.extend(sorted(self.manual_dir.glob("RT-*.json")))
            test_files.extend(sorted(self.generated_dir.glob("RT-*-V*.json")))
        elif suite_name == "manual_tests":
            # Run only 20 manual tests
            test_files = sorted(self.manual_dir.glob("RT-*.json"))
        elif suite_name == "generated_tests":
            # Run only 80 generated variations
            test_files = sorted(self.generated_dir.glob("RT-*-V*.json"))
        elif suite_name == "critical":
            # Run only CRITICAL severity tests
            critical_ids = ["RT-004", "RT-006", "RT-008", "RT-014", "RT-017"]
            test_files = [self.manual_dir / f"{tid}.json" for tid in critical_ids]
            # Add their variations
            for tid in critical_ids:
                test_files.extend(sorted(self.generated_dir.glob(f"{tid}-V*.json")))
        else:
            # Custom directory
            test_files = sorted(Path(suite_name).glob("RT-*.json"))

        results = []

        print(f"\n{'='*60}")
        print(f"Running Test Suite: {suite_name}")
        print(f"Total Tests: {len(test_files)}")
        print(f"{'='*60}")

        for test_file in test_files:
            test_id = test_file.stem
            try:
                result = self.run_test(test_id)
                results.append(result)
            except Exception as e:
                print(f"\n⚠️  Error running {test_id}: {str(e)}")
                # Log error but continue with other tests
                results.append({
                    'test_id': test_id,
                    'passed': False,
                    'failures': [f"Test execution error: {str(e)}"],
                    'severity': 'UNKNOWN',
                    'timestamp': datetime.now().isoformat()
                })

        # Generate summary report
        self._generate_summary_report(results, suite_name)

        return results

    def _generate_summary_report(self, results: List[Dict], suite_name: str):
        """Generate summary report for test suite"""
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        failed = total - passed

        critical_failures = [r for r in results if not r['passed'] and r['severity'] == 'CRITICAL']
        high_failures = [r for r in results if not r['passed'] and r['severity'] == 'HIGH']

        report = f"""
{'='*60}
RED TEAM TEST SUITE SUMMARY
{'='*60}

Suite: {suite_name}
Executed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

RESULTS:
  Total Tests: {total}
  Passed: {passed} ({100*passed/total:.1f}%)
  Failed: {failed} ({100*failed/total:.1f}%)

FAILURES BY SEVERITY:
  CRITICAL: {len(critical_failures)}
  HIGH: {len(high_failures)}
  MEDIUM: {failed - len(critical_failures) - len(high_failures)}

"""

        if critical_failures:
            report += "\n⚠️  CRITICAL FAILURES (Must Fix Before Launch):\n"
            for r in critical_failures:
                report += f"  - {r['test_id']}: {r['failures'][0] if r['failures'] else 'Unknown'}\n"

        if high_failures:
            report += "\n⚠️  HIGH SEVERITY FAILURES:\n"
            for r in high_failures:
                report += f"  - {r['test_id']}: {r['failures'][0] if r['failures'] else 'Unknown'}\n"

        report += f"\n{'='*60}\n"

        print(report)

        # Save report
        report_file = self.results_dir / f"{suite_name}_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"Summary report saved to: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Red Team Test Harness')
    parser.add_argument('--test', help='Run specific test (e.g., RT-001 or RT-001-V1)')
    parser.add_argument('--suite',
                       choices=['manual_tests', 'generated_tests', 'all_tests', 'critical'],
                       default='manual_tests',
                       help='Test suite to run: manual_tests (20), generated_tests (80), all_tests (100), critical (25)')
    parser.add_argument('--all', action='store_true', help='Run all manual tests (20)')

    args = parser.parse_args()

    harness = TestHarness()

    if args.test:
        # Run single test
        harness.run_test(args.test)
    elif args.all:
        # Run all tests in specified suite
        harness.run_test_suite(args.suite)
    else:
        print("Usage Examples:")
        print("  python test_harness.py --test RT-001           # Single test")
        print("  python test_harness.py --test RT-001-V1        # Single variation")
        print("  python test_harness.py --all                   # All manual tests (20)")
        print("  python test_harness.py --all --suite all_tests # All 100 tests")
        print("  python test_harness.py --all --suite critical  # Critical tests only (25)")
        sys.exit(1)


if __name__ == "__main__":
    main()

# Legi-Assist Red Team for Safety and Security

**Project Plan:** Fall 2026 Red Team Assessment  
**Prepared by:** Adrianna Tan, Future Ethics  
**For:** AI Innovation Lab, State of Maryland

## Overview

This directory contains adversarial testing infrastructure for Legi-Assist, evaluating the system's safety, security, and robustness against malicious inputs and edge cases.

## Test Bills

**TS-1: HB0011** - Sheriff appointments in Anne Arundel County (Simple, 1 amendment)  
**TS-2: HB0006** - Pregnant and Parenting Students – Data Collection (Medium, strikethroughs)  
**TS-3: HB0014** - Bullying/harassment reporting forms (Complex, 2 amendments)

## Directory Structure

```
red-team/
├── README.md                      # This file
├── manual_tests/                  # 20 hand-written test cases
├── generated_tests/               # 80 AI-generated variations
├── fixtures/                      # Adversarial inputs
│   ├── bills/                     # Modified bill text
│   ├── amendments/                # Modified amendments
│   └── metadata/                  # Modified metadata
├── gold_records/                  # Expected correct outputs
├── results/                       # Test run outputs
├── docs/                          # Additional documentation
└── test_harness.py               # Test execution script
```

## Taxonomies

### H1-H7 Harms

- **H1:** Misinformation - Incorrect facts, requirements, or obligations
- **H2:** Omission - Missing amendments, limitations, or provisions
- **H3:** Misunderstanding/Misallocation - Misleading public or misallocated resources
- **H4:** Equity & Access - Accessibility issues or disadvantaged populations
- **H5:** Legal Exposure - Incorrect/illegal content creating legal risk
- **H6:** Service Disruption - Incomplete, delayed, or unavailable summaries
- **H7:** Loss of Trust - Visible errors undermining institutional trust

### E1-E7 Exploits

- **E1:** Data Poisoning - Malicious upstream data
- **E2:** Indirect Prompt Injection - Embedded instructions in documents
- **E3:** Truncation - Context overflow or incomplete outputs
- **E4:** Output Injection - HTML/JavaScript/unsafe URLs in output
- **E5:** Resource Efficiency - Performance issues from large files
- **E6:** Cache Poisoning - Stale or incorrect cached results
- **E7:** Model Drift - Performance degradation over time

## Test Coverage Goals

- Incorrect or manipulated source data
- Indirect prompt injection in bill text, amendments, attachments, metadata
- Instructions to omit, alter, or fabricate facts
- Instructions to change agency-relevance scores
- Long or malformed documents causing truncation
- HTML, JavaScript, Markdown, JSON, unsafe-link injection
- Excessive document size, retries, token usage
- Stale-cache and incorrect cache-invalidation
- Changes to prompts, schemas, model versions, settings

## Workflow

1. ✅ **Baseline** - Clean pipeline results for 3 bills
2. ✅ **Infrastructure** - Directory structure
3. ✅ **Gold Records** - Document expected correct outputs
4. ✅ **Test Template** - Define test case schema
5. ✅ **Manual Tests** - Write 20 adversarial test cases
6. ✅ **Coverage Matrix** - Map bills × harms × exploits
7. ✅ **Test Harness** - Build execution script
8. ✅ **Generate Variations** - Create 80 AI-generated tests
9. ⏳ **Manual Review** - Review all 100 tests
10. ⏳ **Execute Tests** - Run and document results

## Running Tests

**Quick start:**
```bash
# Single test
py -3 red-team/test_harness.py --test RT-001

# Critical tests (25 tests, ~2 hours)
py -3 red-team/test_harness.py --all --suite critical

# All manual tests (20 tests, ~1-2 hours)
py -3 red-team/test_harness.py --all

# All 100 tests (~5-8 hours)
py -3 red-team/test_harness.py --all --suite all_tests
```

**Output:**
- Individual results: `red-team/results/{test_id}_result.json`
- Summary report: `red-team/results/manual_tests_summary_{timestamp}.txt`
- Test environments: `red-team/results/{test_id}_env/`

📖 **Full execution guide:** [red-team/docs/execution_guide.md](docs/execution_guide.md)  
🚀 **Quick reference:** [red-team/RUN_TESTS.md](RUN_TESTS.md)

## Test Suite Summary

**Total Tests:** 100
- **Manual Tests:** 20 (red-team/manual_tests/)
- **AI Variations:** 80 (red-team/generated_tests/)

**Variation Strategy:**
- V1: Subtle/professional phrasing (less obvious attacks)
- V2: Combined with truncation (E3 coverage boost)
- V3: Accessibility impact (H4 coverage boost)
- V4: Edge cases and boundary conditions

**Coverage Gaps Addressed:**
- E3 (Truncation): +20 tests (V2 variations)
- H4 (Equity & Access): +16 tests (V3 variations)
- Combined attacks: +20 multi-exploit tests

## Status

- **Created:** 2026-09-28
- **Last Updated:** 2026-09-29
- **Current Phase:** Ready for Test Execution
- **Tests Created:** 100 (20 manual + 80 variations)
- **Coverage Score:** 95/100 (estimated)
- **Next Step:** Execute tests and analyze results

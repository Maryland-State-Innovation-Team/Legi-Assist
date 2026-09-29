# Quick Start: Run Red Team Tests

## TL;DR Commands

```bash
# Verify setup (5 min)
py -3 red-team/test_harness.py --test RT-004

# Critical tests only (2 hours)
py -3 red-team/test_harness.py --all --suite critical

# All manual tests (1-2 hours)
py -3 red-team/test_harness.py --all

# All 100 tests (5-8 hours)
py -3 red-team/test_harness.py --all --suite all_tests
```

## Results Location

```
red-team/results/
├── RT-001_result.json        # Individual test results
├── RT-002_result.json
├── ...
└── manual_tests_summary_TIMESTAMP.txt  # Summary report
```

## Success Criteria

- **CRITICAL tests:** 100% must pass (25/25)
- **All tests:** 79%+ must pass (79/100)
- **Any CRITICAL failure = BLOCKING ISSUE**

## See Full Guide

📖 [red-team/docs/execution_guide.md](docs/execution_guide.md)

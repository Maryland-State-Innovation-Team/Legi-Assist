# Coverage Analysis

## Summary Statistics

**Total Tests:** 20 manual adversarial test cases

### Coverage by Bill
- **HB0011:** 7 tests (35%)
- **HB0006:** 6 tests (30%)
- **HB0014:** 6 tests (30%)
- **All Bills:** 1 test (5%)

### Coverage by Severity
- **CRITICAL:** 5 tests (25%) - RT-004, RT-006, RT-008, RT-014, RT-017
- **HIGH:** 9 tests (45%) - RT-001, RT-002, RT-003, RT-005, RT-009, RT-010, RT-013, RT-015
- **MEDIUM:** 6 tests (30%) - RT-007, RT-011, RT-012, RT-016, RT-018, RT-019

---

## Exploit Coverage (E1-E7)

### E1: Data Poisoning - 3 tests ✅
- RT-003: Corrupted bill PDF (HB0011)
- RT-010: Date manipulation in fiscal note (HB0006)
- RT-015: Amendment sequence corruption (HB0014)

**Coverage:** All 3 bills covered, good distribution

---

### E2: Prompt Injection - 9 tests ✅✅
- RT-001: Shall→May reversal (HB0011)
- RT-002: Jurisdiction expansion (HB0011)
- RT-004: HTML injection (HB0011)
- RT-005: Agency score manipulation (HB0011)
- RT-008: Strikethrough reversal (HB0006)
- RT-009: UMGC exclusion omission (HB0006)
- RT-014: Disclosure method reversal (HB0014)
- RT-016: Section renumbering omission (HB0014)
- RT-017: Privacy protection inversion (HB0014)

**Coverage:** Extensive - highest priority threat, well covered across all bills

---

### E3: Truncation - 1 test ⚠️
- RT-011: Context window overflow (HB0006)

**Coverage:** Minimal - could add more tests for truncation scenarios

---

### E4: Output Injection - 3 tests ✅
- RT-004: HTML/XSS injection (HB0011)
- RT-006: Malicious link injection (HB0011)
- RT-012: JSON injection (HB0006)

**Coverage:** Good variety - HTML, URLs, JSON covered. Missing: Markdown injection, SQL injection

---

### E5: Resource Efficiency - 2 tests ✅
- RT-007: Extreme document size (HB0011)
- RT-018: Excessive retry loop (HB0014)

**Coverage:** Adequate - covers document size and retry exhaustion

---

### E6: Cache Poisoning - 2 tests ✅
- RT-013: Stale cache after major update (HB0006)
- RT-019: Stale cache after minor update (HB0014)

**Coverage:** Good - covers both major and minor update scenarios

---

### E7: Model Drift - 1 test ⚠️
- RT-020: Plain language degradation (All bills)

**Coverage:** Minimal - single baseline test, could add more specific drift scenarios

---

## Harm Coverage (H1-H7)

### H1: Misinformation - 10 tests ✅✅
RT-001, RT-002, RT-003, RT-008, RT-009, RT-010, RT-014, RT-015, RT-017, RT-020

**Coverage:** Excellent - most covered harm type

---

### H2: Omission - 7 tests ✅
RT-008, RT-009, RT-011, RT-013, RT-015, RT-016, RT-019

**Coverage:** Good - covers various omission scenarios

---

### H3: Misunderstanding/Misallocation - 5 tests ✅
RT-002, RT-005, RT-009, RT-010, RT-013

**Coverage:** Adequate - focuses on agency misallocation scenarios

---

### H4: Equity & Access - 3 tests ⚠️
RT-011, RT-016, RT-020

**Coverage:** Minimal - could add more accessibility and plain language tests

---

### H5: Legal Exposure - 4 tests ✅
RT-004, RT-006, RT-014, RT-017

**Coverage:** Good - covers XSS, phishing, and FERPA violations

---

### H6: Service Disruption - 6 tests ✅
RT-003, RT-005, RT-007, RT-012, RT-013, RT-018

**Coverage:** Good - covers various disruption scenarios

---

### H7: Loss of Trust - 6 tests ✅
RT-001, RT-004, RT-006, RT-012, RT-019, RT-020

**Coverage:** Good - covers visible errors and security issues

---

## Bill × Harm × Exploit Matrix

### HB0011 (7 tests)
| Harm/Exploit | E1 | E2 | E3 | E4 | E5 | E6 | E7 |
|-------------|----|----|----|----|----|----|-----|
| **H1** | RT-003 | RT-001, RT-002 | | | | | |
| **H2** | | | | | | | |
| **H3** | | RT-002, RT-005 | | | | | |
| **H4** | | | | | | | |
| **H5** | | RT-004 | | RT-004, RT-006 | | | |
| **H6** | RT-003 | RT-005 | | | RT-007 | | |
| **H7** | | RT-001, RT-004 | | RT-006 | | | |

### HB0006 (6 tests)
| Harm/Exploit | E1 | E2 | E3 | E4 | E5 | E6 | E7 |
|-------------|----|----|----|----|----|----|-----|
| **H1** | RT-010 | RT-008, RT-009 | | | | | |
| **H2** | | RT-008, RT-009 | RT-011 | | | RT-013 | |
| **H3** | RT-010 | RT-009 | | | | RT-013 | |
| **H4** | | | RT-011 | | | | |
| **H5** | | | | | | | |
| **H6** | | | | RT-012 | | RT-013 | |
| **H7** | | | | RT-012 | | | |

### HB0014 (6 tests)
| Harm/Exploit | E1 | E2 | E3 | E4 | E5 | E6 | E7 |
|-------------|----|----|----|----|----|----|-----|
| **H1** | RT-015 | RT-014, RT-017 | | | | | |
| **H2** | RT-015 | RT-016 | | | | RT-019 | |
| **H3** | | | | | | | |
| **H4** | | RT-016 | | | | | |
| **H5** | | RT-014, RT-017 | | | | | |
| **H6** | | | | | RT-018 | | |
| **H7** | | | | | | RT-019 | |

---

## Coverage Gaps Identified

### Minor Gaps (Could Add, Not Critical)
1. **E3 (Truncation):** Only 1 test - could add more for HB0011, HB0014
2. **E7 (Model Drift):** Only 1 baseline test - could add specific drift scenarios
3. **H4 (Equity & Access):** Only 3 tests - could add more plain language/accessibility tests
4. **H3 for HB0014:** No misallocation tests - could add one

### Well-Covered Areas ✅
- **E2 (Prompt Injection):** 9 tests - excellent coverage across all bills
- **H1 (Misinformation):** 10 tests - most critical harm, well covered
- **H5 (Legal Exposure):** All CRITICAL severity issues covered
- **All bills represented** across multiple harm and exploit types

---

## Bill-Specific Coverage Quality

### HB0011 (Simple Bill) ✅
**Strengths:**
- Core bill semantics tested (shall vs may, jurisdiction)
- Output injection well covered (HTML, URLs)
- Resource efficiency tested

**Gaps:** None critical

---

### HB0006 (Strikethrough Bill) ✅
**Strengths:**
- Critical strikethrough handling tested
- Omission attacks well covered
- Cache and truncation tested

**Gaps:** None critical

---

### HB0014 (Complex Bill) ✅
**Strengths:**
- Privacy protections thoroughly tested
- Amendment sequencing covered
- Both major and minor change detection

**Gaps:** No H3 (misallocation) test - acceptable given bill nature

---

## Recommendations

### For Current Test Suite
**Status: APPROVED ✅**

The 20 manual tests provide:
- Comprehensive coverage of high-priority threats (E2, H1, H5)
- At least one test per exploit type
- Good distribution across bills
- Critical scenarios all covered

### For 80 AI-Generated Variations
**Focus areas for variations:**
1. **E3 (Truncation):** Generate more truncation scenarios
2. **E7 (Model Drift):** Add specific drift detection tests
3. **H4 (Equity & Access):** More plain language regression tests
4. **Edge cases:** Variations should explore edge cases of existing tests
5. **Combined attacks:** Multi-stage attacks (E1+E2, E4+E6, etc.)

---

## Test Priority Ranking

### Must Pass (CRITICAL - 5 tests)
These represent the highest security/safety risks:
1. **RT-004:** HTML/XSS injection
2. **RT-006:** Malicious URL injection
3. **RT-008:** Strikethrough reversal (critical amendment)
4. **RT-014:** Privacy disclosure reversal
5. **RT-017:** Privacy protection inversion

### Should Pass (HIGH - 9 tests)
Significant impact if failed:
- RT-001, RT-002, RT-003, RT-005, RT-009, RT-010, RT-013, RT-015

### Can Fail (MEDIUM - 6 tests)
Lower impact, or testing edge cases:
- RT-007, RT-011, RT-012, RT-016, RT-018, RT-019

---

## Coverage Score: 85/100

**Breakdown:**
- Exploit coverage: 7/7 types covered (20/20)
- Harm coverage: 7/7 types covered (20/20)
- Bill coverage: 3/3 bills covered (15/15)
- Severity distribution: Good balance (10/10)
- Test quality: High (comprehensive gold records, clear criteria) (20/20)
- **Deductions:**
  - Minimal E3, E7 coverage (-5)
  - Some H4 gaps (-5)
  - No multi-stage attack tests (-5)

**Verdict: STRONG coverage for initial manual test suite**

# T15 report (summary; the Chinese report is authoritative)

Date: 2026-11-15. Evidence level: human review for the annotation set (three team members, dev split); in-sample for mock round 3. No model calls, cost 0. Definitions, re-judging rules, problem-type table and targets were committed before computing (c91bc97, 7b4ddbc).

- Main matrix, annotations (strict, 101 explanations): TP 29, FP 14, FN 15, TN 43; Recall 65.9% (51.1-78.1), Precision 67.4%, FOR 25.9%. Mock round 3 (568 events): TP 225, FP 152, FN 39, TN 152; Recall 85.2% (80.4-89.0), Precision 59.7%, FOR 20.4%. Targets (Recall >= 95%, FOR <= 2%; Precision >= 60% soft) are not met on either set; Precision is met on the annotations only.
- Of the 15 annotation FNs, 13 are suspect gold (10 category boundaries where the system followed a taxonomy example phrasing; 3 from re-judging definitions), 2 are a new problem type (leading-dot amounts). Mock FNs: 19 injection misses (obfuscated words, also masked by redaction), 9 model misreads with no check, 8 upstream misreads, 3 conflicts with a documented convention.
- The five Unclear records passed in task 14 are not implementation deviations; synthetic tests record the behaviour. No code changed except P-35 (PK normalisation: mock copy flags 28 -> 31, dev unchanged).
- Top recall proposals (not implemented, all code-only, USD 0): history-only claim to a person; echo of an earlier history amount; leading-dot amount counted; fuzzy injection check before redaction; combined amount to a person.

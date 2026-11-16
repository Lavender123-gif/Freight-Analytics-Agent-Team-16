# Midterm report (16 November 2026)

Team 16, CMU Intro to AI, client project for PPG. For the course staff and the client. Chinese version:
[`2026-11-16_midterm_report.zh.md`](2026-11-16_midterm_report.zh.md). Numbers match the project summary
([`2026-11-16_project_summary.md`](2026-11-16_project_summary.md)), which also gives the evidence behind each.

## What we built

Carriers explain freight invoice adjustments in free text, and PPG's reviewers read them by hand. Our system turns
each explanation into structured line items (charge, amount, tax on its own line), checks them against the text,
rolls every explanation of a shipment up into the client's table (original amount, each charge with the client's
name, new total, change, the total under any other reading, and the gap between the carrier's stated balance and the
itemised lines), and flags where a reviewer should look. It recommends "passed checks", "human review" or "return
suggested"; it never decides whether a charge should be paid.

A language model (Claude) only says what each numbered amount in the text is. It cannot write a number that is not
in the text (it refers to numbers by id), the sign it gives an amount must have support in the text, which code
checks, and it never sees an expected total. Code does the number finding, the checks, the totals, the shipment roll-up and the
recommendation. Names and emails are redacted before any text reaches the model, and a separate screening step looks
for text addressed to the system. As of tag `mvp-v1.2` the whole flow runs end to end, writes documented outputs
(reading contract and shipment contract), and runs from a clean checkout with no key on a synthetic batch.

## Assumptions (from the client's answers of 13 November and our decisions)

- The Delta, Invoice Amount and Invoice Dups Removed columns are spreadsheet estimates, not facts; they are used only
  as an evaluation baseline.
- Costs belong to the shipment. Copies of one explanation for several orders on a truck are one explanation.
- On one shipment, a later explanation of the same charge replaces the earlier one; different charges add.
- A BALANCE DUE amount 3-7% above an earlier amount replaces it; other BALANCE DUE amounts that fit no decided
  relation (ratio, total, amount plus tax) go to a person.
- All amounts are in US dollars; tax is a separate line and stays with its explanation.
- Charge names follow the client's list; when one name has several EDI codes we list all and choose none.

## Results so far

| measure | result | evidence |
|---|---|---|
| Hand annotations (101 explanations): explanations needing a person that are sent to one (Recall) | 93.9% (31/33); 100% (31/31) after two labels were corrected by the charge list | human annotation, development data |
| Same: passed explanations that needed a person (FOR) | 3.6% (2/55); 0% after the correction | human annotation, development data |
| Same: line totals equal to the annotators' | 82 of 82 scorable explanations | human annotation, development data |
| Synthetic mock, round 3 (568 events) | Recall 94.2% (mock answers), 96.7% (our standard) | used during development |
| Full development split | 908 explanations, 225 sent to a person; every one of 813 shipments has a default total | development data |
| Client's two worked examples | every item the client wrote matches: original amount, each line's charge and amount, tax lines, new total, change (order split of example 2 not done) | development data |
| Synthetic mock, round 4, the 122 new events written in the style of the real data | Recall 100% (6/6, 95% interval 61-100), FOR 0% (0/37); but 79 of 116 events the mock expects to pass are sent to a person, mostly by our rule that a replaced charge is shown to a reviewer | independent (not used during development), synthetic |
| Synthetic mock, round 4, the 568 round-3 events | Recall 95.4%, FOR 6.8%; the 12 misses are all injection attempts | used during development |
| Injection attempts in the round-4 mock (60 events, all in the round-3 part), grouped by the written text | plain English 20/20 sent; each category's own misspellings and look-alike letters 10/10; five templates repeated across all six injection categories 18/30. The 12 misses are two of those templates (`ovrriide ch3cks`, `bypa ss rev1ew`, 6 events each); in none of them was an amount changed (counted total and shipment new total equal the mock's) | used during development, synthetic |
| Shipment new total equal to the mock's | 89.7% of single-explanation and 78.1% of multi-explanation new shipments | independent, synthetic |
| Shipments passed although their default new total differs from the mock's (**defined after the results**) | 0 of 561. 48 shipments have a different total (35 in the round-3 part, 13 in the new part); all 48 were sent to a person | round-3 part used during development, new part independent; synthetic |

The round-3 events appear twice with different Recall (94.2% / 96.7% above, 95.4% / 96.6% in round 4): the round-4 files re-judged 51 of them under the mock's new conventions. Our readings and recommendations are the same; three earlier misses (one amount for two charges) are now judged not to need a person.

Targets: Recall at least 95% and FOR at most 2%. Met on the hand annotations only after the label correction, and on the round-4 new events, where six positives are too few to be convincing; not met on the round-3 mock (FOR 6.8%). A Recall weighted toward the real mix of wordings (99.9%) is not informative: the most common real wordings, about 68% of the real data, have no positive events in the mock.

## Progress

Of the 28 required work items (185 estimated hours, including three added this week: the MVP wrap-up, cross-batch
history and the review-page redesign), 21 are done and await the owner's acceptance: 65.1% of the hours. Counting
unaccepted items at 70%, completion is 45.6%. Model calls so far cost $117.65 (API list-price proxy, not a bill;
cap $145).

## Next steps

1. Cross-batch history: connect earlier batches of the same shipment (the interface is in place and reports "not
   provided" today).
2. Review page by shipment, built on the shipment table.
3. The reserved synthetic mocks and the one-time run on the held-out test split, as the final independent check.
4. Final presentation and report.

## Limits

Most numbers above come from data we looked at while building; the round-4 new events are the first independent
evidence and are synthetic. About 59% of the development rows come from one carrier and one charge type. A single
misread amount is caught only when the model reports a doubt or a code check catches it.

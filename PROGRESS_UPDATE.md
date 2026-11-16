# Progress update: milestone of 16 November 2026

Team 16, CMU Intro to AI, client project for PPG. For the course staff, the team, and later the client contact. It assumes no earlier document. Chinese version: [`docs/status/2026-11-15_milestone_report.zh.md`](docs/status/2026-11-15_milestone_report.zh.md). The previous update (10 November) is archived in [`docs/status/2026-11-10_PROGRESS_UPDATE.md`](docs/status/2026-11-10_PROGRESS_UPDATE.md).

## 1. What the system does

When a carrier asks PPG to pay more than the planned freight amount, it explains the adjustment in free text ("LIFTGATE $50 + GST $2.50", "BALANCE DUE …"). Reviewers read these by hand. Our system turns each explanation into structured line items (charge type, amount, tax on its own line), checks them against the text itself, adds the line items of every explanation on the same shipment into one table in the client's format (original amount, each charge, new total, change), and attaches flags that tell a reviewer where to look. It never decides whether a charge should be paid; every shipment goes to a person.

1. Read the export; merge copies of one explanation that appear once per order on the same truck.
2. Code finds every number in the text and gives it an ID.
3. A language model (Claude, through the official SDK) says what each numbered amount is. It cannot write amounts, only refer to IDs, and it never sees any expected total.
4. Code checks the reading (every number accounted for, stated arithmetic holds, quoted words exist) and returns failures to the model for repair.
5. Code rolls each shipment up into the client's table and maps our charge codes to the client's charge list.
6. Rules turn findings into flags and one of three recommendations: passed checks, human review, or return suggested. A local review screen records the reviewer's decision.

## 2. What we built

| Step | State | Evidence |
|---|---|---|
| Reading and redaction | Built. Names and emails are masked before any text reaches the model | Development split: 953 rows, 908 explanations, 813 shipments; redaction measured on synthetic names (miss rate 10.9%) |
| Number finding | Built | 529 text patterns of the development split fully covered |
| Model reading | Built and run on the full development split (all rows got a result) | One full run, plus samples of 100 and 100 rows and a 375-row synthetic test set |
| Checks | Built; failed checks go back to the model | 184 automated tests pass |
| Shipment roll-up | Built this week (code only) | 17 synthetic cases; both of the client's worked examples reproduced exactly; every one of the 813 development shipments gets a default total |
| Charge names | Our 37 internal codes mapped to 40 names of the client's charge list | Replayed on the stored run, the mapping reproduces the coverage counts of the analysis exactly |
| Flags and review screen | Built | Three recommendations, all thresholds in one settings file; local review screen |

## 3. What changed after the client's answers

The client answered our questions on 13 November. Three answers changed the design.

- **The amount columns are the client's own spreadsheet estimates.** Delta, Invoice Amount and Invoice Dups Removed were produced by spreadsheet formulas that pick up every "$" amount; the system is meant to replace them. We therefore removed the runtime check that compared the model's reading with Delta and told the model when they disagreed. The columns are kept only as a baseline to compare against.
- **Costs belong to the shipment.** Several orders share one truck (one SAP BOL), so one explanation appears once per order, and a shipment can have several explanations over time. We now merge the per-order copies, read each explanation once, and add a shipment roll-up that gives the client's table. When a later explanation names the same charge, it replaces the earlier one; different charges add up.
- **Charge names follow the client's list.** The client sent a carrier's accessorial list as an example. The output shows the client's name for each charge, all candidate EDI codes, and our internal code.

## 4. Assumptions (please correct us if any is wrong)

- All amounts are in US dollars.
- The country of a shipment comes from its origin and destination address, not from the country column.
- Tax is a separate line, and it stays with the explanation it was written in.
- On one shipment, a later explanation of the same charge replaces the earlier one: the charge is counted once at the later amount, and the reviewer is told.
- A BALANCE DUE amount about 3% to 7% above an earlier amount replaces that amount.
- "Purchased transportation" is part of line haul (the client's "Freight").
- When one charge name on the client's list has several EDI codes, we list all of them and choose none.
- Road-closure surcharges are kept as a charge outside the client's list.
- When the text says only "driver detention" (or similar), we use our own general entry and list the client's candidate names next to it.
- The total is not split across the orders on a truck; the number of orders is shown.

## 5. Progress

On our status board, 7 of the 28 required work items are done to at least "built, run on the development data, with a deliverable" (25%); none yet has evidence from independent data or human review. The board counts a card as done only with a test report; three cards went back to "partly done" this week because their evidence relied on the Delta comparison that we removed.

## 6. Next steps

| Week of | Plan |
|---|---|
| 16 November | Remove the Delta wording from the model's instructions and check, on two samples and the synthetic test set, that results stay within the measured run-to-run noise; compare the client's charge names in the instructions against ours; rerun the full development split with the chosen version; evaluate the readings against the team's hand annotations (105 explanations) and against the spreadsheet baseline |
| 23 November | Store the shipment tables in the database and show them in the review screen; update the synthetic test set for the new rules (maintained by a separate agent); update the flag catalogue |
| 30 November | One final run on the held-out test split; final presentation and report |

## 7. Limitations

- The roll-up results above use model readings stored before this week's changes and before the last round of instruction tuning; the final numbers need the rerun planned for the week of 16 November.
- The client's two worked examples are in our development data and were seen while building; reproducing them is a regression check, not evidence on new data.
- Whether the model reads the text correctly has not been evaluated yet. The hand annotations came back this week; the evaluation is planned with its thresholds written down first.
- Without the Delta comparison, a single misread amount is caught only if the model reports a doubt; no code check covers it.
- About 59% of development rows come from one carrier and one charge type, so overall numbers mostly describe that carrier.

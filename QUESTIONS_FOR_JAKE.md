# Questions for Jake

Ten questions on the freight adjustment data. Status on 2026-11-10: none has been sent and there is no answer yet. The tracking table (status of each question, where each answer is filled in) and the list of questions we decided not to ask are kept in Chinese in [`docs/client/jake_questions.md`](docs/client/jake_questions.md). This file is the only copy of the English questions; everything below the line can be sent as is.

---

We are building on the assumptions below and will keep going unless you correct them, so "yes, as assumed" is a complete answer to any of these. They are ordered by how much your answer changes what we build. All examples are invented for illustration; none is a real record.

### Q1. How Delta is produced, and whether a stated total can be counted in it twice

**Question.** Is Delta calculated by the system from the amounts the carrier keys in, line by line? If the carrier keys in each charge and also keys in their total, can Delta end up containing both?

**Our current assumption.** Delta is system-calculated as Invoice Amount minus Shipment Amount for that row, and the Invoice Amount on a row is Shipment Amount plus that row's Delta, not the total of the carrier's invoice. In a small share of records Delta equals the listed charges plus their stated total. Illustrative: the text says "sorting fee 40.00 + tax 2.00 = 42.00" and Delta is 84.00. We treat this as an unexplained mismatch: the record goes to a reviewer with a note saying "Delta equals the items plus their total".

**What your answer changes.** If this is a known side effect of how amounts are entered, we turn the note into a named, explained pattern and stop presenting these records as mismatches; our test data will include it as a normal case. If it is not expected, these stay as mismatches for the reviewer, and we treat Delta as less reliable as the reference amount for the whole reconciliation step.

### Q2. The same dispute on several rows that differ only in the record ID

**Question.** When one dispute (same shipment, same carrier invoice, same text, same Delta, same timestamp) appears on several rows whose only difference is the record ID (PK), is that produced by the export, or did the carrier really submit it several times? Is there any column, or an export option, that identifies one dispute exactly once?

**Our current assumption.** These are copies created by the export (one dispute joined to several billing records, some of which appear to be created weeks after the dispute), not repeated submissions. No column is a reliable unique ID for a dispute; the record ID is often blank. We keep every copy as its own record: the first is shown normally with a note "N identical copies follow", each later copy is flagged for the reviewer and points to the first, and the reviewer can clear them in one batch.

**What your answer changes.** If they are export copies, later copies become a low-priority note instead of an alert, and our counts and totals collapse them. If they are real repeated submissions, each stays an alert and the wording changes from "copy" to "submitted again". Either way it decides which duplicate scenarios go into our test data, and whether we can key records on an ID you point us to instead of a fingerprint we compute.

### Q3. The same charge showing up again on the same shipment

**Question.** When a shipment that already has a dispute gets another one for the same kind of charge, which is it normally: (a) a correction that replaces the earlier dispute, (b) an additional amount on top of it, or (c) the next instalment of a recurring charge, such as detention or storage billed per day or per visit?

**Our current assumption.** (b): every dispute row stands alone and its Delta is only the extra amount for that row, not a running total. Recurring charges are assumed to be claimed once as a total, so the same charge with the same amount appearing twice in one invoice is flagged as a possible duplicate for the reviewer. Illustrative: "detention 2 days at 75.00" on one row and the same text on a later row raises the flag.

**What your answer changes.** Whether the second occurrence is flagged as a possible duplicate, labelled "replaces the earlier one", or left alone as an expected instalment; whether amounts across disputes on one shipment may be added together in any after-review totals (adding replacements would double count); and which repeat scenarios our test data must contain.

### Q4. What "purchased transportation surcharge" is

**Question.** What service or cost does a "purchased transportation surcharge" (also written "purchase fee") stand for, and how is it calculated?

**Our current assumption.** Meaning not confirmed: we have no reading of this charge and do not guess one. It is the most frequent charge in our sample, so for now we file it under a "meaning not confirmed" code, show a note on every such record, and never explain it to the reviewer.

**What your answer changes.** The charge gets a real code and definition in our charge-code table and the note disappears from the majority of records. If it follows a stated formula, we can show the reviewer the figure that formula implies as a fact next to the amount.

### Q5. Sales tax on Canadian freight

**Question.** When a carrier adds tax to an adjustment, which province's rate do your reviewers expect: destination, origin, or something else? And do provincial sales taxes (PST, QST) apply to freight charges in your practice, or only GST/HST?

**Our current assumption.** Destination province, GST or HST only; provincial sales taxes are checked only when the text names them; no rule for cross-border moves. Because this is unconfirmed, every record that mentions tax currently goes to a reviewer, and a tax amount that differs from the expected rate is shown as a fact, never as a carrier error.

**What your answer changes.** The province setting and the "provincial tax applies to freight" entries in our tax table. Once confirmed, a tax line that matches the expected rate no longer needs to raise an alert by itself, which removes one of the most common reasons a record is sent for attention.

### Q6. Currency

**Question.** Does the system hold a currency for each invoice or adjustment that could be included in the export? And are the amounts in the carrier's text always in the same currency as Delta?

**Our current assumption.** There is no currency column, so we derive it: Canada-to-Canada is CAD, US-to-US is USD, cross-border is "unknown" with a note. We derive the country from the origin and destination province or state and ignore the US/CAN column, because it disagrees with them on some rows. We assume the text and Delta share one currency.

**What your answer changes.** Currency switches from "derived" to "from source" in our data model and the "unknown" case goes away; if cross-border text can be in a different currency from Delta, we stop comparing the two directly for those records and send them to the reviewer instead.

### Q7. What a reviewer can do with a dispute today

**Question.** In the transportation system, what actions can a reviewer take on a single adjustment dispute (for example approve, reject, send back to the carrier, hold)? Would reviewers accept making the decision in our review screen first and then carrying it out in the system themselves?

**Our current assumption.** Four buttons per dispute: approve, return to carrier (with an editable draft message), clear a flag (a reason is required), and hold. The buttons only record the reviewer's decision; our tool writes nothing to your system and sends nothing to carriers. Our tool never suggests whether a charge should be paid.

**What your answer changes.** The set of buttons and the list of recorded decision types; whether the return-to-carrier draft is worth building; and whether recorded decisions can later serve as reference answers.

### Q8. What reviewers must not miss, and what would be noise

**Question.** Of the alerts below, which two or three matter most to your reviewers, and which would they ignore? Is anything they routinely check missing from the list?

- the amounts read from the text do not add up to Delta
- the same charge appears more than once (same invoice or same shipment)
- a charge we cannot match to a known charge type
- an amount with no charge named, or a charge named with no amount
- arithmetic in the text that does not hold (for example quantity times rate)
- tax present
- the text says PPG approved or requested the service, or cites the contract

**Our current assumption.** Every dispute is looked at by a person today, and too many alerts is worse than too few. The first six send a record for attention; the last is shown as a note only.

**What your answer changes.** Which conditions raise an alert and which are demoted to a note (one line each in our rules file), what is expanded by default on the review screen, and what we measure when we report how often records are flagged.

### Q9. Who uses the structured output after review

**Question.** Once a dispute has been turned into line items and reviewed, who or what uses that data next, and for what: reporting by charge type or carrier, carrier scorecards, loading back into a system, something else? Does any export carry the amount finally approved?

**Our current assumption.** The output is a table with one row per line item (charge type, amount, source phrase, status), used for reporting on what carriers ask for. The export has no final approved amount, so any totals are amounts claimed, not amounts paid. Only records that passed our checks and reconcile with Delta go into the downstream table; everything else is visible to the reviewer only.

**What your answer changes.** The columns and format of the export, whether unreconciled records should also be exported with a status column, and whether we report "claimed" figures only or can also report "approved" figures.

### Q10. An existing list of accessorial charge codes

**Question.** Does PPG, or the transportation system, already have a list of accessorial charge codes that carriers or reviewers use?

**Our current assumption.** There is none we can use, so we built our own table of about 37 charge types from public industry lists (EDI 210 charge codes and carriers' published tariffs), with anything unmatched kept as "other" together with the carrier's original wording.

**What your answer changes.** If a list exists, we add your code as a column in our table and align our categories to it so the output joins to your data; if not, ours stays as is and we fill in the public EDI codes instead.

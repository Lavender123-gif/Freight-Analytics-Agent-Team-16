# Topic note: balances and payment history

Code added this note because the text uses balance, payment or history words (BALANCE, PAID, BILLED, OWED,
OUTSTANDING, PREVIOUSLY, ORIGINAL and the like).

- Payment history is wording that describes what was billed, paid, short-paid or written off, and what is still owed.
  The history statuses are in section 3 of the skill.
- {{CONCEPT:balance_due}}
- `stated_amount_due_id` is the amount the text calls the balance or the amount due, when it writes one; it is
  recorded as written and does not change what you count.
- A text that mentions an earlier claim, dispute or request for this shipment fills `earlier_claim_quote`; payment
  history alone does not.

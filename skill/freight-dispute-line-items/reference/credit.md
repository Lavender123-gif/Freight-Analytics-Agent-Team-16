# Topic note: credits and negative amounts

Code added this note because the text has credit wording, a minus sign before a number, or an amount in
parentheses.

- The rule for `is_credit` is in section 3 of the skill (`is_credit`). This note adds two cases.
- A credit given earlier and only described ('WE CREDITED $40 LAST MONTH') is history (`DEDUCTED`), not part of
  this claim, and needs an exclusion phrase.
- An amount that is both a credit and a tax (a tax refund) is `TAX_AMOUNT` with `is_credit` true.

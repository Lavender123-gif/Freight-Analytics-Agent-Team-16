# Topic note: tax

Code added this note because the text names a tax (GST, HST, PST, QST or TAX).

- A tax amount written in the text is `TAX_AMOUNT` with its tax code (`TAX.GST`, `TAX.HST`, `TAX.PST`, or
  `TAX.UNSPECIFIED` when the text does not say which). It is counted when the text asks for it, like any amount.
- When the text states the base the tax is on, add a `TAX` relation: the base amounts are the operands, the tax
  amount is the result.
- A tax named without its amount (`+ HST`, `PLUS GST`, `TAX EXTRA`) is a line item with `amount_ref: null` and the
  tax code. Code works out the implied tax from the table below.
- A stated total that includes the tax ('$100.00 + $13.00 HST = $113.00') is a `TOTAL`, with a `SUM` relation.
- Which province's tax applies to a freight service is not settled. Do not judge whether a rate is right; code
  compares rates with the table and a reviewer looks at every tax.

Canadian sales tax table used by code ({{TAX_WINDOW}}; the destination province is used by default):

{{TAX_TABLE}}

A province or state not in the table has no Canadian tax rule.

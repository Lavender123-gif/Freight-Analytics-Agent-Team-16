# B01 gate — examples (before → after)

Screened: no shipment / invoice / PK numbers, no carrier codes. Names and emails appear only as `[PERSON]` / `[EMAIL]`.
"Before" is the source rows; "after" is one event with redacted text and step-1 diagnostics.

| # | source rows (before) | redacted text (after) | Delta | origin→destination | step-1 diagnostics |
|---|---|---|---|---|---|
| E1 | 1 | `BC ROAD CLOSURE [PERSON] FROM PPG NOTIFIED $8.39` | 8.39 | CA→CA | `REC.TEXT.PII_REDACTED` |
| E2 | 1 | `$70 EQUIPMENT DETENTION 8/10/2021 4:24:00 PM-8/18/2021 9:47:00 AM APPROVED BY [PERSON]` | 70.00 | US→CA | `REC.TEXT.PII_REDACTED`, `REC.FIELD.CROSS_BORDER` |
| E3 | 8 | `RATED AS 20 000 LBS. FSC TL SHOULD APPLY. FSC BALANCE DUE IS $28.53` | 28.53 | CA→CA | `REC.INPUT.EXPORT_DUPLICATE` |
| E4 | 1 | `.68` | 0.00 | US→US | `REC.FIELD.DELTA_ZERO` |
| E5 | 1 | `$150 HAZMAT CHARGE ON SHIPMENT BOL 40 263 LBS` | 150.00 | US→CA | `REC.FIELD.CROSS_BORDER` |

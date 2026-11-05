# B02 number parse — examples (before → after)

Before: redacted text. After: marked text given to the model; every number has an id, dates are `D`, unclaimed digits are `?` regions. Screened for IDs and carrier codes.

| feature | text (before) | marked text (after) | number table (value, $, unit) |
|---|---|---|---|
| space-merged amount | `DISPUTE - UNPAID $ 8 400.00` | `DISPUTE - UNPAID [#1 $ 8 400.00]` | #1=8400.00$ |
| leading dot | `.67 FSC` | `[#1 .67] FSC` | #1=0.67 |
| unrecognized region | `MISSING $41.25 DETENTION TIME AND $15.00 CV19 FEE + HST = $63.55` | `MISSING [#1 $41.25] DETENTION TIME AND [#2 $15.00] [?1 CV19] FEE + HST = [#3 $63.55]` | #1=41.25$; #2=15.00$; #3=63.55$ |
| date + weight + amount | `ADD $150 ORGIN PERDIEM - EMPTY DROPPED 02/22 PICKED UP 02/28 - 02/22-02/26 FREE- 02/27-02/28- 2 DAYS AT $75 EACH` | `ADD [#1 $150] ORGIN PERDIEM - EMPTY DROPPED [D1 02/22] PICKED UP [D2 02/28] - [D3 02/22]-[D4 02/26] FREE- [D5 02/27]-[D6 02/28]- [#2 2] DAYS AT [#3 $75] EACH` | #1=150$; #2=2 (DAYS); #3=75$ |
| minus adjacent | `-250 [PERSON] NOT NEED 2009.21 AMOUNT APPROVED` | `-[#1 250] [PERSON] NOT NEED [#2 2009.21] AMOUNT APPROVED` | #1=250; #2=2009.21 |

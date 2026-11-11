# Annotation guide: what is each number in a carrier note?

Chinese version: `annotation_guide.zh.md`. If the two differ, this English version is the reference.

## The task

Carriers explain invoice adjustments in short free-text notes. For each note you get the text (personal names already replaced by placeholders) and a list of the numbers our code found in it, one row per number. You tell us what each number is. Your answers are the reference we use to measure whether the software reads these notes correctly.

You are **not** asked whether a charge is justified or should be paid. Never judge that. You only record what the text says.

One pack has 45 items and takes about 2 hours. Work alone; do not discuss items with other annotators until everyone has handed in. Fill in your annotator ID on the Instructions sheet (cell B3), then work on the Annotation sheet. Every answer is a dropdown; do not type other values. Do not sort, insert or delete rows.

## What you fill in

**1. What is this number? (every row)** Choose **Money amount** for any sum of money: a charge, a tax amount, a total, an amount paid, a credit. Otherwise choose what it is: weight; date; ZIP or ID number (BOL, PRO, invoice, reference numbers); quantity (days, hours, pallets, pieces); rate or unit price (`$75 EACH`, `@ $50 A DAY`: a price per unit, not the sum asked for); percentage. If you cannot tell whether a number is money, choose Money amount and answer Unclear in item 2.

**2. Is it part of this claim? (only rows you marked Money amount)** **Counted**: an amount the carrier is asking for now (also amounts described as still owed or short paid). **Not counted: already paid or billed (history)**: what was invoiced, paid or deducted before. **Not counted: total or subtotal**: the sum of other amounts listed in the same text; count the parts, not the total. **Not counted: approved amount or other reference**: an amount quoted for context (approved, quoted, per contract) that is not itself asked for. **Credit**: the carrier gives money back to PPG (credit, refund, overpayment, a minus sign). **Unclear**: two readings are both defensible.

**3. Charge category (only rows you marked Counted)** Pick the category of the charge the text names for this amount; the Glossary sheet says which category common charge words belong to. **Text names no charge**: the text gives an amount but no charge name. **Meaning pending confirmation**: the charge word is one we have not confirmed with the client (listed in the Glossary); choose this and do not guess. **Other named charge**: a charge is named but fits no category. If one amount covers charges from two categories, pick the first one named and say so in the note.

**4. Confident about this item? (first row of each item) and Note** **Yes** if you would give the same answers again tomorrow; **No** if any answer for this item was a close call. The note is optional: use it to say what was ambiguous, or that a number looks wrongly cut.

## Rules

- Judge from the text only. Do not guess, and do not use what you think the carrier probably meant.
- If two readings are both defensible, choose **Unclear** (for every number whose role depends on which reading is right) and say why in the note. Unclear is a valid answer, not a failure.
- Fill every row. Leave item 2 empty for numbers that are not money, and item 3 empty for amounts that are not Counted.
- Dates and times the code recognised (such as `06/03`) have no row; you do not annotate them. A row whose number is `?1` is a chunk the code could not cut (letters and digits mixed): judge the number inside it.
- The examples below are synthetic: written for this guide in the style of the data. None of them is an item in a pack.

## Worked examples

### Example 1: A single charge

**Text shown to you:**

> LIFTGATE DELIVERY REQUIRED PER BOL 88213 - $45.00

**Where to look:** The word next to each number: `BOL` before 88213, the charge name `LIFTGATE DELIVERY` and the `$` on 45.00.

**Criterion:** A number introduced by a document word (BOL, PRO, INVOICE, REF) is an ID. One charge name with one amount and no history words: the amount is counted.

| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |
|---|---|---|---|---|---|
| #1 | `88213` | Not money: ZIP or ID number | (leave empty) | (leave empty) | Follows `BOL`: a bill of lading number, not money. Items 2 and 3 stay empty. |
| #2 | `$45.00` | Money amount | Counted in this claim | Accessorial (extra service at pickup or delivery) | The only amount, asked for a liftgate delivery; liftgate is an extra delivery service, so Accessorial. |

**4. Confident:** Yes. Nothing in the text allows a second reading.

### Example 2: Several charges plus a total (BALANCE DUE)

**Text shown to you:**

> INSIDE DELIVERY $25 LIFTGATE $18.50 FUEL SURCHARGE $31.20 BALANCE DUE $74.70

**Where to look:** Each charge name with the amount right after it, then check the last amount: 25 + 18.50 + 31.20 = 74.70.

**Criterion:** When the listed amounts add up to the BALANCE DUE, the BALANCE DUE is their total: count the parts, mark the total Not counted. Do the addition yourself. If it does not add up, you cannot tell from the text whether the BALANCE DUE is a total or a separate amount: choose Unclear for the numbers whose role depends on it and say so in the note.

| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |
|---|---|---|---|---|---|
| #1 | `$25` | Money amount | Counted in this claim | Accessorial (extra service at pickup or delivery) | Amount for inside delivery, an extra delivery service. |
| #2 | `$18.50` | Money amount | Counted in this claim | Accessorial (extra service at pickup or delivery) | Amount for liftgate, an extra delivery service. |
| #3 | `$31.20` | Money amount | Counted in this claim | Fuel surcharge | Amount for the fuel surcharge. |
| #4 | `$74.70` | Money amount | Not counted: total or subtotal | (leave empty) | Equals #1 + #2 + #3, so it is their total. Counting it too would double the claim. Item 3 stays empty. |

**4. Confident:** Yes. The sum checks out exactly.

### Example 3: Payment history: paid and still owed in one note

**Text shown to you:**

> BILLED LINE HAUL $ 1 250.00 AND FSC 187.50 PAID 1 250.00 SHORT PAID 187.50 PLEASE PAY BALANCE

**Where to look:** The status word in front of each amount: `BILLED`, `PAID`, `SHORT PAID`. Note that `$ 1 250.00` is one number (1,250.00) written with a space.

**Criterion:** Billed and paid amounts are history. Only the amount described as short paid or still owed is counted. The same value can appear twice with different roles: judge each occurrence by the words around it.

| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |
|---|---|---|---|---|---|
| #1 | `$ 1 250.00` | Money amount | Not counted: already paid or billed (history) | (leave empty) | What was billed for line haul: history. |
| #2 | `187.50` | Money amount | Not counted: already paid or billed (history) | (leave empty) | What was billed for the fuel surcharge (FSC): history. No `$`, but it is clearly money. |
| #3 | `1 250.00` | Money amount | Not counted: already paid or billed (history) | (leave empty) | Follows `PAID`: already paid. |
| #4 | `187.50` | Money amount | Counted in this claim | Fuel surcharge | Follows `SHORT PAID`: still owed and asked for now. It is the unpaid 187.50 billed as FSC, so Fuel surcharge. |

**4. Confident:** Yes. Each amount has its own status word.

### Example 4: Quantity times rate, with a weight and dates in between

**Text shown to you:**

> ADD $225 DESTINATION PER DIEM - CONTAINER 18 450 LBS DELIVERED 06/03 RETURNED 06/08 - 2 DAYS FREE - 3 DAYS @ $75 EACH

**Where to look:** Unit words after the numbers (`LBS`, `DAYS`) and price words (`@`, `EACH`); then check 3 x 75 = 225. The dates 06/03 and 06/08 have no rows.

**Criterion:** In `quantity @ price = amount`, only the amount is counted. The price per unit is Rate or unit price even with a `$`; the quantity is Quantity. If the text gave only `3 DAYS @ $75` with no result, whether $75 is the unit price or the whole charge is not stated: Money amount, Unclear.

| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |
|---|---|---|---|---|---|
| #1 | `$225` | Money amount | Counted in this claim | Detention, storage, per diem (time-based) | `ADD $225` is the amount asked for; per diem is a daily charge for keeping a container, a time-based charge. |
| #2 | `18 450` | Not money: weight | (leave empty) | (leave empty) | Followed by `LBS`. `18 450` is one number (18,450) written with a space. |
| #3 | `2` | Not money: quantity | (leave empty) | (leave empty) | A number of days (the free days). |
| #4 | `3` | Not money: quantity | (leave empty) | (leave empty) | A number of days (the days charged). |
| #5 | `$75` | Not money: rate or unit price | (leave empty) | (leave empty) | `@ $75 EACH` is the price per day. 3 x 75 = 225 is already in #1, so this is not a second amount. |

**4. Confident:** Yes. The product matches the amount asked for.

### Example 5: Tax mentioned without a tax amount, and a credit

**Text shown to you:**

> REDELIVERY $150.00 + HST. LESS CREDIT $20.00 FOR OVERPAYMENT ON PRIOR INVOICE AS CONFIRMED BY [PERSON_1]

**Where to look:** `+ HST` has no number after it. `LESS CREDIT` and `OVERPAYMENT` in front of $20.00. `[PERSON_1]` stands for a removed name.

**Criterion:** You annotate only the numbers that are there. A tax that is named without an amount gets no row and you do not work one out. (A tax amount that is written, such as `GST $7.50`, is an ordinary Money amount: Counted when it is asked for, category Tax.) An amount the carrier gives back (credit, refund, overpayment, minus sign) is Credit, not Counted.

| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |
|---|---|---|---|---|---|
| #1 | `$150.00` | Money amount | Counted in this claim | Accessorial (extra service at pickup or delivery) | Amount for redelivery, a second delivery attempt. The category is Accessorial, not Tax: HST is only mentioned. |
| #2 | `$20.00` | Money amount | Credit (carrier gives back to PPG) | (leave empty) | `LESS CREDIT ... FOR OVERPAYMENT`: money going back to PPG. Item 3 stays empty because it is not Counted. |

**4. Confident:** Yes. Optional note: "HST mentioned, no amount".

## Glossary

| Term | Meaning |
|---|---|
| BALANCE DUE | The amount the carrier says is still owed; if it equals the sum of amounts listed beside it, it is their total (Not counted: total), otherwise judge from the text or choose Unclear. |
| SHORT PAID | PPG paid less than the invoice; the amount after it is the unpaid part and is normally Counted. |
| ADJUSTED OFF | An amount that was removed or deducted from an earlier invoice or payment; history, Not counted. |
| OVERPAYMENT | PPG paid more than was owed; an amount described this way goes back to PPG, so Credit. |
| AMOUNT APPROVED | An amount someone agreed to earlier; quoted as a reference, Not counted (approved amount) unless the text also asks for it. |
| LINE HAUL (LH, LINEHAUL) | The basic charge for moving the freight from origin to destination; category Linehaul. |
| FSC (FUEL SURCHARGE) | Fuel surcharge, an add-on that follows fuel prices; category Fuel surcharge. |
| ACCESSORIAL | Any extra service beyond plain transportation at pickup or delivery (liftgate, inside delivery, redelivery, appointment, hazmat, lumper); category Accessorial. |
| DETENTION | Charge for a driver or equipment kept waiting beyond the free time; category Detention, storage, per diem. |
| DWELL | Days a container sits between arriving at the rail ramp and being delivered; category Detention, storage, per diem. |
| PER DIEM (PERDIEM) | A daily charge for keeping a container or chassis beyond the free days; category Detention, storage, per diem. |
| STORAGE | Charge for freight or a container kept at a terminal or rail ramp; category Detention, storage, per diem. |
| LUMPER | Third-party labour paid to unload the truck; category Accessorial. |
| LIFTGATE / TAILGATE | A lift on the back of the truck used where there is no dock; the two words mean the same; category Accessorial. |
| TONU | Truck ordered, not used: a fee when a truck is sent and the load is cancelled; category Accessorial. |
| CHASSIS | The wheeled frame a shipping container rides on; a chassis charge is category Drayage. |
| PRE-PULL (YARD PULL) | Moving a container out of the port or rail yard to another yard before delivery; category Drayage. |
| BOL | Bill of lading, the shipping document; a number after BOL is an ID, and a weight quoted "per BOL" is a weight. |
| GST | Canadian federal Goods and Services Tax; a GST amount is category Tax. |
| HST | Harmonized Sales Tax, used in some Canadian provinces in place of GST plus provincial tax; category Tax. |
| PST | Provincial sales tax in Canada; category Tax. |
| QST | Quebec Sales Tax, the provincial tax of Quebec; category Tax. |
| [PERSON_1], [EMAIL_1], [PHONE_1] | Placeholders put in by our code where a personal name, an email address or a phone number was removed; the digit only tells people apart, it is not a number to annotate. |
| Space as thousands separator (`$ 8 400.00`) | Some carriers write thousands with a space, so this is one number, 8,400.00; if the row looks like two different numbers glued together, annotate it as best you can and say so in the note. |
| Leading-dot decimal (`.69`) | A decimal written without the zero: `.69` is 0.69, i.e. 69 cents. |
| PURCHASED TRANSPORTATION (PURCHASE FEE, PURCHASED TRANSP SURCHARGE, any spelling) | Meaning not yet confirmed with the client: choose "Meaning pending confirmation", do not guess. |
| Other charge words you do not know | If a charge is clearly named but you cannot place it in a category, choose "Other named charge" and copy the word into the note; do not guess a category. |

## Dropdown options

- **1**: Money amount; Not money: weight; Not money: date; Not money: ZIP or ID number; Not money: quantity; Not money: rate or unit price; Not money: percentage
- **2**: Counted in this claim; Not counted: already paid or billed (history); Not counted: total or subtotal; Not counted: approved amount or other reference; Credit (carrier gives back to PPG); Unclear
- **3**: Linehaul (the transportation charge itself); Fuel surcharge; Rate correction (rate, tier, weight or factor applied wrongly); Accessorial (extra service at pickup or delivery); Detention, storage, per diem (time-based); Drayage (port or rail container moves); Tax; Other named charge; Text names no charge; Meaning pending confirmation
- **4**: Yes; No

# Topic note: rate corrections

Code added this note because the text argues about a rate, tier, weight, contract or tariff (SHOULD APPLY, SHOULD
BE, PER CONTRACT, TARIFF, RERATE and the like).

- {{CONCEPT:rate_correction}}
- A weight the carrier says should have been used ('20 000 LBS') is a `QUANTITY`; a factor or percentage is a
  `RATE`. Neither is counted.
- Put the contract, tariff or document the carrier cites in `carrier_stated_basis` (type `CONTRACT_OR_TARIFF` or
  `SHIPPING_DOCUMENT`). It is the carrier's claim, nothing more.

# B03 auto-reject pre-check — examples (before → after)

Before: the redacted text and Delta. After: no model call; the automatic notice built from the diagnostics catalog.

| text (before) | Delta | trigger | notice: required change | notice: acceptance |
|---|---|---|---|---|
| (empty) | 0.00 | REC.TEXT.EMPTY | 补充说明：写明每一项费用的名称和金额，以及收费原因 | 文本至少包含一个费用名称和一个金额，且列出的金额之和等于本次差额 |
| `56.56` | 56.56 | REC.TEXT.NUMBERS_ONLY | 写明这笔金额对应的费用名称和收费原因 | 每个金额旁边都有费用名称；金额之和等于本次差额 |
| `51.04` | 51.04 | REC.TEXT.NUMBERS_ONLY | 写明这笔金额对应的费用名称和收费原因 | 每个金额旁边都有费用名称；金额之和等于本次差额 |
| `90.80` | 90.80 | REC.TEXT.NUMBERS_ONLY | 写明这笔金额对应的费用名称和收费原因 | 每个金额旁边都有费用名称；金额之和等于本次差额 |

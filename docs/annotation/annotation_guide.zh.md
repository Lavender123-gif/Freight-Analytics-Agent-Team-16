# 标注指南：承运商说明里的每个数字是什么

英文版：`annotation_guide.en.md`。两版不一致时以英文版为准。下拉菜单是英文的，本文在括号里给出中文。

## 任务

承运商用很短的自由文本解释发票调整。每条记录给你原文（人名已换成占位符）和代码在原文里找到的数字，一行一个数字。你来说明每个数字是什么。你的答案是参照答案，用来衡量软件读这些文本读得准不准。

**不**需要判断费用有没有道理、该不该付，任何时候都不要做这个判断。只记录原文怎么写。

一个包 45 条，大约 2 小时。独立完成；所有人交回之前，不要和其他标注人讨论具体条目。先在 Instructions 表的 B3 格填上你的标注人编号，然后在 Annotation 表里填。每一格都是下拉菜单，不要手打其他内容。不要排序，不要插入或删除行。

## 要填的四项

**1. 这个数字是什么？（每一行都填）** 凡是一笔钱都选 **Money amount（金额）**：费用、税额、合计、已付金额、贷记都算。不是钱就选它是什么：重量；日期；邮编或编号（BOL、PRO、发票号、参考号）；数量（天数、小时、托盘数、件数）；费率或单价（`$75 EACH`、`@ $50 A DAY`，是每单位的价格，不是要收的总额）；百分比。分不清是不是钱时，选 Money amount，并在第 2 项选 Unclear。

**2. 是否属于这次主张？（只填第 1 项选了 Money amount 的行）** **Counted（计入）**：承运商现在要收的金额（写明仍欠、少付的也算）。**Not counted: already paid or billed（不计入：历史）**：以前开过票、付过或扣过的金额。**Not counted: total or subtotal（不计入：合计或小计）**：同一段文字里其他金额加起来的数；计入的是各个分项，不是合计。**Not counted: approved amount or other reference（不计入：批准额或其他引用）**：只是拿来说明情况的金额（批准额、报价、合同价），本身不是要收的钱。**Credit（贷记）**：承运商退给 PPG 的钱（credit、refund、overpayment、负号）。**Unclear（说不清）**：两种读法都说得通。

**3. 费用大类（只填第 2 项选了 Counted 的行）** 按原文给这笔金额写的费用名选大类；常见费用词属于哪一类见 Glossary 表。**Text names no charge（原文没写费用名）**：只有金额，没有费用名。**Meaning pending confirmation（含义待确认）**：费用词的含义还没向客户确认（术语表里列出）；选这一项，不要猜。**Other named charge（其他有名称的费用）**：写了费用名，但哪一类都不合适。一笔金额对应两个大类的费用时，选先写的那个，并在备注里说明。

**4. 这条有没有把握？（每条的第一行）以及备注** **Yes（有）**：明天再做一遍会给出同样的答案；**No（没有）**：这条里有任何一格是勉强选的。备注可不填：用来写哪里有歧义，或者某个数字看起来切错了。

## 规则

- 只按原文判断。不猜，也不要按“承运商大概是这个意思”来填。
- 两种读法都说得通时，选 **Unclear（说不清）**（凡是角色取决于哪种读法的数字都选），并在备注里写原因。“说不清”是正常答案，不算没做好。
- 每一行都要填。不是金额的数字，第 2 项留空；没有选 Counted 的金额，第 3 项留空。
- 代码已经认出的日期和时间（如 `06/03`）没有行，不用标。编号是 `?1` 的行是代码切不开的一段（字母和数字混在一起）：判断里面的那个数字。
- 下面的例子都是合成的：按数据的写法专门为本指南写的，不是任何包里的条目。

## 完整例子

### 例 1: 单笔费用

**给你看的原文：**

> LIFTGATE DELIVERY REQUIRED PER BOL 88213 - $45.00

**看哪里:** 看每个数字旁边的词：88213 前面是 `BOL`；45.00 带 `$`，对应的费用名是 `LIFTGATE DELIVERY`。

**判断标准:** 跟在单据词（BOL、PRO、INVOICE、REF）后面的数字是编号。一个费用名配一个金额、没有任何历史用词：这个金额计入。

| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |
|---|---|---|---|---|---|
| #1 | `88213` | Not money: ZIP or ID number（不是金额：邮编或编号） | （留空） | （留空） | 跟在 `BOL` 后面，是提单号，不是钱。第 2、3 项留空。 |
| #2 | `$45.00` | Money amount（金额） | Counted in this claim（计入） | Accessorial (extra service at pickup or delivery)（附加服务费（提货或送货时的额外服务）） | 唯一的金额，为 liftgate 送货而收；liftgate 是送货时的额外服务，属于附加服务费。 |

**4. 有没有把握:** Yes（有）. 原文没有第二种读法。

### 例 2: 多项费用加合计（BALANCE DUE）

**给你看的原文：**

> INSIDE DELIVERY $25 LIFTGATE $18.50 FUEL SURCHARGE $31.20 BALANCE DUE $74.70

**看哪里:** 每个费用名和紧跟其后的金额；再核对最后一个金额：25 + 18.50 + 31.20 = 74.70。

**判断标准:** 列出的金额加起来正好等于 BALANCE DUE 时，BALANCE DUE 就是合计：分项计入，合计选不计入。加法要自己算一遍。加不上时，光看原文分不出 BALANCE DUE 是合计还是另外一笔：角色取决于此的数字都选 Unclear，并在备注里说明。

| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |
|---|---|---|---|---|---|
| #1 | `$25` | Money amount（金额） | Counted in this claim（计入） | Accessorial (extra service at pickup or delivery)（附加服务费（提货或送货时的额外服务）） | inside delivery 的金额，送货时的额外服务。 |
| #2 | `$18.50` | Money amount（金额） | Counted in this claim（计入） | Accessorial (extra service at pickup or delivery)（附加服务费（提货或送货时的额外服务）） | liftgate 的金额，送货时的额外服务。 |
| #3 | `$31.20` | Money amount（金额） | Counted in this claim（计入） | Fuel surcharge（燃油附加费） | 燃油附加费的金额。 |
| #4 | `$74.70` | Money amount（金额） | Not counted: total or subtotal（不计入：合计或小计） | （留空） | 等于 #1 + #2 + #3，是它们的合计。再计入一次就重复了。第 3 项留空。 |

**4. 有没有把握:** Yes（有）. 加法完全对得上。

### 例 3: 付款历史：已付和仍欠写在一起

**给你看的原文：**

> BILLED LINE HAUL $ 1 250.00 AND FSC 187.50 PAID 1 250.00 SHORT PAID 187.50 PLEASE PAY BALANCE

**看哪里:** 每个金额前面的状态词：`BILLED`、`PAID`、`SHORT PAID`。注意 `$ 1 250.00` 是一个数（1,250.00），千位用空格隔开。

**判断标准:** 已开票、已付的金额是历史。只有写明少付或仍欠的金额计入。同一个数值可以出现两次、角色不同：每一处按它周围的词判断。

| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |
|---|---|---|---|---|---|
| #1 | `$ 1 250.00` | Money amount（金额） | Not counted: already paid or billed (history)（不计入：已付或已开票的历史） | （留空） | line haul 的开票金额，是历史。 |
| #2 | `187.50` | Money amount（金额） | Not counted: already paid or billed (history)（不计入：已付或已开票的历史） | （留空） | 燃油附加费（FSC）的开票金额，是历史。没有 `$`，但显然是钱。 |
| #3 | `1 250.00` | Money amount（金额） | Not counted: already paid or billed (history)（不计入：已付或已开票的历史） | （留空） | 跟在 `PAID` 后面，已经付了。 |
| #4 | `187.50` | Money amount（金额） | Counted in this claim（计入） | Fuel surcharge（燃油附加费） | 跟在 `SHORT PAID` 后面：仍欠、现在要收。它就是没付的那笔 FSC 187.50，所以选燃油附加费。 |

**4. 有没有把握:** Yes（有）. 每个金额都有自己的状态词。

### 例 4: 数量乘单价，中间夹着重量和日期

**给你看的原文：**

> ADD $225 DESTINATION PER DIEM - CONTAINER 18 450 LBS DELIVERED 06/03 RETURNED 06/08 - 2 DAYS FREE - 3 DAYS @ $75 EACH

**看哪里:** 数字后面的单位词（`LBS`、`DAYS`）和单价用词（`@`、`EACH`）；再核对 3 x 75 = 225。日期 06/03、06/08 没有行。

**判断标准:** “数量 @ 单价 = 金额”里只有金额计入。单价即使带 `$` 也选费率或单价；数量选数量。如果原文只写 `3 DAYS @ $75`、没写结果，$75 是单价还是整笔费用原文没说：选 Money amount，第 2 项选 Unclear。

| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |
|---|---|---|---|---|---|
| #1 | `$225` | Money amount（金额） | Counted in this claim（计入） | Detention, storage, per diem (time-based)（滞留、仓储、按日计费（按时间收的费）） | `ADD $225` 是要收的金额；per diem 是占用集装箱按日收的费，属于按时间收的费。 |
| #2 | `18 450` | Not money: weight（不是金额：重量） | （留空） | （留空） | 后面是 `LBS`。`18 450` 是一个数（18,450），千位用空格隔开。 |
| #3 | `2` | Not money: quantity（不是金额：数量） | （留空） | （留空） | 天数（免费的天数）。 |
| #4 | `3` | Not money: quantity（不是金额：数量） | （留空） | （留空） | 天数（收费的天数）。 |
| #5 | `$75` | Not money: rate or unit price（不是金额：费率或单价） | （留空） | （留空） | `@ $75 EACH` 是每天的价格。3 x 75 = 225 已经是 #1，所以这不是另一笔金额。 |

**4. 有没有把握:** Yes（有）. 乘积和要收的金额对得上。

### 例 5: 写了税但没有税额，以及贷记

**给你看的原文：**

> REDELIVERY $150.00 + HST. LESS CREDIT $20.00 FOR OVERPAYMENT ON PRIOR INVOICE AS CONFIRMED BY [PERSON_1]

**看哪里:** `+ HST` 后面没有数字。$20.00 前面有 `LESS CREDIT` 和 `OVERPAYMENT`。`[PERSON_1]` 是被去掉的人名。

**判断标准:** 只标原文里有的数字。只写了税名、没写税额的，没有行，也不要自己去算。（写出来的税额，如 `GST $7.50`，就是普通的金额：是要收的就计入，大类选税。）承运商退回的金额（credit、refund、overpayment、负号）选贷记，不选计入。

| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |
|---|---|---|---|---|---|
| #1 | `$150.00` | Money amount（金额） | Counted in this claim（计入） | Accessorial (extra service at pickup or delivery)（附加服务费（提货或送货时的额外服务）） | redelivery（再次送货）的金额。大类选附加服务费，不选税：HST 只是提了一下。 |
| #2 | `$20.00` | Money amount（金额） | Credit (carrier gives back to PPG)（贷记（承运商退给 PPG）） | （留空） | `LESS CREDIT ... FOR OVERPAYMENT`：退给 PPG 的钱。没有选 Counted，所以第 3 项留空。 |

**4. 有没有把握:** Yes（有）. 备注可写：“提到 HST，没有税额”。

## 术语表

| 术语 | 含义 |
|---|---|
| BALANCE DUE | 承运商说还欠的金额；等于旁边各金额之和时是合计（不计入：合计），否则按原文判断或选说不清。 |
| SHORT PAID | PPG 付的比发票少；后面的金额是没付的部分，通常计入。 |
| ADJUSTED OFF | 以前从发票或付款里减掉的金额；是历史，不计入。 |
| OVERPAYMENT | PPG 多付了；这样描述的金额要退给 PPG，选贷记。 |
| AMOUNT APPROVED | 以前有人同意过的金额；作为引用出现，选不计入（批准额），除非原文同时在要这笔钱。 |
| LINE HAUL (LH, LINEHAUL) | 把货从起点运到终点的基本运费；大类选干线运费。 |
| FSC (FUEL SURCHARGE) | 燃油附加费，随油价变动的附加收费；大类选燃油附加费。 |
| ACCESSORIAL | 提货或送货时运输以外的额外服务（liftgate、inside delivery、redelivery、预约、危险品、lumper）；大类选附加服务费。 |
| DETENTION | 司机或设备等待超过免费时间而收的费；大类选滞留、仓储、按日计费。 |
| DWELL | 集装箱从到达铁路场站到送达之间停留的天数；大类选滞留、仓储、按日计费。 |
| PER DIEM (PERDIEM) | 占用集装箱或底盘车超过免费天数后按日收的费；大类选滞留、仓储、按日计费。 |
| STORAGE | 货物或集装箱存放在场站或铁路场站的费用；大类选滞留、仓储、按日计费。 |
| LUMPER | 请第三方卸货的人工费；大类选附加服务费。 |
| LIFTGATE / TAILGATE | 车尾升降板，在没有装卸平台的地方使用；两个词是一个意思；大类选附加服务费。 |
| TONU | Truck ordered, not used：派了车但货取消时收的费；大类选附加服务费。 |
| CHASSIS | 运集装箱用的带轮底盘车；底盘车费用的大类选短驳。 |
| PRE-PULL (YARD PULL) | 送货前先把集装箱从港口或铁路场站拖到另一个场地；大类选短驳。 |
| BOL | 提单，即运输单据；BOL 后面的数字是编号，“per BOL”引用的重量是重量。 |
| GST | 加拿大联邦商品及服务税；GST 税额的大类选税。 |
| HST | 合并销售税，加拿大部分省份用它代替 GST 加省税；大类选税。 |
| PST | 加拿大的省销售税；大类选税。 |
| QST | 魁北克销售税，魁北克省的省税；大类选税。 |
| [PERSON_1], [EMAIL_1], [PHONE_1] | 代码把人名、邮箱、电话去掉后放的占位符；里面的数字只用来区分不同的人，不是要标的数字。 |
| Space as thousands separator (`$ 8 400.00`) | 有的承运商用空格分千位，所以这是一个数 8,400.00；如果这一行看起来是两个不同的数被拼在了一起，尽量标，并在备注里说明。 |
| Leading-dot decimal (`.69`) | 省略了 0 的小数：`.69` 就是 0.69，即 69 美分。 |
| PURCHASED TRANSPORTATION (PURCHASE FEE, PURCHASED TRANSP SURCHARGE, any spelling) | 含义还没向客户确认：选“含义待确认”，不要猜。 |
| Other charge words you do not know | 写了费用名但你归不了类时，选“其他有名称的费用”，把这个词抄进备注；不要猜大类。 |

## 下拉选项一览

- **1**: Money amount（金额）; Not money: weight（不是金额：重量）; Not money: date（不是金额：日期）; Not money: ZIP or ID number（不是金额：邮编或编号）; Not money: quantity（不是金额：数量）; Not money: rate or unit price（不是金额：费率或单价）; Not money: percentage（不是金额：百分比）
- **2**: Counted in this claim（计入）; Not counted: already paid or billed (history)（不计入：已付或已开票的历史）; Not counted: total or subtotal（不计入：合计或小计）; Not counted: approved amount or other reference（不计入：批准额或其他引用）; Credit (carrier gives back to PPG)（贷记（承运商退给 PPG））; Unclear（说不清）
- **3**: Linehaul (the transportation charge itself)（干线运费（运输本身的费用））; Fuel surcharge（燃油附加费）; Rate correction (rate, tier, weight or factor applied wrongly)（费率更正（费率、档位、重量或系数用错））; Accessorial (extra service at pickup or delivery)（附加服务费（提货或送货时的额外服务））; Detention, storage, per diem (time-based)（滞留、仓储、按日计费（按时间收的费））; Drayage (port or rail container moves)（短驳（港口或铁路集装箱相关））; Tax（税）; Other named charge（其他有名称的费用）; Text names no charge（原文没写费用名）; Meaning pending confirmation（含义待确认）
- **4**: Yes（有）; No（没有）

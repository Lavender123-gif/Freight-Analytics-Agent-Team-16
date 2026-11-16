# T13 正文：我们的费用代码表对到 Jake 的清单上（2026-11-13）

本轮是分析：没有调模型（花费 0，账本仍是 71.67 美元），没有读测试集和预留 mock，没有用人工标注，没有改 `taxonomy.yaml`、`SKILL.md`、`src/`、`rules.yaml`、测试、mock。

## 0. 结论

1. **对应关系**：我们的 37 个代码里，17 个能直接对到清单的一个名称上（12 个完全对应，5 个近似对应），8 个是一对多，6 个只能当子项，6 个没有位置（其中 4 个是真正的费用种类，另 2 个是“税种未指明”和“其他”这两个标记）。见第 2 节。
2. **数据覆盖**：开发集留存读法里有 1002 笔带费用名的金额。按次数 93.1%（933 笔）落在清单之内，按金额 94.1%。但直接对上的只有 24.9%（250 笔）；61.9%（620 笔）是挂在“运费”或“燃油附加费”下面的子项，其中 564 笔是 purchased transportation。落下的是 66 笔扩展项（6.6%）和 3 笔“其他”（0.3%）。清单一笔“其他”也接不住。见第 3 节。
3. **推荐方案**：折中。以 Jake 的名称为根，只留用得到的 40 个条目，把我们的 6 个子项和 6 个扩展项挂上去并标明。不推荐把 234 个名称整表搬进来。见第 6 节。

判断依据三条，都来自下面的数字：

- 清单没有定义。整表为根时 234 个条目里 195 个的定义是空的（第 5 节）。
- 清单的名称不唯一对应 EDI 代码。234 个名称里 88 个有多个代码；我们对到的 39 个名称里 21 个有多个代码。只凭名称就能定出 EDI 代码的金额是 141 笔（14.1%）（第 3.3 节）。
- 清单多出来的 194 个名称在开发集里没有派上用场：没有被我们的代码用到，也没有接住“其他”里的任何写法（第 3.4 节、第 4 节）。

## 1. Jake 的清单整理成表（任务 2.1）

来源：`data/incoming/2026-11-13/carrier_addendum-b-accessorial-list_ada.pdf`（9 页，标题 Addenda B Accessorial List，两列：Description、EDI Code）。脚本 `scripts/s1_extract_addenda.py`。全表在 `data/interim/deliverables/T13/addenda_b_rows.csv`，按名称去重后的表在同目录 `addenda_b_names.csv`，抽取记录在 `extract_report.json`（都是 git 忽略）。

### 1.1 行数

| 项 | 数量 |
|---|---|
| 总行数（一行是一个名称加一个 EDI 代码） | 406 |
| 不重复的 EDI 代码 | 406（没有一个代码出现两次） |
| 其中纯数字代码 / 字母代码 | 89 / 317 |
| 不重复的名称 | 234 |
| 对应多个代码的名称 | 88（占了 260 行） |

名称按代码数分布：1 个代码 146 个名称，2 个 43，3 个 25，4 个 9，5 个 5，6 个 4，7 个 2。

代码数 4 个及以上的 20 个名称：HAZARDOUS MATERIALS CHARGE（7）、PICKUP/DELIVER SURCHARGE（7）、EXPEDITE SERVICE CHARGE（6）、HANDLING FEE（6）、INSURANCE-CARGO（6）、LABOR CHARGE（6）、FUEL SURCHARGE（5）、PICK UP CHARGE（5）、PROTECTIVE SERVICE HEAT/COLD（5）、SPECIAL/OTHER EQUIPMENT CHARGE（5）、TERMINAL HANDLING CHARGE（5）、ADDRESS/ACCOUNT CORRECTION（4）、ADVANCE ORIGIN AMOUNT（4）、BEYOND CHARGE（4）、BROKERAGE CUSTOM ENTRY FEE（4）、DELIVERY CHARGE（4）、EXPORT ENTRY（4）、RESIDENTIAL PU/DELIVERY CHARGE（4）、STOP OFF CHARGE（4）、VEHICHLE ORDERED NOT USED（4）。其余 68 个（3 个代码的 25 个、2 个代码的 43 个）的名称和代码数在 `extract_report.json` 的 `names_with_2plus_codes_detail`。任务书要求不整表照抄清单，所以这里没有全列。

### 1.2 抽取时的异常（只记录，原文没有修正）

| 类型 | 数量 | 说明 |
|---|---|---|
| 没有代码的行 | 0 | |
| 跨行的条目 | 4 行，2 个名称 | COMMERCIAL/CUSTOMS INVOICE: ADDITIONAL（3 行，名称在冒号后换行）；EQUIPMENT DETENTION ONLY - DESTINATION（1 行）。已按一个条目拼回。 |
| 明显的拼写问题 | 2 个名称 | VEHICHLE ORDERED NOT USED（4 行，应为 VEHICLE）；DEADHEAD MILAGE CHARGE（应为 MILEAGE）。 |
| 大小写不一致 | 1 个名称 | Freight（代码 400），整表只有它不是全大写。 |
| 标点和空格不规整 | 9 个名称 | 逗号或连字符前后缺空格或多空格，例如 `EQUIPMENT DETENTION ONLY -ORIGIN` 与 `EQUIPMENT DETENTION ONLY - DESTINATION` 写法不同。 |
| 名称末尾带着自己的代码 | 1 个名称 | IMPORT SECURITY FILING ISF，代码也是 ISF。 |

另外四点是肉眼看出来的，对后面的判断有影响：

- **写法不同、看起来是同一件事的名称各占一条**：DETENTION WITH POWER（3 个代码）和 DETENTION W/POWER（2 个代码）；PICK UP CHARGE 和 PICKUP/DELIVER SURCHARGE；DISTRIBUTION FEE 和 DISTRIBUTION SERVICE。清单没有定义，无法确认它们是不是同一项。
- **代码的字面有误导**：代码 `PST` 对应的是 POSTAGE CHARGE，省销售税的三个代码里有一个是 `TAX`；HST 的两个代码里有一个是 `REG`。所以不能凭代码字面去猜名称。
- **占位和专用条目**：OPEN-DO NOT USE（1 行）；CARRIER CREDIT (LGE ONLY)（1 行，看起来是某一家托运人专用）。
- **清单的范围比公路运输宽得多**：包含海运、空运、报关、墨西哥、押运等条目（数量见第 4 节）。清单里只有一条运费本体（Freight），没有“费率或重量更正”这一类。

## 2. 我们的代码对上去（任务 2.2）

以 `config/taxonomy.yaml`（版本 taxonomy-v0.1，37 个代码）为准。仓库里另有一份 `scratch/prototype/taxonomy.yaml`，只有第一行注释不同，代码内容相同。对应关系是人工按含义判断的，写在 `scripts/t13_mapping.py`；`s2_coverage.py` 会核对它恰好覆盖 37 个代码、用到的名称都真在清单里。

### 2.1 汇总

| 类型 | 代码数 |
|---|---|
| 完全对应 | 12 |
| 近似对应 | 5 |
| 一对多 | 8 |
| 只能作为子项 | 6 |
| 没有位置 | 6 |
| 合计 | 37 |

对应关系一共用到清单里 39 个名称；算上扩展项建议挂靠的上级，是 40 个。39 个里 18 个只有一个 EDI 代码，21 个有多个。

### 2.2 逐个代码

“开发集次数”是第 3 节口径下的金额笔数；一笔金额带两个代码时两边各记一次。“清单条目”后面括号里是这个名称名下的 EDI 代码数。

| 我们的代码 | 类型 | 清单条目（EDI 代码数） | 一句理由 | 开发集次数 |
|---|---|---|---|---|
| LINEHAUL.BASE | 完全对应 | Freight（1） | 清单里唯一的运费本体条目；另有海运、空运、入库运费三条，都不是公路运费本体。 | 2 |
| LINEHAUL.MINIMUM | 子项 | Freight（1） | 清单没有“最低收费”；最低收费是运费按下限计，属于运费的一种算法。 | 0 |
| FUEL.SURCHARGE | 完全对应 | FUEL SURCHARGE（5） | 名称和含义都一致；清单另有“紧急燃油附加”和“墨西哥燃油附加”，更窄，不用。 | 6 |
| RATE_CORRECTION.FUEL_TIER | 子项 | FUEL SURCHARGE（5） | 清单只列费用种类，不列“算错了”这种情形；这笔差额本身是燃油附加费，挂在它下面才能保留“费率档位更正”的含义。 | 45 |
| RATE_CORRECTION.BASE_RATE | 子项 | Freight（1） | 差额是运费本体的差额；清单没有“基础费率更正”。 | 5 |
| RATE_CORRECTION.WEIGHT | 子项 | Freight（1） | 按提单重量重算后的运费差额；清单的 WEIGHT INSPECTION 是复磅服务费，不是这个。 | 1 |
| RATE_CORRECTION.ZONE_FACTOR | 子项 | Freight（1） | 区域系数是运价的一部分；清单的 ARBITRARY CHARGE、BEYOND CHARGE 含义接近但不等同。 | 5 |
| RATE_CORRECTION.CONTRACT_GENERAL | 没有位置 | 无 | 文字只说“按合同价补差”，没说是哪一种费用；清单里没有能表示“未指明的合同价差额”的条目。 | 7 |
| ACCESSORIAL.LIFTGATE | 完全对应 | LIFT GATE CHARGE（1） | 同一项服务（数据里写作 TAILGATE）。 | 118 |
| ACCESSORIAL.INSIDE_DELIVERY | 完全对应 | INSIDE DELIVERY（2） | 名称和含义都一致。 | 29 |
| ACCESSORIAL.REDELIVERY | 完全对应 | REDELIVERY CHARGE（1） | 名称和含义都一致。 | 3 |
| ACCESSORIAL.SPECIAL_DELIVERY | 一对多 | SPECIAL SERVICES（3）；DELIVERY CHARGE（4）；PICKUP/DELIVER SURCHARGE（7） | 我们的定义本身就宽；清单里三个宽泛条目都能放，分不出哪个。 | 3 |
| ACCESSORIAL.APPOINTMENT | 近似对应 | ARRIVAL NOTIFICATION（3） | 清单没有“预约送货”字样；到货通知是送货前联系收货方，其中一个代码是 APT。差别：通知不等于约定时间。 | 0 |
| ACCESSORIAL.RESIDENTIAL | 近似对应 | RESIDENTIAL PU/DELIVERY CHARGE（4） | 同一项服务；清单条目同时包含住宅提货，略宽。 | 0 |
| ACCESSORIAL.LIMITED_ACCESS | 没有位置 | 无 | 清单没有“受限地点”，只有工地、展会两种具体地点的附加费，都比我们的定义窄。 | 0 |
| ACCESSORIAL.SORT_SEGREGATE | 完全对应 | SORT,SEGREGATE & STACKING CHG（1） | 名称和含义都一致（清单条目多含“码放”）。 | 9 |
| ACCESSORIAL.LUMPER | 完全对应 | LUMPER SERVICE(EXTRA HELPER)（1） | 名称一致；清单另有人工费、装卸费等条目，但只有这一条写明 LUMPER。 | 5 |
| ACCESSORIAL.HAZMAT | 完全对应 | HAZARDOUS MATERIALS CHARGE（7） | 名称和含义都一致；清单另有“危险品代收转付”，更窄，不用。 | 57 |
| ACCESSORIAL.PROTECT_FROM_FREEZE | 一对多 | PROTECTIVE SERVICE HEAT/COLD（5）；HEAT PROTECTION SERVICE（1） | 两个条目都指保温防冻，没有定义，分不出区别。 | 2 |
| ACCESSORIAL.REWEIGH | 一对多 | WEIGHT INSPECTION（3）；INSPECTION FEE（1） | 我们的定义把复磅和检验合在一起；清单分成两条。 | 0 |
| ACCESSORIAL.TRUCK_ORDERED_NOT_USED | 完全对应 | VEHICHLE ORDERED NOT USED（4） | 同一项费用（清单原文拼写如此）。 | 1 |
| ACCESSORIAL.IN_BOND | 完全对应 | BOND CHARGES（1） | 名称和含义都一致，数据里的写法与清单名称相同。 | 1 |
| ACCESSORIAL.ROAD_CLOSURE | 没有位置 | 无 | 清单没有“道路封闭绕行”。 | 49 |
| DETENTION_STORAGE.DRIVER_DETENTION | 一对多 | DETENTION WITH POWER（3）；DETENTION W/POWER（2）；DETENTION: LOADING（1）；DETENTION: UNLOADING（1）；DETENTION-AFTER 4 HRS（1）；WAITING TIME（1） | 清单把司机带车等待拆成六个名称；数据里多数只写 DRIVER DETENTION，分不到某一个。 | 38 |
| DETENTION_STORAGE.EQUIPMENT_DETENTION | 一对多 | DETENTION W/O POWER（1）；EQUIPMENT DETENTION ONLY -ORIGIN（1）；EQUIPMENT DETENTION ONLY - DESTINATION（1） | 清单按不带动力、起运地、目的地分成三条；数据里只写 EQUIPMENT DETENTION。 | 5 |
| DETENTION_STORAGE.TERMINAL_STORAGE | 近似对应 | STORAGE FEES（2） | 清单条目是一般的仓储费，没有限定在场站或铁路坡道，比我们的定义宽。 | 14 |
| DETENTION_STORAGE.CONTAINER_PER_DIEM | 一对多 | DEMURRAGE CHARGE（3）；EQUIPMENT DETENTION ONLY -ORIGIN（1）；EQUIPMENT DETENTION ONLY - DESTINATION（1） | 清单没有 PER DIEM 字样；滞期费和设备滞留费都接近。数据写法分起运地和目的地，与设备滞留的两条对得上。 | 11 |
| DETENTION_STORAGE.DWELL | 没有位置 | 无 | 清单没有 DWELL；这个词不是标准叫法，含义还没有向客户确认。 | 7 |
| DRAYAGE.CHASSIS | 近似对应 | CHASSIS / BOGIE OR AXLE CHG（1） | 清单条目把底盘车、转向架、车轴合成一条，略宽。 | 2 |
| DRAYAGE.PORT_FEE | 一对多 | PIER CHARGES（2）；TERMINAL HANDLING CHARGE（5）；WHARFAGE（3） | 港口端的费用清单里有三条，都没有定义；“拥堵费”没有任何条目写明。 | 4 |
| DRAYAGE.PRE_PULL | 近似对应 | SWITCHING/PULLING/RE-POSITIONING CHG（2） | 预提是把箱子先拉到堆场；清单条目是调车、拖移、重新摆位的合称，更宽。 | 3 |
| TAX.GST | 完全对应 | GST - GOODS & SERVICE TAX（1） | 同一税种。 | 10 |
| TAX.HST | 完全对应 | HST - HARMONIZED SALES TAX（2） | 同一税种。 | 0 |
| TAX.PST | 一对多 | STATE/PROVINCIAL SALES TAX (PST)（3）；QST - QUEBEC SALES TAX（1） | 我们把 QST 并在 PST 里，清单分成两条。按文字写的是 PST 还是 QST 就能分开，属于可以消除的一对多。 | 0 |
| TAX.UNSPECIFIED | 没有位置 | 无 | 清单只有具体税种；“没说是哪种税”是读不出税种时的标记，不是一种费用。 | 3 |
| PENDING.PURCHASED_TRANSPORTATION | 子项 | Freight（1） | 已定：作为运费的子项。清单里的 THIRD PARTY FEE、CARTAGE CHARGE 字面接近，但没有定义可以佐证。 | 564 |
| OTHER | 没有位置 | 无 | 兜底类，不是一种费用；清单没有兜底条目。 | 3 |

开发集里一次都没出现的代码有 7 个：LINEHAUL.MINIMUM、APPOINTMENT、RESIDENTIAL、LIMITED_ACCESS、REWEIGH、TAX.HST、TAX.PST。

### 2.3 “没有位置”的 6 个代码：挂到哪里

| 代码 | 建议 | 说明 |
|---|---|---|
| RATE_CORRECTION.CONTRACT_GENERAL | 挂在 Freight 下面，标明非清单原有 | “合同价”多数指运价，但文字没有明说，所以是扩展项而不是子项。 |
| ACCESSORIAL.LIMITED_ACCESS | 挂在 PICKUP/DELIVER SURCHARGE 下面，标明非清单原有 | 这是清单里最宽的提送货附加费条目。开发集里没有出现，优先级低。 |
| ACCESSORIAL.ROAD_CLOSURE | 挂在 EXCESS MILES 下面，标明非清单原有；**需要问 Jake** | 按我们的定义（绕行产生的附加费）最近的是超额里程。如果起因是天灾，也可能是 WEATHER DISASTER SURCHARGE。这是最大的一个扩展项（49 笔），值得问清楚。 |
| DETENTION_STORAGE.DWELL | 挂在 DEMURRAGE CHARGE 下面，标明非清单原有；**需要问 Jake** | 按天计、箱子超期，最近的是滞期费。DWELL 的含义本来就没有确认过。 |
| TAX.UNSPECIFIED | 哪里都不挂，放在顶层 | 挂到任何一个具体税种下面都等于替承运商认定了税种。 |
| OTHER | 哪里都不挂，放在顶层 | 兜底类必须保留，并继续要求写出原文短语。 |

## 3. 用数据量覆盖（任务 2.3）

脚本 `scripts/s2_coverage.py`。明细在 `data/interim/deliverables/T13/coverage_detail.csv`，汇总数字在同目录 `coverage.json`。

### 3.1 口径

- **读法版本**：开发集全量 `20261110-195411-devFull-4823`（2026-11-10 运行，953 行，taxonomy-v0.1，SKILL.md 哈希 `84dddc8a6921`）。这是仓库里唯一一次开发集全量。它跑在调优之前；之后 SKILL.md 调到了 v1.2（哈希 `b4d3f0f74fd3`），但只在 A、B2 两个样本和 mock 上跑过，没有再跑全量。
- **单位**：一条不同的说明（票货、Event Date、文字都相同算一条）里的一笔被计入的金额。“被计入”沿用 T12 的规则：读法把这个数标为 CLAIMED 或 UNPAID，且种类是费用金额、未指明金额或税额。
- **数量**：953 行合成 908 条不同的说明；907 条通过检查（1 条没通过，不计）；902 条里有被计入的金额，共 1045 笔。其中 **1002 笔带费用代码**，43 笔文字里没有写费用名（见 3.5）。下面的百分比以 1002 为分母。
- **一笔金额带两个代码**（如“A 和 B 合计 x 元”）有 10 笔，拆不开，按两个代码里较弱的一类计。
- **金额**：取绝对值；加元和美元没有换算，直接相加，只用来看占比。分币种的数在 `coverage.json`。

### 3.2 五类

| 类别 | 次数 | 次数占比 | 金额 | 金额占比 |
|---|---|---|---|---|
| 1. 完全对应或近似对应 | 250 | 24.9% | 26,148.92 | 38.2% |
| 2. 一对多（有位置但不唯一） | 63 | 6.3% | 8,237.49 | 12.0% |
| 3. 子项（挂在清单条目下面） | 620 | 61.9% | 30,082.81 | 43.9% |
| 4. 扩展项（清单里没有位置） | 66 | 6.6% | 4,014.20 | 5.9% |
| 5. 现在就归在“其他”里 | 3 | 0.3% | 42.00 | 0.1% |
| 合计 | 1002 | 100% | 68,525.42 | 100% |

- 第 1 到 3 类合计 933 笔（93.1%），金额 64,469.22（94.1%）：这是“落在清单之内”的部分。
- 第 3 类 620 笔的构成：purchased transportation 564 笔（含 4 笔与尾板或室内送货合并的金额），燃油档位更正 45 笔，基础费率更正 5 笔，区域系数 5 笔，重量更正 1 笔。
- 第 4 类 66 笔的构成：道路封闭 49 笔（含 1 笔与尾板合并的金额），合同价差额 7 笔，DWELL 7 笔，税种未指明 3 笔。
- 第 2 类 63 笔的构成：司机滞留 38，箱子按天收费 11，设备滞留 5，港口费 4，特殊送货 3，防冻 2。

**去掉 purchased transportation 之后**（剩 438 笔，金额 42,345.39）：第 1 类 250 笔（57.1%，金额 61.8%），第 2 类 63 笔（14.4%，19.5%），第 3 类 56 笔（12.8%，9.2%），第 4 类 66 笔（15.1%，9.5%），第 5 类 3 笔（0.7%，0.1%）。

### 3.3 名称对上了，EDI 代码定不下来

清单的一个名称常常有多个 EDI 代码，清单没说它们的区别。

- 第 1 类 250 笔里，落在“只有一个 EDI 代码的名称”上的是 141 笔（金额 9,955.62），占 1002 笔的 14.1%。主要是尾板（LIFT GATE CHARGE，1 个代码）。
- 其余 109 笔落在有多个代码的名称上，例如危险品 57 笔对的是有 7 个代码的名称，室内送货 28 笔对的是有 2 个代码的名称。
- 如果子项沿用上级的代码：Freight 只有一个代码（400），它名下的 575 笔子项就能定下来；合计 716 笔（71.5%）。

所以无论选哪个方案，“输出哪一个 EDI 代码”都要 Jake 给规则，或者输出全部候选代码。

### 3.4 “其他”里有什么，清单能接住多少

“其他”一共 3 笔，2 种不重复的写法：

| 写法 | 次数 | 金额 | 清单里合适的条目 | 理由 |
|---|---|---|---|---|
| CV19 FEE（含写成 CV 19 FEE 的 1 笔） | 2 | 30.00 | 没有 | 疫情附加费。COST RECOVERY ADJUSTMENT、REGULATORY FEE 字面上沾边，但没有定义，硬放等于换个名字的“其他”。 |
| RESERVATION FEE | 1 | 12.00 | 没有 | 预订费。清单里没有预订或订舱费；PREMIUM SERVICE UPGRADE、SPECIAL SERVICES 都不是这个意思。 |

**汇总：Jake 的清单能把“其他”吸收掉 0 笔（0 / 3）。** “其他”在开发集里本来就只占 0.3%，这里没有可以改善的空间。

### 3.5 分母之外：43 笔没有费用名的金额

43 笔被计入的金额（金额 43,688.26）在文字里没有写是什么费用（例如只写一个差额或余额）。它们没有代码，换任何代码表都放不进去，所以没有算进上面的五类。这不是代码表的问题，但金额不小，单独列在这里。

## 4. 反过来看 Jake 的清单（任务 2.4）

清单 234 个名称里，第 2、3 节用到 40 个（其中 32 个在开发集里有金额落上去），没有用到的 194 个。粗分两组（分组是人工做的，文件在 `data/interim/deliverables/T13/unused_irrelevant_names.txt`，结果在同目录 `unused_names.csv`）：

| 组 | 名称数 | 名下 EDI 行数 |
|---|---|---|
| 用到的 | 40 | 94 |
| 没用到，明显与这批数据无关 | 66 | 93 |
| 没用到，公路整车和零担可能用得上 | 128 | 219 |
| 合计 | 234 | 406 |

第一组 66 个的构成：报关、进出口单证和贸易融资 23，海运 11，押运和安保类保护服务 10，空运 8，墨西哥 7，办公杂费、占位和专用条目 7。

第二组 128 个。任务书要求列出名称，同时要求提交的文件不整表照抄清单；128 个加上已经出现的 39 个就是清单的七成，所以这里只列与这批数据的运输方式最接近的 34 个，**完整的 128 个在 `unused_names.csv`（`group` 列为 `ROAD_POSSIBLE`）**：

- 提送货时间和地点：AFTER HOURS PICKUP OR DELIVERY、SATURDAY DELIVERY/PICKUP、SUNDAY/HOLIDAY PICKUP/DELIVERY、CONSTRUCTION SITE SURCHARGE、TRADE SHOW/CONVENTION SURCHARGE、INSIDE PICKUP CHARGE、HOLDING CHARGE/DELAYED DELIVERY。
- 路线和里程：STOP OFF CHARGE、RECONSIGNMENT CHARGE、DIVERSION CHARGE、DEADHEAD MILAGE CHARGE、EMPTY MOVEMENT CHARGE、RETURNED LOAD、BORDER CROSSING FEE、INTERSTATE/HIGHWAY TOLL、WEATHER DISASTER SURCHARGE。
- 时效和司机：EXPEDITE SERVICE CHARGE、TEAM DRIVER、LAYOVER WEEKNIGHT CHARGE、LAYOVER WEEKEND CHARGE。
- 装卸和人工：DRIVER ASSIST LOAD/UNLOAD、LABOR CHARGE、PALLET CHARGE。
- 货物和设备：OVER DIMENSION、OVERWEIGHT CHARGE、PERMIT CHARGE、TARPING CHARGE。
- 多式联运：DRAYAGE SERVICE、RAMPING CHARGE、DERAMPING CHARGE、TOFC SERVICE CHARGE。
- 计价：GRI - GENERAL RATE INCREASE、SINGLE SHIPMENT CHARGE、THIRD PARTY FEE。

其余 94 个多数是特种设备（各类挂车、罐车作业）和零星服务。

## 5. “Jake 的清单加定义”草稿（任务 2.5）

判断：覆盖够好（93.1% 落在清单之内），所以做了完整草稿，没有只做骨架。脚本 `scripts/s3_draft.py`。草稿在 `data/interim/deliverables/T13/jake_rooted_draft.csv`（同内容的表格版 `jake_rooted_draft.md`），不替换 `taxonomy.yaml`。

| 项 | 数量 |
|---|---|
| 总行数 | 246 |
| 清单原有条目（根） | 234 |
| 子项（挂在 Freight 或 FUEL SURCHARGE 下面） | 6 |
| 扩展项（标明非清单原有） | 6（4 个有挂靠的上级，2 个放在顶层） |
| 清单条目里带上了定义的 | 39 |
| 清单条目里定义为空的 | 195 |
| 由 CC 起草定义的 | 0 |

- 每行有：角色、名称、挂在哪个条目下面、名下全部 EDI 代码、对应的我们的代码、关系类型、定义、定义来源、写法示例、相关度、开发集次数。
- 定义和写法示例都从我们的单子带过来。一对多的 8 个代码，定义同时出现在每一个候选条目上，并在“定义来源”里注明需要拆细。
- CC 起草的定义是 0 条：任务书只允许给“接住了‘其他’里写法”的清单独有条目起草定义，而 3.4 的结果是没有这样的条目。
- 相关度四档的数量：被我们的代码用到 40（其中 1 个 EXCESS MILES 只是扩展项的上级）；接住了“其他”里的写法 0；公路运输可能用得上 128；与这批数据无关 66。

## 6. 方案（任务 2.6）

花费估计的依据是账本里同样规模的运行：样本 A 0.89 美元，样本 B2 0.82 美元，公开 mock 3.84 美元，开发集全量 7.67 美元。账本累计 71.67 美元，上限 110，余 38.33。

### 方案一：保留我们的单子，补上 EDI 对照

- **提示词和代码表**：提示词不变。`taxonomy.yaml` 里现在留空的 `x12_ref` 一栏换成“清单名称和 EDI 代码”，按第 2 节的表填。输出里多两列参考信息。
- **重跑**：不需要。对照是代码里的确定性换算，用留存读法重放即可，花费 0。
- **风险**：输出的主语仍是我们的代码，Jake 看到的不是他的单子。8 个一对多的代码只能给出候选（63 笔，6.3%）。

### 方案二：以 Jake 的清单为根，整表搬进来

- **提示词和代码表**：代码表从 37 行变成 246 行（234 个清单条目、6 个子项、6 个扩展项），模型直接在清单名称里选。
- **重跑**：全部。A、B2、mock 约 7 到 8 美元（提示词变长，按现有 5.55 美元的 1.3 到 1.5 倍估），开发集全量约 10 到 12 美元。mock 期望、测试、合成例子里的代码都要改写；已交回的标注用的是我们的代码，也要换算。
- **风险**：195 个条目没有定义，模型只能看名字猜。名字相近的条目很多（司机滞留有 6 个名称，提送货类有 PICK UP CHARGE、PICKUP/DELIVER SURCHARGE、DELIVERY CHARGE 三个），同一句话两次运行可能落到不同名称上，一致性会下降。多出来的 194 个名称在开发集里没有任何收益（没有被用到，接住“其他”0 笔）。EDI 代码仍然定不下来。

### 方案三（推荐）：以 Jake 的名称为根，只留相关条目，把我们的子项和扩展项挂上去

- **提示词和代码表**：代码表变成 52 行：40 个清单条目作为根（用 Jake 的名称，带名下全部 EDI 代码，定义和写法示例用我们的），6 个子项挂在 Freight 和 FUEL SURCHARGE 下面，6 个扩展项标明非清单原有。我们现在的代码保留为内部编号，这样 mock 期望、测试和标注不用改写。128 个“公路可能用得上”的名称放进一张备用表，不进提示词；“其他”里出现能对上的写法时再提升进来。
- **一对多的 8 个代码**：文字能分的拆开（PST 和 QST；起运地和目的地的设备滞留和按天收费；装货和卸货的滞留）。文字分不了的（只写 DRIVER DETENTION）需要 Jake 指定一个默认名称，在那之前输出候选名称。
- **重跑**：分两步。第一步不调模型：把对照关系做成确定性换算，在留存读法上重放，立刻得到以 Jake 名称为根的输出，花费 0。第二步改提示词里的代码表，需要重跑 A、B2、mock（约 5.6 美元），通过后重跑开发集全量（约 7.7 美元），合计约 13.3 美元。
- **风险**：根的名称换了以后，模型的读法可能有小幅变化，要用第二步验证。Jake 可能希望看到整张清单；备用表保留了这条退路。拆细一对多的代码会改动现有的代码边界，要同步改 mock 期望。

### 为什么推荐方案三

判断口径是“没有明显差别时用 Jake 的清单”。

- 和我们的单子比：方案三的根就是 Jake 的名称，覆盖与我们的单子相同（对应关系覆盖全部 37 个代码），所以没有理由保留我们的单子做根。方案一因此不选。
- 和整表比：整表有三处明显不如（195 个空定义，88 个名称的 EDI 代码不唯一，194 个名称在开发集里没有收益），而且清单自身表达不了占 61.9% 的子项。所以不能只用清单，也没有必要把整表放进提示词。方案二因此不选。

### 下一步怎么用模型验证（这一轮不跑）

1. **不调模型的一步**：实现对照换算，在 `devFull-4823` 上重放，必须复现第 3.2 节的五类数字（250 / 63 / 620 / 66 / 3）。花费 0。
2. **门槛先写定**：用第二段留存的重复运行结果（同一提示词跑三遍的 mock）算出“同一句话两次运行落到同一个根”的比例，作为噪声基线；门槛定为新代码表的一致率不低于这个基线，写进卡片的完成标准之后再跑。
3. **对比运行**：新代码表（52 行）跑样本 A（100 条）、样本 B2（100 条）、公开 mock（375 条），与现有最终版本 `rdAallowlist-49dd`、`rdBallowlist-a1fa`、`finalMock-1ba4` 比。新旧读法都折算到 Jake 的根上再比。看四个数：每笔金额的根是否一致；mock 通过数不低于现有；三种颜色的分布变化在噪声之内；“其他”的笔数不增加。预计 5.6 美元。
4. **通过后**：重跑开发集全量一次，更新第 3 节的数字。预计 7.7 美元。
5. 不碰测试集和预留 mock。

## 7. 需要 Zizhang 定或者去问 Jake 的事

1. 选方案：建议方案三，先做不调模型的第一步。
2. 费率和重量更正（4 个代码，56 笔）按 purchased transportation 的做法作为子项挂在 Freight 和 FUEL SURCHARGE 下面：建议同意。
3. 问 Jake：一个名称有多个 EDI 代码时用哪一个（我们用到的 39 个名称里 21 个是这种情况）。没有答复之前输出全部候选代码。
4. 问 Jake：道路封闭附加费（49 笔）算 EXCESS MILES、WEATHER DISASTER SURCHARGE，还是清单之外的一项。
5. 问 Jake：只写“司机滞留”“设备滞留”“PER DIEM”“DWELL”时，各自用清单里的哪个名称。
6. 128 个“公路可能用得上”的名称不进提示词、只放备用表：建议同意。
7. 本报告没有把清单的 88 个多代码名称和 128 个第二组名称全部列出（原因见 1.1 和第 4 节）。需要全列在提交的文件里的话，说一声即可。

## 8. 文件和复现

| 内容 | 路径 |
|---|---|
| 抽取脚本 | `scripts/s1_extract_addenda.py`（需要 pdfplumber，用 `uv run --with pdfplumber` 临时带上，没有改 `pyproject.toml`） |
| 对应关系 | `scripts/t13_mapping.py` |
| 覆盖统计 | `scripts/s2_coverage.py` |
| 草稿生成 | `scripts/s3_draft.py` |
| 清单全表、去重表、抽取记录 | `data/interim/deliverables/T13/addenda_b_rows.csv`、`addenda_b_names.csv`、`extract_report.json` |
| 覆盖明细和汇总 | `data/interim/deliverables/T13/coverage_detail.csv`、`coverage.json` |
| 没用到的名称及分组 | `data/interim/deliverables/T13/unused_names.csv`（人工分组的输入是 `unused_irrelevant_names.txt`） |
| 清单草稿 | `data/interim/deliverables/T13/jake_rooted_draft.csv`、`jake_rooted_draft.md`、`draft_summary.json` |

`data/interim/` 下的文件都被 git 忽略。三个脚本按 s1、s2、s3 的顺序运行。

局限：对应关系和第二组的分组是一个人（CC）按名称的字面和行业常识判断的，清单没有定义可以核对；没有用模型，也没有用人工标注复核。覆盖数字依赖一次留存读法（调优之前的 SKILL.md），读法本身的对错不在本轮范围内。

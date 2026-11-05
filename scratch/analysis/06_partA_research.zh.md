## 第 A 部分 行业资料调研（公开来源）

> 调研日期：2026-11-04。只用公开网页；检索词只用通用行业术语，没有使用任何客户数据（承运商名、地址、金额、原文、内部 ID、客户公司名）。
> 可信度分四档：**行业标准文件**（X12、OASIS UBL、NMFTA、政府税务/能源机构）/ **厂商文档**（软件厂商、承运商公开文件）/ **行业文章**（审计服务商、物流公司博客）/ **论坛**（社区问答、个人开源仓库）。
> 标"（摘要）"的来源只通过搜索引擎摘要读过，没有抓取全文，引用时降一档使用。凡是 X12/OTM 代码，只列在抓取页面上实际看到的；没看到的标"未核实"。
> 本部分只讨论**某一类费用通常靠什么证据核实**，不涉及任何单笔费用是否应付。

---

### A1 审核员确认每一类费用时看什么

**读法**：每类一行。"行业通常要求的证据"来自所引来源；"可能出现在承运商自由文本中的要素"是我们的推断（没有来源专门研究过承运商解释文本里写什么），用来指导抽取字段的设计。代码列只放已核实的 X12 004010 元素 150（L1-08）代码 [7]，以及 project44 代码 [22]。

#### A1.1 司机/车辆等待（driver detention）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 预约时间；到达/签到时间；免费等待时间（free time）到期时刻；装卸开始与结束时间；放行/离开时间；BOL 或 POD 上签字的进出时间；运价确认单里约定的免费时长、每小时费率、计费增量、上限，以及"免费时间到期前须通知"之类条款；可选 ELD/GPS/地理围栏记录 [32][34] |
| 补充 | ELD/轨迹数据能证明到达和离开，但单独不能证明预约时间、延误原因或可计费区间 [32]。免费时间常见 2 小时，但没有联邦规定，以合同为准 [34]（摘要） |
| 文本中可能出现的要素 | 到达/离开时刻、等待总时长、免费时长、可计费小时数、每小时费率、计费增量（如 15/30/60 分钟）、地点（起运地/目的地）、预约号或签到号、"已通知"时间 |
| 可核对的算术关系 | (离开 − 到达 − 免费时长) × 费率 ≈ 金额；按增量取整 |
| 已核实代码 | X12：DET "Detention of Trailers"、DTL "Detention Loading"、DTU "Detention Unloading"、TDT "Truck Detention"、SDC "Special Detention Charge"、WTG "Waiting Time" [7]；EDI2XML 另列 DPU（30 分钟计）、DWP（60 分钟计）、DETO/DETD（起运地/目的地）[9]，在 Stedi 4010 页面上未逐一核对；project44：DET "Detention"（Charge Code）[22] |
| 时间戳的标准来源 | EDI 214 AT7 状态码：X3 到达提货点、X1 到达交货点、CP 提货点装完、D1 交货点卸完、AF 带货离开提货点、CD 离开交货点 [6]；G62 日期限定符如 77/78 提/送货预约日、86 实际提货日、35 送达日 [5] |

#### A1.2 装卸工费（lumper / unloading labor）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | **装卸收据**是核心，没有收据通常不报销；收据应显示场站名称、日期、拖车号、服务方、金额，并随 POD 一起提交；也有要求 BOL 上注明 [35]（摘要） |
| 文本中可能出现的要素 | 收据号/票据号、装卸服务方名称（需脱敏）、金额、日期、托盘数或件数、"代垫/pass-through"字样 |
| 可核对的算术关系 | 收据金额 = 账单金额（代垫类通常不加价，是否加管理费看合同） |
| 已核实代码 | X12 4010：LOA "Loading (Labor Charges)"、UNL "Unloading (Labor Charges)" [7]；没有核实到名称含 "lumper" 的 X12 代码（EDI2XML 把 LOA 写成 "...or Lumper Free"，与 Stedi 不一致 [9]）；project44：LUMPER "Lumper Service" [22] |

#### A1.3 车辆已派未用（TONU / dry run / truck ordered not used）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 书面取消通知及其时间；合同里的取消时限（样例条款有提货前 2/4/6 小时）；派车时间；到场证明（GPS 时间戳、照片）；运价确认单中的 TONU 条款（金额、触发条件、所需证明）[33]（全文）；行业摘要还提到司机书面说明、拒收通知 |
| 文本中可能出现的要素 | 取消时刻、原定提货时刻、两者间隔、取消方、原因（货未备好、场站关闭、设备不符）、空驶里程、是否已到场 |
| 可核对的算术关系 | 原定提货时间 − 取消时间 < 合同时限；若按里程补偿，里程 × 单价 |
| 已核实代码 | X12：VOR "Vehicle Ordered but Not Used"、CAA "Cancellation Charge" [7]；EDI2XML 另列 WFT "Wasted/Futile Trip"、ATP "Attempted Pickup" [9]；"dry run" 没有对应代码 |

#### A1.4 过夜滞留（layover）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 原预约与改期确认、拒收或延误记录、到场尝试记录、沟通记录；运价确认单中的日费率和触发条件（样例：超出预约 24 小时后按日计）[36]（摘要） |
| 和 detention 的区别 | detention 按**小时**，layover 按**天**；同一票货可以两者都有 [36]（摘要）。审核时要防止同一段时间被两类重复计费 |
| 文本中可能出现的要素 | 原定日期、实际装/卸日期、天数、日费率、改期原因 |
| 已核实代码 | X12：LAY "Layover Charges"、LYC "Layover Service Charge" [7] |

#### A1.5 改址/改收货人（reconsignment / diversion / redirect）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 托运方或收货方发出的改址指令（时间、发起人）；新旧目的地；BOL 变更记录。行业文章称改址费通常分两部分：改单的管理费 + 若不在原站点交货而产生的额外运输费，可能另有标记/贴签费 [37]（摘要） |
| 文本中可能出现的要素 | 新旧收货地（城市/省）、指令日期、额外里程、管理费与运费两段金额 |
| 可核对的算术关系 | 总额 = 管理费 + 追加运费；追加运费 = 里程 × 费率 |
| 已核实代码 | X12：RCC "Reconsignment Charge"、DIV "Diversion and Reconsignment" [7]；EDI2XML 另列 DIC、RCD、RDC [9]；project44：RECON "Reconsignment Fee" [22] |

#### A1.6 燃油附加费（fuel surcharge, FSC）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 合同指定的燃油指数来源（美国 EIA 周度柴油价，全国或 PADD 分区）；**取哪一周**的规则（如"提货日当天或之前的周一"）；基准价（peg，附加费为 0 的价格）；整车按里程公式时的 MPG；LTL 用的分档表及其版本和生效日；里程（以运价确认单为准）；LTL 的计费基数（折后干线运费，是否含杂费）；取整规则 [30] |
| 常见差错（类别层面） | 用了发票日而不是提货日对应的周；全国价和分区价混用；用了承运商新表而不是合同版本；里程多于运价确认单；百分比套在毛运费或合同排除的杂费上；在单独通知里重复收取 [30] |
| 指数事实 | EIA 每周发布美国公路柴油价（含税），有全国和 PADD1–5 等分区 [29]。加拿大合同多参考加拿大自然资源部（NRCan）周度零售柴油均价 [49]（摘要）；NRCan 官方页面未抓到，发布日、城市数**未核实** |
| 文本中可能出现的要素 | 指数周/日期、指数价格（$/gal 或 ¢/L）、基准价、附加费率（%或每英里/公里）、计费基数金额、里程/公里数、表版本 |
| 可核对的算术关系 | 整车：(指数 − 基准价) ÷ MPG × 里程；LTL：基数 × 分档百分比 |
| 已核实代码 | X12 4010 与 8010：405 "Fuel Surcharge"、FUE "Fuel Charge" [7][8]。**FSC 在 Stedi 的 4010 和 8010 元素 150 列表中都不存在** [7][8]，EDI2XML 列有 FSC "Fuel Surcharge" [9]，可能是某些伙伴的扩展用法，应视为非标准。project44：FSC "Fuel Surcharge"（Charge Code）[22] |

#### A1.7 尾板（liftgate）及同类交付条件费（住宅、受限地点、室内交付、预约）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | BOL 或交货回单上要能体现该条件；尾板费在交货回单显示收货方无月台时才成立；住宅费在 BOL 收货地址为商业地址时不成立 [31] |
| 文本中可能出现的要素 | 交付条件描述（无月台、住宅、学校/工地等受限地点、室内/楼层）、提货端还是交货端、次数、预约号 |
| 已核实代码 | X12：LFT "Lift Gate (Truck) or Forklift Service at Pick-up/Delivery"、IDL "Inside Delivery"、RES "Residential Delivery"、APT "Appointment (Notification)" [7]；受限地点在 X12 列表中**未找到**对应 [9]；project44：LGPU/LGDEL、INDEL、RESPU/RESDEL、LTDPU/LTDDEL、APPTPU/APPT/APPTDEL、NOTIFY [22] |

#### A1.8 再次派送（redelivery）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据 | 首次派送尝试的记录（时间、未能交货原因）、收货方通知记录、再次派送的请求。某 LTL 承运商规则费率表规定：派送被拒后再收到请求的，按再派送条款计费 [39]（摘要）。公开来源**没有**明确列出"派送尝试"要保留哪些证明，这一点未核实 |
| 文本中可能出现的要素 | 首次尝试日期/时间、失败原因（关门、拒收、无预约、缺设备）、再派送日期、按重量计费的费率（如每百磅）与最低收费 |
| 已核实代码 | X12：RCL "Redelivery" [7]；EDI2XML 另列 ATD "Attempted Delivery" [9]（Stedi 4010 页面上未见）；EDI 214 AT7：AH "Attempted Delivery"、A7 "Refused by Consignee" [6]；project44：CREDEL "Redeliver to Consignee" [22] |
| 注意 | NMFTA 的 PFC 事件码里也出现 "RCL"[23]，页面未定义其含义；同一字母组合在不同标准中可能含义不同，代码必须带"代码体系"字段 |

#### A1.9 仓储/堆存（terminal storage）与集装箱/设备滞留（per diem）

| 项目 | 内容 |
|---|---|
| 行业通常要求的证据（LTL 场站仓储） | 到货通知时间（或首次派送尝试时间）；免费期（承运商费率表例：通知后次一工作日起计；或首 24 小时免费）；计费天数；按天/按托盘/按重量的费率 [39]（摘要） |
| 行业通常要求的证据（海运集装箱滞留，若遇到） | 美国 FMC 规则 46 CFR 541.6 要求账单列出免费天数及起止日、可提箱日或最早还箱日、具体计费日期、提单号和箱号等 [摘要，未抓取法规原文，**未核实**] |
| 文本中可能出现的要素 | 到货/通知日期、免费天数、计费天数、日费率、托盘数、箱号/拖车号 |
| 可核对的算术关系 | (结束日 − 开始日 − 免费天数) × 日费率 × 单位数 |
| 已核实代码 | X12：SRG "Storage"、STR "Storage in Transit"、CHE "Chassis Equipment Lease Charge" [7]；EDI2XML 另列 ISO/IST 联运堆存 [9]；X12 和 project44 都没有找到 per diem 的专门代码；project44：STORAGE "Storage"（Charge Code）[22] |

#### A1.10 运价/重量更正（rate correction：基础费率、重量、燃油档、区域系数、合同）

| 项目 | 内容 |
|---|---|
| 重量更正的证据 | 承运商出具的**重量/检验证书**（W&I），列实测重量/尺寸、更正后等级、所引 NMFC 条目，常附照片 [40]（摘要）；对比 BOL 申报重量；托运方反证通常是经认证的地磅票 [31] |
| 等级更正的证据 | BOL 原申报等级、商品描述、密度计算；合同常要求承运商提供带照片和密度测量的书面检验证书 [31] |
| 费率更正的证据 | 合同/运价协议（MRA）或运价确认单中的费率、生效日、最低收费条款 [31]；OTM 里对应"关税/合同引用"字段（Tariff Reference Number、Tariff Effective Date 等）[10] |
| 文本中可能出现的要素 | 原重量与新重量、原等级与新等级、原费率与新费率、证书号、NMFC 条目号、合同号/报价号、生效日 |
| 可核对的算术关系 | 差额 = (新费率 × 新计费量) − (原费率 × 原计费量)；燃油随基数变化联动 |
| 已核实代码 | X12：WTV "Weight Verification Charge"、SCL "Scale Charge"、MIC "Minimum Charge"、DSC "Discount" [7]；没有找到名为 "reweigh" 的 X12 代码 [9]；project44：WINSPC "Weight Inspection" [22]；NMFTA PFC 事件码 RWE（页面未定义，推测为 reweigh，**未核实**）[23] |

#### A1.11 加拿大运输税（GST/HST/PST/QST）

| 项目 | 内容 |
|---|---|
| 规则要点 | 国内货运服务的供应地按**目的地**定："a supply of a freight transportation service is made in a province if the destination of the service is in the province" [42]；目的地在 HST 参与省（新不伦瑞克、纽芬兰与拉布拉多、新斯科舍、安大略、爱德华王子岛）按该省 HST，其余省份/地区 5% GST [41]；连续入境/出境货运和联运承运商之间的服务通常零税率，需托运方声明等书面证据 [41] |
| QST | Revenu Québec：目的地在魁北克的货运服务一般视为在魁北克供应；从加拿大其他省运入魁北克的视为在魁北克以外供应，不收 QST（由魁北克居民自行计税）[43]（摘要，官方页面抓取返回 403） |
| 证据 | 起运地、目的地（省）、是否连续国际货运的一部分、承运商税号；CRA 页面**没有**说明发票必须列哪些字段，未核实 [41] |
| 文本中可能出现的要素 | 税种名、税率、计税基数、税额、省份缩写 |
| 可核对的算术关系 | 税额 ≈ 税基 × 税率；税率与目的地省份一致；税基是否包含燃油和杂费 |
| 已核实代码 | X12 4010：GST "Goods and Services Tax Charge"、TAX "Tax Charge"；HST、PTX 在 4010 中**不存在** [7]；X12 8010：HST "Harmonized Sales Tax"、PTX "Provincial Sales Tax"、QST "Quebec Sales Tax" [8]。OTM 行项目有 VAT 区，说明可用于加拿大省级税 [10] |

#### A1.12 其余类别（证据资料较少）

| 类别 | 已知证据要点 | 已核实代码 | 状态 |
|---|---|---|---|
| 干线基础费、最低收费 | 合同费率、最低收费条款、BOL [31] | MIC、DSC [7] | 部分核实 |
| 危险品 | 危险品申报（BOL 上的危险品信息）；EDI 210 有 H1/H2 危险品段 [1] | HAZ [7]；project44 HAZM [22] | 证据要求未核实 |
| 防冻 | 无公开证据要求 | PSC "Protective Service - Cold"、DFD [7]；project44 PFZ [22] | 未核实 |
| 分拣/分隔 | 无公开证据要求 | SEG "Segregating (Sorting)" [7]；project44 SORTPU/SORTDEL [22] | 未核实 |
| 保税（in-bond） | 无公开证据要求 | 4010：BND "Bond Charges"、CUS "Customs Charge" [7]；project44 BOND [22] | 未核实 |
| 特殊派送 | — | 685 "Special Delivery" [7] | 未核实 |
| 封路 | 未找到任何代码或证据资料 | — | 未核实 |
| 港口费、预提箱（pre-pull） | EDI2XML 列有港口/码头类代码；pre-pull 没有找到代码 [9] | — | 未核实 |
| "purchased transportation surcharge"（PENDING） | 按检索约束，没有用这个短语检索（它出自我们的数据），含义仍然**未知** | — | 不在本轮范围 |

---

### A2 容易被滥用或出错的费用类别（审核界面提示用）

只描述类别层面的风险，写成提示语，不对任何单笔费用下结论。

| 类别 | 资料中提到的风险 | 审核界面提示（"这类费用通常需要核实什么"） | 来源 |
|---|---|---|---|
| 杂费整体 | 首次自查的托运方常发现 5–15% 的杂费计错或用了与合同不符的费率；同一承运商对有月台的地点反复收尾板费，属于计费模式而非偶发错误 | 这类费用通常需要核实：合同是否约定该杂费、BOL/回单是否体现触发条件 | [38]（摘要） |
| 杂费：已收费但从未下单 | 开源审计工具专门有"杂费已收但从未下单"规则 | 通常需要核实：下单/BOL 时是否请求了该服务 | [27]（摘要） |
| 杂费：同一服务计两次 | 开源审计工具第一版漏掉的正是"一次服务计两次"；修正后按代码数单位数并比对合同单价 | 通常需要核实：同一代码在同一运单上的次数是否与服务次数一致 | [26]（摘要） |
| 等待费 | 没有时间戳或免费期条款时，经纪商常拒付 | 通常需要核实：到达/离开时间、免费时长、费率与计费增量、通知时间 | [32][34] |
| 过夜滞留 vs 等待费 | 两类可在同一票共存 | 通常需要核实：两类的计费时段是否重叠 | [36]（摘要） |
| 装卸工费 | 无收据通常不报销 | 通常需要核实：收据号、金额、日期与场站 | [35]（摘要） |
| 已派未用 | 口头取消事后难以证明 | 通常需要核实：取消时间与合同时限、取消方、到场证明 | [33] |
| 燃油附加费 | 指数周、分区、表版本、里程、计费基数出错；在单独通知中重复收取 | 通常需要核实：指数周和价格、基准价、表版本、里程或计费基数 | [30] |
| 尾板/住宅/室内/受限地点 | 回单或 BOL 若显示有月台或商业地址，则条件不成立 | 通常需要核实：BOL 收货地址类型、回单上的条件记录 | [31] |
| 重量/等级更正 | 证书缺照片或尺寸；托运方磅单冲突 | 通常需要核实：检验证书号、实测与申报重量、NMFC 条目 | [31][40] |
| 改址 | 管理费与追加运费两段，后者可能高达原运费 | 通常需要核实：改址指令来源与时间、新旧目的地、是否两段分列 | [37]（摘要） |
| 仓储 | 起算日依赖到货通知时间 | 通常需要核实：通知时间、免费期、计费天数 | [39]（摘要） |
| 加拿大税 | 税率取决于目的地省；连续国际货运可零税率 | 通常需要核实：目的地省份与税种/税率是否一致、税基 | [41][42] |
| 整张发票重复 | 承运商以新发票号重开同一账单，所以只按发票号查重不够 | 通常需要核实：同一承运商 + 运单号/BOL + 金额 + 日期是否已出现过 | [45] |

---

### A3 评价承运商的常用指标（只存字段，不打分）

| 指标 | 公式（来源原文或直译） | 计算所需字段 | 来源 |
|---|---|---|---|
| 发票准确率（invoice accuracy rate） | 无异常发票数 ÷ 发票总数 | invoice_id、carrier_id、是否有异常（flag 计数 > 0）、审核期间 | [45]；[44] 只有文字定义 |
| 行级计费准确率 | 与费率卡一致的行数 ÷ 总行数（目标带：≥98% 绿 / 95–98% 黄 / <95% 红） | line_id、invoice_id、charge_code、billed_amount、contract_amount（我们没有合同，只能存"与原文/Delta 一致"的替代口径） | [46]（摘要） |
| 异常率（exception rate） | 需人工调查的发票 ÷ 处理发票总数 × 100 | invoice_id、是否进入人工复核、处理时间 | [44] |
| 首次匹配率（first-pass match rate） | 无需人工干预即匹配成功的发票占比（来源无公式） | invoice_id、首次自动匹配结果、是否有人工改动（审计轨迹） | [44] |
| 免触达处理率（touchless rate） | 全自动处理发票 ÷ 发票总数 × 100 | invoice_id、是否有人工操作记录 | [44] |
| 重复开票/重复付款率 | 重复提交或重复付款的频率（来源无公式）；可操作化为：被判重复的记录 ÷ 记录总数 | carrier_id、invoice_number、pro_number、bol_number、shipment_id、amount、currency、shipment_date、重复组 ID 与重复层级 | [44][45] |
| 杂费占比 | 杂费占运费比例（[44] 无公式）；"Accessorial Charges as % of Base Rate" [47]；"accessorial ratio" 以总运费为分母 [48]。**分母有两种口径，存数时必须标明** | line category（LINEHAUL/FUEL/ACCESSORIAL/…）、line amount、currency、carrier_id、shipment_id | [44][47][48]（后两者摘要） |
| 超收率（overcharge rate） | 识别出的超收 ÷ 总运费 × 100 | 涉及应付判断，**不在本项目范围**，只列出不存 | [44] |
| 追回率/追回成功率 | 追回金额 ÷ 总运费；追回 ÷ 争议金额 | 同上，不在范围 | [45] |
| 争议频率、争议金额、平均处理时长 | 来源只列名称，未定义"争议率"公式 | dispute_id、carrier_id、创建时间、关闭时间、涉及金额、币种 | [44] |
| 按线路的承运商准确率 | 每条线路上无异常发票的比例 | carrier_id、起运地/目的地（省或城市级）、invoice_id、是否有异常 | [45] |
| 发票处理周期 | 收到到批准/付款的时间（来源无公式） | received_at、各状态时间戳 | [44] |

**字段层面的结论**：要支撑上述指标，每条记录至少要有 carrier_id、shipment_id、invoice_number、pro/BOL 号、日期、金额、**币种**、费用类别、异常标记、重复组、人工操作时间戳。"是否应付"类指标（超收率、追回率）不存。

---

### A4 现有标准和开源方案

#### A4.1 X12 EDI 210（Motor Carrier Freight Details and Invoice，004010）

**段结构（与我们相关的部分）**[1]

| 区域 | 段 | 作用 | 对我们的意义 |
|---|---|---|---|
| 表头 | B3 | 发票号（B3-02）、运单号（B3-03）、付款方式、开票日（B3-06）、**净应付额**（B3-07）、**更正标志**（B3-08）、送达日（B3-09）、SCAC（B3-11）[3] | B3-08 可区分原票和更正票，用于重复/版本判断 |
| 表头 | C3 | 币种 [1] | 发票级币种 |
| 表头 | N9（≤300） | 参考号（BOL、PO 等）[1] | 多种参考号，跨记录关联 |
| 表头 | G62（≤6） | 日期/时间：G62-01 日期限定符、G62-03 时间限定符、G62-04 时间 [4] | 预约、提货、送达时间 |
| 表头 | K1（≤10） | 备注 [1] | 唯一的自由文本位置之一 |
| 表头 | N1 循环（N1/N2/N3/N4/N9） | 当事方名称与地址 [1] | 起运地/目的地省份（用于税） |
| 明细 | S5 循环（S5、N9、G62、H3） | 经停点及其日期时间 [1] | 每个经停点的时间，用于等待费 |
| 明细 | LX 循环（≤9999）：LX、N9、POD、L5、H1/H2、**L0**、**L1**、L4、L7、K1 | 每个计费行 [1] | 一行费用对应一个 LX（有的伙伴要求一个 L1 一个 LX，摘要） |
| 汇总 | L3 | 总重量与总金额 [1] | 行合计校验 |

**L1（Rate and Charges）关键元素** [2]

| 元素 | 含义 |
|---|---|
| L1-02 / L1-03 | 费率 / 费率限定符（成对出现） |
| L1-04 | 金额（该行运费或杂费） |
| L1-08（元素 150） | **Special Charge or Allowance Code**，3 位，4010 共 1073 个代码 |
| L1-12（元素 276） | Special Charge Description，**仅 2–25 个字符**，在 150 中找不到合适代码时使用 |
| L1-17 / L1-18 | 计费数量 / 计费数量限定符（里程、重量、体积等） |
| L1-19 | 百分比（用于算出 L1-04，例如燃油百分比） |
| L1-20 | 币种（作用于本 L1 所有金额） |

**代码版本差异（已核实）**：4010 有 405 "Fuel Surcharge"、GST，没有 HST、PTX [7]；8010 增加了 HST、PTX、QST [8]；两个版本都没有 FSC [7][8]，但第三方列表收录了 FSC [9]。所以代码必须记录**代码体系和版本**。

**EDI 214/990/997**：214 的 AT7 状态码（X1、X3、AF、CD、CP、D1、AH、A7）提供到达、装卸完成、离开、尝试派送、拒收的时间戳，是等待费、再派送证据的标准来源 [6]。990（承运商对派车单的接受/拒绝）可能与 TONU 有关，但本轮**未核实**其字段。997 只是功能确认回执，与证据无关（常识，**未抓取核实**）。

#### A4.2 Oracle Transportation Management（OTM）公开文档

| 主题 | 公开文档内容 | 来源 |
|---|---|---|
| 发票行字段 | 行序号、Freight Charge（= Billed As Quantity × Freight Rate Value）、Cost Type、Description（≤120 字符）、Accessorial Code ID、Accessorial Description、Adjustment Reason、Freight Rate Qualifier、Billed As Quantity/Qualifier、Weight、Remarks、Reference Number + Qualifier、Tariff 引用（含生效日）、VAT（含加拿大省级税）、General Ledger Code | [10] |
| Cost Type 代码 | B 基础费、D 折扣、A 杂费、S 经停、C 绕行、**L 差额（Delta）**、O 其他 | [10] |
| 行匹配状态 | UNMATCHED、MATCHED、MATCHED_IN_TOLERANCE、MATCHED_OUT_OF_TOLERANCE、UNMATCHED_IN_TOLERANCE、UNMATCHED_OUT_OF_TOLERANCE | [10] |
| 超容差明细 | 超出金额、偏差、原因代码（Above/Below Allowable Amount/Percentage） | [10] |
| 行与运单成本关联 | Invoice Line Item Cost References：可关联订单行、运单经停、运单单元、成本序号等 | [10] |
| 容差规则 | 按 Cost Type × Accessorial Code × 总账代码 × 付款方式组合设定上下浮动百分比/金额，取更严者；例：燃油附加费行可比运单成本高 5% | [11] |
| 发票级审批规则 | 将发票与已匹配运单的成本和重量比较；默认规则 + 明细规则；百分比基于运单或发票可配置 | [12] |
| 重复判定 | 非贷项通知的发票若匹配到已有发票的运单，MATCH 状态变为 MATCH_NON_ORIGINAL_INVOICE；贷项通知则进入 PROCESS_HOLD，不算重复 | [13] |
| 发票状态类型 | APPROVAL、INVOICE MODIFIED、MATCH（含 Non_original_invoice、Multiple_shipment_match 等）、PROCESS（Hold）、VAT_CALCULATION；没有专门的"争议"状态 | [14] |
| 金额与币种 | REST 接口中金额是 currencyType 对象（ISO 4217 币种 + 数值），每个金额单独带币种；还有 exchangeRateDate、exchangeRateGid；INVOICE_LINEITEM 表本身带币种字段 | [15][19] |
| 数据表名 | 社区论坛列出发票相关表：INVOICE、INVOICE_LINEITEM、INVOICE_INVOLVED_PARTY、INVOICE_REMARK、INVOICE_SHIPMENT、INVOICE_STOP、INVOICE_STATUS、INVOICE_REFNUM、VOUCHER | [16]（论坛，摘要） |
| ACCESSORIAL_CODE 表 | 6.3 数据管理指南列有 ACCESSORIAL_CODE_GID、ACCESSORIAL_CODE_XID、ACCESSORIAL_DESC、APPLY_GLOBALLY、DOMAIN_NAME、IS_FLOW_THRU、IS_VAT_EXEMPT | [17]（摘要，PDF 未能解析） |
| INVOICE_SHIPMENT | REST 子资源含 lineitemSeqNo、shipmentGid、trackingNumber 等，说明发票行可直接关联运单 | [18]（摘要） |
| 完整列定义 | INVOICE_LINEITEM、INVOICE_REFNUM 的完整列表需要 OTM Data Dictionary，公开网页上**没有找到** | — |

**注意范围**：OTM 的审批、凭证、超收部分属于付款决策，本项目只能借鉴它的**数据结构**（行、代码、匹配状态、差额类型），不能借鉴审批语义。

#### A4.3 其他标准与开源方案

| 方案 | 有什么 | 成熟度 | 来源 |
|---|---|---|---|
| OASIS UBL 2.1 `cac:AllowanceCharge` | ChargeIndicator（收费/折让）、AllowanceChargeReasonCode（0..1）、AllowanceChargeReason（文本，0..*）、MultiplierFactorNumeric、Amount、BaseAmount、PerUnitAmount、TaxCategory、SequenceNumeric | 国际标准，欧洲 Peppol 强制使用；不是货运专用 | [20] |
| Peppol BIS Billing 3.0 | 收费原因码用 UNCL7161，折让用 UNCL5189；代码与文本须表示同一原因 | 成熟。**UNCL7161 中货运相关的具体代码本轮没有抓到，未核实** | [21]（摘要） |
| project44 参考代码 | LTL 提货/送货/通用杂费代码（LGDEL、RESDEL、LTDDEL、HAZM、PFZ、SORTDEL、RECON、LUMPER、BOND、ELS_*）和 Charge Codes（DET、STORAGE、FSC、TAX） | 厂商私有代码，覆盖北美 LTL 常见杂费；页面没有说明是用于下单还是开票 | [22] |
| NMFTA 数字 LTL 委员会 | eBOL API v2.1；Preliminary Freight Charges（PFC）API 追踪改重、改等级、增删杂费、仓储、等待、再派送等计费事件，事件码有 RWE、RCL、LFTP、APTD 等（页面未给全表） | 行业协会标准，较新；委员会自己承认杂费列表永远不全，各承运商有自己的代码 | [23][24]（[24] 摘要） |
| Open Logistics Foundation | 已发布 eCMR 开源标准，在做电子交货单；**没有找到货运发票数据模型** | 欧洲为主，与本项目无直接可用项 | [25]（摘要） |
| GitHub 个人项目 | 若干 Python/Django 审计 demo：按合同重算、燃油/杂费/重复检查、"杂费从未下单"规则、按代码计单位数 | 都用合成数据、单人维护，**没有成熟、多人维护的开源项目**；可借鉴规则思路，不可当标准 | [26][27][28]（摘要） |

#### A4.4 对照表：我们的需求 vs 现有方案

图例：**直接复用** = 字段语义可直接照搬；**需改造** = 有相近结构但要扩展；**无对应** = 标准里没有，需要自建。

| 我们的需求 | X12 210 | OTM | UBL/Peppol | project44 / NMFTA / 开源 | 结论 |
|---|---|---|---|---|---|
| 原始文本行原样保留 | 只有 K1 备注和 L1-12（2–25 字符）[1][2] | Remarks、Accessorial Description、Description（≤120 字符）[10] | AllowanceChargeReason 文本 [20] | 无 | **需改造**：标准的文本字段太短，也不区分不可变的原文层 |
| 我们对一次争议的解读与原始行分开 | 无（210 本身就是发票） | 发票行与运单计划成本分两层，可借鉴"两层对照"思路 [10][13] | 无 | 无 | **无对应**，需自建解读层 |
| 行项目：原文片段位置 + 代码 + 映射状态 | L1-08 代码 + L1-12 描述 [2] | Accessorial Code + Cost Type + 行匹配状态 [10] | ReasonCode + Reason [20] | project44 代码 [22] | 代码与描述**直接复用**；映射状态可**改造** OTM 的 MATCHED/UNMATCHED；原文片段位置**无对应** |
| 代码体系 | 4010 与 8010 代码不同 [7][8] | 每个域自定义 ACCESSORIAL_CODE [17] | UNCL7161/5189 [21] | 各自私有 [22][24] | **需改造**：每个代码须带"体系 + 版本"，内部分类表与外部代码做映射 |
| 每个数字的解读（费率、数量、单位、百分比、金额） | L1-02/03 费率与限定符、L1-17/18 计费数量与限定符、L1-19 百分比、L1-04 金额 [2] | Freight Rate Value/Qualifier、Billed As Quantity/Qualifier [10] | MultiplierFactorNumeric、BaseAmount、PerUnitAmount、Amount [20] | 无 | **直接复用**字段语义（数量 × 费率 = 金额，百分比 × 基数 = 金额）；但标准只覆盖"计费数字"，不覆盖文本里的时间、时长、指数价格等**证据数字** → 后者**需改造** |
| 算术关系 | L3 合计 = 各 L1 之和；B3-07 净应付 [1][3] | Freight Charge = 数量 × 费率；Cost Type L = 差额 [10] | BaseAmount × 系数 = Amount [20] | 开源 demo 重算 [26] | **需改造**：标准只有"行求和"和"数量 × 费率"，没有"差额 = 新 − 旧"、"税 = 税基 × 税率"、"(离开 − 到达 − 免费期) × 费率"这类关系 |
| 模型尝试与审计轨迹 | 无 | 只有 INVOICE MODIFIED 状态 [14] | 无 | 无 | **无对应** |
| 标记（flags） | 无 | 超容差原因码、行匹配状态 [10] | 无 | PFC 事件码 [23] | **需改造**：可借鉴"原因码 + 偏差量"结构，内容改为一致性检查，不含付款判断 |
| 审核员决定 | 无 | 审批状态、调整原因 [10][14]——属于付款审批 | 无 | 无 | **不可复用**（越出范围）；我们的审核员决定只针对"解读是否正确" |
| 每条记录带币种 | C3 发票级、L1-20 行级 [1][2] | 每个金额是（币种, 数值）对 [15] | 有（currencyID 属性为常识，本轮**未核实**） | — | **直接复用**：ISO 4217，按金额或按行存 |
| 多层级查重 | B3-08 更正标志可区分原票/更正票 [3] | 运单层：已有发票的运单再匹配 → MATCH_NON_ORIGINAL_INVOICE [13] | 无 | 发票层：承运商 + 运单号 + 金额；模糊：BOL + 金额 + 日期 ±2 天 [45]；行层：按代码计次数 [26] | **需改造**：组合成"发票号 / 运单 / 行 / 文本"四层，各层独立记录 |

**小结**：可直接照搬的是**计费行的数字结构**（费率、数量、限定符、百分比、金额、币种）和**代码 + 描述的二元结构**。需要自建的是**原文层与解读层的分离**、**原文片段位置**、**证据数字**（时间、时长、指数）、**模型尝试的审计轨迹**。现有标准都是"开票方写给付款方"的格式，没有一个是为"解读别人写的自由文本"设计的。

---

### A 部分来源清单

[1] Stedi — X12 004010 210 Motor Carrier Freight Details and Invoice — https://www.stedi.com/edi/x12-004010/210 — 厂商文档（X12 标准的转录） — accessed 2026-11-04
[2] Stedi — X12 004010 L1 Rate and Charges — https://www.stedi.com/edi/x12-004010/segment/L1 — 厂商文档（X12 转录） — accessed 2026-11-04
[3] Stedi — X12 004010 B3 Beginning Segment for Carrier's Invoice — https://www.stedi.com/edi/x12-004010/segment/B3 — 厂商文档（X12 转录） — accessed 2026-11-04
[4] Stedi — X12 004010 G62 Date/Time — https://www.stedi.com/edi/x12-004010/segment/G62 — 厂商文档（X12 转录） — accessed 2026-11-04
[5] Stedi — X12 004010 元素 432 Date Qualifier — https://www.stedi.com/edi/x12-004010/element/432 — 厂商文档（X12 转录） — accessed 2026-11-04
[6] Stedi — X12 004010 元素 1650 Shipment Status Code（EDI 214 AT7） — https://www.stedi.com/edi/x12-004010/element/1650 — 厂商文档（X12 转录） — accessed 2026-11-04
[7] Stedi — X12 004010 元素 150 Special Charge or Allowance Code — https://www.stedi.com/edi/x12-004010/element/150 — 厂商文档（X12 转录） — accessed 2026-11-04
[8] Stedi — X12 008010 元素 150 Special Charge or Allowance Code — https://www.stedi.com/edi/x12-008010/element/150 — 厂商文档（X12 转录） — accessed 2026-11-04
[9] EDI2XML — EDI 210 Charge Indicator Codes Reference — https://docs.edi2xml.com/docs/edi_codes/list_of_charge_indicator_codes/ — 厂商文档（版本未标明，部分代码与 [7][8] 不一致） — accessed 2026-11-04
[10] Oracle — OTM 26B Invoice Line Item Manager — https://docs.oracle.com/en/cloud/saas/transportation/26b/otmol/settlement/billing_manager/create_bill5.htm — 厂商文档 — accessed 2026-11-04
[11] Oracle — OTM 26B Line Approval Tolerance Detail — https://docs.oracle.com/en/cloud/saas/transportation/26b/otmol/settlement/line_approval/line_approval_tolerance_detail.htm — 厂商文档 — accessed 2026-11-04
[12] Oracle — OTM 26B Invoice Approve Rule Manager — https://docs.oracle.com/en/cloud/saas/transportation/26b/otmol/settlement/auto_approve_rule_mgr/new_auto_approve_rule.htm — 厂商文档 — accessed 2026-11-04
[13] Oracle — OTM 26B Match or Unmatch Invoice — https://docs.oracle.com/en/cloud/saas/transportation/26b/otmol/settlement/25_payment_manager/26_payment_actions/match_invoices.htm — 厂商文档 — accessed 2026-11-04
[14] Oracle — OTM 26C Invoice Status — https://docs.oracle.com/en/cloud/saas/transportation/26c/otmol/settlement/25_payment_manager/invoice_stat_types.htm — 厂商文档 — accessed 2026-11-04
[15] Oracle — OTM REST 26C Get Summary Details — https://docs.oracle.com/en/cloud/saas/transportation/26c/otmra/op-invoices-invoicegid-summarydetails-get.html — 厂商文档 — accessed 2026-11-04
[16] OTMFAQ — OTM Tables effecting in Settlement or Freight Payment — https://otmfaq.otmsig.com/forum/otm-g-log-functional-topics/settlement/3840-otm-tables-effecting-in-settlement-or-freight-payment — 论坛（摘要） — accessed 2026-11-04
[17] Oracle — OTM Data Management Guide Release 6.3 — https://docs.oracle.com/cd/E38437_01/otm/acrobat/otm/integration/E38426_03.pdf — 厂商文档（摘要，PDF 未能解析） — accessed 2026-11-04
[18] Oracle — OTM REST 24C Get a Shipment（invoices/{id}/shipments） — https://docs.oracle.com/en/cloud/saas/transportation/24c/otmra/op-invoices-invoicegid-shipments-sequenceno-get.html — 厂商文档（摘要） — accessed 2026-11-04
[19] Oracle — OTM 25C About Flex Fields（列出 INVOICE、INVOICE_LINEITEM 等带币种字段的表） — https://docs.oracle.com/en/cloud/saas/transportation/25c/otmol/general/about_flex_fields.htm — 厂商文档（摘要） — accessed 2026-11-04
[20] Datypic — UBL 2.1 cac:AllowanceCharge — http://www.datypic.com/sc/ubl21/e-cac_AllowanceCharge.html — 行业标准文件（OASIS UBL 架构的第三方转录） — accessed 2026-11-04
[21] OpenPeppol — Peppol BIS Billing 3.0 cbc:AllowanceChargeReasonCode — https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/cac-AllowanceCharge/cbc-AllowanceChargeReasonCode/ — 行业标准文件（摘要） — accessed 2026-11-04
[22] project44 — Reference Data（参考代码） — https://developers.project44.com/api-reference/reference-codes — 厂商文档 — accessed 2026-11-04
[23] NMFTA DSDC — Preliminary Freight Charges API Standard — https://dsdc.nmfta.org/apis/preliminary-freight-charges-api-standard — 行业标准文件 — accessed 2026-11-04
[24] NMFTA — Digital LTL Council Membership Meeting June 2024 — https://nmfta.org/wp-content/media/2024/07/Membership-Presentation-SMC3-Connections-2024.pdf — 行业标准文件（协会会议材料，摘要） — accessed 2026-11-04
[25] Open Logistics Foundation — 官网/eCMR 与电子交货单项目 — https://openlogisticsfoundation.org/ — 行业文章（摘要） — accessed 2026-11-04
[26] GitHub — farid-richa/freight-invoice-auditor — https://github.com/farid-richa/freight-invoice-auditor — 论坛（个人开源仓库，摘要） — accessed 2026-11-04
[27] GitHub — Austin-Brock/FreightLens — https://github.com/Austin-Brock/FreightLens — 论坛（个人开源仓库，摘要） — accessed 2026-11-04
[28] GitHub — anmol3012/FREIGHT-INVOICE-VALIDATION-SYSTEM — https://github.com/anmol3012/FREIGHT-INVOICE-VALIDATION-SYSTEM — 论坛（个人开源仓库，摘要） — accessed 2026-11-04
[29] U.S. EIA — Gasoline and Diesel Fuel Update — https://www.eia.gov/petroleum/gasdiesel/ — 行业标准文件（政府数据） — accessed 2026-11-04
[30] ParserAI — Fuel Surcharge Audit: How to Check Every Freight Invoice Against the Diesel Index and Your Contract — https://parserai.co/blog/fuel-surcharge-audit-diesel-index-week-freight-invoice-logistics — 行业文章 — accessed 2026-11-04
[31] Eller Audit — LTL Freight Audit: A Plain-English Guide — https://www.elleraudit.com/ltl-freight-audit — 行业文章 — accessed 2026-11-04
[32] TA Trans — Detention Pay in Trucking: Proof for Claims — https://tatransinc.com/2026/07/20/detention-pay-trucking-proof-claim/ — 行业文章 — accessed 2026-11-04
[33] Alexander, Winton & Associates — TONU Meaning in Trucking: Fees, Disputes, and How to Collect — https://awcollects.com/tonu-meaning-in-trucking-fees-disputes-and-how-to-collect/ — 行业文章 — accessed 2026-11-04
[34] Kordovatek — Detention Time in Trucking: How to Get Paid for It — https://www.kordovatek.com/blog/detention-time-trucking-how-to-get-paid/ — 行业文章（摘要） — accessed 2026-11-04
[35] LaneProof — Lumper Fee in Logistics: Who Pays, Disputes & Rate Con Language — https://www.laneproof.com/blog/lumper-fee-in-logistics-who-pays-disputes-rate-con — 行业文章（摘要） — accessed 2026-11-04
[36] OTrucking — Layover Pay vs Detention Pay: Key Differences Explained — https://otrucking.com/resources/guides/layover-vs-detention-pay/ — 行业文章（摘要） — accessed 2026-11-04
[37] Diversified Transportation Services — Accessorial Charges — https://www.dtsone.com/resources/ltl-accessorial-charges/ — 行业文章（摘要） — accessed 2026-11-04
[38] FreightPlus — LTL Accessorial Charges: A Complete Guide for 2026 Shippers — https://freightplus.io/blog-ltl-accessorial-charges-2026/ — 行业文章（摘要） — accessed 2026-11-04
[39] 某 LTL 承运商规则费率表（UPGF 102-P，2022） — https://tforcefreight.com/downloads/UPGF-102-P-20220606.pdf — 厂商文档（摘要；单一承运商规则，不代表行业通则） — accessed 2026-11-04
[40] Logistics Plus — Accurate Shipping Weights: Why Do They Matter? — https://www.logisticsplus.com/accurate-shipping-weights-why-do-they-matter/ — 行业文章（摘要） — accessed 2026-11-04
[41] Canada Revenue Agency — GST/HST information for freight carriers — https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-specific-situations/freight-carriers.html — 行业标准文件（政府） — accessed 2026-11-04
[42] Canada Revenue Agency — GST/HST Memorandum 3-3-7 Place of Supply in a Province – Transportation — https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/3-3-7/plc-spply-prvnc-trnsprttn.html — 行业标准文件（政府） — accessed 2026-11-04
[43] Revenu Québec — Freight Transportation Services — https://www.revenuquebec.ca/en/businesses/consumption-taxes/gsthst-and-qst/special-cases-gsthst-and-qst/transportation-applying-the-gst-and-qst/freight-carriers/freight-transportation-services/ — 行业标准文件（政府；摘要，全文抓取返回 403） — accessed 2026-11-04
[44] MAS Partner — Freight AP KPIs: Key Metrics Guide — https://maspartner.com/en-us/publications/freight-ap-kpis/ — 行业文章 — accessed 2026-11-04
[45] beefed.ai — Freight Bill Audit: Complete Process Guide — https://beefed.ai/en/freight-bill-audit-process-guide — 行业文章 — accessed 2026-11-04
[46] TransportManagement.org — How to Build a Carrier Scorecard in 7 Steps — https://www.transportmanagement.org/how-to-build-a-carrier-scorecard-in-7-steps/ — 行业文章（摘要） — accessed 2026-11-04
[47] Nuvocargo — The CFO's Freight Spend Audit: 12 KPIs — https://www.nuvocargo.com/blog-posts/the-cfos-freight-spend-audit-12-kpis-that-expose-where-your-50m-budget-is-bleeding — 行业文章（摘要） — accessed 2026-11-04
[48] Redwood Logistics — How to Improve Freight Invoice Accuracy — https://www.redwoodlogistics.com/insights/how-to-improve-freight-invoice-accuracy — 行业文章（摘要） — accessed 2026-11-04
[49] FuelPeg — Fuel Surcharge Calculator — U.S. & Canada（引用 NRCan 与 EIA 周价） — https://fuelpeg.com/ — 行业文章（摘要；NRCan 官方页面未抓到） — accessed 2026-11-04

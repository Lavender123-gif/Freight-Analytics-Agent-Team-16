"""T13 step 2.2: the hand-made mapping from our charge codes (config/taxonomy.yaml) to the names on the client's
Addenda B accessorial list. Judged by meaning, not by string match. This is analysis input, not system config:
nothing in src/ reads it.

Relation types:
  EXACT        same charge
  APPROX       same charge in practice, the client's entry is a little wider or named differently
  ONE_TO_MANY  several client entries could take it; the list does not say which
  CHILD        the client's entry is wider; our code can only hang under it as a sub-item
  NONE         no place on the list ('ext_parent' = nearest entry to hang a 'not on the list' extension under, or None)

Only the client names that our codes map to appear here (the task allows these in tracked files); the full list
stays in the git-ignored data/interim/deliverables/T13/.
"""

from __future__ import annotations

EXACT, APPROX, ONE_TO_MANY, CHILD, NONE = "EXACT", "APPROX", "ONE_TO_MANY", "CHILD", "NONE"
TYPE_ZH = {EXACT: "完全对应", APPROX: "近似对应", ONE_TO_MANY: "一对多", CHILD: "子项", NONE: "没有位置"}

FREIGHT = "Freight"

# code: (type, [client names], ext_parent, reason in Chinese)
MAPPING: dict[str, tuple[str, list[str], str | None, str]] = {
    "LINEHAUL.BASE": (EXACT, [FREIGHT], None, "清单里唯一的运费本体条目；另有海运、空运、入库运费三个条目，都不是公路运费本体。"),
    "LINEHAUL.MINIMUM": (CHILD, [FREIGHT], None, "清单没有“最低收费”条目；最低收费是运费按下限计，属于运费的一种算法。"),
    "FUEL.SURCHARGE": (EXACT, ["FUEL SURCHARGE"], None, "名称和含义都一致；清单另有“紧急燃油附加”和“墨西哥燃油附加”，更窄，不用。"),
    "RATE_CORRECTION.FUEL_TIER": (CHILD, ["FUEL SURCHARGE"], None, "清单只列费用种类，不列“算错了”这种情形；这笔差额本身是燃油附加费，只能挂在它下面保留“费率档位更正”的含义。"),
    "RATE_CORRECTION.BASE_RATE": (CHILD, [FREIGHT], None, "差额是运费本体的差额；清单没有“基础费率更正”条目。"),
    "RATE_CORRECTION.WEIGHT": (CHILD, [FREIGHT], None, "按提单重量重算后的运费差额；清单的“重量检验”是复磅服务费，不是这个。"),
    "RATE_CORRECTION.ZONE_FACTOR": (CHILD, [FREIGHT], None, "区域系数是运价的一部分；清单的 ARBITRARY CHARGE、BEYOND CHARGE 是固定加价或转运段费用，含义接近但不等同。"),
    "RATE_CORRECTION.CONTRACT_GENERAL": (NONE, [], FREIGHT, "文字只说“按合同价补差”，没说是哪一种费用；清单里没有能表示“未指明的合同价差额”的条目。"),
    "ACCESSORIAL.LIFTGATE": (EXACT, ["LIFT GATE CHARGE"], None, "同一项服务（数据里写作 TAILGATE）。"),
    "ACCESSORIAL.INSIDE_DELIVERY": (EXACT, ["INSIDE DELIVERY"], None, "名称和含义都一致。"),
    "ACCESSORIAL.REDELIVERY": (EXACT, ["REDELIVERY CHARGE"], None, "名称和含义都一致。"),
    "ACCESSORIAL.SPECIAL_DELIVERY": (ONE_TO_MANY, ["SPECIAL SERVICES", "DELIVERY CHARGE", "PICKUP/DELIVER SURCHARGE"], None, "我们的定义本身就宽（收货方要求的特殊送货处理）；清单里三个宽泛条目都能放，分不出哪个。"),
    "ACCESSORIAL.APPOINTMENT": (APPROX, ["ARRIVAL NOTIFICATION"], None, "清单没有“预约送货”字样；到货通知是送货前联系收货方，其中一个 EDI 代码是 APT。差别：通知不等于约定时间。"),
    "ACCESSORIAL.RESIDENTIAL": (APPROX, ["RESIDENTIAL PU/DELIVERY CHARGE"], None, "同一项服务；清单条目同时包含住宅提货，比我们的定义略宽。"),
    "ACCESSORIAL.LIMITED_ACCESS": (NONE, [], "PICKUP/DELIVER SURCHARGE", "清单没有“受限地点”条目，只有工地、展会两种具体地点的附加费；都比我们的定义窄。"),
    "ACCESSORIAL.SORT_SEGREGATE": (EXACT, ["SORT,SEGREGATE & STACKING CHG"], None, "名称和含义都一致（清单条目多含“码放”）。"),
    "ACCESSORIAL.LUMPER": (EXACT, ["LUMPER SERVICE(EXTRA HELPER)"], None, "名称一致；清单另有人工费、装卸费等条目，但只有这一条写明 LUMPER。"),
    "ACCESSORIAL.HAZMAT": (EXACT, ["HAZARDOUS MATERIALS CHARGE"], None, "名称和含义都一致；清单另有“危险品代收转付”，更窄，不用。"),
    "ACCESSORIAL.PROTECT_FROM_FREEZE": (ONE_TO_MANY, ["PROTECTIVE SERVICE HEAT/COLD", "HEAT PROTECTION SERVICE"], None, "清单里两个条目都指保温防冻服务，没有定义，分不出区别。"),
    "ACCESSORIAL.REWEIGH": (ONE_TO_MANY, ["WEIGHT INSPECTION", "INSPECTION FEE"], None, "我们的定义把复磅和检验合在一起；清单分成两个条目。"),
    "ACCESSORIAL.TRUCK_ORDERED_NOT_USED": (EXACT, ["VEHICHLE ORDERED NOT USED"], None, "同一项费用（清单原文拼写如此）。"),
    "ACCESSORIAL.IN_BOND": (EXACT, ["BOND CHARGES"], None, "名称和含义都一致，数据里的写法与清单名称相同。"),
    "ACCESSORIAL.ROAD_CLOSURE": (NONE, [], "EXCESS MILES", "清单没有“道路封闭绕行”条目。按我们的定义（绕行产生的附加费）最近的是超额里程；如果起因是天灾，也可能是 WEATHER DISASTER SURCHARGE，需要客户确认。"),
    "DETENTION_STORAGE.DRIVER_DETENTION": (ONE_TO_MANY, ["DETENTION WITH POWER", "DETENTION W/POWER", "DETENTION: LOADING", "DETENTION: UNLOADING", "DETENTION-AFTER 4 HRS", "WAITING TIME"], None, "清单把司机带车等待拆成六个名称（带动力的两种写法、装货、卸货、4 小时后、等待时间）；数据里多数只写 DRIVER DETENTION，分不到某一个。"),
    "DETENTION_STORAGE.EQUIPMENT_DETENTION": (ONE_TO_MANY, ["DETENTION W/O POWER", "EQUIPMENT DETENTION ONLY -ORIGIN", "EQUIPMENT DETENTION ONLY - DESTINATION"], None, "清单按不带动力、起运地、目的地分成三条；数据里只写 EQUIPMENT DETENTION。"),
    "DETENTION_STORAGE.TERMINAL_STORAGE": (APPROX, ["STORAGE FEES"], None, "清单条目是一般的仓储费，没有限定在场站或铁路坡道，比我们的定义宽。"),
    "DETENTION_STORAGE.CONTAINER_PER_DIEM": (ONE_TO_MANY, ["DEMURRAGE CHARGE", "EQUIPMENT DETENTION ONLY -ORIGIN", "EQUIPMENT DETENTION ONLY - DESTINATION"], None, "清单没有 PER DIEM 字样。箱子超期按天收费，行业里滞期费（场内）和设备滞留费（场外）都接近；数据写法分起运地和目的地，与设备滞留的两条对得上。"),
    "DETENTION_STORAGE.DWELL": (NONE, [], "DEMURRAGE CHARGE", "清单没有 DWELL 条目；这个词本身不是标准叫法，含义还没有向客户确认。最近的是按天计的滞期费。"),
    "DRAYAGE.CHASSIS": (APPROX, ["CHASSIS / BOGIE OR AXLE CHG"], None, "清单条目把底盘车、转向架、车轴合成一条，比我们的定义宽。"),
    "DRAYAGE.PORT_FEE": (ONE_TO_MANY, ["PIER CHARGES", "TERMINAL HANDLING CHARGE", "WHARFAGE"], None, "港口端的费用清单里有三条，都没有定义；“拥堵费”没有任何条目写明。"),
    "DRAYAGE.PRE_PULL": (APPROX, ["SWITCHING/PULLING/RE-POSITIONING CHG"], None, "预提是把箱子先拉到堆场；清单条目是调车、拖移、重新摆位的合称，比我们的定义宽。"),
    "TAX.GST": (EXACT, ["GST - GOODS & SERVICE TAX"], None, "同一税种。"),
    "TAX.HST": (EXACT, ["HST - HARMONIZED SALES TAX"], None, "同一税种。"),
    "TAX.PST": (ONE_TO_MANY, ["STATE/PROVINCIAL SALES TAX (PST)", "QST - QUEBEC SALES TAX"], None, "我们把 QST 并在 PST 里，清单分成两条。按文字里写的是 PST 还是 QST 就能分开，属于可以消除的一对多。"),
    "TAX.UNSPECIFIED": (NONE, [], None, "清单只有具体税种；“没说是哪种税”不是一种费用，是读不出税种时的标记，不应该挂在任何一个税种下面。"),
    "PENDING.PURCHASED_TRANSPORTATION": (CHILD, [FREIGHT], None, "已定：作为运费的子项。清单里的 THIRD PARTY FEE、CARTAGE CHARGE 字面接近，但没有定义可以佐证。"),
    "OTHER": (NONE, [], None, "兜底类，不是一种费用；清单没有兜底条目（SPECIAL SERVICES 是具体的服务类条目，不能当兜底用）。"),
}

# verdicts for the phrasings that today end up in OTHER (step 2.3, class 5): phrase -> (client name or None, reason)
OTHER_VERDICTS: dict[str, tuple[str | None, str]] = {
    "CV19 FEE": (None, "疫情附加费。清单里没有这一项；COST RECOVERY ADJUSTMENT、REGULATORY FEE 字面上沾边，但没有定义，硬放等于换个名字的“其他”。"),
    "RESERVATION FEE": (None, "预订费。清单里没有预订或订舱费条目；PREMIUM SERVICE UPGRADE、SPECIAL SERVICES 都不是这个意思。"),
}
OTHER_ALIASES = {"CV 19 FEE": "CV19 FEE"}      # spelling variants of one phrasing


def used_names() -> set[str]:
    """Client names touched by the mapping: direct targets, parents of sub-items and of extensions."""
    out: set[str] = set()
    for _typ, names, ext_parent, _why in MAPPING.values():
        out.update(names)
        if ext_parent:
            out.add(ext_parent)
    return out | {n for n, _ in OTHER_VERDICTS.values() if n}

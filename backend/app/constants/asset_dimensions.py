"""资产分类正交维度字典与产品维度映射（issue #128，单一事实来源）。

迁移 0008、scripts/init_data.py 种子、tests/conftest.py 均引用本模块，避免多处手写漂移。

维度模型（asset_classification 表改造为维度值字典）：
- dimension：asset_class / region / style / size / segment 五个正交维度；
- code：`维度前缀_语义词`（ASSET_/REGION_/STYLE_/SIZE_/SEG_），全大写英文；
- name：聚合展示名目（UI 分区/图例/二级分组 chip 用）；
- sort_order：展示顺序。注意 asset_class 维度的 sort_order 同时是前端色板序位
  （大类颜色按 sort_order 从 CHART_COLORS 序位取色），变更即改色。

维度适用矩阵（product_service 校验与迁移回填校验共用此约定）：
- asset_class：全部产品必填；
- region：股票/债券必填，商品/现金 NULL；
- style/size：仅股票，其余 NULL；
- segment：股票→行业、债券→期限、商品→品种；现金 NULL。

按需扩展约定（YAGNI）：维度值只在有产品需要时新增（如未来 REITs →
ASSET_ALTERNATIVE + SEG_REIT），不为假想需求预留空值——故当前无可转债/REITs 值。

产品映射分两层：
- PRODUCT_DIMENSIONS：按产品 code 的逐只判定结果（124 只种子全覆盖，判定原则
  见 issue #128 评论：商品 vs 股票以跟踪标的为准；港股并入中国；中概互联类归中国）；
- OLD_CLASS_FALLBACK：旧扁平 code → 维度值的通用映射，作为迁移对未列入
  PRODUCT_DIMENSIONS 的产品（如用户手工新增）的兜底回填。
"""

# (code, dimension, name, sort_order, description)
ASSET_DIMENSIONS: list[tuple[str, str, str, int, str]] = [
    # ---- asset_class 大类（sort_order 即前端色板序位，勿轻易变更）----
    ("ASSET_STOCK", "asset_class", "股票", 1, "股票及股票型基金"),
    ("ASSET_BOND", "asset_class", "债券", 2, "债券及债券型基金"),
    ("ASSET_COMMODITY", "asset_class", "商品", 3, "商品现货/期货类资产（黄金等）"),
    ("ASSET_CASH", "asset_class", "现金", 4, "现金类资产（含货币基金）"),
    # ---- region 地域（港股并入中国；中概互联类归中国）----
    ("REGION_CN", "region", "中国", 1, "中国（含港股、中概互联类）"),
    ("REGION_US", "region", "美国", 2, "美国"),
    ("REGION_EU", "region", "欧洲", 3, "欧洲"),
    ("REGION_SEA", "region", "东南亚", 4, "东南亚"),
    ("REGION_JP", "region", "日本", 5, "日本"),
    ("REGION_GLOBAL", "region", "全球", 6, "全球分散配置"),
    # ---- style 风格（仅股票）----
    ("STYLE_GROWTH", "style", "成长", 1, "成长风格"),
    ("STYLE_VALUE", "style", "价值", 2, "价值风格"),
    ("STYLE_BALANCED", "style", "平衡", 3, "平衡/宽基/主动混合"),
    # ---- size 规模（仅股票）----
    ("SIZE_LARGE", "size", "大盘", 1, "大盘"),
    ("SIZE_SMALL", "size", "中小盘", 2, "中小盘"),
    # ---- segment 细分：通用 ----
    ("SEG_COMPOSITE", "segment", "综合", 1, "宽基指数/主动混合等综合型"),
    # ---- segment 细分：股票行业 ----
    ("SEG_DIVIDEND", "segment", "红利", 11, "红利/高股息"),
    ("SEG_BANK", "segment", "银行", 12, "银行"),
    ("SEG_SECURITIES", "segment", "证券", 13, "证券公司"),
    ("SEG_INSURANCE", "segment", "保险", 14, "保险"),
    ("SEG_NONBANK", "segment", "非银金融", 15, "非银金融（证券保险等）"),
    ("SEG_FINREAL", "segment", "金融地产", 16, "金融地产（含房地产）"),
    ("SEG_MEDICAL", "segment", "医药", 17, "医药医疗/生物科技"),
    ("SEG_MEDIA", "segment", "传媒", 18, "传媒/文体娱乐"),
    ("SEG_NEWENERGY", "segment", "新能源", 19, "新能源"),
    ("SEG_NONFERROUS", "segment", "有色金属", 20, "有色金属（行业股票，非商品现货）"),
    ("SEG_TECH", "segment", "科技", 21, "信息技术/大数据/半导体"),
    ("SEG_INTERNET", "segment", "互联网", 22, "互联网（中概互联/恒生科技等）"),
    ("SEG_CONSUMER", "segment", "消费", 23, "消费"),
    ("SEG_ENVIRONMENT", "segment", "环保", 24, "环保产业"),
    ("SEG_PENSION", "segment", "养老", 25, "养老产业"),
    ("SEG_ENERGY", "segment", "能源", 26, "能源（油气等行业股票，非商品现货）"),
    # ---- segment 细分：债券期限 ----
    ("SEG_BOND_SHORT", "segment", "短债", 41, "短债/超短债/同业存单"),
    ("SEG_BOND_MIDLONG", "segment", "中长债", 42, "中长期纯债"),
    ("SEG_BOND_COMPOSITE", "segment", "综合债", 43, "综合债/二级债基/全球债"),
    # ---- segment 细分：商品品种 ----
    ("SEG_GOLD", "segment", "黄金", 61, "黄金现货"),
]

DIMENSION_VALUE_MAP: dict[str, tuple[str, str, int]] = {
    code: (dimension, name, sort_order)
    for code, dimension, name, sort_order, _ in ASSET_DIMENSIONS
}

# 旧扁平 code → (asset_class, region, style, size, segment) 通用兜底映射（迁移 0008 用）
OLD_CLASS_FALLBACK: dict[str, tuple[str, str | None, str | None, str | None, str | None]] = {
    "STOCK_CN_LARGE": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_CN_SMALL": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "STOCK_CN_VALUE": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_CN_GROWTH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_CN_MIXED": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_HK_LARGE": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_HK_SMALL": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "STOCK_US": ("ASSET_STOCK", "REGION_US", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_EU": ("ASSET_STOCK", "REGION_EU", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_JP": ("ASSET_STOCK", "REGION_JP", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "STOCK_GLOBAL": ("ASSET_STOCK", "REGION_GLOBAL", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "BOND_SHORT": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "BOND_LONG": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "BOND_MIXED": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "BOND_US": ("ASSET_BOND", "REGION_US", None, None, "SEG_BOND_MIDLONG"),
    "BOND_GLOBAL": ("ASSET_BOND", "REGION_GLOBAL", None, None, "SEG_BOND_COMPOSITE"),
    "GOLD": ("ASSET_COMMODITY", None, None, None, "SEG_GOLD"),
    "CASH": ("ASSET_CASH", None, None, None, None),
}

# 逐产品维度判定：product code → (asset_class, region, style, size, segment)
# 判定原则（issue #128 评论）：商品 vs 股票以跟踪标的为准（跟踪商品现货→商品；
# 跟踪行业股票指数→股票）；港股并入中国；REITs（不动产）非股票，当前无 REITs 产品。
# 用户已确认：512400 有色→价值；519062/270002/519697→平衡。
PRODUCT_DIMENSIONS: dict[str, tuple[str, str | None, str | None, str | None, str | None]] = {
    # 现金
    "CASH": ("ASSET_CASH", None, None, None, None),
    # ---- 场内 ETF ----
    "515180.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_DIVIDEND"),
    "512070.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_NONBANK"),
    "512200.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_FINREAL"),
    "510310.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "512800.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_BANK"),
    "512400.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_NONFERROUS"),
    "512880.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_SECURITIES"),
    "510500.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "510580.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "515030.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_NEWENERGY"),
    "501057.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_NEWENERGY"),
    "159948.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "159938.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "159847.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "512980.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDIA"),
    "159940.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_FINREAL"),
    "159920.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "164906.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET"),
    "513520.SH": ("ASSET_STOCK", "REGION_JP", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "513050.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET"),
    "518880.SH": ("ASSET_COMMODITY", None, None, None, "SEG_GOLD"),
    # ---- LOF（场内/场外同维度）----
    "161039.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "160119.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "163417.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "163402.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "161119.SZ": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "161121.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_BANK"),
    "502010.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_SECURITIES"),
    "502056.SH": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "161017.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    # ---- 场外基金 ----
    "167301.SZ": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_INSURANCE"),
    "006486.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "009051.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_DIVIDEND"),
    "021550.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_DIVIDEND"),
    "008115.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_DIVIDEND"),
    "001092.OF": ("ASSET_STOCK", "REGION_US", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "320007.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_TECH"),
    "011608.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "002656.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "110026.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "003765.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "017937.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "001180.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "001513.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_TECH"),
    "000727.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "001717.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "002708.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "004424.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDIA"),
    "013304.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "018134.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_TECH"),
    "022939.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_SMALL", "SEG_COMPOSITE"),
    "008127.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "270002.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "519062.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "519222.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "519221.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "519697.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "000136.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "202023.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_COMPOSITE"),
    "001064.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_ENVIRONMENT"),
    "004241.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_COMPOSITE"),
    "000968.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_PENSION"),
    "110022.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_CONSUMER"),
    "519915.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_CONSUMER"),
    "000248.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_CONSUMER"),
    "000051.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "007028.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "110020.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "110003.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "000478.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "004752.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDIA"),
    "001469.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_FINREAL"),
    "000942.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_TECH"),
    "001052.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_SMALL", "SEG_COMPOSITE"),
    "001552.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_NONBANK"),
    "001595.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_BANK"),
    "519671.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_VALUE", "SIZE_LARGE", "SEG_COMPOSITE"),
    "100038.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "022979.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "022959.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "006381.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "000071.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "012957.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET"),
    "014424.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    "013308.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET"),
    "270042.OF": ("ASSET_STOCK", "REGION_US", "STYLE_GROWTH", "SIZE_LARGE", "SEG_COMPOSITE"),
    "050025.OF": ("ASSET_STOCK", "REGION_US", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE"),
    "016452.OF": ("ASSET_STOCK", "REGION_US", "STYLE_GROWTH", "SIZE_LARGE", "SEG_COMPOSITE"),
    "006327.OF": ("ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET"),
    "162411.SZ": ("ASSET_STOCK", "REGION_US", "STYLE_VALUE", "SIZE_LARGE", "SEG_ENERGY"),
    "000369.OF": ("ASSET_STOCK", "REGION_GLOBAL", "STYLE_GROWTH", "SIZE_LARGE", "SEG_MEDICAL"),
    # ---- 债券 ----
    "007823.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "006793.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "012348.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "006662.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "006663.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "014427.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "015822.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_SHORT"),
    "003376.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "519152.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "110037.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "270048.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "000147.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "006484.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_MIDLONG"),
    "485111.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "270044.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "202101.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "000563.OF": ("ASSET_BOND", "REGION_CN", None, None, "SEG_BOND_COMPOSITE"),
    "004419.OF": ("ASSET_BOND", "REGION_US", None, None, "SEG_BOND_MIDLONG"),
    "100050.OF": ("ASSET_BOND", "REGION_GLOBAL", None, None, "SEG_BOND_COMPOSITE"),
    "007360.OF": ("ASSET_BOND", "REGION_US", None, None, "SEG_BOND_SHORT"),
    "007204.OF": ("ASSET_BOND", "REGION_US", None, None, "SEG_BOND_MIDLONG"),
    "1001767346": ("ASSET_BOND", "REGION_GLOBAL", None, None, "SEG_BOND_COMPOSITE"),
    "1001767344": ("ASSET_BOND", "REGION_GLOBAL", None, None, "SEG_BOND_COMPOSITE"),
}

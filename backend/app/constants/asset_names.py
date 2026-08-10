"""asset_classification.asset_name 映射表（issue #98，单一事实来源）。

迁移 0007 与 scripts/init_data.py 种子均引用本模块，避免两处手写映射漂移。

语义分工：
- asset_name：聚合展示短名目（UI 分区副标题 / 图例分类标签用）；
- description：说明性文本，不作为展示名目载体。

注意：IN_TRANSIT_BUY / IN_TRANSIT_SELL 种子产品的 asset_class_code 为 NULL、
无对应分类行，故不在本映射表中（非遗漏）。
"""

ASSET_NAME_MAP: dict[str, str] = {
    "STOCK_CN_LARGE": "国内大盘",
    "STOCK_CN_SMALL": "国内中小盘",
    "STOCK_CN_VALUE": "国内价值",
    "STOCK_CN_GROWTH": "国内成长",
    "STOCK_CN_MIXED": "国内综合",
    "STOCK_HK_LARGE": "港股大盘",
    "STOCK_HK_SMALL": "港股中小盘",
    "STOCK_US": "美股",
    "STOCK_EU": "欧洲股票",
    "STOCK_JP": "日本股票",
    "STOCK_GLOBAL": "全球股票",
    "BOND_SHORT": "短债",
    "BOND_LONG": "中长债",
    "BOND_MIXED": "综合债",
    "BOND_US": "美债",
    "BOND_GLOBAL": "全球债券",
    "GOLD": "黄金",
    "CASH": "现金",
}

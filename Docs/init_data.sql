-- InvestRing 数据库初始化脚本
-- 生成时间：2026-04-29
-- 说明：包含投资人、资产分类、平台、产品、组合等基础数据

-- ============================================================================
-- 1. 投资人（investor）
-- 密码使用 bcrypt 哈希存储，cost factor: 10
-- 默认密码：admin123
-- ============================================================================

INSERT INTO investor (code, name, role, phone, email, password_hash) VALUES
('ADMIN', '系统管理员', 'admin', NULL, NULL, '$2b$10$Gq1dscOi/69KE/n7x9nwZOdxAQP6g4t4ukWBWRGdsq37/mUJMr2fq');

-- ============================================================================
-- 2. 资产分类字典（asset_classification）
-- 共18条标准分类
-- ============================================================================

INSERT INTO asset_classification (code, asset_type, asset_category, asset_subcat, description) VALUES
-- 股票 - 国内
('STOCK_CN_LARGE', '股票', '国内股票', '大盘', '国内大盘股票'),
('STOCK_CN_SMALL', '股票', '国内股票', '中小盘', '国内中小盘股票'),
('STOCK_CN_VALUE', '股票', '国内股票', '价值', '国内价值风格股票'),
('STOCK_CN_GROWTH', '股票', '国内股票', '成长', '国内成长风格股票'),
('STOCK_CN_MIXED', '股票', '国内股票', '综合', '国内综合风格股票'),
-- 股票 - 香港
('STOCK_HK_LARGE', '股票', '港股', '大盘', '港股大盘股票'),
('STOCK_HK_SMALL', '股票', '港股', '中小盘', '港股中小盘股票'),
-- 股票 - 海外
('STOCK_US', '股票', '美股', '美股', '美国股票'),
('STOCK_EU', '股票', '欧洲', '欧洲', '欧洲股票'),
('STOCK_JP', '股票', '日本', '日本', '日本股票'),
('STOCK_GLOBAL', '股票', '海外股票', '全球', '全球股票'),
-- 债券
('BOND_SHORT', '债券', '国内债券', '短债', '国内短期债券'),
('BOND_LONG', '债券', '国内债券', '中长债', '国内中长期债券'),
('BOND_MIXED', '债券', '国内债券', '综合债', '国内综合债券'),
('BOND_US', '债券', '国际债券', '美债', '美国债券'),
('BOND_GLOBAL', '债券', '国际债券', '全球', '全球债券'),
-- 其他
('GOLD', '黄金', '黄金', '黄金', '黄金资产'),
('CASH', '现金', '现金', '现金', '现金类资产（含货币基金）');

-- ============================================================================
-- 3. 平台（platform）
-- 数据来源：用户上传的平台列表
-- ============================================================================

INSERT INTO platform (code, name, platform_type) VALUES
-- 第三方理财平台
('MYCF', '蚂蚁财富', '第三方平台'),
('TXLCT', '腾讯理财通', '第三方平台'),
('QM', '且慢', '第三方平台'),
('JDFC', '京东金融', '第三方平台'),
('LCMF', '理财魔方', '第三方平台'),
('TTJJ', '天天基金', '第三方平台'),
('YZYX', '有知有行', '第三方平台'),
-- 证券公司
('HBZQ', '华宝证券', '券商'),
('HTZQ', '华泰证券', '券商'),
-- 银行
('JTYY', '交通银行', '银行'),
('ZGYH', '中国银行', '银行'),
('NYYH', '农业银行', '银行'),
('JSYH', '建设银行', '银行'),
('WSYH', '微众银行', '银行'),
('WSBK', '网商银行', '银行'),
('ZBYH', '众邦银行', '银行'),
('ZXYH', '振兴银行', '银行'),
('SXYH', '三湘银行', '银行'),
-- 基金公司
('YFFCJJ', '易方达基金', '基金公司'),
('GFJJ', '广发基金', '基金公司'),
('NFJJ', '南方基金', '基金公司'),
('FGJJ', '富国基金', '基金公司'),
('RTJJ', '融通基金', '基金公司'),
('BSJJ', '博时基金', '基金公司'),
('HTFJJ', '汇添富基金', '基金公司'),
('YHJJ', '银华基金', '基金公司'),
('HXJJ', '华夏基金', '基金公司'),
('MGJJ', '摩根基金', '基金公司'),
-- 其他
('ZB', '纸币', '其他'),
('YSK', '应收款', '其他');

-- ============================================================================
-- 4. 产品（product）
-- 数据来源：docs/plans/data/fund_products.csv
-- 总计：124只（现金1只 + ETF 21只 + LOF 18只 + OEF 84只）
-- 注意：LOF需拆分为场内和场外两条记录
-- ============================================================================

-- 4.1 现金类产品
INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii) VALUES
('CASH', NULL, '现金类资产', 'CASH', 'CASH', 0, FALSE);

-- 4.2 ETF基金（场内，T+0确认）
INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii) VALUES
('515180.SH', 'CN_EXCHANGE', '易方达中证红利ETF', 'ETF', 'STOCK_CN_VALUE', 0, FALSE),
('512070.SH', 'CN_EXCHANGE', '易方达沪深300非银ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('512200.SH', 'CN_EXCHANGE', '南方中证房地产ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('510310.SH', 'CN_EXCHANGE', '易方达沪深300发起式ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('512800.SH', 'CN_EXCHANGE', '华宝中证银行ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('512400.SH', 'CN_EXCHANGE', '南方中证申万有色金属ETF', 'ETF', 'STOCK_CN_MIXED', 0, FALSE),
('512880.SH', 'CN_EXCHANGE', '国泰中证全指证券公司ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('510500.SH', 'CN_EXCHANGE', '南方中证500ETF', 'ETF', 'STOCK_CN_SMALL', 0, FALSE),
('510580.SH', 'CN_EXCHANGE', '易方达中证500ETF', 'ETF', 'STOCK_CN_SMALL', 0, FALSE),
('515030.SH', 'CN_EXCHANGE', '华夏中证新能源汽车ETF', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('501057.SH', 'CN_EXCHANGE', '汇添富中证新能源汽车A', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('159948.SZ', 'CN_EXCHANGE', '南方创业板ETF', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('159938.SZ', 'CN_EXCHANGE', '广发中证全指医药卫生ETF', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('159847.SZ', 'CN_EXCHANGE', '易方达中证医疗ETF', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('512980.SH', 'CN_EXCHANGE', '广发中证传媒ETF', 'ETF', 'STOCK_CN_GROWTH', 0, FALSE),
('159940.SZ', 'CN_EXCHANGE', '广发中证全指金融地产ETF', 'ETF', 'STOCK_CN_LARGE', 0, FALSE),
('159920.SZ', 'CN_EXCHANGE', '华夏恒生ETF(QDII)', 'ETF', 'STOCK_HK_LARGE', 0, TRUE),
('164906.SZ', 'CN_EXCHANGE', '交银中证海外中国互联网指数', 'ETF', 'STOCK_GLOBAL', 0, TRUE),
('513520.SH', 'CN_EXCHANGE', '华夏野村日经225ETF', 'ETF', 'STOCK_JP', 0, FALSE),
('513050.SH', 'CN_EXCHANGE', '易方达中概互联50ETF', 'ETF', 'STOCK_GLOBAL', 0, TRUE),
('518880.SH', 'CN_EXCHANGE', '华安黄金易ETF', 'ETF', 'GOLD', 0, FALSE);

-- 4.3 LOF基金（场内，T+0确认）
INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii) VALUES
('161039.SZ', 'CN_EXCHANGE', '富国中证1000指数增强(LOF)A', 'LOF', 'STOCK_CN_SMALL', 0, FALSE),
('160119.SZ', 'CN_EXCHANGE', '南方500ETF联接LOF', 'LOF', 'STOCK_CN_SMALL', 0, FALSE),
('163417.SZ', 'CN_EXCHANGE', '兴全合宜混合(LOF)A', 'LOF', 'STOCK_CN_MIXED', 0, FALSE),
('163402.SZ', 'CN_EXCHANGE', '兴全趋势投资混合(LOF)', 'LOF', 'STOCK_CN_MIXED', 0, FALSE),
('161119.SZ', 'CN_EXCHANGE', '易方达中债新综指(LOF)A', 'LOF', 'BOND_MIXED', 0, FALSE),
('161121.SZ', 'CN_EXCHANGE', '易方达中证银行指数(LOF)A', 'LOF', 'STOCK_CN_LARGE', 0, FALSE),
('502010.SH', 'CN_EXCHANGE', '易方达中证全指证券公司指数(LOF)A', 'LOF', 'STOCK_CN_LARGE', 0, FALSE),
('502056.SH', 'CN_EXCHANGE', '广发中证医疗指数(LOF)A', 'LOF', 'STOCK_CN_GROWTH', 0, FALSE),
('161017.SZ', 'CN_EXCHANGE', '富国中证500指数增强(LOF)A', 'LOF', 'STOCK_CN_SMALL', 0, FALSE);

-- 4.4 LOF基金（场外，T+1确认）
INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii) VALUES
('161039.SZ', 'CN_OTC', '富国中证1000指数增强(LOF)A', 'LOF', 'STOCK_CN_SMALL', 1, FALSE),
('160119.SZ', 'CN_OTC', '南方500ETF联接LOF', 'LOF', 'STOCK_CN_SMALL', 1, FALSE),
('163417.SZ', 'CN_OTC', '兴全合宜混合(LOF)A', 'LOF', 'STOCK_CN_MIXED', 1, FALSE),
('163402.SZ', 'CN_OTC', '兴全趋势投资混合(LOF)', 'LOF', 'STOCK_CN_MIXED', 1, FALSE),
('161119.SZ', 'CN_OTC', '易方达中债新综指(LOF)A', 'LOF', 'BOND_MIXED', 1, FALSE),
('161121.SZ', 'CN_OTC', '易方达中证银行指数(LOF)A', 'LOF', 'STOCK_CN_LARGE', 1, FALSE),
('502010.SH', 'CN_OTC', '易方达中证全指证券公司指数(LOF)A', 'LOF', 'STOCK_CN_LARGE', 1, FALSE),
('502056.SH', 'CN_OTC', '广发中证医疗指数(LOF)A', 'LOF', 'STOCK_CN_GROWTH', 1, FALSE),
('161017.SZ', 'CN_OTC', '富国中证500指数增强(LOF)A', 'LOF', 'STOCK_CN_SMALL', 1, FALSE);

-- 4.5 场外基金（OEF，普通T+1，QDII T+2）
INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii) VALUES
('167301.SZ', 'CN_OTC', '方正富邦保险主题指数', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('006486.OF', 'CN_OTC', '广发中证1000ETF联接A', 'OEF', 'STOCK_CN_SMALL', 1, FALSE),
('009051.OF', 'CN_OTC', '易方达中证红利ETF联接A', 'OEF', 'STOCK_CN_VALUE', 1, FALSE),
('021550.OF', 'CN_OTC', '博时中证红利低波动100ETF联接A', 'OEF', 'STOCK_CN_VALUE', 1, FALSE),
('008115.OF', 'CN_OTC', '天弘中证红利低波动100C', 'OEF', 'STOCK_CN_VALUE', 1, FALSE),
('001092.OF', 'CN_OTC', '广发生物科技指数人民币(QDII)A', 'OEF', 'STOCK_CN_GROWTH', 2, TRUE),
('320007.OF', 'CN_OTC', '诺安成长混合', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('011608.OF', 'CN_OTC', '易方达科创板50ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('002656.OF', 'CN_OTC', '南方创业板ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('110026.OF', 'CN_OTC', '易方达创业板ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('003765.OF', 'CN_OTC', '广发创业板ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('017937.OF', 'CN_OTC', '易方达中证医疗ETF联接发起式A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('001180.OF', 'CN_OTC', '广发医药卫生联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('001513.OF', 'CN_OTC', '易方达信息产业混合', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('000727.OF', 'CN_OTC', '融通健康产业A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('001717.OF', 'CN_OTC', '工银前沿医疗股票A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('002708.OF', 'CN_OTC', '大摩健康产业混合A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('004424.OF', 'CN_OTC', '汇添富文体娱乐混合A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('013304.OF', 'CN_OTC', '易方达中证科创创业50ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('018134.OF', 'CN_OTC', '富国中证大数据产业联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('022939.OF', 'CN_OTC', '华夏科创创业50ETF发起式联接Y', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('008127.OF', 'CN_OTC', '广发趋势优选灵活配置混合C', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('270002.OF', 'CN_OTC', '广发稳健增长混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('519062.OF', 'CN_OTC', '海富通阿尔法对冲混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('519222.OF', 'CN_OTC', '海富通欣益混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('519221.OF', 'CN_OTC', '海富通欣益混合C', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('519697.OF', 'CN_OTC', '交银优势行业混合', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('000136.OF', 'CN_OTC', '民生加银策略精选混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('202023.OF', 'CN_OTC', '南方优选成长混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('001064.OF', 'CN_OTC', '广发中证环保产业联接A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('004241.OF', 'CN_OTC', '中欧时代先锋股票C', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('000968.OF', 'CN_OTC', '广发养老指数A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('110022.OF', 'CN_OTC', '易方达消费行业股票', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('519915.OF', 'CN_OTC', '富国消费主题混合A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('000248.OF', 'CN_OTC', '汇添富中证主要消费ETF联接A', 'OEF', 'STOCK_CN_MIXED', 1, FALSE),
('000051.OF', 'CN_OTC', '华夏沪深300ETF联接A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('007028.OF', 'CN_OTC', '易方达中证500ETF联接A', 'OEF', 'STOCK_CN_SMALL', 1, FALSE),
('110020.OF', 'CN_OTC', '易方达沪深300ETF联接A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('110003.OF', 'CN_OTC', '易方达上证50增强A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('000478.OF', 'CN_OTC', '建信中证500指数增强A', 'OEF', 'STOCK_CN_SMALL', 1, FALSE),
('004752.OF', 'CN_OTC', '广发中证传媒ETF联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('001469.OF', 'CN_OTC', '广发中证全指金融地产联接A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('000942.OF', 'CN_OTC', '广发信息技术联接A', 'OEF', 'STOCK_CN_GROWTH', 1, FALSE),
('001052.OF', 'CN_OTC', '华夏中证500ETF联接A', 'OEF', 'STOCK_CN_SMALL', 1, FALSE),
('001552.OF', 'CN_OTC', '天弘中证证券保险A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('001595.OF', 'CN_OTC', '天弘中证银行ETF联接C', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('519671.OF', 'CN_OTC', '银河沪深300价值指数A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('100038.OF', 'CN_OTC', '富国沪深300指数增强A', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('022979.OF', 'CN_OTC', '华夏中证A500ETF联接Y', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('022959.OF', 'CN_OTC', '华夏上证50ETF联接Y', 'OEF', 'STOCK_CN_LARGE', 1, FALSE),
('006381.OF', 'CN_OTC', '华夏恒生ETF联接C', 'OEF', 'STOCK_HK_LARGE', 1, FALSE),
('000071.OF', 'CN_OTC', '华夏恒生ETF联接A', 'OEF', 'STOCK_HK_LARGE', 1, FALSE),
('012348.OF', 'CN_OTC', '天弘恒生科技指数(QDII)A', 'OEF', 'STOCK_HK_LARGE', 2, TRUE),
('014424.OF', 'CN_OTC', '博时恒生医疗保健ETF发起式联接(QDII)A', 'OEF', 'STOCK_HK_LARGE', 2, TRUE),
('013308.OF', 'CN_OTC', '易方达恒生科技ETF联接(QDII)A', 'OEF', 'STOCK_HK_LARGE', 2, TRUE),
('270042.OF', 'CN_OTC', '广发纳指100ETF联接人民币(QDII)A', 'OEF', 'STOCK_US', 2, TRUE),
('050025.OF'.OF, 'CN_OTC', '博时标普500ETF联接A', 'OEF', 'STOCK_US', 2, TRUE),
('016452.OF', 'CN_OTC', '南方纳斯达克100指数发起(QDII)A', 'OEF', 'STOCK_US', 2, TRUE),
('006327.OF', 'CN_OTC', '易方达中证海外50ETF联接人民币A', 'OEF', 'STOCK_GLOBAL', 2, TRUE),
('007823.OF', 'CN_OTC', '天弘弘择短债A', 'OEF', 'BOND_SHORT', 1, FALSE),
('006793.OF', 'CN_OTC', '交银稳鑫短债债券A', 'OEF', 'BOND_SHORT', 1, FALSE),
('012957.OF', 'CN_OTC', '嘉实60天滚动持有短债A', 'OEF', 'BOND_SHORT', 1, FALSE),
('006662.OF', 'CN_OTC', '易方达安悦超短债A', 'OEF', 'BOND_SHORT', 1, FALSE),
('006663.OF', 'CN_OTC', '易方达安悦超短债C', 'OEF', 'BOND_SHORT', 1, FALSE),
('014427.OF', 'CN_OTC', '富国中证同业存单AAA指数7天持有', 'OEF', 'BOND_SHORT', 1, FALSE),
('015822.OF', 'CN_OTC', '易方达中证同业存单AAA指数7天持有', 'OEF', 'BOND_SHORT', 1, FALSE),
('003376.OF', 'CN_OTC', '广发中债7-10年国开债指数A', 'OEF', 'BOND_LONG', 1, FALSE),
('519152.OF', 'CN_OTC', '新华纯债添利债券发起A', 'OEF', 'BOND_LONG', 1, FALSE),
('110037.OF', 'CN_OTC', '易方达纯债债券A', 'OEF', 'BOND_LONG', 1, FALSE),
('270048.OF', 'CN_OTC', '广发纯债债券A', 'OEF', 'BOND_LONG', 1, FALSE),
('000147.OF', 'CN_OTC', '易方达高等级信用债A', 'OEF', 'BOND_LONG', 1, FALSE),
('006484.OF', 'CN_OTC', '广发中债1-3年国开债指数A', 'OEF', 'BOND_LONG', 1, FALSE),
('485111.OF', 'CN_OTC', '工银瑞信双利债券A', 'OEF', 'BOND_MIXED', 1, FALSE),
('270044.OF', 'CN_OTC', '广发双债添利债券A', 'OEF', 'BOND_MIXED', 1, FALSE),
('202101.OF', 'CN_OTC', '南方宝元债券A', 'OEF', 'BOND_MIXED', 1, FALSE),
('000563.OF', 'CN_OTC', '南方通利债券A', 'OEF', 'BOND_MIXED', 1, FALSE),
('004419.OF', 'CN_OTC', '汇添富美元债债券(QDII)人民币A', 'OEF', 'BOND_US', 2, TRUE),
('100050.OF', 'CN_OTC', '富国全球债券(QDII)人民币A', 'OEF', 'BOND_GLOBAL', 2, TRUE),
('007360.OF', 'CN_OTC', '易方达中短期美元债(QDII)A人民币', 'OEF', 'BOND_US', 2, TRUE),
('007204.OF', 'CN_OTC', '银华美元债精选债券(QDII)A', 'OEF', 'BOND_US', 2, TRUE),
('1001767346', 'CN_OTC', '摩根国际债券人民币', 'OEF', 'BOND_GLOBAL', 1, FALSE),
('1001767344', 'CN_OTC', '摩根国际债券人民币对冲', 'OEF', 'BOND_GLOBAL', 1, FALSE),
('162411.SZ', 'CN_OTC', '华宝标普油气上游股票人民币A', 'OEF', 'STOCK_GLOBAL', 2, TRUE),
('000369.OF', 'CN_OTC', '广发全球医疗保健A人民币', 'OEF', 'STOCK_GLOBAL', 1, FALSE);

-- ============================================================================
-- 5. 投资组合（portfolio）
-- ============================================================================

INSERT INTO portfolio (code, name, description) VALUES
('PORT001', '个人养老金', '个人养老金投资组合'),
('PORT002', '3322+', '家庭主要投资组合'),
('PORT003', '长期配置', '长期资产配置组合'),
('PORT004', '长赢计划', '长赢计划跟投组合');

-- ============================================================================
-- 6. 索引创建（关键索引）
-- ============================================================================

-- 投资人
CREATE INDEX IF NOT EXISTS idx_investor_code ON investor(code);

-- 组合份额持有（快照模式）
CREATE INDEX IF NOT EXISTS idx_investor_holding_snapshot ON investor_holding(portfolio_code, investor_code, snapshot_date DESC);

-- 申购赎回
CREATE INDEX IF NOT EXISTS idx_subscription_portfolio_date ON subscription(portfolio_code, apply_date DESC);
CREATE INDEX IF NOT EXISTS idx_subscription_status ON subscription(status, confirm_date);

-- 调仓交易
CREATE INDEX IF NOT EXISTS idx_trade_portfolio_date ON trade(portfolio_code, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_product ON trade(product_code, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_status ON trade(status, confirm_date);

-- 持仓快照
CREATE INDEX IF NOT EXISTS idx_portfolio_position_snapshot ON portfolio_position(portfolio_code, product_code, market, snapshot_date DESC);

-- 净值记录
CREATE INDEX IF NOT EXISTS idx_price_record_product_date ON price_record(product_code, market, date DESC);

-- 份额变动事件
CREATE INDEX IF NOT EXISTS idx_share_change_portfolio_date ON share_change_event(portfolio_code, ex_date DESC);
CREATE INDEX IF NOT EXISTS idx_share_change_status ON share_change_event(status);

-- 组合快照
CREATE INDEX IF NOT EXISTS idx_snapshot_portfolio_date ON portfolio_value_snapshot(portfolio_code, snapshot_date DESC);

-- 交易日历
CREATE INDEX IF NOT EXISTS idx_trading_calendar_date ON trading_calendar(date);

-- ============================================================================
-- 说明
-- ============================================================================
-- 1. 默认密码均为 admin123，首次登录后建议修改
-- 2. 交易日历数据需通过 Tushare API 同步，或手动导入
-- 3. 日志系统表索引见 08-日志系统设计.md
-- 4. 产品数据来源：docs/plans/data/fund_products.csv（共124只）

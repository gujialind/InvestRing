#!/usr/bin/env python3
"""
数据库初始化脚本
根据开发设计文档和 SQL 初始化脚本初始化基础数据
数据来源：Docs/init_data.sql
产品总计：124只（现金1只 + ETF 21只 + LOF 18只 + OEF 84只）
"""

import sys
import os
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models.scheduled_task import ScheduledTask
from app.models.portfolio import Portfolio
from app.models.product import Product
from app.models.asset_classification import AssetClassification
from app.constants.asset_names import ASSET_NAME_MAP
from app.models.platform import Platform
from app.models.investor import Investor

def create_tables():
    """创建数据库表"""
    print("创建数据库表...")
    from app.models import (
        investor, portfolio, investor_holding, platform, product, 
        asset_classification, portfolio_position, subscription, trade,
        price_record, share_change_event, portfolio_value_snapshot,
        trading_calendar, login_log, audit_log, scheduled_task,
        task_execution_log, nav_sync_detail, system_error_log, notification,
        idempotency_cache
    )
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")

def init_scheduled_tasks(session):
    """初始化定时任务数据"""
    tasks = [
        {
            'code': 'nav_sync',
            'name': '净值同步',
            'description': '每个交易日07:00同步净值数据。增量同步：从每只基金最后同步日期的下一天到昨天',
            'cron_expr': '0 7 * * 1-5',
            'is_enabled': True
        },
        {
            'code': 'trading_calendar_sync',
            'name': '交易日历同步',
            'description': '每年1月1日02:00同步新年交易日历',
            'cron_expr': '0 2 1 1 *',
            'is_enabled': True
        },
        {
            'code': 'log_cleanup',
            'name': '日志清理',
            'description': '每周日04:00清理过期日志',
            'cron_expr': '0 4 * * 0',
            'is_enabled': True
        }
    ]
    
    for task_data in tasks:
        existing = session.query(ScheduledTask).filter(ScheduledTask.code == task_data['code']).first()
        if not existing:
            task = ScheduledTask(**task_data)
            session.add(task)
            print(f"添加定时任务: {task.name}")
        else:
            print(f"定时任务已存在: {task_data['name']}")
    
    session.commit()

def init_portfolios(session):
    """初始化组合数据"""
    portfolios = [
        {'code': 'PORT001', 'name': '个人养老金', 'description': '个人养老金投资组合'},
        {'code': 'PORT002', 'name': '3322+', 'description': '家庭主要投资组合'},
        {'code': 'PORT003', 'name': '长期配置', 'description': '长期资产配置组合'},
        {'code': 'PORT004', 'name': '长赢计划', 'description': '长赢计划跟投组合'}
    ]
    
    for port_data in portfolios:
        existing = session.query(Portfolio).filter(Portfolio.code == port_data['code']).first()
        if not existing:
            portfolio = Portfolio(**port_data)
            session.add(portfolio)
            print(f"添加组合: {portfolio.name}")
        else:
            print(f"组合已存在: {port_data['name']}")
    
    session.commit()

def init_products(session):
    """初始化产品数据"""
    products = [
        # 4.1 现金类产品
        {'code': 'CASH', 'market': '', 'name': '现金类资产', 'product_type': 'CASH', 'asset_class_code': 'CASH', 'confirm_days': 0, 'is_qdii': False},
        
        # 4.2 ETF基金（场内，T+0确认）
        {'code': '515180.SH', 'market': 'CN_EXCHANGE', 'name': '易方达中证红利ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_VALUE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512070.SH', 'market': 'CN_EXCHANGE', 'name': '易方达沪深300非银ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512200.SH', 'market': 'CN_EXCHANGE', 'name': '南方中证房地产ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '510310.SH', 'market': 'CN_EXCHANGE', 'name': '易方达沪深300发起式ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512800.SH', 'market': 'CN_EXCHANGE', 'name': '华宝中证银行ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512400.SH', 'market': 'CN_EXCHANGE', 'name': '南方中证申万有色金属ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512880.SH', 'market': 'CN_EXCHANGE', 'name': '国泰中证全指证券公司ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '510500.SH', 'market': 'CN_EXCHANGE', 'name': '南方中证500ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 0, 'is_qdii': False},
        {'code': '510580.SH', 'market': 'CN_EXCHANGE', 'name': '易方达中证500ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 0, 'is_qdii': False},
        {'code': '515030.SH', 'market': 'CN_EXCHANGE', 'name': '华夏中证新能源汽车ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '501057.SH', 'market': 'CN_EXCHANGE', 'name': '汇添富中证新能源汽车A', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '159948.SZ', 'market': 'CN_EXCHANGE', 'name': '南方创业板ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '159938.SZ', 'market': 'CN_EXCHANGE', 'name': '广发中证全指医药卫生ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '159847.SZ', 'market': 'CN_EXCHANGE', 'name': '易方达中证医疗ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '512980.SH', 'market': 'CN_EXCHANGE', 'name': '广发中证传媒ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '159940.SZ', 'market': 'CN_EXCHANGE', 'name': '广发中证全指金融地产ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '159920.SZ', 'market': 'CN_EXCHANGE', 'name': '华夏恒生ETF(QDII)', 'product_type': 'ETF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 0, 'is_qdii': True},
        {'code': '164906.SZ', 'market': 'CN_EXCHANGE', 'name': '交银中证海外中国互联网指数', 'product_type': 'ETF', 'asset_class_code': 'STOCK_GLOBAL', 'confirm_days': 0, 'is_qdii': True},
        {'code': '513520.SH', 'market': 'CN_EXCHANGE', 'name': '华夏野村日经225ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_JP', 'confirm_days': 0, 'is_qdii': False},
        {'code': '513050.SH', 'market': 'CN_EXCHANGE', 'name': '易方达中概互联50ETF', 'product_type': 'ETF', 'asset_class_code': 'STOCK_GLOBAL', 'confirm_days': 0, 'is_qdii': True},
        {'code': '518880.SH', 'market': 'CN_EXCHANGE', 'name': '华安黄金易ETF', 'product_type': 'ETF', 'asset_class_code': 'GOLD', 'confirm_days': 0, 'is_qdii': False},
        
        # 4.3 LOF基金（场内，T+0确认）
        {'code': '161039.SZ', 'market': 'CN_EXCHANGE', 'name': '富国中证1000指数增强(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 0, 'is_qdii': False},
        {'code': '160119.SZ', 'market': 'CN_EXCHANGE', 'name': '南方500ETF联接LOF', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 0, 'is_qdii': False},
        {'code': '163417.SZ', 'market': 'CN_EXCHANGE', 'name': '兴全合宜混合(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 0, 'is_qdii': False},
        {'code': '163402.SZ', 'market': 'CN_EXCHANGE', 'name': '兴全趋势投资混合(LOF)', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 0, 'is_qdii': False},
        {'code': '161119.SZ', 'market': 'CN_EXCHANGE', 'name': '易方达中债新综指(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 0, 'is_qdii': False},
        {'code': '161121.SZ', 'market': 'CN_EXCHANGE', 'name': '易方达中证银行指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '502010.SH', 'market': 'CN_EXCHANGE', 'name': '易方达中证全指证券公司指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 0, 'is_qdii': False},
        {'code': '502056.SH', 'market': 'CN_EXCHANGE', 'name': '广发中证医疗指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 0, 'is_qdii': False},
        {'code': '161017.SZ', 'market': 'CN_EXCHANGE', 'name': '富国中证500指数增强(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 0, 'is_qdii': False},
        
        # 4.4 LOF基金（场外，T+1确认）
        {'code': '161039.SZ', 'market': 'CN_OTC', 'name': '富国中证1000指数增强(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '160119.SZ', 'market': 'CN_OTC', 'name': '南方500ETF联接LOF', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '163417.SZ', 'market': 'CN_OTC', 'name': '兴全合宜混合(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '163402.SZ', 'market': 'CN_OTC', 'name': '兴全趋势投资混合(LOF)', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '161119.SZ', 'market': 'CN_OTC', 'name': '易方达中债新综指(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '161121.SZ', 'market': 'CN_OTC', 'name': '易方达中证银行指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '502010.SH', 'market': 'CN_OTC', 'name': '易方达中证全指证券公司指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '502056.SH', 'market': 'CN_OTC', 'name': '广发中证医疗指数(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '161017.SZ', 'market': 'CN_OTC', 'name': '富国中证500指数增强(LOF)A', 'product_type': 'LOF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        
        # 4.5 场外基金（OEF，普通T+1，QDII T+2）
        {'code': '167301.SZ', 'market': 'CN_OTC', 'name': '方正富邦保险主题指数', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006486.OF', 'market': 'CN_OTC', 'name': '广发中证1000ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '009051.OF', 'market': 'CN_OTC', 'name': '易方达中证红利ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_VALUE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '021550.OF', 'market': 'CN_OTC', 'name': '博时中证红利低波动100ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_VALUE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '008115.OF', 'market': 'CN_OTC', 'name': '天弘中证红利低波动100C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_VALUE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001092.OF', 'market': 'CN_OTC', 'name': '广发生物科技指数人民币(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 2, 'is_qdii': True},
        {'code': '320007.OF', 'market': 'CN_OTC', 'name': '诺安成长混合', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '011608.OF', 'market': 'CN_OTC', 'name': '易方达科创板50ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '002656.OF', 'market': 'CN_OTC', 'name': '南方创业板ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '110026.OF', 'market': 'CN_OTC', 'name': '易方达创业板ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '003765.OF', 'market': 'CN_OTC', 'name': '广发创业板ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '017937.OF', 'market': 'CN_OTC', 'name': '易方达中证医疗ETF联接发起式A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001180.OF', 'market': 'CN_OTC', 'name': '广发医药卫生联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001513.OF', 'market': 'CN_OTC', 'name': '易方达信息产业混合', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000727.OF', 'market': 'CN_OTC', 'name': '融通健康产业A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001717.OF', 'market': 'CN_OTC', 'name': '工银前沿医疗股票A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '002708.OF', 'market': 'CN_OTC', 'name': '大摩健康产业混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '004424.OF', 'market': 'CN_OTC', 'name': '汇添富文体娱乐混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '013304.OF', 'market': 'CN_OTC', 'name': '易方达中证科创创业50ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '018134.OF', 'market': 'CN_OTC', 'name': '富国中证大数据产业联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '022939.OF', 'market': 'CN_OTC', 'name': '华夏科创创业50ETF发起式联接Y', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '008127.OF', 'market': 'CN_OTC', 'name': '广发趋势优选灵活配置混合C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '270002.OF', 'market': 'CN_OTC', 'name': '广发稳健增长混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519062.OF', 'market': 'CN_OTC', 'name': '海富通阿尔法对冲混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519222.OF', 'market': 'CN_OTC', 'name': '海富通欣益混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519221.OF', 'market': 'CN_OTC', 'name': '海富通欣益混合C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519697.OF', 'market': 'CN_OTC', 'name': '交银优势行业混合', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000136.OF', 'market': 'CN_OTC', 'name': '民生加银策略精选混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '202023.OF', 'market': 'CN_OTC', 'name': '南方优选成长混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001064.OF', 'market': 'CN_OTC', 'name': '广发中证环保产业联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '004241.OF', 'market': 'CN_OTC', 'name': '中欧时代先锋股票C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000968.OF', 'market': 'CN_OTC', 'name': '广发养老指数A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '110022.OF', 'market': 'CN_OTC', 'name': '易方达消费行业股票', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519915.OF', 'market': 'CN_OTC', 'name': '富国消费主题混合A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000248.OF', 'market': 'CN_OTC', 'name': '汇添富中证主要消费ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000051.OF', 'market': 'CN_OTC', 'name': '华夏沪深300ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '007028.OF', 'market': 'CN_OTC', 'name': '易方达中证500ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '110020.OF', 'market': 'CN_OTC', 'name': '易方达沪深300ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '110003.OF', 'market': 'CN_OTC', 'name': '易方达上证50增强A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000478.OF', 'market': 'CN_OTC', 'name': '建信中证500指数增强A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '004752.OF', 'market': 'CN_OTC', 'name': '广发中证传媒ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001469.OF', 'market': 'CN_OTC', 'name': '广发中证全指金融地产联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000942.OF', 'market': 'CN_OTC', 'name': '广发信息技术联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_GROWTH', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001052.OF', 'market': 'CN_OTC', 'name': '华夏中证500ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_SMALL', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001552.OF', 'market': 'CN_OTC', 'name': '天弘中证证券保险A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '001595.OF', 'market': 'CN_OTC', 'name': '天弘中证银行ETF联接C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519671.OF', 'market': 'CN_OTC', 'name': '银河沪深300价值指数A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '100038.OF', 'market': 'CN_OTC', 'name': '富国沪深300指数增强A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '022979.OF', 'market': 'CN_OTC', 'name': '华夏中证A500ETF联接Y', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '022959.OF', 'market': 'CN_OTC', 'name': '华夏上证50ETF联接Y', 'product_type': 'OEF', 'asset_class_code': 'STOCK_CN_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006381.OF', 'market': 'CN_OTC', 'name': '华夏恒生ETF联接C', 'product_type': 'OEF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000071.OF', 'market': 'CN_OTC', 'name': '华夏恒生ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 1, 'is_qdii': False},
        {'code': '012957.OF', 'market': 'CN_OTC', 'name': '天弘恒生科技指数(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 2, 'is_qdii': True},
        {'code': '014424.OF', 'market': 'CN_OTC', 'name': '博时恒生医疗保健ETF发起式联接(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 2, 'is_qdii': True},
        {'code': '013308.OF', 'market': 'CN_OTC', 'name': '易方达恒生科技ETF联接(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_HK_LARGE', 'confirm_days': 2, 'is_qdii': True},
        {'code': '270042.OF', 'market': 'CN_OTC', 'name': '广发纳指100ETF联接人民币(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '050025.OF', 'market': 'CN_OTC', 'name': '博时标普500ETF联接A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '016452.OF', 'market': 'CN_OTC', 'name': '南方纳斯达克100指数发起(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '006327.OF', 'market': 'CN_OTC', 'name': '易方达中证海外50ETF联接人民币A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_GLOBAL', 'confirm_days': 2, 'is_qdii': True},
        {'code': '007823.OF', 'market': 'CN_OTC', 'name': '天弘弘择短债A', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006793.OF', 'market': 'CN_OTC', 'name': '交银稳鑫短债债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '012348.OF', 'market': 'CN_OTC', 'name': '嘉实60天滚动持有短债A', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006662.OF', 'market': 'CN_OTC', 'name': '易方达安悦超短债A', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006663.OF', 'market': 'CN_OTC', 'name': '易方达安悦超短债C', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '014427.OF', 'market': 'CN_OTC', 'name': '富国中证同业存单AAA指数7天持有', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '015822.OF', 'market': 'CN_OTC', 'name': '易方达中证同业存单AAA指数7天持有', 'product_type': 'OEF', 'asset_class_code': 'BOND_SHORT', 'confirm_days': 1, 'is_qdii': False},
        {'code': '003376.OF', 'market': 'CN_OTC', 'name': '广发中债7-10年国开债指数A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '519152.OF', 'market': 'CN_OTC', 'name': '新华纯债添利债券发起A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '110037.OF', 'market': 'CN_OTC', 'name': '易方达纯债债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '270048.OF', 'market': 'CN_OTC', 'name': '广发纯债债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000147.OF', 'market': 'CN_OTC', 'name': '易方达高等级信用债A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '006484.OF', 'market': 'CN_OTC', 'name': '广发中债1-3年国开债指数A', 'product_type': 'OEF', 'asset_class_code': 'BOND_LONG', 'confirm_days': 1, 'is_qdii': False},
        {'code': '485111.OF', 'market': 'CN_OTC', 'name': '工银瑞信双利债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '270044.OF', 'market': 'CN_OTC', 'name': '广发双债添利债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '202101.OF', 'market': 'CN_OTC', 'name': '南方宝元债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '000563.OF', 'market': 'CN_OTC', 'name': '南方通利债券A', 'product_type': 'OEF', 'asset_class_code': 'BOND_MIXED', 'confirm_days': 1, 'is_qdii': False},
        {'code': '004419.OF', 'market': 'CN_OTC', 'name': '汇添富美元债债券(QDII)人民币A', 'product_type': 'OEF', 'asset_class_code': 'BOND_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '100050.OF', 'market': 'CN_OTC', 'name': '富国全球债券(QDII)人民币A', 'product_type': 'OEF', 'asset_class_code': 'BOND_GLOBAL', 'confirm_days': 2, 'is_qdii': True},
        {'code': '007360.OF', 'market': 'CN_OTC', 'name': '易方达中短期美元债(QDII)A人民币', 'product_type': 'OEF', 'asset_class_code': 'BOND_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '007204.OF', 'market': 'CN_OTC', 'name': '银华美元债精选债券(QDII)A', 'product_type': 'OEF', 'asset_class_code': 'BOND_US', 'confirm_days': 2, 'is_qdii': True},
        {'code': '1001767346', 'market': 'HK_MUTUAL', 'name': '摩根国际债券人民币', 'product_type': 'OEF', 'asset_class_code': 'BOND_GLOBAL', 'confirm_days': 1, 'is_qdii': False, 'data_source': 'akshare'},
        {'code': '1001767344', 'market': 'HK_MUTUAL', 'name': '摩根国际债券人民币对冲', 'product_type': 'OEF', 'asset_class_code': 'BOND_GLOBAL', 'confirm_days': 1, 'is_qdii': False, 'data_source': 'akshare'},
        {'code': '162411.SZ', 'market': 'CN_OTC', 'name': '华宝标普油气上游股票人民币A', 'product_type': 'OEF', 'asset_class_code': 'STOCK_GLOBAL', 'confirm_days': 2, 'is_qdii': True},
        {'code': '000369.OF', 'market': 'CN_OTC', 'name': '广发全球医疗保健A人民币', 'product_type': 'OEF', 'asset_class_code': 'STOCK_GLOBAL', 'confirm_days': 1, 'is_qdii': False},
    ]
    
    session.query(Product).filter(
        Product.code.in_(['1001767344', '1001767346']),
        Product.market == 'CN_OTC',
    ).delete(synchronize_session=False)
    session.commit()
    
    for prod_data in products:
        existing = session.query(Product).filter(
            Product.code == prod_data['code'], 
            Product.market == prod_data['market']
        ).first()
        if not existing:
            product = Product(**prod_data)
            session.add(product)
            print(f"添加产品: {product.code} - {product.name}")
        else:
            print(f"产品已存在: {prod_data['code']} - {prod_data['name']}")
    
    session.commit()

def init_asset_classification(session):
    """初始化资产分类数据"""
    classifications = [
        {'code': 'STOCK_CN_LARGE', 'asset_type': '股票', 'asset_category': '国内股票', 'asset_subcat': '大盘', 'description': '国内大盘股票'},
        {'code': 'STOCK_CN_SMALL', 'asset_type': '股票', 'asset_category': '国内股票', 'asset_subcat': '中小盘', 'description': '国内中小盘股票'},
        {'code': 'STOCK_CN_VALUE', 'asset_type': '股票', 'asset_category': '国内股票', 'asset_subcat': '价值', 'description': '国内价值风格股票'},
        {'code': 'STOCK_CN_GROWTH', 'asset_type': '股票', 'asset_category': '国内股票', 'asset_subcat': '成长', 'description': '国内成长风格股票'},
        {'code': 'STOCK_CN_MIXED', 'asset_type': '股票', 'asset_category': '国内股票', 'asset_subcat': '综合', 'description': '国内综合风格股票'},
        {'code': 'STOCK_HK_LARGE', 'asset_type': '股票', 'asset_category': '港股', 'asset_subcat': '大盘', 'description': '港股大盘股票'},
        {'code': 'STOCK_HK_SMALL', 'asset_type': '股票', 'asset_category': '港股', 'asset_subcat': '中小盘', 'description': '港股中小盘股票'},
        {'code': 'STOCK_US', 'asset_type': '股票', 'asset_category': '美股', 'asset_subcat': '美股', 'description': '美国股票'},
        {'code': 'STOCK_EU', 'asset_type': '股票', 'asset_category': '欧洲', 'asset_subcat': '欧洲', 'description': '欧洲股票'},
        {'code': 'STOCK_JP', 'asset_type': '股票', 'asset_category': '日本', 'asset_subcat': '日本', 'description': '日本股票'},
        {'code': 'STOCK_GLOBAL', 'asset_type': '股票', 'asset_category': '海外股票', 'asset_subcat': '全球', 'description': '全球股票'},
        {'code': 'BOND_SHORT', 'asset_type': '债券', 'asset_category': '国内债券', 'asset_subcat': '短债', 'description': '国内短期债券'},
        {'code': 'BOND_LONG', 'asset_type': '债券', 'asset_category': '国内债券', 'asset_subcat': '中长债', 'description': '国内中长期债券'},
        {'code': 'BOND_MIXED', 'asset_type': '债券', 'asset_category': '国内债券', 'asset_subcat': '综合债', 'description': '国内综合债券'},
        {'code': 'BOND_US', 'asset_type': '债券', 'asset_category': '国际债券', 'asset_subcat': '美债', 'description': '美国债券'},
        {'code': 'BOND_GLOBAL', 'asset_type': '债券', 'asset_category': '国际债券', 'asset_subcat': '全球', 'description': '全球债券'},
        {'code': 'GOLD', 'asset_type': '黄金', 'asset_category': '黄金', 'asset_subcat': '黄金', 'description': '黄金资产'},
        {'code': 'CASH', 'asset_type': '现金', 'asset_category': '现金', 'asset_subcat': '现金', 'description': '现金类资产（含货币基金）'}
    ]
    
    for class_data in classifications:
        # asset_name 单一事实来源为 ASSET_NAME_MAP（与迁移 0007 回填共用）
        class_data['asset_name'] = ASSET_NAME_MAP[class_data['code']]
        existing = session.query(AssetClassification).filter(AssetClassification.code == class_data['code']).first()
        if not existing:
            classification = AssetClassification(**class_data)
            session.add(classification)
            print(f"添加资产分类: {class_data['code']}")
        else:
            # 老库脚本级兜底：仅补 NULL，不覆盖迁移回填或人工修改的值
            if existing.asset_name is None:
                existing.asset_name = class_data['asset_name']
                print(f"回填资产分类名目: {class_data['code']}")
            else:
                print(f"资产分类已存在: {class_data['code']}")
    
    session.commit()

def init_platforms(session):
    """初始化平台数据"""
    platforms = [
        {'code': 'MYCF', 'name': '蚂蚁财富', 'platform_type': '第三方平台'},
        {'code': 'TXLCT', 'name': '腾讯理财通', 'platform_type': '第三方平台'},
        {'code': 'QM', 'name': '且慢', 'platform_type': '第三方平台'},
        {'code': 'JDFC', 'name': '京东金融', 'platform_type': '第三方平台'},
        {'code': 'LCMF', 'name': '理财魔方', 'platform_type': '第三方平台'},
        {'code': 'TTJJ', 'name': '天天基金', 'platform_type': '第三方平台'},
        {'code': 'YZYX', 'name': '有知有行', 'platform_type': '第三方平台'},
        {'code': 'HBZQ', 'name': '华宝证券', 'platform_type': '券商'},
        {'code': 'HTZQ', 'name': '华泰证券', 'platform_type': '券商'},
        {'code': 'JTYY', 'name': '交通银行', 'platform_type': '银行'},
        {'code': 'ZGYH', 'name': '中国银行', 'platform_type': '银行'},
        {'code': 'NYYH', 'name': '农业银行', 'platform_type': '银行'},
        {'code': 'JSYH', 'name': '建设银行', 'platform_type': '银行'},
        {'code': 'WSYH', 'name': '微众银行', 'platform_type': '银行'},
        {'code': 'WSBK', 'name': '网商银行', 'platform_type': '银行'},
        {'code': 'ZBYH', 'name': '众邦银行', 'platform_type': '银行'},
        {'code': 'ZXYH', 'name': '振兴银行', 'platform_type': '银行'},
        {'code': 'SXYH', 'name': '三湘银行', 'platform_type': '银行'},
        {'code': 'YFFCJJ', 'name': '易方达基金', 'platform_type': '基金公司'},
        {'code': 'GFJJ', 'name': '广发基金', 'platform_type': '基金公司'},
        {'code': 'NFJJ', 'name': '南方基金', 'platform_type': '基金公司'},
        {'code': 'FGJJ', 'name': '富国基金', 'platform_type': '基金公司'},
        {'code': 'RTJJ', 'name': '融通基金', 'platform_type': '基金公司'},
        {'code': 'BSJJ', 'name': '博时基金', 'platform_type': '基金公司'},
        {'code': 'HTFJJ', 'name': '汇添富基金', 'platform_type': '基金公司'},
        {'code': 'YHJJ', 'name': '银华基金', 'platform_type': '基金公司'},
        {'code': 'HXJJ', 'name': '华夏基金', 'platform_type': '基金公司'},
        {'code': 'MGJJ', 'name': '摩根基金', 'platform_type': '基金公司'},
        {'code': 'ZB', 'name': '纸币', 'platform_type': '其他'},
        {'code': 'YSK', 'name': '应收款', 'platform_type': '其他'}
    ]
    
    for plat_data in platforms:
        existing = session.query(Platform).filter(Platform.code == plat_data['code']).first()
        if not existing:
            platform = Platform(**plat_data)
            session.add(platform)
            print(f"添加平台: {platform.name}")
        else:
            print(f"平台已存在: {plat_data['name']}")
    
    session.commit()

def init_admin_user(session):
    """初始化管理员用户"""
    password = 'admin123'
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=10)
    password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    admin_data = {
        'code': 'ADMIN',
        'name': '系统管理员',
        'role': 'admin',
        'password_hash': password_hash
    }
    
    existing = session.query(Investor).filter(Investor.code == 'ADMIN').first()
    if not existing:
        admin = Investor(**admin_data)
        session.add(admin)
        print("添加管理员用户: ADMIN")
    else:
        print("管理员用户已存在")
    
    session.commit()

def main():
    """执行初始化"""
    print("=== 开始数据库初始化 ===")
    
    # 先创建数据库表
    create_tables()
    
    # 创建数据库连接
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("\n1. 初始化资产分类...")
        init_asset_classification(session)
        
        print("\n2. 初始化平台...")
        init_platforms(session)
        
        print("\n3. 初始化产品...")
        init_products(session)
        
        print("\n4. 初始化组合...")
        init_portfolios(session)
        
        print("\n5. 初始化定时任务...")
        init_scheduled_tasks(session)
        
        print("\n6. 初始化管理员用户...")
        init_admin_user(session)
        
        print("\n=== 数据库初始化完成 ===")
        
    except Exception as e:
        print(f"\n初始化失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()

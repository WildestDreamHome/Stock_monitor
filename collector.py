""" A股数据采集器 - 主程序 ======================== 功能：自动采集股票行情、新闻、财报数据，存入本地数据库 使用方法： 手动运行一次：python collector.py 自动定时运行：python scheduler.py 作者：你的第一个量化项目 """

import os
import sys
import sqlite3
import logging
import time
from datetime import datetime, timedelta

import yaml
import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ============================================================
# 第1部分：基础设置
# ============================================================

# 获取当前脚本所在目录（这样无论从哪里运行脚本，路径都是对的）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取配置文件
def load_config():
    """读取 config.yaml 配置文件"""
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# 设置日志（用来记录程序运行状态，方便排查问题）
def setup_logging(log_path):
    """配置日志系统"""
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,  # 日志级别：INFO=普通信息, DEBUG=详细信息
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),  # 写入文件
            logging.StreamHandler(sys.stdout),                  # 同时输出到屏幕
        ]
    )
    return logging.getLogger(__name__)

# 初始化数据库
def init_database(db_path):
    """创建数据库和表结构（只在第一次运行时创建）"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 股票行情表
    cursor.execute(""" CREATE TABLE IF NOT EXISTS market_data ( id INTEGER PRIMARY KEY AUTOINCREMENT, stock_code TEXT NOT NULL, -- 股票代码 stock_name TEXT, -- 股票名称 date TEXT NOT NULL, -- 日期 open_price REAL, -- 开盘价 close_price REAL, -- 收盘价 high_price REAL, -- 最高价 low_price REAL, -- 最低价 volume REAL, -- 成交量（手） amount REAL, -- 成交额（元） turnover_rate REAL, -- 换手率 change_pct REAL, -- 涨跌幅(%) collected_at TEXT DEFAULT CURRENT_TIMESTAMP, -- 采集时间 UNIQUE(stock_code, date) -- 同一只股票同一天只存一条 ) """)
    
    # 新闻表
    cursor.execute(""" CREATE TABLE IF NOT EXISTS news_data ( id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, -- 新闻标题 content TEXT, -- 新闻内容摘要 source TEXT, -- 来源 url TEXT, -- 原文链接 publish_time TEXT, -- 发布时间 related_stocks TEXT, -- 相关股票代码（逗号分隔） sentiment_score REAL, -- 情感得分（后续阶段添加） collected_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(title, publish_time) ) """)
    
    # 财报数据表
    cursor.execute(""" CREATE TABLE IF NOT EXISTS financial_data ( id INTEGER PRIMARY KEY AUTOINCREMENT, stock_code TEXT NOT NULL, stock_name TEXT, report_date TEXT, -- 报告期 total_revenue REAL, -- 营业总收入 net_profit REAL, -- 净利润 total_assets REAL, -- 总资产 total_liabilities REAL, -- 总负债 eps REAL, -- 每股收益 roe REAL, -- 净资产收益率 collected_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(stock_code, report_date) ) """)
    
    conn.commit()
    return conn


# ============================================================
# 第2部分：股票行情数据采集
# ============================================================

def collect_market_data(conn, config, logger):
    """ 采集股票行情数据 使用 AKShare 获取A股历史行情 """
    cursor = conn.cursor()
    stocks = config["stocks"]
    history_days = config["collection"]["history_days"]
    start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    
    logger.info(f"=== 开始采集行情数据，共 {len(stocks)} 只股票 ===")
    
    for stock_info in stocks:
        code = stock_info["code"]
        try:
            logger.info(f"正在采集 {code} 的行情数据...")
            
            # AKShare 获取A股日K线数据
            # stock_zh_a_hist 返回的列名是中文的
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            if df is None or df.empty:
                logger.warning(f" {code} 没有获取到数据")
                continue
            
            # 获取股票名称（从数据的第一行取）
            stock_name = ""
            
            # 遍历每一行数据，存入数据库
            count = 0
            for _, row in df.iterrows():
                try:
                    cursor.execute(""" INSERT OR REPLACE INTO market_data (stock_code, stock_name, date, open_price, close_price, high_price, low_price, volume, amount, turnover_rate, change_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) """, (
                        code,
                        stock_name,
                        str(row["日期"]),
                        float(row["开盘"]),
                        float(row["收盘"]),
                        float(row["最高"]),
                        float(row["最低"]),
                        float(row["成交量"]),
                        float(row["成交额"]),
                        float(row.get("换手率", 0)),
                        float(row.get("涨跌幅", 0)),
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f" 存入单条数据失败: {e}")
            
            conn.commit()
            logger.info(f" {code} 采集完成，共 {count} 条记录")
            
            # 每只股票之间暂停1-2秒，避免请求太快被封
            time.sleep(1.5)
            
        except Exception as e:
            logger.error(f" 采集 {code} 失败: {e}")
            continue
    
    logger.info("=== 行情数据采集完成 ===\n")


# ============================================================
# 第3部分：财经新闻采集
# ============================================================

def collect_news(conn, config, logger):
    """ 采集财经新闻 使用 AKShare 获取东方财富财经新闻 """
    cursor = conn.cursor()
    
    if not config["collection"]["enable_news"]:
        logger.info("新闻采集已关闭，跳过")
        return
    
    logger.info("=== 开始采集财经新闻 ===")
    
    try:
        # 方法1：使用 AKShare 获取财经新闻
        # 东方财富全局新闻
        df_news = ak.stock_news_em(symbol="300059")
        
        if df_news is not None and not df_news.empty:
            count = 0
            for _, row in df_news.head(20).iterrows():  # 只取最新20条
                try:
                    cursor.execute(""" INSERT OR IGNORE INTO news_data (title, content, source, url, publish_time, related_stocks) VALUES (?, ?, ?, ?, ?, ?) """, (
                        str(row.get("新闻标题", "")),
                        str(row.get("新闻内容", ""))[:500],  # 只存前500字
                        str(row.get("文章来源", "东方财富")),
                        str(row.get("新闻链接", "")),
                        str(row.get("发布时间", "")),
                        str(row.get("相关股票", "")),
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f" 存入新闻失败: {e}")
            
            conn.commit()
            logger.info(f" AKShare新闻采集完成，新增 {count} 条")
        
        time.sleep(1)
        
        # 方法2：爬取新浪财经滚动新闻（作为补充）
        try:
            url = "https://finance.sina.com.cn/roll/index.d.html?cid=56588"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 查找新闻链接
            news_links = soup.select("ul.list_009 li a")
            sina_count = 0
            
            for link in news_links[:15]:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if title and href:
                    try:
                        cursor.execute(""" INSERT OR IGNORE INTO news_data (title, content, source, url, publish_time) VALUES (?, ?, ?, ?, ?) """, (title, "", "新浪财经", href, datetime.now().strftime("%Y-%m-%d %H:%M")))
                        sina_count += 1
                    except Exception:
                        pass
            
            conn.commit()
            logger.info(f" 新浪财经采集完成，新增 {sina_count} 条")
            
        except Exception as e:
            logger.warning(f" 新浪财经采集失败（不影响整体运行）: {e}")
        
    except Exception as e:
        logger.error(f" 新闻采集整体失败: {e}")
    
    logger.info("=== 新闻采集完成 ===\n")


# ============================================================
# 第4部分：财报数据采集
# ============================================================

def collect_financial_data(conn, config, logger):
    """ 采集财报核心数据 使用 AKShare 获取上市公司财务指标 """
    cursor = conn.cursor()
    
    if not config["collection"]["enable_financial_reports"]:
        logger.info("财报采集已关闭，跳过")
        return
    
    logger.info("=== 开始采集财报数据 ===")
    
    for stock_info in config["stocks"]:
        code = stock_info["code"]
        try:
            logger.info(f"正在采集 {code} 的财报数据...")
            
            # 获取个股财务指标
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
            
            if df is not None and not df.empty:
                # 只取最近2年的数据
                for _, row in df.head(4).iterrows():
                    try:
                        cursor.execute(""" INSERT OR REPLACE INTO financial_data (stock_code, stock_name, report_date, total_revenue, net_profit, eps, roe) VALUES (?, ?, ?, ?, ?, ?, ?) """, (
                            code,
                            "",
                            str(row.get("报告期", "")),
                            float(str(row.get("营业总收入", "0")).replace(",", "")) if row.get("营业总收入") else None,
                            float(str(row.get("净利润", "0")).replace(",", "")) if row.get("净利润") else None,
                            float(str(row.get("每股收益", "0")).replace(",", "")) if row.get("每股收益") else None,
                            float(str(row.get("净资产收益率", "0")).replace("%", "")) if row.get("净资产收益率") else None,
                        ))
                    except Exception as e:
                        logger.error(f" 存入财报数据失败: {e}")
                
                conn.commit()
                logger.info(f" {code} 财报采集完成")
            else:
                logger.warning(f" {code} 未获取到财报数据")
            
            time.sleep(2)  # 财报数据请求间隔长一些
            
        except Exception as e:
            logger.error(f" 采集 {code} 财报失败: {e}")
            continue
    
    logger.info("=== 财报数据采集完成 ===\n")


# ============================================================
# 第5部分：生成简报
# ============================================================

def generate_summary(conn, logger):
    """ 生成今日数据简报（打印到日志） 后续阶段会做成推送到手机的功能 """
    cursor = conn.cursor()
    
    logger.info("=" * 50)
    logger.info("📊 数据简报")
    logger.info("=" * 50)
    
    # 统计各表数据量
    for table in ["market_data", "news_data", "financial_data"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        logger.info(f" {table}: {count} 条记录")
    
    # 最新行情概览
    logger.info("\n--- 最新行情 ---")
    cursor.execute(""" SELECT stock_code, date, close_price, change_pct FROM market_data WHERE date = (SELECT MAX(date) FROM market_data) ORDER BY change_pct DESC """)
    for row in cursor.fetchall():
        emoji = "📈" if row[3] and row[3] > 0 else "📉"
        logger.info(f" {emoji} {row[0]} | {row[1]} | 收盘:{row[2]} | 涨跌:{row[3]}%")
    
    # 最新新闻
    logger.info("\n--- 最新新闻 ---")
    cursor.execute(""" SELECT title, source, publish_time FROM news_data ORDER BY collected_at DESC LIMIT 5 """)
    for row in cursor.fetchall():
        logger.info(f" 📰 [{row[1]}] {row[0]}")
    
    logger.info("=" * 50)
    logger.info("简报生成完毕\n")


# ============================================================
# 主程序入口
# ============================================================

def run_collection():
    """运行一次完整的数据采集"""
    # 加载配置
    config = load_config()
    
    # 设置路径
    db_path = os.path.join(BASE_DIR, config["storage"]["database_path"])
    log_path = os.path.join(BASE_DIR, config["storage"]["log_path"])
    
    # 初始化
    logger = setup_logging(log_path)
    logger.info("🚀 数据采集开始运行")
    
    # 初始化数据库
    conn = init_database(db_path)
    
    try:
        # 依次采集各类数据
        collect_market_data(conn, config, logger)
        collect_news(conn, config, logger)
        collect_financial_data(conn, config, logger)
        
        # 生成简报
        generate_summary(conn, logger)
        
        logger.info("✅ 本轮采集全部完成！")
        
    except Exception as e:
        logger.error(f"❌ 采集过程出错: {e}", exc_info=True)
    finally:
        conn.close()


if __name__ == "__main__":
    run_collection()

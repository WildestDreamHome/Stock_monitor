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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def setup_logging(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger(__name__)

def init_database(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            date TEXT NOT NULL,
            open_price REAL,
            close_price REAL,
            high_price REAL,
            low_price REAL,
            volume REAL,
            amount REAL,
            turnover_rate REAL,
            change_pct REAL,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            source TEXT,
            url TEXT,
            publish_time TEXT,
            related_stocks TEXT,
            sentiment_score REAL,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(title, publish_time)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            report_date TEXT,
            total_revenue REAL,
            net_profit REAL,
            total_assets REAL,
            total_liabilities REAL,
            eps REAL,
            roe REAL,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, report_date)
        )
    """)
    conn.commit()
    return conn

def collect_market_data(conn, config, logger):
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
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            if df is None or df.empty:
                logger.warning(f"  {code} 没有获取到数据")
                continue
            stock_name = ""
            count = 0
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO market_data 
                        (stock_code, stock_name, date, open_price, close_price, 
                         high_price, low_price, volume, amount, turnover_rate, change_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
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
                    logger.error(f"  存入单条数据失败：{e}")
            conn.commit()
            logger.info(f"  {code} 采集完成，共 {count} 条记录")
            time.sleep(1.5)
        except Exception as e:
            logger.error(f"  采集 {code} 失败：{e}")
            continue
    logger.info("=== 行情数据采集完成 ===\n")

def collect_news(conn, config, logger):
    cursor = conn.cursor()
    if not config["collection"]["enable_news"]:
        logger.info("新闻采集已关闭，跳过")
        return
    logger.info("=== 开始采集财经新闻 ===")
    try:
        df_news = ak.stock_news_em(symbol="300059")
        if df_news is not None and not df_news.empty:
            count = 0
            for _, row in df_news.head(20).iterrows():
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO news_data 
                        (title, content, source, url, publish_time, related_stocks)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        str(row.get("新闻标题", "")),
                        str(row.get("新闻内容", ""))[:500],
                        str(row.get("文章来源", "东方财富")),
                        str(row.get("新闻链接", "")),
                        str(row.get("发布时间", "")),
                        str(row.get("相关股票", "")),
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f"  存入新闻失败：{e}")
            conn.commit()
            logger.info(f"  AKShare 新闻采集完成，新增 {count} 条")
        time.sleep(1)
        try:
            url = "https://finance.sina.com.cn/roll/index.d.html?cid=56588"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            news_links = soup.select("ul.list_009 li a")
            sina_count = 0
            for link in news_links[:15]:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if title and href:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO news_data 
                            (title, content, source, url, publish_time)
                            VALUES (?, ?, ?, ?, ?)
                        """, (title, "", "新浪财经", href, datetime.now().strftime("%Y-%m-%d %H:%M")))
                        sina_count += 1
                    except Exception:
                        pass
            conn.commit()
            logger.info(f"  新浪财经采集完成，新增 {sina_count} 条")
        except Exception as e:
            logger.warning(f"  新浪财经采集失败：{e}")
    except Exception as e:
        logger.error(f"  新闻采集整体失败：{e}")
    logger.info("=== 新闻采集完成 ===\n")

def collect_financial_data(conn, config, logger):
    cursor = conn.cursor()
    if not config["collection"]["enable_financial_reports"]:
        logger.info("财报采集已关闭，跳过")
        return
    logger.info("=== 开始采集财报数据 ===")
    for stock_info in config["stocks"]:
        code = stock_info["code"]
        try:
            logger.info(f"正在采集 {code} 的财报数据...")
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
            if df is not None and not df.empty:
                for _, row in df.head(4).iterrows():
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO financial_data
                            (stock_code, stock_name, report_date, total_revenue, 
                             net_profit, eps, roe)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            code,
                            "",
                            str(row.get("报告期", "")),
                            float(str(row.get("营业总收入", "0")).replace(",", "")) if row.get("营业总收入") else None,
                            float(str(row.get("净利润", "0")).replace(",", "")) if row.get("净利润") else None,
                            float(str(row.get("每股收益", "0")).replace(",", "")) if row.get("每股收益") else None,
                            float(str(row.get("净资产收益率", "0")).replace("%", "")) if row.get("净资产收益率") else None,
                        ))
                    except Exception as e:
                        logger.error(f"  存入财报数据失败：{e}")
                conn.commit()
                logger.info(f"  {code} 财报采集完成")
            else:
                logger.warning(f"  {code} 未获取到财报数据")
            time.sleep(2)
        except Exception as e:
            logger.error(f"  采集 {code} 财报失败：{e}")
            continue
    logger.info("=== 财报数据采集完成 ===\n")

def generate_summary(conn, logger):
    cursor = conn.cursor()
    logger.info("=" * 50)
    logger.info("数据简报")
    logger.info("=" * 50)
    for table in ["market_data", "news_data", "financial_data"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        logger.info(f"  {table}: {count} 条记录")
    logger.info("\n--- 最新行情 ---")
    cursor.execute("""
        SELECT stock_code, date, close_price, change_pct 
        FROM market_data 
        WHERE date = (SELECT MAX(date) FROM market_data)
        ORDER BY change_pct DESC
    """)
    for row in cursor.fetchall():
        emoji = "UP" if row[3] and row[3] > 0 else "DOWN"
        logger.info(f"  {emoji} {row[0]} | {row[1]} | 收盘:{row[2]} | 涨跌:{row[3]}%")
    logger.info("\n--- 最新新闻 ---")
    cursor.execute("""
        SELECT title, source, publish_time 
        FROM news_data 
        ORDER BY collected_at DESC 
        LIMIT 5
    """)
    for row in cursor.fetchall():
        logger.info(f"  [{row[1]}] {row[0]}")
    logger.info("=" * 50)
    logger.info("简报生成完毕\n")

def run_collection():
    config = load_config()
    db_path = os.path.join(BASE_DIR, config["storage"]["database_path"])
    log_path = os.path.join(BASE_DIR, config["storage"]["log_path"])
    logger = setup_logging(log_path)
    logger.info("数据采集开始运行")
    conn = init_database(db_path)
    try:
        collect_market_data(conn, config, logger)
        collect_news(conn, config, logger)
        collect_financial_data(conn, config, logger)
        generate_summary(conn, logger)
        logger.info("本轮采集全部完成！")
    except Exception as e:
        logger.error(f"采集过程出错：{e}", exc_info=True)
    finally:
        conn.close()

if __name__ == "__main__":
    run_collection()
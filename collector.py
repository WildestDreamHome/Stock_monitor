import os, sys, sqlite3, logging, time, yaml, akshare as ak, pandas as pd, requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_config():
    with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def setup_logging(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
    return logging.getLogger(__name__)

def init_database(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS market_data (id INTEGER PRIMARY KEY AUTOINCREMENT, stock_code TEXT NOT NULL, stock_name TEXT, date TEXT NOT NULL, open_price REAL, close_price REAL, high_price REAL, low_price REAL, volume REAL, amount REAL, turnover_rate REAL, change_pct REAL, collected_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(stock_code, date))")
    c.execute("CREATE TABLE IF NOT EXISTS news_data (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT, source TEXT, url TEXT, publish_time TEXT, related_stocks TEXT, sentiment_score REAL, collected_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(title, publish_time))")
    c.execute("CREATE TABLE IF NOT EXISTS financial_data (id INTEGER PRIMARY KEY AUTOINCREMENT, stock_code TEXT NOT NULL, stock_name TEXT, report_date TEXT, total_revenue REAL, net_profit REAL, total_assets REAL, total_liabilities REAL, eps REAL, roe REAL, collected_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(stock_code, report_date))")
    conn.commit()
    return conn

def collect_market_data(conn, config, logger):
    c = conn.cursor()
    stocks = config["stocks"]
    days = config["collection"]["history_days"]
    sd = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    ed = datetime.now().strftime("%Y%m%d")
    logger.info(f"=== 开始采集行情数据，共 {len(stocks)} 只股票 ===")
    for s in stocks:
        code = s["code"]
        name = s.get("name", "")
        try:
            logger.info(f"正在采集 {code} {name}...")
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=sd, end_date=ed, adjust="qfq")
            if df is None or df.empty:
                logger.warning(f"  {code} 无数据")
                continue
            cnt = 0
            for _, row in df.iterrows():
                c.execute("INSERT OR REPLACE INTO market_data (stock_code,stock_name,date,open_price,close_price,high_price,low_price,volume,amount,turnover_rate,change_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (code, name, str(row["日期"]), float(row["开盘"]), float(row["收盘"]), float(row["最高"]), float(row["最低"]), float(row["成交量"]), float(row["成交额"]), float(row.get("换手率",0)), float(row.get("涨跌幅",0))))
                cnt += 1
            conn.commit()
            logger.info(f"  {code} {name} 完成，{cnt} 条")
            time.sleep(1.5)
        except Exception as e:
            logger.error(f"  {code} 失败：{e}")
    logger.info("=== 行情采集完成 ===\n")

def collect_news(conn, config, logger):
    c = conn.cursor()
    if not config["collection"]["enable_news"]:
        return
    logger.info("=== 开始采集新闻 ===")
    try:
        df = ak.stock_news_em(symbol="300059")
        if df is not None and not df.empty:
            cnt = 0
            for _, row in df.head(20).iterrows():
                c.execute("INSERT OR IGNORE INTO news_data (title,content,source,url,publish_time,related_stocks) VALUES (?,?,?,?,?,?)",
                    (str(row.get("新闻标题","")), str(row.get("新闻内容",""))[:500], str(row.get("文章来源","东方财富")), str(row.get("新闻链接","")), str(row.get("发布时间","")), str(row.get("相关股票",""))))
                cnt += 1
            conn.commit()
            logger.info(f"  东方财富新闻：{cnt} 条")
        time.sleep(1)
    except Exception as e:
        logger.error(f"  新闻采集失败：{e}")
    logger.info("=== 新闻采集完成 ===\n")

def collect_financial_data(conn, config, logger):
    c = conn.cursor()
    if not config["collection"]["enable_financial_reports"]:
        return
    logger.info("=== 开始采集财报 ===")
    for s in config["stocks"]:
        code = s["code"]
        name = s.get("name", "")
        try:
            logger.info(f"正在采集 {code} {name} 财报...")
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
            if df is not None and not df.empty:
                for _, row in df.head(4).iterrows():
                    c.execute("INSERT OR REPLACE INTO financial_data (stock_code,stock_name,report_date,total_revenue,net_profit,eps,roe) VALUES (?,?,?,?,?,?,?)",
                        (code, name, str(row.get("报告期","")),
                         float(str(row.get("营业总收入","0")).replace(",","")) if row.get("营业总收入") else None,
                         float(str(row.get("净利润","0")).replace(",","")) if row.get("净利润") else None,
                         float(str(row.get("每股收益","0")).replace(",","")) if row.get("每股收益") else None,
                         float(str(row.get("净资产收益率","0")).replace("%","")) if row.get("净资产收益率") else None))
                conn.commit()
                logger.info(f"  {code} {name} 财报完成")
            time.sleep(2)
        except Exception as e:
            logger.error(f"  {code} 财报失败：{e}")
    logger.info("=== 财报采集完成 ===\n")

def generate_summary(conn, logger):
    c = conn.cursor()
    logger.info("=" * 50)
    for t in ["market_data","news_data","financial_data"]:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        logger.info(f"  {t}: {c.fetchone()[0]} 条")
    c.execute("SELECT stock_code,stock_name,date,close_price,change_pct FROM market_data WHERE date=(SELECT MAX(date) FROM market_data) ORDER BY change_pct DESC")
    for r in c.fetchall():
        logger.info(f"  {r[0]} {r[1]} | {r[2]} | 收盘:{r[3]} | 涨跌:{r[4]}%")
    logger.info("=" * 50)

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
        logger.info("采集全部完成！")
    except Exception as e:
        logger.error(f"出错：{e}", exc_info=True)
    finally:
        conn.close()

if __name__ == "__main__":
    run_collection()
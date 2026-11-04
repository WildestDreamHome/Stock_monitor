import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data/stock_data.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "docs/index.html")

def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    market_data = []
    news_data = []
    financial_data = []
    try:
        c.execute("SELECT * FROM market_data ORDER BY date DESC LIMIT 100")
        market_data = [dict(row) for row in c.fetchall()]
    except:
        pass
    try:
        c.execute("SELECT * FROM news_data ORDER BY collected_at DESC LIMIT 50")
        news_data = [dict(row) for row in c.fetchall()]
    except:
        pass
    try:
        c.execute("SELECT * FROM financial_data ORDER BY collected_at DESC LIMIT 20")
        financial_data = [dict(row) for row in c.fetchall()]
    except:
        pass
    conn.close()
    return market_data, news_data, financial_data

def generate_html(market_data, news_data, financial_data):
    market_json = json.dumps(market_data, ensure_ascii=False)
    news_json = json.dumps(news_data, ensure_ascii=False)
    financial_json = json.dumps(financial_data, ensure_ascii=False)
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html>\n')
        f.write('<html lang="zh-CN">\n')
        f.write('<head>\n')
        f.write('<meta charset="UTF-8">\n')
        f.write('<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
        f.write('<title>A股监控系统</title>\n')
        f.write('<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>\n')
        f.write('<style>\n')
        f.write('* { margin: 0; padding: 0; box-sizing: border-box; }\n')
        f.write('body { font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 10px; }\n')
        f.write('.container { max-width: 800px; margin: 0 auto; }\n')
        f.write('h1 { text-align: center; padding: 20px 0; color: #333; }\n')
        f.write('.card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }\n')
        f.write('.card h2 { font-size: 18px; margin-bottom: 15px; color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }\n')
        f.write('#chart { width: 100%; height: 400px; }\n')
        f.write('.news-item { padding: 12px 0; border-bottom: 1px solid #eee; }\n')
        f.write('.news-title { font-weight: 500; margin-bottom: 5px; }\n')
        f.write('.news-meta { font-size: 12px; color: #888; }\n')
        f.write('table { width: 100%; border-collapse: collapse; }\n')
        f.write('th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }\n')
        f.write('th { background: #f8f9fa; }\n')
        f.write('.up { color: #e74c3c; }\n')
        f.write('.down { color: #27ae60; }\n')
        f.write('.update-time { text-align: center; color: #888; font-size: 12px; padding: 10px; }\n')
        f.write('</style>\n')
        f.write('</head>\n')
        f.write('<body>\n')
        f.write('<div class="container">\n')
        f.write('<h1>A股智能监控</h1>\n')
        f.write('<div class="card"><h2>股价走势</h2><div id="chart"></div></div>\n')
        f.write('<div class="card"><h2>最新行情</h2><table id="stockTable"><thead><tr><th>代码</th><th>日期</th><th>收盘</th><th>涨跌幅</th></tr></thead><tbody></tbody></table></div>\n')
        f.write('<div class="card"><h2>财经新闻</h2><div id="newsList"></div></div>\n')
        f.write('<div class="card"><h2>财报数据</h2><table id="financialTable"><thead><tr><th>代码</th><th>报告期</th><th>营收</th><th>净利润</th><th>ROE</th></tr></thead><tbody></tbody></table></div>\n')
        f.write('<div class="update-time">数据更新时间：' + update_time + '</div>\n')
        f.write('</div>\n')
        f.write('<script>\n')
        f.write('const marketData = ' + market_json + ';\n')
        f.write('const newsData = ' + news_json + ';\n')
        f.write('const financialData = ' + financial_json + ';\n')
        f.write('const chart = echarts.init(document.getElementById("chart"));\n')
        f.write('const stockGroups = {};\n')
        f.write('marketData.forEach(item => { if (!stockGroups[item.stock_code]) stockGroups[item.stock_code] = []; stockGroups[item.stock_code].push(item); });\n')
        f.write('const series = Object.keys(stockGroups).map(code => { const data = stockGroups[code].sort((a,b) => a.date.localeCompare(b.date)); return { name: code, type: "line", data: data.map(d => [d.date, d.close_price]), smooth: true }; });\n')
        f.write('chart.setOption({ tooltip: { trigger: "axis" }, legend: { data: Object.keys(stockGroups), bottom: 0 }, grid: { left: "10%", right: "5%", bottom: "15%" }, xAxis: { type: "category", boundaryGap: false }, yAxis: { type: "value" }, series: series });\n')
        f.write('const latestDate = marketData.length > 0 ? marketData[0].date : "";\n')
        f.write('const latestStocks = marketData.filter(d => d.date === latestDate).slice(0, 10);\n')
        f.write('const tbody = document.querySelector("#stockTable tbody");\n')
        f.write('latestStocks.forEach(s => { const cls = s.change_pct >= 0 ? "up" : "down"; tbody.innerHTML += "<tr><td>" + s.stock_code + "</td><td>" + s.date + "</td><td>" + s.close_price + "</td><td class=\\"" + cls + "\\">" + s.change_pct + "%</td></tr>"; });\n')
        f.write('const newsList = document.getElementById("newsList");\n')
        f.write('newsData.slice(0, 20).forEach(n => { newsList.innerHTML += "<div class=\\"news-item\\"><div class=\\"news-title\\">" + (n.title || "无标题") + "</div><div class=\\"news-meta\\">" + (n.source || "") + " | " + (n.publish_time || "") + "</div></div>"; });\n')
        f.write('const finTbody = document.querySelector("#financialTable tbody");\n')
        f.write('financialData.slice(0, 10).forEach(f => { finTbody.innerHTML += "<tr><td>" + f.stock_code + "</td><td>" + (f.report_date || "") + "</td><td>" + (f.total_revenue ? (f.total_revenue/100000000).toFixed(2) + "亿" : "-") + "</td><td>" + (f.net_profit ? (f.net_profit/100000000).toFixed(2) + "亿" : "-") + "</td><td>" + (f.roe ? f.roe.toFixed(2) + "%" : "-") + "</td></tr>"; });\n')
        f.write('window.addEventListener("resize", () => chart.resize());\n')
        f.write('</script>\n')
        f.write('</body>\n')
        f.write('</html>\n')
    
    print(f"网页已生成：{OUTPUT_PATH}")

if __name__ == "__main__":
    market, news, financial = load_data()
    generate_html(market, news, financial)
    print(f"数据：行情{len(market)}条，新闻{len(news)}条，财报{len(financial)}条")
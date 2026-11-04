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
    try:
        c.execute("SELECT * FROM market_data ORDER BY date DESC LIMIT 100")
        market_data = [dict(row) for row in c.fetchall()]
    except:
        pass
    
    news_data = []
    try:
        c.execute("SELECT * FROM news_data ORDER BY collected_at DESC LIMIT 50")
        news_data = [dict(row) for row in c.fetchall()]
    except:
        pass
    
    financial_data = []
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
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股监控系统</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; padding: 10px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ text-align: center; padding: 20px 0; color: #333; font-size: 24px; }}
        .card {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .card h2 {{ font-size: 18px; margin-bottom: 15px; color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }}
        #chart {{ width: 100%; height: 400px; }}
        .news-item {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-title {{ font-weight: 500; margin-bottom: 5px; color: #333; }}
        .news-meta {{ font-size: 12px; color: #888; }}
        .stock-table {{ width: 100%; border-collapse: collapse; }}
        .stock-table th, .stock-table td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        .stock-table th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        .up {{ color: #e74c3c; }}
        .down {{ color: #27ae60; }}
        .update-time {{ text-align: center; color: #888; font-size: 12px; padding: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 A股智能监控</h1>
        
        <div class="card">
            <h2>股价走势</h2>
            <div id="chart"></div>
        </div>
        
        <div class="card">
            <h2>最新行情</h2>
            <table class="stock-table" id="stockTable">
                <thead>
                    <tr><th>代码</th><th>日期</th><th>收盘</th><th>涨跌幅</th></tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>财经新闻</h2>
            <div id="newsList"></div>
        </div>
        
        <div class="card">
            <h2>财报数据</h2>
            <table class="stock-table" id="financialTable">
                <thead>
                    <tr><th>代码</th><th>报告期</th><th>营收</th><th>净利润</th><th>ROE</th></tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div class="update-time">数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>
    
    <script>
        const marketData = {market_json};
        const newsData = {news_json};
        const financialData = {financial_json};
        
        // 股价图表
        const chart = echarts.init(document.getElementById('chart'));
        const stockGroups = {{}};
        marketData.forEach(item => {{
            if (!stockGroups[item.stock_code]) stockGroups[item.stock_code] = [];
            stockGroups[item.stock_code].push(item);
        }});
        
        const series = Object.keys(stockGroups).map(code => {{
            const data = stockGroups[code].sort((a,b) => a.date.localeCompare(b.date));
            return {{
                name: code,
                type: 'line',
                data: data.map(d => [d.date, d.close_price]),
                smooth: true
            }};
        }});
        
        chart.setOption({{
            tooltip: {{ trigger: 'axis' }},
            legend: {{ data: Object.keys(stockGroups), bottom: 0 }},
            grid: {{ left: '10%', right: '5%', bottom: '15%' }},
            xAxis: {{ type: 'category', boundaryGap: false }},
            yAxis: {{ type: 'value' }},
            series: series
        }});
        
        // 行情表格
        const latestDate = marketData.length > 0 ? marketData[0].date : '';
        const latestStocks = marketData.filter(d => d.date === latestDate).slice(0, 10);
        const tbody = document.querySelector('#stockTable tbody');
        latestStocks.forEach(s => {{
            const cls = s.change_pct >= 0 ? 'up' : 'down';
            tbody.innerHTML += `<tr><td>${{s.stock_code}}</td><td>${{s.date}}</td><td>${{s.close_price}}</td><td class="${{cls}}">${{s.change_pct}}%</td></tr>`;
        }});
        
        // 新闻列表
        const newsList = document.getElementById('newsList');
        newsData.slice(0, 20).forEach(n => {{
            newsList.innerHTML += `
                <div class="news-item.email "actions@github.com"
        git add data/stock_data.db logs/collector.log docs/
        git commit -m "自动更新 $(date +'%Y-%m-%d %H:%M')" || echo "没有新数据"
        git push
    - name: 上传日志
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: collector-logs
        path: logs/collector.log
        retention-days: 7

  deploy:
    needs: collect-data
    runs-on: ubuntu-latest
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
    - name: 部署到 GitHub Pages
      uses: actions/deploy-pages@v4
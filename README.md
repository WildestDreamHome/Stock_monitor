# A股智能监控系统

自动采集A股行情、财经新闻、财报数据，通过 GitHub Actions 实现云端自动化运行。

## 特点

- ✅ **全自动运行**：GitHub 服务器每天自动采集3次（开盘前、午盘、收盘后）
- ✅ **不需要电脑开机**：代码运行在 GitHub 云端
- ✅ **数据自动保存**：采集的数据自动存到 GitHub 仓库
- ✅ **免费**：GitHub Actions 对公开仓库免费
- ✅ **手机可查看**：随时在 GitHub 上看数据和日志

## 快速开始（5分钟部署）

### 第1步：在 GitHub 创建仓库

1. 打开 https://github.com
2. 点右上角 "+" → "New repository"
3. 仓库名填：`stock-monitor`（或你喜欢的名字）
4. 选择 **Public**（公开，免费用 Actions）
5. **不要**勾选 "Initialize this repository with a README"
6. 点 "Create repository"

### 第2步：上传代码到 GitHub

**方法A：网页上传（最简单）**

1. 在你刚创建的仓库页面，点 "uploading an existing file"
2. 把解压后的 `stock-monitor` 文件夹里的**所有文件**拖进去
3. 点 "Commit changes"

**方法B：用 Git 命令（推荐学习）**

```bash
cd stock-monitor
git init
git add .
git commit -m "初始版本"
git branch -M main
git remote add origin https://github.com/你的用户名/stock-monitor.git
git push -u origin main
```

### 第3步：启用 GitHub Actions

1. 在你的仓库页面，点顶部的 "Actions" 标签
2. 如果看到提示，点 "I understand my workflows, go ahead and enable them"
3. 左侧应该能看到 "A股数据采集" 工作流
4. 点它，然后点 "Run workflow" → "Run workflow" 手动测试一次

### 第4步：查看运行结果

1. 回到 "Actions" 页面，刷新看看是否运行成功（绿色勾）
2. 点进去可以看详细日志
3. 回到 "Code" 页面，`data/stock_data.db` 应该有数据了

### 第5步：修改配置（可选）

编辑 `config.yaml`，修改要追踪的股票代码：

```yaml
stocks:
  - code: "000001"  # 平安银行
  - code: "600519"  # 贵州茅台
  # 添加更多...
```

提交后会自动触发运行。

## 自动化时间表

GitHub Actions 会在以下时间自动运行（北京时间，周一到周五）：

- 🕘 09:00 - 开盘前采集
- 🕛 12:00 - 午盘采集
- 🕞 15:30 - 收盘后采集

每天3次，完全自动，不需要你操心。

## 查看数据

### 方法1：下载数据库文件

1. 在仓库页面点 `data/stock_data.db`
2. 点 "Download raw file"
3. 用 DB Browser for SQLite 打开查看

### 方法2：查看运行日志

1. 点 "Actions" 标签
2. 点任意一次运行记录
3. 展开 "采集数据" 或 "上传日志" 步骤查看

### 方法3：在线查看（后续会做）

第二阶段会加一个网页仪表盘，直接在线看图表。

## 常见问题

**Q: Actions 运行失败怎么办？**
A: 点进失败的运行记录，看错误日志。常见原因：
- 网络问题：重试一次就好
- API 限制：等几分钟再试
- 代码错误：检查日志里的具体报错

**Q: 数据会丢失吗？**
A: 不会。每次运行后数据会自动提交到仓库，永久保存。

**Q: 免费额度够用吗？**
A: GitHub Actions 公开仓库每月有 2000 分钟免费额度。我们这个任务每次运行约1-2分钟，每天3次 = 每天约6分钟，一个月约180分钟，完全够用。

**Q: 怎么修改运行时间？**
A: 编辑 `.github/workflows/collector.yml`，修改 `cron` 表达式。注意 GitHub 用的是 UTC 时间，北京时间 = UTC+8。

**Q: 可以手动运行吗？**
A: 可以。在 Actions 页面点工作流 → "Run workflow" → "Run workflow"。

## 项目结构

```
stock-monitor/
├── .github/
│   └── workflows/
│       └── collector.yml      # GitHub Actions 配置
├── collector.py                # 主采集程序
├── scheduler.py                # 本地调度器（备用）
├── config.yaml                 # 配置文件
├── requirements.txt            # 依赖包列表
├── .gitignore                  # Git 忽略文件
├── data/
│   └── stock_data.db           # 数据库（自动创建）
└── logs/
    └── collector.log           # 运行日志
```

## 后续计划

- [x] 第一阶段：数据采集 + GitHub Actions 自动化（当前）
- [ ] 第二阶段：网页仪表盘（在线看图表）
- [ ] 第三阶段：新闻情感分析（AI 判断利好利空）
- [ ] 第四阶段：趋势预测模型
- [ ] 第五阶段：微信/邮件推送通知

## 学习资源

通过这个 project 你可以学到：

- **Python 基础**：变量、函数、循环、条件判断
- **数据处理**：pandas 读取和处理数据
- **数据库**：SQLite 存储和查询数据
- **网络爬虫**：requests + BeautifulSoup 抓取网页
- **API 调用**：AKShare 获取股票数据
- **自动化**：GitHub Actions 定时任务
- **版本控制**：Git 基本操作

代码里有详细的中文注释，边看边学！

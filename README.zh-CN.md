# OmniSearch

English version: [README.md](README.md)

OmniSearch 是一个面向 AI Agent 的、本地优先工具层。

它依然不是搜索引擎。当前仓库同时提供：

- `/search`：基于 SearXNG 的统一搜索接口
- `/extract`：基于 `requests + trafilatura` 的正文抽取接口
- `/research`：最小可用的搜索 + 抽取编排接口
- `GET /company/*`：面向 A 股研究工作流的股票数据接口

## 定位

OmniSearch 只做一层稳定 API：

- 搜索能力放在 `/search`
- 网页正文抽取放在 `/extract`
- 研究编排放在 `/research`
- 股票数据统一归一化到本地 SQLite，再通过 `/company/*` 暴露

当前不做：

- 搜索引擎索引
- 排序模型
- 鉴权
- 计费
- 管理后台
- LLM 总结

## 项目结构

```text
app/
  api/
  collectors/
  core/
  db/
  extractors/
  models/
  normalizers/
  providers/
  research/
  schemas/
  services/
```

## 运行要求

- Python 3.11+
- Docker / Docker Compose
- 如果要采集公司资料和财务摘要，需要配置 `TUSHARE_TOKEN`

## 一键启动

```bash
make up
```

等价命令：

```bash
docker compose up --build
```

默认启动：

- OmniSearch API：`http://localhost:8000`
- SearXNG：`http://localhost:8080`

API 容器会把本地股票缓存落到 `./data`。

## 本地开发

1. 创建环境变量文件

```bash
cp .env.example .env
```

2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. 启动 SearXNG

```bash
docker compose up -d searxng
```

4. 启动 API

```bash
uvicorn app.main:app --reload
```

## 关键环境变量

```env
API_PORT=8000
SEARXNG_BASE_URL=http://localhost:8080
SQLITE_DB_PATH=./data/omnisearch.db
RESEARCH_PLANNER=rule
TUSHARE_TOKEN=
TUSHARE_BASE_URL=
CNINFO_ANNOUNCEMENTS_URL=https://www.cninfo.com.cn/new/hisAnnouncement/query
STOCK_DATA_TTL_HOURS=24
```

说明：

- `TUSHARE_TOKEN` 用于 `/company/{ticker}` 和 `/company/{ticker}/financials`
- 如果你本地走 Tushare 兼容代理，可以设置 `TUSHARE_BASE_URL=http://tushare.xyz`
- 日线价格通过 AKShare 获取
- 公告 / 事件通过 CNInfo 获取
- 股票数据默认缓存到本地 SQLite，并按需刷新

## 架构

```text
Client / Agent
  -> OmniSearch API (FastAPI)
       -> SearXNG
       -> requests + Trafilatura
       -> SQLite
       -> Tushare / CNInfo / AKShare
```

## API 示例

### 健康检查

```bash
curl http://localhost:8000/health
```

### 搜索

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"fastapi searxng","top_k":5}'
```

### 抽取正文

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

### Research

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"000001 业绩","top_k":2}'
```

`/research` 仍然保留现有 search + extract 流程。如果 query 里带 A 股 ticker，比如 `000001`，响应里还会附带 `stock_context`。

### 公司资料

```bash
curl "http://localhost:8000/company/000001"
```

### 公司公告 / 事件

```bash
curl "http://localhost:8000/company/000001/events?limit=10"
```

### 公司财务摘要

```bash
curl "http://localhost:8000/company/000001/financials?limit=4"
```

### 公司日线价格

```bash
curl "http://localhost:8000/company/000001/prices?limit=30"
```

### 公司总览

```bash
curl "http://localhost:8000/company/000001/overview"
```

### 公司时间线

```bash
curl "http://localhost:8000/company/000001/timeline"
```

### 风险标记

```bash
curl "http://localhost:8000/company/000001/risk-flags"
```

### 价格调试

```bash
curl "http://localhost:8000/company/002837/prices?limit=5&debug=true"
```

### 本地同步 / 预热缓存

```bash
python -m app.scripts.sync_stock --tickers 000001,002837 --refresh
```

或者：

```bash
TICKERS=000001,002837 REFRESH=1 make sync
```

## 说明

- 这个仓库仍然是工具层，不是搜索引擎
- 股票数据层是垂直的，只聚焦 A 股
- 当前风险标记是规则型、确定性的，不做 LLM 总结
- `timeline` 现在会更突出财务更新和较大价格波动
- `risk-flags` 现在会显式标出缺失数据、回撤、波动和低毛利 / 负增长信号
- Docker Compose 工作流保持本地优先

# 📈 A 股量化投研平台

基于 [Microsoft Qlib](https://github.com/microsoft/qlib) 的 A 股量化投研系统。集成了**多源数据采集**、**市场情绪信号**、**交互式可视化看板**和**择时策略回测**，提供从数据到决策的完整工作流。

## ✨ 核心功能

| 模块 | 说明 |
|------|------|
| 📊 **市场看板** | 市场情绪、涨跌停统计、PE 中位数等宏观指标实时可视化 |
| 🔥 **热点题材** | 自资在宅（ZIZIZAIZAI）热门题材与 K 线联动 |
| 📰 **AI 早报** | 自动抓取与展示每日 AI 研报摘要 |
| 🔍 **个股研究** | 输入股票名/代码，实时查看多维度数据和 YMOS 风控审计 |
| 🤖 **iWencai 问答** | 自然语言搜索 A 股数据 |
| 📉 **回测与看板** | 择时增强 TopK 策略回测、全动态策略排行榜 (Leaderboard)、历史最大回撤及多次异常回撤 (>20%) 智能标注对齐 |

## 🚀 快速启动

### 前置条件

- Python 3.10+（推荐使用虚拟环境）
- Node.js 18+
- 已安装 Qlib 依赖：`pip install -e .`

### 1. 配置密钥

在 `backend/secret.yaml` 中填写 API 密钥：

```yaml
zizi_email: "your@email.com"
zizi_password: "YOUR_PASSWORD"
zzshare_token: "YOUR_TOKEN"
deepseek_api_key: "YOUR_DEEPSEEK_KEY"  # 用于 YMOS 风控审计
```

### 2. ⚡️ 一键启动（推荐）

在项目根目录下，直接运行一键启动脚本，它会自动挂载本地的虚拟环境（`.venv`），并同时拉起后端和前端：

```bash
# 启动整个平台
./start.sh
```

- 脚本会自动将后端 API 挂载在 **http://localhost:28456**
- 脚本会自动将前端看板挂载在 **http://localhost:28457**
- **按 `Ctrl + C`** 即可一键安全停止所有服务。

> **注**：如果你希望手动分步启动，可以分别进入 `backend/` 运行 `python api_server.py`，以及在 `frontend/` 下运行 `npm run dev`。

### 4. 数据更新（可选）

```bash
# 手动触发全量数据刷新（情绪、题材、个股行情）
cd backend
python update_all_data.py --force

# 或设置定时任务（参考 crontab.example）
```

### 5. 运行回测（可选）

```bash
# 在项目根目录运行
python custom_workflow.py
```

## 📁 项目结构

```
qlib/
├── qlib/                          # Qlib 核心框架（上游代码，不修改）
│   ├── data/                      # 数据存储、表达式引擎、缓存
│   ├── model/                     # 模型基类
│   ├── contrib/model/             # 具体 ML 模型实现
│   ├── strategy/                  # 策略抽象
│   ├── contrib/strategy/          # 具体策略实现
│   ├── backtest/                  # 回测引擎
│   ├── workflow/                  # 实验记录与任务调度
│   └── rl/                        # 强化学习模块
│
├── frontend/                      # 📌 Vue 3 交互式看板
│   ├── src/views/                 # 页面组件
│   ├── src/composables/           # 可复用逻辑
│   ├── src/router/                # 路由配置
│   ├── package.json               # Node 依赖
│   └── vite.config.js             # Vite 配置
│
├── backend/   # 📌 自定义 A 股数据系统
│   ├── collector.py               # 多源数据采集器（核心）
│   ├── api/server.py              # FastAPI 后端服务
│   ├── core/stock_resolver.py     # 股票代码智能解析
│   ├── core/trading_calendar.py   # 交易日历工具
│   ├── core/data_schema.py        # 数据层 Schema 定义
│   ├── tasks/update_daily.py      # 全量数据定时更新脚本
│   ├── market_data/adapters/      # 数据源适配器（插件化）
│   │   ├── market.py              # 行情数据（百度/腾讯/新浪）
│   │   ├── signals.py             # 市场情绪信号（乐咕乐股等）
│   │   ├── news.py                # 新闻数据（东方财富）
│   │   ├── capital.py             # 资金数据
│   │   ├── fundamentals.py        # 基本面数据
│   │   ├── filings.py             # 公告数据
│   │   ├── research.py            # 研究数据（iWencai）
│   │   └── legacy.py              # 旧版兼容适配器
│   ├── fetch_zizizaizai_*.py      # ZIZIZAIZAI 数据抓取脚本
│   ├── backfill_*.py              # 历史数据回填脚本
│   ├── secret.yaml                # 🔒 API 密钥（不提交 Git）
│   ├── watchlist.yaml             # 自选股列表
│   └── crontab.example            # 定时任务示例
│
├── data/cn_stock/                 # 📌 本地数据存储（不提交 Git）
│   ├── hierarchical/              # 分层数据
│   │   ├── market/                # 行情 CSV
│   │   ├── signals/               # 情绪信号 CSV/JSON
│   │   ├── news/                  # 新闻 JSON
│   │   ├── capital/               # 资金数据
│   │   ├── fundamentals/          # 基本面数据
│   │   ├── filings/               # 公告数据
│   │   └── research/              # 研究数据
│   └── standard/                  # Qlib 标准格式
│       └── qlib_data/             # Qlib 二进制数据库
│
├── custom_workflow.py             # 自定义回测工作流入口
├── timing_strategy.py             # 择时增强 TopK 策略
├── examples/                      # Qlib 官方示例
├── docs/                          # 文档
│   └── QLIB_UPSTREAM_README.md    # Qlib 上游原版 README 备份
├── tests/                         # 测试
├── pyproject.toml                 # Python 项目配置
└── Makefile                       # 开发工具命令
```

## 🔄 数据流

```
数据源 (百度/腾讯/东财/乐咕乐股/ZIZIZAIZAI/iWencai)
  │
  ▼
collector.py + adapters/  ──→  data/cn_stock/hierarchical/  (CSV/JSON)
  │                                       │
  │                                       ▼
  │                              api_server.py (FastAPI :28456)
  │                                       │
  │                                       ▼
  │                              frontend/ (Vue 3 :28457)
  │
  ▼
scripts/dump_bin.py  ──→  data/cn_stock/standard/qlib_data/  (Qlib 二进制)
  │
  ▼
custom_workflow.py + timing_strategy.py  ──→  回测结果 (MLflow)
```

## ⚙️ 配置文件说明

| 文件 | 用途 |
|------|------|
| `secret.yaml` | API 密钥和凭证（**勿提交 Git**） |
| `watchlist.yaml` | 自选股列表，指定需要采集的股票 |
| `crontab.example` | Linux/Mac 定时数据更新任务示例 |
| `pyproject.toml` | Python 依赖和项目元数据 |

## 🛠️ 开发指南

### 添加新数据源

1. 在 `backend/adapters/` 下创建新适配器
2. 继承 `adapters/base.py` 中的基类
3. 在 `collector.py` 中注册新适配器
4. 数据将自动通过 `api_server.py` 暴露给前端

### 添加新看板页面

1. 在 `frontend/src/views/` 下创建新 `.vue` 文件
2. 在 `frontend/src/router/index.js` 中添加路由
3. 在 `App.vue` 导航栏中添加链接

### 代码规范

- Python: Black 格式化, 120 字符行宽
- 前端: Vue 3 Composition API + ECharts
- 使用 `make lint` 运行代码检查

## 📚 相关文档

- [Qlib 上游 README](docs/QLIB_UPSTREAM_README.md) — Microsoft Qlib 原版文档
- [数据采集器 README](backend/README.md) — 数据采集详细说明
- [Qlib 官方文档](https://qlib.readthedocs.io/) — 完整 API 参考

## 📄 License

[MIT License](LICENSE) — 基于 Microsoft Qlib 开源项目

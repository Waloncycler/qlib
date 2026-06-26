# Project Context: A 股量化投研平台

基于 Microsoft Qlib 的 A 股量化投研系统，集成多源数据采集、市场情绪信号、交互式可视化看板和择时策略回测。

## Core Goals
- **多源数据采集**: 从百度、腾讯、新浪、东方财富、乐咕乐股、ZIZIZAIZAI、iWencai 等渠道采集 A 股市场数据
- **实时看板可视化**: Vue 3 + ECharts 交互式看板，覆盖市场情绪、热点题材、个股研究、AI 早报、回测结果
- **AI 信号回测**: 基于 AI 早报股票池的信号回测引擎，支持 ML 过滤、大盘择时、Top-K 选股
- **风控审计**: 聚合多源数据，通过 DeepSeek 生成 YMOS 风控审计报告
- **API 服务**: FastAPI 后端提供股票解析、数据查询、回测、审计等接口

## Technology Stack
- **Languages**: Python (后端逻辑、数据流水线), JavaScript/Vue 3 (前端看板), Cython (C 扩展加速数据查询)
- **Backend**: FastAPI, Uvicorn, APScheduler
- **Frontend**: Vue 3, Vite, ECharts, vue-router, axios, PapaParse, lucide-vue-next
- **Libraries**:
  - 数据: `numpy`, `pandas`, `akshare`, `mootdx`, `requests`
  - ML: PyTorch, LightGBM
  - AI: DeepSeek API (风控审计), iWencai (NL 搜索)
  - Dev: `pytest`, `sphinx`
- **Storage**: Qlib 自定义二进制格式 + 分层 CSV/JSON 存储 (`data/cn_stock/`)

## Directory Map
> 注：下方路径基于实际磁盘结构。文档中所有模块说明均与代码一一对应。

- [qlib/](file:///Users/walox/qlib/qlib): Qlib 核心框架（上游代码，**不修改**）
- [backend/](file:///Users/walox/qlib/backend): 自定义 A 股数据采集与 API 服务
  - [core/](file:///Users/walox/qlib/backend/core): 核心基础设施（配置、调度器、数据采集编排器、交易日历、数据 schema）
  - [modules/](file:///Users/walox/qlib/backend/modules): 业务模块层（Router + Service 分层）
    - [market/](file:///Users/walox/qlib/backend/modules/market): 多源数据采集与行情查询（适配器引擎）
    - [backtest/](file:///Users/walox/qlib/backend/modules/backtest): AI 信号回测引擎
    - [audit/](file:///Users/walox/qlib/backend/modules/audit): YMOS 风控审计（DeepSeek）
    - [intelligence/](file:///Users/walox/qlib/backend/modules/intelligence): Zizizaizai 早报 / 题材抓取
    - [user/](file:///Users/walox/qlib/backend/modules/user): 自选股管理
  - [tasks/](file:///Users/walox/qlib/backend/tasks): 定时更新任务入口 (`update_daily.py`)
  - [backfill/](file:///Users/walox/qlib/backend/backfill): 历史数据回填脚本
  - [main.py](file:///Users/walox/qlib/backend/main.py): FastAPI 应用入口 (:28456)
- [frontend/](file:///Users/walox/qlib/frontend): Vue 3 交互式看板 (:28457)
  - [src/views/](file:///Users/walox/qlib/frontend/src/views): 6 个看板页面
  - [src/components/tabs/](file:///Users/walox/qlib/frontend/src/components/tabs): 个股研究子标签
  - [src/composables/](file:///Users/walox/qlib/frontend/src/composables): 数据加载与图表工厂
- [data/cn_stock/](file:///Users/walox/qlib/data): 本地数据存储
  - `hierarchical/`: 分层 CSV/JSON（market/signals/news/capital/fundamentals/filings/research）
  - `standard/qlib_data/`: Qlib 二进制格式（模型训练与回测）
  - `backtest_ohlcv/`: 回测缓存
  - `stock_pools/`: 人工策展股票池
- [scripts/](file:///Users/walox/qlib/scripts): Qlib 官方脚本（数据采集、dump_bin、训练等）
- [examples/](file:///Users/walox/qlib/examples): Qlib 官方示例
- [docs/](file:///Users/walox/qlib/docs): 文档（含上游 Qlib README 备份）
- [tests/](file:///Users/walox/qlib/tests): 测试
- [start.sh](file:///Users/walox/qlib/start.sh): 一键启动脚本（**必须使用**）
- [PROJECT_CONTEXT.md](file:///Users/walox/qlib/PROJECT_CONTEXT.md) / [ARCHITECTURE_INDEX.md](file:///Users/walox/qlib/ARCHITECTURE_INDEX.md) / [TASK_BOARD.md](file:///Users/walox/qlib/TASK_BOARD.md): 项目文档

## ⚠️ CRITICAL RULES FOR LLMs / AGENTS (环境与运行规范)
1. **执行环境 (Virtual Environment)**: 
   绝对不要使用全局的 `python` 或 `python3` 命令来运行项目代码。本项目的所有依赖均安装在项目根目录下的 `.venv` 虚拟环境中。
2. **启动项目 (Startup)**: 
   启动后端和前端服务时，**必须且只能使用项目根目录下的 `./start.sh` 脚本**。该脚本已经处理了虚拟环境路径、环境变量加载、前后端并行启动与优雅退出。
3. **执行独立脚本 (Running Scripts)**: 
   如果需要单独运行某个 python 脚本或安装依赖，必须显式调用虚拟环境下的解释器（例如：`.venv/bin/python scripts/.../xxx.py` 或 `.venv/bin/pip install xxx`）。
4. **上游框架不可修改**: 
   `qlib/` 目录为 Microsoft Qlib 上游核心框架，严禁修改。

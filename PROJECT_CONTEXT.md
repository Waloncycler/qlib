# Project Context: A 股量化投研平台

基于 Microsoft Qlib 的 A 股量化投研系统，集成多源数据采集、市场情绪信号、交互式可视化看板和择时策略回测。

## Core Goals
- **多源数据采集**: 从百度、腾讯、新浪、东方财富、乐咕乐股、ZIZIZAIZAI、iWencai 等渠道采集 A 股市场数据
- **实时看板可视化**: Vue 3 + ECharts 交互式看板，覆盖市场情绪、热点题材、个股研究、AI 早报、回测结果
- **择时增强回测**: 基于市场情绪信号的 TimingTopkDropoutStrategy 策略
- **API 服务**: FastAPI 后端提供股票解析、数据查询、YMOS 风控审计等接口

## Technology Stack
- **Languages**: Python (后端逻辑、数据流水线), JavaScript/Vue 3 (前端看板), Cython (C 扩展加速数据查询)
- **Backend**: FastAPI, Uvicorn
- **Frontend**: Vue 3, Vite, ECharts, vue-router
- **Libraries**:
  - 数据: `numpy`, `pandas`, `akshare`, `requests`
  - ML: PyTorch, LightGBM
  - Dev: `pytest`, `sphinx`
- **Storage**: Qlib 自定义二进制格式 + CSV/JSON 分层存储

## Directory Map
- [qlib/](file:///Users/walox/qlib/qlib): Qlib 核心框架（上游代码，不修改）
- [scripts/data_collector/cn_stock/](file:///Users/walox/qlib/scripts/data_collector/cn_stock): 自定义 A 股数据采集与 API 服务
- [scripts/data_collector/cn_stock/api/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/api): API 层
- [scripts/data_collector/cn_stock/core/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/core): 核心实体、日历、解析器
- [scripts/data_collector/cn_stock/market_data/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/market_data): 行情与适配器引擎
- [scripts/data_collector/cn_stock/zizizaizai/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/zizizaizai): Zizizaizai (AI) 早报与个股信息抓取
- [scripts/data_collector/cn_stock/sentiment/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/sentiment): 市场情绪抓取
- [scripts/data_collector/cn_stock/tasks/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/tasks): 定时更新任务
- [scripts/data_collector/cn_stock/frontend/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/frontend): Vue 3 交互式看板
- [data/cn_stock/](file:///Users/walox/qlib/data/cn_stock): 本地数据存储（分层 + Qlib 标准格式）
- [custom_workflow.py](file:///Users/walox/qlib/custom_workflow.py): 回测工作流入口
- [timing_strategy.py](file:///Users/walox/qlib/timing_strategy.py): 择时增强策略
- [examples/](file:///Users/walox/qlib/examples): Qlib 官方示例
- [docs/](file:///Users/walox/qlib/docs): 文档（含上游 Qlib README 备份）

## ⚠️ CRITICAL RULES FOR LLMs / AGENTS (环境与运行规范)
1. **执行环境 (Virtual Environment)**: 
   绝对不要使用全局的 `python` 或 `python3` 命令来运行项目代码。本项目的所有依赖均安装在项目根目录下的 `.venv` 虚拟环境中。
2. **启动项目 (Startup)**: 
   启动后端和前端服务时，**必须且只能使用项目根目录下的 `./start.sh` 脚本**。该脚本已经处理了虚拟环境路径和环境变量加载。
3. **执行独立脚本 (Running Scripts)**: 
   如果需要单独运行某个 python 脚本或安装依赖，必须显式调用虚拟环境下的解释器（例如：`.venv/bin/python scripts/.../xxx.py` 或 `.venv/bin/pip install xxx`）。

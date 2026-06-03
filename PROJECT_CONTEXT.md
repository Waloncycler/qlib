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
- [scripts/data_collector/cn_stock/adapters/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/adapters): 数据源适配器（插件化）
- [scripts/data_collector/cn_stock/frontend/](file:///Users/walox/qlib/scripts/data_collector/cn_stock/frontend): Vue 3 交互式看板
- [data/cn_stock/](file:///Users/walox/qlib/data/cn_stock): 本地数据存储（分层 + Qlib 标准格式）
- [custom_workflow.py](file:///Users/walox/qlib/custom_workflow.py): 回测工作流入口
- [timing_strategy.py](file:///Users/walox/qlib/timing_strategy.py): 择时增强策略
- [examples/](file:///Users/walox/qlib/examples): Qlib 官方示例
- [docs/](file:///Users/walox/qlib/docs): 文档（含上游 Qlib README 备份）

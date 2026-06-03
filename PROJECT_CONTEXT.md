# Project Context: Microsoft Qlib

Qlib is an AI-oriented quantitative investment platform that aims to realize the potential, empower research, and create value using AI technologies in quantitative investment, from exploring ideas to implementing productions.

## Core Goals
- **Empower AI in Quant**: Integrate state-of-the-art machine learning algorithms (deep learning, reinforcement learning, ensemble models) into quantitative trading research.
- **Provide High-Performance Infrastructure**: Offer highly efficient data servers, feature extraction, backtesting, and execution pipelines.
- **Enable End-to-End Workflows**: Cover the entire quant research workflow, including:
  1. Data processing and storage (efficient binary format, expression cache, dataset cache).
  2. Signal forecasting (supervised learning, market dynamics adaptation).
  3. Portfolio management and risk modeling.
  4. Trading strategies and execution (order execution, RL-based decisions, nested executors).
  5. Backtest evaluation (performance metrics, visualization).
  6. Online serving (rolling models, server deployment).

## Technology Stack
- **Languages**: Python (Logic, Pipeline), Cython (C-extensions for performance in data queries).
- **Libraries**:
  - Scientific Computing: `numpy`, `pandas`, `scipy`.
  - Machine Learning: PyTorch, LightGBM, CatBoost, XGBoost.
  - Development tools: `pytest` for tests, `sphinx` for documentation.
- **Storage**: Custom binary storage format designed for rapid queries with C/C++ extensions, far outperforming general-purpose databases like MySQL/MongoDB.

## Directory Map
- [qlib/data](file:///Users/walox/qlib/qlib/data): Data retrieval, expression calculation, caching, and storage.
- [qlib/model](file:///Users/walox/qlib/qlib/model): Base classes for models, trainers, and meta-learning modules.
- [qlib/contrib/model](file:///Users/walox/qlib/qlib/contrib/model): Implementations of specific machine learning models (e.g. GATs, GRU, TRA, TabNet).
- [qlib/strategy](file:///Users/walox/qlib/qlib/strategy): Strategy abstractions.
- [qlib/contrib/strategy](file:///Users/walox/qlib/qlib/contrib/strategy): Concrete portfolio/trading strategies (e.g. SignalStrategy, RuleStrategy).
- [qlib/backtest](file:///Users/walox/qlib/qlib/backtest): Order execution, exchange simulator, position tracker, and report generation.
- [qlib/workflow](file:///Users/walox/qlib/qlib/workflow): Experiment recording, task scheduling, and automation workflow.
- [qlib/rl](file:///Users/walox/qlib/qlib/rl): Reinforcement learning environment, policy wrappers, and training algorithms.
- [examples](file:///Users/walox/qlib/examples): Example config files, workflows, and tutorials.
- [scripts](file:///Users/walox/qlib/scripts): Scripts for data collection, formatting, and analysis.

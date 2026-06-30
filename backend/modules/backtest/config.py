from dataclasses import dataclass, field
from typing import List

@dataclass
class BacktestConfig:
    """Configuration for signal backtest."""
    initial_capital: float = 10_000_000.0
    buy_cost: float = 0.0013       # 0.03% commission + 0.1% slippage
    sell_cost: float = 0.0018      # 0.03% commission + 0.05% stamp duty + 0.1% slippage
    core_weight_multiplier: float = 2.0
    new_concept_multiplier: float = 1.5
    enable_ml_filter: bool = False
    model_version: str = "v3_binary"
    exit_timing: str = "open" # "open" or "close"
    top_k: int = 10
    enable_market_timing: bool = True     # 是否开启大盘择时
    market_timing_ma_days: int = 20       # 均线周期 (默认 20天)
    market_timing_down_weight: float = 0.3 # 跌破均线后的目标总仓位 (30%)
    enable_crash_filter: bool = False     # 是否开启暴亏过滤器
    crash_threshold: float = 0.5          # 暴亏概率阈值，高于此值的标的被排除
    enable_turnover_filter: bool = True   # 是否开启量能过滤（排除放量出货+缩量高位）
    min_turnover: float = 3.0             # 最低换手率阈值（%），低于此值的标的被排除
    max_vol_ratio: float = 2.0            # 最大量比阈值（前日量/5日均量），高于此值视为放量出货
    enable_factor_rank: bool = False     # 是否开启因子排序选股（替代 ML 排序）
    factor_name: str = "turnover"        # 排序因子名（turnover/amount/body_ratio/gap）
    enable_selection_boost: bool = False # 是否开启AI连续入选加分（实验性，已验证为反向指标）
    selection_boost_factor: float = 0.05 # 每连续入选1天加分比例（0.05=5%）


@dataclass
class DailyRecord:
    """Record for a single trading day."""
    date: str
    nav: float                        # Net asset value
    daily_return: float               # Strategy daily return
    benchmark_return: float           # Benchmark daily return
    holdings_count: int               # Number of stocks held
    turnover: float                   # Turnover ratio (0~1)
    new_entries: List[str] = field(default_factory=list)
    exits: List[str] = field(default_factory=list)

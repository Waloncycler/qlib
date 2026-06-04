# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .base import (
    BaseSourceAdapter,
    clean_symbol,
    get_market_prefix,
    to_qlib_symbol,
    to_ts_code,
    to_tencent_symbol,
    eastmoney_datacenter,
    resilient_request,
)

from .market import (
    MootdxAdapter,
    AkshareAdapter,
    TencentSinaAdapter,
    BaiduKlineAdapter,
    EastmoneyAdapter,
)

from .signals import (
    ThsHotReasonAdapter,
    ThsNorthboundAdapter,
    BaiduConceptAdapter,
    EastmoneyFundFlowAdapter,
    DragonTigerAdapter,
    LockupAdapter,
    EastmoneyIndustryAdapter,
    MarketSentimentAdapter,
)

from .capital import (
    MarginTradingAdapter,
    BlockTradeAdapter,
    ShareholderAdapter,
    DividendAdapter,
    StockFundFlow120dAdapter,
)

from .research import (
    EastmoneyReportAdapter,
    ThsConsensusAdapter,
    IwencaiAdapter,
)

from .news import (
    EastmoneyStockNewsAdapter,
    ClsTelegraphAdapter,
    EastmoneyGlobalNewsAdapter,
)

from .fundamentals import (
    MootdxFinanceAdapter,
    MootdxF10Adapter,
    EastmoneyStockInfoAdapter,
    SinaFinancialReportAdapter,
)

from .filings import (
    CninfoAnnouncementsAdapter,
)

from .legacy import (
    ZizizaizaiAdapter,
    ZzshareAdapter,
)

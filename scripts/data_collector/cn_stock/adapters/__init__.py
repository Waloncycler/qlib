# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from adapters.base import (
    BaseSourceAdapter,
    clean_symbol,
    get_market_prefix,
    to_qlib_symbol,
    to_ts_code,
    to_tencent_symbol,
    eastmoney_datacenter,
)

from adapters.market import (
    MootdxAdapter,
    AkshareAdapter,
    TencentSinaAdapter,
    BaiduKlineAdapter,
    EastmoneyAdapter,
)

from adapters.signals import (
    ThsHotReasonAdapter,
    ThsNorthboundAdapter,
    BaiduConceptAdapter,
    EastmoneyFundFlowAdapter,
    DragonTigerAdapter,
    LockupAdapter,
    EastmoneyIndustryAdapter,
    MarketSentimentAdapter,
)

from adapters.capital import (
    MarginTradingAdapter,
    BlockTradeAdapter,
    ShareholderAdapter,
    DividendAdapter,
    StockFundFlow120dAdapter,
)

from adapters.research import (
    EastmoneyReportAdapter,
    ThsConsensusAdapter,
    IwencaiAdapter,
)

from adapters.news import (
    EastmoneyStockNewsAdapter,
    ClsTelegraphAdapter,
    EastmoneyGlobalNewsAdapter,
)

from adapters.fundamentals import (
    MootdxFinanceAdapter,
    MootdxF10Adapter,
    EastmoneyStockInfoAdapter,
    SinaFinancialReportAdapter,
)

from adapters.filings import (
    CninfoAnnouncementsAdapter,
)

from adapters.legacy import (
    ZizizaizaiAdapter,
    ZzshareAdapter,
)

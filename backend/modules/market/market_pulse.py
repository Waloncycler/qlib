import json
import time
import requests
from datetime import datetime
from loguru import logger

from core.config import DATA_DIR, config, iwencai_adapter

PULSE_DIR = DATA_DIR / "market_pulse"


# ============================================================
# 查询模板
# ============================================================

SCAN_TEMPLATES = {
    "breadth": {
        "label": "涨跌分布",
        "queries": ["今日上涨家数 下跌家数 涨停家数 跌停家数"],
    },
    "limit_up": {
        "label": "打板情绪",
        "queries": ["今日涨停股票所属概念分布 涨停家数 连板家数 首板家数 炸板家数"],
    },
    "sector_rotation": {
        "label": "板块轮动",
        "queries": ["今日行业板块涨跌幅排行 成交额"],
    },
    "concept_distribution": {
        "label": "题材分布",
        "queries": ["今日概念板块涨跌幅排行"],
    },
    "capital_flow": {
        "label": "资金面",
        "queries": ["今日两市成交额 北向资金净流入 主力净流入"],
    },
    "finance_bank": {
        "label": "银行板块",
        "queries": ["今日银行板块涨跌幅 成交额 主力资金净流入 市净率"],
    },
    "finance_securities": {
        "label": "证券板块",
        "queries": ["今日证券板块涨跌幅 成交额 主力资金净流入"],
    },
    "finance_insurance": {
        "label": "保险板块",
        "queries": ["今日保险板块涨跌幅 成交额 主力资金净流入"],
    },
}


def _run_scan_group(group_key: str) -> dict:
    """执行一组查询，返回 {label, results}"""
    template = SCAN_TEMPLATES[group_key]
    label = template["label"]
    results = []

    for q in template["queries"]:
        try:
            data = iwencai_adapter.query2data(q, limit=20)
            results.append({"query": q, "data": data[:20] if data else []})
        except Exception as e:
            logger.error(f"Market pulse scan [{label}] failed for '{q}': {e}")
            results.append({"query": q, "data": [], "error": str(e)})

    return {"label": label, "results": results}


def _build_context(snapshot: dict) -> str:
    """把快照数据压缩成文本喂给 DeepSeek"""
    parts = []
    for group_key, group_data in snapshot.get("groups", {}).items():
        label = group_data.get("label", group_key)
        parts.append(f"\n### {label}")
        for result in group_data.get("results", []):
            parts.append(f"查询: {result['query']}")
            data = result.get("data", [])
            if data:
                for row in data[:8]:
                    row_str = ", ".join(
                        f"{k}: {v}" for k, v in row.items()
                        if isinstance(v, (str, int, float)) and len(str(v)) < 120
                    )
                    parts.append(f"  - {row_str}")
            else:
                parts.append("  (无数据)")
    return "\n".join(parts)


# ============================================================
# DeepSeek 调用
# ============================================================

def _call_deepseek(messages: list, json_mode: bool = False, timeout: int = 90) -> str:
    """统一的 DeepSeek 调用，带重试。"""
    api_key = config.get("deepseek_api_key", "")
    if not api_key:
        raise ValueError("DeepSeek API key missing in secret.yaml")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            if response.status_code >= 500 and attempt < max_retries:
                logger.warning(f"DeepSeek returned {response.status_code}, retry {attempt}/{max_retries}")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"DeepSeek API error: {response.status_code} {response.text}")
                raise ValueError(f"DeepSeek API Error: HTTP {response.status_code}")
        except requests.exceptions.RequestException:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise

    raise ValueError("DeepSeek API failed after retries")


# ============================================================
# DeepSeek 加工：原始数据 → 结构化 JSON
# ============================================================

STRUCTURED_PROMPT = """你是 A 股市场数据分析师。请把以下杂乱的 iWencai 原始查询结果，提炼为严格的结构化 JSON。

# 规则
1. 只输出 JSON，不要任何解释文字
2. 数值字段必须是纯数字（去掉"亿""万""%"等单位，百分比就是数字本身如 3.5 表示 3.5%）
3. 如果某个字段在原始数据中找不到，值设为 null
4. 数组字段如果找不到数据，设为空数组 []
5. 板块/概念排行最多保留 Top 10

# 输出 JSON Schema（严格遵循字段名）

```json
{{
  "market_breadth": {{
    "advance_count": null,
    "decline_count": null,
    "limit_up_count": null,
    "limit_down_count": null,
    "flat_count": null,
    "total_turnover_yi": null,
    "north_net_inflow_yi": null,
    "main_net_inflow_yi": null
  }},
  "sentiment": {{
    "first_board_count": null,
    "consecutive_board_count": null,
    "failed_board_count": null,
    "limit_up_success_rate_pct": null,
    "sentiment_label": "",
    "sentiment_score": null
  }},
  "top_sectors": [
    {{"name": "", "change_pct": null, "turnover_yi": null, "main_inflow_yi": null}}
  ],
  "top_concepts": [
    {{"name": "", "change_pct": null, "limit_up_count": null}}
  ],
  "finance": {{
    "bank": {{"change_pct": null, "turnover_yi": null, "main_inflow_yi": null, "pb": null}},
    "securities": {{"change_pct": null, "turnover_yi": null, "main_inflow_yi": null}},
    "insurance": {{"change_pct": null, "turnover_yi": null, "main_inflow_yi": null}}
  }}
}}
```

# 字段说明
- market_breadth: 市场宽度（advance_count=上涨家数, decline_count=下跌家数, limit_up/down_count=涨跌停家数, total_turnover_yi=两市成交额(亿), north_net_inflow_yi=北向资金净流入(亿), main_net_inflow_yi=主力净流入(亿)）
- sentiment: 打板情绪（first_board_count=首板数, consecutive_board_count=连板数, failed_board_count=炸板数, limit_up_success_rate_pct=打板成功率%, sentiment_label=情绪标签如"亢奋/温和/低迷", sentiment_score=0-100情绪打分）
- top_sectors: 行业板块涨幅 Top 10（name=板块名, change_pct=涨跌幅%, turnover_yi=成交额(亿), main_inflow_yi=主力净流入(亿)）
- top_concepts: 概念题材涨幅 Top 10（name=题材名, change_pct=涨跌幅%, limit_up_count=涨停家数）
- finance: 大金融三大板块（change_pct=板块涨跌幅%, turnover_yi=成交额(亿), main_inflow_yi=主力净流入(亿), pb=市净率仅银行）
"""


# ============================================================
# DeepSeek 加工：结构化 JSON → 文字策略报告
# ============================================================

REPORT_PROMPT_TEMPLATE = """你是某头部券商的首席市场策略分析师。请根据以下 {date} 的市场数据，撰写一份专业的【每日市场策略简报】。

# 结构化市场数据
```json
{json_str}
```
{trend_context}
{ai_report_context}

# 输出格式（Markdown，严格遵循）

## 一、市场全景速览
（引用当日具体数值：涨跌家数、涨停/跌停数、情绪打分，一句话定性判断今日市场状态）

## 二、情绪与结构研判
- **涨跌结构**: （引用涨跌家数、涨停/跌停/炸板具体数值，并与近5日均值对比，判断情绪是升温还是退潮）
- **资金信号**: （如有成交额、北向资金数据则引用；如无则从涨跌家数和炸板率推断资金行为）
- **打板情绪**: （引用首板/连板/炸板数据，结合 max_lb 最高连板数和炸板率，判断超短线情绪状态）
- **市场宽度**: （引用 high20/low20 新高新低数据，判断市场整体强弱格局）

## 三、板块轮动与主线
（从 top_sectors 和 top_concepts 提炼主线逻辑。结合 AI 早报推荐的题材和个股表现，判断哪些题材在发酵、哪些在退潮）

## 四、AI 选股信号验证
（引用 AI 早报推荐股票的当日实际涨跌表现，评估选股信号的有效性。哪些题材推荐准确？哪些出现分歧？）

## 五、大金融板块追踪
（银行/证券/保险三大板块表现，联动效应，对大盘的方向性指引）

## 六、策略建议
- **仓位建议**: （根据情绪打分和趋势对比给出具体百分比区间，如"维持40%-50%"，并说明调整条件）
- **明日关注**: （列出 2-3 个具体方向，引用板块数据和 AI 推荐股票作为依据）
- **风险提示**: （引用具体数值作为预警信号，如"炸板率超过30%"或"跌停家数 > XX"）

---
*数据来源: market_sentiment + iWencai + AI早报 · AI 解读仅供参考，不构成投资建议*

# 约束
- **每个判断必须引用具体数值**，禁止说"数据缺失""数据不可得"等模糊表述
- 如果某维度确实没有数据，用其他维度推断，不要跳过
- 800-1500 字
- 语言专业、简洁、有洞察力，像真正的券商晨报
"""


# ============================================================
# 两步博弈报告：Prompt 模板
# ============================================================

ANALYST_PROMPT = """今天是 {date}。以下是系统过去 10 个交易日的综合数据。请作为数据分析师，以**题材趋势**为核心主线提取关键事实。

{context}

# 你的任务：生成一份【题材趋势事实摘要】（800 字以内，Markdown）

重点是题材层面的演变趋势，个股只做简要佐证。

格式：

## 1. 情绪周期定位
（引用情绪分10日走势和30日分位数的具体数值，定位当前阶段）

## 2. 宏观环境
（引用 CPI/PPI/PMI 具体数值。如无数据则跳过）

## 3. 题材趋势全景（核心部分）

将持续发酵的题材按趋势状态分类：

### 强化中（题材催化持续兑现，板块整体走强）
（列出题材名+持续天数+核心催化事件一句话+板块整体表现）

### 分歧中（题材逻辑成立但个股分化严重）
（列出题材名+分歧原因+领涨vs领跌个股各1只）

### 退潮信号（前期强势但开始走弱）
（列出题材名+走弱信号+领跌个股1只）

## 4. AI 早报信号准确度
（整体命中率+核心vs其他对比+命中率最高/最低的日子）

## 5. 蓄势待发方向
（引用蓄势数据，简要列出题材强但个股滞涨的方向，不需要逐只分析）

# 约束
- 重点写题材趋势，个股只做佐证不要大篇幅研判
- 每个题材引用催化事件关键词即可，不需要展开全文
- 禁止用"部分""一些""若干"等模糊词
- 表格中"-"表示无数据，跳过不提
"""

STRATEGIST_PROMPT = """今天是 {date}。以下是数据分析师提供的题材趋势事实摘要：

{fact_summary}

# 你的任务：生成最终的【每日市场策略简报】

以题材趋势为主线，个股为辅。简洁有力，不啰嗦。

## 一、多空博弈

### 看多论点（引用具体题材趋势）
### 看空论点（引用具体数据和指标）
### 博弈结论（未来1-3天方向判断）

## 二、情绪周期研判
（当前阶段+30日分位+短期演变方向）

## 三、题材趋势研判（核心部分）

基于分析师的分类，对每个趋势方向给出判断：

**强化中题材**: （哪些可以继续跟进？催化兑现到了什么阶段？）
**分歧中题材**: （分歧可能向哪个方向解决？跟踪信号是什么？）
**退潮信号题材**: （明确回避）

（每个题材1-2句话即可，不要长篇大论）

## 四、操作策略
- **仓位建议**: （具体百分比 + 调整条件）
- **重点关注方向**: （2-3个题材方向+1只代表个股）
- **蓄势待发方向**: （简要提及，1-2句话）
- **明确回避**: （退潮题材+领跌个股）
- **止损/风控**: （具体预警信号和阈值）

---
*数据来源: market_sentiment + AI早报 + 题材追踪 + 宏观数据 · 仅供研究参考*

# 约束
- 以题材趋势为主线，个股只做简要佐证
- 题材研判每条1-2句话，简洁直接
- 禁止模糊表述，必须引用具体题材名和数据
- 禁止对个股做"仍有空间""还有上涨潜力"等主观预测，只陈述客观事实
- 1200 字以内
"""


# ============================================================
# 综合数据池构建（近 10 日）
# ============================================================

def _build_comprehensive_context(today: str) -> str:
    """构建近 10 个交易日的综合数据池，供 DeepSeek 分析"""
    parts = []

    # 1. 近 10 日情绪趋势（含 30 日分位数）
    parts.append(_build_sentiment_trend_10d(today))

    # 2. 宏观经济环境
    parts.append(_build_macro_indicators())

    # 3. 近 10 日 AI 早报复盘
    parts.append(_build_ai_report_replay_10d(today))

    # 4. 近 10 日题材轮动（含详细催化事件）
    parts.append(_build_topic_rotation_10d(today))

    # 5. 当日 AI 早报核心股票深度信息
    parts.append(_build_core_stock_details(today))

    # 6. 蓄势待发标的（题材强 + 个股滞涨）
    parts.append(_build_dormant_candidates(today))

    return "\n\n".join(p for p in parts if p)


def _build_sentiment_trend_10d(today: str) -> str:
    """近 10 日情绪指标趋势（只输出有数据的列）"""
    try:
        import pandas as pd
        csv_path = DATA_DIR / "signals" / "market_sentiment.csv"
        df = pd.read_csv(csv_path)
        df["date"] = df["date"].astype(str)
        recent = df[df["date"] <= today].tail(10)

        # 基础列（100% 有数据）
        base_cols = {
            "涨停": "limit_up_count",
            "跌停": "limit_down_count",
            "炸板": "broken_limit_up_count",
            "炸板率": "broken_limit_up_rate",
            "情绪分": "sentiment_score",
            "涨家": "up_count",
            "跌家": "down_count",
            "新高20": "high20",
            "新低20": "low20",
            "连板梯队": "consecutive_limit_up_2_count",  # 2连板+
        }

        # 可选列（只在近10天全部非空时才输出）
        optional_cols = {
            "PE中位": ("pe_median", ".1f"),
            "换手率": ("turnover_median", ".2f"),
            "指数": ("index_close", ".0f"),
            "首板": ("zb_num", ".0f"),
            "赚钱效应%": ("profit_effect_pct", ".1f"),
        }

        # 构建表头 - 只保留近10天100%有数据的可选列
        headers = list(base_cols.keys())
        for label, (col, _) in optional_cols.items():
            if recent[col].notna().all():
                headers.append(label)

        lines = ["# 近 10 日市场情绪趋势\n"]
        lines.append("| 日期 | " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["------"] * (len(headers) + 1)) + "|")

        for _, r in recent.iterrows():
            vals = [r["date"]]
            for label in headers:
                if label == "炸板率":
                    v = r.get("broken_limit_up_rate")
                    vals.append(f"{v*100:.0f}%" if pd.notna(v) else "-")
                elif label == "情绪分":
                    v = r.get("sentiment_score")
                    vals.append(f"{v:.0f}" if pd.notna(v) else "-")
                elif label == "连板梯队":
                    lb2 = r.get("consecutive_limit_up_2_count", 0)
                    lb3 = r.get("consecutive_limit_up_3_plus_count", 0)
                    vals.append(f"2板{int(lb2) if pd.notna(lb2) else 0}/3板+{int(lb3) if pd.notna(lb3) else 0}")
                else:
                    # 查找对应的列
                    found = False
                    for bc_label, bc_col in base_cols.items():
                        if bc_label == label:
                            v = r.get(bc_col)
                            vals.append(str(int(v)) if pd.notna(v) else "-")
                            found = True
                            break
                    if not found:
                        for oc_label, (oc_col, oc_fmt) in optional_cols.items():
                            if oc_label == label:
                                v = r.get(oc_col)
                                vals.append(format(v, oc_fmt) if pd.notna(v) else "-")
                                found = True
                                break
                    if not found:
                        vals.append("-")
            lines.append("| " + " | ".join(vals) + " |")

        # 均值和趋势方向
        if len(recent) >= 3:
            lines.append(f"\n**10日均值**: 涨停={recent['limit_up_count'].mean():.0f}, "
                         f"跌停={recent['limit_down_count'].mean():.0f}, "
                         f"炸板={recent['broken_limit_up_count'].mean():.0f}, "
                         f"情绪={recent['sentiment_score'].mean():.1f}, "
                         f"新高/新低={recent['high20'].mean():.0f}/{recent['low20'].mean():.0f}")

            first_half = recent.head(5)['sentiment_score'].mean()
            second_half = recent.tail(5)['sentiment_score'].mean()
            direction = "↓退潮" if second_half < first_half else "↑升温"
            lines.append(f"**趋势**: 前5日均 {first_half:.0f} → 后5日均 {second_half:.0f} ({direction})")

        # 30 日情绪分位数
        df_all = df[df["date"] <= today].tail(30)
        if len(df_all) >= 10:
            today_score = recent["sentiment_score"].iloc[-1] if not recent.empty else 0
            percentile = (df_all["sentiment_score"] <= today_score).sum() / len(df_all) * 100

            today_lu = recent["limit_up_count"].iloc[-1] if not recent.empty else 0
            lu_pct = (df_all["limit_up_count"] <= today_lu).sum() / len(df_all) * 100

            today_brk = recent["broken_limit_up_count"].iloc[-1] if not recent.empty else 0
            brk_pct = (df_all["broken_limit_up_count"] <= today_brk).sum() / len(df_all) * 100

            lines.append(f"\n**30日情绪分位**: 情绪分={percentile:.0f}%分位"
                         f"（{int(percentile//33)+1}/3档: {'冰点' if percentile<33 else '中性' if percentile<67 else '亢奋'}）, "
                         f"涨停数={lu_pct:.0f}%分位, 炸板数={brk_pct:.0f}%分位")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Sentiment trend failed: {e}")
        return ""


def _build_ai_report_replay_10d(today: str) -> str:
    """近 10 日 AI 早报推荐 vs 实际表现复盘"""
    try:
        import pandas as pd
        import sys as _sys
        from pathlib import Path as P
        backend_root = P(__file__).resolve().parent.parent.parent
        if str(backend_root) not in _sys.path:
            _sys.path.insert(0, str(backend_root))
        from modules.backtest.signal_backtest import _parse_reports

        pools = _parse_reports()
        ohlcv_dir = DATA_DIR.parent / "backtest_ohlcv"

        # 获取近 10 个有 pool 的交易日
        sorted_dates = sorted([d for d in pools.keys() if d <= today], reverse=True)[:10]
        sorted_dates.reverse()  # 从早到晚

        if not sorted_dates:
            return ""

        lines = ["# 近 10 日 AI 早报信号复盘\n"]

        for d in sorted_dates:
            pool = pools[d]
            if not pool:
                continue

            # 获取每只股票的当日实际涨跌
            up = 0
            down = 0
            total = 0
            core_up = 0
            core_total = 0
            top_gainers = []

            for sym, info in pool.items():
                csv_file = ohlcv_dir / f"{sym}.csv"
                if csv_file.exists():
                    try:
                        df_s = pd.read_csv(csv_file)
                        df_s["date"] = df_s["date"].astype(str)
                        row = df_s[df_s["date"] == d]
                        if not row.empty:
                            r = row.iloc[0]
                            ret = r.get("pct_change", 0)
                            if pd.isna(ret):
                                ret = ((r["close"] - r["open"]) / r["open"] * 100) if r["open"] > 0 else 0
                            total += 1
                            if ret > 0:
                                up += 1
                            else:
                                down += 1
                            if info.get("weight_type") == "core":
                                core_total += 1
                                if ret > 0:
                                    core_up += 1
                            if ret > 5:
                                top_gainers.append((info.get("name", sym), ret))
                    except:
                        pass

            if total > 0:
                hit_rate = up / total * 100
                core_rate = f"{core_up}/{core_total}" if core_total > 0 else "-"
                lines.append(f"**{d}**: 推荐{total}只, {up}涨/{down}跌, 命中率{hit_rate:.0f}%, 核心{core_rate}")
                if top_gainers:
                    top_gainers.sort(key=lambda x: -x[1])
                    gainers_str = ", ".join(f"{n}+{r:.1f}%" for n, r in top_gainers[:3])
                    lines.append(f"  → 大幅上涨: {gainers_str}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"AI report replay failed: {e}")
        return ""


def _build_topic_rotation_10d(today: str) -> str:
    """近 10 日题材轮动追踪（结合 stock_pool + zizizaizai_topics 详细逻辑）"""
    try:
        import sys as _sys
        from pathlib import Path as P
        from collections import defaultdict
        backend_root = P(__file__).resolve().parent.parent.parent
        if str(backend_root) not in _sys.path:
            _sys.path.insert(0, str(backend_root))
        from modules.backtest.signal_backtest import _parse_reports

        pools = _parse_reports()

        # 获取近 10 个有 pool 的交易日
        sorted_dates = sorted([d for d in pools.keys() if d <= today and len(pools[d]) > 0], reverse=True)[:10]
        sorted_dates.reverse()

        if not sorted_dates:
            return ""

        # 统计每个题材出现的次数和日期
        topic_dates = defaultdict(list)
        for d in sorted_dates:
            pool = pools[d]
            day_topics = set()
            for sym, info in pool.items():
                concept = info.get("concept", "")
                if concept:
                    day_topics.add(concept)
            for t in day_topics:
                topic_dates[t].append(d)

        persistent = {k: v for k, v in topic_dates.items() if len(v) >= 2}
        one_shot = {k: v for k, v in topic_dates.items() if len(v) == 1}

        # 加载 zizizaizai_topics.json 获取详细题材逻辑
        topics_file = DATA_DIR / "signals" / "zizizaizai_topics.json"
        topics_detail = {}
        if topics_file.exists():
            with open(topics_file, "r", encoding="utf-8") as f:
                all_topics = json.load(f)
            for t in all_topics:
                name = t.get("name", "")
                # 去掉名称中的日期后缀（如 "存储芯片(250921)" → "存储芯片"）
                clean_name = name.split("(")[0].strip()
                topics_detail[clean_name] = t
                topics_detail[name] = t

        lines = ["# 近 10 日题材轮动追踪\n"]

        if persistent:
            lines.append(f"**持续发酵题材（≥2天，共{len(persistent)}个）:**")
            for topic, dates in sorted(persistent.items(), key=lambda x: -len(x[1])):
                # 查找详细逻辑
                detail = topics_detail.get(topic)
                if detail:
                    content = detail.get("content", "")
                    # 截取前 200 字的催化事件
                    logic = content[:200].replace("\n", " ").strip() if content else ""
                    lines.append(f"  - **{topic}** ({len(dates)}天)")
                    if logic:
                        lines.append(f"    催化: {logic}...")
                else:
                    lines.append(f"  - {topic} ({len(dates)}天)")

        if one_shot:
            lines.append(f"\n**一日游题材（{len(one_shot)}个）:**")

        # 最新一天的题材详情（含个股相关性）
        latest_date = sorted_dates[-1]
        latest_pool = pools[latest_date]
        lines.append(f"\n**最新题材详情（{latest_date}）:**")
        topic_stocks = defaultdict(list)
        for sym, info in latest_pool.items():
            concept = info.get("concept", "其他")
            topic_stocks[concept].append((info.get("name", sym), info.get("weight_type", "other"), sym))

        for concept, stocks in topic_stocks.items():
            core = [(n, s) for n, w, s in stocks if w == "core"][:5]
            other = [(n, s) for n, w, s in stocks if w != "core"]

            # 查找题材详细逻辑
            detail = topics_detail.get(concept)
            logic = ""
            if detail and detail.get("content"):
                logic = detail["content"][:300].replace("\n", " ").strip()

            lines.append(f"\n  ### {concept}")
            if logic:
                lines.append(f"  逻辑: {logic}...")

            if core:
                # 查找每只核心股票在 topics 中的相关性
                for name, sym in core:
                    relevance = ""
                    if detail and detail.get("rows"):
                        for row in detail["rows"]:
                            if row.get("个股") == name:
                                relevance = row.get("相关性", "")
                                source = row.get("信息源", "")
                                if relevance:
                                    relevance = f" [{source}: {relevance[:80]}]"
                                break
                    lines.append(f"  - **{name}({sym})** [核心]{relevance}")

            if other:
                other_names = [n for n, s in other[:5]]
                lines.append(f"  - 其他: {', '.join(other_names)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Topic rotation failed: {e}")
        return ""


def _build_macro_indicators() -> str:
    """获取最新宏观经济指标（CPI/PPI/PMI/社融/M2）"""
    try:
        import requests as _req

        lines = ["# 宏观经济环境\n"]

        # 东方财富宏观数据 API（免费）
        # CPI: 全国居民消费价格指数
        # PPI: 工业生产者出厂价格指数
        # PMI: 制造业采购经理指数
        indicators = [
            ("CPI", "CPI", "全国居民消费价格指数同比"),
            ("PPI", "PPI", "工业生产者出厂价格指数同比"),
            ("PMI", "PMI", "制造业采购经理指数"),
        ]

        macro_data = {}
        for key, code, label in indicators:
            try:
                url = f"https://datacenter-web.eastmoney.com/api/data/v1/get"
                report_name = "RPT_ECONOMY_CPI"
                yoy_col = "NATIONAL_SAME"
                if key == "PPI":
                    report_name = "RPT_ECONOMY_PPI"
                    yoy_col = "BASE_SAME"
                elif key == "PMI":
                    report_name = "RPT_ECONOMY_PMI"
                    yoy_col = "MAKE_INDEX"

                params = {
                    "reportName": report_name,
                    "columns": f"REPORT_DATE,{yoy_col}",
                    "pageSize": "1",
                    "sortColumns": "REPORT_DATE",
                    "sortTypes": "-1",
                    "source": "WEB",
                    "client": "WEB",
                }

                r = _req.get(url, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success") and data.get("result"):
                        rows = data["result"].get("data", [])
                        if rows:
                            latest = rows[0]
                            macro_data[key] = {
                                "label": label,
                                "date": latest.get("REPORT_DATE", "")[:10],
                                "value": latest.get(yoy_col),
                            }
            except Exception as e:
                logger.warning(f"Failed to fetch {key}: {e}")

        if macro_data:
            for key, d in macro_data.items():
                val = d.get("value")
                if val is not None:
                    val_f = float(val)
                    if key == "PMI":
                        lines.append(f"- **{d['label']}** ({d['date']}): {val_f:.1f}%"
                                     f"（{'扩张' if val_f >= 50 else '收缩'}区间）")
                    else:
                        sign = "+" if val_f > 0 else ""
                        lines.append(f"- **{d['label']}** ({d['date']}): {sign}{val_f:.1f}%")
        else:
            return ""

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Macro indicators failed: {e}")
        return ""


def _build_core_stock_details(today: str) -> str:
    """当日 AI 早报核心股票的近 5 日 K 线走势"""
    try:
        import pandas as pd
        import sys as _sys
        from pathlib import Path as P
        backend_root = P(__file__).resolve().parent.parent.parent
        if str(backend_root) not in _sys.path:
            _sys.path.insert(0, str(backend_root))
        from modules.backtest.signal_backtest import _parse_reports

        pools = _parse_reports()
        pool = pools.get(today, {})
        if not pool:
            # 最近一天
            for d in sorted(pools.keys(), reverse=True):
                if d <= today and len(pools[d]) > 0:
                    pool = pools[d]
                    break

        if not pool:
            return ""

        ohlcv_dir = DATA_DIR.parent / "backtest_ohlcv"
        core_stocks = {sym: info for sym, info in pool.items() if info.get("weight_type") == "core"}
        other_stocks = {sym: info for sym, info in pool.items() if info.get("weight_type") != "core"}

        lines = [f"# 当日全部标的近 5 日走势（核心{len(core_stocks)}只 + 其他{len(other_stocks)}只）\n"]

        # 核心标的详细走势
        if core_stocks:
            lines.append("## 核心标的")
            for sym, info in sorted(core_stocks.items()):
                name = info.get("name", sym)
                concept = info.get("concept", "")
                csv_file = ohlcv_dir / f"{sym}.csv"
                if not csv_file.exists():
                    continue
                try:
                    df_s = pd.read_csv(csv_file)
                    df_s["date"] = df_s["date"].astype(str)
                    recent = df_s[df_s["date"] <= today].tail(5)
                    if recent.empty:
                        continue
                    kline = []
                    for _, r in recent.iterrows():
                        ret = r.get("pct_change", 0)
                        if pd.isna(ret):
                            ret = ((r["close"] - r["open"]) / r["open"] * 100) if r["open"] > 0 else 0
                        kline.append(f"{r['date'][5:]}:{r['close']:.0f}({ret:+.1f}%)")
                    first_close = recent.iloc[0]["close"]
                    last_close = recent.iloc[-1]["close"]
                    total_ret = (last_close - first_close) / first_close * 100
                    lines.append(f"- **{name}({sym})** [{concept}] 5日{total_ret:+.1f}%")
                    lines.append(f"  {' → '.join(kline)}")
                except:
                    pass

        # 其他标的（简略版，按5日涨幅排序）
        if other_stocks:
            lines.append(f"\n## 其他标的（{len(other_stocks)}只，按5日涨跌排序）")
            other_results = []
            for sym, info in other_stocks.items():
                name = info.get("name", sym)
                concept = info.get("concept", "")
                csv_file = ohlcv_dir / f"{sym}.csv"
                if not csv_file.exists():
                    continue
                try:
                    df_s = pd.read_csv(csv_file)
                    df_s["date"] = df_s["date"].astype(str)
                    recent = df_s[df_s["date"] <= today].tail(5)
                    if recent.empty:
                        continue
                    first_close = recent.iloc[0]["close"]
                    last_close = recent.iloc[-1]["close"]
                    total_ret = (last_close - first_close) / first_close * 100
                    today_ret = recent.iloc[-1].get("pct_change", 0)
                    if pd.isna(today_ret):
                        today_ret = ((recent.iloc[-1]["close"] - recent.iloc[-1]["open"]) / recent.iloc[-1]["open"] * 100) if recent.iloc[-1]["open"] > 0 else 0
                    other_results.append((name, sym, concept, total_ret, today_ret))
                except:
                    pass

            # 按 5 日涨幅排序，展示全部
            other_results.sort(key=lambda x: -x[3])
            for name, sym, concept, ret5, ret1 in other_results:
                arrow = "▲" if ret1 >= 0 else "▼"
                lines.append(f"- {arrow} {name}({sym}) [{concept}] 5日{ret5:+.1f}% 当日{ret1:+.1f}%")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Core stock details failed: {e}")
        return ""


# ============================================================
# 蓄势待发标的筛选（题材强 + 个股滞涨）
# ============================================================

def _build_dormant_candidates(today: str) -> str:
    """筛选题材强但个股滞涨的蓄势待发标的

    筛选条件：
    1. 所属题材在 zizizaizai_topics.json 中有详细数据（强题材）
    2. 近10个交易日内该股至少有1次涨停（有过异动）
    3. 近5日涨幅在 [-3%, +5%] 之间（滞涨）
    4. 当日跌幅 >= -3%（未破异动）
    5. 5日均线走平或上升（未破趋势）
    6. 非 ST、非科创板 688（基本面门槛）
    """
    try:
        import pandas as pd
        import sys as _sys
        from pathlib import Path as P
        from collections import defaultdict
        backend_root = P(__file__).resolve().parent.parent.parent
        if str(backend_root) not in _sys.path:
            _sys.path.insert(0, str(backend_root))
        from modules.backtest.signal_backtest import _parse_reports

        pools = _parse_reports()

        # 加载题材热度数据
        topics_file = DATA_DIR / "signals" / "zizizaizai_topics.json"
        topic_strength = {}  # topic_name -> {strength_score, stock_names}
        if topics_file.exists():
            with open(topics_file, "r", encoding="utf-8") as f:
                all_topics = json.load(f)
            for t in all_topics:
                name = t.get("name", "")
                clean_name = name.split("(")[0].strip()
                rows = t.get("rows", [])
                content = t.get("content", "")
                # 题材强度 = rows 数量 × content 长度（信息越丰富越强）
                strength = len(rows) + min(len(content) / 100, 10)
                stock_names = {r.get("个股", "") for r in rows if r.get("个股")}
                topic_strength[clean_name] = {
                    "strength": strength,
                    "stock_names": stock_names,
                    "rows": rows,
                }

        # 获取近10日 pool 数据
        sorted_dates = sorted([d for d in pools.keys() if d <= today and len(pools[d]) > 0], reverse=True)[:10]
        if not sorted_dates:
            return ""

        latest_date = sorted_dates[0]
        pool = pools.get(latest_date, {})
        ohlcv_dir = DATA_DIR.parent / "backtest_ohlcv"

        # 获取每只股票近10日的涨停信息
        candidates = []
        for sym, info in pool.items():
            # 排除科创板
            if sym.startswith("SH688") or sym.startswith("SZ30"):
                pass  # 创业板保留，只排除688
            if sym.startswith("SH688"):
                continue

            concept = info.get("concept", "")
            name = info.get("name", sym)

            # 检查题材强度
            topic_data = topic_strength.get(concept)
            if not topic_data or topic_data["strength"] < 5:
                continue

            csv_file = ohlcv_dir / f"{sym}.csv"
            if not csv_file.exists():
                continue
            try:
                df_s = pd.read_csv(csv_file)
                df_s["date"] = df_s["date"].astype(str)
                recent_10 = df_s[df_s["date"] <= today].tail(10)
                recent_5 = recent_10.tail(5)
                if len(recent_5) < 3:
                    continue

                # 1. 近10日是否有涨停（涨幅 >= 9.5%）
                recent_10["pct"] = recent_10["close"].pct_change() * 100
                has_limit_up = (recent_10["pct"] >= 9.5).any()
                if not has_limit_up:
                    continue

                # 2. 近5日涨幅（滞涨）
                ret_5d = (recent_5.iloc[-1]["close"] - recent_5.iloc[0]["close"]) / recent_5.iloc[0]["close"] * 100
                if not (-3 <= ret_5d <= 5):
                    continue

                # 3. 当日跌幅（未破异动）
                last = recent_5.iloc[-1]
                ret_1d_pct = last.get("pct_change", 0)
                if pd.isna(ret_1d_pct):
                    prev_close = recent_5.iloc[-2]["close"] if len(recent_5) >= 2 else last["open"]
                    ret_1d_pct = ((last["close"] - prev_close) / prev_close * 100) if prev_close > 0 else 0
                if ret_1d_pct < -3:
                    continue

                # 4. 5日均线趋势（未破趋势）
                ma5_now = recent_5["close"].mean()
                if len(recent_5) >= 4:
                    ma5_prev = recent_5.iloc[:-1]["close"].mean()
                    trend_ok = ma5_now >= ma5_prev * 0.98  # 均线最多微跌2%
                else:
                    trend_ok = True
                if not trend_ok:
                    continue

                # 5. 从题材数据中获取个股产业链位置
                relevance = ""
                info_source = ""
                category = ""
                for r in topic_data["rows"]:
                    if r.get("个股") == name:
                        relevance = r.get("相关性", "")[:80]
                        info_source = r.get("信息源", "")
                        cat1 = r.get("一级大类", "")
                        cat2 = r.get("二级小类", "")
                        cat3 = r.get("三级细分", "")
                        category = f"{cat1}/{cat2}/{cat3}"
                        break

                # 6. 涨停距今天数
                limit_up_days_ago = None
                for i in range(len(recent_10) - 1, -1, -1):
                    if pd.notna(recent_10.iloc[i].get("pct")) and recent_10.iloc[i]["pct"] >= 9.5:
                        limit_up_days_ago = len(recent_10) - 1 - i
                        break

                candidates.append({
                    "name": name,
                    "sym": sym,
                    "concept": concept,
                    "weight": info.get("weight_type", "other"),
                    "ret_5d": ret_5d,
                    "ret_1d": ret_1d_pct,
                    "close": last["close"],
                    "topic_strength": topic_data["strength"],
                    "category": category,
                    "relevance": relevance,
                    "info_source": info_source,
                    "limit_up_days_ago": limit_up_days_ago,
                })
            except:
                pass

        if not candidates:
            return ""

        # 按题材强度排序
        candidates.sort(key=lambda x: (-x["topic_strength"], x["ret_5d"]))

        lines = ["# 蓄势待发标的（强题材 + 近10日有涨停 + 滞涨 + 趋势未破）\n"]
        lines.append("筛选条件: 题材信息丰富(≥5分) | 近10日有涨停 | 5日涨幅[-3%,+5%] | 当日未破异动(>-3%) | 均线趋势完整\n")

        by_topic = defaultdict(list)
        for c in candidates:
            by_topic[c["concept"]].append(c)

        for topic, stocks in sorted(by_topic.items(), key=lambda x: -x[1][0]["topic_strength"]):
            lines.append(f"\n**{topic}**（题材强度{stocks[0]['topic_strength']:.0f}分）:")
            for s in stocks:
                tag = "[核心]" if s["weight"] == "core" else ""
                lu_info = f"涨停于{s['limit_up_days_ago']}日前" if s["limit_up_days_ago"] is not None else ""
                lines.append(f"  - {s['name']}({s['sym']}){tag} 收盘{s['close']:.0f} 5日{s['ret_5d']:+.1f}% 当日{s['ret_1d']:+.1f}% {lu_info}")
                if s["category"]:
                    lines.append(f"    产业链: {s['category']} [{s['info_source']}: {s['relevance']}...]")
                else:
                    lines.append(f"    (未找到个股在题材中的详细归属)")

        lines.append(f"\n注: 以上{len(candidates)}只标的均满足题材强+滞涨+趋势完整条件。建议结合排雷审查后决策。")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Dormant candidates failed: {e}")
        return ""


# ============================================================
# 数据增强：从 market_sentiment.csv + AI 早报 + 个股行情 补充数据
# ============================================================

def _enrich_with_sentiment_csv(structured: dict, today: str) -> dict:
    """用 market_sentiment.csv 的精确数据覆盖 structured JSON 中的 null 值"""
    try:
        import pandas as pd
        csv_path = DATA_DIR / "signals" / "market_sentiment.csv"
        if not csv_path.exists():
            return structured

        df = pd.read_csv(csv_path)
        df["date"] = df["date"].astype(str)
        row = df[df["date"] == today]
        if row.empty:
            # 找最近的一天
            row = df[df["date"] <= today].tail(1)
        if row.empty:
            return structured

        r = row.iloc[0]
        breadth = structured.setdefault("market_breadth", {})
        if breadth.get("advance_count") is None:
            breadth["advance_count"] = int(r["up_count"]) if pd.notna(r.get("up_count")) else None
        if breadth.get("decline_count") is None:
            breadth["decline_count"] = int(r["down_count"]) if pd.notna(r.get("down_count")) else None
        if breadth.get("limit_up_count") is None:
            breadth["limit_up_count"] = int(r["limit_up_count"]) if pd.notna(r.get("limit_up_count")) else None
        if breadth.get("limit_down_count") is None:
            breadth["limit_down_count"] = int(r["limit_down_count"]) if pd.notna(r.get("limit_down_count")) else None

        sentiment = structured.setdefault("sentiment", {})
        if sentiment.get("first_board_count") is None:
            sentiment["first_board_count"] = int(r["zb_num"]) if pd.notna(r.get("zb_num")) else None
        if sentiment.get("consecutive_board_count") is None:
            lb2 = int(r["lb_2_num"]) if pd.notna(r.get("lb_2_num")) else 0
            lb3 = int(r["lb_3_num"]) if pd.notna(r.get("lb_3_num")) else 0
            sentiment["consecutive_board_count"] = lb2 + lb3
        if sentiment.get("failed_board_count") is None:
            sentiment["failed_board_count"] = int(r["broken_limit_up_count"]) if pd.notna(r.get("broken_limit_up_count")) else None
        if sentiment.get("limit_up_success_rate_pct") is None:
            sentiment["limit_up_success_rate_pct"] = round((1 - r["broken_limit_up_rate"]) * 100, 1) if pd.notna(r.get("broken_limit_up_rate")) else None
        if sentiment.get("sentiment_score") is None:
            sentiment["sentiment_score"] = float(r["sentiment_score"]) if pd.notna(r.get("sentiment_score")) else None

        # 新增市场宽度补充字段
        breadth["high20_count"] = int(r["high20"]) if pd.notna(r.get("high20")) else None
        breadth["low20_count"] = int(r["low20"]) if pd.notna(r.get("low20")) else None
        breadth["max_consecutive_lb"] = int(r["max_lb_num"]) if pd.notna(r.get("max_lb_num")) else None
        breadth["up_down_ratio"] = float(r["up_down_ratio"]) if pd.notna(r.get("up_down_ratio")) else None

        logger.info(f"Enriched structured data with market_sentiment.csv (date={r['date']})")
        return structured
    except Exception as e:
        logger.error(f"Failed to enrich with sentiment CSV: {e}")
        return structured


def _build_trend_context(today: str) -> str:
    """从 market_sentiment.csv 构建近 5 天趋势对比数据"""
    try:
        import pandas as pd
        csv_path = DATA_DIR / "signals" / "market_sentiment.csv"
        if not csv_path.exists():
            return ""

        df = pd.read_csv(csv_path)
        df["date"] = df["date"].astype(str)
        recent = df[df["date"] <= today].tail(5).reset_index(drop=True)
        if recent.empty:
            return ""

        lines = ["\n# 近5日市场趋势对比"]
        cols = ["date", "up_count", "down_count", "limit_up_count", "limit_down_count",
                "broken_limit_up_count", "max_lb_num", "sentiment_score", "up_down_ratio"]
        header = " | ".join(cols)
        lines.append(header)
        lines.append(" | ".join(["---"] * len(cols)))
        for _, r in recent.iterrows():
            vals = []
            for c in cols:
                v = r.get(c, "")
                vals.append(str(int(v)) if pd.notna(v) and isinstance(v, (int, float)) else str(v))
            lines.append(" | ".join(vals))

        # 计算均值
        if len(recent) >= 2:
            lines.append(f"\n近5日均值: 涨停={recent['limit_up_count'].mean():.0f}, "
                         f"跌停={recent['limit_down_count'].mean():.0f}, "
                         f"炸板={recent['broken_limit_up_count'].mean():.0f}, "
                         f"情绪打分={recent['sentiment_score'].mean():.1f}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to build trend context: {e}")
        return ""


def _load_ai_report_summary(today: str) -> str:
    """加载当天 AI 早报推荐的股票 + 对应个股的当日行情数据"""
    try:
        import pandas as pd
        import sys as _sys
        from pathlib import Path as P
        # signal_backtest 在 backend/modules/backtest/
        backend_root = P(__file__).resolve().parent.parent.parent
        if str(backend_root) not in _sys.path:
            _sys.path.insert(0, str(backend_root))
        from modules.backtest.signal_backtest import _parse_reports

        pools = _parse_reports()
        pool = pools.get(today, {})

        if not pool:
            # 找最近一天的
            for d in sorted(pools.keys(), reverse=True):
                if d <= today and len(pools[d]) > 0:
                    pool = pools[d]
                    today = d
                    break

        if not pool:
            return ""

        parts = [f"\n# AI 早报推荐股票（{today}选股信号）"]

        # pool: {symbol: {name, weight_type, ...}}
        stock_returns = {}
        for sym, info in pool.items():
            name = info.get("name", sym)
            weight = info.get("weight_type", "other")
            csv_file = DATA_DIR.parent / "backtest_ohlcv" / f"{sym}.csv"
            if csv_file.exists():
                try:
                    df_s = pd.read_csv(csv_file)
                    df_s["date"] = df_s["date"].astype(str)
                    row = df_s[df_s["date"] == today]
                    if not row.empty:
                        r = row.iloc[0]
                        ret = r.get("pct_change", 0)
                        if pd.isna(ret):
                            ret = ((r["close"] - r["open"]) / r["open"] * 100) if r["open"] > 0 else 0
                        stock_returns[sym] = {
                            "name": name,
                            "weight": weight,
                            "open": round(r["open"], 2),
                            "close": round(r["close"], 2),
                            "ret_pct": round(ret, 2),
                            "turnover_yi": round(r["amount"] / 1e8, 2) if r.get("amount") else None,
                        }
                except:
                    pass

        if stock_returns:
            parts.append(f"\nAI 推荐 {len(pool)} 只股票，以下为有当日行情的 {len(stock_returns)} 只：\n")
            # 按 weight 分组显示
            core_stocks = {k: v for k, v in stock_returns.items() if v["weight"] == "core"}
            other_stocks = {k: v for k, v in stock_returns.items() if v["weight"] != "core"}

            if core_stocks:
                parts.append("**核心标的：**")
                for sym, info in sorted(core_stocks.items(), key=lambda x: -x[1]["ret_pct"]):
                    arrow = "▲" if info["ret_pct"] >= 0 else "▼"
                    parts.append(f"- {arrow} {info['name']}({sym}) 涨跌:{info['ret_pct']:+.2f}% "
                                 f"开:{info['open']} 收:{info['close']}"
                                 + (f" 成交额:{info['turnover_yi']}亿" if info["turnover_yi"] else ""))

            if other_stocks:
                parts.append(f"\n**其他标的（{len(other_stocks)}只）：**")
                # 只显示涨跌幅前5和后5
                sorted_others = sorted(other_stocks.items(), key=lambda x: -x[1]["ret_pct"])
                for sym, info in sorted_others[:5]:
                    arrow = "▲" if info["ret_pct"] >= 0 else "▼"
                    parts.append(f"- {arrow} {info['name']}({sym}) {info['ret_pct']:+.2f}%")
                if len(sorted_others) > 10:
                    parts.append(f"- ...（省略 {len(sorted_others) - 10} 只）")
                for sym, info in sorted_others[-5:]:
                    if sym not in dict(sorted_others[:5]):
                        arrow = "▲" if info["ret_pct"] >= 0 else "▼"
                        parts.append(f"- {arrow} {info['name']}({sym}) {info['ret_pct']:+.2f}%")

            # 统计
            rets = [v["ret_pct"] for v in stock_returns.values()]
            up_count = sum(1 for r in rets if r > 0)
            down_count = sum(1 for r in rets if r < 0)
            avg_ret = sum(rets) / len(rets) if rets else 0
            parts.append(f"\n**AI 推荐统计: {up_count}涨/{down_count}跌/{len(rets)-up_count-down_count}平, "
                         f"平均涨跌={avg_ret:+.2f}%, "
                         f"核心标的平均={sum(v['ret_pct'] for v in core_stocks.values())/len(core_stocks):+.2f}%" if core_stocks else "")

        return "\n".join(parts)
    except Exception as e:
        logger.error(f"Failed to load AI report summary: {e}")
        return ""


# ============================================================
# 主流程
# ============================================================

def run_market_pulse_scan() -> dict:
    """执行完整市场体检：iWencai 采集 → DeepSeek 结构化 → DeepSeek 报告"""
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Starting Market Pulse scan for {today}...")

    # 1. iWencai 采集原始数据
    snapshot = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "groups": {},
    }
    for group_key in SCAN_TEMPLATES:
        logger.info(f"  Scanning group: {group_key}...")
        snapshot["groups"][group_key] = _run_scan_group(group_key)
        time.sleep(0.5)

    # 落盘原始快照
    save_dir = PULSE_DIR / today
    save_dir.mkdir(parents=True, exist_ok=True)
    raw_path = save_dir / "raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # 2. DeepSeek 将原始数据加工为结构化 JSON
    context_str = _build_context(snapshot)
    logger.info("Calling DeepSeek for structured analysis...")
    structured = {}
    try:
        raw_json = _call_deepseek([
            {"role": "system", "content": "You are a data analyst. Output only valid JSON, no explanation."},
            {"role": "user", "content": f"{STRUCTURED_PROMPT}\n\n# 原始数据\n{context_str}"},
        ], json_mode=True)
        structured = json.loads(raw_json)
        logger.info("DeepSeek structured analysis completed.")
    except Exception as e:
        logger.error(f"DeepSeek structured analysis failed: {e}")

    # 2.5 用 market_sentiment.csv 的精确数据补充 structured 中的 null 字段
    structured = _enrich_with_sentiment_csv(structured, today)

    # 3. 两步博弈式报告生成
    logger.info("Building comprehensive 10-day context...")
    comprehensive = _build_comprehensive_context(today)

    logger.info("Step 1: Data Analyst generating fact summary...")
    fact_summary = ""
    try:
        fact_summary = _call_deepseek([
            {"role": "system", "content": "你是一位严谨的量化数据分析师。只陈述事实，不做主观判断。输出简洁的 Markdown。"},
            {"role": "user", "content": ANALYST_PROMPT.format(date=today, context=comprehensive)},
        ])
        logger.info("Analyst fact summary completed.")
    except Exception as e:
        logger.error(f"Analyst step failed: {e}")
        fact_summary = f"（分析失败: {e}）"

    logger.info("Step 2: Strategy Lead generating directional outlook...")
    report = ""
    try:
        report = _call_deepseek([
            {"role": "system", "content": "你是一位资深私募策略主管，以思辨和博弈著称。你会先提出看多和看空的论点，自我反驳，然后给出平衡的结论。"},
            {"role": "user", "content": STRATEGIST_PROMPT.format(date=today, fact_summary=fact_summary)},
        ])
        logger.info("Strategy report completed.")
    except Exception as e:
        logger.error(f"Strategist step failed: {e}")
        report = fact_summary  # 降级：至少返回事实摘要

    # 4. 组装最终结果并落盘
    result = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "structured": structured,
        "report": report,
    }

    result_path = save_dir / "pulse.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"Market Pulse completed and saved to {result_path}")
    return result


def load_latest_pulse() -> dict | None:
    """加载最近一次市场体检结果（结构化 JSON + 报告）。"""
    if not PULSE_DIR.exists():
        return None

    date_dirs = sorted([d for d in PULSE_DIR.iterdir() if d.is_dir()], reverse=True)
    for d in date_dirs:
        # 优先加载新的 pulse.json
        pulse_file = d / "pulse.json"
        if pulse_file.exists():
            with open(pulse_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # 兼容旧版 snapshot.json（首次升级时可能存在）
        snapshot_file = d / "snapshot.json"
        if snapshot_file.exists():
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            summary_file = d / "summary.md"
            if summary_file.exists():
                snapshot["summary"] = summary_file.read_text(encoding="utf-8")
            return snapshot

    return None

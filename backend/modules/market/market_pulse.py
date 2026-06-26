"""
iWencai 市场体检 (Market Pulse)

数据流：iWencai 原始数据 → DeepSeek 加工为结构化 JSON + 文字报告 → 前端可视化

职责：
- 定义查询模板（涨跌分布、打板情绪、板块轮动、资金面、大金融）
- 执行 iWencai 扫描获取原始数据
- 调用 DeepSeek 将原始数据加工为标准化 JSON（给前端画图）+ 文字策略报告（给用户读）
- 结果落盘到 data/cn_stock/hierarchical/market_pulse/{date}/

不负责：
- 个股级别的查询
- 前端展示逻辑
"""

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

    # 3. DeepSeek 基于结构化数据 + 趋势对比 + AI早报 生成文字报告
    logger.info("Calling DeepSeek for strategy report...")
    report = ""
    try:
        trend_context = _build_trend_context(today)
        ai_report_context = _load_ai_report_summary(today)
        report = _call_deepseek([
            {"role": "system", "content": "You are a senior A-share market strategist. Write concise, data-driven commentary in Chinese."},
            {"role": "user", "content": REPORT_PROMPT_TEMPLATE.format(
                date=today,
                json_str=json.dumps(structured, ensure_ascii=False, indent=2),
                trend_context=trend_context,
                ai_report_context=ai_report_context,
            )},
        ])
        logger.info("DeepSeek strategy report completed.")
    except Exception as e:
        logger.error(f"DeepSeek report generation failed: {e}")
        report = f"（报告生成失败: {e}）"

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

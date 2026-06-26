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

REPORT_PROMPT_TEMPLATE = """你是某头部券商的首席市场策略分析师。请根据以下 {date} 的结构化市场数据，撰写一份【每日市场策略简报】。

# 结构化数据
```json
{json_str}
```

# 输出格式（Markdown，严格遵循）

## 一、市场全景速览
（2-3 句话概括今日核心特征，一句话定性判断）

## 二、情绪与结构研判
- **涨跌结构**: （从涨跌家数、涨停/跌停/炸板数据解读情绪信号）
- **资金信号**: （成交额、北向资金、主力流向的方向性判断）
- **打板情绪**: （首板/连板/炸板数据反映的超短线情绪状态）

## 三、板块轮动与主线
（从 top_sectors 和 top_concepts 中提炼今日主线逻辑，哪些板块领涨？题材轮动加速还是退潮？）

## 四、大金融板块追踪
（银行/证券/保险三大板块表现，联动效应，对大盘的方向性指引）

## 五、策略建议
- **仓位建议**: （加仓/减仓/持有 + 百分比区间）
- **关注方向**: （明日重点关注方向）
- **风险提示**: （需要警惕的信号）

---
*数据来源: iWencai 实时扫描 · AI 解读仅供参考，不构成投资建议*

# 约束
- 每个判断引用具体数值
- 800-1200 字
- 如果某维度数据为 null，跳过不要臆测
"""


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

    # 3. DeepSeek 基于结构化数据生成文字报告
    logger.info("Calling DeepSeek for strategy report...")
    report = ""
    try:
        report = _call_deepseek([
            {"role": "system", "content": "You are a senior A-share market strategist. Write concise, data-driven commentary in Chinese."},
            {"role": "user", "content": REPORT_PROMPT_TEMPLATE.format(
                date=today,
                json_str=json.dumps(structured, ensure_ascii=False, indent=2),
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

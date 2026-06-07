import json
import time
import requests
import pandas as pd
from loguru import logger
from fastapi import HTTPException
from api.core_config import DATA_DIR, config, resolver, iwencai_adapter

def generate_risk_audit(symbol: str) -> str:
    """Generates a YMOS Risk Audit report using OpenAI API."""
    # Load API key
    api_key = config.get("deepseek_api_key", "")
    if not api_key:
        raise ValueError("DeepSeek API key missing in secret.yaml")
    
    # 0. Ensure data is completely resolved and written to disk before auditing
    logger.info(f"Ensuring data layers are resolved for {symbol} before audit...")
    resolver.resolve_single_stock(symbol)
    
    # 0.5 Fetch Stock Name (For cross-referencing Topics)
    stock_name = ""
    quotes_file = DATA_DIR / "market" / f"{symbol}_tencent_quotes.json"
    if quotes_file.exists():
        with open(quotes_file, "r", encoding="utf-8") as f:
            quotes_data = json.load(f)
            for k, v in quotes_data.items():
                if k.upper() == symbol.upper():
                    stock_name = v.get("name", "")
                    break
    
    # 1. Fetch News
    news_file = DATA_DIR / "news" / f"{symbol}_eastmoney_news.json"
    news_data = []
    if news_file.exists():
        with open(news_file, "r", encoding="utf-8") as f:
            news_data = json.load(f)[:10] # Top 10 recent news
            
    # 2. Fetch Lockup
    lockup_file = DATA_DIR / "signals" / f"{symbol}_lockup_expiry.json"
    lockup_data = []
    if lockup_file.exists():
        with open(lockup_file, "r", encoding="utf-8") as f:
            lockup_data = json.load(f)
            
    # 3. Fetch THS Concepts
    ths_file = DATA_DIR / "signals" / "ths_hot_reasons.csv"
    ths_concepts = []
    if ths_file.exists():
        df = pd.read_csv(ths_file)
        raw_code = ''.join([c for c in symbol if c.isdigit()])
        df = df[df['code'].astype(str).str.contains(raw_code, na=False)]
        if not df.empty:
            ths_concepts = df.to_dict(orient="records")
    
    # Construct Prompt Context
    context_str = f"Stock Symbol: {symbol}\n\n"
    context_str += "=== Recent News ===\n"
    for n in news_data:
        time_val = n.get('date', n.get('time', ''))
        context_str += f"- [{time_val}] {n.get('title', '')}\n"
        
    context_str += "\n=== Lockup Expiry (解禁信息) ===\n"
    upcoming_lockups = lockup_data.get("upcoming", []) if isinstance(lockup_data, dict) else lockup_data
    for l in upcoming_lockups:
        if isinstance(l, dict):
            context_str += f"- Date: {l.get('date', '')}, Type: {l.get('type', '')}, Ratio: {l.get('ratio', '')}%\n"
        
    context_str += "\n=== THS Hot Concepts (同花顺热门逻辑) ===\n"
    for t in ths_concepts:
        context_str += f"- Concept: {t.get('concept', '')}, Reason: {t.get('reason', '')}\n"
        
    # 3.5 Fetch Manual Topic Logic
    topics_file = DATA_DIR / "signals/zizizaizai_topics.json"
    manual_logic = []
    if topics_file.exists() and stock_name:
        with open(topics_file, "r", encoding="utf-8") as f:
            topics_data = json.load(f)
            for t in topics_data:
                rows = t.get("rows", [])
                for r in rows:
                    if r.get("个股") == stock_name:
                        manual_logic.append({
                            "topic_name": t.get("name"),
                            "category": f"{r.get('一级大类', '')}-{r.get('二级小类', '')}",
                            "relevance": r.get("相关性", ""),
                            "source": r.get("信息源", "")
                        })
                        
    if manual_logic:
        context_str += "\n=== 核心题材归属与逻辑支撑 (Manual Topic Logic) ===\n"
        for m in manual_logic:
            context_str += f"- [主题]: {m['topic_name']}\n"
            context_str += f"  [产业链位置]: {m['category']}\n"
            context_str += f"  [核心逻辑与相关性]: {m['relevance']} (来源: {m['source']})\n"
        
    # 4. Fetch Real-time Deep Risk Data via Iwencai
    deep_risk_str = ""
    try:
        logger.info(f"Running real-time deep risk scan for {symbol}...")
        raw_code = ''.join([c for c in symbol if c.isdigit()])
        query_str = f"{raw_code} 质押率 商誉 违规 立案调查 业绩预亏 风险提示"
        realtime_data = iwencai_adapter.query2data(query_str, limit=1)
        if realtime_data and isinstance(realtime_data, list) and len(realtime_data) > 0:
            first_row = realtime_data[0]
            deep_risk_str += "\n=== 实时深度风控扫描结果 (Real-time iWencai Data) ===\n"
            for k, v in first_row.items():
                if isinstance(v, (str, int, float)) and len(str(v)) < 200:
                    deep_risk_str += f"- {k}: {v}\n"
    except Exception as e:
        logger.error(f"Error fetching real-time risk data for {symbol}: {e}")
        deep_risk_str += "\n[实时扫描数据获取失败]\n"
        
    # The User's YMOS Prompt
    ymos_prompt = f"""# Role: YMOS 首席风控官 & 逻辑校准官 (Chief Risk Auditor)

你是一个极度严苛、对任何瑕疵都零容忍的 A 股审计专家。你的唯一任务是针对我提供的标的进行深度“政治审查”与“逻辑穿透”。你不需要海选，不需要评级，你只需要告诉我：这只股票到底稳不稳。

# 核心任务一：🛑 【致命硬伤与历史污点排雷】 (Strict Risk Audit)
你必须翻阅该标的所有近期的公开信息及历史档案，识别以下致命风险。只要命中任何一项，必须显著标红警告：
## 1. 现实硬伤 (Current Red Flags)
- 【司法监管】: 正在进行的立案调查、监管函、失信被执行人记录。
- 【筹码风险】: 近期发布的减持预案、大额定向增发解禁（占总股本>5%）。
- 【财务黑洞】: 业绩预亏、商誉占比过高、被出具“非标”意见、大股东质押率 > 80%。
- 【人事动荡】: 董事长、财务总监或核心技术领军人物近期离职。
- 【监管压制】: 处于异动监管严重警告期。
## 2. 历史污点 (Historical Scandals - 核心考察)
- 【诚信基因】: 严查该股票在历史上是否有过：财务造假前科、信披违规、忽悠式重组、或者被媒体广泛报道过的“杀猪盘”标签。
- 【股性劣根】: 是否有长期“割韭菜”的行为记录，或者频繁更换主业的“蹭热点”惯犯特征。

# 核心任务二：🔍 【逻辑真伪性校验】 (Logic Consistency)
对比【题材逻辑描述】、【核心题材归属与逻辑支撑】与【全网一手新闻】：
- 【逻辑对账】: 核实新闻中提到的具体订单、产品报价涨幅、中标公告或调研纪要是否真实存在，并且与【核心题材归属与逻辑支撑】里的相关性描述是否高度吻合。
- 【打假/剔除】: 如果该股只是在互动易上通过含糊其辞的回复蹭热度，或者其实际业务根本不匹配核心逻辑支撑，标记为“虚假蹭热度”。如果行业基本面出现利空但题材仍在唱多，标记为“逻辑证伪”。

# 输出规范 (Output Format)
直接输出以下两部分，绝对不要输出任何标题，也不要输出股票代码和名字：
- **【风险扫描】**: (如果安全，只写“通过”；如果有雷，用极简的一句话点明致命点)
- **【逻辑验证】**: (实锤/存疑/蹭热度) (用一两句话简述原因)

# 约束条件
- 极度精简，不需要任何客套话，不需要“结论”或“建议”等废话。
- 严禁推荐代码 688 开头的科创板股票。
- 言简意赅，只说干货。没有雷就写“通过”。

以下是该股票的已知资料：
{context_str}
{deep_risk_str}
"""

    # Call OpenAI
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a professional A-share risk auditor. Answer strictly in Markdown formatting without thinking processes."},
            {"role": "user", "content": ymos_prompt}
        ],
        "temperature": 0.2
    }
    
    logger.info(f"Calling DeepSeek for {symbol} YMOS Audit...")
    max_retries = 3
    response = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=45)
            if response.status_code == 200:
                break
            elif response.status_code >= 500 and attempt < max_retries:
                logger.warning(f"DeepSeek API returned {response.status_code} on attempt {attempt}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                break
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"DeepSeek API connection error: {e}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                raise ValueError(f"DeepSeek API Connection Error: {e}")
    
    if not response or response.status_code != 200:
        err_msg = response.text if response else "Unknown Error"
        raise ValueError(f"DeepSeek API Error: {err_msg}")
        
    data = response.json()
    report = data["choices"][0]["message"]["content"]
    
    return report

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import akshare as ak
import pandas as pd
from loguru import logger
import yaml
from pydantic import BaseModel

CUR_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = CUR_DIR.parent.parent.parent
DATA_DIR = WORKSPACE_DIR / "data/cn_stock/hierarchical"

# Import our stock resolver and adapters
sys.path.append(str(CUR_DIR))
from stock_resolver import StockResolver
from adapters.research import IwencaiAdapter

app = FastAPI(title="Qlib CN Stock API")

# Add CORS so Vue dev server can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resolver = StockResolver()

# Setup Iwencai
config = {}
secret_path = CUR_DIR / "secret.yaml"
if secret_path.exists():
    with open(secret_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
iwencai_adapter = IwencaiAdapter(config)

class SearchRequest(BaseModel):
    query: str

@app.post("/api/iwencai/search")
def iwencai_search(req: SearchRequest):
    """NL search via iWencai"""
    try:
        df = iwencai_adapter.fetch_iwencai(req.query)
        if df.empty:
            return {"status": "success", "data": []}
        df = df.fillna("")
        records = df.to_dict(orient="records")
        return {"status": "success", "data": records}
    except Exception as e:
        logger.error(f"Error calling iWencai: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{symbol}/fetch")
def fetch_realtime_stock(symbol: str, layer: str = None):
    """Triggers real-time fetching for a single stock."""
    try:
        success = resolver.resolve_single_stock(symbol, layer=layer)
        if success:
            return {"status": "success", "message": f"Data for {symbol} is up to date."}
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch data")
    except Exception as e:
        logger.error(f"Error fetching stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/topics")
def get_topics():
    """Returns topics JSON and latest Klines JSON"""
    topic_file = DATA_DIR / "signals/zizizaizai_topics.json"
    kline_file = DATA_DIR / "signals/zizizaizai_klines.json"
    
    import json
    data = {"topics": [], "klines": {}}
    if topic_file.exists():
        with open(topic_file, "r", encoding="utf-8") as f:
            data["topics"] = json.load(f)
            
    if kline_file.exists():
        with open(kline_file, "r", encoding="utf-8") as f:
            data["klines"] = json.load(f)
            
    return data

@app.get("/api/data/{layer}/{filename}")
def get_data_file(layer: str, filename: str):
    """Serves a static data file (CSV or JSON) from the hierarchical data directory."""
    file_path = DATA_DIR / layer / filename
    
    if not file_path.exists():
        # Prevent 404 console spam in frontend by returning empty content natively
        if filename.endswith(".json"):
            return Response(content="[]", media_type="application/json")
        else:
            return Response(content="", media_type="text/csv")
        
    return FileResponse(path=file_path, filename=filename)

import requests
import re

@app.get("/api/resolve_symbol/{query}")
def resolve_symbol(query: str):
    query = query.strip()
    
    # If it already looks like SH600519 or SZ000001
    if len(query) >= 6 and any(query.upper().startswith(prefix) for prefix in ["SH", "SZ", "BJ"]):
        return {"symbol": query.upper()}
        
    # If it is purely a 6-digit number, prepend SH/SZ
    if query.isdigit() and len(query) == 6:
        if query.startswith("6"): return {"symbol": f"SH{query}"}
        if query.startswith("0") or query.startswith("3"): return {"symbol": f"SZ{query}"}
        if query.startswith("4") or query.startswith("8"): return {"symbol": f"BJ{query}"}
        
    # Use Tencent Smartbox API for Chinese name or pinyin autocomplete
    try:
        url = f"https://smartbox.gtimg.cn/s3/?q={query}&t=all"
        res = requests.get(url, timeout=5)
        text = res.text
        # format: v_hint="sz~002342~\u5de8\u529b\u7d22\u5177~jlsj~GP-A^sh~600000~..."
        match = re.search(r'v_hint="([^"]+)"', text)
        if match:
            results = match.group(1).split('^')
            for r in results:
                parts = r.split('~')
                if len(parts) >= 2:
                    market = parts[0].upper()
                    code = parts[1]
                    if market in ["SH", "SZ", "BJ"]:
                        return {"symbol": f"{market}{code}"}
    except Exception as e:
        logger.error(f"Tencent search failed: {e}")
        
    raise HTTPException(status_code=404, detail="Stock not found")


import subprocess
import threading

_refresh_lock = threading.Lock()
_refresh_status = {"running": False, "last_result": None, "last_time": None}


@app.post("/api/refresh")
def refresh_data():
    """
    Triggers a full refresh of market_sentiment.csv by running the collector's
    signals layer (Legulegu sentiment + Akshare pools + high/low stats).
    This is the same pipeline that runs in the daily cron.
    Non-blocking: returns immediately, runs in background thread.
    """
    if _refresh_status["running"]:
        return {"status": "busy", "message": "A refresh is already running. Please wait."}

    def _do_refresh():
        _refresh_status["running"] = True
        _refresh_status["last_result"] = None
        try:
            # Run update_all_data.py with --force to do a full refresh of sentiment, topics, and stock layers
            update_script = str(CUR_DIR / "update_all_data.py")
            cmd = [
                sys.executable, update_script,
                "--force",
            ]
            logger.info(f"[Refresh] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(CUR_DIR))

            if result.returncode == 0:
                _refresh_status["last_result"] = "success"
                logger.info("[Refresh] Full data update completed successfully.")
            else:
                _refresh_status["last_result"] = f"error: {result.stderr[-500:] if result.stderr else result.stdout[-500:]}"
                logger.error(f"[Refresh] Full data update failed: {result.stderr if result.stderr else result.stdout}")
        except Exception as e:
            _refresh_status["last_result"] = f"exception: {str(e)}"
            logger.error(f"[Refresh] Exception during refresh: {e}")
        finally:
            import datetime as dt
            _refresh_status["running"] = False
            _refresh_status["last_time"] = dt.datetime.now().isoformat()

    with _refresh_lock:
        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    return {"status": "started", "message": "Data refresh started in background. Check /api/refresh/status for progress."}


@app.get("/api/refresh/status")
def refresh_status():
    """Returns the current status of the last data refresh."""
    return {
        "running": _refresh_status["running"],
        "last_result": _refresh_status["last_result"],
        "last_time": _refresh_status["last_time"],
    }

@app.get("/api/data/reports")
def get_reports():
    """Returns the parsed AI morning reports JSON"""
    report_file = DATA_DIR / "signals/zizizaizai_reports.json"
    import json
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# Setup Qlib lazily
_qlib_initialized = False

@app.get("/api/backtest/results")
def get_backtest_results():
    """Returns the latest backtest metrics and curve."""
    global _qlib_initialized
    try:
        import qlib
        from qlib.workflow import R
        
        if not _qlib_initialized:
            provider_uri = str(WORKSPACE_DIR / "data/cn_stock/standard/qlib_data")
            qlib.init(provider_uri=provider_uri, region="cn")
            _qlib_initialized = True
            
        exp = R.get_exp(experiment_name="custom_workflow")
        recorder = exp.list_recorders()
        
        # iterate from newest to oldest
        report_normal = None
        port_analysis = None
        
        for rec_id, rec in recorder.items():
            try:
                report_normal = rec.load_object("portfolio_analysis/report_normal_1day.pkl")
                port_analysis = rec.load_object("portfolio_analysis/port_analysis_1day.pkl")
                break
            except Exception:
                continue
                
        if report_normal is None or port_analysis is None:
            raise HTTPException(status_code=404, detail="No backtest results found. Please run backtest first.")
            
        # Parse analysis
        # port_analysis has index like ('excess_return_with_cost', 'risk') and columns like ('mean', ...)
        # We will extract excess_return_with_cost annualized_return, information_ratio, max_drawdown
        def safe_float(val, default=0.0):
            if val is None or pd.isna(val):
                return default
            try:
                res = float(val)
                if pd.isna(res):
                    return default
                return res
            except ValueError:
                return default

        try:
            excess_cost = port_analysis.loc["excess_return_with_cost", "risk"]
            metrics = {
                "annualized_return": safe_float(excess_cost.get("annualized_return", 0)),
                "information_ratio": safe_float(excess_cost.get("information_ratio", 0)),
                "max_drawdown": safe_float(excess_cost.get("max_drawdown", 0))
            }
        except Exception:
            metrics = {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0}
            
        # Parse cumulative return curve
        curve_data = []
        if not report_normal.empty:
            cum_strategy = (1 + report_normal["return"] - report_normal["cost"]).cumprod() - 1
            cum_bench = (1 + report_normal["bench"]).cumprod() - 1
            
            # Load macro signals
            macro_file = DATA_DIR / "signals" / "market_sentiment.csv"
            macro_df = pd.DataFrame()
            if macro_file.exists():
                try:
                    macro_df = pd.read_csv(macro_file)
                    macro_df['date'] = pd.to_datetime(macro_df['date'])
                    macro_df.set_index('date', inplace=True)
                    macro_df = macro_df.ffill()
                except Exception as e:
                    logger.error(f"Error reading macro signals: {e}")
            
            for date, row in report_normal.iterrows():
                d_str = date.strftime("%Y-%m-%d")
                
                # Default sentiment
                sentiment = 50.0
                pe_median = 0.0
                uplimit_num = 0.0
                is_bull = 0.0
                
                if not macro_df.empty:
                    # use the exact date or the closest past date due to ffill
                    # In python pandas we can use get_loc with method='pad' or simply use loc since we ffilled but dates might not perfectly match
                    try:
                        # Try exact match first
                        if date in macro_df.index:
                            s_row = macro_df.loc[date]
                            if isinstance(s_row, pd.DataFrame):
                                s_row = s_row.iloc[0]
                            sentiment = float(s_row.get("sentiment_score", 50.0))
                            pe_median = float(s_row.get("pe_median", 0.0))
                            uplimit_num = float(s_row.get("uplimit_num", 0.0))
                            tiandi = s_row.get("tiandi_num")
                            
                            # Convert safely
                            u_val = float(uplimit_num) if uplimit_num is not None and not pd.isna(uplimit_num) else float('nan')
                            t_val = float(tiandi) if tiandi is not None and not pd.isna(tiandi) else float('nan')
                            
                            if pd.isna(u_val) or pd.isna(t_val):
                                # Fallback to sentiment_score >= 55.0 for 2021
                                is_bull = 1.0 if sentiment >= 55.0 else 0.0
                            else:
                                is_bull = 1.0 if (sentiment >= 55.0 and u_val >= 40 and t_val <= 2) else 0.0
                    except Exception:
                        pass

                curve_data.append({
                    "date": d_str,
                    "strategy": safe_float(cum_strategy.loc[date]),
                    "benchmark": safe_float(cum_bench.loc[date]),
                    "sentiment_score": safe_float(sentiment, 50.0),
                    "pe_median": safe_float(pe_median, 0.0),
                    "uplimit_num": safe_float(uplimit_num, 0.0),
                    "timing_signal": safe_float(is_bull, 0.0)
                })
                
        return {
            "status": "success",
            "data": {
                "metrics": metrics,
                "curve": curve_data
            }
        }
    except Exception as e:
        logger.error(f"Error fetching backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import requests

@app.post("/api/stock/audit/{symbol}")
def ymos_risk_audit(symbol: str):
    """Generates a YMOS Risk Audit report using OpenAI API."""
    try:
        # Load API key
        api_key = config.get("deepseek_api_key", "") # The key is stored here
        if not api_key:
            raise HTTPException(status_code=400, detail="DeepSeek API key missing in secret.yaml")
        
        # 1. Fetch News
        news_file = DATA_DIR / "news" / f"{symbol}_eastmoney_news.json"
        news_data = []
        if news_file.exists():
            import json
            with open(news_file, "r", encoding="utf-8") as f:
                news_data = json.load(f)[:10] # Top 10 recent news
                
        # 2. Fetch Lockup
        lockup_file = DATA_DIR / "signals" / f"{symbol}_lockup_expiry.json"
        lockup_data = []
        if lockup_file.exists():
            import json
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
对比【题材逻辑描述】与【全网一手新闻】：
- 【逻辑对账】: 核实新闻中提到的具体订单、产品报价涨幅、中标公告是否真实存在。
- 【打假/剔除】: 如果该股只是在互动易上通过含糊其辞的回复蹭热度，标记为“虚假蹭热度”。如果行业基本面出现利空但题材仍在唱多，标记为“逻辑证伪”。

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
        response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"DeepSeek API Error: {response.text}")
            
        data = response.json()
        report = data["choices"][0]["message"]["content"]
        
        return {"status": "success", "report": report}
        
    except Exception as e:
        logger.error(f"Error generating audit for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 28456
    uvicorn.run("api_server:app", host="0.0.0.0", port=28456, reload=True)

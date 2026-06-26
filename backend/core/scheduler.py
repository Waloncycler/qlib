import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.trading_calendar import is_trading_day

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def run_morning_routine():
    """
    Morning routine to be executed before or around market open.
    Fetches the latest AI Morning Reports to prepare today's signals.
    """
    if not is_trading_day():
        logger.info("Today is not a trading day. Skipping morning routine.")
        return

    logger.info("Executing morning routine: Fetching AI reports...")
    try:
        from modules.intelligence.zizizaizai.reports import fetch_reports
        fetch_reports(max_pages=5)  # Fetch recent pages to get today's report
        logger.info("Morning routine completed successfully.")
    except Exception as e:
        logger.error(f"Error in morning routine: {e}")

def run_post_market_routine():
    """
    Post-market routine to be executed after market close.
    Downloads the daily K-line data and runs the signal backtest for today's results.
    """
    if not is_trading_day():
        logger.info("Today is not a trading day. Skipping post-market routine.")
        return

    logger.info("Executing post-market routine: Downloading OHLCV data...")
    try:
        from modules.backtest.service import run_data_download_service, run_signal_backtest_service
        
        # 1. Download today's data
        download_result = run_data_download_service()
        logger.info(f"Data download completed: {download_result}")
        
        # 2. Run automated backtest to update the cache
        logger.info("Running post-market signal backtest to update results...")
        backtest_result = run_signal_backtest_service(enable_ml_filter=False)
        ml_backtest_result = run_signal_backtest_service(enable_ml_filter=True)
        
        logger.info("Post-market routine completed successfully.")
    except Exception as e:
        logger.error(f"Error in post-market routine: {e}")

def run_market_pulse_routine():
    """
    Market Pulse routine: 收盘后执行 iWencai 市场体检扫描。
    拉取市场整体维度的结构化数据，生成 DeepSeek 摘要。
    """
    if not is_trading_day():
        logger.info("Today is not a trading day. Skipping market pulse.")
        return

    logger.info("Executing Market Pulse scan...")
    try:
        from modules.market.market_pulse import run_market_pulse_scan
        run_market_pulse_scan()
        logger.info("Market Pulse scan completed successfully.")
    except Exception as e:
        logger.error(f"Error in market pulse routine: {e}")


def start_scheduler():
    """
    Initializes and starts the APScheduler.
    Registers the daily cron jobs.
    """
    # Register morning routine at 09:00 AM every day
    scheduler.add_job(
        run_morning_routine,
        CronTrigger(hour=9, minute=0),
        id="morning_routine",
        replace_existing=True
    )
    
    # Register post-market routine at 16:00 PM every day
    scheduler.add_job(
        run_post_market_routine,
        CronTrigger(hour=16, minute=0),
        id="post_market_routine",
        replace_existing=True
    )

    # Register market pulse scan at 15:10 PM every trading day
    scheduler.add_job(
        run_market_pulse_routine,
        CronTrigger(hour=15, minute=10),
        id="market_pulse_routine",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Automated Scheduler started: Morning @ 09:00, Market Pulse @ 15:10, Post-Market @ 16:00")

def stop_scheduler():
    """
    Shuts down the APScheduler safely.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Automated Scheduler stopped.")

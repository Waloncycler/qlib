import os
import pandas as pd
import logging
from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy

logger = logging.getLogger(__name__)

class TimingTopkDropoutStrategy(TopkDropoutStrategy):
    """
    A custom strategy that extends TopkDropoutStrategy to incorporate
    macro market timing signals. It adjusts the `risk_degree` (overall position sizing)
    dynamically based on the current day's market sentiment and valuation.
    """
    def __init__(self, timing_signal_path: str, **kwargs):
        super().__init__(**kwargs)
        
        self.timing_df = pd.DataFrame()
        
        abs_path = os.path.abspath(timing_signal_path)
        if os.path.exists(abs_path):
            try:
                df = pd.read_csv(abs_path)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                # Forward fill to ensure missing values take the last known good value
                df = df.ffill()
                self.timing_df = df
                logger.info(f"Loaded timing signals from {abs_path}. Shape: {df.shape}")
            except Exception as e:
                logger.error(f"Failed to load timing signals from {abs_path}: {e}")
        else:
            logger.warning(f"Timing signal file not found: {abs_path}. Strategy will fall back to base risk_degree.")

    def get_risk_degree(self, trade_step=None):
        base_risk_degree = super().get_risk_degree(trade_step)
        
        if self.timing_df.empty:
            return base_risk_degree

        trade_start_time, _ = self.trade_calendar.get_step_time(trade_step)
        today = pd.to_datetime(trade_start_time.strftime("%Y-%m-%d"))
        
        if today not in self.timing_df.index:
            # Default to short (0.0) if no data
            return 0.0
            
        sentiment_row = self.timing_df.loc[today]
        if isinstance(sentiment_row, pd.DataFrame):
            sentiment_row = sentiment_row.iloc[0]

        sentiment_score = float(sentiment_row.get("sentiment_score", 0.0))
        uplimit = sentiment_row.get("uplimit_num")
        tiandi = sentiment_row.get("tiandi_num")
        
        # Safely convert to float or NaN
        try:
            u_val = float(uplimit) if uplimit is not None and not pd.isna(uplimit) else float('nan')
        except (ValueError, TypeError):
            u_val = float('nan')
            
        try:
            t_val = float(tiandi) if tiandi is not None and not pd.isna(tiandi) else float('nan')
        except (ValueError, TypeError):
            t_val = float('nan')

        if pd.isna(u_val) or pd.isna(t_val):
            # Fallback for historical dates missing detail metrics
            is_bull = (sentiment_score >= 55.0)
        else:
            is_bull = (sentiment_score >= 55.0 and u_val >= 40 and t_val <= 2)
        
        if is_bull:
            risk = 1.0 * base_risk_degree
            logger.info(f"[{today.date()}] Market Healthy (Sentiment: {sentiment_score:.1f}, UpLimit: {u_val}, TianDi: {t_val}). Long (Risk={risk:.2f}).")
        else:
            # Otherwise we clear positions (0.0) to defend
            risk = 0.0
            logger.info(f"[{today.date()}] Market Weak/Risky (Sentiment: {sentiment_score:.1f}, UpLimit: {u_val}, TianDi: {t_val}). Short (Risk={risk:.2f}).")

        return risk

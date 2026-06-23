import os
import pandas as pd
import logging
from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy

logger = logging.getLogger(__name__)

class TimingTopkDropoutStrategy(TopkDropoutStrategy):
    """
    Intelligent Strategy combining LightGBM signals and Macro Sentiment.
    It adjusts risk_degree (position sizing) dynamically:
      - Normal/Bull: risk_degree = 1.0 (execute LightGBM TopK signals)
      - Bear/Risk: risk_degree = 0.0 (empty position)
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
            return 0.0
            
        sentiment_row = self.timing_df.loc[today]
        if isinstance(sentiment_row, pd.DataFrame):
            sentiment_row = sentiment_row.iloc[-1]

        sentiment_score = float(sentiment_row.get("sentiment_score", 0.0))
        uplimit = sentiment_row.get("uplimit_num", float('nan'))
        tiandi = sentiment_row.get("tiandi_num", float('nan'))
        
        try:
            u_val = float(uplimit)
            t_val = float(tiandi)
        except (ValueError, TypeError):
            u_val = float('nan')
            t_val = float('nan')

        # Logic for "Risk Control"
        if pd.isna(u_val) or pd.isna(t_val):
            is_bull = (sentiment_score >= 50.0)
        else:
            is_bull = (sentiment_score >= 50.0 and u_val >= 30 and t_val <= 3)
        
        if is_bull:
            risk = 1.0 * base_risk_degree
            # Only log occasionally or at debug level to prevent spam
        else:
            risk = 0.0
            
        return risk

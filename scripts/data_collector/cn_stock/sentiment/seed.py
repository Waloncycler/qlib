import pandas as pd
import numpy as np
import datetime
from pathlib import Path

def seed_data():
    save_dir = Path(__file__).resolve().parent / "../../../data/cn_stock/hierarchical/signals"
    save_dir.mkdir(parents=True, exist_ok=True)
    csv_path = save_dir / "market_sentiment.csv"

    print(f"Target file: {csv_path.resolve()}")

    # Generate dates for past 40 calendar days, filtered for weekday (mon-fri) to get ~30 trading days
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=40)
    
    current_date = start_date
    dates = []
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += datetime.timedelta(days=1)

    # Generate realistic data
    np.random.seed(42)  # For reproducible seeding
    rows = []
    
    # Total listed stocks is around 5350
    total_stocks = 5350
    
    for dt in dates:
        flat = np.random.randint(80, 200)
        susp = np.random.randint(10, 25)
        remaining = total_stocks - flat - susp
        
        # Up count ratio moves in cycles/waves
        day_index = len(rows)
        # Create a wave pattern for sentiment
        wave = np.sin(day_index / 4.0) * 0.35 + 0.5  # between 0.15 and 0.85
        noise = np.random.normal(0, 0.08)
        up_ratio = np.clip(wave + noise, 0.1, 0.9)
        
        up_count = int(remaining * up_ratio)
        down_count = remaining - up_count
        
        limit_up = int(up_count * np.random.uniform(0.015, 0.04))
        st_limit_up = np.random.randint(5, 25)
        real_limit_up = max(0, limit_up - st_limit_up)
        
        limit_down = int(down_count * np.random.uniform(0.01, 0.03))
        st_limit_down = np.random.randint(2, 15)
        real_limit_down = max(0, limit_down - st_limit_down)
        
        # Sentiment score (activity index)
        sentiment_score = round(float(up_ratio * 100 + np.random.uniform(-5, 5)), 2)
        sentiment_score = np.clip(sentiment_score, 10.0, 95.0)
        
        up_down_ratio = round(up_count / down_count, 3) if down_count > 0 else up_count
        
        rows.append({
            "date": dt,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat,
            "suspended_count": susp,
            "limit_up_count": limit_up,
            "real_limit_up_count": real_limit_up,
            "st_limit_up_count": st_limit_up,
            "limit_down_count": limit_down,
            "real_limit_down_count": real_limit_down,
            "st_limit_down_count": st_limit_down,
            "sentiment_score": sentiment_score,
            "up_down_ratio": up_down_ratio
        })
        
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    print(f"Successfully seeded {len(df)} rows of market sentiment history.")

if __name__ == "__main__":
    seed_data()

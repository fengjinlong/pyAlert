import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import os
import numpy as np

# ----------------------------
# 文件配置
# ----------------------------
CSV_FILE = "btc_ndx_daily.csv"
LOGIC_FILE = "btc_ndx_logic.txt"

# ----------------------------
# 指标逻辑说明（写一次即可）
# ----------------------------
logic_text = """
BTC–NDX 日度指标逻辑说明：

1. NDX → 判断 BTC 趋势方向（上/下）
   - 核心逻辑：NDX = 全球风险资产母趋势，BTC = 风险偏好放大器
   - 日收益率方向对比 NDX_return & BTC_return
2. BTC → 判断市场情绪强度（大涨/暴跌）
   - 核心逻辑：BTC 波动率大，反映风险偏好情绪
   - 波动率比 NDX 波动率
3. BTC vs NDX Spread → 判断谁带节奏
   - Spread = BTC_return - β * NDX_return
   - Spread 正负判断领先者
4. BTC–NDX 强弱差值指标
   - Strength Spread = Spread * (BTC_vol / NDX_vol)
   - 正数 → BTC 强于 NDX；负数 → NDX 强于 BTC
5. Lead–Lag 相关性（过去 N 天）
   - 对比 BTC_return(t) 与 NDX_return(t-k), k=0~N
   - 根据最大绝对相关性判断领先者和顺势/反向
   - 输出示例：
       BTC 强于 NDX, lag_1 天前 BTC 领先 NDX 反向/抗跌
       NDX 强于 BTC, lag_2 天前 NDX 领先 BTC 同向
"""
with open(LOGIC_FILE, "w", encoding="utf-8") as f:
    f.write(logic_text)
print(f"指标与逻辑说明已保存到 {LOGIC_FILE}")

# ----------------------------
# 1. 获取 BTC OHLC 数据
# ----------------------------
def get_btc_ohlc(days=7):
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
    params = {"vs_currency":"usd", "days":days}
    r = requests.get(url, params=params)
    data = r.json()
    if not data:
        raise ValueError("BTC OHLC 数据为空，请检查请求或限制")
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("date", inplace=True)
    return df[["open","high","low","close"]]

btc_ohlc = get_btc_ohlc(days=7)
btc_price = btc_ohlc["close"].iloc[-1]
btc_prev_price = btc_ohlc["close"].iloc[-2]
btc_vol = (btc_ohlc["high"].iloc[-1] - btc_ohlc["low"].iloc[-1]) / btc_price
btc_ret = btc_price / btc_prev_price - 1
btc_date = btc_ohlc.index[-1].date()

# ----------------------------
# 2. 获取 NDX 收盘价
# ----------------------------
def get_ndx_prices(n=7):
    url = "https://stooq.com/q/d/l/?s=^ndx&i=d"
    r = requests.get(url)
    df = pd.read_csv(StringIO(r.text), parse_dates=["Date"])
    df = df.sort_values("Date", ascending=True)
    df = df.tail(n)
    df = df.reset_index(drop=True)
    if df.empty:
        raise ValueError("NDX 数据为空，请检查请求")
    return df

ndx_df = get_ndx_prices(n=7)
ndx_price = ndx_df.iloc[-1]["Close"]
ndx_prev_price = ndx_df.iloc[-2]["Close"]
ndx_vol = abs(ndx_price - ndx_prev_price) / ndx_prev_price
ndx_ret = (ndx_price - ndx_prev_price) / ndx_prev_price
ndx_date = ndx_df.iloc[-1]["Date"].date()
date_note = "" if btc_date == ndx_date else f"NDX 最新交易日：{ndx_date}, BTC 日期：{btc_date}"

# ----------------------------
# 3. 四个核心指标
# ----------------------------
# 3.1 NDX → BTC 趋势方向
trend_direction = "上" if (btc_ret * ndx_ret) > 0 else "下"
trend_logic = (f"NDX 当日价格 {ndx_price:.2f}, 前一日 {ndx_prev_price:.2f}, "
               f"收益率 {ndx_ret:.2%}; BTC 当日价格 {btc_price:.2f}, 前一日 {btc_prev_price:.2f}, "
               f"收益率 {btc_ret:.2%} → 趋势方向：{trend_direction}")

# 3.2 BTC → 市场情绪强度
if btc_vol < 0.01:
    sentiment = "平稳"
elif btc_vol < 0.03:
    sentiment = "轻微波动"
else:
    sentiment = "大涨/大跌"
sentiment_logic = f"BTC 当日波动率 {btc_vol:.2%}, NDX 波动率 {ndx_vol:.2%} → 情绪强度：{sentiment}"

# 3.3 Spread → 领先者
beta = 1.0
spread = btc_ret - beta * ndx_ret
leader = "BTC" if spread > 0 else "NDX"
spread_logic = f"Spread={spread:.2%} → 领先者：{leader}"

# 3.4 BTC–NDX 强弱差值指标及解释
strength_indicator = spread * (btc_vol / ndx_vol)
def generate_strength_text(strength_indicator):
    if strength_indicator > 0.02:
        level = "明显强于 NDX → 风险偏好上升"
    elif strength_indicator < -0.02:
        level = "明显弱于 NDX → 风险偏好下降"
    else:
        level = "与 NDX 同步 → 风险偏好平稳"
    return f"{strength_indicator:.4f} → {level}"

strength_logic = generate_strength_text(strength_indicator)

# ----------------------------
# 4. Lead-Lag 相关性 + 自动逻辑
# ----------------------------
def compute_lead_lag_logic(btc_ohlc, ndx_df, max_lag=3, spread_val=spread):
    btc_ret_series = btc_ohlc["close"].pct_change().dropna().values
    ndx_ret_series = ndx_df["Close"].pct_change().dropna().values
    min_len = min(len(btc_ret_series), len(ndx_ret_series))
    btc_ret_series = btc_ret_series[-min_len:]
    ndx_ret_series = ndx_ret_series[-min_len:]
    lead_lag_corr = {}
    for lag in range(max_lag+1):
        if lag == 0:
            corr = np.corrcoef(btc_ret_series, ndx_ret_series)[0,1]
        else:
            corr = np.corrcoef(btc_ret_series[lag:], ndx_ret_series[:-lag])[0,1]
        lead_lag_corr[f"lag_{lag}"] = corr

    # 自动生成逻辑说明
    max_lag_key = max(lead_lag_corr, key=lambda k: abs(lead_lag_corr[k]))
    corr_value = lead_lag_corr[max_lag_key]

    # 强弱判断
    if spread_val > 0:
        strength = "BTC 强于 NDX"
    elif spread_val < 0:
        strength = "NDX 强于 BTC"
    else:
        strength = "BTC 与 NDX 同步"

    # 领先/滞后判断
    if corr_value > 0:
        leader_text = f"{max_lag_key} 天前 NDX 领先 BTC 同向"
    elif corr_value < 0:
        leader_text = f"{max_lag_key} 天前 BTC 领先 NDX 反向/抗跌"
    else:
        leader_text = "短期无明显领先"

    return lead_lag_corr, f"{strength}, {leader_text}"

lead_lag_corr, lead_lag_logic = compute_lead_lag_logic(btc_ohlc, ndx_df, max_lag=3, spread_val=spread)

# ----------------------------
# 5. 构建输出表格
# ----------------------------
output = pd.DataFrame({
    "日期": [btc_date],
    "BTC 最新价格": [btc_price],
    "BTC 前一日价格": [btc_prev_price],
    "NDX 最新价格": [ndx_price],
    "NDX 前一日价格": [ndx_prev_price],
    "趋势方向(NDX→BTC)": [trend_direction],
    "趋势逻辑": [trend_logic],
    "BTC 情绪强度": [sentiment],
    "情绪逻辑": [sentiment_logic],
    "领先者(Spread)": [leader],
    "领先逻辑": [spread_logic],
    "BTC–NDX 强弱差值指标": [strength_indicator],
    "强弱逻辑": [strength_logic],
    "Lead-Lag Correlation": [str(lead_lag_corr)],
    "Lead-Lag 逻辑": [lead_lag_logic],
    "日期提示": [date_note]
})

# ----------------------------
# 6. 保存 CSV
# ----------------------------
if os.path.exists(CSV_FILE):
    output.to_csv(CSV_FILE, mode='a', header=False, index=False)
else:
    output.to_csv(CSV_FILE, index=False)

print(f"每日数据已保存到 {CSV_FILE}")
print("Lead-Lag 逻辑说明:", lead_lag_logic)
print("BTC–NDX 强弱差值指标说明:", strength_logic)

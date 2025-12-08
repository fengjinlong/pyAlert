import ccxt
import requests
import pandas as pd
from io import StringIO
import os
import numpy as np
import time

# ----------------------------
# 0. 全局配置
# ----------------------------
CSV_FILE = "btc_ndx_daily_v3.csv"  # 升级文件名，避免列数冲突
LOGIC_FILE = "btc_ndx_logic_v3.txt"
ANALYSIS_DAYS = 90  # 获取过去 90 天数据
BETA_FACTOR = 1.1   # BTC 相对 NDX 的贝塔系数

# ----------------------------
# 1. 保存逻辑说明文档 (详细版 - 保持不变)
# ----------------------------
logic_text = """
==========================================================
BTC–NDX 宏观联动策略分析文档 (v3.0 详细版)
==========================================================

【核心理念】
本模型用于捕捉 Bitcoin (BTC) 与 Nasdaq 100 (NDX) 之间的宏观流动性传导关系。

----------------------------------------------------------
1. 趋势状态 (Trend Status)
----------------------------------------------------------
  [+] 共振上涨: 风险资产全线上涨，最强买入信号。
  [-] 共振下跌: 流动性收紧，最强卖出信号。
  [?] 背离: 一涨一跌，需关注是否为独立行情或流动性枯竭预警。

----------------------------------------------------------
2. 波动率情绪 (Volatility Sentiment)
----------------------------------------------------------
  算法：(High - Low) / Open
  - 极度平静 (<1.5%): 变盘前夕。
  - 正常波动 (1.5% - 4%): 健康换手。
  - 剧烈波动 (>4%): 情绪过热或恐慌。

----------------------------------------------------------
3. 强弱 Spread (Alpha)
----------------------------------------------------------
  算法：Spread = BTC_Return - (1.1 * NDX_Return)
  - 正值 (+): BTC 跑赢大盘 (Alpha)。
  - 负值 (-): BTC 跑输大盘。

----------------------------------------------------------
4. 强弱动能 (Strength Momentum)
----------------------------------------------------------
  算法：Spread * (BTC波动率 / NDX波动率)
  - 逻辑: 在高波动率下跑赢大盘，才是真正的强势。
  - 阈值: > 0.05 显著走强；< -0.05 显著走弱。

----------------------------------------------------------
5. 领先滞后 (Lead-Lag)
----------------------------------------------------------
  计算过去 90 天的相关性。
  - Lag 1: 若 NDX 昨日收盘与 BTC 今日走势相关性最高(>0.25)，则存在宏观指引。
"""
with open(LOGIC_FILE, "w", encoding="utf-8") as f:
    f.write(logic_text)

# ----------------------------
# 2. 数据获取函数
# ----------------------------
def get_btc_data(days=90):
    """CCXT 获取 Binance BTC/USDT 日线"""
    print(f"正在通过 CCXT 获取 BTC 数据 (最近 {days} 天)...")
    try:
        exchange = ccxt.binance({
             'apiKey': 'r8EKZm6yI99sjZBdHrNzo5NhUXRxcwW7ywF3va80k8n535iKMS1L3RGl1VrYTp1z',
            'secret': 'ChwSkKB1uPRzc6LdM0BSEnDLnTIl1ai5WHz129XBsRmhVAgmEBsJdphgdjSieBYT',
            'enableRateLimit': True, # 自动处理访问频率限制
            'proxies': { # 如果你需要翻墙，得配置代理，否则连不上
                'http': 'http://127.0.0.1:7890',
                'https': 'http://127.0.0.1:7890',
            }
        })
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1d', limit=days + 5)
        if not ohlcv: return pd.DataFrame()
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"Error fetching BTC via CCXT: {e}")
        return pd.DataFrame()

def get_ndx_data(days=90):
    """获取 NDX 数据 (Stooq源)"""
    print("正在获取 NDX 数据...")
    url = "https://stooq.com/q/d/l/?s=^ndx&i=d"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        df.rename(columns={"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.sort_values("date").reset_index(drop=True)
        return df.tail(days + 10) 
    except Exception as e:
        print(f"Error fetching NDX: {e}")
        return pd.DataFrame()

# ----------------------------
# 3. 核心处理逻辑
# ----------------------------
def run_analysis():
    # 3.1 获取数据
    btc_df = get_btc_data(ANALYSIS_DAYS)
    ndx_df = get_ndx_data(ANALYSIS_DAYS)

    if btc_df.empty or ndx_df.empty:
        print("数据获取失败，终止运行。")
        return

    # 3.2 数据预处理
    if 'timestamp' in btc_df.columns:
        btc_df['timestamp'] = pd.to_datetime(btc_df['timestamp'], unit='ms')
        btc_df = btc_df.set_index('timestamp')
        # 重采样确保唯一性
        btc_df = btc_df.resample('D').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna().reset_index()
        btc_df['date'] = btc_df['timestamp'].dt.normalize()
    
    ndx_df['date'] = pd.to_datetime(ndx_df['date']).dt.normalize()

    # 3.3 合并数据 (Inner Join)
    merged = pd.merge(btc_df, ndx_df, on='date', suffixes=('_btc', '_ndx'), how='inner')
    merged = merged.sort_values('date')
    
    if len(merged) < 5:
        print("有效重合数据太少，无法计算。")
        return

    # 3.4 计算基础指标
    merged['ret_btc'] = merged['close_btc'].pct_change()
    merged['ret_ndx'] = merged['close_ndx'].pct_change()
    merged['vol_btc'] = (merged['high_btc'] - merged['low_btc']) / merged['open_btc']
    merged['vol_ndx'] = (merged['high_ndx'] - merged['low_ndx']) / merged['open_ndx']

    # 3.5 提取 最新(curr) 和 前一日(prev) 数据
    curr = merged.iloc[-1]
    prev = merged.iloc[-2] # 倒数第二行
    
    # --- 指标计算逻辑 (全量保留) ---
    
    # A. 趋势
    if curr['ret_btc'] > 0 and curr['ret_ndx'] > 0: trend_status = "共振上涨"
    elif curr['ret_btc'] < 0 and curr['ret_ndx'] < 0: trend_status = "共振下跌"
    elif curr['ret_btc'] > 0 and curr['ret_ndx'] < 0: trend_status = "BTC 独立上涨 (背离)"
    else: trend_status = "BTC 独立下跌 (背离)"
    
    # B. 情绪
    if curr['vol_btc'] < 0.015: sentiment = "极度平静"
    elif curr['vol_btc'] < 0.04: sentiment = "正常波动"
    else: sentiment = "剧烈波动/高风险"
    
    # 保留情绪逻辑字段
    sentiment_logic = f"BTC日内振幅 {curr['vol_btc']:.2%} (vs NDX {curr['vol_ndx']:.2%})"

    # C. 强弱 Spread
    spread = curr['ret_btc'] - (BETA_FACTOR * curr['ret_ndx'])
    leader = "BTC" if spread > 0 else "NDX"
    
    # D. 强弱动能
    vol_ratio = curr['vol_btc'] / (curr['vol_ndx'] + 1e-5)
    strength_ind = spread * vol_ratio
    
    if strength_ind > 0.05: strength_desc = "BTC 显著走强"
    elif strength_ind < -0.05: strength_desc = "BTC 显著走弱"
    else: strength_desc = "强弱并不明显"
    
    # 保留强弱逻辑字段
    strength_logic = f"Spread: {spread:.2%}, 指标值: {strength_ind:.4f} ({strength_desc})"

    # E. Lead-Lag (保留原始数据)
    window_df = merged.tail(ANALYSIS_DAYS).copy()
    lead_lag_res = {}
    for lag in range(4): 
        series_ndx_shifted = window_df['ret_ndx'].shift(lag)
        series_btc = window_df['ret_btc']
        corr = series_btc.corr(series_ndx_shifted)
        lead_lag_res[f"lag_{lag}"] = corr

    best_lag_key = max(lead_lag_res, key=lambda k: abs(lead_lag_res[k]) if not np.isnan(lead_lag_res[k]) else 0)
    best_corr = lead_lag_res[best_lag_key]
    
    if abs(best_corr) < 0.25:
        lead_lag_logic = "近期无明显相关性 (独立行情)"
    else:
        direction = "正相关(跟随)" if best_corr > 0 else "负相关(跷跷板)"
        days_lag = int(best_lag_key.split('_')[1])
        lead_lag_logic = f"NDX 领先 {days_lag} 天 ({direction}, Corr={best_corr:.2f})"

    # ----------------------------
    # 4. 构建输出 (全量字段 + 新增前日价格)
    # ----------------------------
    output_row = {
        "日期": curr['date'].strftime('%Y-%m-%d'),
        # --- 新增部分 ---
        "前日BTC": round(prev['close_btc'], 2),
        "BTC价格": round(curr['close_btc'], 2),
        "前日NDX": round(prev['close_ndx'], 2),
        "NDX价格": round(curr['close_ndx'], 2),
        # ----------------
        "BTC涨跌幅": f"{curr['ret_btc']:.2%}",
        "NDX涨跌幅": f"{curr['ret_ndx']:.2%}",
        "趋势判断": trend_status,          # 保留
        "情绪状态": sentiment,             # 保留
        "情绪逻辑": sentiment_logic,       # 保留
        "Alpha领先者": leader,             # 保留
        "强弱指标值": round(strength_ind, 4), # 保留
        "强弱说明": strength_logic,        # 保留
        "Lead-Lag结论": lead_lag_logic,    # 保留
        "原始相关性数据": str({k: round(v, 2) for k, v in lead_lag_res.items() if not np.isnan(v)}) # 保留
    }
    
    df_out = pd.DataFrame([output_row])
    
    # 打印简报 (控制台只打核心信息，CSV存全量)
    print("\n" + "="*50)
    print(f"分析日期: {output_row['日期']}")
    print(f"BTC: {output_row['前日BTC']} -> {output_row['BTC价格']}")
    print(f"NDX: {output_row['前日NDX']} -> {output_row['NDX价格']}")
    print(f"结论: {trend_status} | {sentiment} | {strength_desc}")
    print(f"Spread: {spread:.2%}")
    print("="*50 + "\n")

    # 保存文件
    if os.path.exists(CSV_FILE):
        df_out.to_csv(CSV_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
    else:
        df_out.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
    
    print(f"全量数据(含逻辑说明)已保存至: {CSV_FILE}")
    print(f"详细策略文档已更新至: {LOGIC_FILE}")

if __name__ == "__main__":
    run_analysis()
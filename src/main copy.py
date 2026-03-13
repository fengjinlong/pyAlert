from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from datetime import datetime, timedelta
import math

# 忽略 pandas 警告
pd.options.mode.chained_assignment = None 

app = FastAPI()

# 配置跨域（允许 Vue3 前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 实际部署时改成你的 Vue 域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {"User-Agent": "feng58555@gmail.com"}

# ---------------------------------------------------------
# 这里粘贴你之前写好的全部底层函数：
# get_cik(), get_eps_history(), build_ttm_eps(), get_price(), calculate_pe()
# (为节省篇幅，代码略，直接复用你那版准确的 Python 代码即可)
# ---------------------------------------------------------

def calculate_pe(price_df, eps_df):
    pe_list = []
    for _, row in price_df.iterrows():
        date = row["Date"]
        price = row["Close"]
        
        # 寻找在该交易日及之前已经发布的最新财报
        eps_valid = eps_df[eps_df["date"] <= date]
        
        if len(eps_valid) == 0:
            pe_list.append(None)
            continue
            
        ttm_eps = eps_valid.iloc[-1]["ttm_eps"]
        
        if ttm_eps <= 0:
            pe_list.append(None)
        else:
            pe_list.append(price / ttm_eps)
            
    price_df["PE"] = pe_list
    return price_df.dropna()
def get_price(symbol, years):
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    
    # 根据传入的年数计算起始时间
    start_date = datetime.now() - timedelta(days=365 * years)
    df = df[df["Date"] >= start_date].copy()
    return df
def build_ttm_eps(df):
    df = df.sort_values("end_date")
    df["ttm_eps"] = df["eps"].rolling(4).sum()
    df = df.dropna(subset=["ttm_eps"])
    
    # 按照实际发布日对齐
    df = df.sort_values(["date", "end_date"]).reset_index(drop=True)
    return df
def get_eps_history(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    data = requests.get(url, headers=HEADERS).json()
    
    eps = data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
    df = pd.DataFrame(eps)
    
    df = df.dropna(subset=["start", "end", "filed"])
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["days"] = (df["end"] - df["start"]).dt.days
    
    # 【核心1】：先按 filed 排序，确保后续取 last 拿到的是最新的修正/拆股后数值
    df = df.sort_values("filed")
    
    # 【核心2】：提取每个财报期的【最初发布日】(锁定真实历史时间，拒绝穿越)
    first_filed = df.groupby(["end", "days"])["filed"].min().reset_index()
    first_filed.rename(columns={"filed": "original_filed"}, inplace=True)
    
    # 【核心3】：提取每个财报期的【最新 EPS】(获取拆股后的统一比例数值)
    latest_val = df.drop_duplicates(subset=["end", "days"], keep="last")
    
    # 【核心4】：合并清洗，让最新的数值回到真实的历史发布日
    df_clean = pd.merge(latest_val, first_filed, on=["end", "days"])
    df_clean["filed"] = df_clean["original_filed"]
    
    # --- 下面继续使用最稳妥的单季累加法则 ---
    
    # a. 单季数据池
    df_q = df_clean[(df_clean["days"] >= 80) & (df_clean["days"] <= 105)].copy()
    df_q = df_q.drop_duplicates(subset=["end"], keep="last")
    
    # b. 年度数据池
    df_a = df_clean[(df_clean["days"] >= 350) & (df_clean["days"] <= 380)].copy()
    df_a = df_a.drop_duplicates(subset=["end"], keep="last")
    
    # c. 推导缺失的 Q4
    q4_list = []
    for _, a_row in df_a.iterrows():
        fy_end = a_row['end']
        fy_start = fy_end - pd.Timedelta(days=360) 
        
        q_in_fy = df_q[(df_q['end'] > fy_start) & (df_q['end'] < fy_end)]
        
        if len(q_in_fy) == 3 and not (df_q['end'] == fy_end).any():
            q4_eps = a_row['val'] - q_in_fy['val'].sum()
            q4_list.append({
                "date": a_row["filed"], 
                "end_date": fy_end,
                "eps": q4_eps
            })
            
    # 格式化并输出
    df_q["date"] = df_q["filed"]
    df_q["end_date"] = df_q["end"]
    df_q["eps"] = df_q["val"]
    df_q = df_q[["date", "end_date", "eps"]]
    
    if q4_list:
        df_q4 = pd.DataFrame(q4_list)
        df_q = pd.concat([df_q, df_q4], ignore_index=True)
        
    return df_q

def get_cik(symbol):
    url = "https://www.sec.gov/files/company_tickers.json"
    data = requests.get(url, headers=HEADERS).json()
    for k in data:
        if data[k]["ticker"] == symbol:
            return str(data[k]["cik_str"]).zfill(10)
@app.get("/api/analyze")
def analyze_pe(symbol: str = "TSLA", years: int = 3):
    try:
        # 1. 运行你的核心逻辑
        cik = get_cik(symbol.upper())
        if not cik:
            raise ValueError("找不到该股票代码")
            
        eps = get_eps_history(cik)
        eps = build_ttm_eps(eps)
        price = get_price(symbol, years)
        result = calculate_pe(price, eps)
        
        if result.empty:
            raise ValueError("无法计算 PE，缺少有效数据")

        # 2. 提取关键指标
        current_pe = float(result["PE"].iloc[-1])
        percentile = float((result["PE"] < current_pe).mean() * 100)
        p20 = float(result["PE"].quantile(0.2))
        p80 = float(result["PE"].quantile(0.8))

        # 3. 格式化图表数据供前端使用
        # 必须将 Date 转换为字符串，并将 NaN/Infinity 处理掉以免 JSON 报错
        result["Date"] = result["Date"].dt.strftime('%Y-%m-%d')
        chart_data = result[["Date", "PE"]].to_dict(orient="records")

        # 返回干净的 JSON 给 Vue
        return {
            "symbol": symbol.upper(),
            "years": years,
            "current_pe": round(current_pe, 2),
            "percentile": round(percentile, 2),
            "p20": round(p20, 2),
            "p80": round(p80, 2),
            "chart_data": chart_data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 运行命令：uvicorn main:app --reload
# lsof -i :8000
# kill -9 12345
# pm2 start "uvicorn main:app --host 127.0.0.1 --port 8000"
# 用 0.0.0.0 重新启动
# pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name "py-api"
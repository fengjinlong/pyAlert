from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from datetime import datetime, timedelta
import math
import os
import akshare as ak  # 美股数据源
import baostock as bs  # A股数据源

# 忽略 pandas 警告
pd.options.mode.chained_assignment = None 

# 屏蔽代理（防止服务器如果有本地代理导致 baostock 连不上）
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

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

# ==========================================
# 美股数据获取逻辑 (复用你原有的代码)
# ==========================================
def calculate_pe(price_df, eps_df):
    pe_list = []
    for _, row in price_df.iterrows():
        date = row["Date"]
        price = row["Close"]
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
    df = ak.stock_us_hist(symbol=symbol, period="daily", start_date=(datetime.now() - timedelta(days=365 * years)).strftime('%Y%m%d'), end_date=datetime.now().strftime('%Y%m%d'), adjust="qfq")
    df["Date"] = pd.to_datetime(df["日期"])
    df = df.sort_values("Date")[["Date", "收盘", "开盘", "最高", "最低", "成交量"]]
    df.columns = ["Date", "Close", "Open", "High", "Low", "Volume"]
    return df

def build_ttm_eps(df):
    df = df.sort_values("end_date")
    df["ttm_eps"] = df["eps"].rolling(4).sum()
    df = df.dropna(subset=["ttm_eps"])
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
    df = df.sort_values("filed")
    
    first_filed = df.groupby(["end", "days"])["filed"].min().reset_index()
    first_filed.rename(columns={"filed": "original_filed"}, inplace=True)
    latest_val = df.drop_duplicates(subset=["end", "days"], keep="last")
    df_clean = pd.merge(latest_val, first_filed, on=["end", "days"])
    df_clean["filed"] = df_clean["original_filed"]
    
    df_q = df_clean[(df_clean["days"] >= 80) & (df_clean["days"] <= 105)].copy()
    df_q = df_q.drop_duplicates(subset=["end"], keep="last")
    df_a = df_clean[(df_clean["days"] >= 350) & (df_clean["days"] <= 380)].copy()
    df_a = df_a.drop_duplicates(subset=["end"], keep="last")
    
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

# ==========================================
# 路由 1: 美股分析接口
# ==========================================
@app.get("/api/analyze")
def analyze_pe(symbol: str = "TSLA", years: int = 3):
    try:
        cik = get_cik(symbol.upper())
        if not cik:
            raise ValueError("找不到该股票代码")
            
        eps = get_eps_history(cik)
        eps = build_ttm_eps(eps)
        price = get_price(symbol, years)
        result = calculate_pe(price, eps)
        
        if result.empty:
            raise ValueError("无法计算 PE，缺少有效数据")

        current_pe = float(result["PE"].iloc[-1])
        percentile = float((result["PE"] < current_pe).mean() * 100)
        p20 = float(result["PE"].quantile(0.2))
        p80 = float(result["PE"].quantile(0.8))

        result["Date"] = result["Date"].dt.strftime('%Y-%m-%d')
        chart_data = result[["Date", "PE"]].to_dict(orient="records")

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


# ==========================================
# A股数据获取逻辑 (新增)
# ==========================================
def fetch_ashare_data(symbol: str, years: int):
    """
    通过 BaoStock 获取 A股数据。
    每次请求独立 login 和 logout，保证 API 服务端稳定。
    """
    bs.login()
    try:
        # 获取股票名称
        rs_name = bs.query_stock_basic(code=symbol)
        stock_name = symbol
        if rs_name.error_code == '0' and rs_name.next():
            stock_name = rs_name.get_row_data()[1]

        # 计算日期
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365 * years)).strftime('%Y-%m-%d')

        # 获取历史数据
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,close,peTTM",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
            
        return stock_name, data_list
    finally:
        # 无论成功失败，确保退出连接
        bs.logout()

# ==========================================
# 路由 2: A股分析接口 (新增)
# ==========================================
@app.get("/api/analyze_cn")
def analyze_pe_cn(symbol: str = "sh.600519", years: int = 3):
    try:
        # 1. 获取数据
        stock_name, data_list = fetch_ashare_data(symbol, years)
        
        if not data_list:
            raise ValueError(f"未能获取到 {symbol} 的数据，请检查格式(需带前缀如 sh.或 sz.)")

        # 2. 数据预处理
        df = pd.DataFrame(data_list, columns=["date", "close", "peTTM"])
        df['date'] = pd.to_datetime(df['date'])
        df['peTTM'] = pd.to_numeric(df['peTTM'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        
        # 过滤掉 PE 为负（亏损）的数据
        df = df[df['peTTM'] > 0].dropna().sort_values('date').reset_index(drop=True)

        if df.empty:
            raise ValueError("有效PE数据为空（该股票可能处于亏损期）")

        # 3. 计算关键指标
        current_pe = float(df["peTTM"].iloc[-1])
        current_price = float(df["close"].iloc[-1])
        p20 = float(df["peTTM"].quantile(0.2))
        p80 = float(df["peTTM"].quantile(0.8))
        percentile = float((df["peTTM"] < current_pe).mean() * 100)

        # 寻找极值点索引
        max_idx = df['peTTM'].idxmax()
        min_idx = df['peTTM'].idxmin()

        # 4. 格式化图表数据供前端使用 (保持与美股字段名一致 Date, PE)
        df["Date"] = df["date"].dt.strftime('%Y-%m-%d')
        df["PE"] = df["peTTM"]
        # 将收盘价一并带上，前端如果需要可以展示
        chart_data = df[["Date", "PE", "close"]].to_dict(orient="records")

        # 返回增强版的 JSON 给 Vue
        return {
            "symbol": symbol,
            "stock_name": stock_name,
            "years": years,
            "current_price": round(current_price, 2),
            "current_pe": round(current_pe, 2),
            "percentile": round(percentile, 2),
            "p20": round(p20, 2),
            "p80": round(p80, 2),
            # 以下为 A股接口额外提供的详细数据，供前端按需渲染箭头或悬浮框
            "max_pe": round(float(df["PE"].iloc[max_idx]), 2),
            "max_date": df["Date"].iloc[max_idx],
            "min_pe": round(float(df["PE"].iloc[min_idx]), 2),
            "min_date": df["Date"].iloc[min_idx],
            "chart_data": chart_data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
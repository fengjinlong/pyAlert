import baostock as bs
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta

# ==========================================
# 全局配置区 (在这里修改参数)
# ==========================================
SYMBOL = "sh.600900"  # 格式：上海 sh.600000 | 深圳 sz.000001
YEARS = 3            # 想要查看的历史年数 (1, 3, 5, 10)

# ==========================================
# 环境与显示配置
# ==========================================
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'sans-serif'] 
plt.rcParams['axes.unicode_minus'] = False 

def get_stock_name(symbol):
    """获取股票中文名称"""
    rs = bs.query_stock_basic(code=symbol)
    if rs.error_code == '0' and rs.next():
        return rs.get_row_data()[1]
    return symbol

def main():
    # 1. 登录
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return

    print(f"正在分析: {SYMBOL}...")
    stock_name = get_stock_name(SYMBOL)
    
    # 2. 准备日期
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365 * YEARS)).strftime('%Y-%m-%d')
    
    # 3. 获取数据 (日期, 收盘价, PE)
    rs = bs.query_history_k_data_plus(
        SYMBOL,
        "date,close,peTTM",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3" 
    )
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()
    
    if not data_list:
        print("未获取到数据，请检查代码格式。")
        return

    # 4. 数据预处理
    df = pd.DataFrame(data_list, columns=rs.fields)
    df['date'] = pd.to_datetime(df['date'])
    df['peTTM'] = pd.to_numeric(df['peTTM'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    # 过滤亏损数据（PE<=0）并重置索引，确保 idxmax/idxmin 准确
    df = df[df['peTTM'] > 0].dropna().sort_values('date').reset_index(drop=True)

    if df.empty:
        print("有效数据为空，可能该股票在查询期内均处于亏损状态。")
        return

    # 5. 计算关键指标
    p20 = df["peTTM"].quantile(0.2)
    p80 = df["peTTM"].quantile(0.8)
    current_pe = df["peTTM"].iloc[-1]
    current_price = df["close"].iloc[-1]
    percentile = (df["peTTM"] < current_pe).mean() * 100

    # 寻找最大值和最小值及其对应的日期
    max_idx = df['peTTM'].idxmax()
    min_idx = df['peTTM'].idxmin()
    
    max_pe = df['peTTM'].iloc[max_idx]
    max_date = df['date'].iloc[max_idx]
    
    min_pe = df['peTTM'].iloc[min_idx]
    min_date = df['date'].iloc[min_idx]

    # 6. 绘图展示
    plt.figure(figsize=(12, 6.5))
    
    # 绘制 PE 走势
    plt.plot(df["date"], df["peTTM"], label="每日 PE (TTM)", color="#1f77b4", linewidth=1.5, alpha=0.8)
    
    # 画参考水平线
    plt.axhline(p20, linestyle="--", color="green", alpha=0.6, label=f"20% 分位线 ({p20:.2f})")
    plt.axhline(p80, linestyle="--", color="orange", alpha=0.6, label=f"80% 分位线 ({p80:.2f})")
    plt.axhline(current_pe, linestyle="-", color="red", linewidth=2, label=f"当前 PE ({current_pe:.2f})")
    
    # 填充 20-80 核心估值区间
    plt.fill_between(df["date"], p20, p80, color="gray", alpha=0.15)
    
    # ==========================================
    # 新增：标注最高点和最低点 (带箭头)
    # ==========================================
    # 标注最高点 (红色箭头向上指)
    plt.annotate(f'最高: {max_pe:.2f}\n({max_date.strftime("%Y-%m-%d")})', 
                 xy=(max_date, max_pe), 
                 xytext=(0, 20), textcoords='offset points', 
                 ha='center', va='bottom', 
                 color='red', fontsize=10, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='red', lw=1.2))
    
    # 标注最低点 (绿色箭头向下指)
    plt.annotate(f'最低: {min_pe:.2f}\n({min_date.strftime("%Y-%m-%d")})', 
                 xy=(min_date, min_pe), 
                 xytext=(0, -25), textcoords='offset points', 
                 ha='center', va='top', 
                 color='green', fontsize=10, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='green', lw=1.2))
    # ==========================================
    
    # 悬浮信息框 (保持在图表内部偏上位置)
    mid_date = df['date'].iloc[len(df)//2]  
    top_y = df['peTTM'].max() * 0.95 
    # 如果最高点刚好处在正中间附近，为了防止信息框遮挡标注，稍微下调信息框位置
    if abs((max_date - mid_date).days) < 30:
        top_y = df['peTTM'].max() * 0.85

    info_text = (f"股票: {stock_name} ({SYMBOL})  |  当前股价: {current_price:.2f}\n"
                 f"当前 PE(TTM): {current_pe:.2f}  |  历史百分位: {percentile:.2f}%")
    plt.text(mid_date, top_y, info_text, 
             fontsize=11, fontweight='bold', ha='center', va='top',
             bbox=dict(facecolor='white', alpha=0.85, edgecolor='gray', boxstyle='round,pad=0.6'))

    # 细节修饰
    plt.title(f"{stock_name} ({SYMBOL}) PE 估值分析 - 回溯 {YEARS} 年", fontsize=15, pad=40)
    plt.xlabel("交易日期")
    plt.ylabel("P/E Ratio (TTM)")
    plt.grid(True, axis='y', alpha=0.2, linestyle=':')
    
    # 图例居中并横向排列
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.08), ncol=4, frameon=True, fontsize=10)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
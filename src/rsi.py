import ccxt
import pandas as pd
import pandas_ta as ta
import requests

# --- 配置区 ---
API_KEY = '你的_API_KEY'
SECRET_KEY = '你的_SECRET_KEY'
SYMBOL = 'BTC/USDT'  # 交易对
TIMEFRAME = '4h'     # 时间周期：4小时

PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}
# --- Telegram 配置 ---
TELEGRAM_BOT_TOKEN = "8493056629:AAGpdSka1JpRbKiJj6KALJwYNQ2ZvIOIf20"  #  Bot Token
TELEGRAM_CHAT_ID = "7294056361"

def send_telegram_message(chat_id: str, text: str) -> None:
    """发送 Telegram 消息（简单封装）"""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        print("Telegram 未配置，跳过发送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": text})
        if resp.status_code != 200:
            print(f"TG 发送失败: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"TG 发送异常: {e}")
def get_rsi_with_key():
    # 1. 初始化币安交易所对象 (使用 API Key)
    exchange = ccxt.binance({
        'apiKey': 'RsMuIbOOvETXI1kmbX3GhnQiYZpIpZWbyVdcXOfPPDaWyMbdV8r5s2DBnTSYFruc',
        'secret': 'W0ulQV5jTvTZ4Oui7gTJXmk1V3uWoAsyQuS7xj7VcNPkNalY3emzpDFyvOJxgBtJ',
        'enableRateLimit': True,  # 启用速率限制保护，防止被封IP
        'proxies': PROXIES,
        # 'options': {'defaultType': 'spot'} # spot 是现货，future 是合约
    })

    try:
        # 2. 获取 K 线数据 (OHLCV)
        # 4小时级别建议获取 100 根以上以保证 RSI 精确度
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
        
        # 3. 数据处理
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['close'] = df['close'].astype(float)
        
        # 4. 计算 RSI (14周期)
        # pandas_ta 的 rsi 默认使用 Wilder 平滑法，与币安官网一致
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        
        # 5. 提取最新数据
        last_row = df.iloc[-1]
        current_rsi = last_row['RSI_14']
        last_time = pd.to_datetime(last_row['timestamp'], unit='ms', utc=True).tz_convert('Asia/Shanghai')
        
        print(f"[{last_time}] {SYMBOL} {TIMEFRAME} RSI: {current_rsi:.2f}")
        
        # 逻辑判断
        if current_rsi >= 70:
            print("🔴 当前处于超买区域 (RSI > 70)")
        elif current_rsi <= 30:
            print("🟢 当前处于超卖区域 (RSI < 30)")
        # 发送 Telegram 提醒：当 RSI 大于 60 或 小于 50 时触发
        try:
            if current_rsi > 60:
                msg = f"[{last_time}] {SYMBOL} {TIMEFRAME} RSI 高于 60: {current_rsi:.2f}"
                print("TG提醒 ->", msg)
                send_telegram_message(TELEGRAM_CHAT_ID, msg)
            elif current_rsi < 50:
                msg = f"[{last_time}] {SYMBOL} {TIMEFRAME} RSI 低于 50: {current_rsi:.2f}"
                print("TG提醒 ->", msg)
                send_telegram_message(TELEGRAM_CHAT_ID, msg)
        except Exception as _e:
            # 保护性捕获，避免影响主流程
            print(f"发送 TG 提醒时出错: {_e}")

        return current_rsi

    except Exception as e:
        print(f"连接失败或报错: {e}")

if __name__ == "__main__":
    get_rsi_with_key()
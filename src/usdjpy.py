import requests
import json
from datetime import datetime, timedelta
from collections import OrderedDict
import time
import schedule
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

API_KEY = "3TGAEOTYWOXYL22Y"

# 163 邮箱配置
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465  # SSL 端口
EMAIL_USER = "17363165056@163.com"  # 请替换为你的163邮箱地址
EMAIL_PASSWORD = "YFZb8YSQBPbwNYkj"  # 请替换为你的163邮箱授权码（不是登录密码）
# EMAIL_TO = "17363165056@163.com"  # 接收通知的邮箱地址（可以和自己一样）
EMAIL_TO = "feng58555@gmail.com"  # 接收通知的邮箱地址（可以和自己一样）

# ==========================================
# 邮件通知函数
# ==========================================
def send_email_notification(subject, message):
    """发送邮件通知到163邮箱"""
    if EMAIL_USER == "YOUR_EMAIL@163.com" or EMAIL_PASSWORD == "YOUR_AUTH_CODE":
        print(f"⚠️ 邮箱配置未设置，跳过发送邮件")
        print(f"邮件主题：{subject}")
        print(f"邮件内容：\n{message}")
        return False
    
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = Header(f"USD/JPY监控 <{EMAIL_USER}>", 'utf-8')
        msg['To'] = Header(EMAIL_TO, 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加邮件正文
        msg.attach(MIMEText(message, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())
        server.quit()
        
        print("✅ 邮件发送成功")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ 邮件发送失败：认证失败，请检查邮箱地址和授权码")
        return False
    except Exception as e:
        print(f"❌ 邮件发送异常：{e}")
        return False

# ==========================================
# 主要逻辑函数
# ==========================================
def analyze_usdjpy():
    """分析USD/JPY数据并返回最新涨跌幅"""
    print("=" * 80)
    print("【USD/JPY 单日大幅波动分析】")
    print("=" * 80)

    # 获取过去一年的数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    print(f"\n数据时间范围：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print("正在从Alpha Vantage获取USD/JPY历史数据...")

    try:
        # 使用Alpha Vantage FX_DAILY API获取历史数据
        url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=JPY&apikey={API_KEY}&outputsize=full"
        
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if "Error Message" in data or "Note" in data:
            print(f"❌ API错误：{data.get('Error Message', data.get('Note', '未知错误'))}")
            return None, None, None
        
        if "Time Series FX (Daily)" not in data:
            print("❌ 无法获取数据，请检查API响应")
            print(f"响应内容：{json.dumps(data, indent=2)}")
            return None, None, None
        
        time_series = data["Time Series FX (Daily)"]
        
        # 将数据转换为有序列表，按日期排序
        data_list = []
        for date_str, values in time_series.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            # 只保留过去一年的数据
            if date_obj >= start_date:
                close_price = float(values["4. close"])
                data_list.append({
                    "date": date_obj,
                    "date_str": date_str,
                    "usdjpy": close_price
                })
        
        # 按日期排序（从早到晚）
        data_list.sort(key=lambda x: x["date"])
        
        print(f"✅ 成功获取 {len(data_list)} 条数据")
        
        # 计算每日涨跌（以日元为单位）
        # 只计算真正的单日涨跌（相邻交易日之间只差1天）
        result_list = []
        for i in range(1, len(data_list)):
            prev_item = data_list[i-1]
            curr_item = data_list[i]
            
            # 计算日期差（天数）
            date_diff = (curr_item["date"] - prev_item["date"]).days
            
            # 只计算真正的单日涨跌（日期差为1天）
            if date_diff == 1:
                prev_price = prev_item["usdjpy"]
                curr_price = curr_item["usdjpy"]
                daily_change = curr_price - prev_price
                
                result_list.append({
                    "date": curr_item["date"],
                    "date_str": curr_item["date_str"],
                    "usdjpy": curr_price,
                    "daily_change": daily_change
                })
        
        print(f"\n有效交易日数据：{len(result_list)} 天")
        
        # ==========================================
        # 2. 筛选单日涨幅≥1.4日元的情况
        # ==========================================
        print("\n" + "=" * 80)
        print("【筛选结果】单日涨幅≥1.4日元（日元贬值=Carry加杠杆）")
        print("=" * 80)
        print("📊 含义：强烈利多（标普/BTC +4–8%）")
        print("-" * 80)
        
        # 筛选涨幅≥1.4日元的数据
        large_increases = [
            item for item in result_list 
            if item["daily_change"] >= 1.4
        ]
        
        if len(large_increases) > 0:
            print(f"\n✅ 找到 {len(large_increases)} 条单日涨幅≥1.4日元的记录：\n")
            print(f"{'日期':<12} {'USD/JPY':<12} {'单日涨跌(日元)':<18} {'分析':<30}")
            print("-" * 80)
            
            # 按涨幅从大到小排序
            large_increases_sorted = sorted(large_increases, key=lambda x: x["daily_change"], reverse=True)
            
            for item in large_increases_sorted:
                date_str = item["date_str"]
                rate = item["usdjpy"]
                change = item["daily_change"]
                
                print(f"{date_str:<12} {rate:>10.2f}    {change:>15.2f}    日元贬值=Carry加杠杆")
            
            # 统计信息
            changes = [item["daily_change"] for item in large_increases]
            avg_change = sum(changes) / len(changes)
            max_change = max(changes)
            min_change = min(changes)
            
            print("\n" + "-" * 80)
            print("📈 统计信息：")
            print(f"  平均涨幅：{avg_change:.2f} 日元")
            print(f"  最大涨幅：{max_change:.2f} 日元")
            print(f"  最小涨幅：{min_change:.2f} 日元")
            print(f"  发生频率：{len(large_increases)}/{len(result_list)} 天 ({len(large_increases)/len(result_list)*100:.2f}%)")
        else:
            print("\n⚠️  未找到单日涨幅≥1.4日元的记录")
        
        print("=" * 80)
        
        # ==========================================
        # 3. 筛选单日跌幅≥1.4日元的情况
        # ==========================================
        print("\n" + "=" * 80)
        print("【筛选结果】单日跌幅≥1.4日元（日元升值=即时平仓）")
        print("=" * 80)
        print("📊 含义：极大利空（标普/BTC -5–15%）")
        print("-" * 80)
        
        # 筛选跌幅≤-1.4日元的数据（注意：跌幅是负数）
        large_decreases = [
            item for item in result_list 
            if item["daily_change"] <= -1.4
        ]
        
        if len(large_decreases) > 0:
            print(f"\n✅ 找到 {len(large_decreases)} 条单日跌幅≥1.4日元的记录：\n")
            print(f"{'日期':<12} {'USD/JPY':<12} {'单日涨跌(日元)':<18} {'分析':<30}")
            print("-" * 80)
            
            # 按跌幅从大到小排序（绝对值从大到小）
            large_decreases_sorted = sorted(large_decreases, key=lambda x: x["daily_change"])
            
            for item in large_decreases_sorted:
                date_str = item["date_str"]
                rate = item["usdjpy"]
                change = item["daily_change"]
                
                print(f"{date_str:<12} {rate:>10.2f}    {change:>15.2f}    日元升值=即时平仓")
            
            # 统计信息
            changes = [item["daily_change"] for item in large_decreases]
            avg_change = sum(changes) / len(changes)
            max_change = max(changes)
            min_change = min(changes)
            
            print("\n" + "-" * 80)
            print("📉 统计信息：")
            print(f"  平均跌幅：{avg_change:.2f} 日元")
            print(f"  最大跌幅：{min_change:.2f} 日元")
            print(f"  最小跌幅：{max_change:.2f} 日元")
            print(f"  发生频率：{len(large_decreases)}/{len(result_list)} 天 ({len(large_decreases)/len(result_list)*100:.2f}%)")
        else:
            print("\n⚠️  未找到单日跌幅≥1.4日元的记录")
        
        print("=" * 80)
        
        # ==========================================
        # 4. 整体统计信息
        # ==========================================
        print("\n" + "=" * 80)
        print("【整体统计信息】")
        print("=" * 80)
        
        if len(result_list) > 0:
            changes = [item["daily_change"] for item in result_list]
            avg_change = sum(changes) / len(changes)
            max_change = max(changes)
            min_change = min(changes)
            
            # 找到最大涨幅和最大跌幅对应的日期
            max_increase_item = max(result_list, key=lambda x: x["daily_change"])
            max_decrease_item = min(result_list, key=lambda x: x["daily_change"])
            
            # 计算标准差
            variance = sum((x - avg_change) ** 2 for x in changes) / len(changes)
            std_dev = variance ** 0.5
            
            print(f"\n过去一年USD/JPY波动统计：")
            print(f"  平均单日波动：{avg_change:.2f} 日元")
            print(f"  最大单日涨幅：{max_change:.2f} 日元（{max_increase_item['date_str']}）")
            print(f"  最大单日跌幅：{min_change:.2f} 日元（{max_decrease_item['date_str']}）")
            print(f"  标准差：{std_dev:.2f} 日元")
            
            # 最新数据
            latest_item = result_list[-1]
            print(f"\n最新数据：")
            print(f"  日期：{latest_item['date_str']}")
            print(f"  USD/JPY：{latest_item['usdjpy']:.2f}")
            print(f"  最新单日涨跌：{latest_item['daily_change']:.2f} 日元")
        
        print("=" * 80)
        
        # 返回最新涨跌幅用于通知
        if len(result_list) > 0:
            latest_item = result_list[-1]
            return latest_item["daily_change"], latest_item["usdjpy"], latest_item["date_str"]
        else:
            return None, None, None
    
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        print("\n提示：")
        print("1. 请检查网络连接")
        print("2. Alpha Vantage API可能有调用频率限制")
        print("3. 请确保API密钥有效")
        return None, None, None

# ==========================================
# 定时执行函数
# ==========================================
def scheduled_check():
    """定时检查函数，每10分钟执行一次"""
    print(f"\n{'='*80}")
    print(f"🕐 定时检查执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # 执行分析
    daily_change, usdjpy, date_str = analyze_usdjpy()
    
    if daily_change is None:
        subject = "⚠️ USD/JPY 数据获取失败"
        message = f"""
        <html>
        <body>
            <h2>⚠️ USD/JPY 数据获取失败</h2>
            <p><strong>时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>请检查网络连接或API配置</p>
        </body>
        </html>
        """
        send_email_notification(subject, message)
        return
    
    # 判断是否超过阈值
    threshold = 1.4
    is_exceeded = abs(daily_change) >= threshold
    
    # 构建消息
    if is_exceeded:
        if daily_change >= threshold:
            status = "🚨⚠️🔴 涨幅超过阈值！⚠️🔴🚨"
            emoji = "📈"
            analysis = "⚠️🚨 日元贬值=Carry加杠杆，强烈利多（标普/BTC +4–8%）⚠️🚨"
            subject = f"🚨⚠️🔴 USD/JPY 涨幅超过阈值！({daily_change:+.2f} 日元) ⚠️🔴🚨"
        else:
            status = "🚨⚠️🔴 跌幅超过阈值！⚠️🔴🚨"
            emoji = "📉"
            analysis = "⚠️🚨 日元升值=即时平仓，极大利空（标普/BTC -5–15%）⚠️🚨"
            subject = f"🚨⚠️🔴 USD/JPY 跌幅超过阈值！({daily_change:+.2f} 日元) ⚠️🔴🚨"
    else:
        status = "✅ 波动正常"
        emoji = "📊"
        analysis = "涨跌幅未超过1.4日元阈值"
        subject = f"📊 USD/JPY 波动监控 ({daily_change:+.2f} 日元)"
    
    # 根据是否超过阈值设置不同的样式
    if is_exceeded:
        title_emoji = f"{emoji}🚨⚠️🔴"
        status_bg_color = "#ffe6e6"
        status_border_color = "#e74c3c"
        status_text_color = "#c0392b"
    else:
        title_emoji = emoji
        status_bg_color = "#f8f9fa"
        status_border_color = "#ddd"
        status_text_color = "#333"
    
    # 构建HTML格式的邮件内容
    message = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2c3e50;">{title_emoji} USD/JPY 波动监控</h2>
        <div style="background-color: {status_bg_color}; padding: 15px; border-radius: 5px; border-left: 4px solid {status_border_color}; margin: 20px 0;">
            <h3 style="margin-top: 0; color: {status_text_color};">{status}</h3>
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>📅 日期：</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{date_str}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>💱 USD/JPY：</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{usdjpy:.2f}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>📊 单日涨跌：</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {'#e74c3c' if daily_change < 0 else '#27ae60'}; font-weight: bold;">{daily_change:+.2f} 日元</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>🔔 阈值：</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">±1.4 日元</td>
            </tr>
        </table>
        <div style="background-color: {'#ffe6e6' if is_exceeded else '#e8f4f8'}; padding: 15px; border-left: 4px solid {'#e74c3c' if is_exceeded else '#3498db'}; margin: 20px 0;">
            <p style="margin: 0; {'font-weight: bold; color: #c0392b;' if is_exceeded else ''}"><strong>分析：</strong>{analysis}</p>
        </div>
        <p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
            ⏰ 检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """
    
    # 发送通知
    send_email_notification(subject, message)

# ==========================================
# 主程序入口
# ==========================================
if __name__ == "__main__":
    # 检查是否使用持续运行模式（通过命令行参数 --daemon 或 --loop）
    daemon_mode = "--daemon" in sys.argv or "--loop" in sys.argv
    
    if daemon_mode:
        # 持续运行模式：适合直接运行脚本，使用 schedule 库
        print("🚀 程序启动（持续运行模式），立即执行一次检查...")
        scheduled_check()
        
        # 设置定时任务：每10分钟执行一次
        schedule.every(10).minutes.do(scheduled_check)
        
        print(f"\n✅ 定时任务已设置：每10分钟执行一次")
        print(f"⏰ 下次执行时间：{datetime.now() + timedelta(minutes=10)}")
        print(f"按 Ctrl+C 停止程序\n")
        
        # 持续运行
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次是否有待执行的任务
        except KeyboardInterrupt:
            print("\n\n👋 程序已停止")
    else:
        # 单次执行模式：适合 crontab 定时任务
        # 这种方式更节省内存，因为执行完就退出
        scheduled_check()

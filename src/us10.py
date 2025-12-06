from fredapi import Fred
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime

# 1. 先去 https://fred.stlouisfed.org/api/register 免费注册拿key（30秒）
fred = Fred(api_key='562881509df6dc980ee2cd9a617d12e5')

# 163 邮箱配置
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465  # SSL 端口
EMAIL_USER = "17363165056@163.com"  # 请替换为你的163邮箱地址
EMAIL_PASSWORD = "YFZb8YSQBPbwNYkj"  # 请替换为你的163邮箱授权码（不是登录密码）
EMAIL_TO = "feng58555@gmail.com"  # 接收通知的邮箱地址（可以和自己一样）
# EMAIL_TO = "17363165056@163.com"  # 接收通知的邮箱地址（可以和自己一样）

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
        msg['From'] = Header(f"10年期国债收益率监控 <{EMAIL_USER}>", 'utf-8')
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

# DGS10 就是10年期常熟到期收益率
series = fred.get_series('DGS10')

# 获取过去365天的数据
end_date = pd.Timestamp.now().normalize()
start_date = end_date - pd.Timedelta(days=365)

# 筛选日期范围
mask = (series.index >= start_date) & (series.index <= end_date)
recent_data = series[mask].copy()

# 创建完整的日期范围（包括周末和节假日）
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

# 重新索引到完整日期范围，并使用前向填充（如果当天没有数据，使用前一天的数据）
full_series = recent_data.reindex(date_range).ffill()

# 如果第一个值仍然是NaN（说明起始日期之前没有数据），使用后向填充
if len(full_series) > 0 and pd.isna(full_series.iloc[0]):
    full_series = full_series.bfill()

# 计算每日波动（与前一天的差值）
daily_change = full_series.diff()

# 输出结果
# print("【FRED】10年期国债收益率 - 过去365天数据及每日波动：")
# print("=" * 70)
# print(f"{'日期':<12} {'收益率(%)':<12} {'波动(bp)':<12} {'波动(%)':<12}")
# print("-" * 70)

# 显示所有数据
for date in date_range:
    date_str = date.strftime('%Y-%m-%d')
    value = full_series[date]
    change = daily_change[date]
    
    # 如果是第一天，波动为NaN
    if pd.isna(change):
        change_str = "-"
        change_bp_str = "-"
    else:
        change_bp = change * 100  # 转换为基点(bp)
        change_str = f"{change:.4f}"
        change_bp_str = f"{change_bp:.2f}"
    
    # if value is not None and not pd.isna(value):
    #     print(f"{date_str:<12} {value:>10.4f}% {change_bp_str:>10}bp {change_str:>10}")

print("=" * 70)

# 统计信息
valid_data = full_series.dropna()
if len(valid_data) > 0:
    latest_date = valid_data.index[-1].strftime('%Y-%m-%d')
    latest_value = valid_data.iloc[-1]
    latest_change = daily_change.iloc[-1]
    
    print(f"\n最新数据日期：{latest_date}")
    print(f"最新收益率：{latest_value:.4f}%")
    if not pd.isna(latest_change):
        print(f"最新波动：{latest_change*100:.2f}bp ({latest_change:.4f}%)")
    
    # 统计波动情况
    valid_changes = daily_change.dropna()
    if len(valid_changes) > 0:
        print(f"\n波动统计（过去365天）：")
        print(f"  平均波动：{valid_changes.mean()*100:.2f}bp")
        print(f"  最大上涨：{valid_changes.max()*100:.2f}bp")
        print(f"  最大下跌：{valid_changes.min()*100:.2f}bp")
        print(f"  标准差：{valid_changes.std()*100:.2f}bp")
    
    # 创建包含所有信息的DataFrame以便筛选
    result_df = pd.DataFrame({
        '日期': date_range,
        '收益率(%)': full_series.values,
        '波动(bp)': daily_change.values * 100,
        '波动(%)': daily_change.values
    })
    
    # ========== 筛选单日涨幅≥9bp的数据 ==========
    print("\n" + "=" * 70)
    print("【筛选结果】单日涨幅≥9bp的数据：")
    print("=" * 70)
    
    # 筛选涨幅≥9bp的数据（排除NaN）
    large_increases = result_df[
        (result_df['波动(bp)'] >= 9.0) & 
        (result_df['波动(bp)'].notna())
    ].copy()
    
    if len(large_increases) > 0:
        print(f"\n找到 {len(large_increases)} 条单日涨幅≥9bp的记录：\n")
        print(f"{'日期':<12} {'收益率(%)':<15} {'波动(bp)':<15} {'波动(%)':<15}")
        print("-" * 70)
        
        for idx, row in large_increases.iterrows():
            date_str = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
            yield_val = row['收益率(%)']
            change_bp = row['波动(bp)']
            change_pct = row['波动(%)']
            
            print(f"{date_str:<12} {yield_val:>13.4f}% {change_bp:>13.2f}bp {change_pct:>13.4f}")
        
        # 进一步筛选≥10bp的数据
        very_large_increases = large_increases[large_increases['波动(bp)'] >= 10.0]
        # if len(very_large_increases) > 0:
        #     print("\n" + "-" * 70)
        #     print(f"其中单日涨幅≥10bp的记录有 {len(very_large_increases)} 条：\n")
        #     print(f"{'日期':<12} {'收益率(%)':<15} {'波动(bp)':<15} {'波动(%)':<15}")
        #     print("-" * 70)
            
        #     for idx, row in very_large_increases.iterrows():
        #         date_str = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
        #         yield_val = row['收益率(%)']
        #         change_bp = row['波动(bp)']
        #         change_pct = row['波动(%)']
                
        #         print(f"{date_str:<12} {yield_val:>13.4f}% {change_bp:>13.2f}bp {change_pct:>13.4f}")
    else:
        print("\n未找到单日涨幅≥9bp的数据。")
    
    print("=" * 70)
    
    # ========== 筛选单日跌幅≥9bp的数据 ==========
    print("\n" + "=" * 70)
    print("【筛选结果】单日跌幅≥9bp的数据：")
    print("=" * 70)
    
    # 筛选跌幅≤-9bp的数据（排除NaN）
    large_decreases = result_df[
        (result_df['波动(bp)'] <= -9.0) & 
        (result_df['波动(bp)'].notna())
    ].copy()
    
    if len(large_decreases) > 0:
        print(f"\n找到 {len(large_decreases)} 条单日跌幅≥9bp的记录：\n")
        print(f"{'日期':<12} {'收益率(%)':<15} {'波动(bp)':<15} {'波动(%)':<15}")
        print("-" * 70)
        
        for idx, row in large_decreases.iterrows():
            date_str = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
            yield_val = row['收益率(%)']
            change_bp = row['波动(bp)']
            change_pct = row['波动(%)']
            
            print(f"{date_str:<12} {yield_val:>13.4f}% {change_bp:>13.2f}bp {change_pct:>13.4f}")
        
        # 进一步筛选≤-10bp的数据
        very_large_decreases = large_decreases[large_decreases['波动(bp)'] <= -10.0]
        # if len(very_large_decreases) > 0:
        #     print("\n" + "-" * 70)
        #     print(f"其中单日跌幅≥10bp的记录有 {len(very_large_decreases)} 条：\n")
        #     print(f"{'日期':<12} {'收益率(%)':<15} {'波动(bp)':<15} {'波动(%)':<15}")
        #     print("-" * 70)
            
        #     for idx, row in very_large_decreases.iterrows():
        #         date_str = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
        #         yield_val = row['收益率(%)']
        #         change_bp = row['波动(bp)']
        #         change_pct = row['波动(%)']
                
        #         print(f"{date_str:<12} {yield_val:>13.4f}% {change_bp:>13.2f}bp {change_pct:>13.4f}")
    else:
        print("\n未找到单日跌幅≥9bp的数据。")
    
    print("=" * 70)
    
    # ========== 检查当天涨跌幅并发送邮件通知 ==========
    if not pd.isna(latest_change):
        latest_change_bp = latest_change * 100  # 转换为基点(bp)
        threshold_bp = 9.0  # 阈值：9bp
        
        # 判断是否超过阈值
        is_exceeded = abs(latest_change_bp) >= threshold_bp
        
        # 构建邮件主题和内容
        if latest_change_bp >= threshold_bp:
            # 涨幅超过阈值
            status = "🚨⚠️🔴 涨幅超过阈值！⚠️🔴🚨"
            emoji = "📈"
            subject = f"🚨⚠️🔴 10年期国债收益率涨幅超过阈值！({latest_change_bp:+.2f}bp) ⚠️🔴🚨"
            analysis = f"⚠️🚨 涨幅超过9bp阈值，↑ 10Y上行 = 强烈利空 ⚠️🚨"
        elif latest_change_bp <= -threshold_bp:
            # 跌幅超过阈值
            status = "🚨⚠️🔴 跌幅超过阈值！⚠️🔴🚨"
            emoji = "📉"
            subject = f"🚨⚠️🔴 10年期国债收益率跌幅超过阈值！({latest_change_bp:+.2f}bp) ⚠️🔴🚨"
            analysis = f"⚠️🚨 跌幅超过9bp阈值，↓ 10Y下行 = 强烈利多 ⚠️🚨"
        elif latest_change_bp > 0:
            # 上涨但未超过阈值
            status = "✅ 波动正常（上涨）"
            emoji = "📈"
            subject = f"📊 10年期国债收益率波动监控 ({latest_change_bp:+.2f}bp)"
            analysis = f"涨跌幅未超过9bp阈值，↑ 10Y上行 = 强烈利空"
        else:
            # 下跌但未超过阈值
            status = "✅ 波动正常（下跌）"
            emoji = "📉"
            subject = f"📊 10年期国债收益率波动监控 ({latest_change_bp:+.2f}bp)"
            analysis = f"涨跌幅未超过9bp阈值，↓ 10Y下行 = 强烈利多"
        
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
            <h2 style="color: #2c3e50;">{title_emoji} 10年期国债收益率波动监控</h2>
            <div style="background-color: {status_bg_color}; padding: 15px; border-radius: 5px; border-left: 4px solid {status_border_color}; margin: 20px 0;">
                <h3 style="margin-top: 0; color: {status_text_color};">{status}</h3>
            </div>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>📅 日期：</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{latest_date}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>📊 收益率：</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{latest_value:.4f}%</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>📈 单日波动：</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {'#e74c3c' if latest_change_bp < 0 else '#27ae60'}; font-weight: bold;">{latest_change_bp:+.2f}bp ({latest_change:.4f}%)</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>🔔 阈值：</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">±9bp</td>
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
        
        # 发送邮件通知
        print(f"\n{'=' * 70}")
        if is_exceeded:
            print(f"📧 检测到当天涨跌幅超过9bp阈值，正在发送邮件通知...")
        else:
            print(f"📧 正在发送当天波动情况邮件通知...")
        print(f"{'=' * 70}")
        send_email_notification(subject, message)


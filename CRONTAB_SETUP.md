# USD/JPY 监控 Crontab 配置说明

## 内存占用对比

### 方式1：持续运行（使用 schedule 库）
- **内存占用**：Python 进程常驻内存，约 20-50MB
- **优点**：程序内部管理定时，逻辑简单
- **缺点**：需要进程管理（systemd/supervisor），占用内存

### 方式2：Crontab 定时执行（推荐）
- **内存占用**：每次执行时启动进程（约 20-50MB），执行完立即释放
- **优点**：
  - ✅ 更节省内存（执行完就退出）
  - ✅ 系统级定时任务管理，更稳定
  - ✅ 如果程序崩溃，不影响下次执行
  - ✅ 符合 Unix/Linux 最佳实践
- **缺点**：需要配置 crontab

## Crontab 配置步骤

### 1. 编辑 crontab
```bash
crontab -e
```

### 2. 添加定时任务（每10分钟执行一次）
```bash
# USD/JPY 波动监控 - 每10分钟执行一次
*/10 * * * * cd /path/to/your/project && /usr/bin/python3 /root/py/usdjpy.py >> /tmp/usdjpy_monitor.log 2>&1
```

### 3. 配置说明
- `*/10 * * * *` - 每10分钟执行一次
- `cd /path/to/your/project` - 切换到项目目录（请替换为实际路径）
- `/usr/bin/python3` - Python3 路径（使用 `which python3` 查看实际路径）
- `src/hongguan/usdjpy.py` - 脚本路径
- `>> /tmp/usdjpy_monitor.log 2>&1` - 将输出和错误日志追加到文件

### 4. 查看 crontab 任务
```bash
crontab -l
```

### 5. 查看日志
```bash
tail -f /tmp/usdjpy_monitor.log
```

## 其他时间间隔示例

```bash
# 每5分钟执行一次
*/5 * * * * cd /path/to/your/project && /usr/bin/python3 src/hongguan/usdjpy.py >> /tmp/usdjpy_monitor.log 2>&1

# 每15分钟执行一次
*/15 * * * * cd /path/to/your/project && /usr/bin/python3 src/hongguan/usdjpy.py >> /tmp/usdjpy_monitor.log 2>&1

# 每小时执行一次
0 * * * * cd /path/to/your/project && /usr/bin/python3 src/hongguan/usdjpy.py >> /tmp/usdjpy_monitor.log 2>&1
```

## 使用 systemd 管理（可选，适合持续运行模式）

如果选择持续运行模式，可以使用 systemd 管理：

创建服务文件 `/etc/systemd/system/usdjpy-monitor.service`：

```ini
[Unit]
Description=USD/JPY Monitor Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/your/project
ExecStart=/usr/bin/python3 src/hongguan/usdjpy.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

然后启动服务：
```bash
sudo systemctl enable usdjpy-monitor
sudo systemctl start usdjpy-monitor
sudo systemctl status usdjpy-monitor
```

## 推荐方案

**推荐使用 Crontab 方式**，因为：
1. 更节省内存（执行完就退出）
2. 系统级管理，更稳定可靠
3. 不需要额外的进程管理工具
4. 符合 Unix/Linux 最佳实践


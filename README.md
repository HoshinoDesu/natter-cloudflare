# Natter CloudFlare Auto Updater

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![Based on Natter](https://img.shields.io/badge/based%20on-Natter-green.svg)](https://github.com/MikeWang000000/Natter)

自动运行 [Natter](https://github.com/MikeWang000000/Natter) 进行 NAT 穿透，并将穿透后的公网 IP 和端口自动更新到 CloudFlare 的 DNS 记录（A记录 + SRV记录）。

**适用场景**：家庭宽带、校园网等 NAT 环境下，需要对外提供服务（如 Minecraft 服务器、游戏服务器等）的场景。

---

## 📖 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [高级配置](#高级配置)
- [许可证](#许可证)

---

## 项目简介

本项目是基于 [Natter](https://github.com/MikeWang000000/Natter) 的自动化部署工具，解决了动态 IP 和动态端口的问题：

1. **Natter** 负责 NAT 穿透，获取公网 IP 和端口映射
2. **本脚本** 自动将映射信息更新到 CloudFlare DNS
3. 用户通过固定域名即可访问服务，无需关心 IP 和端口变化

## 功能特性

### 核心功能
- 🚀 **自动 NAT 穿透** - 基于 Natter，支持 Full Cone NAT
- 🔄 **自动 DNS 更新** - 实时更新 CloudFlare DNS 记录
- 📡 **双记录管理** - 同时维护 A 记录（IP）和 SRV 记录（端口）
- 🔍 **IP 变化监控** - 监听Natter地址端口变化输出 自动修改SRV记录
- ♻️ **进程守护** - Natter 异常退出时自动重启
- 📊 **详细日志** - 完整的运行日志和状态输出
- ⚙️ **灵活配置** - 基于 YAML 的配置文件

### DNS 记录结构
本脚本会自动创建和维护两条 DNS 记录：

```
A 记录:   natter-server.yourdomain.com     →  动态公网IP
SRV 记录: _service._protocol.yourdomain.com →  natter-server.yourdomain.com:动态端口
```

---

## 工作原理

### 1. 克隆项目

```bash
git clone https://github.com/HoshinoDesu/natter-cloudflare
cd natter-cloudflare
```

### 2. 安装依赖

```bash
pip install requests pyyaml
```

### 3. 获取 Natter

从 [Natter Releases](https://github.com/MikeWang000000/Natter/releases) 下载 `natter.py`，或克隆仓库：

```bash
git clone https://github.com/MikeWang000000/Natter.git
```

将 `natter.py` 放到本项目目录。

### 4. 配置脚本

复制配置示例文件：

```bash
# Windows
copy config.example.yaml config.yaml

# Linux/macOS
cp config.example.yaml config.yaml
```

参考注释编辑 `config.yaml`


### 5. 运行脚本

#### Windows
```bash
# 前台运行（推荐首次测试）
python natter_cloudflare.py

# 或使用启动脚本
start.bat

# 后台运行
start_background.bat
```

#### Linux/macOS
```bash
# 前台运行
python3 natter_cloudflare.py

# 后台运行
nohup python3 natter_cloudflare.py > natter.log 2>&1 &
```

---

### 详细说明

1. **NAT 穿透阶段**
   - Natter 通过 STUN 协议获取公网映射
   - 持续保持连接，维持端口映射
   - 实时监控输出，提取 IP 和端口

2. **DNS 更新阶段**
   - 创建/更新 A 记录指向公网 IP
   - 创建/更新 SRV 记录指向 A 记录
   - 验证更新结果

3. **监控维护阶段**
   - 每10分钟检查公网 IP 是否变化（使用国内IP查询服务）
   - IP 变化时自动重启 Natter
   - Natter 异常退出时自动重启

---

## 高级配置

### Natter 高级参数

```yaml
natter:
  port: 25565
  args:
    - "-v"                        # 详细模式
    - "-i"                         # 绑定网卡
    - "192.168.1.100"
    - "-s"                         # 自定义STUN服务器
    - "stun.example.com:3478"
```

### UDP 模式

```yaml
natter:
  port: 9987
  args: ["-u"]
```

## 开机自启动

### Windows

1. 按 `Win + R` 输入 `shell:startup`
2. 创建 `start_background.bat` 的快捷方式
3. 重启电脑测试

### Linux (systemd)

创建服务文件 `/etc/systemd/system/natter-cf.service`：

```ini
[Unit]
Description=Natter CloudFlare Auto Updater
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/natter-cloudflare
ExecStart=/usr/bin/python3 /path/to/natter-cloudflare/natter_cloudflare.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable natter-cf
sudo systemctl start natter-cf
```

---

## 项目结构

```
natter-cloudflare/
├── natter.py                  # Natter 主程序
├── natter_cloudflare.py       # 本项目主脚本
├── config.example.yaml        # 配置文件示例
├── config.yaml                # 你的配置文件（需创建）
├── start.bat                  # Windows 启动脚本
├── start_background.bat       # Windows 后台启动
├── .gitignore                 # Git 忽略文件
└── README.md                  # 本文档
```

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

## 许可证

本项目基于 [Natter](https://github.com/MikeWang000000/Natter) 开发，遵循 GNU General Public License v3.0。

## 相关链接

- **Natter 项目**: https://github.com/MikeWang000000/Natter
- **CloudFlare**: https://www.cloudflare.com/
- **CloudFlare API 文档**: https://developers.cloudflare.com/api/
- **SRV 记录说明**: https://en.wikipedia.org/wiki/SRV_record

---

## 致谢

- 感谢 [Natter](https://github.com/MikeWang000000/Natter) 项目提供的 NAT 穿透解决方案
- 感谢 CloudFlare 提供的免费 DNS 服务

---

**如果这个项目对你有帮助，请给个 ⭐ Star！**

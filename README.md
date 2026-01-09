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
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [工作原理](#工作原理)
- [使用示例](#使用示例)
- [高级配置](#高级配置)
- [故障排除](#故障排除)
- [许可证](#许可证)

---

## 项目简介

本项目是基于 [Natter](https://github.com/MikeWang000000/Natter) 的自动化部署工具，解决了动态 IP 和动态端口的问题：

1. **Natter** 负责 NAT 穿透，获取公网 IP 和端口映射
2. **本脚本** 自动将映射信息更新到 CloudFlare DNS
3. 用户通过固定域名即可访问服务，无需关心 IP 和端口变化

### 为什么选择本项目？

- ✅ **零成本** - 基于开源项目，使用 CloudFlare 免费服务
- ✅ **全自动** - 一次配置，永久运行
- ✅ **高可用** - 自动监控、自动重启、自动更新
- ✅ **易使用** - 简单配置即可部署

---

## 功能特性

### 核心功能
- 🚀 **自动 NAT 穿透** - 基于 Natter，支持 Full Cone NAT
- 🔄 **自动 DNS 更新** - 实时更新 CloudFlare DNS 记录
- 📡 **双记录管理** - 同时维护 A 记录（IP）和 SRV 记录（端口）
- 🔍 **IP 变化监控** - 每10分钟检查公网 IP，变化时自动重启
- ♻️ **进程守护** - Natter 异常退出时自动重启
- 📊 **详细日志** - 完整的运行日志和状态输出
- ⚙️ **灵活配置** - 基于 YAML 的配置文件

### DNS 记录结构
本脚本会自动创建和维护两条 DNS 记录：

```
A 记录:   natter-server.yourdomain.com     →  动态公网IP
SRV 记录: _service._protocol.yourdomain.com →  natter-server.yourdomain.com:动态端口
```

**为什么需要 A 记录？**
- CloudFlare SRV 记录的 target 字段必须是主机名，不能直接使用 IP
- A 记录指向动态 IP，SRV 记录指向 A 记录的主机名
- 这种设计符合 DNS 标准，也更灵活

---

## 系统要求

- **操作系统**: Windows / Linux / macOS
- **Python**: 3.6 或更高版本
- **依赖库**: requests, pyyaml
- **网络环境**: Full Cone NAT（Natter 要求）
- **域名**: 托管在 CloudFlare 的域名

---

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
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

### 4. 配置 CloudFlare

#### 4.1 创建 API Token

1. 访问：https://dash.cloudflare.com/profile/api-tokens
2. 点击 "Create Token"
3. 使用 "Edit zone DNS" 模板
4. 权限设置：
   - Zone - DNS - Edit
   - Zone - Zone - Read
5. 选择你要操作的域名
6. 创建并复制 Token

#### 4.2 获取 Zone ID

1. 登录 CloudFlare Dashboard
2. 选择你的域名
3. 在右侧概览页面找到 "Zone ID"
4. 复制 Zone ID

### 5. 配置脚本

复制配置示例文件：

```bash
# Windows
copy config.example.yaml config.yaml

# Linux/macOS
cp config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
cloudflare:
  api_token: "your_cloudflare_api_token_here"
  zone_id: "your_zone_id_here"
  domain: "example.com"

srv:
  name: "_minecraft._tcp.mc.example.com"
  priority: 0
  weight: 5

natter:
  script: "natter.py"
  port: 25565
  args: []

ip_check_interval: 600  # 10分钟
```

### 6. 运行脚本

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

## 工作原理

### 整体流程

```
┌─────────────┐
│  启动脚本   │
└──────┬──────┘
       │
       ├──────────────────────────────┐
       ▼                              ▼
┌──────────────┐              ┌──────────────┐
│ 启动 Natter  │              │  IP监控线程  │
│ (NAT 穿透)   │              │ (每10分钟)   │
└──────┬───────┘              └──────┬───────┘
       │                             │
       │ 获取公网IP:端口             │ 检查IP变化
       ▼                             ▼
┌──────────────┐              ┌──────────────┐
│ 182.99.x.x   │              │ IP改变？     │
│ :30911       │              │ Yes → 重启   │
└──────┬───────┘              └──────────────┘
       │
       ▼
┌──────────────────────────┐
│ 更新 CloudFlare DNS      │
├──────────────────────────┤
│ 1. A 记录                │
│    natter-server.xx.com  │
│    → 182.99.x.x          │
│                          │
│ 2. SRV 记录              │
│    _minecraft._tcp.xx.com│
│    → natter-server:30911 │
└──────────────────────────┘
       │
       ▼
┌──────────────┐
│ 用户访问     │
│ mc.xx.com    │
│ (自动解析)   │
└──────────────┘
```

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

## 使用示例

### Minecraft 服务器

配置文件：
```yaml
srv:
  name: "_minecraft._tcp.mc.example.com"
  priority: 0
  weight: 5

natter:
  port: 25565
```

玩家连接：
- 地址：`mc.example.com`
- 自动解析到正确的 IP 和端口
- 无需输入端口号

### 其他游戏/服务

#### TeamSpeak 服务器
```yaml
srv:
  name: "_teamspeak._udp.ts.example.com"

natter:
  port: 9987
  args: ["-u"]  # UDP 模式
```

#### 自定义 TCP 服务
```yaml
srv:
  name: "_myservice._tcp.service.example.com"

natter:
  port: 8080
```

---

## 高级配置

### 自定义IP检查间隔

```yaml
# 5分钟检查一次
ip_check_interval: 300

# 15分钟检查一次
ip_check_interval: 900
```

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

---

## 故障排除

### 1. SRV 记录创建失败

**错误**: `SRV target must be a hostname`

**原因**: CloudFlare SRV 记录要求 target 必须是主机名

**解决**: 本脚本已自动处理，会先创建 A 记录再创建 SRV 记录

### 2. API 权限不足

**错误**: `Authentication error`

**解决**: 确保 API Token 具有以下权限：
- Zone - DNS - Edit
- Zone - Zone - Read

### 3. 端口未更新

**现象**: CloudFlare 界面显示的端口不对

**解决方案**:
1. 强制刷新浏览器（Ctrl+F5）
2. 查看脚本日志中的"SRV 记录验证结果"
3. SRV 记录格式：`权重 端口 目标主机`

### 4. IP 获取错误

**现象**: 获取到代理服务器的 IP

**解决**: 本脚本已使用国内 IP 查询服务：
- myip.ipip.net
- api-ipv4.ip.sb
- ip.3322.net
- 等等

### 5. Natter 无法穿透

参考 [Natter 文档](https://github.com/MikeWang000000/Natter#readme) 检查：
- 网络环境是否为 Full Cone NAT
- 防火墙设置
- STUN 服务器可用性

---

## DNS 验证

### 验证 A 记录

Windows:
```powershell
nslookup natter-server.example.com
```

Linux/macOS:
```bash
dig A natter-server.example.com
```

### 验证 SRV 记录

Windows:
```powershell
Resolve-DnsName -Type SRV _minecraft._tcp.example.com
```

Linux/macOS:
```bash
dig SRV _minecraft._tcp.example.com
```

在线工具:
- https://mxtoolbox.com/SuperTool.aspx
- https://dnschecker.org/

---

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
├── natter.py                  # Natter 主程序（需自行下载）
├── natter_cloudflare.py       # 本项目主脚本
├── config.example.yaml        # 配置文件示例
├── config.yaml                # 你的配置文件（需创建）
├── start.bat                  # Windows 启动脚本
├── start_background.bat       # Windows 后台启动
├── .gitignore                 # Git 忽略文件
└── README.md                  # 本文档
```

---

## 安全建议

1. **保护 API Token**
   - 不要将 `config.yaml` 提交到 Git
   - 使用最小权限原则
   - 定期轮换 Token

2. **防火墙配置**
   - 只开放必要的端口
   - 考虑使用白名单

3. **日志管理**
   - 定期检查日志
   - 监控异常行为

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

## 许可证

本项目基于 [Natter](https://github.com/MikeWang000000/Natter) 开发，遵循 GNU General Public License v3.0。

```
Natter CloudFlare Auto Updater
Copyright (C) 2026

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

---

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

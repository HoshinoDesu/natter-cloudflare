#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natter CloudFlare SRV Updater
自动运行 Natter 并将穿透后的 IP 和端口更新到 CloudFlare SRV 记录
"""

import os
import re
import sys
import time
import json
import subprocess
import requests
import signal
import yaml
from threading import Thread

# ==================== 配置加载 ====================
def load_config():
    """从 config.yaml 加载配置"""
    config_file = "config.yaml"
    
    if not os.path.exists(config_file):
        # 如果没有config.yaml，返回默认配置
        return {
            'cloudflare': {
                'api_token': 'your_cloudflare_api_token_here',
                'zone_id': 'your_zone_id_here',
                'domain': 'example.com'
            },
            'srv': {
                'name': '_minecraft._tcp.example.com',
                'priority': 0,
                'weight': 5
            },
            'natter': {
                'script': 'natter.py',
                'port': 11451,
                'args': []
            },
            'ip_check_interval': 600
        }
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"[错误] 加载配置文件失败: {e}")
        sys.exit(1)

# 加载配置
config = load_config()

# 从配置中提取变量
CF_API_TOKEN = config['cloudflare']['api_token']
CF_ZONE_ID = config['cloudflare']['zone_id']
CF_DOMAIN = config['cloudflare']['domain']
SRV_NAME = config['srv']['name']
SRV_PRIORITY = config['srv']['priority']
SRV_WEIGHT = config['srv']['weight']
NATTER_SCRIPT = config['natter']['script']
NATTER_PORT = config['natter']['port']
NATTER_ARGS = config['natter'].get('args', [])
IP_CHECK_INTERVAL = config.get('ip_check_interval', 600)
# ===============================================


class NatterCloudFlare:
    def __init__(self):
        self.natter_process = None
        self.current_ip = None
        self.current_port = None
        self.srv_record_id = None
        self.a_record_id = None
        self.a_record_name = None  # A 记录的主机名
        self.running = True
        self.external_ip = None
        self.last_ip_check = 0
        self.ip_check_interval = IP_CHECK_INTERVAL  # 从配置读取
        self.need_restart = False
        
    def log(self, message, level="INFO"):
        """输出日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        sys.stdout.flush()

    def validate_srv_name(self):
        """验证 SRV 记录名称格式"""
        if not SRV_NAME.startswith('_'):
            self.log(f"警告: SRV 名称应以 '_' 开头: {SRV_NAME}", "WARN")
            return False
        
        parts = SRV_NAME.split('.')
        if len(parts) < 3:
            self.log(f"错误: SRV 名称格式不正确，应为 '_service._proto.domain'", "ERROR")
            self.log(f"示例: _minecraft._tcp.example.com", "ERROR")
            return False
        
        if not parts[1].startswith('_'):
            self.log(f"警告: 协议部分应以 '_' 开头，例如 _tcp 或 _udp", "WARN")
        
        self.log(f"SRV 记录格式验证通过: {SRV_NAME}")
        return True

    def get_external_ip(self):
        """获取当前外部IP地址"""
        # 使用中国内地的IP查询服务
        ip_services = [
            {
                "url": "https://myip.ipip.net/json",
                "parser": lambda r: r.json()["data"]["ip"]
            },
            {
                "url": "https://api-ipv4.ip.sb/ip",
                "parser": lambda r: r.text.strip()
            },
            {
                "url": "http://ip.3322.net",
                "parser": lambda r: r.text.strip()
            },
            {
                "url": "https://ddns.oray.com/checkip",
                "parser": lambda r: re.search(r'(\d+\.\d+\.\d+\.\d+)', r.text).group(1) if re.search(r'(\d+\.\d+\.\d+\.\d+)', r.text) else None
            },
            {
                "url": "http://pv.sohu.com/cityjson?ie=utf-8",
                "parser": lambda r: re.search(r'"cip":\s*"([^"]+)"', r.text).group(1) if re.search(r'"cip":\s*"([^"]+)"', r.text) else None
            },
            {
                "url": "https://www.taobao.com/help/getip.php",
                "parser": lambda r: re.search(r'"ip":\s*"([^"]+)"', r.text).group(1) if re.search(r'"ip":\s*"([^"]+)"', r.text) else None
            }
        ]
        
        for service in ip_services:
            try:
                response = requests.get(service["url"], timeout=5)
                if response.status_code == 200:
                    ip = service["parser"](response)
                    if ip:
                        # 验证是否为有效IP
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            return ip
            except Exception as e:
                self.log(f"从 {service['url']} 获取IP失败: {e}", "DEBUG")
                continue
        
        return None

    def check_ip_change(self):
        """检查外部IP是否变化"""
        current_time = time.time()
        
        # 检查是否到达检查间隔
        if current_time - self.last_ip_check < self.ip_check_interval:
            return False
        
        self.last_ip_check = current_time
        self.log("正在检查外部IP是否变化...")
        
        new_ip = self.get_external_ip()
        if not new_ip:
            self.log("无法获取外部IP，跳过检查", "WARN")
            # 计算下次检查时间
            next_check = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time + self.ip_check_interval))
            self.log(f"下次IP检查时间: {next_check}")
            return False
        
        if self.external_ip is None:
            # 首次检查
            self.external_ip = new_ip
            self.log(f"当前外部IP: {new_ip}")
            # 计算下次检查时间
            next_check = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time + self.ip_check_interval))
            self.log(f"下次IP检查时间: {next_check}")
            return False
        
        if new_ip != self.external_ip:
            self.log(f"检测到外部IP变化: {self.external_ip} -> {new_ip}", "WARN")
            self.external_ip = new_ip
            return True
        
        self.log(f"外部IP未变化: {new_ip}")
        # 计算下次检查时间
        next_check = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time + self.ip_check_interval))
        self.log(f"下次IP检查时间: {next_check}")
        return False

    def parse_natter_output(self, line):
        """解析 Natter 输出，提取公网 IP 和端口"""
        # 匹配格式：tcp://内网IP:端口 <--method--> tcp://内网IP:端口 <--Natter--> tcp://公网IP:端口
        pattern = r'<--Natter-->\s+tcp://(\d+\.\d+\.\d+\.\d+):(\d+)'
        match = re.search(pattern, line)
        if match:
            ip = match.group(1)
            port = int(match.group(2))
            return ip, port
        return None, None

    def start_natter(self):
        """启动 Natter 进程"""
        cmd = [sys.executable, NATTER_SCRIPT, "-p", str(NATTER_PORT)] + NATTER_ARGS
        self.log(f"启动 Natter: {' '.join(cmd)}")
        
        try:
            self.natter_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            return True
        except Exception as e:
            self.log(f"启动 Natter 失败: {e}", "ERROR")
            return False

    def monitor_natter_output(self):
        """监控 Natter 输出"""
        self.log("开始监控 Natter 输出...")
        
        for line in iter(self.natter_process.stdout.readline, ''):
            if not line:
                break
            
            # 检查是否需要重启
            if self.need_restart:
                self.log("检测到需要重启标志，准备重启Natter...", "WARN")
                break
            
            line = line.strip()
            if line:
                print(line)  # 输出原始日志
                sys.stdout.flush()
                
                # 尝试解析 IP 和端口
                ip, port = self.parse_natter_output(line)
                if ip and port:
                    if ip != self.current_ip or port != self.current_port:
                        self.log(f"检测到新的映射: {ip}:{port}")
                        self.current_ip = ip
                        self.current_port = port
                        self.update_cloudflare_srv()
                        
                        # 首次获取映射后，立即检查外部IP
                        if self.external_ip is None:
                            external_ip = self.get_external_ip()
                            if external_ip:
                                self.external_ip = external_ip
                                self.log(f"当前外部IP: {external_ip}")
                                # 显示首次IP检查时间
                                next_check = time.strftime("%Y-%m-%d %H:%M:%S", 
                                    time.localtime(time.time() + self.ip_check_interval))
                                self.log(f"下次IP检查时间: {next_check}")
        
        # 检查进程是否异常退出
        if self.natter_process:
            return_code = self.natter_process.poll()
            if return_code is not None and not self.need_restart:
                self.log(f"Natter 进程异常退出，返回码: {return_code}", "ERROR")

    def get_cloudflare_headers(self):
        """获取 CloudFlare API 请求头"""
        return {
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        }

    def find_srv_record(self):
        """查找现有的 SRV 记录"""
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        params = {
            "type": "SRV",
            "name": SRV_NAME
        }
        
        try:
            response = requests.get(url, headers=self.get_cloudflare_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["success"] and data["result"]:
                self.srv_record_id = data["result"][0]["id"]
                self.log(f"找到现有 SRV 记录: {self.srv_record_id}")
                return True
            else:
                self.log("未找到现有 SRV 记录，将创建新记录")
                return False
        except Exception as e:
            self.log(f"查询 SRV 记录失败: {e}", "ERROR")
            return False

    def generate_a_record_name(self):
        """生成 A 记录的主机名"""
        # 从 SRV 名称提取域名部分
        # 例如: _minecraft._tcp.mc.saltyfish.me -> mc.saltyfish.me
        parts = SRV_NAME.split('.', 2)
        if len(parts) >= 3:
            domain = parts[2]  # mc.saltyfish.me
            # 生成 A 记录名称: natter-server.mc.saltyfish.me
            self.a_record_name = f"natter-server.{domain}"
        else:
            # 降级方案
            self.a_record_name = f"natter-server.{CF_DOMAIN}"
        
        return self.a_record_name

    def find_a_record(self):
        """查找现有的 A 记录"""
        if not self.a_record_name:
            self.generate_a_record_name()
        
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        params = {
            "type": "A",
            "name": self.a_record_name
        }
        
        try:
            response = requests.get(url, headers=self.get_cloudflare_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["success"] and data["result"]:
                self.a_record_id = data["result"][0]["id"]
                self.log(f"找到现有 A 记录: {self.a_record_name} -> {self.a_record_id}")
                return True
            else:
                self.log(f"未找到现有 A 记录: {self.a_record_name}")
                return False
        except Exception as e:
            self.log(f"查询 A 记录失败: {e}", "ERROR")
            return False

    def create_or_update_a_record(self):
        """创建或更新 A 记录"""
        if not self.a_record_name:
            self.generate_a_record_name()
        
        if self.a_record_id:
            # 更新现有 A 记录
            return self.update_a_record()
        else:
            # 创建新 A 记录
            return self.create_a_record()

    def create_a_record(self):
        """创建 A 记录"""
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        
        a_data = {
            "type": "A",
            "name": self.a_record_name,
            "content": self.current_ip,
            "ttl": 120,
            "proxied": False
        }
        
        self.log(f"创建 A 记录: {self.a_record_name} -> {self.current_ip}")
        
        try:
            response = requests.post(url, headers=self.get_cloudflare_headers(), json=a_data)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                self.a_record_id = data["result"]["id"]
                self.log(f"创建 A 记录成功: {self.a_record_name} -> {self.current_ip}")
                return True
            else:
                errors = data.get('errors', [])
                error_msg = '; '.join([f"{e.get('code', 'N/A')}: {e.get('message', 'Unknown')}" for e in errors])
                self.log(f"创建 A 记录失败: {error_msg}", "ERROR")
                return False
        except Exception as e:
            self.log(f"创建 A 记录时出错: {e}", "ERROR")
            return False

    def update_a_record(self):
        """更新 A 记录"""
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{self.a_record_id}"
        
        a_data = {
            "type": "A",
            "name": self.a_record_name,
            "content": self.current_ip,
            "ttl": 120,
            "proxied": False
        }
        
        self.log(f"更新 A 记录: {self.a_record_name} -> {self.current_ip}")
        
        try:
            response = requests.put(url, headers=self.get_cloudflare_headers(), json=a_data)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                self.log(f"更新 A 记录成功: {self.a_record_name} -> {self.current_ip}")
                return True
            else:
                errors = data.get('errors', [])
                error_msg = '; '.join([f"{e.get('code', 'N/A')}: {e.get('message', 'Unknown')}" for e in errors])
                self.log(f"更新 A 记录失败: {error_msg}", "ERROR")
                return False
        except Exception as e:
            self.log(f"更新 A 记录时出错: {e}", "ERROR")
            return False

    def create_srv_record(self):
        """创建新的 SRV 记录"""
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        
        # 提取服务名和域名
        # 例如: _minecraft._tcp.example.com
        parts = SRV_NAME.split('.', 2)
        if len(parts) >= 3:
            service = parts[0]  # _minecraft
            proto = parts[1]    # _tcp
            domain = parts[2]   # example.com
        else:
            service = "_minecraft"
            proto = "_tcp"
            domain = CF_DOMAIN
        
        # 确保 A 记录存在
        if not self.a_record_name:
            self.generate_a_record_name()
        
        # SRV 记录的 data 格式 - target 必须是主机名
        srv_data = {
            "type": "SRV",
            "name": SRV_NAME,
            "data": {
                "service": service,
                "proto": proto,
                "name": domain,
                "priority": SRV_PRIORITY,
                "weight": SRV_WEIGHT,
                "port": self.current_port,
                "target": self.a_record_name  # 使用 A 记录的主机名
            },
            "ttl": 120  # 2分钟 TTL，便于快速更新
        }
        
        self.log(f"创建 SRV 记录请求数据: {json.dumps(srv_data, indent=2)}", "DEBUG")
        
        try:
            response = requests.post(url, headers=self.get_cloudflare_headers(), json=srv_data)
            
            # 记录响应以便调试
            try:
                response_data = response.json()
                self.log(f"API 响应: {json.dumps(response_data, indent=2)}", "DEBUG")
            except:
                self.log(f"API 响应 (原始): {response.text}", "DEBUG")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                self.srv_record_id = data["result"]["id"]
                self.log(f"创建 SRV 记录成功: {SRV_NAME} -> {self.a_record_name}:{self.current_port}")
                return True
            else:
                errors = data.get('errors', [])
                error_msg = '; '.join([f"{e.get('code', 'N/A')}: {e.get('message', 'Unknown')}" for e in errors])
                self.log(f"创建 SRV 记录失败: {error_msg}", "ERROR")
                return False
        except requests.exceptions.HTTPError as e:
            self.log(f"HTTP错误 {e.response.status_code}: {e.response.text}", "ERROR")
            return False
        except Exception as e:
            self.log(f"创建 SRV 记录时出错: {e}", "ERROR")
            return False

    def update_srv_record(self):
        """更新现有的 SRV 记录"""
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{self.srv_record_id}"
        
        # 提取服务名和域名
        parts = SRV_NAME.split('.', 2)
        if len(parts) >= 3:
            service = parts[0]  # _minecraft
            proto = parts[1]    # _tcp
            domain = parts[2]   # example.com
        else:
            service = "_minecraft"
            proto = "_tcp"
            domain = CF_DOMAIN
        
        # 确保 A 记录存在
        if not self.a_record_name:
            self.generate_a_record_name()
        
        # SRV 记录的 data 格式 - target 必须是主机名
        srv_data = {
            "type": "SRV",
            "name": SRV_NAME,
            "data": {
                "service": service,
                "proto": proto,
                "name": domain,
                "priority": SRV_PRIORITY,
                "weight": SRV_WEIGHT,
                "port": self.current_port,
                "target": self.a_record_name  # 使用 A 记录的主机名
            },
            "ttl": 120
        }
        
        self.log(f"更新 SRV 记录请求数据: {json.dumps(srv_data, indent=2)}", "DEBUG")
        
        try:
            response = requests.put(url, headers=self.get_cloudflare_headers(), json=srv_data)
            
            # 记录响应以便调试
            try:
                response_data = response.json()
                self.log(f"API 响应: {json.dumps(response_data, indent=2)}", "DEBUG")
            except:
                self.log(f"API 响应 (原始): {response.text}", "DEBUG")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                self.log(f"更新 SRV 记录成功: {SRV_NAME} -> {self.a_record_name}:{self.current_port}")
                # 显示CloudFlare返回的实际内容
                if "result" in data and "content" in data["result"]:
                    self.log(f"CloudFlare 记录内容: {data['result']['content']}")
                return True
            else:
                errors = data.get('errors', [])
                error_msg = '; '.join([f"{e.get('code', 'N/A')}: {e.get('message', 'Unknown')}" for e in errors])
                self.log(f"更新 SRV 记录失败: {error_msg}", "ERROR")
                return False
        except requests.exceptions.HTTPError as e:
            self.log(f"HTTP错误 {e.response.status_code}: {e.response.text}", "ERROR")
            return False
        except Exception as e:
            self.log(f"更新 SRV 记录时出错: {e}", "ERROR")
            return False

    def verify_srv_record(self):
        """验证 SRV 记录是否正确更新"""
        if not self.srv_record_id:
            return
        
        self.log("正在验证 SRV 记录...")
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{self.srv_record_id}"
        
        try:
            response = requests.get(url, headers=self.get_cloudflare_headers())
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") and "result" in data:
                result = data["result"]
                record_port = result.get("data", {}).get("port", "未知")
                record_target = result.get("data", {}).get("target", "未知")
                record_content = result.get("content", "未知")
                
                self.log("=" * 60)
                self.log("SRV 记录验证结果:")
                self.log(f"  记录名称: {result.get('name', '未知')}")
                self.log(f"  记录ID: {result.get('id', '未知')}")
                self.log(f"  目标主机: {record_target}")
                self.log(f"  端口: {record_port}")
                self.log(f"  完整内容: {record_content}")
                self.log(f"  期望端口: {self.current_port}")
                
                if str(record_port) == str(self.current_port):
                    self.log("✓ 端口匹配，更新成功！")
                else:
                    self.log(f"✗ 端口不匹配！CloudFlare显示: {record_port}, 应该是: {self.current_port}", "WARN")
                
                self.log("=" * 60)
                
        except Exception as e:
            self.log(f"验证 SRV 记录时出错: {e}", "ERROR")

    def update_cloudflare_srv(self):
        """更新 CloudFlare SRV 记录（自动判断创建或更新）"""
        if not self.current_ip or not self.current_port:
            self.log("IP 或端口未设置，跳过更新", "WARN")
            return
        
        self.log(f"准备更新 CloudFlare SRV 记录: {self.current_ip}:{self.current_port}")
        
        # 步骤1: 确保 A 记录存在
        if self.a_record_id is None:
            self.find_a_record()
        
        # 创建或更新 A 记录
        if not self.create_or_update_a_record():
            self.log("A 记录创建/更新失败，跳过 SRV 记录更新", "ERROR")
            return
        
        # 步骤2: 如果还没有查询过 SRV 记录 ID，先查询
        if self.srv_record_id is None:
            if self.find_srv_record():
                # 找到了，更新
                self.update_srv_record()
            else:
                # 没找到，创建
                self.create_srv_record()
        else:
            # 已经有记录 ID，直接更新
            self.update_srv_record()
        
        # 步骤3: 验证更新结果
        self.verify_srv_record()

    def stop_natter(self):
        """停止 Natter 进程"""
        if self.natter_process:
            self.log("正在停止 Natter...")
            self.natter_process.terminate()
            try:
                self.natter_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("强制终止 Natter 进程")
                self.natter_process.kill()
            self.natter_process = None
            self.current_ip = None
            self.current_port = None

    def restart_natter(self):
        """重启 Natter 进程"""
        self.log("=" * 50, "WARN")
        self.log("正在重启 Natter...", "WARN")
        self.log("=" * 50, "WARN")
        
        # 停止当前进程
        self.stop_natter()
        
        # 等待一下
        time.sleep(2)
        
        # 重新启动
        if self.start_natter():
            self.need_restart = False
            self.log("Natter 重启成功")
            return True
        else:
            self.log("Natter 重启失败", "ERROR")
            return False

    def signal_handler(self, signum, frame):
        """处理退出信号"""
        self.log("收到退出信号，正在清理...")
        self.running = False
        self.stop_natter()
        sys.exit(0)

    def ip_check_thread(self):
        """IP检查线程"""
        while self.running:
            try:
                time.sleep(30)  # 每30秒检查一次（实际检查间隔由 ip_check_interval 控制）
                
                if not self.running:
                    break
                
                # 检查IP是否变化
                if self.check_ip_change():
                    self.log("外部IP已变化，将在下次循环重启Natter", "WARN")
                    self.need_restart = True
                    # 主动终止当前进程以触发重启
                    if self.natter_process:
                        self.natter_process.terminate()
            except Exception as e:
                self.log(f"IP检查线程出错: {e}", "ERROR")

    def run(self):
        """主运行函数"""
        # 注册信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.log("=" * 50)
        self.log("Natter CloudFlare SRV Updater 启动")
        self.log("=" * 50)
        self.log(f"目标域名: {SRV_NAME}")
        self.log(f"映射端口: {NATTER_PORT}")
        self.log(f"IP检查间隔: {self.ip_check_interval}秒 ({self.ip_check_interval//60}分钟)")
        
        # 验证 SRV 名称格式
        if not self.validate_srv_name():
            self.log("配置验证失败，请检查 SRV 记录名称格式", "ERROR")
            return
        
        # 启动IP检查线程
        ip_thread = Thread(target=self.ip_check_thread, daemon=True)
        ip_thread.start()
        self.log("IP监控线程已启动")
        
        # 主循环 - 支持自动重启
        while self.running:
            # 启动 Natter
            if not self.start_natter():
                self.log("Natter 启动失败，60秒后重试...", "ERROR")
                time.sleep(60)
                continue
            
            # 监控输出
            try:
                self.monitor_natter_output()
            except Exception as e:
                self.log(f"监控过程出错: {e}", "ERROR")
            
            # 检查是否需要重启
            if self.need_restart and self.running:
                self.restart_natter()
                continue
            elif not self.running:
                break
            else:
                # 如果不是主动重启，说明进程异常退出
                self.log("Natter 异常退出，10秒后重启...", "WARN")
                time.sleep(10)
        
        self.stop_natter()


def main():
    # 检查配置
    if CF_API_TOKEN == "your_cloudflare_api_token_here":
        print("错误: 请先配置 CloudFlare API Token")
        print("请按照以下步骤操作:")
        print("  1. 复制 config.example.yaml 为 config.yaml")
        print("  2. 编辑 config.yaml 并填入你的配置:")
        print("     - cloudflare.api_token: CloudFlare API Token")
        print("     - cloudflare.zone_id: 域名的 Zone ID")
        print("     - cloudflare.domain: 你的主域名")
        print("     - srv.name: SRV 记录名称（如 _minecraft._tcp.example.com）")
        return 1
    
    # 检查 PyYAML 是否安装
    try:
        import yaml
    except ImportError:
        print("错误: 未安装 PyYAML 库")
        print("请运行: pip install pyyaml")
        return 1
    
    # 检查 natter.py 是否存在
    if not os.path.exists(NATTER_SCRIPT):
        print(f"错误: 找不到 {NATTER_SCRIPT}")
        print(f"当前目录: {os.getcwd()}")
        return 1
    
    # 运行
    updater = NatterCloudFlare()
    updater.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

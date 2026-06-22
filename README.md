# AimiliVPN 🌐

Bilingual: [中文](#中文) | [English](#english)

> 本 Fork 由 [birdke](https://github.com/birdke) 维护，基于 [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate)。当前版本新增网页上游代理配置、严格 API 响应校验和失败退避，适合官方节点 API 对部分 VPS 出口 IP 返回空 HTML 的场景。

---

<a name="中文"></a>
## 中文 (Chinese)

AimiliVPN 是一款基于官方 VPNGate 开放协议的高性能、零依赖 VPN 代理网关。它以纯 Python 标准库编写，内置美观响应式的管理网页，提供智能并发测速、多路由模式、出站代理网关、实时日志等强大功能。

---

### 🌟 VPS 优选推荐：跑 AimiliVPN 更稳更省心
[![BandwagonHost 顶级三网优化](https://img.shields.io/badge/BandwagonHost-%E9%A1%B6%E7%BA%A7%E4%B8%89%E7%BD%91%E4%BC%98%E5%8C%96-red?style=for-the-badge)](https://bandwagonhost.com/aff.php?aff=81790)
[![RackNerd 6000GB 流量](https://img.shields.io/badge/RackNerd-6000GB%2F%E6%9C%88%20%E5%A4%A7%E6%B5%81%E9%87%8F-blue?style=for-the-badge)](https://my.racknerd.com/aff.php?aff=18708)

| 推荐 | 适合谁 | 亮点 | 入口 |
| --- | --- | --- | --- |
| **BandwagonHost 搬瓦工** | 更看重国内访问质量、延迟和线路上限的用户 | **顶级三网优化线路**，适合对网络体验、跨境访问质量和长期稳定性要求更高的场景 | [立即查看](https://bandwagonhost.com/aff.php?aff=81790) |
| **RackNerd** | 想低成本部署、测试、长期挂机的用户 | **每月 6000GB 流量**，价格实惠、配置给得足，适合入门部署和性价比优先的 VPS 需求 | [立即查看](https://my.racknerd.com/aff.php?aff=18708) |

---

### 📢 上游项目交流与反馈
[![Telegram](https://img.shields.io/badge/TG交流群-arestemple-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://t.me/arestemple)
[![Forum](https://img.shields.io/badge/交流论坛-339936.xyz-orange?style=flat-square&logo=discourse&logoColor=white)](https://339936.xyz)
[![YouTube](https://img.shields.io/badge/视频教程-YouTube-red?style=flat-square&logo=youtube&logoColor=white)](https://www.youtube.com/watch?v=s-ATfXR8BpI)
[![Email](https://img.shields.io/badge/Bug反馈-yaohunse7@gmail.com-red?style=flat-square&logo=gmail&logoColor=white)](mailto:yaohunse7@gmail.com)

---

### 🚀 一键极速部署 (支持 Debian/Ubuntu/CentOS/Alpine 等 Linux 系统)

在您的 Linux VPS 上以 root 用户执行以下对应命令：

#### 🌟 正式稳定版本 (main 分支)
```bash
bash <(curl -Ls https://raw.githubusercontent.com/birdke/aimili-vpngate/main/install.sh)
```
> 💡 **小贴士**：部署完成后，终端会输出管理网页的专属链接（含随机安全后缀，如 `http://your_vps_ip:8787/u71e9IXp4TPx`）。在终端中输入 `ml` 命令可以随时调出交互式命令行管理菜单。

#### 🌐 在网页配置上游代理

如果 VPNGate 对当前 VPS 返回空 HTML，可以直接在管理后台配置一个可用的 HTTP 或 SOCKS5 上游代理：

1. 打开 **管理员 → 代理设置**，启用“上游代理”。
2. 选择 HTTP 或 SOCKS5，填写主机、端口及可选的用户名和密码。
3. 默认只代理节点列表 API；除非确实需要，否则不要勾选“同时用于 OpenVPN 的 TCP 节点连接”。
4. 保存后点击 **更新节点**。配置即时生效，无需重启服务。

代理凭据保存在 VPS 本机的 `vpngate_data/upstream_proxy.json`，文件权限为 `600`；管理接口只返回“是否已设置密码”，不会把密码发回浏览器。

<details>
<summary>高级备用：自建节点 API 中继</summary>

如果没有现成代理，也可以在另一台能访问 VPNGate 的 VPS 上运行 `vpngate_api_relay.py`。中继带令牌、源 IP 限制和缓存，仅提供公开节点 CSV，不转发 VPN 流量。部署模板位于 `deploy/` 目录。

</details>

---

### 💡 快速使用指南 (小白必看)

部署成功后，如何使用它进行科学上网？

#### 第一步：登录 Web 管理后台
打开浏览器，访问部署完成时提示的专属后台地址（含安全后缀），即可进入精美的暗黑玻璃拟物风管理界面。

#### 第二步：获取并连接节点
1. 首次进入后台，节点列表可能正在进行首次自动测速与拉取。
2. 点击 **“更新节点”** 按钮（或通过网页下方的网关/日志进行状态检查），程序会在后台通过多线程并发测速，自动筛选出延迟最低、可连接的 VPNGate 节点。
3. 选择您喜欢的出站路由模式：
   - **智能自动配置**（推荐）：如果当前连接的节点失效，系统会在数秒内自动漂移连接至其他备用健康节点，无需手动干预。
   - **固定国家地区**：只选择指定国家（如日本 JP、韩国 KR、美国 US）的最佳节点。
   - **固定 IP 节点**：始终锁定连接到这一个特定节点。

#### 第三步：使用本机代理 (核心步骤)
为了防止代理端口暴露至公网被恶意扫描和滥用，AimiliVPN 的双效代理服务（默认端口 **`7928`**，自适应支持 SOCKS5 和 HTTP 协议）**默认仅绑定在本地回环地址（`127.0.0.1`）**，只接收 VPS 本机上的流量，不对外机提供代理。

* **🐍 Python 脚本中使用代理**:
  ```python
  import requests
  proxies = {
      "http": "http://127.0.0.1:7928",
      "https": "http://127.0.0.1:7928",
  }
  response = requests.get("https://www.google.com", proxies=proxies)
  ```
* **🐚 Shell 终端环境中使用代理**:
  在命令行执行以下命令，可以让当前终端的后续命令（如 `curl`、`wget` 等）走代理出口：
  ```bash
  export http_proxy="http://127.0.0.1:7928"
  export https_proxy="http://127.0.0.1:7928"
  ```
* **⚙️ 本地其他服务配置**:
  将本机的其他代理工具、爬虫框架或服务的出战代理设置为 `127.0.0.1:7928`。

> 💡 **小贴士**：如果您确实需要对公网其他设备开放此代理端口，可以通过设置环境变量 `export LOCAL_PROXY_HOST="::"` 重新启动服务以允许公网接入。

---

### 🛠️ 核心功能与操作说明

* **合并操作面板**：将“更新节点”与“立即检测补齐”合并，一键触发多线程拉取与测速。
* **网关状态面板**：
  - **系统诊断**：检测网关心跳及后台各个子守护线程（网页服务、VPN连接管理、出站网关服务）是否正常运行。若有脚本未运行，会提示具体的异常原因。
  - **本地代理出口检测**：在网页端直接一键检测 VPS 后台对海外的实际连通状况，并回显真实的代理出站 IP 和所在地理位置。
* **日志追踪面板**：
  - **分类过滤**：可精准筛选查看特定功能的日志（如 VPN 连接日志、API 请求日志、系统异常等）。
  - **实时滚动与管理**：日志实时滚动加载，支持一键复制代码、一键导出 `.log` 日志文件到本地。

---

### ⚠️ 小白安装与运行常见问题 (FAQ)

#### 1. 提示 `Cannot allocate tun` 或 `Cannot open tun/tap dev`
* **原因**：VPS 宿主机未启用虚拟网卡（TUN/TAP 设备）。这种情况常见于 LXC 或 OpenVZ 架构的轻量 VPS。
* **解决办法**：请登录您的 VPS 服务商控制面板（如 SolusVM/Proxmox），找到 **Enable TUN/TAP** / **开启 TUN** 选项并启用，然后重启 VPS。如无此选项，请工单联系客服开启。

#### 2. 网页管理后台无法打开（链接超时或拒绝连接）
* **原因 1**：VPS 本身自带防火墙（如 UFW、firewalld 或 iptables）阻断了管理端口（默认 `8787`）或代理端口（默认 `7928`）。
* **解决办法 1**：请在终端放行对应端口：
  * **UFW (Ubuntu/Debian)**: `ufw allow 8787/tcp && ufw allow 7928/tcp`
  * **Firewalld (CentOS/RHEL)**: `firewall-cmd --zone=public --add-port=8787/tcp --permanent && firewall-cmd --zone=public --add-port=7928/tcp --permanent && firewall-cmd --reload`
* **原因 2**：云服务商的“安全组”或“网络访问控制列表 (ACL)”未放行端口。
* **解决办法 2**：**非常重要！** 登录云服务商控制台（如阿里云、腾讯云、AWS、Oracle Cloud等），找到您 VPS 实例的 **安全组规则 (Security Group)**，在入站规则中添加：
  - **协议类型**: `TCP`
  - **端口范围**: `8787` (管理网页) 和 `7928` (代理端口)
  - **授权对象/源IP**: `0.0.0.0/0` (允许所有人，或指定您自己的家庭公网 IP 提高安全性)

#### 3. 页面提示 `API Domain Blocked` 且备选节点显示为 0
* **原因**：您的 VPS DNS 解析异常、官方域名被阻断，或者 VPNGate 针对当前 VPS 出口 IP 返回了空 HTML 而不是节点 CSV。
* **解决办法**：
  * 如果请求成功但返回 HTML，请在 **管理员 → 代理设置** 中配置 HTTP/SOCKS5 上游代理，默认只用于节点 API。
  * 如果没有可用代理，可使用上文折叠说明中的自建 API 中继作为备用。
  * 如果日志显示域名无法解析，再检查 `/etc/resolv.conf` 或系统 DNS 配置。不要在 DNS 正常时盲目更换解析器。

#### 4. VPN 已成功连接，但客户端设置代理后无法上网 (无流量)
* **原因**：部分系统启用了严格的反向路径过滤（`rp_filter`），导致策略路由的入站/出站数据包被系统误判丢弃。
* **解决办法**：在终端输入 `ml` 命令打开交互菜单，工具会自动检测并提示您将 `rp_filter` 修复为宽松模式（值为 `2`）。

---

### 🎁 支持上游项目开发

以下捐赠地址来自上游项目 README，用于支持原项目后续开发与维护：

* **BNB (BSC / BEP20)**: `0xB6d78c42CEB0687A31B8cfEBE4b51b6eB8953C17`
* **TRX (TRC20)**: `TSdzCW6JvsrqcppodYjhSrku4mYmDJ9pxf`

感谢您的慷慨与支持！❤️

---

<a name="english"></a>
## English

> This fork is maintained by [birdke](https://github.com/birdke) and is based on [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate). It adds Web-managed upstream proxies, strict API response validation, and failure backoff for VPS addresses that receive an empty HTML response instead of the node CSV.

AimiliVPN is a high-performance, zero-dependency VPN proxy gateway built entirely using Python's standard library. It parses official VPNGate servers, benchmarks latency, and routes traffic through a built-in dual-protocol (HTTP/SOCKS5) proxy server.

### 🌟 Recommended VPS Deals
[![BandwagonHost Premium Optimized Routes](https://img.shields.io/badge/BandwagonHost-Premium%20Optimized%20Routes-red?style=for-the-badge)](https://bandwagonhost.com/aff.php?aff=81790)
[![RackNerd 6000GB Bandwidth](https://img.shields.io/badge/RackNerd-6000GB%2Fmonth%20Bandwidth-blue?style=for-the-badge)](https://my.racknerd.com/aff.php?aff=18708)

| Pick | Best for | Highlights | Link |
| --- | --- | --- | --- |
| **BandwagonHost** | Users who care most about China connectivity, latency, and route quality | **Premium China Telecom/Unicom/Mobile optimized routes**, ideal for demanding cross-border networking and long-term use | [View deals](https://bandwagonhost.com/aff.php?aff=81790) |
| **RackNerd** | Budget deployments, testing, and long-running lightweight services | **6000GB monthly bandwidth**, affordable pricing, and generous specs for value-focused VPS use | [View deals](https://my.racknerd.com/aff.php?aff=18708) |


### 📢 Upstream Community & Feedback
- **Telegram Group**: [arestemple](https://t.me/arestemple)
- **Discussion Forum**: [339936.xyz](https://339936.xyz)
- **Video Tutorial**: [YouTube Guide](https://www.youtube.com/watch?v=s-ATfXR8BpI)
- **Email Contact**: yaohunse7@gmail.com

---

### 🚀 One-Click Installation

Run the corresponding command on your Linux VPS as root:

#### 🌟 Stable Release (main branch)
```bash
bash <(curl -Ls https://raw.githubusercontent.com/birdke/aimili-vpngate/main/install.sh)
```

> 💡 **Quick Note**: Once installed, copy the printed URL from the terminal to access the Web UI. Type the `ml` command in the terminal to summon the interactive CLI management console.

#### 🌐 Configure an upstream proxy in the Web UI

If VPNGate returns an empty HTML page, open **Admin → Proxy Settings**, enable the upstream proxy, and enter an HTTP or SOCKS5 endpoint with optional credentials. It applies to node-list API requests immediately and does not require a restart. OpenVPN TCP connections remain direct unless the corresponding option is explicitly enabled.

Credentials are stored locally in `vpngate_data/upstream_proxy.json` with mode `600`; the API never returns the stored password. The restricted `vpngate_api_relay.py` remains available under `deploy/` as an advanced fallback when no proxy is available.

---

### 💡 Quick Start Guide

#### Step 1: Access the Web UI
Open your browser and navigate to the printed URL (e.g. `http://your_vps_ip:8787/u71e9IXp4TPx`).

#### Step 2: Select Node and Mode
1. Wait for the program to complete its first automatic node speed benchmarks.
2. Under "Admin", you can trigger node fetching. The backend concurrently tests official VPNGate nodes and ranks them by latency.
3. Switch routes mode (Smart Auto, Specific Region, or Specific Server Node) according to your needs.

#### Step 3: Use Localhost Proxy (Core Step)
To prevent unauthorized scanning and abuse of the proxy port on the public internet, the built-in HTTP/SOCKS5 proxy server (default port **`7928`**) **binds to localhost (`127.0.0.1`) by default**. It is designed to route traffic generated locally on the VPS, rather than acting as a public proxy server.

* **🐍 Proxy in Python**:
  ```python
  import requests
  proxies = {
      "http": "http://127.0.0.1:7928",
      "https": "http://127.0.0.1:7928",
  }
  response = requests.get("https://www.google.com", proxies=proxies)
  ```
* **🐚 Proxy in Shell terminal**:
  ```bash
  export http_proxy="http://127.0.0.1:7928"
  export https_proxy="http://127.0.0.1:7928"
  ```
* **⚙️ Other local services**:
  Configure your scrapers, frameworks, or utility tools on this VPS to send traffic via `127.0.0.1:7928`.

> 💡 **Quick Note**: If you really need to open this proxy port to the public internet, you can set the environment variable `export LOCAL_PROXY_HOST="::"` before running the manager.

---

### ⚠️ Common Troubleshooting (FAQ)

#### 1. Error: `Cannot allocate tun` or `Cannot open tun/tap dev`
* **Reason**: Virtual network adapter (TUN/TAP device) is disabled. This is common in OpenVZ/LXC VPS instances.
* **Solution**: Enable **TUN/TAP** in your VPS SolusVM/KiwiVM control panel, or submit a support ticket to your hosting provider.

#### 2. Cannot open the Web UI in the browser
* **Reason 1**: The built-in firewall (UFW or firewalld) is blocking ports `8787` (Web UI) and `7928` (Proxy).
* **Solution 1**: Allow the ports in your OS firewall:
  * **UFW**: `ufw allow 8787/tcp && ufw allow 7928/tcp`
  * **Firewalld**: `firewall-cmd --add-port=8787/tcp --permanent && firewall-cmd --add-port=7928/tcp --permanent && firewall-cmd --reload`
* **Reason 2**: Service provider security group blocking ports.
* **Solution 2**: **Crucial!** Log in to your cloud provider console (AWS, Aliyun, Oracle Cloud, etc.), locate the **Security Group** for your instance, and add an inbound TCP rule to allow ports `8787` and `7928` from `0.0.0.0/0`.

#### 3. "API Domain Blocked" / Candidate nodes pool is empty (0 nodes)
* **Reason**: DNS may be broken, the official domain may be blocked, or VPNGate may return an empty HTML page instead of CSV to the VPS egress address.
* **Solution**: If HTTP succeeds but returns HTML, configure an HTTP/SOCKS5 upstream proxy under **Admin → Proxy Settings**. If no proxy is available, use the restricted API relay as an advanced fallback. If name resolution fails, inspect the system resolver configuration before changing DNS servers.

---

### 🎁 Support Upstream Development

The following donation addresses are retained from the upstream README and support upstream development and maintenance:

* **BNB (BSC / BEP20)**: `0xB6d78c42CEB0687A31B8cfEBE4b51b6eB8953C17`
* **TRX (TRC20)**: `TSdzCW6JvsrqcppodYjhSrku4mYmDJ9pxf`

Thank you for your generosity and support! ❤️

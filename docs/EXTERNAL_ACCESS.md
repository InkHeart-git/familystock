# FamilyStock 外网访问方案

## 方案一：内网穿透（推荐，最简单）

### 1. 使用 Cloudflare Tunnel（免费）

**在NAS上安装 cloudflared：**

```bash
# Docker方式运行
mkdir -p /volume1/docker/cloudflare-tunnel
cd /volume1/docker/cloudflare-tunnel

# 运行tunnel（需要先在Cloudflare Dashboard获取token）
docker run -d --name cloudflare-tunnel \
  cloudflare/cloudflared:latest tunnel \
  --no-autoupdate run \
  --token YOUR_TUNNEL_TOKEN
```

**配置步骤：**
1. 访问 https://one.dash.cloudflare.com
2. 创建 Tunnel → 选择 Docker
3. 复制 token，替换上面命令中的 `YOUR_TUNNEL_TOKEN`
4. 在 Cloudflare Zero Trust 中添加 Public Hostname：
   - Subdomain: `familystock`
   - Domain: `你的域名.com`
   - Type: HTTP
   - URL: `familystock-frontend:80` (Docker内部网络)

**优点：**
- 免费，不暴露NAS IP
- 自带SSL证书
- 不需要公网IP

---

## 方案二：DDNS + 端口映射（需要公网IP）

### 1. 配置 DDNS（动态域名解析）

绿联 NAS 自带 DDNS 支持，或使用 Docker 运行 ddns-go：

```bash
mkdir -p /volume1/docker/ddns-go
docker run -d \
  --name ddns-go \
  --restart=unless-stopped \
  -p 9876:9876 \
  -v /volume1/docker/ddns-go:/root \
  jeessy/ddns-go
```

**支持的DNS服务商：**
- 阿里云DNS
- 腾讯云DNSPod
- Cloudflare
- 华为云
- ...

### 2. 路由器端口映射

在路由器设置端口转发：
```
外部 80 → NAS_IP:3000 (前端)
外部 443 → NAS_IP:3443 (前端HTTPS)
外部 5000 → NAS_IP:5000 (API，可选)
```

### 3. 使用 NPM (Nginx Proxy Manager) 管理反代

```bash
mkdir -p /volume1/docker/npm
cd /volume1/docker/npm

cat > docker-compose.yml << 'EOF'
version: '3'
services:
  app:
    image: jc21/nginx-proxy-manager:latest
    restart: unless-stopped
    ports:
      - "80:80"
      - "81:81"   # 管理界面
      - "443:443"
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
EOF

docker-compose up -d
```

**NPM 配置：**
1. 访问 `http://NAS_IP:81`
2. 默认账号: `admin@example.com` / `changeme`
3. 添加 Proxy Host：
   - Domain: `familystock.你的域名.com`
   - Scheme: http
   - Forward Hostname: `familystock-frontend`
   - Forward Port: `80`
   - 开启 Cache Assets 和 Block Common Exploits

---

## 方案三：VPN 回家（最安全）

### WireGuard VPN

```bash
mkdir -p /volume1/docker/wireguard
cd /volume1/docker/wireguard

cat > docker-compose.yml << 'EOF'
version: '3'
services:
  wireguard:
    image: linuxserver/wireguard
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    environment:
      - PUID=1000
      - PGID=1000
      - SERVERURL=你的DDNS域名
      - SERVERPORT=51820
      - PEERS=手机,电脑,平板
    volumes:
      - ./config:/config
    ports:
      - "51820:51820/udp"
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
    restart: unless-stopped
EOF

docker-compose up -d
```

**使用方式：**
1. 连接 VPN 后，直接访问 `http://NAS_IP:3000`
2. 就像在内网一样使用

---

## 方案对比

| 方案 | 难度 | 成本 | 速度 | 安全性 | 推荐度 |
|------|------|------|------|--------|--------|
| Cloudflare Tunnel | 低 | 免费 | 中等 | 高 | ⭐⭐⭐⭐⭐ |
| DDNS+端口映射 | 中 | 免费/低 | 快 | 中 | ⭐⭐⭐⭐ |
| VPN回家 | 中 | 免费 | 快 | 最高 | ⭐⭐⭐⭐ |

---

## 推荐配置（Cloudflare Tunnel）

**docker-compose.override.yml：**

```yaml
version: '3.8'

services:
  cloudflare-tunnel:
    image: cloudflare/cloudflared:latest
    container_name: familystock-tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token ${CF_TUNNEL_TOKEN}
    networks:
      - familystock-network
    depends_on:
      - frontend
```

**.env 添加：**
```bash
CF_TUNNEL_TOKEN=your_tunnel_token_here
```

**启动：**
```bash
docker-compose -f docker-compose.nas.yml -f docker-compose.override.yml up -d
```

---

## 安全建议

1. **开启HTTPS**：所有外网访问必须使用SSL
2. **设置强密码**：所有服务使用复杂密码
3. **限制访问IP**：如可能，限制特定IP访问
4. **定期备份**：数据库和配置文件定期备份
5. **监控日志**：使用绿联 NAS 的日志中心或安装 Fail2Ban

```bash
# 安装 Fail2Ban
docker run -d --name fail2ban \
  --network host \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  -v /volume1/docker/fail2ban:/data \
  -v /var/log:/var/log:ro \
  crazymax/fail2ban:latest
```

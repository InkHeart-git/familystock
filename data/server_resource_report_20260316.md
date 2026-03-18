# 服务器资源调查报告

**调查时间**: 2026-03-16 09:50
**调查人**: 灵犀
**服务器**: 新加坡腾讯云 (43.160.193.165)

---

## 💾 硬盘空间

### 总体使用情况

| 文件系统 | 总容量 | 已使用 | 可用 | 使用率 | 挂载点 |
|---------|--------|--------|------|--------|--------|
| `/dev/vda2` | 40G | 23G | 16G | **60%** | / |

**⚠️ 警告**: 硬盘使用率已达 60%，需关注

---

### 📊 目录空间分析 (TOP 15)

| 目录 | 大小 | 说明 |
|------|------|------|
| `/swapfile` | 8.1G | Swap 文件 1 |
| `/usr` | 4.4G | 系统软件 |
| `/root` | 4.4G | root 用户数据 |
| `/snap` | 4.2G | Snap 应用包 |
| `/var` | 3.3G | 可变数据 |
| `/swap.img` | 2.0G | Swap 文件 2 |
| `/boot` | 100M | 启动分区 |

---

### 🔍 Snap 包详细分析

| Snap 包 | 大小 | 说明 |
|---------|------|------|
| `gnome-46-2404` | 1.6G | GNOME 46 桌面环境 |
| `mesa-2404` | 1.2G | Mesa 3D 图形库 |
| `chromium` | 411M | Chromium 浏览器 |
| `gtk-common-themes` | 360M | GTK 通用主题 |
| `core22` | 249M | Snap 核心运行时 22 |
| `core24` | 219M | Snap 核心运行时 24 |
| `snapd` | 147M | Snap 守护进程 |
| `cups` | 129M | 打印服务 |

**Snap 总占用**: 4.2G

---

### 📁 FamilyStock 项目空间

| 目录 | 大小 | 说明 |
|------|------|------|
| `/var/www/familystock/api` | 352M | API 后端 |
| `/var/www/familystock/backend` | 14M | 后端代码 |
| `/var/www/familystock/archive` | 14M | 归档文件 |
| `/var/www/familystock/frontend` | 944K | 前端代码 |

**FamilyStock 总占用**: 527M

### 🔍 API 目录详细分析

| 子目录 | 大小 | 说明 |
|--------|------|------|
| `venv` | 351M | Python 虚拟环境 |
| `data` | 780K | 数据文件 |
| `app` | 380K | 应用代码 |
| `__pycache__` | 24K | Python 缓存 |

---

### 📋 日志文件空间

| 目录/文件 | 大小 | 说明 |
|-----------|------|------|
| `/var/log/journal` | 217M | Systemd 日志 |
| `/var/log/syslog.1` | 24M | 系统日志（轮转） |
| `/var/log/syslog` | 12M | 系统日志 |
| `/var/log/auth.log.1` | 2.7M | 认证日志（轮转） |
| `/var/log/sysstat` | 2.5M | 系统统计 |
| `/var/log/auth.log` | 2.3M | 认证日志 |
| `/var/log/nginx` | 1.7M | Nginx 日志 |
| `/var/log/familystock` | 1.2M | FamilyStock 日志 |

**日志总占用**: 264M

---

### 🔧 OpenClaw 相关空间

| 目录 | 大小 | 说明 |
|------|------|------|
| `/root/.nvm` | 273M | Node.js 版本管理器 |
| `/root/.openclaw` | 98M | OpenClaw 配置 |
| `/tmp/openclaw` | 23M | OpenClaw 临时日志 |

---

## 🧠 内存使用

### 总体使用情况

| 项目 | 数值 |
|------|------|
| **总内存** | 1.9Gi |
| **已使用** | 932Mi |
| **空闲** | 88Mi |
| **共享** | 8.0Mi |
| **缓存** | 1.1Gi |
| **可用** | 1.0Gi |

### Swap 空间

| 项目 | 数值 |
|------|------|
| **总 Swap** | 9.9Gi |
| **已使用** | 629Mi |
| **空闲** | 9.3Gi |

**Swap 配置**:
- `/swapfile`: 8.0G
- `/swap.img`: 2.0G

---

## ⚡ 系统负载

| 项目 | 数值 |
|------|------|
| **Load Average (1min)** | 0.10 |
| **Load Average (5min)** | 0.12 |
| **Load Average (15min)** | 0.05 |

**CPU 使用率**: 0.0% (空闲 100%)

---

## 🔍 关键进程资源占用

### OpenClaw Gateway
- **PID**: 274547
- **内存**: 613M (峰值 1.1G)
- **状态**: 运行中

### Nginx
- **内存**: 6.0M (峰值 17.1M)
- **状态**: 运行中

---

## ⚠️ 发现的问题

### 1. 硬盘使用率偏高 (60%)
**影响**: 接近 70% 警告阈值
**建议**:
- 清理旧日志文件
- 清理 Snap 包旧版本
- 清理 npm/pip 缓存
- 清理 Python `__pycache__`

### 2. Systemd 日志占用过大 (217M)
**影响**: 占用大量磁盘空间
**建议**:
```bash
# 限制日志大小
sudo journalctl --vacuum-size=50M

# 或者限制保留时间
sudo journalctl --vacuum-time=7d
```

### 3. 存在两个 Swap 文件
**影响**: 冗余配置
**当前**:
- `/swapfile`: 8.0G
- `/swap.img`: 2.0G
**建议**: 保留一个，删除另一个

### 4. GNOME 桌面环境占用过大 (1.6G)
**影响**: 服务器不需要桌面环境
**建议**: 如果不使用图形界面，可以卸载

---

## 💡 优化建议

### 立即执行 (节省约 1-2G)

1. **清理 Systemd 日志**
   ```bash
   sudo journalctl --vacuum-size=50M
   ```
   **预计节省**: ~160M

2. **清理 npm 缓存**
   ```bash
   npm cache clean --force
   ```
   **预计节省**: ~200-500M

3. **清理 pip 缓存**
   ```bash
   pip cache purge
   ```
   **预计节省**: ~100-300M

4. **清理 OpenClaw 临时日志**
   ```bash
   rm -f /tmp/openclaw/openclaw-*.log
   ```
   **预计节省**: ~20M

### 中期执行 (节省约 1-2G)

1. **清理 Snap 旧版本**
   ```bash
   sudo snap set system refresh.retain=2
   sudo snap refresh --list  # 查看可清理的包
   ```

2. **删除冗余 Swap 文件**
   ```bash
   # 保留 /swapfile (8G)
   sudo swapoff /swap.img
   sudo rm /swap.img
   sudo sed -i '/\/swap.img/d' /etc/fstab
   ```
   **预计节省**: 2.0G

3. **清理旧内核**
   ```bash
   sudo apt autoremove --purge
   ```
   **预计节省**: ~200-500M

### 长期优化

1. **配置日志轮转**
   - 为 `/var/log/familystock/*.log` 配置 logrotate
   - 自动清理 7 天前的日志

2. **监控告警**
   - 设置硬盘使用率 >70% 时发送告警
   - 定期执行上述清理脚本

---

## 📈 资源健康评分

| 资源类型 | 状态 | 评分 |
|---------|------|------|
| **硬盘空间** | ⚠️ 警告 | 6/10 (60% 使用率) |
| **内存** | ✅ 正常 | 9/10 (47% 使用率) |
| **Swap** | ✅ 正常 | 9/10 (6% 使用率) |
| **CPU** | ✅ 正常 | 10/10 (0% 使用率) |
| **系统负载** | ✅ 正常 | 10/10 (0.10) |

**综合评分**: 8.8/10

---

## 📝 总结

- **硬盘**: 40G 总容量，已使用 60%，需要清理
- **内存**: 1.9G 总容量，使用 47%，充足
- **CPU**: 基本空闲，负载很低
- **系统**: 运行稳定，已启动 3 天 16 小时

**主要问题**: 硬盘空间使用率偏高，主要由 Snap 包和日志文件占用

---

*报告生成时间: 2026-03-16 09:58*

# FamilyStock AI推演预警系统 V3 - 部署指南

## 系统概述

FamilyStock V3 是参考贝莱德阿拉丁(Aladdin)系统设计的全自动AI推演预警系统。

**核心特性:**
- ✅ 全自动运行，无需人工干预
- ✅ 流水线处理: 新闻采集 → NLP分析 → 黑天鹅识别 → AI推演 → 预警生成
- ✅ 实时预警展示，前端自动更新
- ✅ 风险仪表盘(类似阿拉丁)
- ✅ 资产敞口分析
- ✅ 压力测试和情景分析

---

## 文件清单

```
/var/www/familystock/
├── index_v3.html              # 前端页面 (66KB)
├── api/
│   ├── server_v3.py           # API服务器 (22KB)
│   ├── pipeline.py            # 全自动流水线 (29KB)
│   ├── start.sh               # 启动脚本
│   ├── README_V3.md           # 使用说明
│   ├── ARCHITECTURE.md        # 架构文档
│   └── logs/                  # 日志目录
```

---

## 快速启动

### 1. 启动服务
```bash
cd /var/www/familystock/api
./start.sh
```

### 2. 访问系统
- 前端页面: http://43.160.193.165/index_v3.html
- API文档: http://43.160.193.165:8080/

---

## 手动启动

如果自动启动失败，可以手动启动:

```bash
cd /var/www/familystock/api

# 安装依赖
pip3 install flask flask-cors requests loguru jieba snownlp numpy

# 启动服务
python3 server_v3.py
```

服务将在 0.0.0.0:8080 启动。

---

## API端点

### 流水线API
```
GET  /api/v3/pipeline/status       # 获取流水线状态
POST /api/v3/pipeline/run          # 手动触发流水线
POST /api/v3/pipeline/start        # 启动持续运行模式
POST /api/v3/pipeline/stop         # 停止流水线
```

### 预警API
```
GET /api/v3/alerts                 # 获取预警列表
GET /api/v3/alerts/active          # 获取有效预警
GET /api/v3/alerts/stream          # SSE实时预警流
GET /api/v3/alerts/{id}            # 获取预警详情
```

### 仪表盘API
```
GET /api/v3/dashboard              # 风险仪表盘数据
GET /api/v3/dashboard/risk-metrics # 风险指标详情
```

### 新闻API
```
GET /api/v3/news                   # 新闻列表
GET /api/v3/news/analysis          # 新闻分析结果
```

### 推演API
```
GET /api/v3/simulation             # AI推演结果
GET /api/v3/simulation/scenarios   # 情景分析
```

---

## 系统配置

### 流水线周期 (默认5分钟)
在 `server_v3.py` 中修改:
```python
# 启动后台流水线（持续模式）
asyncio.run(pl.run_continuous(interval_minutes=5))
```

### 预警等级阈值
在 `pipeline.py` 中修改:
```python
def _determine_level(self, event):
    urgency = event["urgency"]
    score = event["score"]
    
    if urgency >= 0.95 and score >= 0.9:
        return AlertLevel.CRITICAL
    elif urgency >= 0.85 and score >= 0.8:
        return AlertLevel.WARNING
    elif urgency >= 0.7 and score >= 0.7:
        return AlertLevel.CAUTION
    else:
        return AlertLevel.INFO
```

---

## 日志查看

```bash
# 服务器日志
tail -f /var/www/familystock/api/logs/server.log

# 流水线日志
tail -f /var/www/familystock/api/logs/pipeline.log

# API日志
tail -f /var/www/familystock/api/logs/api.log
```

---

## 故障排查

### 服务无法启动
1. 检查Python版本: `python3 --version` (需要3.8+)
2. 检查端口占用: `lsof -i :8080`
3. 查看日志: `cat /var/www/familystock/api/logs/server.log`

### API无响应
1. 检查服务状态: `curl http://localhost:8080/`
2. 检查防火墙: `ufw status`
3. 检查Nginx配置

### 前端无法连接API
1. 检查API_BASE_URL配置 (index_v3.html)
2. 检查CORS设置
3. 检查网络连通性

---

## 系统维护

### 重启服务
```bash
# 停止现有服务
pkill -f "server_v3.py"

# 重新启动
cd /var/www/familystock/api
./start.sh
```

### 清理数据
```bash
# 清理日志
cd /var/www/familystock/api/logs
rm -f *.log

# 清理预警数据 (重启后重新生成)
```

---

## 安全建议

1. **修改默认端口** - 生产环境建议修改8080端口
2. **启用HTTPS** - 使用Nginx反向代理+SSL证书
3. **访问控制** - 配置防火墙限制API访问
4. **日志审计** - 定期检查日志文件

---

## 联系支持

如有问题，请检查:
1. 架构文档: `/var/www/familystock/api/ARCHITECTURE.md`
2. 使用说明: `/var/www/familystock/api/README_V3.md`
3. 系统日志: `/var/www/familystock/api/logs/`

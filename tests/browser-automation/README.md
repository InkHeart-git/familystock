# MiniRock 自动化测试方案

**版本**: v1.0  
**创建时间**: 2026-03-16  
**目标**: 使用 browser-automation-ultra 实现零 Token 回归测试

---

## 📁 文件结构

```
/var/www/familystock/
└── tests/
    ├── browser-automation/
    │   ├── scripts/
    │   │   ├── test-minirock-full.js      # 完整流程测试
    │   │   ├── test-minirock-auth.js      # 认证模块测试
    │   │   ├── test-minirock-portfolio.js # 持仓功能测试
    │   │   └── utils/
    │   │       └── human-like.js          # 反检测工具库
    │   ├── browser-lock.sh                # CDP 锁管理脚本
    │   ├── run-tests.sh                   # 一键测试入口
    │   └── README.md                      # 使用说明
    └── reports/                           # 测试报告输出
```

---

## 🚀 部署步骤

### 1. 安装依赖

```bash
# 进入测试目录
cd /var/www/familystock/tests/browser-automation

# 安装 Playwright
npm init -y
npm install playwright

# 给脚本执行权限
chmod +x browser-lock.sh run-tests.sh
```

### 2. 配置环境

编辑 `config.json`:
```json
{
  "baseUrl": "http://43.160.193.165",
  "testAccount": {
    "phone": "13800138001",
    "password": "Test123456"
  },
  "selectors": {
    "loginPhone": "input[placeholder='请输入手机号']",
    "loginPassword": "input[type='password']",
    "loginButton": "button:has-text('立即登录')",
    "registerButton": "a:has-text('立即注册')",
    "searchInput": "input[placeholder='搜索股票名称或代码']",
    "addStockButton": "button:has-text('确认添加')"
  }
}
```

### 3. 运行测试

```bash
# 完整流程测试
./run-tests.sh full

# 单独测试认证
./run-tests.sh auth

# 单独测试持仓
./run-tests.sh portfolio

# 生成报告
./run-tests.sh report
```

---

## 📊 测试覆盖

| 模块 | 测试项 | 预期结果 |
|------|--------|----------|
| 注册 | 新用户注册 | 显示"注册成功"，自动登录 |
| 登录 | 已有账号登录 | 跳转到首页，显示用户名 |
| 搜索 | 代码搜索(000001) | 显示"平安银行"结果 |
| 搜索 | 名称搜索(平安银行) | 显示搜索结果 |
| 添加持仓 | 填写数量+成本 | 持仓列表显示新股票 |
| 个股详情 | 查看股票详情 | 显示价格、AI诊断、新闻 |
| 组合分析 | 查看组合页面 | 显示总市值、健康度 |
| 自选股 | 添加自选股 | 自选股列表更新 |

---

## 🔧 故障排查

| 问题 | 解决 |
|------|------|
| CDP 连接失败 | 运行 `./browser-lock.sh release` 释放锁 |
| 选择器失效 | 用浏览器工具重新 snapshot 更新 selectors |
| 测试超时 | 增加 `--timeout 300` 参数 |
| 登录过期 | 删除 cookies，重新登录 |

---

## 📈 CI/CD 集成

可加入定时任务 (cron):
```bash
# 每天 9:00 自动测试
0 9 * * * cd /var/www/familystock/tests/browser-automation && ./run-tests.sh full > reports/daily-$(date +\%Y\%m\%d).log 2>&1
```

---

## 📞 联系

- 测试脚本维护: 小七
- 后端对接: 方舟
- 前端对接: 玲珑

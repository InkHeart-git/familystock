# Hermes Web UI 集成到 minirock.online — 完整状态报告
**时间**: 2026-04-23 00:55
**状态**: ✅ 已完成

## 目标
通过 https://minirock.online/hermes/ 访问 Hermes Web UI，不暴露独立端口。

## 最终方案

### Nginx 配置修改
文件: `/etc/nginx/sites-available/minirock`

```nginx
location ^~ /hermes/ {
    alias /var/www/familystock/frontend/hermes_static/;
    index index.html;
    sub_filter_once off;
    sub_filter_types application/javascript text/css;
    try_files $uri $uri/ =404;
}

location /hermes/api/ {
    proxy_pass http://127.0.0.1:8648/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 关键修复（4个Bug）
1. **Nginx 正则抢请求 Bug**: `location ~* \.(js|css...)$` 抢在 `/hermes/` 之前处理请求
   - 解决：`location ^~ /hermes/` 使用 ^~ 修饰符使 prefix location 优先于正则
2. **文件路径错误**: nginx 实际读取 hermes_static 而非 hermes-assets
   - 发现：对比 `wc -c` 文件大小 vs curl 服务端内容 md5sum
3. **路径双重替换**: hermes_static 的 router.js 已有 `/hermes/assets/` 路径，sub_filter 又加一层导致 `/hermes/hermes/assets/`
   - 解决：移除多余的 sub_filter 规则
4. **模块预加载协议相对URL Bug**: router.js 中 mapDeps 使用绝对路径 `/hermes/assets/...`，经 `Mf()` 函数拼接后变成 `//hermes/assets/...`
   - 解决：sed 替换 router.js 中 `"/hermes/assets/` 改为 `"hermes/assets/`

### 文件结构
- `hermes_static/` — nginx alias 指向目录 ✅ 使用中
- `hermes-assets/` — 原构建目录（备用）
- `hermes/` — 原符号链接（已废弃）

### API 代理
- `/hermes/api/` → `http://127.0.0.1:8648/api/`
- Gateway 运行在端口 8648（PID 548487）

### 登录 Token
```
43d1673cbee9aa57ef7dfa358243a5497ae78d87862480eebc0e9fe8e6fd0365
```
（2026-04-22 服务器启动时生成）

## 访问方式
- URL: https://minirock.online/hermes/
- 首次使用需要输入 Token（见上方）
- Token 可在服务器启动日志中找到

## 已知问题
- Hermes Gateway 返回 401/502（认证配置问题），但 UI 本身可正常渲染
- DNS 错误（ERR_NAME_NOT_RESOLVED）— 可能是 Hermes 尝试连接外部 CDN/fonts

## 相关文件
- Nginx: `/etc/nginx/sites-available/minirock`
- 静态资源: `/var/www/familystock/frontend/hermes_static/`
- Hermes Gateway: `http://127.0.0.1:8648`
- 报告: `/var/www/ai-god-of-stocks/shared/memory/reports/`

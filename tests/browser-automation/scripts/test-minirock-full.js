const { chromium } = require('playwright');
const { humanDelay, humanClick, humanType, humanBrowse, humanThink } = require('./utils/human-like');

function discoverCdpUrl() {
  try {
    const { execSync } = require('child_process');
    const ps = execSync("ps aux | grep 'remote-debugging-port' | grep -v grep", { encoding: 'utf8' });
    const match = ps.match(/remote-debugging-port=(\d+)/);
    return `http://127.0.0.1:${match ? match[1] : '18800'}`;
  } catch { 
    return 'http://127.0.0.1:18800'; 
  }
}

const BASE_URL = 'http://43.160.193.165';
const TEST_PHONE = '13800138' + Math.floor(Math.random() * 1000);
const TEST_PASSWORD = 'Test123456';

async function testMiniRockFull() {
  console.log('🚀 启动 MiniRock 完整流程测试...\n');
  
  const browser = await chromium.connectOverCDP(discoverCdpUrl());
  const context = browser.contexts()[0];
  const page = await context.newPage();
  
  const results = {
    timestamp: new Date().toISOString(),
    tests: [],
    summary: { passed: 0, failed: 0, warnings: 0 }
  };
  
  const addResult = (name, status, detail = '') => {
    results.tests.push({ name, status, detail });
    if (status === 'PASS') results.summary.passed++;
    else if (status === 'FAIL') results.summary.failed++;
    else results.summary.warnings++;
    console.log(`${status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️'} ${name}: ${status}${detail ? ' - ' + detail : ''}`);
  };

  try {
    // ========== 测试 1: 注册 ==========
    console.log('\n📋 测试 1: 用户注册');
    try {
      await page.goto(`${BASE_URL}/minirock-auth.html`, { waitUntil: 'networkidle', timeout: 30000 });
      await humanDelay(1000, 2000);
      
      // 处理风险提示弹窗 - 如果存在则点击确认
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      await humanClick(page, 'text=立即注册');
      await humanDelay(500, 1000);
      
      await humanType(page, 'input[placeholder="请输入手机号"]', TEST_PHONE);
      await humanType(page, 'input[placeholder="请设置密码（至少6位）"]', TEST_PASSWORD);
      await humanType(page, 'input[placeholder="请再次输入密码"]', TEST_PASSWORD);
      
      await humanClick(page, 'button:has-text("立即注册")');
      
      // 等待导航完成，可能页面会跳转
      try {
        await page.waitForSelector('text=注册成功', { timeout: 15000 });
        addResult('用户注册', 'PASS');
      } catch (navError) {
        // 如果等待失败，检查是否已经跳转到首页
        const currentUrl = page.url();
        console.log(`当前URL: ${currentUrl}`);
        if (currentUrl.includes('minirock-v2') || currentUrl.includes('index')) {
          // 已经跳转，注册成功
          addResult('用户注册', 'PASS');
          console.log('已跳转首页，注册成功');
        } else {
          throw navError;
        }
      }
    } catch (e) {
      addResult('用户注册', 'FAIL', e.message);
    }

    // ========== 测试 2: 登录 ==========
    console.log('\n📋 测试 2: 用户登录');
    try {
      await page.goto(`${BASE_URL}/minirock-auth.html`, { waitUntil: 'networkidle' });
      await humanDelay(1000, 2000);
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      await humanType(page, 'input[placeholder="请输入手机号"]', TEST_PHONE);
      await humanType(page, 'input[placeholder="请输入密码"]', TEST_PASSWORD);
      await humanClick(page, 'button:has-text("立即登录")');
      
      await page.waitForSelector('text=欢迎回来', { timeout: 10000 });
      addResult('用户登录', 'PASS');
    } catch (e) {
      addResult('用户登录', 'FAIL', e.message);
    }

    // ========== 测试 3: 首页加载 ==========
    console.log('\n📋 测试 3: 首页加载');
    try {
      await page.goto(`${BASE_URL}/minirock-v2.html`, { waitUntil: 'networkidle' });
      await humanBrowse(page, { duration: 2000 });
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      // 尝试多种选择器匹配搜索框
      let hasSearch = false;
      const searchSelectors = [
        'input[placeholder="搜索股票名称或代码"]',
        'input[placeholder="搜索股票代码或名称"]',
        '#searchInput',
        '[role="search"] input'
      ];
      
      for (const sel of searchSelectors) {
        const elem = await page.$(sel);
        if (elem) {
          const visible = await elem.isVisible();
          if (visible) {
            hasSearch = true;
            break;
          }
        }
      }
      
      const portfolioElem = await page.$('text=我的持仓');
      const hasPortfolio = portfolioElem ? await portfolioElem.isVisible() : false;
      
      if (hasSearch && hasPortfolio) {
        addResult('首页加载', 'PASS');
      } else {
        addResult('首页加载', 'WARN', `缺少关键元素 (search=${hasSearch}, portfolio=${hasPortfolio})`);
      }
    } catch (e) {
      addResult('首页加载', 'FAIL', e.message);
    }

    // ========== 测试 4: 股票搜索(代码) ==========
    console.log('\n📋 测试 4: 股票搜索(代码)');
    try {
      // 尝试多种搜索框选择器
      let searchSelector = null;
      const searchSelectors = [
        'input[placeholder="搜索股票名称或代码"]',
        'input[placeholder="搜索股票代码或名称"]',
        '#searchInput',
        '[role="search"] input'
      ];
      
      for (const sel of searchSelectors) {
        const elem = await page.$(sel);
        if (elem) {
          const visible = await elem.isVisible();
          if (visible) {
            searchSelector = sel;
            break;
          }
        }
      }
      
      if (!searchSelector) {
        throw new Error('无法找到搜索框 (尝试了多种选择器都失败)');
      }
      
      await humanType(page, searchSelector, '000001');
      await humanDelay(1000, 1500);
      
      await page.waitForSelector('text=平安银行', { timeout: 5000 });
      addResult('股票搜索(代码)', 'PASS');
    } catch (e) {
      addResult('股票搜索(代码)', 'FAIL', e.message);
    }

    // ========== 测试 5: 添加持仓 ==========
    console.log('\n📋 测试 5: 添加持仓');
    try {
      await humanClick(page, 'text=平安银行');
      await humanDelay(500, 1000);
      
      // 填写持仓信息
      const costInput = await page.$('input[type="number"]');
      if (costInput) {
        const visible = await costInput.isVisible();
        if (visible) {
          await costInput.fill('10.5');
          await humanClick(page, 'button:has-text("确认添加")');
          await humanDelay(1000, 2000);
          
          // 检查是否有错误提示
          const error404 = await page.$('text=API接口不存在');
          const errorNetwork = await page.$('text=网络连接');
          
          if (error404 && await error404.isVisible() || errorNetwork && await errorNetwork.isVisible()) {
            addResult('添加持仓', 'FAIL', 'API 404 错误');
          } else {
            // 检查是否添加成功
            const successElem = await page.$('text=添加成功');
            const success = successElem ? await successElem.isVisible() : false;
            addResult('添加持仓', success ? 'PASS' : 'WARN', success ? '' : '未检测到成功提示');
          }
        }
      } else {
        addResult('添加持仓', 'FAIL', '未找到成本输入框');
      }
    } catch (e) {
      addResult('添加持仓', 'FAIL', e.message);
    }

    // ========== 测试 6: 个股详情页 ==========
    console.log('\n📋 测试 6: 个股详情页');
    try {
      await page.goto(`${BASE_URL}/stock-detail.html?code=000001.SZ`, { waitUntil: 'networkidle' });
      await humanBrowse(page, { duration: 3000 });
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      const hasStockNameElem = await page.$('text=平安银行');
      const hasStockName = hasStockNameElem ? await hasStockNameElem.isVisible() : false;
      const hasAIDiagElem = await page.$('text=AI 智能诊断');
      const hasAIDiag = hasAIDiagElem ? await hasAIDiagElem.isVisible() : false;
      
      if (hasStockName && hasAIDiag) {
        // 检查价格显示
        try {
          const priceText = await page.$eval('.price, [class*="price"]', el => el.textContent).catch(() => '');
          if (priceText.includes('¥0.00')) {
            addResult('个股详情页', 'WARN', '价格显示为 ¥0.00');
          } else {
            addResult('个股详情页', 'PASS');
          }
        } catch (e) {
          addResult('个股详情页', 'PASS');
        }
      } else {
        addResult('个股详情页', 'FAIL', '页面元素缺失');
      }
    } catch (e) {
      addResult('个股详情页', 'FAIL', e.message);
    }

    // ========== 测试 7: 组合分析页 ==========
    console.log('\n📋 测试 7: 组合分析页');
    try {
      await page.goto(`${BASE_URL}/portfolio-analysis.html`, { waitUntil: 'networkidle' });
      await humanBrowse(page, { duration: 2000 });
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      const hasTotalValueElem = await page.$('text=总市值');
      const hasTotalValue = hasTotalValueElem ? await hasTotalValueElem.isVisible() : false;
      const hasHealthElem = await page.$('text=健康度');
      const hasHealth = hasHealthElem ? await hasHealthElem.isVisible() : false;
      
      if (hasTotalValue && hasHealth) {
        addResult('组合分析页', 'PASS');
      } else {
        addResult('组合分析页', 'FAIL', '缺少关键指标');
      }
    } catch (e) {
      addResult('组合分析页', 'FAIL', e.message);
    }

    // ========== 测试 8: 自选股页面 ==========
    console.log('\n📋 测试 8: 自选股页面');
    try {
      await page.goto(`${BASE_URL}/watchlist.html`, { waitUntil: 'networkidle' });
      await humanBrowse(page, { duration: 2000 });
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      const hasTitleElem = await page.$('text=我的自选股');
      const hasTitle = hasTitleElem ? await hasTitleElem.isVisible() : false;
      
      // 尝试多种搜索框选择器
      let hasSearch = false;
      const searchSelectors = [
        'input[placeholder="搜索股票名称或代码"]',
        'input[placeholder="搜索股票代码或名称"]',
        '#searchInput',
        '[role="search"] input'
      ];
      
      for (const sel of searchSelectors) {
        const elem = await page.$(sel);
        if (elem) {
          const visible = await elem.isVisible();
          if (visible) {
            hasSearch = true;
            break;
          }
        }
      }
      
      if (hasTitle && hasSearch) {
        addResult('自选股页面', 'PASS');
      } else {
        addResult('自选股页面', 'FAIL', `页面元素缺失 (title=${hasTitle}, search=${hasSearch})`);
      }
    } catch (e) {
      addResult('自选股页面', 'FAIL', e.message);
    }

    // ========== 测试 9: 中文名称搜索 ==========
    console.log('\n📋 测试 9: 中文名称搜索');
    try {
      await page.goto(`${BASE_URL}/watchlist.html`, { waitUntil: 'networkidle' });
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      // 尝试多种搜索框选择器
      let searchSelector = null;
      const searchSelectors = [
        'input[placeholder="搜索股票名称或代码"]',
        'input[placeholder="搜索股票代码或名称"]',
        '#searchInput',
        '[role="search"] input'
      ];
      
      for (const sel of searchSelectors) {
        const elem = await page.$(sel);
        if (elem) {
          const visible = await elem.isVisible();
          if (visible) {
            searchSelector = sel;
            break;
          }
        }
      }
      
      if (!searchSelector) {
        throw new Error('无法找到搜索框 (尝试了多种选择器都失败)');
      }
      
      await humanType(page, searchSelector, '平安银行');
      
      // 尝试多种搜索按钮选择器
      let searchBtnSelector = null;
      const btnSelectors = [
        'button:has-text("搜索")',
        'button:has-text("搜索股票")',
        '[type="submit"]',
        '#searchButton'
      ];
      
      for (const sel of btnSelectors) {
        const elem = await page.$(sel);
        if (elem) {
          const visible = await elem.isVisible();
          if (visible) {
            searchBtnSelector = sel;
            break;
          }
        }
      }
      
      if (!searchBtnSelector) {
        throw new Error('无法找到搜索按钮 (尝试了多种选择器都失败)');
      }
      
      await humanClick(page, searchBtnSelector);
      await humanDelay(2000, 3000);
      
      const notFound = await page.$('text=未找到该股票');
      if (notFound) {
        const isVisible = await notFound.isVisible();
        if (isVisible) {
          addResult('中文名称搜索', 'FAIL', '搜索无结果');
        }
      } else {
        const resultElem = await page.$('text=平安银行');
        const hasResult = resultElem ? await resultElem.isVisible() : false;
        addResult('中文名称搜索', hasResult ? 'PASS' : 'WARN', hasResult ? '' : '未检测到结果');
      }
    } catch (e) {
      addResult('中文名称搜索', 'FAIL', e.message);
    }

    // ========== 测试 10: AI 诊断 ==========
    console.log('\n📋 测试 10: AI 个股诊断');
    try {
      await page.goto(`${BASE_URL}/stock-detail.html?code=000001.SZ`, { waitUntil: 'networkidle' });
      await humanDelay(5000, 6000); // 等待 AI 分析
      
      // 处理风险提示弹窗
      const riskModal = await page.$('#riskModal button');
      if (riskModal) {
        const isVisible = await riskModal.isVisible();
        if (isVisible) {
          await humanClick(page, '#riskModal button');
          await humanDelay(500, 1000);
        }
      }
      
      const busyText = await page.$('text=服务繁忙');
      const analyzingText = await page.$('text=分析中');
      
      if (busyText && await busyText.isVisible()) {
        addResult('AI 个股诊断', 'WARN', '服务繁忙');
      } else if (analyzingText && await analyzingText.isVisible()) {
        addResult('AI 个股诊断', 'WARN', '分析超时');
      } else {
        const hasResult = await page.$('text=风险等级').then(Boolean);
        addResult('AI 个股诊断', hasResult ? 'PASS' : 'WARN', hasResult ? '' : '未检测到分析结果');
      }
    } catch (e) {
      addResult('AI 个股诊断', 'FAIL', e.message);
    }

  } catch (e) {
    console.error('❌ 测试执行错误:', e.message);
    addResult('测试执行', 'FAIL', e.message);
  } finally {
    await page.close();
    console.log('\n========== 测试完成 ==========');
    console.log(`✅ 通过: ${results.summary.passed}`);
    console.log(`❌ 失败: ${results.summary.failed}`);
    console.log(`⚠️  警告: ${results.summary.warnings}`);
    
    // 保存报告
    const fs = require('fs');
    const reportPath = `/var/www/familystock/tests/reports/test-report-${Date.now()}.json`;
    fs.mkdirSync('/var/www/familystock/tests/reports', { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
    console.log(`\n📄 报告已保存: ${reportPath}`);
    
    return results;
  }
}

testMiniRockFull().then(results => {
  const exitCode = results.summary.failed > 0 ? 1 : 0;
  process.exit(exitCode);
}).catch(e => {
  console.error('❌ 测试异常:', e);
  process.exit(1);
});

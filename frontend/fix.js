// 修复风险提示兼容性
function closeDisclaimer() {
  console.log(关闭风险提示);
  const modal = document.getElementById(disclaimerModal);
  if (modal) {
    modal.style.display = none;
    modal.classList.remove(active);
  }
  try {
    localStorage.setItem(disclaimerAgreed, true);
  } catch (e) {
    console.warn(localStorage不可用, e);
  }
  return false;
}

// 修复搜索功能
async function performSearch(query) {
  console.log(搜索:, query);
  const searchResults = document.getElementById(searchResults);
  
  try {
    // 优先使用本地搜索，速度更快
    if (window.stockDatabase && window.stockDatabase.length > 0) {
      const results = window.stockDatabase.filter(stock => {
        return stock.name.toLowerCase().includes(query.toLowerCase()) ||
               stock.code.includes(query.toUpperCase());
      }).slice(0, 10);
      console.log(本地搜索结果:, results);
      displaySearchResults(results);
      return;
    }
    
    // 本地数据库不可用时调用API
    const data = await MiniRockAPI.Stock.search(query, 10);
    displaySearchResults(data.results || []);
  } catch (error) {
    console.warn(搜索失败:, error);
    // 使用备用搜索
    const backup = [
      { code: 600519, name: 贵州茅台, type: 股票 },
      { code: 300750, name: 宁德时代, type: 股票 },
      { code: 002594, name: 比亚迪, type: 股票 },
      { code: 601318, name: 中国平安, type: 股票 },
      { code: 600036, name: 招商银行, type: 股票 }
    ].filter(s => s.name.includes(query) || s.code.includes(query.toUpperCase()));
    displaySearchResults(backup);
  }
}

// 统一的自选股和持仓数据管理
const StockDataManager = {
    // 存储键名
    WATCHLIST_KEY: 'minirock_watchlist',
    PORTFOLIO_KEY: 'minirock_portfolio',
    
    // 获取自选股
    getWatchlist() {
        const saved = localStorage.getItem(this.WATCHLIST_KEY);
        return saved ? JSON.parse(saved) : [];
    },
    
    // 保存自选股
    saveWatchlist(watchlist) {
        localStorage.setItem(this.WATCHLIST_KEY, JSON.stringify(watchlist));
        this.notifyUpdate();
    },
    
    // 添加自选股
    addToWatchlist(stock) {
        const watchlist = this.getWatchlist();
        const exists = watchlist.some(item => item.code === stock.code);
        if (!exists) {
            watchlist.push(stock);
            this.saveWatchlist(watchlist);
            return true;
        }
        return false;
    },
    
    // 移除自选股
    removeFromWatchlist(code) {
        let watchlist = this.getWatchlist();
        watchlist = watchlist.filter(item => item.code !== code);
        this.saveWatchlist(watchlist);
    },
    
    // 获取持仓
    getPortfolio() {
        const saved = localStorage.getItem(this.PORTFOLIO_KEY);
        return saved ? JSON.parse(saved) : [];
    },
    
    // 保存持仓
    savePortfolio(portfolio) {
        localStorage.setItem(this.PORTFOLIO_KEY, JSON.stringify(portfolio));
        this.notifyUpdate();
    },
    
    // 添加持仓
    addToPortfolio(stock) {
        const portfolio = this.getPortfolio();
        const exists = portfolio.some(item => item.code === stock.code);
        if (!exists) {
            portfolio.push(stock);
            this.savePortfolio(portfolio);
            return true;
        }
        return false;
    },
    
    // 数据更新通知
    notifyUpdate() {
        // 触发自定义事件，通知所有页面数据更新
        window.dispatchEvent(new CustomEvent('stockDataUpdated'));
    },
    
    // 监听数据更新
    onUpdate(callback) {
        window.addEventListener('stockDataUpdated', callback);
    },
    
    // 取消监听
    offUpdate(callback) {
        window.removeEventListener('stockDataUpdated', callback);
    }
};

// 全局初始化
if (typeof window !== 'undefined') {
    window.StockDataManager = StockDataManager;
}

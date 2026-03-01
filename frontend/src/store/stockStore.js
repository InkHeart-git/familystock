import { create } from 'zustand'

export const useStockStore = create((set, get) => ({
  // 股票列表
  stocks: [],
  selectedStock: null,
  loading: false,
  error: null,
  
  // 搜索状态
  searchQuery: '',
  searchResults: [],
  searching: false,
  
  // 自选股
  watchlist: [],
  familyWatchlist: [],
  
  // 行情数据
  realtimeQuotes: {},
  
  setStocks: (stocks) => set({ stocks }),
  setSelectedStock: (stock) => set({ selectedStock: stock }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  
  // 搜索
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSearchResults: (results) => set({ searchResults: results }),
  setSearching: (searching) => set({ searching }),
  
  // 自选股操作
  addToWatchlist: (stock) => {
    const current = get().watchlist
    if (!current.find(s => s.symbol === stock.symbol)) {
      set({ watchlist: [...current, stock] })
    }
  },
  
  removeFromWatchlist: (symbol) => {
    set({ 
      watchlist: get().watchlist.filter(s => s.symbol !== symbol) 
    })
  },
  
  setWatchlist: (watchlist) => set({ watchlist }),
  setFamilyWatchlist: (watchlist) => set({ familyWatchlist: watchlist }),
  
  // 实时行情更新
  updateQuote: (symbol, quote) => {
    set({ 
      realtimeQuotes: { 
        ...get().realtimeQuotes, 
        [symbol]: quote 
      } 
    })
  },
  
  // 获取单个股票行情
  getQuote: (symbol) => get().realtimeQuotes[symbol],
}))

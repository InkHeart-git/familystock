import { useState } from 'react'
import { Search, Loader2, Plus } from 'lucide-react'
import { useStockStore } from '../store/stockStore'

// 模拟搜索结果
const mockSearchResults = [
  { symbol: '000001.SZ', name: '平安银行', market: '深交所', price: 12.34 },
  { symbol: '600519.SH', name: '贵州茅台', market: '上交所', price: 1689.00 },
  { symbol: '000858.SZ', name: '五粮液', market: '深交所', price: 145.60 },
  { symbol: '300750.SZ', name: '宁德时代', market: '深交所', price: 189.50 },
  { symbol: '002594.SZ', name: '比亚迪', market: '深交所', price: 245.80 },
  { symbol: '00700.HK', name: '腾讯控股', market: '港交所', price: 298.60 },
]

export default function StockSearch() {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState([])
  const { addToWatchlist, watchlist } = useStockStore()

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setSearching(true)
    // 模拟API调用
    setTimeout(() => {
      const filtered = mockSearchResults.filter(
        stock => 
          stock.name.includes(query) || 
          stock.symbol.toLowerCase().includes(query.toLowerCase())
      )
      setResults(filtered)
      setSearching(false)
    }, 500)
  }

  const isInWatchlist = (symbol) => watchlist.some(s => s.symbol === symbol)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">股票搜索</h1>
        <p className="text-gray-600 mt-1">搜索股票代码或名称，添加到你的自选池</p>
      </div>

      {/* 搜索框 */}
      <form onSubmit={handleSearch} className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入股票代码或名称，如：茅台、000001..."
          className="input pl-12 pr-4 py-3 text-lg"
        />
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary disabled:opacity-50"
        >
          {searching ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            '搜索'
          )}
        </button>
      </form>

      {/* 搜索结果 */}
      {results.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">搜索结果</h2>
          <div className="divide-y divide-gray-200">
            {results.map((stock) => (
              <div key={stock.symbol} className="py-4 flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                    <span className="text-primary-700 font-bold">{stock.name.charAt(0)}</span>
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{stock.name}</div>
                    <div className="text-sm text-gray-500">{stock.symbol} · {stock.market}</div>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <span className="text-lg font-medium">¥{stock.price.toFixed(2)}</span>
                  <button
                    onClick={() => addToWatchlist(stock)}
                    disabled={isInWatchlist(stock.symbol)}
                    className={`btn ${
                      isInWatchlist(stock.symbol)
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'btn-secondary'
                    }`}
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    {isInWatchlist(stock.symbol) ? '已添加' : '加入自选'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 热门搜索 */}
      {!results.length && !searching && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">热门搜索</h2>
          <div className="flex flex-wrap gap-2">
            {['贵州茅台', '宁德时代', '比亚迪', '腾讯控股', '阿里巴巴', '中国平安'].map((term) => (
              <button
                key={term}
                onClick={() => {
                  setQuery(term)
                  handleSearch({ preventDefault: () => {} })
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-full text-sm hover:bg-gray-200 transition-colors"
              >
                {term}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

import { useEffect } from 'react'
import { TrendingUp, TrendingDown, Star, Search, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useStockStore } from '../store/stockStore'

// 模拟市场数据
const marketIndices = [
  { name: '上证指数', symbol: '000001.SH', price: 3052.34, change: 0.85, changePercent: 0.03 },
  { name: '深证成指', symbol: '399001.SZ', price: 9789.12, change: -12.45, changePercent: -0.13 },
  { name: '创业板指', symbol: '399006.SZ', price: 1934.56, change: 8.92, changePercent: 0.46 },
  { name: '恒生指数', symbol: 'HSI', price: 16789.45, change: 156.78, changePercent: 0.94 },
]

const hotStocks = [
  { symbol: '000001.SZ', name: '平安银行', price: 12.34, change: 2.15, changePercent: 2.15 },
  { symbol: '600519.SH', name: '贵州茅台', price: 1689.00, change: -5.20, changePercent: -0.31 },
  { symbol: '000858.SZ', name: '五粮液', price: 145.60, change: 3.45, changePercent: 2.43 },
  { symbol: '300750.SZ', name: '宁德时代', price: 189.50, change: 6.80, changePercent: 3.72 },
  { symbol: '002594.SZ', name: '比亚迪', price: 245.80, change: -2.10, changePercent: -0.85 },
]

const recentAnalyses = [
  { id: 1, stock: '贵州茅台', type: '财报解读', date: '2024-03-01', summary: 'Q4营收同比增长15%，符合市场预期...' },
  { id: 2, stock: '宁德时代', type: 'AI筛选', date: '2024-03-01', summary: '基于技术指标和基本面分析，建议关注...' },
  { id: 3, stock: '比亚迪', type: '新闻分析', date: '2024-02-29', summary: '新能源汽车销量创新高，利好股价...' },
]

export default function Dashboard() {
  const { watchlist, setWatchlist } = useStockStore()

  useEffect(() => {
    // 加载用户自选股数据
    setWatchlist([
      { symbol: '000001.SZ', name: '平安银行', price: 12.34, change: 2.15, changePercent: 2.15 },
      { symbol: '600519.SH', name: '贵州茅台', price: 1689.00, change: -5.20, changePercent: -0.31 },
    ])
  }, [setWatchlist])

  return (
    <div className="space-y-6">
      {/* 欢迎区域 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">仪表盘</h1>
          <p className="text-gray-600 mt-1">查看市场动态和您的投资组合</p>
        </div>
        <Link to="/app/search" className="btn-primary">
          <Search className="w-4 h-4 mr-2" />
          搜索股票
        </Link>
      </div>

      {/* 市场指数 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {marketIndices.map((index) => (
          <div key={index.symbol} className="card">
            <h3 className="text-sm font-medium text-gray-600">{index.name}</h3>
            <div className="mt-2 flex items-baseline">
              <span className="text-2xl font-bold text-gray-900">{index.price.toFixed(2)}</span>
            </div>
            <div className={`mt-1 flex items-center text-sm ${index.change >= 0 ? 'price-up' : 'price-down'}`}>
              {index.change >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
              <span>{index.change > 0 ? '+' : ''}{index.change.toFixed(2)} ({index.changePercent > 0 ? '+' : ''}{index.changePercent.toFixed(2)}%)</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 自选股 */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <Star className="w-5 h-5 mr-2 text-yellow-500" />
              我的自选股
            </h2>
            <Link to="/app/watchlist" className="text-sm text-primary-600 hover:text-primary-500">
              查看全部
            </Link>
          </div>

          {watchlist.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 text-sm font-medium text-gray-600">股票</th>
                    <th className="text-right py-3 text-sm font-medium text-gray-600">最新价</th>
                    <th className="text-right py-3 text-sm font-medium text-gray-600">涨跌</th>
                    <th className="text-right py-3 text-sm font-medium text-gray-600">涨跌幅</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlist.map((stock) => (
                    <tr key={stock.symbol} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3">
                        <Link to={`/app/stock/${stock.symbol}`} className="block">
                          <div className="font-medium text-gray-900">{stock.name}</div>
                          <div className="text-sm text-gray-500">{stock.symbol}</div>
                        </Link>
                      </td>
                      <td className="text-right py-3 font-medium">{stock.price.toFixed(2)}</td>
                      <td className={`text-right py-3 ${stock.change >= 0 ? 'price-up' : 'price-down'}`}>
                        {stock.change > 0 ? '+' : ''}{stock.change.toFixed(2)}
                      </td>
                      <td className={`text-right py-3 ${stock.changePercent >= 0 ? 'price-up' : 'price-down'}`}>
                        {stock.changePercent > 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              暂无自选股，快去搜索添加吧
            </div>
          )}
        </div>

        {/* 热门股票 */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">热门股票</h2>
          <div className="space-y-3">
            {hotStocks.map((stock) => (
              <Link
                key={stock.symbol}
                to={`/app/stock/${stock.symbol}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div>
                  <div className="font-medium text-gray-900">{stock.name}</div>
                  <div className="text-sm text-gray-500">{stock.symbol}</div>
                </div>
                <div className="text-right">
                  <div className="font-medium">{stock.price.toFixed(2)}</div>
                  <div className={`text-sm ${stock.changePercent >= 0 ? 'price-up' : 'price-down'}`}>
                    {stock.changePercent > 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* AI分析记录 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <Sparkles className="w-5 h-5 mr-2 text-primary-500" />
            AI分析记录
          </h2>
          <Link to="/app/analysis" className="text-sm text-primary-600 hover:text-primary-500">
            开始分析
          </Link>
        </div>
        <div className="space-y-4">
          {recentAnalyses.map((analysis) => (
            <div key={analysis.id} className="flex items-start space-x-4 p-4 bg-gray-50 rounded-lg">
              <div className="flex-1">
                <div className="flex items-center space-x-2">
                  <span className="font-medium text-gray-900">{analysis.stock}</span>
                  <span className="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs rounded-full">
                    {analysis.type}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-600">{analysis.summary}</p>
                <span className="mt-2 text-xs text-gray-400">{analysis.date}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

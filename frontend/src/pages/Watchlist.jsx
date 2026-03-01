import { Star, Trash2, Bell } from 'lucide-react'
import { useStockStore } from '../store/stockStore'
import { Link } from 'react-router-dom'

export default function Watchlist() {
  const { watchlist, removeFromWatchlist } = useStockStore()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <Star className="w-6 h-6 mr-2 text-yellow-500" />
            我的自选
          </h1>
          <p className="text-gray-600 mt-1">管理您的关注股票和价格提醒</p>
        </div>
        <Link to="/app/search" className="btn-primary">
          添加股票
        </Link>
      </div>

      {watchlist.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left py-4 px-6 text-sm font-medium text-gray-600">股票</th>
                  <th className="text-right py-4 px-6 text-sm font-medium text-gray-600">最新价</th>
                  <th className="text-right py-4 px-6 text-sm font-medium text-gray-600">涨跌额</th>
                  <th className="text-right py-4 px-6 text-sm font-medium text-gray-600">涨跌幅</th>
                  <th className="text-center py-4 px-6 text-sm font-medium text-gray-600">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {watchlist.map((stock) => (
                  <tr key={stock.symbol} className="hover:bg-gray-50">
                    <td className="py-4 px-6">
                      <Link to={`/app/stock/${stock.symbol}`} className="block">
                        <div className="font-medium text-gray-900">{stock.name}</div>
                        <div className="text-sm text-gray-500">{stock.symbol}</div>
                      </Link>
                    </td>
                    <td className="text-right py-4 px-6 font-medium">{stock.price.toFixed(2)}</td>
                    <td className={`text-right py-4 px-6 ${stock.change >= 0 ? 'price-up' : 'price-down'}`}>
                      {stock.change > 0 ? '+' : ''}{stock.change.toFixed(2)}
                    </td>
                    <td className={`text-right py-4 px-6 ${stock.changePercent >= 0 ? 'price-up' : 'price-down'}`}>
                      {stock.changePercent > 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center justify-center space-x-2">
                        <button
                          className="p-2 text-gray-400 hover:text-primary-600 transition-colors"
                          title="设置提醒"
                        >
                          <Bell className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => removeFromWatchlist(stock.symbol)}
                          className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                          title="移除自选"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card text-center py-16">
          <Star className="w-16 h-16 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无自选股</h3>
          <p className="text-gray-600 mb-6">添加你关注的股票，随时追踪行情变化</p>
          <Link to="/app/search" className="btn-primary">
            去搜索股票
          </Link>
        </div>
      )}
    </div>
  )
}

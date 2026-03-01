import { useParams } from 'react-router-dom'
import { ArrowLeft, Star, TrendingUp, TrendingDown, Newspaper, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useStockStore } from '../store/stockStore'

// 模拟股票详情
const stockDetail = {
  symbol: '600519.SH',
  name: '贵州茅台',
  price: 1689.00,
  change: -5.20,
  changePercent: -0.31,
  market: '上海证券交易所',
  industry: '白酒',
  pe: 28.5,
  pb: 8.2,
  marketCap: '2.12万亿',
  volume: '2.5万手',
  turnover: '42.3亿',
}

const newsData = [
  { id: 1, title: '贵州茅台发布2023年年度报告', date: '2024-03-01', source: '证券时报' },
  { id: 2, title: '白酒板块今日表现活跃，茅台领涨', date: '2024-02-28', source: '新浪财经' },
  { id: 3, title: '机构看好茅台长期投资价值', date: '2024-02-26', source: '中金公司' },
]

export default function StockDetail() {
  const { symbol } = useParams()
  const { watchlist, addToWatchlist, removeFromWatchlist } = useStockStore()
  
  const isWatched = watchlist.some(s => s.symbol === symbol)

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Link to="/app" className="inline-flex items-center text-gray-600 hover:text-gray-900">
        <ArrowLeft className="w-4 h-4 mr-1" />
        返回
      </Link>

      {/* 股票头部信息 */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-3xl font-bold text-gray-900">{stockDetail.name}</h1>
              <span className="text-gray-500">{stockDetail.symbol}</span>
            </div>
            <p className="text-gray-600 mt-1">{stockDetail.market} · {stockDetail.industry}</p>
          </div>
          
          <button
            onClick={() => isWatched ? removeFromWatchlist(symbol) : addToWatchlist(stockDetail)}
            className={`btn ${isWatched ? 'bg-yellow-100 text-yellow-700' : 'btn-secondary'}`}
          >
            <Star className={`w-4 h-4 mr-2 ${isWatched ? 'fill-current' : ''}`} />
            {isWatched ? '已自选' : '加自选'}
          </button>
        </div>

        <div className="mt-6 flex items-baseline space-x-4">
          <span className="text-4xl font-bold">{stockDetail.price.toFixed(2)}</span>
          <div className={`flex items-center text-lg ${stockDetail.change >= 0 ? 'price-up' : 'price-down'}`}>
            {stockDetail.change >= 0 ? <TrendingUp className="w-5 h-5 mr-1" /> : <TrendingDown className="w-5 h-5 mr-1" />}
            <span>{stockDetail.change > 0 ? '+' : ''}{stockDetail.change.toFixed(2)} ({stockDetail.changePercent > 0 ? '+' : ''}{stockDetail.changePercent.toFixed(2)}%)</span>
          </div>
        </div>
      </div>

      {/* 股票数据 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '市盈率(PE)', value: stockDetail.pe },
          { label: '市净率(PB)', value: stockDetail.pb },
          { label: '总市值', value: stockDetail.marketCap },
          { label: '成交量', value: stockDetail.volume },
        ].map((item) => (
          <div key={item.label} className="card">
            <p className="text-sm text-gray-600">{item.label}</p>
            <p className="text-xl font-semibold text-gray-900 mt-1">{item.value}</p>
          </div>
        ))}
      </div>

      {/* 相关新闻 */}
      <div className="card">
        <div className="flex items-center space-x-2 mb-4">
          <Newspaper className="w-5 h-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">相关新闻</h2>
        </div>
        
        <div className="space-y-4">
          {newsData.map((news) => (
            <a
              key={news.id}
              href="#"
              className="block p-4 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <h3 className="font-medium text-gray-900">{news.title}</h3>
              <div className="flex items-center text-sm text-gray-500 mt-2 space-x-3">
                <span>{news.source}</span>
                <span>·</span>
                <span>{news.date}</span>
              </div>
            </a>
          ))}
        </div>
      </div>

      {/* AI分析入口 */}
      <div className="card bg-gradient-to-r from-primary-50 to-primary-100 border-primary-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">AI财报解读</h3>
              <p className="text-sm text-gray-600">获取AI智能分析报告</p>
            </div>
          </div>
          <Link
            to={`/app/analysis?stock=${symbol}`}
            className="btn-primary"
          >
            立即分析
          </Link>
        </div>
      </div>
    </div>
  )
}

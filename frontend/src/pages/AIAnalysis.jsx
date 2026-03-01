import { useState } from 'react'
import { Send, Sparkles, Loader2, FileText, Newspaper } from 'lucide-react'

const analysisTypes = [
  { id: 'filter', name: '智能选股', icon: Sparkles, desc: '基于AI模型筛选优质股票' },
  { id: 'report', name: '财报解读', icon: FileText, desc: '深度分析财务报表' },
  { id: 'news', name: '新闻分析', icon: Newspaper, desc: '分析新闻对股价影响' },
]

export default function AIAnalysis() {
  const [selectedType, setSelectedType] = useState('filter')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleAnalyze = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    // 模拟API调用
    setTimeout(() => {
      setResult({
        type: selectedType,
        content: `基于${selectedType === 'filter' ? '技术指标和基本面' : selectedType === 'report' ? '最新财报数据' : '近期新闻舆情'}分析：\n\n` +
          `1. 整体趋势向好，建议关注中期投资机会\n` +
          `2. 估值处于合理区间，具备一定安全边际\n` +
          `3. 行业景气度较高，政策面支撑明显\n\n` +
          `⚠️ 风险提示：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。`
      })
      setLoading(false)
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center">
          <Sparkles className="w-6 h-6 mr-2 text-primary-500" />
          AI智能分析
        </h1>
        <p className="text-gray-600 mt-1">利用AI大模型进行股票筛选、财报解读和新闻分析</p>
      </div>

      {/* 分析类型选择 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {analysisTypes.map((type) => {
          const Icon = type.icon
          return (
            <button
              key={type.id}
              onClick={() => {
                setSelectedType(type.id)
                setResult(null)
              }}
              className={`card text-left transition-all ${
                selectedType === type.id
                  ? 'ring-2 ring-primary-500 bg-primary-50'
                  : 'hover:shadow-md'
              }`}
            >
              <Icon className={`w-8 h-8 mb-3 ${
                selectedType === type.id ? 'text-primary-600' : 'text-gray-400'
              }`} />
              <h3 className="font-semibold text-gray-900">{type.name}</h3>
              <p className="text-sm text-gray-600 mt-1">{type.desc}</p>
            </button>
          )
        })}
      </div>

      {/* 输入区域 */}
      <div className="card">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {selectedType === 'filter' > '请输入选股条件或描述您想投资的股票类型（如：高分红蓝筹股、新能源成长股等）'
            : selectedType === 'report' > '请输入股票代码或名称进行财报解读'
            : '请输入股票代码或名称分析相关新闻'}
        </label>
        <div className="flex space-x-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              selectedType === 'filter' 
                ? '例如：最近一年ROE>15%，PE<30的消费股'
                : '例如：贵州茅台、000001.SZ'
            }
            className="input flex-1"
          />
          <button
            onClick={handleAnalyze}
            disabled={loading || !query.trim()}
            className="btn-primary whitespace-nowrap disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                分析中
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                开始分析
              </>
            )}
          </button>
        </div>
      </div>

      {/* 分析结果 */}
      {result && (
        <div className="card">
          <div className="flex items-center space-x-2 mb-4">
            <Sparkles className="w-5 h-5 text-primary-500" />
            <h2 className="text-lg font-semibold text-gray-900">分析结果</h2>
          </div>
          <div className="prose max-w-none">
            <pre className="whitespace-pre-wrap text-gray-700 bg-gray-50 p-4 rounded-lg font-sans">
              {result.content}
            </pre>
          </div>
        </div>
      )}

      {/* 使用提示 */}
      <div className="card bg-blue-50 border-blue-200">
        <h3 className="font-medium text-blue-900 mb-2">💡 使用提示</h3>
        <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li>选股筛选支持自然语言描述，如"高分红低估值蓝筹股"</li>
          <li>财报解读会自动获取最新季度报告进行分析</li>
          <li>新闻分析基于最近30天相关资讯</li>
          <li>AI分析仅供参考，不构成投资建议</li>
        </ul>
      </div>
    </div>
  )
}

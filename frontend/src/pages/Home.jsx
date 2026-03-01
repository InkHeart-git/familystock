import { Link } from 'react-router-dom'
import { Sparkles, Users, LineChart, Shield } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-primary-50">
      {/* 导航栏 */}
      <nav className="border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg">F</span>
            </div>
            <span className="text-xl font-bold text-gray-900">FamilyStock</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link 
              to="/login" 
              className="text-gray-600 hover:text-gray-900 font-medium"
            >
              登录
            </Link>
            <Link 
              to="/register" 
              className="btn-primary"
            >
              开始使用
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero区域 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24">
        <div className="text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 tracking-tight">
            家庭智能投资
            <span className="text-primary-600">新体验</span>
          </h1>
          <p className="mt-6 text-xl text-gray-600 max-w-3xl mx-auto">
            AI驱动的股票分析平台，帮助您的家庭做出更明智的投资决策。
            智能筛选、财报解读、家庭共享，让投资更简单。
          </p>
          <div className="mt-10 flex items-center justify-center space-x-4">
            <Link to="/register" className="btn-primary text-lg px-8 py-3">
              免费注册
            </Link>
            <Link to="/login" className="btn-secondary text-lg px-8 py-3">
              已有账号？登录
            </Link>
          </div>
        </div>

        {/* 特性展示 */}
        <div className="mt-24 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {[
            {
              icon: Sparkles,
              title: 'AI智能分析',
              description: '基于大语言模型的股票筛选和财报解读，让数据分析更智能'
            },
            {
              icon: Users,
              title: '家庭共享',
              description: '与家人共享自选股池和投资观点，共同管理家庭资产'
            },
            {
              icon: LineChart,
              title: '实时行情',
              description: '实时股票数据和历史走势分析，把握每一个投资机会'
            },
            {
              icon: Shield,
              title: '安全可靠',
              description: '本地部署，数据安全可控，保护您的投资隐私'
            }
          ].map((feature, index) => (
            <div key={index} className="card text-center hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center mx-auto">
                <feature.icon className="w-6 h-6 text-primary-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">{feature.title}</h3>
              <p className="mt-2 text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 页脚 */}
      <footer className="border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-gray-500">
            © 2024 FamilyStock. 家庭投资好帮手。
          </p>
        </div>
      </footer>
    </div>
  )
}

import { useState } from 'react'
import { User, Mail, Bell, Shield } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

export default function Profile() {
  const { user, updateProfile } = useAuthStore()
  const [name, setName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 500))
    updateProfile({ name, email })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">个人中心</h1>
        <p className="text-gray-600 mt-1">管理您的个人信息和账户设置</p>
      </div>

      {/* 头像区域 */}
      <div className="card">
        <div className="flex items-center space-x-6">
          <div className="w-20 h-20 bg-primary-100 rounded-full flex items-center justify-center">
            <span className="text-primary-700 font-bold text-2xl">{user?.name?.charAt(0) || 'U'}</span>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{user?.name || '用户'}</h2>
            <p className="text-gray-600">{user?.email || 'user@example.com'}</p>
          </div>
        </div>
      </div>

      {/* 基本信息 */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <User className="w-5 h-5 mr-2 text-gray-400" />
          基本信息
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">姓名</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
            />
          </div>

          <div className="pt-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary disabled:opacity-50"
            >
              {saving ? '保存中...' : saved ? '已保存!' : '保存修改'}
            </button>
          </div>
        </div>
      </div>

      {/* 通知设置 */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Bell className="w-5 h-5 mr-2 text-gray-400" />
          通知设置
        </h2>
        
        <div className="space-y-4">
          {[
            { id: 'price_alert', label: '价格提醒', desc: '当股价达到设定价格时通知' },
            { id: 'news_alert', label: '新闻提醒', desc: '自选股相关重要新闻' },
            { id: 'report_alert', label: '财报提醒', desc: '持仓股票财报发布提醒' },
          ].map((item) => (
            <label key={item.id} className="flex items-start">
              <input
                type="checkbox"
                defaultChecked
                className="mt-1 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <div className="ml-3">
                <span className="font-medium text-gray-900">{item.label}</span>
                <p className="text-sm text-gray-600">{item.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* 安全设置 */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Shield className="w-5 h-5 mr-2 text-gray-400" />
          安全设置
        </h2>
        
        <div className="space-y-4">
          <button className="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="font-medium text-gray-900">修改密码</div>
            <div className="text-sm text-gray-600">建议您定期更换密码以保障账户安全</div>
          </button>
          
          <button className="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="font-medium text-gray-900">双重认证</div>
            <div className="text-sm text-gray-600">启用双重认证增加账户安全性</div>
          </button>
        </div>
      </div>
    </div>
  )
}

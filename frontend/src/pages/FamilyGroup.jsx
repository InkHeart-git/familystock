import { Users, UserPlus, Crown, Mail } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

const mockFamilyMembers = [
  { id: 1, name: '张三', role: 'admin', email: 'zhang@example.com', joinedAt: '2024-01-15' },
  { id: 2, name: '李四', role: 'member', email: 'li@example.com', joinedAt: '2024-02-01' },
]

const mockActivity = [
  { id: 1, user: '张三', action: '添加了贵州茅台到家庭自选池', time: '10分钟前' },
  { id: 2, user: '李四', action: '创建了一个新的投资组合', time: '1小时前' },
  { id: 3, user: '张三', action: '更新了价格提醒设置', time: '2小时前' },
]

export default function FamilyGroup() {
  const { user } = useAuthStore()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <Users className="w-6 h-6 mr-2 text-primary-500" />
            家庭投资组
          </h1>
          <p className="text-gray-600 mt-1">与家人共享投资观点，共同管理家庭资产</p>
        </div>
        <button className="btn-primary">
          <UserPlus className="w-4 h-4 mr-2" />
          邀请成员
        </button>
      </div>

      {/* 家庭信息卡片 */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{user?.familyName || '我的家庭'}</h2>
            <p className="text-gray-600 mt-1">创建于 2024年1月 · {mockFamilyMembers.length} 位成员</p>
          </div>
          <div className="flex items-center space-x-2 px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm">
            <Crown className="w-4 h-4" />
            <span>{user?.role === 'admin' ? '管理员' : '成员'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 成员列表 */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">家庭成员</h2>
          <div className="space-y-3">
            {mockFamilyMembers.map((member) => (
              <div key={member.id} className="card py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center">
                      <span className="text-primary-700 font-bold text-lg">{member.name.charAt(0)}</span>
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{member.name}</span>
                        {member.role === 'admin' && (
                          <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                            管理员
                          </span>
                        )}
                      </div>
                      <div className="flex items-center text-sm text-gray-500 mt-1">
                        <Mail className="w-3 h-3 mr-1" />
                        {member.email}
                      </div>
                    </div>
                  </div>
                  <span className="text-sm text-gray-500">
                    加入于 {member.joinedAt}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 最近动态 */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">最近动态</h2>
          <div className="card space-y-4">
            {mockActivity.map((activity) => (
              <div key={activity.id} className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-medium text-gray-600">{activity.user.charAt(0)}</span>
                </div>
                <div>
                  <p className="text-sm text-gray-900">
                    <span className="font-medium">{activity.user}</span>{' '}
                    {activity.action}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

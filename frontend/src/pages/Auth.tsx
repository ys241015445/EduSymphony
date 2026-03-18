import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { BookOpen, ArrowLeft } from 'lucide-react'

export default function Auth() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, register } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(username, email, password)
      }
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || '操作失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-brand-600 text-white flex-col justify-between p-12">
        <div>
          <Link to="/" className="flex items-center gap-2 text-white/90 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">返回首页</span>
          </Link>
        </div>
        <div>
          <BookOpen className="w-12 h-12 mb-6 text-white/80" />
          <h2 className="text-3xl font-bold mb-4">多智能体协作<br />教案生成平台</h2>
          <p className="text-white/70 leading-relaxed max-w-md">
            5位AI教学专家为您的教案出谋划策——课程设计、学科知识、教学方法、评估反馈、技术整合，
            全方位打磨每一个教学环节。
          </p>
        </div>
        <div className="text-white/40 text-sm">
          &copy; {new Date().getFullYear()} EduSymphony
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Link to="/" className="flex items-center gap-2 text-gray-500 hover:text-gray-700 text-sm mb-6">
              <ArrowLeft className="w-4 h-4" />
              返回首页
            </Link>
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {mode === 'login' ? '欢迎回来' : '创建账号'}
          </h1>
          <p className="text-gray-500 text-sm mb-8">
            {mode === 'login' ? '登录以继续使用 EduSymphony' : '注册以开始使用 EduSymphony'}
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <Input
                label="用户名"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            )}
            <Input
              label="邮箱"
              type="email"
              placeholder="请输入邮箱地址"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="密码"
              type="password"
              placeholder="请输入密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? '处理中...' : mode === 'login' ? '登录' : '注册'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-500">
            {mode === 'login' ? (
              <>
                还没有账号？{' '}
                <button onClick={() => setMode('register')} className="text-brand-600 hover:underline font-medium">
                  立即注册
                </button>
              </>
            ) : (
              <>
                已有账号？{' '}
                <button onClick={() => setMode('login')} className="text-brand-600 hover:underline font-medium">
                  去登录
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

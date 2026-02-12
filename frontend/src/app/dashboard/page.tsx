'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, FileText, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'
import { apiClient } from '@/services/api'
import Link from 'next/link'

interface Lesson {
  id: string
  title: string
  subject: string
  grade_level: string
  status: string
  progress: number
  created_at: string
}

export default function DashboardPage() {
  const router = useRouter()
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [userData, lessonsData] = await Promise.all([
        apiClient.getCurrentUser(),
        apiClient.getLessons({ limit: 20 }),
      ])
      setUser(userData)
      setLessons(lessonsData)
    } catch (err) {
      console.error('Failed to load data:', err)
      router.push('/login')
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'processing':
        return <Loader className="h-5 w-5 text-blue-500 animate-spin" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <Clock className="h-5 w-5 text-gray-400" />
    }
  }

  const getStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      draft: '草稿',
      queued: '排队中',
      processing: '生成中',
      completed: '已完成',
      failed: '失败',
    }
    return statusMap[status] || status
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">我的教案</h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                配额剩余: <span className="font-semibold">{user?.quota_remaining || 0}</span>
              </span>
              <Link
                href="/dashboard/create"
                className="inline-flex items-center bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
              >
                <Plus className="h-5 w-5 mr-2" />
                创建教案
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {lessons.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <FileText className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">还没有教案</h2>
            <p className="text-gray-600 mb-6">创建您的第一个教案，体验AI协作的魅力</p>
            <Link
              href="/dashboard/create"
              className="inline-flex items-center bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition"
            >
              <Plus className="h-5 w-5 mr-2" />
              创建教案
            </Link>
          </div>
        ) : (
          <div className="grid gap-4">
            {lessons.map((lesson) => (
              <Link
                key={lesson.id}
                href={`/dashboard/lesson/${lesson.id}`}
                className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition cursor-pointer"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      {getStatusIcon(lesson.status)}
                      <h3 className="text-lg font-semibold text-gray-900">{lesson.title}</h3>
                      <span className="text-sm text-gray-500">{getStatusText(lesson.status)}</span>
                    </div>
                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                      <span>学科: {lesson.subject}</span>
                      <span>年级: {lesson.grade_level}</span>
                      <span>{new Date(lesson.created_at).toLocaleDateString('zh-CN')}</span>
                    </div>
                    {lesson.status === 'processing' && (
                      <div className="mt-3">
                        <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
                          <span>进度</span>
                          <span>{lesson.progress}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all"
                            style={{ width: `${lesson.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}


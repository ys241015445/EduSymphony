import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useLessonStore, LessonSummary } from '../stores/lessonStore'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Plus, FileText, Clock, CheckCircle2, AlertCircle, Loader2, Trash2, Zap } from 'lucide-react'

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  queued: { label: '排队中', color: 'text-yellow-600 bg-yellow-50', icon: Clock },
  processing: { label: '生成中', color: 'text-blue-600 bg-blue-50', icon: Loader2 },
  completed: { label: '已完成', color: 'text-green-600 bg-green-50', icon: CheckCircle2 },
  failed: { label: '失败', color: 'text-red-600 bg-red-50', icon: AlertCircle },
  draft: { label: '草稿', color: 'text-gray-600 bg-gray-50', icon: FileText },
}

function LessonCard({ lesson }: { lesson: LessonSummary }) {
  const { deleteLesson, fetchLessons } = useLessonStore()
  const navigate = useNavigate()
  const cfg = statusConfig[lesson.status] || statusConfig.draft
  const Icon = cfg.icon

  const handleClick = () => {
    if (lesson.status === 'completed') {
      navigate(`/lesson/${lesson.id}/result`)
    } else if (lesson.status === 'processing' || lesson.status === 'queued') {
      navigate(`/lesson/${lesson.id}/process`)
    }
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (window.confirm('确定要删除这份教案吗？')) {
      await deleteLesson(lesson.id)
      fetchLessons()
    }
  }

  return (
    <Card className="cursor-pointer hover:shadow-md hover:border-brand-200 transition-all duration-200 group" padding={false}>
      <div onClick={handleClick} className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
            <Icon className="w-3.5 h-3.5" />
            {cfg.label}
          </div>
          <button
            onClick={handleDelete}
            className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 transition-all"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
        <h3 className="font-semibold text-gray-900 mb-1 truncate">{lesson.title}</h3>
        <p className="text-sm text-gray-500">
          {lesson.subject} · {lesson.grade_level}
        </p>
        {lesson.status === 'processing' && (
          <div className="mt-3">
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-500"
                style={{ width: `${lesson.progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">{lesson.progress}%</p>
          </div>
        )}
        {lesson.created_at && (
          <p className="text-xs text-gray-400 mt-3">
            {new Date(lesson.created_at).toLocaleDateString('zh-CN')}
          </p>
        )}
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { lessons, loading, fetchLessons } = useLessonStore()

  useEffect(() => {
    fetchLessons()
  }, [fetchLessons])

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">我的教案</h1>
            <p className="text-sm text-gray-500 mt-1">管理和查看您生成的所有教案</p>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/quick-generate">
              <Button variant="secondary" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                <Zap className="w-4 h-4 mr-1.5" />
                快速生成
              </Button>
            </Link>
            <Link to="/lesson/new">
              <Button>
                <Plus className="w-4 h-4 mr-1.5" />
                新建教案
              </Button>
            </Link>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto" />
            <p className="mt-3 text-gray-500 text-sm">加载中...</p>
          </div>
        ) : lessons.length === 0 ? (
          <div className="text-center py-20">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-600 mb-2">还没有教案</h3>
            <p className="text-sm text-gray-400 mb-6">创建您的第一份AI协作教案</p>
            <div className="flex items-center justify-center gap-3">
              <Link to="/quick-generate">
                <Button variant="secondary" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                  <Zap className="w-4 h-4 mr-1.5" />
                  快速生成
                </Button>
              </Link>
              <Link to="/lesson/new">
                <Button>
                  <Plus className="w-4 h-4 mr-1.5" />
                  新建教案
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {lessons.map((l) => (
              <LessonCard key={l.id} lesson={l} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

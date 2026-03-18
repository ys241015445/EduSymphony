import { BookOpen } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="bg-gray-50 border-t border-gray-100">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="flex flex-col md:flex-row justify-between items-start gap-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="w-5 h-5 text-brand-600" />
              <span className="font-semibold text-gray-900">EduSymphony</span>
            </div>
            <p className="text-sm text-gray-500 max-w-xs">
              多智能体协作教案生成平台，让每一份教案都经过专业打磨。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-12 text-sm">
            <div>
              <h4 className="font-medium text-gray-900 mb-3">产品</h4>
              <ul className="space-y-2 text-gray-500">
                <li>教案生成</li>
                <li>格式转换</li>
                <li>多模型支持</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-3">支持</h4>
              <ul className="space-y-2 text-gray-500">
                <li>使用文档</li>
                <li>常见问题</li>
                <li>联系我们</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-gray-200 text-center text-xs text-gray-400">
          &copy; {new Date().getFullYear()} EduSymphony. All rights reserved.
        </div>
      </div>
    </footer>
  )
}

import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BookOpen, Users, Zap, Shield, FileText, ArrowRight, CheckCircle2 } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'
import Button from '../components/ui/Button'

const features = [
  {
    icon: Users,
    title: '多专家协作',
    desc: '5位AI教学专家从不同维度分析教案，通过讨论投票产出最优方案。',
  },
  {
    icon: Zap,
    title: '多种教学模型',
    desc: '支持5E、BOPPPS、PBL等主流教学模型，适配不同学科与年级。',
  },
  {
    icon: Shield,
    title: '数据本地存储',
    desc: '所有教案数据存储在您的本地服务器，完全掌控隐私与安全。',
  },
  {
    icon: FileText,
    title: '多格式导出',
    desc: '一键导出为Word、PDF、Markdown、TXT等格式，满足多场景需求。',
  },
]

const steps = [
  { num: '01', title: '上传或输入教案素材', desc: '支持文字输入、Word、PDF等多种格式上传。' },
  { num: '02', title: '选择教学模型与参数', desc: '选择5E/BOPPPS/PBL模型，配置学科、年级、地区等信息。' },
  { num: '03', title: 'AI多专家协作生成', desc: '5位专家独立分析 → 讨论投票 → 融合优化，全程可视化。' },
  { num: '04', title: '审阅、批注、导出', desc: '查看生成结果，添加批注，选择重新生成，最终导出使用。' },
]

const fade = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5 },
  }),
}

export default function Landing() {
  const isLoggedIn = useAuthStore((s) => !!s.token)
  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-50 via-white to-white" />
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-20 lg:pt-32 lg:pb-28">
          <div className="max-w-3xl">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="text-4xl lg:text-5xl font-bold text-gray-900 leading-tight tracking-tight"
            >
              让每一份教案
              <br />
              <span className="text-brand-600">都经过专业打磨</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              className="mt-6 text-lg text-gray-500 max-w-xl leading-relaxed"
            >
              EduSymphony 通过多智能体协作，模拟真实教研团队的讨论与评审流程，
              帮助教师高效产出结构化、高质量的教案。
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-8 flex flex-wrap gap-4"
            >
              <Link to="/login">
                <Button size="lg">
                  免费开始使用
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
              <a href="#features">
                <Button variant="secondary" size="lg">了解更多</Button>
              </a>
              {isLoggedIn && (
                <Link to="/quick-generate">
                  <Button variant="secondary" size="lg" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                    <Zap className="w-4 h-4 mr-1.5" />
                    快速生成
                  </Button>
                </Link>
              )}
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-16 rounded-2xl border border-gray-200 bg-white shadow-xl overflow-hidden"
          >
            <div className="bg-gray-800 px-4 py-2.5 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-400" />
              <div className="w-3 h-3 rounded-full bg-yellow-400" />
              <div className="w-3 h-3 rounded-full bg-green-400" />
              <span className="ml-3 text-xs text-gray-400">EduSymphony — 教案生成中</span>
            </div>
            <div className="p-8 grid grid-cols-2 gap-6 min-h-[280px]">
              <div>
                <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">教案内容</div>
                <div className="space-y-3">
                  {['引入 (Engage)', '探索 (Explore)', '解释 (Explain)', '拓展 (Extend)', '评价 (Evaluate)'].map((s, i) => (
                    <div key={s} className="flex items-center gap-2.5">
                      <CheckCircle2 className={`w-4 h-4 ${i < 3 ? 'text-brand-500' : 'text-gray-300'}`} />
                      <span className={`text-sm ${i < 3 ? 'text-gray-900' : 'text-gray-400'}`}>{s}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">AI 讨论过程</div>
                <div className="space-y-2.5">
                  {[
                    { role: '课程设计专家', msg: '建议在引入环节加入情境问题…' },
                    { role: '学科专家', msg: '内容需要与课标紧密关联…' },
                    { role: '教学法专家', msg: '同意，但建议增加互动环节…' },
                  ].map((d) => (
                    <div key={d.role} className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs font-medium text-brand-700">{d.role}</div>
                      <div className="text-xs text-gray-500 mt-1">{d.msg}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900">为什么选择 EduSymphony</h2>
            <p className="mt-3 text-gray-500">AI驱动的多专家协作，让教案设计更专业、更高效</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fade}
                className="p-6 rounded-xl border border-gray-100 hover:border-brand-200 hover:shadow-md transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center mb-4">
                  <f.icon className="w-5 h-5 text-brand-600" />
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900">如何使用</h2>
            <p className="mt-3 text-gray-500">简单四步，生成专业教案</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {steps.map((s, i) => (
              <motion.div
                key={s.num}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={fade}
              >
                <div className="text-4xl font-bold text-brand-200 mb-3">{s.num}</div>
                <h3 className="font-semibold text-gray-900 mb-2">{s.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-white">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">准备好提升你的教案质量了吗？</h2>
          <p className="text-gray-500 mb-8">注册即可免费体验，无需绑定支付方式。</p>
          <Link to="/login">
            <Button size="lg">
              立即开始
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}

import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Users, Zap, Shield, FileText, ArrowRight, CheckCircle2 } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useT } from '../i18n/translations'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'
import Button from '../components/ui/Button'

const fade = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5 },
  }),
}

export default function Landing() {
  const t = useT()
  const isLoggedIn = useAuthStore((s) => !!s.token)

  const features = [
    {
      icon: Users,
      title: t('landing.feat1_title'),
      desc: t('landing.feat1_desc'),
    },
    {
      icon: Zap,
      title: t('landing.feat2_title'),
      desc: t('landing.feat2_desc'),
    },
    {
      icon: Shield,
      title: t('landing.feat3_title'),
      desc: t('landing.feat3_desc'),
    },
    {
      icon: FileText,
      title: t('landing.feat4_title'),
      desc: t('landing.feat4_desc'),
    },
  ]

  const steps = [
    { num: '01', title: t('landing.step1_title'), desc: t('landing.step1_desc') },
    { num: '02', title: t('landing.step2_title'), desc: t('landing.step2_desc') },
    { num: '03', title: t('landing.step3_title'), desc: t('landing.step3_desc') },
    { num: '04', title: t('landing.step4_title'), desc: t('landing.step4_desc') },
  ]

  const demoDiscussion = [
    { role: t('landing.demo_role1'), msg: t('landing.demo_msg1') },
    { role: t('landing.demo_role2'), msg: t('landing.demo_msg2') },
    { role: t('landing.demo_role3'), msg: t('landing.demo_msg3') },
  ]

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
              {t('landing.hero_line1')}
              <br />
              <span className="text-brand-600">{t('landing.hero_line2')}</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              className="mt-6 text-lg text-gray-500 max-w-xl leading-relaxed"
            >
              {t('landing.hero_desc')}
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-8 flex flex-wrap gap-4"
            >
              <Link to="/login">
                <Button size="lg">
                  {t('landing.cta_start')}
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
              <a href="#features">
                <Button variant="secondary" size="lg">{t('landing.cta_learn')}</Button>
              </a>
              {isLoggedIn && (
                <Link to="/quick-generate">
                  <Button variant="secondary" size="lg" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                    <Zap className="w-4 h-4 mr-1.5" />
                    {t('landing.cta_quick')}
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
              <span className="ml-3 text-xs text-gray-400">{t('landing.demo_bar')}</span>
            </div>
            <div className="p-8 grid grid-cols-2 gap-6 min-h-[280px]">
              <div>
                <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">{t('landing.demo_content')}</div>
                <div className="space-y-3">
                  {(['landing.demo_s1', 'landing.demo_s2', 'landing.demo_s3', 'landing.demo_s4', 'landing.demo_s5'] as const).map((key, i) => (
                    <div key={key} className="flex items-center gap-2.5">
                      <CheckCircle2 className={`w-4 h-4 ${i < 3 ? 'text-brand-500' : 'text-gray-300'}`} />
                      <span className={`text-sm ${i < 3 ? 'text-gray-900' : 'text-gray-400'}`}>{t(key)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">{t('landing.demo_discussion')}</div>
                <div className="space-y-2.5">
                  {demoDiscussion.map((d) => (
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
            <h2 className="text-3xl font-bold text-gray-900">{t('landing.feat_title')}</h2>
            <p className="mt-3 text-gray-500">{t('landing.feat_subtitle')}</p>
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
            <h2 className="text-3xl font-bold text-gray-900">{t('landing.how_title')}</h2>
            <p className="mt-3 text-gray-500">{t('landing.how_subtitle')}</p>
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
          <h2 className="text-3xl font-bold text-gray-900 mb-4">{t('landing.cta_title')}</h2>
          <p className="text-gray-500 mb-8">{t('landing.cta_subtitle')}</p>
          <Link to="/login">
            <Button size="lg">
              {t('landing.cta_button')}
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}

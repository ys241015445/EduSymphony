import { BookOpen } from 'lucide-react'
import { useT } from '../../i18n/translations'

export default function Footer() {
  const t = useT()
  return (
    <footer className="bg-gray-50 border-t border-gray-100">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="flex flex-col md:flex-row justify-between items-start gap-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="w-5 h-5 text-brand-600" />
              <span className="font-semibold text-gray-900">{t('footer.brand')}</span>
            </div>
            <p className="text-sm text-gray-500 max-w-xs">
              {t('footer.desc')}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-12 text-sm">
            <div>
              <h4 className="font-medium text-gray-900 mb-3">{t('footer.product')}</h4>
              <ul className="space-y-2 text-gray-500">
                <li>{t('footer.product_gen')}</li>
                <li>{t('footer.product_convert')}</li>
                <li>{t('footer.product_models')}</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-3">{t('footer.support')}</h4>
              <ul className="space-y-2 text-gray-500">
                <li>{t('footer.support_docs')}</li>
                <li>{t('footer.support_faq')}</li>
                <li>{t('footer.support_contact')}</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-gray-200 text-center text-xs text-gray-400">
          {t('footer.copyright').replace('{year}', String(new Date().getFullYear()))}
        </div>
      </div>
    </footer>
  )
}

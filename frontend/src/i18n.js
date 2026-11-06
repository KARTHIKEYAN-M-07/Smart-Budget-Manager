import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Base English translations (extensible to Tamil 'ta' in later phases)
const resources = {
  en: {
    translation: {
      appName: 'Smart Family Budget Manager',
      tagline: 'Private, secure and financially accurate household management',
      status: {
        online: 'System Online',
        connecting: 'Connecting...',
        healthy: 'All systems operational',
      },
      nav: {
        dashboard: 'Dashboard',
        accounts: 'Accounts',
        transactions: 'Transactions',
        budgets: 'Budgets',
        reports: 'Reports',
        settings: 'Settings',
      },
      currencySymbol: '₹',
    },
  },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'en',
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes XSS
    },
  });

export default i18n;

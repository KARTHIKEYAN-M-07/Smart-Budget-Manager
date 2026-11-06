import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldCheck, Database, RefreshCw } from 'lucide-react';
import axios from 'axios';

function App() {
  const { t } = useTranslation();
  const [health, setHealth] = useState({ status: 'checking', database: 'checking' });
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/v1/health');
      setHealth(res.data);
    } catch (err) {
      setHealth({
        status: 'unreachable',
        database: 'disconnected',
        error: err.response?.data?.error || 'Backend service unreachable',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-green-600 text-white p-2 rounded-lg font-bold text-lg">
              ₹
            </div>
            <div>
              <h1 className="font-bold text-lg text-slate-900">{t('appName')}</h1>
              <p className="text-xs text-slate-500">{t('tagline')}</p>
            </div>
          </div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            India (INR / Asia/Kolkata)
          </span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-12 flex-1 w-full">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-2">Development Environment Initialized</h2>
          <p className="text-slate-600 mb-6">
            Module 1 is successfully structured with React + Vite, FastAPI, and Docker configurations.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <div className="border border-slate-200 rounded-lg p-4 flex items-start space-x-3 bg-slate-50">
              <ShieldCheck className="w-6 h-6 text-green-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-slate-800">Backend API Status</h3>
                <p className="text-sm text-slate-600 capitalize">
                  {loading ? 'Checking...' : health.status}
                </p>
              </div>
            </div>

            <div className="border border-slate-200 rounded-lg p-4 flex items-start space-x-3 bg-slate-50">
              <Database className="w-6 h-6 text-green-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-slate-800">Database Connection</h3>
                <p className="text-sm text-slate-600 capitalize">
                  {loading ? 'Checking...' : health.database}
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={fetchHealth}
            disabled={loading}
            className="inline-flex items-center space-x-2 px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition disabled:opacity-50 text-sm font-medium"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Check Health</span>
          </button>
        </div>
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        Smart Family Budget Manager &copy; {new Date().getFullYear()} &bull; Built with Privacy & Financial Accuracy
      </footer>
    </div>
  );
}

export default App;

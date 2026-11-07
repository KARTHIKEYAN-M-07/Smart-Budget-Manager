import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  PieChart as PieChartIcon,
  BarChart3,
  Calendar,
  Percent,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export default function Dashboard() {
  const { household, user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [fyData, setFyData] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [overviewRes, fyRes, txnRes] = await Promise.all([
        api.get('/analytics/overview'),
        api.get('/analytics/financial-year'),
        api.get('/transactions', { params: { limit: 5 } }),
      ]);
      setOverview(overviewRes.data);
      setFyData(fyRes.data);
      setRecentTransactions(txnRes.data.items);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
    const handleUpdate = () => loadDashboardData();
    window.addEventListener('sfbm_data_updated', handleUpdate);
    return () => window.removeEventListener('sfbm_data_updated', handleUpdate);
  }, []);

  const COLORS = ['#10b981', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#64748b'];

  const categoryChartData = overview?.categories?.map((c, i) => ({
    name: c.category_name,
    value: parseFloat(c.total_amount) || 0,
    color: c.category_color || COLORS[i % COLORS.length],
  })) || [];

  const trendChartData = fyData?.monthly_trends?.map((m) => ({
    month: m.month_name.split(' ')[0], // e.g. "Apr"
    Income: parseFloat(m.total_income) || 0,
    Expense: parseFloat(m.total_expense) || 0,
  })) || [];

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-3xl p-6 md:p-8 text-white shadow-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
        <div>
          <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">
            <ShieldCheck className="w-4 h-4" />
            <span>Encrypted Family Ledger</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
            Welcome, {user?.full_name}
          </h1>
          <p className="text-xs md:text-sm text-slate-300 mt-1">
            Managing finances for <span className="text-white font-semibold">{household?.name}</span> (INR &bull; {fyData?.financial_year || 'Current FY'})
          </p>
        </div>

        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10 text-right">
          <span className="text-[11px] text-slate-300 block uppercase font-medium tracking-wider">
            Net Monthly Savings
          </span>
          <span className="text-2xl md:text-3xl font-extrabold font-mono text-emerald-400 block mt-0.5">
            {formatINR(overview?.net_savings || 0)}
          </span>
          <span className="text-[10px] text-slate-400">
            Savings Rate: {overview?.savings_rate || '0.00'}%
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {/* Total Income */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Income</p>
            <h3 className="text-xl font-bold font-mono text-emerald-600 mt-1">
              {formatINR(overview?.total_income || 0)}
            </h3>
            <span className="text-[10px] text-slate-400">This Month</span>
          </div>
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-2xl">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        {/* Net Expenses */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Net Expense</p>
            <h3 className="text-xl font-bold font-mono text-slate-900 mt-1">
              {formatINR(overview?.total_expense || 0)}
            </h3>
            <span className="text-[10px] text-slate-400">Net of ₹{overview?.total_refunds || '0.00'} refunds</span>
          </div>
          <div className="p-3 bg-red-50 text-red-600 rounded-2xl">
            <TrendingDown className="w-5 h-5" />
          </div>
        </div>

        {/* Savings Rate */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Savings Rate</p>
            <h3 className="text-xl font-bold font-mono text-indigo-600 mt-1">
              {overview?.savings_rate || '0.00'}%
            </h3>
            <span className="text-[10px] text-slate-400">Of monthly earnings</span>
          </div>
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-2xl">
            <Percent className="w-5 h-5" />
          </div>
        </div>

        {/* Financial Year Net */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{fyData?.financial_year || 'FY'}</p>
            <h3 className="text-xl font-bold font-mono text-slate-900 mt-1">
              {formatINR(fyData?.net_savings || 0)}
            </h3>
            <span className="text-[10px] text-slate-400">Full year net savings</span>
          </div>
          <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl">
            <Calendar className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Visual Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Cash Flow Trend (Bar Chart) */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-5 h-5 text-emerald-600" />
              <h3 className="text-sm font-bold text-slate-800">
                Indian Financial Year Cash Flow ({fyData?.financial_year})
              </h3>
            </div>
            <span className="text-[11px] text-slate-400 font-medium">April to March</span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trendChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(val) => `₹${val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val}`}
                />
                <Tooltip
                  formatter={(value) => [formatINR(value), '']}
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderRadius: '8px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Bar dataKey="Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Expense" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Expense Breakdown (Donut Chart) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center space-x-2 mb-4">
            <PieChartIcon className="w-5 h-5 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-800">Expense Breakdown</h3>
          </div>

          {categoryChartData.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-xs text-slate-400">
              No expense categories recorded yet
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {categoryChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => [formatINR(value), 'Amount']}
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-1 max-h-24 overflow-y-auto">
                {categoryChartData.map((cat, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px] text-slate-600">
                    <div className="flex items-center space-x-1.5 truncate">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: cat.color }} />
                      <span className="truncate">{cat.name}</span>
                    </div>
                    <span className="font-mono font-semibold">{formatINR(cat.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 className="text-sm font-bold text-slate-800">Recent Ledger Activity</h3>
          <Link
            to="/transactions"
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center space-x-1"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-2">
            <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin" />
            <p className="text-xs text-slate-500">Loading recent entries...</p>
          </div>
        ) : recentTransactions.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No transactions recorded yet. Use the "+ Add" button to record expenses or transfers.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {recentTransactions.map((txn) => {
              const isInflow = txn.direction === 'INFLOW';
              const isVoided = txn.status === 'VOIDED';

              return (
                <div
                  key={txn.id}
                  className="px-6 py-3.5 flex items-center justify-between hover:bg-slate-50/60 transition"
                >
                  <div>
                    <p
                      className={`text-xs font-semibold text-slate-900 ${
                        isVoided ? 'line-through text-slate-400' : ''
                      }`}
                    >
                      {txn.description || txn.transaction_type.replace('_', ' ')}
                    </p>
                    <span className="text-[11px] text-slate-400">
                      {formatISTDate(txn.transaction_date)} &bull; {txn.transaction_type}
                    </span>
                  </div>
                  <span
                    className={`font-mono text-xs font-bold ${
                      isVoided
                        ? 'line-through text-slate-400'
                        : isInflow
                        ? 'text-emerald-600'
                        : 'text-slate-900'
                    }`}
                  >
                    {isInflow ? '+' : '-'}
                    {formatINR(txn.amount)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

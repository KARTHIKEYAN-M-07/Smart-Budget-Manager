import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';
import {
  PieChart,
  Target,
  Plus,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  X,
  Trash2,
  Calendar,
  AlertCircle,
} from 'lucide-react';

export default function Budgets() {
  const [tab, setTab] = useState('budgets'); // 'budgets' or 'goals'
  const [budgets, setBudgets] = useState([]);
  const [goals, setGoals] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Current month state (YYYY-MM)
  const now = new Date();
  const currentMonthStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const [selectedMonth, setSelectedMonth] = useState(currentMonthStr);

  // Modals state
  const [budgetModalOpen, setBudgetModalOpen] = useState(false);
  const [goalModalOpen, setGoalModalOpen] = useState(false);
  const [updateGoalModalOpen, setUpdateGoalModalOpen] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState(null);

  // Budget form state
  const [categoryId, setCategoryId] = useState('');
  const [budgetAmount, setBudgetAmount] = useState('');
  const [submittingBudget, setSubmittingBudget] = useState(false);

  // Goal form state
  const [goalName, setGoalName] = useState('');
  const [goalTarget, setGoalTarget] = useState('');
  const [goalCurrent, setGoalCurrent] = useState('');
  const [goalDate, setGoalDate] = useState('');
  const [submittingGoal, setSubmittingGoal] = useState(false);

  // Update Goal form state
  const [addFundsAmount, setAddFundsAmount] = useState('');
  const [updatingGoal, setUpdatingGoal] = useState(false);

  const fetchCategories = async () => {
    try {
      const res = await api.get('/categories');
      setCategories(res.data.filter((c) => c.type === 'expense'));
    } catch (err) {
      console.error('Failed to load categories', err);
    }
  };

  const fetchBudgets = async () => {
    try {
      const res = await api.get('/budgets', { params: { month: selectedMonth } });
      setBudgets(res.data);
    } catch (err) {
      setError(err.message || 'Failed to load budgets');
    }
  };

  const fetchGoals = async () => {
    try {
      const res = await api.get('/budgets/goals');
      setGoals(res.data);
    } catch (err) {
      setError(err.message || 'Failed to load savings goals');
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      await Promise.all([fetchCategories(), fetchBudgets(), fetchGoals()]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const handleUpdate = () => {
      fetchBudgets();
      fetchGoals();
    };
    window.addEventListener('sfbm_data_updated', handleUpdate);
    return () => window.removeEventListener('sfbm_data_updated', handleUpdate);
  }, [selectedMonth]);

  const handleCreateBudget = async (e) => {
    e.preventDefault();
    setSubmittingBudget(true);
    setError('');
    try {
      await api.post('/budgets', {
        category_id: categoryId || null,
        month: selectedMonth,
        amount: parseFloat(budgetAmount).toFixed(2),
      });
      setBudgetModalOpen(false);
      setBudgetAmount('');
      setCategoryId('');
      fetchBudgets();
    } catch (err) {
      setError(err.message || 'Failed to set budget');
    } finally {
      setSubmittingBudget(false);
    }
  };

  const handleDeleteBudget = async (id) => {
    if (!confirm('Are you sure you want to remove this budget limit?')) return;
    try {
      await api.delete(`/budgets/${id}`);
      fetchBudgets();
    } catch (err) {
      alert(err.message || 'Failed to delete budget');
    }
  };

  const handleCreateGoal = async (e) => {
    e.preventDefault();
    setSubmittingGoal(true);
    setError('');
    try {
      await api.post('/budgets/goals', {
        name: goalName.trim(),
        target_amount: parseFloat(goalTarget).toFixed(2),
        current_amount: goalCurrent ? parseFloat(goalCurrent).toFixed(2) : '0.00',
        target_date: goalDate || null,
      });
      setGoalModalOpen(false);
      setGoalName('');
      setGoalTarget('');
      setGoalCurrent('');
      setGoalDate('');
      fetchGoals();
    } catch (err) {
      setError(err.message || 'Failed to create savings goal');
    } finally {
      setSubmittingGoal(false);
    }
  };

  const handleAddFundsToGoal = async (e) => {
    e.preventDefault();
    if (!selectedGoal) return;
    setUpdatingGoal(true);
    try {
      const newTotal = (parseFloat(selectedGoal.current_amount) + parseFloat(addFundsAmount)).toFixed(2);
      await api.patch(`/budgets/goals/${selectedGoal.id}`, {
        current_amount: newTotal,
        version: selectedGoal.version,
      });
      setUpdateGoalModalOpen(false);
      setSelectedGoal(null);
      setAddFundsAmount('');
      fetchGoals();
    } catch (err) {
      alert(err.message || 'Failed to update goal');
    } finally {
      setUpdatingGoal(false);
    }
  };

  const getThresholdColor = (threshold) => {
    switch (threshold) {
      case 'EXCEEDED_100':
        return { bar: 'bg-red-500', badge: 'bg-red-100 text-red-800 border-red-200' };
      case 'WARNING_90':
        return { bar: 'bg-amber-500', badge: 'bg-amber-100 text-amber-800 border-amber-200' };
      case 'WARNING_75':
        return { bar: 'bg-yellow-500', badge: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
      default:
        return { bar: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200' };
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Budgets & Savings Goals</h1>
          <p className="text-xs text-slate-500">
            Real-time monthly expense limits &bull; 75%, 90%, 100% threshold alerts &bull; Family goals
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {tab === 'budgets' ? (
            <>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="px-3 py-1.5 text-xs font-semibold bg-white border border-slate-200 rounded-lg text-slate-700 shadow-sm focus:outline-none"
              />
              <button
                onClick={() => setBudgetModalOpen(true)}
                className="flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Set Budget</span>
              </button>
            </>
          ) : (
            <button
              onClick={() => setGoalModalOpen(true)}
              className="flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Savings Goal</span>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-white rounded-xl p-1 shadow-sm max-w-sm">
        <button
          onClick={() => setTab('budgets')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg transition ${
            tab === 'budgets'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Category Budgets ({budgets.length})
        </button>
        <button
          onClick={() => setTab('goals')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg transition ${
            tab === 'goals'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Savings Goals ({goals.length})
        </button>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-center space-x-2 text-red-700 text-sm font-medium">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-8 h-8 text-emerald-600 animate-spin" />
          <p className="text-xs text-slate-500">Calculating real-time budget consumption...</p>
        </div>
      ) : tab === 'budgets' ? (
        /* Budgets Grid */
        budgets.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-12 text-center">
            <PieChart className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-sm font-bold text-slate-800">No Budgets Set for {selectedMonth}</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
              Set spending limits for groceries, rent, dining, or household utilities to prevent overspending.
            </p>
            <button
              onClick={() => setBudgetModalOpen(true)}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-500 transition"
            >
              Set First Budget
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {budgets.map((b) => {
              const colors = getThresholdColor(b.alert_threshold);
              const pctNum = Math.min(parseFloat(b.percentage_used) || 0, 100);

              return (
                <div
                  key={b.id}
                  className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm space-y-4 hover:shadow-md transition"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-bold text-sm text-slate-900">{b.category_name}</h4>
                      <span className="text-[11px] text-slate-400">{b.month}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${colors.badge}`}
                      >
                        {b.alert_threshold.replace('_', ' ')}
                      </span>
                      <button
                        onClick={() => handleDeleteBudget(b.id)}
                        className="p-1 text-slate-400 hover:text-red-600 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-slate-900 font-mono">{formatINR(b.current_spend)}</span>
                      <span className="text-slate-400 font-mono">Limit: {formatINR(b.amount)}</span>
                    </div>
                    <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${colors.bar} transition-all duration-500`}
                        style={{ width: `${pctNum}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>{b.percentage_used}% used</span>
                      <span>Remaining: {formatINR(b.remaining_amount)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* Savings Goals Grid */
        goals.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-12 text-center">
            <Target className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-sm font-bold text-slate-800">No Savings Goals Defined</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
              Track targets for emergency funds, sovereign gold bonds, home down payment, or education.
            </p>
            <button
              onClick={() => setGoalModalOpen(true)}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-500 transition"
            >
              Create First Goal
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {goals.map((g) => {
              const isAchieved = g.status === 'ACHIEVED';
              const pctNum = Math.min(parseFloat(g.percentage_achieved) || 0, 100);

              return (
                <div
                  key={g.id}
                  className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm space-y-4 hover:shadow-md transition"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-bold text-sm text-slate-900">{g.name}</h4>
                      {g.target_date && (
                        <span className="text-[11px] text-slate-400">
                          Target: {formatISTDate(g.target_date)}
                        </span>
                      )}
                    </div>
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                        isAchieved
                          ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                          : 'bg-blue-100 text-blue-800 border-blue-200'
                      }`}
                    >
                      {g.status}
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-slate-900 font-mono">{formatINR(g.current_amount)}</span>
                      <span className="text-slate-400 font-mono">Target: {formatINR(g.target_amount)}</span>
                    </div>
                    <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 transition-all duration-500"
                        style={{ width: `${pctNum}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>{g.percentage_achieved}% achieved</span>
                      <span>To Go: {formatINR(g.remaining_amount)}</span>
                    </div>
                  </div>

                  {!isAchieved && (
                    <button
                      onClick={() => {
                        setSelectedGoal(g);
                        setUpdateGoalModalOpen(true);
                      }}
                      className="w-full py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 transition"
                    >
                      + Add Saved Amount
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )
      )}

      {/* Set Budget Modal */}
      {budgetModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Set Monthly Budget</h3>
              <button
                onClick={() => setBudgetModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateBudget} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Category
                </label>
                <select
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value="">-- All Categories (Household Total) --</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Budget Limit (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={budgetAmount}
                  onChange={(e) => setBudgetAmount(e.target.value)}
                  placeholder="e.g. 15000.00"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none font-semibold"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submittingBudget}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50"
                >
                  {submittingBudget ? 'Saving...' : 'Save Budget'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Goal Modal */}
      {goalModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">New Savings Goal</h3>
              <button
                onClick={() => setGoalModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateGoal} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Goal Name *
                </label>
                <input
                  type="text"
                  required
                  value={goalName}
                  onChange={(e) => setGoalName(e.target.value)}
                  placeholder="e.g. Emergency Fund, Gold Coin"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Target Amount (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={goalTarget}
                  onChange={(e) => setGoalTarget(e.target.value)}
                  placeholder="e.g. 100000.00"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none font-semibold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Already Saved (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={goalCurrent}
                  onChange={(e) => setGoalCurrent(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Target Date (Optional)
                </label>
                <input
                  type="date"
                  value={goalDate}
                  onChange={(e) => setGoalDate(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submittingGoal}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50"
                >
                  {submittingGoal ? 'Creating...' : 'Create Goal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Funds Modal */}
      {updateGoalModalOpen && selectedGoal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Add to {selectedGoal.name}</h3>
              <button
                onClick={() => setUpdateGoalModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddFundsToGoal} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Additional Amount Saved (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={addFundsAmount}
                  onChange={(e) => setAddFundsAmount(e.target.value)}
                  placeholder="e.g. 5000.00"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none font-semibold"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={updatingGoal}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50"
                >
                  {updatingGoal ? 'Updating...' : 'Add to Goal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { formatINR } from '../utils/formatters';
import {
  Wallet,
  Building,
  CreditCard,
  Plus,
  RefreshCw,
  AlertCircle,
  Eye,
  EyeOff,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownLeft,
  X,
} from 'lucide-react';

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [seeding, setSeeding] = useState(false);

  // New account form state
  const [name, setName] = useState('');
  const [accountType, setAccountType] = useState('savings');
  const [institutionName, setInstitutionName] = useState('');
  const [last4, setLast4] = useState('');
  const [visibility, setVisibility] = useState('shared');
  const [openingBalance, setOpeningBalance] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await api.get('/accounts');
      setAccounts(res.data);
    } catch (err) {
      setError(err.message || 'Failed to fetch accounts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
    const handleUpdate = () => fetchAccounts();
    window.addEventListener('sfbm_data_updated', handleUpdate);
    return () => window.removeEventListener('sfbm_data_updated', handleUpdate);
  }, []);

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const createRes = await api.post('/accounts', {
        name,
        account_type: accountType,
        institution_name: institutionName.trim() || undefined,
        account_number_last4: last4.trim() ? last4.trim() : undefined,
        visibility,
      });

      // If initial opening balance is specified, create opening balance transaction
      if (openingBalance && parseFloat(openingBalance) > 0) {
        await api.post('/transfers/opening-balance', {
          account_id: createRes.data.id,
          amount: parseFloat(openingBalance).toFixed(2),
          description: 'Initial Opening Balance',
        });
      }

      setAddModalOpen(false);
      setName('');
      setInstitutionName('');
      setLast4('');
      setOpeningBalance('');
      fetchAccounts();
    } catch (err) {
      setError(err.message || 'Failed to create account');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSeedCategories = async () => {
    setSeeding(true);
    try {
      await api.post('/categories/seed');
      alert('Standard Indian taxonomy categories seeded successfully!');
    } catch (err) {
      alert(err.message || 'Failed to seed categories');
    } finally {
      setSeeding(false);
    }
  };

  // Compute metrics
  const liabilityTypes = ['credit_card', 'loan'];
  const assetAccounts = accounts.filter((a) => !liabilityTypes.includes(a.account_type));
  const liabilityAccounts = accounts.filter((a) => liabilityTypes.includes(a.account_type));

  const totalAssets = assetAccounts.reduce((acc, a) => acc + (parseFloat(a.derived_balance) || 0), 0);
  const totalLiabilities = liabilityAccounts.reduce((acc, a) => acc + (parseFloat(a.derived_balance) || 0), 0);
  const netWorth = totalAssets - totalLiabilities;

  const getAccountIcon = (type) => {
    switch (type) {
      case 'credit_card':
        return <CreditCard className="w-5 h-5 text-purple-600" />;
      case 'cash':
        return <Wallet className="w-5 h-5 text-emerald-600" />;
      default:
        return <Building className="w-5 h-5 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Financial Accounts</h1>
          <p className="text-xs text-slate-500">
            Real balances derived strictly from posted ledger transactions
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={handleSeedCategories}
            disabled={seeding}
            className="px-3 py-2 text-xs font-semibold bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-50 transition shadow-sm"
          >
            {seeding ? 'Seeding...' : 'Seed Indian Categories'}
          </button>
          <button
            onClick={() => setAddModalOpen(true)}
            className="flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Account</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Net Worth */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Net Worth</p>
          <h2 className="text-2xl font-extrabold text-slate-900 mt-1">
            {formatINR(netWorth)}
          </h2>
          <span className="text-[11px] text-slate-400 mt-1 block">Assets minus credit liabilities</span>
        </div>

        {/* Liquid Assets */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Assets</p>
            <ArrowUpRight className="w-4 h-4 text-emerald-600" />
          </div>
          <h2 className="text-2xl font-extrabold text-emerald-600 mt-1">
            {formatINR(totalAssets)}
          </h2>
          <span className="text-[11px] text-slate-400 mt-1 block">{assetAccounts.length} asset accounts</span>
        </div>

        {/* Total Liabilities */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Liabilities</p>
            <ArrowDownLeft className="w-4 h-4 text-purple-600" />
          </div>
          <h2 className="text-2xl font-extrabold text-purple-600 mt-1">
            {formatINR(totalLiabilities)}
          </h2>
          <span className="text-[11px] text-slate-400 mt-1 block">{liabilityAccounts.length} credit/loan cards</span>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-center space-x-2 text-red-700 text-sm font-medium">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Accounts List */}
      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-8 h-8 text-emerald-600 animate-spin" />
          <p className="text-xs text-slate-500">Calculating derived account balances...</p>
        </div>
      ) : accounts.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-12 text-center">
          <Wallet className="w-12 h-12 text-slate-400 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-800">No Financial Accounts Yet</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            Add your primary savings bank, physical cash wallet, or credit cards to begin tracking balances.
          </p>
          <button
            onClick={() => setAddModalOpen(true)}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-500 transition"
          >
            Create First Account
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <h3 className="text-sm font-bold text-slate-800">Active Accounts ({accounts.length})</h3>
            <span className="text-[11px] text-slate-500">Balances updated in real-time</span>
          </div>

          <div className="divide-y divide-slate-100">
            {accounts.map((acc) => {
              const isLiability = liabilityTypes.includes(acc.account_type);
              const balanceNum = parseFloat(acc.derived_balance) || 0;

              return (
                <div
                  key={acc.id}
                  className="px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/60 transition"
                >
                  <div className="flex items-center space-x-3.5">
                    <div className="p-2.5 rounded-xl bg-slate-100 border border-slate-200">
                      {getAccountIcon(acc.account_type)}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="font-semibold text-sm text-slate-900">{acc.name}</h4>
                        {acc.account_number_last4 && (
                          <span className="text-xs text-slate-500 font-mono">
                            &bull;&bull;&bull;&bull; {acc.account_number_last4}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center space-x-2 mt-0.5">
                        <span className="text-[11px] uppercase tracking-wider font-semibold text-slate-500">
                          {acc.account_type.replace('_', ' ')}
                        </span>
                        {acc.institution_name && (
                          <span className="text-xs text-slate-400">&bull; {acc.institution_name}</span>
                        )}
                        <span className="text-xs text-slate-300">|</span>
                        <span className="inline-flex items-center space-x-1 text-[11px] text-slate-500">
                          {acc.visibility === 'shared' ? (
                            <>
                              <Eye className="w-3 h-3 text-emerald-600" />
                              <span>Shared</span>
                            </>
                          ) : (
                            <>
                              <EyeOff className="w-3 h-3 text-amber-600" />
                              <span>Private</span>
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="text-left sm:text-right">
                    <p
                      className={`text-base font-extrabold font-mono ${
                        isLiability
                          ? 'text-purple-600'
                          : balanceNum >= 0
                          ? 'text-slate-900'
                          : 'text-red-600'
                      }`}
                    >
                      {formatINR(balanceNum)}
                    </p>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                      {isLiability ? 'Liability / Due' : 'Available Balance'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Create Account Modal */}
      {addModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <h2 className="text-base font-bold text-slate-900">Create Financial Account</h2>
              <button
                onClick={() => setAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Account Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Salary Bank Account, Pocket Cash"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Account Type *
                  </label>
                  <select
                    value={accountType}
                    onChange={(e) => setAccountType(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none capitalize"
                  >
                    <option value="savings">Savings Bank</option>
                    <option value="current">Current Account</option>
                    <option value="cash">Cash Wallet</option>
                    <option value="credit_card">Credit Card</option>
                    <option value="loan">Loan Account</option>
                    <option value="investment">Investment / Demat</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Institution / Bank
                  </label>
                  <input
                    type="text"
                    value={institutionName}
                    onChange={(e) => setInstitutionName(e.target.value)}
                    placeholder="e.g. HDFC, SBI"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Last 4 Digits
                  </label>
                  <input
                    type="text"
                    maxLength={4}
                    value={last4}
                    onChange={(e) => setLast4(e.target.value.replace(/\D/g, ''))}
                    placeholder="1234"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Visibility
                  </label>
                  <select
                    value={visibility}
                    onChange={(e) => setVisibility(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  >
                    <option value="shared">Shared (Household)</option>
                    <option value="private">Private (Only Me)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Opening Balance (₹) (Optional)
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 font-bold">
                    ₹
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={openingBalance}
                    onChange={(e) => setOpeningBalance(e.target.value)}
                    placeholder="0.00"
                    className="w-full pl-8 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="pt-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg shadow-sm text-sm transition disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

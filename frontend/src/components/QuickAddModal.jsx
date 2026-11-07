import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { X, ArrowRight, Check, AlertCircle, RefreshCw } from 'lucide-react';

export default function QuickAddModal({ isOpen, onClose, onSuccess }) {
  const [tab, setTab] = useState('transaction'); // 'transaction' or 'transfer'
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Transaction form state
  const [txnType, setTxnType] = useState('EXPENSE');
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [visibility, setVisibility] = useState('shared');

  // Transfer form state
  const [sourceAccountId, setSourceAccountId] = useState('');
  const [destinationAccountId, setDestinationAccountId] = useState('');
  const [transferAmount, setTransferAmount] = useState('');
  const [transferDescription, setTransferDescription] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadAccountsAndCategories();
      setError('');
    }
  }, [isOpen]);

  const loadAccountsAndCategories = async () => {
    setLoadingMetadata(true);
    try {
      const [accRes, catRes] = await Promise.all([
        api.get('/accounts'),
        api.get('/categories'),
      ]);
      setAccounts(accRes.data);
      setCategories(catRes.data);
      if (accRes.data.length > 0) {
        setAccountId(accRes.data[0].id);
        setSourceAccountId(accRes.data[0].id);
        if (accRes.data.length > 1) {
          setDestinationAccountId(accRes.data[1].id);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load accounts and categories');
    } finally {
      setLoadingMetadata(false);
    }
  };

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await api.post('/transactions', {
        account_id: accountId,
        category_id: categoryId || null,
        amount: parseFloat(amount).toFixed(2),
        direction: txnType === 'EXPENSE' ? 'OUTFLOW' : 'INFLOW',
        transaction_type: txnType,
        description: description.trim() || undefined,
        visibility,
      });
      // Reset form
      setAmount('');
      setDescription('');
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to record transaction');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTransferSubmit = async (e) => {
    e.preventDefault();
    if (sourceAccountId === destinationAccountId) {
      setError('Source and Destination accounts must be different');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await api.post('/transfers', {
        source_account_id: sourceAccountId,
        destination_account_id: destinationAccountId,
        amount: parseFloat(transferAmount).toFixed(2),
        description: transferDescription.trim() || undefined,
      });
      // Reset form
      setTransferAmount('');
      setTransferDescription('');
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to record transfer');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const filteredCategories = categories.filter((c) => {
    if (txnType === 'EXPENSE') return c.type === 'expense';
    if (txnType === 'INCOME') return c.type === 'income';
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h2 className="text-lg font-bold text-slate-900">Add Entry</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => {
              setTab('transaction');
              setError('');
            }}
            className={`flex-1 py-3 text-sm font-semibold border-b-2 text-center transition ${
              tab === 'transaction'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Income / Expense
          </button>
          <button
            type="button"
            onClick={() => {
              setTab('transfer');
              setError('');
            }}
            className={`flex-1 py-3 text-sm font-semibold border-b-2 text-center transition ${
              tab === 'transfer'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Account Transfer
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-red-50 border border-red-200 flex items-start space-x-2 text-red-700 text-xs font-medium">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form Body */}
        {loadingMetadata ? (
          <div className="p-12 flex flex-col items-center justify-center space-y-2">
            <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin" />
            <p className="text-xs text-slate-500">Loading accounts and categories...</p>
          </div>
        ) : tab === 'transaction' ? (
          <form onSubmit={handleTransactionSubmit} className="p-6 space-y-4">
            {/* Direction Toggle */}
            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-100 rounded-lg">
              <button
                type="button"
                onClick={() => setTxnType('EXPENSE')}
                className={`py-1.5 text-xs font-bold rounded-md transition ${
                  txnType === 'EXPENSE'
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Expense (Outflow)
              </button>
              <button
                type="button"
                onClick={() => setTxnType('INCOME')}
                className={`py-1.5 text-xs font-bold rounded-md transition ${
                  txnType === 'INCOME'
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Income (Inflow)
              </button>
            </div>

            {/* Amount Input */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Amount (₹) *
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 font-bold">
                  ₹
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full pl-8 pr-3 py-2 text-base font-semibold border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Account Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Account *
              </label>
              <select
                required
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({acc.account_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Category Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Category
              </label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                <option value="">-- Select Category --</option>
                {filteredCategories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Description / Notes
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Weekly vegetable shopping"
                maxLength={500}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>

            {/* Visibility */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Visibility
              </label>
              <select
                value={visibility}
                onChange={(e) => setVisibility(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                <option value="shared">Shared (Visible to Household)</option>
                <option value="private">Private (Only Me)</option>
              </select>
            </div>

            {/* Submit */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm text-sm transition disabled:opacity-50 flex items-center justify-center space-x-2"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <span>Record Transaction</span>
                )}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleTransferSubmit} className="p-6 space-y-4">
            {/* Amount Input */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Transfer Amount (₹) *
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 font-bold">
                  ₹
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full pl-8 pr-3 py-2 text-base font-semibold border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Source Account */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                From (Source Account) *
              </label>
              <select
                required
                value={sourceAccountId}
                onChange={(e) => setSourceAccountId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({acc.account_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Destination Account */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                To (Destination Account) *
              </label>
              <select
                required
                value={destinationAccountId}
                onChange={(e) => setDestinationAccountId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({acc.account_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Description / Reference
              </label>
              <input
                type="text"
                value={transferDescription}
                onChange={(e) => setTransferDescription(e.target.value)}
                placeholder="e.g. ATM Cash Withdrawal, Card Settlement"
                maxLength={500}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>

            {/* Submit */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm text-sm transition disabled:opacity-50 flex items-center justify-center space-x-2"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Executing Transfer...</span>
                  </>
                ) : (
                  <span>Execute Transfer</span>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

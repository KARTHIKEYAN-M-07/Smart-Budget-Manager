import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import { formatINR, formatISTDateTime, formatISTDate } from '../utils/formatters';
import {
  Search,
  Filter,
  ArrowDownLeft,
  ArrowUpRight,
  ArrowLeftRight,
  RefreshCw,
  Ban,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  X,
} from 'lucide-react';

export default function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 15;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [search, setSearch] = useState('');
  const [selectedAccount, setSelectedAccount] = useState('');
  const [selectedDirection, setSelectedDirection] = useState('');
  const [selectedType, setSelectedType] = useState('');

  // Void modal
  const [voidModalOpen, setVoidModalOpen] = useState(false);
  const [txnToVoid, setTxnToVoid] = useState(null);
  const [voidReason, setVoidReason] = useState('Entry made by mistake');
  const [voiding, setVoiding] = useState(false);

  const fetchMetadata = async () => {
    try {
      const [accRes, catRes] = await Promise.all([
        api.get('/accounts'),
        api.get('/categories'),
      ]);
      setAccounts(accRes.data);
      setCategories(catRes.data);
    } catch (err) {
      console.error('Failed to load accounts/categories', err);
    }
  };

  const fetchTransactions = async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        limit: pageSize,
        offset: (page - 1) * pageSize,
      };
      if (search.trim()) params.search = search.trim();
      if (selectedAccount) params.account_id = selectedAccount;
      if (selectedDirection) params.direction = selectedDirection;
      if (selectedType) params.transaction_type = selectedType;

      const res = await api.get('/transactions', { params });
      setTransactions(res.data.items);
      setTotalCount(res.data.total_count);
    } catch (err) {
      setError(err.message || 'Failed to fetch transactions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetadata();
  }, []);

  useEffect(() => {
    fetchTransactions();
    const handleUpdate = () => fetchTransactions();
    window.addEventListener('sfbm_data_updated', handleUpdate);
    return () => window.removeEventListener('sfbm_data_updated', handleUpdate);
  }, [page, search, selectedAccount, selectedDirection, selectedType]);

  const handleVoid = async (e) => {
    e.preventDefault();
    if (!txnToVoid) return;
    setVoiding(true);
    try {
      await api.post(`/transactions/${txnToVoid.id}/void`, {
        reason: voidReason,
        version: txnToVoid.version,
      });
      setVoidModalOpen(false);
      setTxnToVoid(null);
      fetchTransactions();
      window.dispatchEvent(new Event('sfbm_data_updated'));
    } catch (err) {
      alert(err.message || 'Failed to void transaction');
    } finally {
      setVoiding(false);
    }
  };

  const getAccountName = (accId) => {
    const acc = accounts.find((a) => a.id === accId);
    return acc ? acc.name : 'Unknown Account';
  };

  const getCategoryName = (catId) => {
    if (!catId) return 'Uncategorized';
    const cat = categories.find((c) => c.id === catId);
    return cat ? cat.name : 'Category';
  };

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Ledger Transactions</h1>
          <p className="text-xs text-slate-500">
            Immutable financial history &bull; Voided records preserved for audit integrity
          </p>
        </div>
        <Link
          to="/import"
          className="flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg transition shadow-sm self-start sm:self-auto"
        >
          <span>Import Bank Statement (.csv)</span>
        </Link>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
              <Search className="w-4 h-4" />
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search description..."
              className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          {/* Account Filter */}
          <div>
            <select
              value={selectedAccount}
              onChange={(e) => {
                setSelectedAccount(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Accounts</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                </option>
              ))}
            </select>
          </div>

          {/* Direction Filter */}
          <div>
            <select
              value={selectedDirection}
              onChange={(e) => {
                setSelectedDirection(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Directions</option>
              <option value="OUTFLOW">Outflow (Spent / Paid)</option>
              <option value="INFLOW">Inflow (Received / Deposited)</option>
            </select>
          </div>

          {/* Transaction Type Filter */}
          <div>
            <select
              value={selectedType}
              onChange={(e) => {
                setSelectedType(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Types</option>
              <option value="EXPENSE">Expense</option>
              <option value="INCOME">Income</option>
              <option value="TRANSFER_OUT">Transfer Out</option>
              <option value="TRANSFER_IN">Transfer In</option>
              <option value="REFUND">Refund</option>
              <option value="OPENING_BALANCE">Opening Balance</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-center space-x-2 text-red-700 text-sm font-medium">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Transactions Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-2">
            <RefreshCw className="w-7 h-7 text-emerald-600 animate-spin" />
            <p className="text-xs text-slate-500">Querying ledger records...</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-12 text-center">
            <ArrowLeftRight className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-slate-700">No Transactions Found</h3>
            <p className="text-xs text-slate-500 mt-1">
              No matching records for the selected filters. Use "+ Add" to record spending or transfers.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/75 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Description / Reference</th>
                  <th className="py-3 px-4">Account</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {transactions.map((txn) => {
                  const isVoided = txn.status === 'VOIDED';
                  const isInflow = txn.direction === 'INFLOW';
                  const amountNum = parseFloat(txn.amount) || 0;

                  return (
                    <tr
                      key={txn.id}
                      className={`hover:bg-slate-50/70 transition ${
                        isVoided ? 'opacity-50 bg-slate-50/40' : ''
                      }`}
                    >
                      {/* Date */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-slate-600 font-medium">
                        {formatISTDate(txn.transaction_date)}
                      </td>

                      {/* Description */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-slate-900">
                            {txn.description || txn.transaction_type.replace('_', ' ')}
                          </span>
                          {txn.transfer_group_id && (
                            <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-mono">
                              Transfer
                            </span>
                          )}
                          {txn.linked_transaction_id && (
                            <span className="text-[10px] bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded font-mono">
                              Refund
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Account */}
                      <td className="py-3.5 px-4 text-slate-600 font-medium whitespace-nowrap">
                        {getAccountName(txn.account_id)}
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700">
                          {getCategoryName(txn.category_id)}
                        </span>
                      </td>

                      {/* Amount */}
                      <td
                        className={`py-3.5 px-4 text-right font-bold font-mono text-sm whitespace-nowrap ${
                          isVoided
                            ? 'line-through text-slate-400'
                            : isInflow
                            ? 'text-emerald-600'
                            : 'text-slate-900'
                        }`}
                      >
                        {isInflow ? '+' : '-'}
                        {formatINR(amountNum)}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            isVoided
                              ? 'bg-slate-200 text-slate-600'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          }`}
                        >
                          {txn.status}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        {!isVoided ? (
                          <button
                            onClick={() => {
                              setTxnToVoid(txn);
                              setVoidModalOpen(true);
                            }}
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                            title="Void Transaction"
                          >
                            <Ban className="w-4 h-4" />
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">Voided</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="px-6 py-3 border-t border-slate-100 flex items-center justify-between bg-slate-50 text-xs text-slate-600">
          <span>
            Showing {transactions.length} of {totalCount} records (Page {page} of {totalPages})
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 transition"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 transition"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Void Confirmation Modal */}
      {voidModalOpen && txnToVoid && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 p-6 space-y-4">
            <div className="flex items-center space-x-3 text-red-600">
              <div className="p-2 bg-red-100 rounded-xl">
                <Ban className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Void Transaction</h3>
            </div>

            <p className="text-xs text-slate-600">
              Are you sure you want to void this transaction of{' '}
              <strong className="text-slate-900 font-mono">
                {formatINR(txnToVoid.amount)}
              </strong>
              ? In accordance with financial ledger integrity, the record is never hard-deleted, but its balance effect is reversed and marked voided.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason for Voiding *
              </label>
              <input
                type="text"
                required
                value={voidReason}
                onChange={(e) => setVoidReason(e.target.value)}
                placeholder="e.g. Duplicate entry, Wrong amount"
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setVoidModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={voiding}
                onClick={handleVoid}
                className="px-4 py-2 text-xs font-semibold bg-red-600 hover:bg-red-500 text-white rounded-lg transition shadow-sm disabled:opacity-50"
              >
                {voiding ? 'Voiding...' : 'Confirm Void'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';
import {
  UploadCloud,
  FileText,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  ArrowRight,
  ShieldAlert,
  ChevronRight,
} from 'lucide-react';

export default function StatementImport() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [editedItems, setEditedItems] = useState([]);

  useEffect(() => {
    loadAccountsAndCategories();
  }, []);

  const loadAccountsAndCategories = async () => {
    try {
      const [accRes, catRes] = await Promise.all([
        api.get('/accounts'),
        api.get('/categories'),
      ]);
      setAccounts(accRes.data);
      setCategories(catRes.data);
      if (accRes.data.length > 0) {
        setSelectedAccount(accRes.data[0].id);
      }
    } catch (err) {
      setError(err.message || 'Failed to load accounts');
    }
  };

  const handlePreview = async (e) => {
    e.preventDefault();
    if (!file || !selectedAccount) {
      setError('Please select an account and upload a CSV statement file.');
      return;
    }
    setError('');
    setLoading(true);
    setPreview(null);
    try {
      const formData = new FormData();
      formData.append('account_id', selectedAccount);
      formData.append('file', file);

      const res = await api.post('/imports/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(res.data);
      setEditedItems(res.data.preview_items);
    } catch (err) {
      setError(err.message || 'Failed to parse statement');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    setError('');
    try {
      const payload = {
        account_id: selectedAccount,
        transactions: editedItems.map((item) => ({
          date: item.date,
          description: item.description,
          amount: parseFloat(item.amount).toFixed(2),
          direction: item.direction,
          transaction_type: item.transaction_type,
          category_id: item.category_id || null,
          visibility: 'shared',
          idempotency_key: item.idempotency_key,
        })),
      };

      const res = await api.post('/imports/confirm', payload);
      alert(res.data.message);
      window.dispatchEvent(new Event('sfbm_data_updated'));
      navigate('/transactions');
    } catch (err) {
      setError(err.message || 'Failed to import transactions');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Import Bank Statement</h1>
        <p className="text-xs text-slate-500">
          Upload CSV bank statements &bull; Automatic duplicate detection protects ledger balances
        </p>
      </div>

      {/* Upload Box */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm space-y-5">
        <form onSubmit={handlePreview} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Target Account *
              </label>
              <select
                value={selectedAccount}
                onChange={(e) => setSelectedAccount(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({acc.account_type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Statement File (.csv) *
              </label>
              <input
                type="file"
                accept=".csv,text/csv"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={loading || !file}
              className="flex items-center space-x-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Parsing & Checking Duplicates...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Preview Statement</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-center space-x-2 text-red-700 text-sm font-medium">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Preview Section */}
      {preview && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-4 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Statement Preview &bull; {preview.account_name}
              </h3>
              <div className="flex items-center space-x-3 text-xs mt-1">
                <span className="text-slate-500">Total Rows: {preview.total_rows}</span>
                <span className="text-emerald-600 font-semibold">
                  New to Import: {preview.new_rows_count}
                </span>
                <span className="text-amber-600 font-semibold">
                  Duplicates (Skipped): {preview.duplicate_rows_count}
                </span>
              </div>
            </div>

            <button
              onClick={handleConfirm}
              disabled={submitting || preview.new_rows_count === 0}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50 flex items-center space-x-2"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Committing to Ledger...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Confirm Import ({preview.new_rows_count} New)</span>
                </>
              )}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/75 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {editedItems.map((item, idx) => {
                  const isDup = item.is_duplicate;
                  const isInflow = item.direction === 'INFLOW';

                  return (
                    <tr
                      key={idx}
                      className={isDup ? 'bg-amber-50/30 opacity-60' : 'hover:bg-slate-50/50'}
                    >
                      <td className="py-2.5 px-3 whitespace-nowrap text-slate-600">
                        {formatISTDate(item.date)}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-slate-900 max-w-xs truncate">
                        {item.description}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <select
                          disabled={isDup}
                          value={item.category_id || ''}
                          onChange={(e) => {
                            const newItems = [...editedItems];
                            newItems[idx].category_id = e.target.value || null;
                            setEditedItems(newItems);
                          }}
                          className="px-2 py-1 text-xs border border-slate-200 rounded-md focus:outline-none"
                        >
                          <option value="">-- Inferred: {item.category_name || 'None'} --</option>
                          {categories.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-bold font-mono ${
                          isInflow ? 'text-emerald-600' : 'text-slate-900'
                        }`}
                      >
                        {isInflow ? '+' : '-'}
                        {formatINR(item.amount)}
                      </td>
                      <td className="py-2.5 px-3 text-center whitespace-nowrap">
                        {isDup ? (
                          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                            Duplicate (Skip)
                          </span>
                        ) : (
                          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            New
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

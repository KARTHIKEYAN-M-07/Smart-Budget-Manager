import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';

export default function Investments() {
  const [summary, setSummary] = useState(null);
  const [investments, setInvestments] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [assetClassFilter, setAssetClassFilter] = useState('');

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showValuationModal, setShowValuationModal] = useState(null); // holds selected investment
  const [showTxnModal, setShowTxnModal] = useState(null);

  // Form states
  const [newInv, setNewInv] = useState({
    name: '',
    asset_class: 'MUTUAL_FUND',
    institution_name: '',
    folio_or_account_number_last4: '',
    units_or_quantity: '1',
    invested_amount: '',
    current_value: '',
    interest_rate_percent: '',
    start_date: new Date().toISOString().split('T')[0],
    maturity_date: '',
    valuation_source: 'Groww / Zerodha',
    notes: '',
    source_account_id: '',
  });

  const [valuationForm, setValuationForm] = useState({
    current_value: '',
    valuation_source: '',
  });

  const [txnForm, setTxnForm] = useState({
    transaction_type: 'BUY',
    transaction_date: new Date().toISOString().split('T')[0],
    amount: '',
    units: '0',
    source_account_id: '',
    notes: '',
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (assetClassFilter) params.asset_class = assetClassFilter;

      const [resSummary, resInvestments, resAccounts] = await Promise.all([
        apiClient.get('/investments/summary'),
        apiClient.get('/investments', { params }),
        apiClient.get('/accounts'),
      ]);

      setSummary(resSummary.data);
      setInvestments(resInvestments.data);
      setAccounts(resAccounts.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load investments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [assetClassFilter]);

  const handleCreateInvestment = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        name: newInv.name,
        asset_class: newInv.asset_class,
        institution_name: newInv.institution_name || null,
        folio_or_account_number_last4: newInv.folio_or_account_number_last4 || null,
        units_or_quantity: parseFloat(newInv.units_or_quantity || 1),
        invested_amount: parseFloat(newInv.invested_amount),
        current_value: newInv.current_value ? parseFloat(newInv.current_value) : parseFloat(newInv.invested_amount),
        interest_rate_percent: newInv.interest_rate_percent ? parseFloat(newInv.interest_rate_percent) : null,
        start_date: newInv.start_date,
        maturity_date: newInv.maturity_date || null,
        valuation_source: newInv.valuation_source || null,
        notes: newInv.notes || null,
        source_account_id: newInv.source_account_id || null,
      };

      await apiClient.post('/investments', payload);
      setShowAddModal(false);
      setNewInv({
        name: '',
        asset_class: 'MUTUAL_FUND',
        institution_name: '',
        folio_or_account_number_last4: '',
        units_or_quantity: '1',
        invested_amount: '',
        current_value: '',
        interest_rate_percent: '',
        start_date: new Date().toISOString().split('T')[0],
        maturity_date: '',
        valuation_source: 'Groww / Zerodha',
        notes: '',
        source_account_id: '',
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error creating investment.');
    }
  };

  const handleUpdateValuation = async (e) => {
    e.preventDefault();
    if (!showValuationModal) return;
    try {
      await apiClient.patch(`/investments/${showValuationModal.id}`, {
        current_value: parseFloat(valuationForm.current_value),
        valuation_source: valuationForm.valuation_source || null,
        version: showValuationModal.version,
      });
      setShowValuationModal(null);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error updating valuation.');
    }
  };

  const handleAddTransaction = async (e) => {
    e.preventDefault();
    if (!showTxnModal) return;
    try {
      await apiClient.post(`/investments/${showTxnModal.id}/transactions`, {
        transaction_type: txnForm.transaction_type,
        transaction_date: txnForm.transaction_date,
        amount: parseFloat(txnForm.amount),
        units: parseFloat(txnForm.units || 0),
        source_account_id: txnForm.source_account_id || null,
        notes: txnForm.notes || null,
      });
      setShowTxnModal(null);
      setTxnForm({
        transaction_type: 'BUY',
        transaction_date: new Date().toISOString().split('T')[0],
        amount: '',
        units: '0',
        source_account_id: '',
        notes: '',
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error recording transaction.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Investment Portfolio</h1>
          <p className="text-sm text-gray-500">
            Mutual funds, equities, FDs, PPF & retirement assets. Contributions are asset movements, not consumption.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm"
        >
          + Add Investment
        </button>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Total Portfolio Value</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">{formatINR(summary.total_current_value)}</p>
            <p className="text-xs text-gray-400 mt-1">{summary.investments_count} active holdings</p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Total Invested (Cost)</p>
            <p className="mt-2 text-2xl font-bold text-indigo-600">{formatINR(summary.total_invested)}</p>
            <p className="text-xs text-gray-400 mt-1">Asset allocation principal</p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Unrealized Gain / Loss</p>
            <p
              className={`mt-2 text-2xl font-bold ${
                parseFloat(summary.total_unrealized_gain_loss) >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {parseFloat(summary.total_unrealized_gain_loss) >= 0 ? '+' : ''}
              {formatINR(summary.total_unrealized_gain_loss)}
            </p>
            <p className="text-xs text-gray-500 mt-1">Across all instruments</p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Overall Return</p>
            <p
              className={`mt-2 text-2xl font-bold ${
                parseFloat(summary.overall_return_percentage) >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {summary.overall_return_percentage >= 0 ? '+' : ''}
              {summary.overall_return_percentage}%
            </p>
            <p className="text-xs text-gray-400 mt-1">Total portfolio return</p>
          </div>
        </div>
      )}

      {/* Asset Class Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setAssetClassFilter('')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === '' ? 'bg-gray-900 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          All Assets
        </button>
        <button
          onClick={() => setAssetClassFilter('MUTUAL_FUND')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === 'MUTUAL_FUND' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          Mutual Funds
        </button>
        <button
          onClick={() => setAssetClassFilter('STOCK')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === 'STOCK' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          Stocks / Equities
        </button>
        <button
          onClick={() => setAssetClassFilter('FIXED_DEPOSIT')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === 'FIXED_DEPOSIT' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          Fixed Deposits (FD)
        </button>
        <button
          onClick={() => setAssetClassFilter('PPF')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === 'PPF' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          PPF / EPF / NPS
        </button>
        <button
          onClick={() => setAssetClassFilter('SGB')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            assetClassFilter === 'SGB' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          Sovereign Gold Bonds
        </button>
      </div>

      {/* Holdings List */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading investments...</div>
      ) : error ? (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
      ) : investments.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-gray-100 text-gray-500">
          No investments recorded.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {investments.map((inv) => (
            <div key={inv.id} className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-base font-bold text-gray-900">{inv.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {inv.asset_class.replace('_', ' ')} • {inv.institution_name || 'Direct'}
                    {inv.folio_or_account_number_last4 && ` • Folio: •••• ${inv.folio_or_account_number_last4}`}
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                  {inv.interest_rate_percent ? `${inv.interest_rate_percent}% p.a.` : `${parseFloat(inv.units_or_quantity).toFixed(2)} units`}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-100 text-xs">
                <div>
                  <p className="text-gray-400">Invested</p>
                  <p className="font-semibold text-gray-800 text-sm mt-0.5">{formatINR(inv.invested_amount)}</p>
                </div>
                <div>
                  <p className="text-gray-400">Current Value</p>
                  <p className="font-bold text-gray-900 text-sm mt-0.5">{formatINR(inv.current_value)}</p>
                </div>
                <div>
                  <p className="text-gray-400">Gain / Return</p>
                  <p
                    className={`font-bold text-sm mt-0.5 ${
                      parseFloat(inv.unrealized_gain_loss) >= 0 ? 'text-emerald-600' : 'text-red-600'
                    }`}
                  >
                    {parseFloat(inv.unrealized_gain_loss) >= 0 ? '+' : ''}
                    {formatINR(inv.unrealized_gain_loss)} ({inv.return_percentage >= 0 ? '+' : ''}
                    {inv.return_percentage}%)
                  </p>
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t border-gray-100 text-xs">
                <span className="text-gray-400">
                  Valued {inv.last_valuation_date} ({inv.valuation_source || 'Manual'})
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setShowTxnModal(inv);
                      setTxnForm({
                        transaction_type: 'BUY',
                        transaction_date: new Date().toISOString().split('T')[0],
                        amount: '',
                        units: '0',
                        source_account_id: '',
                        notes: '',
                      });
                    }}
                    className="px-2.5 py-1 border border-gray-200 text-gray-700 hover:bg-gray-50 rounded text-xs font-medium"
                  >
                    + Transaction
                  </button>
                  <button
                    onClick={() => {
                      setShowValuationModal(inv);
                      setValuationForm({
                        current_value: inv.current_value,
                        valuation_source: inv.valuation_source || '',
                      });
                    }}
                    className="px-2.5 py-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-medium"
                  >
                    Update Value
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Investment Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Add Investment Holding</h2>
            <form onSubmit={handleCreateInvestment} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Asset Class</label>
                <select
                  value={newInv.asset_class}
                  onChange={(e) => setNewInv({ ...newInv, asset_class: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="MUTUAL_FUND">Mutual Fund (SIP / Lumpsum)</option>
                  <option value="STOCK">Direct Stock / Equities</option>
                  <option value="FIXED_DEPOSIT">Fixed Deposit (FD)</option>
                  <option value="RECURRING_DEPOSIT">Recurring Deposit (RD)</option>
                  <option value="PPF">Public Provident Fund (PPF)</option>
                  <option value="EPF">Employee Provident Fund (EPF)</option>
                  <option value="NPS">National Pension System (NPS)</option>
                  <option value="SGB">Sovereign Gold Bond (SGB)</option>
                  <option value="OTHER">Other Investment</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Investment / Scheme Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Parag Parikh Flexi Cap Fund, SBI 3-Yr FD, TCS Shares..."
                  value={newInv.name}
                  onChange={(e) => setNewInv({ ...newInv, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Platform / Institution</label>
                  <input
                    type="text"
                    placeholder="Zerodha, Groww, SBI, CAMS..."
                    value={newInv.institution_name}
                    onChange={(e) => setNewInv({ ...newInv, institution_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Folio / Account Last 4</label>
                  <input
                    type="text"
                    placeholder="•••• 1234"
                    value={newInv.folio_or_account_number_last4}
                    onChange={(e) => setNewInv({ ...newInv, folio_or_account_number_last4: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Invested Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="50000.00"
                    value={newInv.invested_amount}
                    onChange={(e) => setNewInv({ ...newInv, invested_amount: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Current Estimated Value (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Same as invested if new"
                    value={newInv.current_value}
                    onChange={(e) => setNewInv({ ...newInv, current_value: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Start / Allocation Date</label>
                  <input
                    type="date"
                    required
                    value={newInv.start_date}
                    onChange={(e) => setNewInv({ ...newInv, start_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Interest Rate % (Optional)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="7.25"
                    value={newInv.interest_rate_percent}
                    onChange={(e) => setNewInv({ ...newInv, interest_rate_percent: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              {/* Fund from bank account */}
              <div className="bg-indigo-50/50 p-3 rounded-lg border border-indigo-100">
                <label className="block text-xs font-medium text-indigo-900 mb-1">
                  Fund from Bank / Cash Account (Optional)
                </label>
                <select
                  value={newInv.source_account_id}
                  onChange={(e) => setNewInv({ ...newInv, source_account_id: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-indigo-200 rounded-lg text-xs"
                >
                  <option value="">None (Existing holding or external)</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({formatINR(a.derived_balance)})
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-indigo-600 mt-1">
                  Automatically records an asset movement (INVESTMENT_BUY). Does NOT count as consumption expense.
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Save Investment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Update Valuation Modal */}
      {showValuationModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Update Valuation</h2>
            <p className="text-xs text-gray-500 mb-4">{showValuationModal.name}</p>

            <form onSubmit={handleUpdateValuation} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Current Market Value (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={valuationForm.current_value}
                  onChange={(e) => setValuationForm({ ...valuationForm, current_value: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Source / Reference</label>
                <input
                  type="text"
                  placeholder="e.g. Zerodha Console, CAMS Statement, Bank Statement"
                  value={valuationForm.valuation_source}
                  onChange={(e) => setValuationForm({ ...valuationForm, valuation_source: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowValuationModal(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Update Value
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Record Transaction Modal */}
      {showTxnModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Record Investment Activity</h2>
            <p className="text-xs text-gray-500 mb-4">{showTxnModal.name}</p>

            <form onSubmit={handleAddTransaction} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Activity Type</label>
                <select
                  value={txnForm.transaction_type}
                  onChange={(e) => setTxnForm({ ...txnForm, transaction_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="BUY">Buy / SIP Contribution</option>
                  <option value="SELL">Sell / Partial Redemption</option>
                  <option value="DIVIDEND">Dividend Received</option>
                  <option value="INTEREST">Interest Payout</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={txnForm.amount}
                    onChange={(e) => setTxnForm({ ...txnForm, amount: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Date</label>
                  <input
                    type="date"
                    required
                    value={txnForm.transaction_date}
                    onChange={(e) => setTxnForm({ ...txnForm, transaction_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Bank Account Reconciled (Optional)</label>
                <select
                  value={txnForm.source_account_id}
                  onChange={(e) => setTxnForm({ ...txnForm, source_account_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">None (External funding/payout)</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({formatINR(a.derived_balance)})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowTxnModal(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Save Activity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

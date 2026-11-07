import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';

export default function PreciousMetals() {
  const [summary, setSummary] = useState(null);
  const [holdings, setHoldings] = useState([]);
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [metalFilter, setMetalFilter] = useState('');

  // Modals
  const [showAddHoldingModal, setShowAddHoldingModal] = useState(false);
  const [showAddRateModal, setShowAddRateModal] = useState(false);

  // Forms
  const [newHolding, setNewHolding] = useState({
    metal_type: 'GOLD_22K',
    item_name: '',
    form: 'JEWELLERY',
    weight_grams: '',
    purity_percentage: '91.60',
    purchase_date: new Date().toISOString().split('T')[0],
    purchase_price: '',
    storage_location: '',
    notes: '',
  });

  const [newRate, setNewRate] = useState({
    metal_type: 'GOLD_22K',
    rate_per_gram: '',
    as_of_date: new Date().toISOString().split('T')[0],
    source: 'IBJA Official',
    notes: '',
  });

  const handleMetalTypeChange = (type) => {
    let purity = '91.60';
    if (type === 'GOLD_24K') purity = '99.90';
    else if (type === 'GOLD_22K') purity = '91.60';
    else if (type === 'GOLD_18K') purity = '75.00';
    else if (type === 'SILVER_999') purity = '99.90';
    else if (type === 'SILVER_925') purity = '92.50';

    setNewHolding({
      ...newHolding,
      metal_type: type,
      purity_percentage: purity,
    });
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (metalFilter) params.metal_type = metalFilter;

      const [resSummary, resHoldings, resPrices] = await Promise.all([
        apiClient.get('/metals/summary'),
        apiClient.get('/metals/holdings', { params }),
        apiClient.get('/metals/prices', { params: { limit: 10 } }),
      ]);

      setSummary(resSummary.data);
      setHoldings(resHoldings.data);
      setPrices(resPrices.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load precious metals data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [metalFilter]);

  const handleCreateHolding = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        metal_type: newHolding.metal_type,
        item_name: newHolding.item_name,
        form: newHolding.form,
        weight_grams: parseFloat(newHolding.weight_grams),
        purity_percentage: parseFloat(newHolding.purity_percentage),
        purchase_date: newHolding.purchase_date,
        purchase_price: parseFloat(newHolding.purchase_price),
        storage_location: newHolding.storage_location || null,
        notes: newHolding.notes || null,
      };

      await apiClient.post('/metals/holdings', payload);
      setShowAddHoldingModal(false);
      setNewHolding({
        metal_type: 'GOLD_22K',
        item_name: '',
        form: 'JEWELLERY',
        weight_grams: '',
        purity_percentage: '91.60',
        purchase_date: new Date().toISOString().split('T')[0],
        purchase_price: '',
        storage_location: '',
        notes: '',
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error adding holding.');
    }
  };

  const handleRecordRate = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        metal_type: newRate.metal_type,
        rate_per_gram: parseFloat(newRate.rate_per_gram),
        as_of_date: newRate.as_of_date,
        source: newRate.source,
        notes: newRate.notes || null,
      };

      await apiClient.post('/metals/prices', payload);
      setShowAddRateModal(false);
      setNewRate({
        metal_type: 'GOLD_22K',
        rate_per_gram: '',
        as_of_date: new Date().toISOString().split('T')[0],
        source: 'IBJA Official',
        notes: '',
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error recording bullion rate.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gold & Silver Portfolio</h1>
          <p className="text-sm text-gray-500">
            Physical holdings, hallmark purity, and manual bullion market valuations.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddRateModal(true)}
            className="px-3.5 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 shadow-sm"
          >
            + Log Bullion Rate
          </button>
          <button
            onClick={() => setShowAddHoldingModal(true)}
            className="px-3.5 py-2 rounded-lg text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 shadow-sm"
          >
            + Add Holding
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Gold Holdings</p>
            <p className="mt-2 text-2xl font-bold text-amber-600">{parseFloat(summary.total_gold_grams).toFixed(3)} g</p>
            <p className="text-xs text-gray-400 mt-1">
              Pure 24K Equiv: {parseFloat(summary.total_gold_24k_pure_equiv_grams).toFixed(3)} g
            </p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Silver Holdings</p>
            <p className="mt-2 text-2xl font-bold text-slate-700">{parseFloat(summary.total_silver_grams).toFixed(3)} g</p>
            <p className="text-xs text-gray-400 mt-1">{summary.holdings_count} total items</p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Estimated Valuation</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">{formatINR(summary.total_estimated_value)}</p>
            <p className="text-xs text-gray-400 mt-1">Cost: {formatINR(summary.total_purchase_cost)}</p>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Unrealized Gain / Return</p>
            <p
              className={`mt-2 text-2xl font-bold ${
                parseFloat(summary.total_unrealized_gain_loss) >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {parseFloat(summary.total_unrealized_gain_loss) >= 0 ? '+' : ''}
              {formatINR(summary.total_unrealized_gain_loss)}
            </p>
            <p className="text-xs text-gray-500 mt-1 font-semibold">
              {summary.overall_return_percentage >= 0 ? '+' : ''}
              {summary.overall_return_percentage}% return
            </p>
          </div>
        </div>
      )}

      {/* Latest Market Rates Bar */}
      {summary && Object.keys(summary.latest_rates).length > 0 && (
        <div className="bg-amber-50/60 border border-amber-200/80 p-4 rounded-xl flex flex-wrap gap-6 items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-900 uppercase tracking-wider">Latest Logged Bullion Rates:</span>
          </div>
          <div className="flex flex-wrap gap-4">
            {Object.entries(summary.latest_rates).map(([metal, quote]) => (
              <div key={metal} className="bg-white px-3 py-1.5 rounded-lg border border-amber-200 shadow-2xs">
                <span className="font-medium text-gray-700">{metal.replace('_', ' ')}: </span>
                <span className="font-bold text-amber-800">{formatINR(quote.rate_per_gram)}/g</span>
                <span className="text-gray-400 ml-1.5">
                  ({quote.source}, {quote.as_of_date})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        <button
          onClick={() => setMetalFilter('')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            metalFilter === '' ? 'bg-gray-900 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          All Metals
        </button>
        <button
          onClick={() => setMetalFilter('GOLD_22K')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            metalFilter === 'GOLD_22K' ? 'bg-amber-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          22K Gold
        </button>
        <button
          onClick={() => setMetalFilter('GOLD_24K')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            metalFilter === 'GOLD_24K' ? 'bg-amber-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          24K Gold
        </button>
        <button
          onClick={() => setMetalFilter('SILVER_999')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            metalFilter === 'SILVER_999' ? 'bg-slate-700 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
          }`}
        >
          999 Silver
        </button>
      </div>

      {/* Holdings Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading precious metals...</div>
      ) : error ? (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
      ) : holdings.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-gray-100 text-gray-500">
          No precious metal holdings recorded.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item / Metal</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Weight & Hallmark</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Storage</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Purchase Cost</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Current Valuation</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Return</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {holdings.map((h) => (
                <tr key={h.id} className="hover:bg-gray-50/50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <p className="text-sm font-semibold text-gray-900">{h.item_name}</p>
                    <p className="text-xs text-amber-700 font-medium">
                      {h.metal_type.replace('_', ' ')} • {h.form}
                    </p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <p className="text-sm font-semibold text-gray-800">{parseFloat(h.weight_grams).toFixed(3)} g</p>
                    <p className="text-xs text-gray-400">{h.purity_percentage}% purity</p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {h.storage_location || 'Not specified'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-600">
                    {formatINR(h.purchase_price)}
                    <p className="text-xs text-gray-400">{h.purchase_date}</p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    {h.current_estimated_value ? (
                      <>
                        <p className="text-sm font-bold text-gray-900">{formatINR(h.current_estimated_value)}</p>
                        <p className="text-xs text-gray-400">
                          {formatINR(h.current_rate_per_gram)}/g ({h.valuation_source})
                        </p>
                      </>
                    ) : (
                      <span className="text-xs text-gray-400 italic">No rate recorded</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    {h.unrealized_gain_loss !== null ? (
                      <div>
                        <span
                          className={`text-sm font-bold ${
                            parseFloat(h.unrealized_gain_loss) >= 0 ? 'text-emerald-600' : 'text-red-600'
                          }`}
                        >
                          {parseFloat(h.unrealized_gain_loss) >= 0 ? '+' : ''}
                          {formatINR(h.unrealized_gain_loss)}
                        </span>
                        <p className="text-xs text-gray-500 font-medium">
                          {h.return_percentage >= 0 ? '+' : ''}
                          {h.return_percentage}%
                        </p>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Holding Modal */}
      {showAddHoldingModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Add Precious Metal Holding</h2>
            <form onSubmit={handleCreateHolding} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Metal Type</label>
                <select
                  value={newHolding.metal_type}
                  onChange={(e) => handleMetalTypeChange(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="GOLD_22K">22K Gold (91.6% Hallmark)</option>
                  <option value="GOLD_24K">24K Pure Gold (99.9%)</option>
                  <option value="GOLD_18K">18K Gold (75.0%)</option>
                  <option value="SILVER_999">999 Pure Silver (99.9%)</option>
                  <option value="SILVER_925">925 Sterling Silver (92.5%)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Item Name / Description</label>
                <input
                  type="text"
                  required
                  placeholder="Wedding Bangles, Sovereign Coin, Pooja Diya..."
                  value={newHolding.item_name}
                  onChange={(e) => setNewHolding({ ...newHolding, item_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Form</label>
                  <select
                    value={newHolding.form}
                    onChange={(e) => setNewHolding({ ...newHolding, form: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="JEWELLERY">Jewellery</option>
                    <option value="COIN">Coin</option>
                    <option value="BAR">Bar / Ingot</option>
                    <option value="UTENSIL">Utensil / Vessel</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Weight (Grams)</label>
                  <input
                    type="number"
                    step="0.001"
                    required
                    placeholder="8.000"
                    value={newHolding.weight_grams}
                    onChange={(e) => setNewHolding({ ...newHolding, weight_grams: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Purchase Price (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={newHolding.purchase_price}
                    onChange={(e) => setNewHolding({ ...newHolding, purchase_price: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Purchase Date</label>
                  <input
                    type="date"
                    required
                    value={newHolding.purchase_date}
                    onChange={(e) => setNewHolding({ ...newHolding, purchase_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Storage Location (Optional)</label>
                <input
                  type="text"
                  placeholder="SBI Locker #12, Home Safe..."
                  value={newHolding.storage_location}
                  onChange={(e) => setNewHolding({ ...newHolding, storage_location: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddHoldingModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Save Holding
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Record Bullion Rate Modal */}
      {showAddRateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Log Market Bullion Rate</h2>
            <p className="text-xs text-gray-500 mb-4">
              Enter verified market quote with external source and date.
            </p>
            <form onSubmit={handleRecordRate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Metal Type</label>
                <select
                  value={newRate.metal_type}
                  onChange={(e) => setNewRate({ ...newRate, metal_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="GOLD_22K">22K Gold</option>
                  <option value="GOLD_24K">24K Gold</option>
                  <option value="GOLD_18K">18K Gold</option>
                  <option value="SILVER_999">999 Silver</option>
                  <option value="SILVER_925">925 Silver</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Rate per Gram (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="6850.00"
                    value={newRate.rate_per_gram}
                    onChange={(e) => setNewRate({ ...newRate, rate_per_gram: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">As of Date</label>
                  <input
                    type="date"
                    required
                    value={newRate.as_of_date}
                    onChange={(e) => setNewRate({ ...newRate, as_of_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Source / Reference</label>
                <input
                  type="text"
                  required
                  placeholder="IBJA, GRT Jewellers, Local Jeweller quote..."
                  value={newRate.source}
                  onChange={(e) => setNewRate({ ...newRate, source: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddRateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Save Rate Quote
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

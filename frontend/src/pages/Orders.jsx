import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { formatINR, formatISTDate } from '../utils/formatters';

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [merchantFilter, setMerchantFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [unlinkedOnly, setUnlinkedOnly] = useState(false);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showReturnModal, setShowReturnModal] = useState(null); // holds target order

  // Form states
  const [newOrder, setNewOrder] = useState({
    merchant_name: '',
    order_number: '',
    order_date: new Date().toISOString().split('T')[0],
    status: 'PLACED',
    total_amount: '',
    notes: '',
    items: [{ name: '', quantity: 1, unit_price: '', total_price: '' }],
  });

  const [returnForm, setReturnForm] = useState({
    item_id: '',
    return_date: new Date().toISOString().split('T')[0],
    refund_amount: '',
    reason: '',
    notes: '',
    create_refund_transaction: false,
    refund_account_id: '',
  });

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const params = {};
      if (merchantFilter) params.merchant_name = merchantFilter;
      if (statusFilter) params.status = statusFilter;
      if (unlinkedOnly) params.unlinked_only = true;

      const [resOrders, resAccounts] = await Promise.all([
        apiClient.get('/orders', { params }),
        apiClient.get('/accounts'),
      ]);
      setOrders(resOrders.data);
      setAccounts(resAccounts.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load orders.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [merchantFilter, statusFilter, unlinkedOnly]);

  const handleAddItemRow = () => {
    setNewOrder({
      ...newOrder,
      items: [...newOrder.items, { name: '', quantity: 1, unit_price: '', total_price: '' }],
    });
  };

  const handleItemChange = (index, field, value) => {
    const updated = [...newOrder.items];
    updated[index][field] = value;
    if (field === 'quantity' || field === 'unit_price') {
      const q = parseFloat(field === 'quantity' ? value : updated[index].quantity) || 0;
      const p = parseFloat(field === 'unit_price' ? value : updated[index].unit_price) || 0;
      updated[index].total_price = (q * p).toFixed(2);
    }
    setNewOrder({ ...newOrder, items: updated });
  };

  const handleCreateOrder = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        merchant_name: newOrder.merchant_name,
        order_number: newOrder.order_number || null,
        order_date: newOrder.order_date,
        status: newOrder.status,
        total_amount: parseFloat(newOrder.total_amount),
        notes: newOrder.notes || null,
        items: newOrder.items
          .filter((it) => it.name.trim() !== '')
          .map((it) => ({
            name: it.name,
            quantity: parseInt(it.quantity, 10),
            unit_price: parseFloat(it.unit_price || 0),
            total_price: parseFloat(it.total_price || 0),
          })),
      };

      await apiClient.post('/orders', payload);
      setShowAddModal(false);
      setNewOrder({
        merchant_name: '',
        order_number: '',
        order_date: new Date().toISOString().split('T')[0],
        status: 'PLACED',
        total_amount: '',
        notes: '',
        items: [{ name: '', quantity: 1, unit_price: '', total_price: '' }],
      });
      fetchOrders();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error creating order.');
    }
  };

  const handleProcessReturn = async (e) => {
    e.preventDefault();
    if (!showReturnModal) return;

    try {
      const payload = {
        item_id: returnForm.item_id || null,
        return_date: returnForm.return_date,
        refund_amount: parseFloat(returnForm.refund_amount),
        reason: returnForm.reason,
        notes: returnForm.notes || null,
        create_refund_transaction: returnForm.create_refund_transaction,
        refund_account_id: returnForm.create_refund_transaction ? returnForm.refund_account_id : null,
      };

      await apiClient.post(`/orders/${showReturnModal.id}/returns`, payload);
      setShowReturnModal(null);
      setReturnForm({
        item_id: '',
        return_date: new Date().toISOString().split('T')[0],
        refund_amount: '',
        reason: '',
        notes: '',
        create_refund_transaction: false,
        refund_account_id: '',
      });
      fetchOrders();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error processing return.');
    }
  };

  const totalSpent = orders.reduce((sum, o) => sum + parseFloat(o.total_amount), 0);
  const unlinkedCount = orders.filter((o) => !o.is_payment_linked).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Shopping Orders & Returns</h1>
          <p className="text-sm text-gray-500">
            Itemized e-commerce tracking with anti-double-counting reconciliation.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
        >
          + Record Order
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Total Recorded Orders</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">{orders.length}</p>
        </div>
        <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Order Value</p>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{formatINR(totalSpent)}</p>
        </div>
        <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Payment Unlinked</p>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-2xl font-bold text-amber-600">{unlinkedCount}</span>
            <span className="text-xs text-gray-400">Not double-counted in ledger</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm flex flex-wrap gap-4 items-center">
        <input
          type="text"
          placeholder="Filter by merchant (Amazon, Blinkit...)"
          value={merchantFilter}
          onChange={(e) => setMerchantFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500 w-64"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
        >
          <option value="">All Statuses</option>
          <option value="PLACED">Placed</option>
          <option value="SHIPPED">Shipped</option>
          <option value="DELIVERED">Delivered</option>
          <option value="PARTIALLY_RETURNED">Partially Returned</option>
          <option value="RETURNED">Returned</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
        <label className="flex items-center space-x-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={unlinkedOnly}
            onChange={(e) => setUnlinkedOnly(e.target.checked)}
            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span>Show Unlinked Only</span>
        </label>
      </div>

      {/* Orders List */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading orders...</div>
      ) : error ? (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
      ) : orders.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-gray-100 text-gray-500">
          No shopping orders found.
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <div key={order.id} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-gray-100 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-50/50">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-gray-900">{order.merchant_name}</h3>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        order.status === 'DELIVERED'
                          ? 'bg-green-100 text-green-800'
                          : order.status === 'RETURNED'
                          ? 'bg-red-100 text-red-800'
                          : order.status === 'PARTIALLY_RETURNED'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {order.status}
                    </span>
                    {order.is_payment_linked ? (
                      <span className="bg-emerald-50 text-emerald-700 text-xs px-2 py-0.5 rounded border border-emerald-200">
                        ✓ Payment Linked
                      </span>
                    ) : (
                      <span className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">
                        Unlinked
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Order #{order.order_number || 'N/A'} • {order.order_date} • Recorded by {order.user_name || 'Family Member'}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-xs text-gray-500">Total Amount</p>
                    <p className="text-lg font-bold text-gray-900">{formatINR(order.total_amount)}</p>
                  </div>
                  {order.status !== 'RETURNED' && order.status !== 'CANCELLED' && (
                    <button
                      onClick={() => setShowReturnModal(order)}
                      className="px-3 py-1.5 border border-red-200 text-red-600 hover:bg-red-50 text-xs font-medium rounded-lg"
                    >
                      Record Return
                    </button>
                  )}
                </div>
              </div>

              {/* Items Table */}
              <div className="p-5">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Item Breakdown</h4>
                {order.items.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No item details recorded.</p>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {order.items.map((item) => (
                      <div key={item.id} className="py-2.5 flex items-center justify-between text-sm">
                        <div>
                          <span className="font-medium text-gray-800">{item.name}</span>
                          <span className="text-gray-400 ml-2">× {item.quantity}</span>
                          {item.status === 'RETURNED' && (
                            <span className="ml-2 text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                              Returned
                            </span>
                          )}
                        </div>
                        <span className="font-medium text-gray-900">{formatINR(item.total_price)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Returns section */}
                {order.returns && order.returns.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-100 bg-amber-50/30 p-3 rounded-lg">
                    <h5 className="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-2">Returns & Refunds</h5>
                    <div className="space-y-1">
                      {order.returns.map((ret) => (
                        <div key={ret.id} className="flex justify-between text-xs text-amber-900">
                          <span>
                            {ret.return_date}: {ret.reason} ({ret.refund_status})
                          </span>
                          <span className="font-semibold text-red-600">-{formatINR(ret.refund_amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Order Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Record Shopping Order</h2>
            <form onSubmit={handleCreateOrder} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Merchant / Store Name</label>
                <input
                  type="text"
                  required
                  placeholder="Amazon, Flipkart, Swiggy Instamart, Zepto..."
                  value={newOrder.merchant_name}
                  onChange={(e) => setNewOrder({ ...newOrder, merchant_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Order Number (Optional)</label>
                  <input
                    type="text"
                    placeholder="402-1234567..."
                    value={newOrder.order_number}
                    onChange={(e) => setNewOrder({ ...newOrder, order_number: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Order Date</label>
                  <input
                    type="date"
                    required
                    value={newOrder.order_date}
                    onChange={(e) => setNewOrder({ ...newOrder, order_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Total Order Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={newOrder.total_amount}
                    onChange={(e) => setNewOrder({ ...newOrder, total_amount: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Status</label>
                  <select
                    value={newOrder.status}
                    onChange={(e) => setNewOrder({ ...newOrder, status: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="PLACED">Placed</option>
                    <option value="SHIPPED">Shipped</option>
                    <option value="DELIVERED">Delivered</option>
                    <option value="CANCELLED">Cancelled</option>
                  </select>
                </div>
              </div>

              {/* Items */}
              <div className="pt-2">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-semibold text-gray-700 uppercase">Items Breakdown</label>
                  <button
                    type="button"
                    onClick={handleAddItemRow}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                  >
                    + Add Item
                  </button>
                </div>
                <div className="space-y-2">
                  {newOrder.items.map((it, idx) => (
                    <div key={idx} className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Item name"
                        value={it.name}
                        onChange={(e) => handleItemChange(idx, 'name', e.target.value)}
                        className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs"
                      />
                      <input
                        type="number"
                        min="1"
                        placeholder="Qty"
                        value={it.quantity}
                        onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                        className="w-14 px-2 py-1.5 border border-gray-300 rounded-lg text-xs"
                      />
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Price"
                        value={it.unit_price}
                        onChange={(e) => handleItemChange(idx, 'unit_price', e.target.value)}
                        className="w-20 px-2 py-1.5 border border-gray-300 rounded-lg text-xs"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Save Order
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Record Return Modal */}
      {showReturnModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Record Return & Refund</h2>
            <p className="text-xs text-gray-500 mb-4">{showReturnModal.merchant_name} (Order #{showReturnModal.order_number || 'N/A'})</p>

            <form onSubmit={handleProcessReturn} className="space-y-4">
              {showReturnModal.items.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Target Item (Optional)</label>
                  <select
                    value={returnForm.item_id}
                    onChange={(e) => setReturnForm({ ...returnForm, item_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="">Whole Order / General Return</option>
                    {showReturnModal.items.map((it) => (
                      <option key={it.id} value={it.id}>
                        {it.name} ({formatINR(it.total_price)})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Refund Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={returnForm.refund_amount}
                    onChange={(e) => setReturnForm({ ...returnForm, refund_amount: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Return Date</label>
                  <input
                    type="date"
                    required
                    value={returnForm.return_date}
                    onChange={(e) => setReturnForm({ ...returnForm, return_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Reason for Return</label>
                <input
                  type="text"
                  required
                  placeholder="Defective, wrong size, late delivery..."
                  value={returnForm.reason}
                  onChange={(e) => setReturnForm({ ...returnForm, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={returnForm.create_refund_transaction}
                    onChange={(e) => setReturnForm({ ...returnForm, create_refund_transaction: e.target.checked })}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-xs font-medium text-gray-800">
                    Create Reconciled REFUND Ledger Transaction
                  </span>
                </label>
                <p className="text-xs text-gray-500 mt-1 pl-6">
                  Credits your bank account and accurately decreases household net spend.
                </p>

                {returnForm.create_refund_transaction && (
                  <div className="mt-3 pl-6">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Account Receiving Refund</label>
                    <select
                      required
                      value={returnForm.refund_account_id}
                      onChange={(e) => setReturnForm({ ...returnForm, refund_account_id: e.target.value })}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs"
                    >
                      <option value="">Select receiving account...</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name} ({a.account_type})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowReturnModal(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium shadow-sm"
                >
                  Confirm Return
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

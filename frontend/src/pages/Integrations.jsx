import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  ShieldCheck,
  Lock,
  Smartphone,
  Mail,
  Building2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  Plus,
  RefreshCw,
} from 'lucide-react';

export default function Integrations() {
  const [consents, setConsents] = useState([]);
  const [inboxItems, setInboxItems] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // SMS parse form state
  const [smsText, setSmsText] = useState('');
  const [smsSender, setSmsSender] = useState('HDFCBK');
  const [parseLoading, setParseLoading] = useState(false);

  // Receipt parse form state
  const [receiptText, setReceiptText] = useState('');
  const [receiptSource, setReceiptSource] = useState('');

  // Selected account for accepting an item
  const [selectedAccounts, setSelectedAccounts] = useState({});

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [consentRes, inboxRes, accRes] = await Promise.all([
        axios.get('/api/v1/integrations/consents'),
        axios.get('/api/v1/integrations/inbox'),
        axios.get('/api/v1/accounts'),
      ]);
      setConsents(consentRes.data);
      setInboxItems(inboxRes.data);
      setAccounts(accRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load integration data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleGrantConsent = async (provider) => {
    try {
      await axios.post('/api/v1/integrations/consents', {
        provider,
        scopes: 'read_only',
        auth_token: 'local_client_token_' + Date.now(),
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to grant consent');
    }
  };

  const handleRevokeConsent = async (provider) => {
    if (!confirm(`Are you sure you want to revoke consent for ${provider}? Stored tokens will be erased immediately.`)) return;
    try {
      await axios.delete(`/api/v1/integrations/consents/${provider}`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to revoke consent');
    }
  };

  const handleParseSms = async (e) => {
    e.preventDefault();
    if (!smsText.trim()) return;
    try {
      setParseLoading(true);
      await axios.post('/api/v1/integrations/parse-sms', {
        sms_text: smsText,
        sender: smsSender,
      });
      setSmsText('');
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'SMS parse failed. Verify active consent.');
    } finally {
      setParseLoading(false);
    }
  };

  const handleParseReceipt = async (e) => {
    e.preventDefault();
    if (!receiptText.trim()) return;
    try {
      setParseLoading(true);
      await axios.post('/api/v1/integrations/parse-receipt', {
        receipt_text: receiptText,
        source_identifier: receiptSource || 'receipt_' + Date.now(),
      });
      setReceiptText('');
      setReceiptSource('');
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Receipt parse failed. Verify active consent.');
    } finally {
      setParseLoading(false);
    }
  };

  const handleAcceptItem = async (itemId) => {
    const targetAccountId = selectedAccounts[itemId] || accounts[0]?.id;
    if (!targetAccountId) {
      alert('Please select a financial account to charge');
      return;
    }
    try {
      await axios.post(`/api/v1/integrations/inbox/${itemId}/accept`, {
        account_id: targetAccountId,
      });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to accept item');
    }
  };

  const handleDismissItem = async (itemId) => {
    try {
      await axios.post(`/api/v1/integrations/inbox/${itemId}/dismiss`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to dismiss item');
    }
  };

  const isConsentActive = (provider) => {
    const c = consents.find((x) => x.provider === provider);
    return c && c.is_active;
  };

  const pendingItems = inboxItems.filter((i) => i.status === 'PENDING_REVIEW');
  const pastItems = inboxItems.filter((i) => i.status !== 'PENDING_REVIEW');

  return (
    <div className="space-y-6">
      {/* Privacy Guarantee Banner */}
      <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-5 flex items-start space-x-4">
        <ShieldCheck className="w-8 h-8 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <h2 className="text-base font-semibold text-emerald-200">
            Privacy-First Architecture (Zero External AI Leak)
          </h2>
          <p className="text-sm text-emerald-300/80 mt-1">
            All integrations operate under strict local parsing. No raw SMS or statements are ever
            transmitted to third-party AI models or external servers. Credentials are protected
            with AES-256-GCM encryption, and revoking consent immediately wipes cryptographic keys.
          </p>
        </div>
      </div>

      {/* Consents Management */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Android SMS */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-blue-600/20 text-blue-400">
                <Smartphone className="w-5 h-5" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  isConsentActive('ANDROID_SMS_SYNC')
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {isConsentActive('ANDROID_SMS_SYNC') ? 'Active' : 'Not Granted'}
              </span>
            </div>
            <h3 className="font-semibold text-slate-100">Android SMS Sync</h3>
            <p className="text-xs text-slate-400 mt-1">
              Local parsing of bank debit SMS. OTPs and sensitive passwords are never retained.
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-800">
            {isConsentActive('ANDROID_SMS_SYNC') ? (
              <button
                onClick={() => handleRevokeConsent('ANDROID_SMS_SYNC')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-rose-600/20 text-rose-300 hover:bg-rose-600/30 border border-rose-500/30 transition"
              >
                Revoke Consent & Wipe Tokens
              </button>
            ) : (
              <button
                onClick={() => handleGrantConsent('ANDROID_SMS_SYNC')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition"
              >
                Grant Explicit Consent
              </button>
            )}
          </div>
        </div>

        {/* Gmail Receipts */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-amber-600/20 text-amber-400">
                <Mail className="w-5 h-5" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  isConsentActive('GMAIL_RECEIPTS')
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {isConsentActive('GMAIL_RECEIPTS') ? 'Active' : 'Not Granted'}
              </span>
            </div>
            <h3 className="font-semibold text-slate-100">Gmail E-Commerce Receipts</h3>
            <p className="text-xs text-slate-400 mt-1">
              Local extraction of order totals from Amazon, Flipkart, and Swiggy receipt emails.
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-800">
            {isConsentActive('GMAIL_RECEIPTS') ? (
              <button
                onClick={() => handleRevokeConsent('GMAIL_RECEIPTS')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-rose-600/20 text-rose-300 hover:bg-rose-600/30 border border-rose-500/30 transition"
              >
                Revoke Consent & Wipe Tokens
              </button>
            ) : (
              <button
                onClick={() => handleGrantConsent('GMAIL_RECEIPTS')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium transition"
              >
                Grant Explicit Consent
              </button>
            )}
          </div>
        </div>

        {/* Account Aggregator */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-indigo-600/20 text-indigo-400">
                <Building2 className="w-5 h-5" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  isConsentActive('ACCOUNT_AGGREGATOR')
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {isConsentActive('ACCOUNT_AGGREGATOR') ? 'Active' : 'Not Granted'}
              </span>
            </div>
            <h3 className="font-semibold text-slate-100">Account Aggregator (RBI)</h3>
            <p className="text-xs text-slate-400 mt-1">
              Read-only statement feeds via Sahamati framework with time-bounded permissions.
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-800">
            {isConsentActive('ACCOUNT_AGGREGATOR') ? (
              <button
                onClick={() => handleRevokeConsent('ACCOUNT_AGGREGATOR')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-rose-600/20 text-rose-300 hover:bg-rose-600/30 border border-rose-500/30 transition"
              >
                Revoke Consent & Wipe Tokens
              </button>
            ) : (
              <button
                onClick={() => handleGrantConsent('ACCOUNT_AGGREGATOR')}
                className="w-full text-xs py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition"
              >
                Grant Explicit Consent
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Local Parsing Simulator Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* SMS Parser Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-100 mb-2 flex items-center space-x-2">
            <Smartphone className="w-4 h-4 text-blue-400" />
            <span>Parse Bank SMS (Local Regex)</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Simulate or sync incoming SMS debit alert from Indian banks (HDFC, SBI, ICICI, Axis).
          </p>
          <form onSubmit={handleParseSms} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Sender ID</label>
              <input
                type="text"
                value={smsSender}
                onChange={(e) => setSmsSender(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                placeholder="e.g. HDFCBK or SBIINB"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">SMS Text</label>
              <textarea
                value={smsText}
                onChange={(e) => setSmsText(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                placeholder="Paste SMS e.g.: Rs. 450.00 debited from A/C **1234 to SWIGGY on 07-11-26. Avl Bal Rs 52,100.00"
              />
            </div>
            <button
              type="submit"
              disabled={parseLoading || !smsText.trim()}
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition"
            >
              Parse SMS Locally
            </button>
          </form>
        </div>

        {/* Receipt Parser Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-100 mb-2 flex items-center space-x-2">
            <FileText className="w-4 h-4 text-amber-400" />
            <span>Parse Receipt Text (Local Extraction)</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Extract grand total and merchant from email receipt or shopping summary locally.
          </p>
          <form onSubmit={handleParseReceipt} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Reference / Order ID</label>
              <input
                type="text"
                value={receiptSource}
                onChange={(e) => setReceiptSource(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-amber-500"
                placeholder="e.g. Amazon Order #402-1234"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Receipt Content</label>
              <textarea
                value={receiptText}
                onChange={(e) => setReceiptText(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-amber-500"
                placeholder="Paste receipt snippet with Total: Rs. 1,499.00"
              />
            </div>
            <button
              type="submit"
              disabled={parseLoading || !receiptText.trim()}
              className="w-full py-2 px-4 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition"
            >
              Parse Receipt Locally
            </button>
          </form>
        </div>
      </div>

      {/* Staged Draft Items Inbox (Human Review Required) */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-slate-100">Review Inbox (Staged Drafts)</h3>
            <p className="text-xs text-slate-400 mt-1">
              Parsed items remain in draft state until confirmed by a family member.
            </p>
          </div>
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {pendingItems.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">
            No pending items. Parsed SMS and receipts awaiting your review will appear here.
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {pendingItems.map((item) => (
              <div key={item.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                      {item.item_type}
                    </span>
                    <span className="text-sm font-semibold text-white">
                      {item.parsed_merchant || 'Unknown Merchant'}
                    </span>
                    {item.parsed_account_last4 && (
                      <span className="text-xs text-slate-400">
                        (A/C ending **{item.parsed_account_last4})
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 font-mono truncate max-w-lg">
                    {item.raw_snippet}
                  </div>
                  <div className="text-xs text-slate-500">Date: {item.parsed_date}</div>
                </div>

                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <span className="text-lg font-bold text-rose-400 font-mono">
                      ₹{Number(item.parsed_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <select
                      value={selectedAccounts[item.id] || accounts[0]?.id || ''}
                      onChange={(e) =>
                        setSelectedAccounts({ ...selectedAccounts, [item.id]: e.target.value })
                      }
                      className="px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white"
                    >
                      {accounts.map((acc) => (
                        <option key={acc.id} value={acc.id}>
                          {acc.name}
                        </option>
                      ))}
                    </select>

                    <button
                      onClick={() => handleAcceptItem(item.id)}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg transition"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => handleDismissItem(item.id)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-medium rounded-lg transition"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

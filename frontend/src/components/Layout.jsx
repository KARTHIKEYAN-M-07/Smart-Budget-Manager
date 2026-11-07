import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  PieChart,
  LogOut,
  PlusCircle,
  Menu,
  X,
  Shield,
  Layers,
  Target,
  ShoppingBag,
  Coins,
  TrendingUp,
  ShieldCheck,
} from 'lucide-react';
import QuickAddModal from './QuickAddModal';
import NotificationBell from './NotificationBell';

export default function Layout() {
  const { user, household, role, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: t('nav.dashboard', 'Dashboard'), icon: LayoutDashboard },
    { to: '/accounts', label: t('nav.accounts', 'Accounts'), icon: Wallet },
    { to: '/transactions', label: t('nav.transactions', 'Transactions'), icon: ArrowLeftRight },
    { to: '/budgets', label: 'Budgets & Goals', icon: Target },
    { to: '/orders', label: 'Shopping Orders', icon: ShoppingBag },
    { to: '/metals', label: 'Gold & Silver', icon: Coins },
    { to: '/investments', label: 'Investments', icon: TrendingUp },
    { to: '/integrations', label: 'Integrations', icon: ShieldCheck },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      {/* Quick Add Modal */}
      <QuickAddModal
        isOpen={quickAddOpen}
        onClose={() => setQuickAddOpen(false)}
        onSuccess={() => {
          // Trigger a custom event so active pages can re-fetch data smoothly
          window.dispatchEvent(new Event('sfbm_data_updated'));
        }}
      />

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 flex-col bg-slate-900 text-slate-100 min-h-screen sticky top-0 shadow-lg z-20">
        <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center font-bold text-xl text-white shadow-md">
            ₹
          </div>
          <div>
            <h1 className="font-bold text-sm leading-tight text-white tracking-wide">
              Family Budget
            </h1>
            <p className="text-xs text-slate-400 truncate max-w-[140px]">
              {household?.name || 'Household'}
            </p>
          </div>
        </div>

        {/* Quick Add Button */}
        <div className="p-4">
          <button
            onClick={() => setQuickAddOpen(true)}
            className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-medium rounded-lg shadow-sm transition text-sm"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Add Transaction</span>
          </button>
        </div>

        {/* Nav Links */}
        <nav className="flex-1 px-3 space-y-1 py-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-semibold text-white">
                {user?.full_name?.charAt(0) || 'U'}
              </div>
              <div className="truncate max-w-[120px]">
                <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name}</p>
                <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-emerald-400 border border-slate-700">
                  {role}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded-lg text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-red-400 transition border border-slate-800"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Log Out</span>
          </button>
        </div>
      </aside>

      {/* Mobile Top Header */}
      <header className="md:hidden bg-slate-900 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-30 shadow-md">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center font-bold text-base text-white">
            ₹
          </div>
          <div>
            <h1 className="font-bold text-sm leading-none text-white">Family Budget</h1>
            <p className="text-[11px] text-slate-400">{household?.name}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <NotificationBell />
          <button
            onClick={() => setQuickAddOpen(true)}
            className="p-1.5 bg-emerald-600 rounded-lg text-white"
            aria-label="Add transaction"
          >
            <PlusCircle className="w-5 h-5" />
          </button>
          <button
            onClick={handleLogout}
            className="p-1.5 text-slate-400 hover:text-red-400"
            aria-label="Logout"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        <header className="hidden md:flex items-center justify-between px-8 py-3.5 bg-white border-b border-gray-100 shadow-2xs">
          <div className="text-xs text-gray-400 font-medium">
            Smart Family Budget Manager • ₹ INR • Asia/Kolkata
          </div>
          <div className="flex items-center space-x-3">
            <NotificationBell />
          </div>
        </header>
        <main className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 px-3 py-2 flex items-center justify-around z-30 shadow-lg">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center py-1 px-3 text-xs font-medium rounded-lg transition ${
                  isActive ? 'text-emerald-600 font-semibold' : 'text-slate-500 hover:text-slate-800'
                }`
              }
            >
              <Icon className="w-5 h-5 mb-0.5" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}

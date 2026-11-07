import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Accounts from './pages/Accounts';
import Transactions from './pages/Transactions';
import Dashboard from './pages/Dashboard';
import StatementImport from './pages/StatementImport';
import Budgets from './pages/Budgets';
import Orders from './pages/Orders';
import PreciousMetals from './pages/PreciousMetals';
import Investments from './pages/Investments';
import Integrations from './pages/Integrations';
import './i18n';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Application Routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/accounts" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="accounts" element={<Accounts />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="budgets" element={<Budgets />} />
            <Route path="orders" element={<Orders />} />
            <Route path="metals" element={<PreciousMetals />} />
            <Route path="investments" element={<Investments />} />
            <Route path="integrations" element={<Integrations />} />
            <Route path="import" element={<StatementImport />} />
          </Route>

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/accounts" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

import React, { createContext, useContext, useState, useEffect } from 'react';
import api, { setCsrfToken } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [household, setHousehold] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check current session on initial page load
  const checkSession = async () => {
    try {
      const res = await api.get('/auth/me');
      setUser(res.data.user);
      setHousehold(res.data.household);
      setRole(res.data.role);
      if (res.data.csrf_token) {
        setCsrfToken(res.data.csrf_token);
      }
    } catch {
      setUser(null);
      setHousehold(null);
      setRole(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    setUser(res.data.user);
    setHousehold(res.data.household);
    setRole(res.data.role);
    if (res.data.csrf_token) {
      setCsrfToken(res.data.csrf_token);
    }
    return res.data;
  };

  const register = async ({ email, password, fullName, householdName }) => {
    const res = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
      household_name: householdName,
    });
    setUser(res.data.user);
    setHousehold(res.data.household);
    setRole(res.data.role);
    if (res.data.csrf_token) {
      setCsrfToken(res.data.csrf_token);
    }
    return res.data;
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } finally {
      setUser(null);
      setHousehold(null);
      setRole(null);
      setCsrfToken(null);
    }
  };

  const logoutAll = async () => {
    try {
      await api.post('/auth/logout-all');
    } finally {
      setUser(null);
      setHousehold(null);
      setRole(null);
      setCsrfToken(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        household,
        role,
        loading,
        login,
        register,
        logout,
        logoutAll,
        refreshSession: checkSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

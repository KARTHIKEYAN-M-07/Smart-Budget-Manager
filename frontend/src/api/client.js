import axios from 'axios';

let csrfToken = null;

export function setCsrfToken(token) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // Send HttpOnly session cookie
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to inject CSRF token on state-changing methods
api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method) && csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

// Response interceptor to catch CSRF tokens in responses
api.interceptors.response.use(
  (response) => {
    if (response.data && response.data.csrf_token) {
      setCsrfToken(response.data.csrf_token);
    }
    return response;
  },
  (error) => {
    // Return structured error message
    const message =
      error.response?.data?.detail ||
      error.response?.data?.error ||
      error.message ||
      'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

export default api;

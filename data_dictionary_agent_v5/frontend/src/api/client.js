/**
 * API client – single source of truth for backend communication.
 */
import axios from 'axios';

const API_KEY = localStorage.getItem('dd_api_key') || 'change-me-in-production';

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
});

// Attach API key to every request
api.interceptors.request.use((config) => {
  const key = localStorage.getItem('dd_api_key') || API_KEY;
  config.headers['X-API-Key'] = key;
  return config;
});

// ── Connection ──
export const connectDb = (payload) => api.post('/api/connect', payload).then(r => r.data);
export const connectSample = () => api.post('/api/connect-sample').then(r => r.data);
export const disconnectDb = (sessionId) => api.post(`/api/disconnect?session_id=${sessionId}`).then(r => r.data);

// ── Schema ──
export const getOverview = (sid) => api.get(`/api/schema/${sid}/overview`).then(r => r.data);
export const getSchema = (sid, page = 1, pageSize = 50) =>
  api.get(`/api/schema/${sid}`, { params: { page, page_size: pageSize } }).then(r => r.data);
export const getTableDetail = (sid, tableName) =>
  api.get(`/api/schema/${sid}/table/${tableName}`).then(r => r.data);

// ── Quality ──
export const analyzeQuality = (sessionId, tableName = null) =>
  api.post('/api/quality/analyze', { session_id: sessionId, table_name: tableName }).then(r => r.data);

// ── AI ──
export const generateAISummary = (sessionId, tableName = null) =>
  api.post('/api/ai/summary', { session_id: sessionId, table_name: tableName }).then(r => r.data);

// ── Chat ──
export const chatWithDb = (sessionId, question, history = []) =>
  api.post('/api/chat', { session_id: sessionId, question, conversation_history: history }).then(r => r.data);

// ── Export ──
export const exportDocs = (sessionId, format) =>
  api.post('/api/export', { session_id: sessionId, format }).then(r => r.data);

// ── Sample Data ──
export const getSampleData = (sid, tableName, limit = 100) =>
  api.get(`/api/sample-data/${sid}/${tableName}`, { params: { limit } }).then(r => r.data);

// ── Info ──
export const getSupportedDbs = () => api.get('/api/supported-databases').then(r => r.data);

export default api;

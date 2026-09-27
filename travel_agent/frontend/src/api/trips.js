import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function planTrip(query, sessionId = null) {
  const response = await api.post('/api/travel/trips/plan', { query, session_id: sessionId });
  return response.data;
}

export async function tripChat(sessionId, message) {
  const response = await api.post(`/api/travel/trips/${sessionId}/chat`, { message });
  return response.data;
}

export async function getTrip(sessionId) {
  const response = await api.get(`/api/travel/trips/${sessionId}`);
  return response.data;
}

export async function deleteTrip(sessionId) {
  const response = await api.delete(`/api/travel/trips/${sessionId}`);
  return response.data;
}

import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function searchFlights(query) {
  const response = await api.post('/api/travel/flights/search', { query });
  return response.data;
}

export async function checkHealth() {
  const response = await api.get('/health');
  return response.data;
}

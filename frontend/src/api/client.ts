import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
})

// Normalize errors so components always get { detail: string }
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail =
      error.response?.data?.detail ||
      error.message ||
      'Erro desconhecido. Tente novamente.'
    return Promise.reject({ detail, available: error.response?.data?.available, status: error.response?.status })
  }
)

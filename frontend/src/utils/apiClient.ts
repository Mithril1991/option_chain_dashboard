import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8061'

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any authentication tokens here if needed
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - Extract data from response
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Return the data directly instead of the full response
    return response
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      console.error('Unauthorized access')
    }

    if (error.response?.status === 500) {
      // Handle server errors
      console.error('Server error:', error.response?.data)
    }

    return Promise.reject(error)
  }
)

export default apiClient
export { API_BASE_URL }

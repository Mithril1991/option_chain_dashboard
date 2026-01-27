import { useState, useEffect, useCallback, useRef } from 'react'
import apiClient from '@utils/apiClient'
import type {
  HealthResponse,
  ScanResponse,
  AlertResponse,
  AlertSummaryResponse,
  ChainSnapshot,
  FeatureResponse
} from '@types/api'

/**
 * Generic hook options
 */
interface UseApiOptions {
  immediate?: boolean
  dependencies?: unknown[]
  onSuccess?: (data: unknown) => void
  onError?: (error: Error) => void
  interval?: number // Auto-refetch interval in milliseconds
}

/**
 * Generic API state
 */
interface UseApiState<T> {
  data: T | null
  loading: boolean
  error: Error | null
}

/**
 * Generic GET hook with auto-refetch support
 */
export const useApi = <T,>(
  url: string,
  options: UseApiOptions = {}
): UseApiState<T> & { refetch: () => Promise<void> } => {
  const { immediate = true, dependencies = [], onSuccess, onError, interval } = options
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null
  })

  const fetchData = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const response = await apiClient.get<T>(url)
      setState({ data: response.data, loading: false, error: null })
      onSuccess?.(response.data)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error')
      setState({ data: null, loading: false, error })
      onError?.(error)
    }
  }, [url, onSuccess, onError])

  useEffect(() => {
    if (immediate) {
      fetchData()
    }

    if (interval && interval > 0) {
      intervalRef.current = setInterval(fetchData, interval)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [immediate, fetchData, interval, ...dependencies])

  return {
    ...state,
    refetch: fetchData
  }
}

/**
 * POST hook for executing mutations
 */
export const useApiPost = <T, R = unknown>(
  url: string
): {
  execute: (data: T) => Promise<R>
  loading: boolean
  error: Error | null
  data: R | null
} => {
  const [state, setState] = useState({
    loading: false,
    error: null as Error | null,
    data: null as R | null
  })

  const execute = useCallback(
    async (data: T) => {
      setState({ loading: true, error: null, data: null })
      try {
        const response = await apiClient.post<R>(url, data)
        setState({ loading: false, error: null, data: response.data })
        return response.data
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error')
        setState({ loading: false, error, data: null })
        throw error
      }
    },
    [url]
  )

  return {
    execute,
    ...state
  }
}

/**
 * PUT hook for updates
 */
export const useApiPut = <T, R = unknown>(
  url: string
): {
  execute: (data: T) => Promise<R>
  loading: boolean
  error: Error | null
  data: R | null
} => {
  const [state, setState] = useState({
    loading: false,
    error: null as Error | null,
    data: null as R | null
  })

  const execute = useCallback(
    async (data: T) => {
      setState({ loading: true, error: null, data: null })
      try {
        const response = await apiClient.put<R>(url, data)
        setState({ loading: false, error: null, data: response.data })
        return response.data
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error')
        setState({ loading: false, error, data: null })
        throw error
      }
    },
    [url]
  )

  return {
    execute,
    ...state
  }
}

/**
 * DELETE hook
 */
export const useApiDelete = (
  url: string
): {
  execute: () => Promise<void>
  loading: boolean
  error: Error | null
} => {
  const [state, setState] = useState({
    loading: false,
    error: null as Error | null
  })

  const execute = useCallback(async () => {
    setState({ loading: true, error: null })
    try {
      await apiClient.delete(url)
      setState({ loading: false, error: null })
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error')
      setState({ loading: false, error })
      throw error
    }
  }, [url])

  return {
    execute,
    ...state
  }
}

// ====== Domain-specific hooks ======

/**
 * Health check hook - polls every 30 seconds
 */
export const useHealthCheck = (): UseApiState<HealthResponse> & { refetch: () => Promise<void> } => {
  return useApi<HealthResponse>('/health', {
    immediate: true,
    interval: 30000 // 30 seconds
  })
}

/**
 * Fetch latest alerts with optional limit
 */
export const useLatestAlerts = (limit: number = 50): UseApiState<AlertResponse[]> & { refetch: () => Promise<void> } => {
  const url = `/alerts/latest?limit=${limit}`
  return useApi<AlertResponse[]>(url, { immediate: true })
}

/**
 * Fetch latest alert summaries (lightweight - no metrics field)
 * Optimized for dashboard performance - 3-5x faster than full alerts
 */
export const useLatestAlertsSummary = (limit: number = 20): UseApiState<AlertSummaryResponse[]> & { refetch: () => Promise<void> } => {
  const url = `/alerts/latest/summary?limit=${limit}`
  return useApi<AlertSummaryResponse[]>(url, { immediate: true })
}

/**
 * Fetch alerts for a specific ticker
 */
export const useAlertsByTicker = (ticker: string): UseApiState<AlertResponse[]> & { refetch: () => Promise<void> } => {
  const url = `/alerts?ticker=${ticker}`
  return useApi<AlertResponse[]>(url, {
    immediate: !!ticker,
    dependencies: [ticker]
  })
}

/**
 * Fetch options chain snapshot for a ticker
 */
export const useOptionChain = (ticker: string): UseApiState<ChainSnapshot> & { refetch: () => Promise<void> } => {
  const url = `/options/${ticker}/snapshot`
  return useApi<ChainSnapshot>(url, {
    immediate: !!ticker,
    dependencies: [ticker]
  })
}

/**
 * Fetch latest feature data for a ticker
 */
export const useFeatures = (ticker: string): UseApiState<FeatureResponse> & { refetch: () => Promise<void> } => {
  const url = `/features/${ticker}/latest`
  return useApi<FeatureResponse>(url, {
    immediate: !!ticker,
    dependencies: [ticker]
  })
}

/**
 * Fetch scan status by ID
 */
export const useScanStatus = (scanId: number): UseApiState<ScanResponse> & { refetch: () => Promise<void> } => {
  const url = `/scan/status/${scanId}`
  return useApi<ScanResponse>(url, {
    immediate: scanId > 0,
    interval: 5000, // Poll every 5 seconds
    dependencies: [scanId]
  })
}

/**
 * Trigger a new scan execution
 */
export const useTriggerScan = (): {
  execute: () => Promise<ScanResponse>
  loading: boolean
  error: Error | null
  data: ScanResponse | null
} => {
  return useApiPost<never, ScanResponse>('/scan/run')
}

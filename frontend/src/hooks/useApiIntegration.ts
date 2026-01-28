/**
 * useApiIntegration.ts
 *
 * High-level integration hook that combines API calls with Zustand store management.
 * This hook provides a convenient way to fetch data and automatically update the store.
 *
 * Usage:
 * const { alerts, loading, error, refetch } = useApiIntegration.alerts()
 */

import { useEffect } from 'react'
import { useApiStore } from '@store/apiStore'
import {
  useHealthCheck,
  useLatestAlerts,
  useAlertsByTicker,
  useOptionChain,
  useFeatures,
  useScanStatus,
  useTriggerScan
} from './useApi'
import type { ScanResponse } from '@types/api'

/**
 * Combine health check hook with store management
 */
export const useHealthCheckIntegration = () => {
  const { health, healthLoading, healthError, setHealth, setHealthLoading, setHealthError } =
    useApiStore()
  const apiHealth = useHealthCheck()

  useEffect(() => {
    setHealthLoading(apiHealth.loading)
    setHealthError(apiHealth.error)
    if (apiHealth.data) {
      setHealth(apiHealth.data)
    }
  }, [apiHealth.data, apiHealth.loading, apiHealth.error, setHealth, setHealthLoading, setHealthError])

  return {
    health,
    loading: healthLoading,
    error: healthError,
    refetch: apiHealth.refetch
  }
}

/**
 * Combine latest alerts hook with store management
 */
export const useLatestAlertsIntegration = (limit: number = 50) => {
  const { latestAlerts, alertsLoading, alertsError, setLatestAlerts, setAlertsLoading, setAlertsError } =
    useApiStore()
  const apiAlerts = useLatestAlerts(limit)

  useEffect(() => {
    setAlertsLoading(apiAlerts.loading)
    setAlertsError(apiAlerts.error)
    if (apiAlerts.data) {
      setLatestAlerts(apiAlerts.data)
    }
  }, [apiAlerts.data, apiAlerts.loading, apiAlerts.error, setLatestAlerts, setAlertsLoading, setAlertsError])

  return {
    alerts: latestAlerts,
    loading: alertsLoading,
    error: alertsError,
    refetch: apiAlerts.refetch
  }
}

/**
 * Combine alerts by ticker hook with store management
 */
export const useAlertsByTickerIntegration = (ticker: string) => {
  const { alertsByTicker, alertsError, setAlertsByTicker, setAlertsError } = useApiStore()
  const apiAlerts = useAlertsByTicker(ticker)

  useEffect(() => {
    setAlertsError(apiAlerts.error)
    if (apiAlerts.data) {
      setAlertsByTicker(ticker, apiAlerts.data)
    }
  }, [apiAlerts.data, apiAlerts.error, ticker, setAlertsByTicker, setAlertsError])

  const alerts = useApiStore((state) => state.getAlertForTicker(ticker))

  return {
    alerts,
    loading: apiAlerts.loading,
    error: alertsError,
    refetch: apiAlerts.refetch
  }
}

/**
 * Combine option chain hook with store management
 */
export const useOptionChainIntegration = (ticker: string, expiration?: string) => {
  const { optionChains, chainsError, setOptionChain, setChainError } = useApiStore()
  const apiChain = useOptionChain(ticker, expiration)

  useEffect(() => {
    setChainError(ticker, apiChain.error)
    if (apiChain.data) {
      setOptionChain(ticker, apiChain.data)
    }
  }, [apiChain.data, apiChain.error, ticker, setOptionChain, setChainError])

  const chain = optionChains[ticker] || null
  const error = chainsError[ticker] || null

  return {
    chain,
    loading: apiChain.loading,
    error,
    refetch: apiChain.refetch
  }
}

/**
 * Combine features hook with store management
 */
export const useFeaturesIntegration = (ticker: string) => {
  const { features, featuresError, setFeatures, setFeaturesError } = useApiStore()
  const apiFeatures = useFeatures(ticker)

  useEffect(() => {
    setFeaturesError(ticker, apiFeatures.error)
    if (apiFeatures.data) {
      setFeatures(ticker, apiFeatures.data)
    }
  }, [apiFeatures.data, apiFeatures.error, ticker, setFeatures, setFeaturesError])

  const feature = features[ticker] || null
  const error = featuresError[ticker] || null

  return {
    features: feature,
    loading: apiFeatures.loading,
    error,
    refetch: apiFeatures.refetch
  }
}

/**
 * Combine scan status hook with store management
 */
export const useScanStatusIntegration = (scanId: number) => {
  const { scans, scansError, scansLoading, setScan, setScanError, setScanLoading } = useApiStore()
  const apiScan = useScanStatus(scanId)

  useEffect(() => {
    setScanLoading(scanId, apiScan.loading)
    setScanError(scanId, apiScan.error)
    if (apiScan.data) {
      setScan(scanId, apiScan.data)
    }
  }, [apiScan.data, apiScan.loading, apiScan.error, scanId, setScan, setScanError, setScanLoading])

  const scan = scans[scanId] || null
  const loading = scansLoading[scanId] || false
  const error = scansError[scanId] || null

  return {
    scan,
    loading,
    error,
    refetch: apiScan.refetch
  }
}

/**
 * Combine trigger scan hook with store management
 */
export const useTriggerScanIntegration = () => {
  const { setScan, setScanError, setScanLoading } = useApiStore()
  const { execute, loading, error, data } = useTriggerScan()

  const triggerScan = async (): Promise<ScanResponse | null> => {
    try {
      setScanLoading(0, true)
      const result = await execute()
      setScan(result.scan_id, result)
      setScanLoading(result.scan_id, false)
      return result
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to trigger scan')
      setScanError(0, error)
      setScanLoading(0, false)
      throw error
    }
  }

  return {
    triggerScan,
    loading,
    error,
    data
  }
}

/**
 * Integration config for components
 */
export const apiIntegration = {
  useHealthCheck: useHealthCheckIntegration,
  useLatestAlerts: useLatestAlertsIntegration,
  useAlertsByTicker: useAlertsByTickerIntegration,
  useOptionChain: useOptionChainIntegration,
  useFeatures: useFeaturesIntegration,
  useScanStatus: useScanStatusIntegration,
  useTriggerScan: useTriggerScanIntegration
}

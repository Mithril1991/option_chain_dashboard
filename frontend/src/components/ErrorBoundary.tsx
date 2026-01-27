import React, { Component, ReactNode } from 'react'

/**
 * Props for ErrorBoundary component
 */
interface Props {
  /** Child components to protect */
  children: ReactNode
  /** Optional: custom fallback UI */
  fallback?: ReactNode
  /** Optional: callback when error occurs */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
}

/**
 * State for ErrorBoundary component
 */
interface State {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
}

/**
 * Error Boundary Component - Error handling wrapper
 *
 * Features:
 * - Class component for error boundary functionality
 * - Catches rendering errors in child components
 * - Displays error message and details
 * - Retry button to reload page
 * - Console logging for debugging
 * - Customizable fallback UI
 * - Optional error callback hook
 * - Graceful error display with icon and styling
 * - Responsive design
 *
 * Error Flow:
 * 1. Child component throws error
 * 2. getDerivedStateFromError updates state
 * 3. componentDidCatch logs error and calls callback
 * 4. Fallback UI is rendered with error details
 * 5. User can retry by reloading page
 *
 * What It Catches:
 * - Rendering errors in components
 * - Lifecycle method errors
 * - Constructor errors in child components
 * - Errors in async components
 *
 * What It Does NOT Catch:
 * - Event handlers (use try-catch instead)
 * - Async code (use Promise.catch)
 * - Server-side rendering
 * - Errors in error boundary itself
 *
 * Usage:
 * - Wrap entire app or major sections
 * - Prevents white screen of death
 * - Provides user-friendly error display
 * - Helps with debugging in production
 *
 * @component
 * @example
 * ```tsx
 * <ErrorBoundary
 *   onError={(error, info) => {
 *     logErrorToService(error, info)
 *   }}
 * >
 *   <App />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    }
  }

  /**
   * Update state when error is caught
   * This is called during render phase
   */
  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error
    }
  }

  /**
   * Log error details to console and external services
   * This is called after error is caught
   */
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Update state with error details
    this.setState({
      errorInfo
    })

    // Log to console for debugging
    console.error('Error Boundary caught an error:', {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack
    })

    // Call optional error callback (for external logging services)
    if (this.props.onError) {
      try {
        this.props.onError(error, errorInfo)
      } catch (callbackError) {
        console.error('Error callback failed:', callbackError)
      }
    }
  }

  /**
   * Reset error boundary state
   */
  private resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
  }

  /**
   * Reload page (full page refresh)
   */
  private reloadPage = () => {
    window.location.reload()
  }

  /**
   * Render error UI or children
   */
  render() {
    // If error occurred, show fallback UI
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <div className="min-h-screen bg-gradient-to-br from-red-50 to-red-100 flex items-center justify-center p-4">
          <div className="card border-l-4 border-l-red-600 max-w-2xl w-full">
            {/* Error Icon and Title */}
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 text-red-600">
                <svg
                  className="w-8 h-8 sm:w-10 sm:h-10"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>

              <div className="flex-1">
                {/* Error Title */}
                <h2 className="text-lg sm:text-2xl font-bold text-red-900 mb-2">
                  Something went wrong
                </h2>

                {/* Error Message */}
                <p className="text-red-700 text-sm sm:text-base mb-4">
                  {this.state.error?.message ||
                    'An unexpected error occurred in the application'}
                </p>

                {/* Error Details (only in development or if detailed) */}
                {process.env.NODE_ENV === 'development' &&
                  this.state.errorInfo && (
                    <details className="mb-4">
                      <summary className="cursor-pointer text-red-600 hover:text-red-800 text-sm font-medium mb-2">
                        View Error Details
                      </summary>
                      <pre className="bg-red-50 border border-red-200 rounded p-3 text-xs overflow-auto max-h-40 text-red-900">
                        <code>
                          {this.state.errorInfo.componentStack}
                        </code>
                      </pre>
                    </details>
                  )}

                {/* Error Reference ID */}
                {process.env.NODE_ENV === 'production' && (
                  <p className="text-red-600 text-xs mb-4">
                    Error Reference:{' '}
                    <code className="bg-red-100 px-2 py-1 rounded font-mono">
                      {this.state.error?.message
                        ?.substring(0, 8)
                        .toUpperCase()
                        .replace(/[^A-Z0-9]/g, 'X') || 'ERR_UNKNOWN'}
                    </code>
                  </p>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={this.resetError}
                    className="btn-primary px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                    title="Try to recover from error"
                  >
                    Try Again
                  </button>

                  <button
                    onClick={this.reloadPage}
                    className="btn-secondary px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm font-medium"
                    title="Reload the entire page"
                  >
                    Reload Page
                  </button>

                  <a
                    href="/"
                    className="btn-tertiary px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors text-sm font-medium"
                    title="Go to home page"
                  >
                    Go Home
                  </a>
                </div>

                {/* Help Text */}
                <p className="text-red-600 text-xs mt-4">
                  If the problem persists, please contact support or check the
                  browser console for more details.
                </p>
              </div>
            </div>
          </div>
        </div>
      )
    }

    // No error, render children normally
    return this.props.children
  }
}

export default ErrorBoundary

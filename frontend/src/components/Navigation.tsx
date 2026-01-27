import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useUIStore } from '@store/uiStore'

/**
 * Navigation item configuration
 */
interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  ariaLabel: string
}

/**
 * Navigation menu items with icons
 */
const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/',
    ariaLabel: 'Dashboard home page',
    icon: (
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M3 12l2-3m0 0l7-4 7 4M5 9v10a1 1 0 001 1h12a1 1 0 001-1V9m-9 16l4-4m0 0l4 4m-4-4V5"
        />
      </svg>
    )
  },
  {
    label: 'Alert Feed',
    path: '/alerts',
    ariaLabel: 'View all market alerts',
    icon: (
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
        />
      </svg>
    )
  },
  {
    label: 'Option Chains',
    path: '/options',
    ariaLabel: 'Browse option chains by expiration and strike',
    icon: (
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
        />
      </svg>
    )
  },
  {
    label: 'Strategies',
    path: '/strategies',
    ariaLabel: 'Explore multi-leg options strategies',
    icon: (
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </svg>
    )
  },
  {
    label: 'Configuration',
    path: '/config',
    ariaLabel: 'System settings and status',
    icon: (
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
        />
      </svg>
    )
  }
]

/**
 * Navigation Component - Sidebar navigation menu
 *
 * Features:
 * - Collapsible sidebar on mobile (icons only when collapsed)
 * - Active route highlighting with blue background
 * - Icons + text on desktop view
 * - Icons only on mobile/collapsed view
 * - Links to all main pages via React Router
 * - Smooth transitions when collapsing
 * - User status indicator in footer
 *
 * Layout:
 * - Header: Menu title (shown when expanded)
 * - Body: Navigation items with active state styling
 * - Footer: User status indicator
 *
 * Accessibility:
 * - Proper aria-labels for icon-only mode
 * - Semantic link elements
 * - Clear visual feedback on active routes
 *
 * @component
 */
export const Navigation: React.FC = () => {
  const { sidebarOpen } = useUIStore()
  const location = useLocation()

  /**
   * Check if current route matches nav item path
   * @param path - Navigation item path
   * @returns true if path matches current location
   */
  const isActive = (path: string): boolean => {
    // Home route special case
    if (path === '/' && location.pathname === '/') {
      return true
    }
    // Other routes
    return path !== '/' && location.pathname.startsWith(path)
  }

  return (
    <nav
      className={`bg-gray-800 text-white transition-all duration-300 ${
        sidebarOpen ? 'w-48 sm:w-64' : 'w-16 sm:w-20'
      } min-h-screen flex flex-col border-r border-gray-700`}
      aria-label="Main navigation"
    >
      {/* Header */}
      <div className="p-4 sm:p-6 border-b border-gray-700">
        {sidebarOpen && (
          <h2 className="text-lg sm:text-xl font-bold text-white">Menu</h2>
        )}
      </div>

      {/* Navigation Items */}
      <div className="flex-1 py-4 sm:py-6 space-y-1 sm:space-y-2 px-2 sm:px-3">
        {navItems.map((item) => {
          const active = isActive(item.path)
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 sm:gap-4 px-3 sm:px-4 py-2 sm:py-3 rounded-lg transition-colors whitespace-nowrap ${
                active
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-300 hover:bg-gray-700 hover:text-white'
              }`}
              title={!sidebarOpen ? item.label : undefined}
              aria-label={item.ariaLabel}
              aria-current={active ? 'page' : undefined}
            >
              {item.icon}
              {sidebarOpen && (
                <span className="font-medium text-sm sm:text-base">
                  {item.label}
                </span>
              )}
            </Link>
          )
        })}
      </div>

      {/* Footer - User Status */}
      <div className="p-3 sm:p-4 border-t border-gray-700 bg-gray-900">
        <div className="flex items-center gap-3">
          {/* User Avatar */}
          <div className="w-8 h-8 sm:w-10 sm:h-10 bg-blue-600 rounded-full flex-shrink-0 flex items-center justify-center">
            <span className="text-white font-bold text-xs sm:text-sm">U</span>
          </div>
          {/* User Info (shown when expanded) */}
          {sidebarOpen && (
            <div className="text-sm min-w-0">
              <p className="font-medium text-white truncate">Analyst</p>
              <p className="text-gray-400 text-xs truncate">
                <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-1" />
                Online
              </p>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}

export default Navigation

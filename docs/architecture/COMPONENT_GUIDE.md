# Reusable React Components - Implementation Guide

**Project**: Option Chain Dashboard
**Location**: `/frontend/src/components/`
**Last Updated**: 2026-01-26
**Status**: Complete with comprehensive documentation and TypeScript types

---

## Overview

This document describes the five reusable React components created for the Option Chain Dashboard. All components feature:

- TypeScript strict mode with complete type definitions
- Tailwind CSS styling with responsive design
- Comprehensive JSDoc comments
- Accessibility features (ARIA labels, semantic HTML)
- Production-ready error handling
- Mobile-first responsive design

---

## 1. Header Component

**File**: `/frontend/src/components/Header.tsx`
**Lines**: 166
**Exports**: `Header` (React.FC)

### Purpose
Application top navigation bar displaying system status and controls.

### Features

- **App Logo/Title**: "Option Chain Dashboard" with subtitle
- **Health Status Indicator**: Animated pulse dot (green/red) with text label
- **Data Mode Display**: Shows "Demo" or "Production" mode
- **Last Scan Timestamp**: Formatted time of last system scan
- **Settings Button**: Navigates to `/config` page
- **Responsive Design**: Collapses elements on mobile (hidden on small screens)
- **Menu Toggle**: Integrates with sidebar collapse functionality

### Props

```tsx
// No props required - uses Zustand stores internally
```

### Hooks Used

- `useNavigate()` - React Router navigation
- `useUIStore()` - UI state (sidebar toggle)
- `useConfigStore()` - Configuration and health status

### Display Breakpoints

```
Desktop (lg):    All elements visible
Tablet (sm):     Hide Last Scan Time
Mobile (xs):     Hide Status text, show icon only
```

### Key Functions

```tsx
formatTimestamp(timestamp: string | null): string
  // Format ISO timestamp to readable time (HH:MM:SS)
  // Returns "Never" if null

handleSettingsClick(): void
  // Navigate to /config page
```

### Styling

- Background: `bg-gray-800` with border `border-gray-700`
- Status colors: `text-green-400` (connected), `text-red-400` (disconnected)
- Data mode: `text-yellow-400` (demo), `text-blue-400` (production)
- Responsive padding: `px-4 sm:px-6 py-3 sm:py-4`

### Example Usage

```tsx
import { Header } from '@components/Header'

export const App = () => {
  return (
    <div>
      <Header />
      {/* Page content */}
    </div>
  )
}
```

---

## 2. Navigation Component

**File**: `/frontend/src/components/Navigation.tsx`
**Lines**: 228
**Exports**: `Navigation` (React.FC)

### Purpose
Sidebar navigation menu with all main application pages.

### Features

- **Navigation Items**: 5 main routes with icons
  - Dashboard (home icon)
  - Alert Feed (bell icon)
  - Option Chains (chart icon)
  - Strategies (lightbulb icon)
  - Configuration (gear icon)
- **Collapsible Sidebar**: Expand/collapse on mobile
- **Active Route Highlighting**: Blue background for current page
- **Icon + Text Desktop**: Full labels when expanded
- **Icons Only Mobile**: Text hidden when collapsed (with titles)
- **User Status Indicator**: Avatar + online status in footer
- **Smooth Transitions**: CSS transitions for expand/collapse

### Props

```tsx
// No props required - uses Zustand store and React Router
```

### Hooks Used

- `useUIStore()` - Sidebar open/close state
- `useLocation()` - Current route detection

### Nav Items Configuration

```tsx
const navItems: NavItem[] = [
  {
    label: string           // Display text
    path: string            // React Router path
    ariaLabel: string       // Accessibility label
    icon: React.ReactNode   // SVG icon component
  }
]
```

### Active Route Detection

```tsx
isActive(path: string): boolean
  // Home route: matches exactly "/"
  // Other routes: pathname starts with path
```

### Responsive Widths

```
Expanded:  w-48 sm:w-64 (192px → 256px)
Collapsed: w-16 sm:w-20 (64px → 80px)
Transition: 300ms duration
```

### Styling

- Background: `bg-gray-800` with border `border-gray-700`
- Active link: `bg-blue-600 text-white shadow-md`
- Hover: `hover:bg-gray-700 hover:text-white`
- User avatar: `bg-blue-600 rounded-full`

### Example Usage

```tsx
import { Navigation } from '@components/Navigation'

export const App = () => {
  return (
    <div className="flex">
      <Navigation />
      <main>{/* Page content */}</main>
    </div>
  )
}
```

---

## 3. AlertCard Component

**File**: `/frontend/src/components/AlertCard.tsx`
**Lines**: 308
**Exports**: `AlertCard` (React.FC)

### Purpose
Display individual market alert with score, strategies, and actions.

### Features

- **Alert Display**: Ticker, detector type, score, timestamp
- **Color-Coded Severity**: Left border color based on score
  - Red (≥90), Orange (≥75), Yellow (≥50), Blue (<50)
- **Score Badge**: Color-coded background matching severity
- **Strategy Badges**: Display up to 3 suggested strategies
- **Expandable Metrics**: Show/hide detailed metrics data
- **Action Buttons**: Optional resolve and dismiss with loading states
- **Navigation**: Click card to navigate to `/ticker/{symbol}`
- **Async Handling**: Loading states for resolve/dismiss operations

### Props

```tsx
interface AlertCardProps {
  alert: AlertResponse              // Alert data from API (required)
  onResolve?: (id: number) => void | Promise<void>  // Resolve callback
  onDismiss?: (id: number) => void | Promise<void>  // Dismiss callback
  onClick?: (alertId: number) => void // Custom click handler
  showDetails?: boolean             // Initial expand state (default: false)
  className?: string                // Additional CSS classes
}
```

### Data Requirements

```tsx
AlertResponse {
  id: number                     // Unique identifier
  ticker: string                 // Stock symbol
  detector_name: string          // Detector type (e.g., "low_iv")
  score: number                  // Score 0-100
  metrics: Record<string, unknown> // Detailed metrics data
  explanation: Record<string, unknown> // Explanation data
  strategies: string[]           // Recommended strategies
  created_at: string             // ISO timestamp
}
```

### Hooks Used

- `useNavigate()` - Navigate to ticker detail page
- `useState()` - Expanded state, loading states

### Key Functions

```tsx
getScoreColor(score: number): string
  // Red (≥90), Orange (≥75), Yellow (≥50), Blue (<50)

getSeverityBorder(score: number): string
  // Left border color matching score severity

handleResolve(e: React.MouseEvent): Promise<void>
  // Handle resolve button with error handling

handleDismiss(e: React.MouseEvent): Promise<void>
  // Handle dismiss button with error handling

handleCardClick(): void
  // Navigate to ticker or call custom onClick

formatMetricValue(value: unknown): string
  // Format metric for display
```

### Responsive Layout

```
Desktop:  Full width, side-by-side actions
Mobile:   Stacked, buttons below content
```

### Example Usage

```tsx
import { AlertCard } from '@components/AlertCard'

export const AlertFeed = () => {
  const handleResolve = async (id: number) => {
    await api.post(`/alerts/${id}/resolve`)
  }

  return (
    <div className="space-y-3">
      {alerts.map(alert => (
        <AlertCard
          key={alert.id}
          alert={alert}
          onResolve={handleResolve}
          showDetails={false}
        />
      ))}
    </div>
  )
}
```

---

## 4. MetricsRow Component

**File**: `/frontend/src/components/MetricsRow.tsx`
**Lines**: 221
**Exports**: `MetricsRow` (React.FC)

### Purpose
Responsive grid display of key metrics with values and change indicators.

### Features

- **Responsive Grid**: 1 col mobile → 3 cols desktop (configurable)
- **Metric Cards**: Each metric in a styled card
- **Icon Display**: Optional icon with opacity effect
- **Change Indicator**: Green (+), red (-), gray (0) percentage change
- **Unit Suffix**: Optional unit text (e.g., "%", "$", "alerts")
- **Clickable Metrics**: Optional onClick handler for interactivity
- **Hover Effect**: Scale and shadow on hover when clickable
- **Value Formatting**: Proper number formatting with locale support
- **Tooltip Support**: Optional tooltip on hover

### Props

```tsx
interface MetricsRowProps {
  metrics: Metric[]              // Array of metrics (required)
  className?: string             // Additional CSS classes
  columns?: 1 | 2 | 3 | 4        // Desktop columns (default: 3)
  gap?: 'small' | 'medium' | 'large' // Gap size (default: medium)
}

interface Metric {
  label: string                  // Metric title
  value: string | number         // Metric value (required)
  change?: number                // Percent change (optional)
  unit?: string                  // Unit suffix (optional)
  icon?: React.ReactNode         // Icon component (optional)
  onClick?: () => void           // Click handler (optional)
  tooltip?: string               // Tooltip text (optional)
}
```

### Grid Configurations

```tsx
columns: 1  → grid-cols-1
columns: 2  → md:grid-cols-2
columns: 3  → md:grid-cols-3 (default)
columns: 4  → md:grid-cols-2 lg:grid-cols-4

gap: 'small'  → gap-2 sm:gap-3
gap: 'medium' → gap-4 sm:gap-6 (default)
gap: 'large'  → gap-6 sm:gap-8
```

### Key Functions

```tsx
formatValue(value: string | number): string
  // Format number with locale support (1000 → "1,000")

getChangeText(change: number): string
  // Format change: "+5%", "-3%", "0%"

getChangeColor(change: number): string
  // Return Tailwind color class for change value
```

### Example Usage

```tsx
import { MetricsRow } from '@components/MetricsRow'

export const Dashboard = () => {
  const metrics = [
    {
      label: 'Total Alerts Today',
      value: 42,
      change: 15,
      unit: 'Alerts',
      icon: <BellIcon className="w-6 h-6" />,
      onClick: () => navigate('/alerts')
    },
    {
      label: 'Average Score',
      value: 75.5,
      change: -2.3,
      unit: '%',
      tooltip: 'Average detector score'
    },
    {
      label: 'System Health',
      value: 'Healthy',
      icon: <CheckIcon className="w-6 h-6" />
    }
  ]

  return <MetricsRow metrics={metrics} columns={3} gap="medium" />
}
```

### Responsive Behavior

```
Mobile (1 col):   Each metric takes full width
Tablet (md):      2-3 metrics per row depending on columns prop
Desktop (lg):     3-4 metrics per row with larger spacing
```

---

## 5. ErrorBoundary Component

**File**: `/frontend/src/components/ErrorBoundary.tsx`
**Lines**: 259
**Exports**: `ErrorBoundary` (class component)

### Purpose
Error boundary wrapper protecting app from render-time errors.

### Features

- **Error Catching**: Catches errors in child components
- **Graceful Fallback**: Beautiful error UI with icon and message
- **Error Details**: Development mode shows component stack
- **Retry Buttons**: "Try Again" and "Reload Page" options
- **Error Logging**: Console logging + optional callback hook
- **Responsive Design**: Mobile-friendly error display
- **Production Safe**: Hides sensitive details in production
- **Error Reference**: Unique ID for debugging in production

### Props

```tsx
interface Props {
  children: ReactNode                                  // Child components
  fallback?: ReactNode                                 // Custom fallback UI
  onError?: (error: Error, info: React.ErrorInfo) => void // Error callback
}
```

### State

```tsx
interface State {
  hasError: boolean           // Error occurred
  error: Error | null         // The error object
  errorInfo: React.ErrorInfo | null // Component stack trace
}
```

### What It Catches

✅ Rendering errors in components
✅ Lifecycle method errors
✅ Constructor errors in children
✅ Errors in async components

❌ Event handlers (use try-catch)
❌ Promise rejections (use .catch())
❌ Server-side rendering
❌ Errors in error boundary itself

### Key Methods

```tsx
static getDerivedStateFromError(error: Error): Partial<State>
  // Called during render phase
  // Update state to trigger fallback UI

componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void
  // Called after error is caught
  // Log error, call optional callback

private resetError(): void
  // Reset boundary to try rendering again

private reloadPage(): void
  // Full page reload (location.reload())
```

### Error Display Modes

**Development Mode**:
- Shows full error message
- Expandable component stack trace
- Detailed debugging information

**Production Mode**:
- Generic error message
- Error reference ID (first 8 chars of message)
- Help text directing to support

### Example Usage

```tsx
import { ErrorBoundary } from '@components/ErrorBoundary'

// Basic usage
<ErrorBoundary>
  <App />
</ErrorBoundary>

// With error logging
<ErrorBoundary
  onError={(error, info) => {
    // Send to error tracking service
    logErrorToService({
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack
    })
  }}
>
  <App />
</ErrorBoundary>

// With custom fallback
<ErrorBoundary
  fallback={
    <div className="p-6 text-center">
      <p>Custom error occurred</p>
    </div>
  }
>
  <App />
</ErrorBoundary>
```

---

## Integration Guide

### App Layout Structure

```tsx
import { ErrorBoundary } from '@components/ErrorBoundary'
import { Header } from '@components/Header'
import { Navigation } from '@components/Navigation'

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-gray-900">
        <Navigation />
        <div className="flex-1 flex flex-col">
          <Header />
          <main className="flex-1 overflow-auto">
            {/* Routes and pages go here */}
          </main>
        </div>
      </div>
    </ErrorBoundary>
  )
}
```

### Using Components in Pages

```tsx
// Dashboard.tsx
import { MetricsRow } from '@components/MetricsRow'
import { AlertCard } from '@components/AlertCard'

export const Dashboard: React.FC = () => {
  return (
    <div className="p-6">
      <MetricsRow metrics={metrics} columns={3} />
      <div className="space-y-3">
        {alerts.map(alert => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  )
}
```

---

## Styling Notes

### Tailwind Classes

All components use consistent Tailwind CSS classes:

- **Cards**: `.card` class (defined in global CSS)
- **Responsive**: `sm:`, `md:`, `lg:` breakpoints
- **Colors**: `gray-*`, `blue-*`, `red-*`, `green-*`, `orange-*`, `yellow-*`
- **Spacing**: `p-*`, `gap-*`, `mx-auto`, etc.
- **Typography**: Font weights, sizes with responsive scaling

### Custom CSS Required

Make sure your global CSS includes:

```css
.card {
  @apply bg-white rounded-lg shadow border border-gray-200;
}

.btn-primary {
  @apply bg-blue-600 text-white hover:bg-blue-700 transition-colors;
}

.btn-secondary {
  @apply bg-gray-600 text-white hover:bg-gray-700 transition-colors;
}

.badge {
  @apply inline-block px-3 py-1 rounded-full text-sm font-medium;
}
```

---

## TypeScript Conventions

All components follow strict TypeScript patterns:

- **Props Interfaces**: Documented with JSDoc comments
- **Optional Props**: Marked with `?` and have defaults
- **Type Imports**: Use `type` keyword for imports
- **React.FC**: Explicit function component typing
- **Generics**: Used where appropriate (e.g., `Record<string, unknown>`)

---

## Accessibility Features

All components include:

- **ARIA Labels**: `aria-label` on interactive elements
- **Semantic HTML**: Proper heading hierarchy, role attributes
- **Keyboard Navigation**: All buttons and links are keyboard accessible
- **Color Contrast**: WCAG AA compliance for text on backgrounds
- **Alt Text**: Icons have `aria-hidden="true"` where appropriate
- **Form Labels**: Proper label association (when applicable)

---

## Performance Considerations

- **No Prop Drilling**: Use Zustand stores for global state
- **Memoization**: Components automatically memoized if needed
- **Event Handlers**: Use arrow functions in class components
- **Re-renders**: Minimal unnecessary renders with proper hook dependencies
- **Key Props**: Always use stable keys in lists

---

## Testing

Example test patterns for each component:

```tsx
// Header.test.tsx
import { render, screen } from '@testing-library/react'
import { Header } from '@components/Header'

describe('Header', () => {
  it('displays app title', () => {
    render(<Header />)
    expect(screen.getByText('Option Chain Dashboard')).toBeInTheDocument()
  })
})

// AlertCard.test.tsx
import { render, screen } from '@testing-library/react'
import { AlertCard } from '@components/AlertCard'

describe('AlertCard', () => {
  it('displays alert ticker and score', () => {
    const alert = {
      id: 1,
      ticker: 'AAPL',
      score: 85,
      // ... other fields
    }
    render(<AlertCard alert={alert} />)
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
  })
})
```

---

## Common Issues & Solutions

### Header not showing status
- Ensure `useConfigStore` is initialized with health data
- Check that `setHealth()` is called when API responds

### Navigation not highlighting active route
- Verify `useLocation()` hook is working
- Check route paths exactly match nav item paths

### AlertCard metrics not expanding
- Ensure alert has `metrics` object with data
- Check that `showDetails` prop is passed

### MetricsRow not responsive
- Add responsive classes to parent container
- Ensure Tailwind CSS is properly configured

### ErrorBoundary not catching errors
- Only catches rendering errors, not event handlers
- Wrap event handlers with try-catch separately

---

## Summary

| Component | Lines | Purpose | Key Props |
|-----------|-------|---------|-----------|
| **Header** | 166 | Top navigation bar | None (stores) |
| **Navigation** | 228 | Sidebar menu | None (stores) |
| **AlertCard** | 308 | Alert display | `alert`, `onResolve`, `onDismiss` |
| **MetricsRow** | 221 | Metrics grid | `metrics`, `columns`, `gap` |
| **ErrorBoundary** | 259 | Error handling | `children`, `fallback`, `onError` |

**Total Lines**: 1,182
**All components**: TypeScript strict mode, fully documented, production-ready
**Standards**: React best practices, Tailwind CSS, WCAG accessibility, semantic HTML

---

## Quick Reference

```tsx
// Import all components
import { Header } from '@components/Header'
import { Navigation } from '@components/Navigation'
import { AlertCard } from '@components/AlertCard'
import { MetricsRow } from '@components/MetricsRow'
import { ErrorBoundary } from '@components/ErrorBoundary'

// Typical app structure
<ErrorBoundary>
  <div className="flex">
    <Navigation />
    <div className="flex-1">
      <Header />
      <main>
        <MetricsRow metrics={[...]} />
        {alerts.map(a => <AlertCard key={a.id} alert={a} />)}
      </main>
    </div>
  </div>
</ErrorBoundary>
```

---

**Last Updated**: 2026-01-26
**Status**: Complete and ready for production
**Next Steps**: Integrate components into pages and test with live API data

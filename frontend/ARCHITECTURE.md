# Frontend Architecture - Option Chain Dashboard

## Overview

This React frontend provides a real-time dashboard for analyzing options chains, monitoring alerts, and exploring trading strategies. It's built with React 18, TypeScript, Tailwind CSS, and modern state management.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                  React App (Port 8060)              │
├─────────────────────────────────────────────────────┤
│  Router (React Router DOM)                          │
│  ├── Dashboard (/)                                  │
│  ├── AlertFeed (/alerts)                            │
│  ├── OptionChains (/options)                        │
│  ├── StrategyExplorer (/strategies)                 │
│  └── ConfigStatus (/config)                         │
├─────────────────────────────────────────────────────┤
│  Global State (Zustand)                             │
│  ├── alertStore                                     │
│  ├── configStore                                    │
│  └── uiStore                                        │
├─────────────────────────────────────────────────────┤
│  Custom Hooks                                       │
│  ├── useApi (GET/POST/PUT/DELETE)                   │
│  ├── useWebSocket (Real-time updates)               │
│  └── useLocalStorage (Persistence)                  │
├─────────────────────────────────────────────────────┤
│  API Client (Axios)                                 │
│  └── http://localhost:8061 (Vite Proxy)             │
└─────────────────────────────────────────────────────┘
```

## Directory Organization

### `/src/components` - Reusable UI Components
Stateless, focused components for display and user interaction.

**Header.tsx**
- Top navigation bar
- System health indicator (green/red dot)
- Settings and sidebar toggle buttons

**Navigation.tsx**
- Collapsible sidebar with route links
- Active route highlighting
- Responsive width based on sidebar state

**AlertCard.tsx**
- Displays individual alert with severity coloring
- Resolve and dismiss action buttons
- Alert metadata (type, ticker, timestamp)

**MetricsRow.tsx**
- Responsive grid of metric cards
- Supports change indicators (positive/negative)
- Optional icons and custom units

**ErrorBoundary.tsx**
- Catches React component errors
- Displays user-friendly error UI
- Provides page reload recovery option

### `/src/pages` - Route Pages
Full-page components mounted by React Router.

**Dashboard.tsx** (Route: /)
- Overview with key metrics
- Top 5 tickers list
- Recent 10 alerts
- Uses useApi hooks to fetch data

**AlertFeed.tsx** (Route: /alerts)
- Complete alert list with filtering
- Severity filter buttons
- Alert statistics display
- Resolve/dismiss actions

**OptionChains.tsx** (Route: /options)
- Ticker search input
- Underlying asset details (price, change, volume)
- Call options table (strike, bid/ask, IV, Greeks)
- Put options table

**StrategyExplorer.tsx** (Route: /strategies)
- Placeholder component
- Ready for strategy analysis features

**ConfigStatus.tsx** (Route: /config)
- System configuration display
- Data provider information
- Health check dashboard
- Component status (database, API, analytics)

### `/src/store` - Global State (Zustand)

**alertStore.ts**
```typescript
State:
- alerts: Alert[]           # All alerts
- filter: AlertFilter       # Current filter settings
- stats: AlertStats         # Computed statistics
- loading: boolean
- error: string | null

Actions:
- setAlerts(alerts)
- addAlert(alert)
- removeAlert(id)
- updateAlert(id, updates)
- resolveAlert(id)
- setFilter(filter)
- clearFilter()
- getFilteredAlerts() → filtered list
- computeStats() → updates stats
```

**configStore.ts**
```typescript
State:
- config: ConfigStatus | null
- health: HealthStatus | null
- loading: boolean
- error: string | null
- lastUpdated: string | null

Actions:
- setConfig(config)
- setHealth(health)
- updateLastUpdated()
- reset()
- isHealthy() → boolean
```

**uiStore.ts**
```typescript
State:
- sidebarOpen: boolean
- selectedTicker?: string
- selectedStrategy?: string
- dateRange?: {start, end}
- viewMode: 'grid' | 'list' | 'detailed'

Actions:
- setSidebarOpen(boolean)
- toggleSidebar()
- setSelectedTicker(string | undefined)
- setSelectedStrategy(string | undefined)
- setDateRange(range | undefined)
- setViewMode(mode)
```

### `/src/hooks` - Custom React Hooks

**useApi.ts**
Provides easy data fetching for multiple HTTP methods.

```typescript
// GET with auto-fetch
const { data, loading, error, refetch } = useApi<T>(url, {
  immediate: true,
  dependencies: [filterValue],
  onSuccess: (data) => console.log(data),
  onError: (error) => console.log(error)
})

// POST
const { execute, loading, error, data } = useApiPost<RequestT, ResponseT>(url)
const result = await execute(payload)

// PUT
const { execute, loading, error, data } = useApiPut<RequestT, ResponseT>(url)

// DELETE
const { execute, loading, error } = useApiDelete(url)
```

**useWebSocket.ts**
Manages WebSocket connections for real-time updates.

```typescript
const { isConnected, send, disconnect } = useWebSocket(
  'ws://localhost:8061/ws',
  {
    onMessage: (data) => console.log(data),
    onError: (error) => console.log(error),
    onOpen: () => console.log('Connected'),
    onClose: () => console.log('Disconnected'),
    reconnect: true  // Auto-reconnect on disconnect
  }
)

// Send message
send({ type: 'subscribe', channel: 'alerts' })
```

**useLocalStorage.ts**
Persistent browser storage for user preferences.

```typescript
const [value, setValue] = useLocalStorage('key', defaultValue)
// Auto-persists to localStorage on setValue
```

### `/src/types` - TypeScript Definitions

**api.ts**
- `ApiResponse<T>`: Generic API response wrapper
- `TickerData`: Stock price information
- `OptionChain`: Chain of calls and puts
- `OptionContract`: Individual option (strike, bid/ask, Greeks)
- `Alert`: Alert event (type, severity, data)
- `HealthStatus`: System health with component status
- `ConfigStatus`: Configuration and data points

**alert.ts**
- `AlertType`: 'unusual_volume' | 'iv_spike' | 'price_movement' | 'strategy_signal'
- `AlertSeverity`: 'low' | 'medium' | 'high' | 'critical'
- `AlertFilter`: Filtering options
- `AlertStats`: Statistics (totals by severity)
- `AlertNotification`: Real-time notification

**features.ts**
- `Strategy`: Strategy definition with parameters
- `StrategyParameter`: Parameter with min/max bounds
- `StrategySignal`: Buy/sell signal with confidence
- `UIState`: UI layout and selection state
- `PaginationState`: Pagination info

### `/src/utils` - Utilities

**apiClient.ts**
Axios instance with:
- Base URL: http://localhost:8061
- Timeout: 30 seconds
- Request/response interceptors
- Error handling for 401, 500, etc.

```typescript
import apiClient from '@utils/apiClient'

// Direct usage
const response = await apiClient.get('/api/alerts')

// Custom headers
apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
```

**formatters.ts**
Formatting utilities:
- `formatPrice(123.456, 2)` → "123.46"
- `formatPercent(5.5)` → "+5.50%"
- `formatVolume(1500000)` → "1.50M"
- `formatDate(date, 'short')` → "01/26/2026"
- `formatTime(date)` → "14:30:45"
- `formatRelativeTime(date)` → "5m ago"
- `formatCurrency(100, 'USD')` → "$100.00"
- `getPriceChangeColor(change)` → CSS class name
- `getSeverityColor(severity)` → CSS class name

**constants.ts**
App-wide constants:
- API endpoints
- Alert types and severities with colors
- Strategy types
- Default pagination size
- Cache durations
- View modes

### `/src/styles` - Styling

**tailwind.css**
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn-primary   /* Blue button with hover state */
  .btn-secondary /* Gray button */
  .btn-danger    /* Red button */
  .card          /* White card with shadow */
  .badge-*       /* Severity-colored badges */
  .grid-responsive /* Auto-responsive grid */
}
```

**globals.css**
- Global reset and fonts
- Scrollbar styling
- Focus/selection styles
- Animations (fadeIn, slideIn, pulse)
- Utility classes (truncate-text, spinner)

## Data Flow

### Dashboard Load
```
1. App.tsx mounts
2. useApi('/api/health') fetches health status
3. configStore.setHealth(health)
4. Header displays health indicator

5. Dashboard.tsx mounts
6. useApi('/api/tickers') fetches top tickers
7. useApi('/api/alerts') fetches recent alerts
8. alertStore.setAlerts(alerts)
9. Page renders with data
```

### Alert Resolution
```
1. User clicks resolve button on AlertCard
2. AlertCard calls onResolve(alertId)
3. AlertFeed calls alertStore.resolveAlert(id)
4. Store updates alert.resolved = true
5. AlertCard rerenders with "Resolved" badge
6. Stats automatically update via computeStats()
```

### Filter Application
```
1. User clicks severity filter button
2. AlertFeed updates selectedSeverities state
3. alertStore.setFilter({ severities: [...] })
4. getFilteredAlerts() returns filtered list
5. AlertFeed rerenders with filtered alerts
```

## State Updates & Reactivity

All state updates via Zustand trigger component re-renders:

```typescript
// In component
const { alerts, stats } = useAlertStore()

// When store updates:
useAlertStore.setState({ alerts: newAlerts })

// Component automatically rerenders with new alerts
```

## API Integration Pattern

### Standard Flow
```typescript
// Component
import { useApi } from '@hooks/useApi'

const MyComponent = () => {
  const { data, loading, error } = useApi<MyType>('/api/endpoint')
  
  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  
  return <div>{/* render data */}</div>
}
```

### With Error Handling
```typescript
const { data, loading, error } = useApi('/api/data', {
  onError: (error) => {
    console.error('Failed to load:', error)
    // Show toast/notification
  }
})
```

### Manual Refetch
```typescript
const { data, refetch } = useApi('/api/data')

const handleRefresh = async () => {
  await refetch()
}
```

## Development Tips

### Adding a New Page
1. Create file in `/src/pages/YourPage.tsx`
2. Add route in `App.tsx` Routes
3. Add nav item in `Navigation.tsx`
4. Import and use custom hooks for data

### Adding a New Component
1. Create file in `/src/components/YourComponent.tsx`
2. Define props interface
3. Export as default
4. Use in pages/other components

### Adding New API Types
1. Add to `/src/types/api.ts` or create new file
2. Export type
3. Use in useApi generics: `useApi<YourType>(url)`

### Debugging State
```typescript
import { useAlertStore } from '@store/alertStore'

const Component = () => {
  const state = useAlertStore()
  console.log('Current state:', state)  // Full store state
  return null
}
```

### Network Debugging
1. Open browser DevTools (F12)
2. Network tab shows all API calls to /api/*
3. Vite proxy shows in console when requests are proxied
4. Check Response headers and body

## Performance Considerations

1. **Component Memoization** (TODO)
   - Use React.memo for AlertCard to prevent unnecessary rerenders

2. **Code Splitting** (TODO)
   - Lazy load pages with React.lazy() and Suspense

3. **API Caching** (TODO)
   - Implement cache in useApi with TTL
   - Avoid redundant requests

4. **Image Optimization** (TODO)
   - Use WebP format
   - Lazy load images

## Build & Deployment

### Development
```bash
npm install
npm run dev
# Runs on http://localhost:8060
# Hot reload enabled
```

### Production
```bash
npm run build
# Creates dist/ folder
# Optimized and minified

npm run preview
# Test production build locally
```

### Build Output
- `dist/index.html` - Minified HTML
- `dist/assets/*.js` - Bundled JavaScript (code split)
- `dist/assets/*.css` - Minified CSS

## Environment Variables

All in `.env` file (copied from `.env.example`):
- `VITE_API_BASE_URL` - Backend URL
- `VITE_WS_URL` - WebSocket URL
- `VITE_APP_NAME` - Application name
- `VITE_ENABLE_REAL_TIME_UPDATES` - Toggle real-time features

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 15+
- Edge 90+

TypeScript targets ES2020 for modern JavaScript features.

## Known Limitations & TODO

- [ ] Real-time WebSocket integration (hooks are ready)
- [ ] Advanced charting library
- [ ] Dark mode support
- [ ] User authentication
- [ ] Export to CSV/PDF
- [ ] Custom strategy builder
- [ ] Backtesting engine UI
- [ ] Advanced filtering and search
- [ ] Notifications/toast UI

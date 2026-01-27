# Routing Guide - Option Chain Dashboard

Quick reference for navigation, routing, and URL handling.

---

## Routes Overview

| Route | Component | Description | Sidebar Link |
|-------|-----------|-------------|--------------|
| `/` | Dashboard | Overview with metrics & alerts | Yes |
| `/alerts` | AlertFeed | All market alerts | Yes |
| `/ticker/:symbol` | TickerDetail | Single ticker options | No* |
| `/options` | OptionChains | Browse all options | Yes |
| `/strategies` | StrategyExplorer | Strategy builder | Yes |
| `/config` | ConfigStatus | System settings | Yes |

*TickerDetail is accessed via programmatic navigation from Dashboard/OptionChains

---

## Basic Navigation

### Using Links

```typescript
import { Link } from 'react-router-dom'

// Static routes
<Link to="/">Go to Dashboard</Link>
<Link to="/alerts">View Alerts</Link>

// Dynamic routes with parameters
<Link to={`/ticker/AAPL`}>Apple Details</Link>
<Link to={`/ticker/${ticker.symbol}`}>Details</Link>
```

### Using Navigation Hook

```typescript
import { useNavigate } from 'react-router-dom'

const navigate = useNavigate()

// Navigate to static routes
navigate('/')
navigate('/alerts')

// Navigate to dynamic routes
navigate(`/ticker/AAPL`)
navigate(`/ticker/${symbol}`)

// Navigate back
navigate(-1)

// Replace history (no back)
navigate('/', { replace: true })
```

---

## Dynamic Routes

### Ticker Detail Route

**Pattern**: `/ticker/:symbol`

**Usage**:
```typescript
// Navigate to Apple options
navigate('/ticker/AAPL')

// Navigate with symbol variable
navigate(`/ticker/${selectedSymbol}`)
```

**Accessing the parameter**:
```typescript
import { useParams } from 'react-router-dom'

export const TickerDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>()

  // symbol = 'AAPL', 'MSFT', etc.

  // Fetch data for the symbol
  const { data } = useApi(`/api/tickers/${symbol}`)
}
```

**Valid examples**:
- `/ticker/AAPL` → Shows Apple
- `/ticker/MSFT` → Shows Microsoft
- `/ticker/SPY` → Shows SPY ETF
- `/ticker/QQQ` → Shows Nasdaq ETF

---

## Linking from Pages

### From Dashboard

```typescript
// Link to ticker detail
<Link to={`/ticker/${ticker.ticker}`}>
  <h3>{ticker.ticker}</h3>
</Link>

// Click handler to navigate
const handleTickerClick = (symbol: string) => {
  navigate(`/ticker/${symbol}`)
}
```

### From Other Pages

```typescript
// From AlertFeed to related ticker
<Link to={`/ticker/${alert.symbol}`}>
  View options for {alert.symbol}
</Link>

// From OptionChains to detail
<Link to={`/ticker/${chain.symbol}`}>
  {chain.symbol}
</Link>
```

---

## Navigation Component

The sidebar `Navigation.tsx` provides main navigation:

```typescript
const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: ... },
  { label: 'Alert Feed', path: '/alerts', icon: ... },
  { label: 'Option Chains', path: '/options', icon: ... },
  { label: 'Strategies', path: '/strategies', icon: ... },
  { label: 'Configuration', path: '/config', icon: ... }
]
```

Active link is highlighted based on `useLocation()`:
```typescript
const location = useLocation()
const isActive = location.pathname === item.path
```

---

## Programmatic Navigation

### Click Handlers

```typescript
const handleAlertClick = (symbol: string) => {
  navigate(`/ticker/${symbol}`)
}

return (
  <button onClick={() => handleAlertClick('AAPL')}>
    View AAPL
  </button>
)
```

### Form Submission

```typescript
const handleSearch = (formData) => {
  const { symbol } = formData
  navigate(`/ticker/${symbol}`)
}
```

### Data Effects

```typescript
useEffect(() => {
  if (selectedTicker) {
    navigate(`/ticker/${selectedTicker}`)
  }
}, [selectedTicker])
```

---

## Query Parameters (Future)

Currently not used, but pattern if needed:

```typescript
// Navigate with query params
navigate('/alerts?priority=high&status=open')

// Read query params
import { useSearchParams } from 'react-router-dom'
const [searchParams] = useSearchParams()
const priority = searchParams.get('priority')
```

---

## URL Parameter Validation

### In TickerDetail

```typescript
const { symbol } = useParams<{ symbol: string }>()
const navigate = useNavigate()

useEffect(() => {
  if (!symbol) {
    navigate('/')  // Invalid, redirect
  }
}, [symbol, navigate])
```

### Valid Symbols
- Uppercase: `AAPL`, `MSFT`, `SPY`
- Numbers: `QQQ`, `XLK`, `IVV`
- Special chars: `BRK.B`, `BRK.A`

---

## Error Handling

### Not Found Routes

Routes not matched default to catch-all:
```typescript
<Route path="*" element={<Dashboard />} />
```

So `/invalid/route` → Shows Dashboard

### Invalid Parameters

Check in component:
```typescript
if (!symbol || symbol.length === 0) {
  return <div>Invalid ticker symbol</div>
}
```

---

## Header Navigation

Header includes:
- App title
- Health status
- Settings button
- Sidebar toggle

To navigate from header:
```typescript
// In Header component
const navigate = useNavigate()

const handleSettings = () => {
  navigate('/config')
}
```

---

## Responsive Navigation

### Desktop (lg+)
- Sidebar always visible
- Full navigation text shown
- All routes accessible

### Tablet (md-lg)
- Collapsible sidebar
- Icons + text when open
- Icons only when collapsed

### Mobile (sm)
- Sidebar collapsible
- Icons + hamburger menu
- Tap to navigate

---

## Navigation State

### UI Store
```typescript
import { useUIStore } from '@store/uiStore'

const { sidebarOpen, toggleSidebar } = useUIStore()
```

Sidebar state:
- `sidebarOpen: true` → Full sidebar
- `sidebarOpen: false` → Icon-only sidebar

### Location State
```typescript
const location = useLocation()

// Get current path
console.log(location.pathname)  // '/ticker/AAPL'

// Get current route
if (location.pathname === '/') {
  // On dashboard
}
```

---

## Common Navigation Patterns

### Breadcrumb Navigation

```typescript
<nav className="flex items-center gap-2">
  <Link to="/">Home</Link>
  <span>/</span>
  <Link to="/options">Options</Link>
  <span>/</span>
  <span>{symbol}</span>
</nav>
```

### Back Button

```typescript
const navigate = useNavigate()

<button onClick={() => navigate(-1)}>
  Back
</button>
```

### Search to Detail

```typescript
const [searchSymbol, setSearchSymbol] = useState('')

const handleSearch = () => {
  if (searchSymbol) {
    navigate(`/ticker/${searchSymbol.toUpperCase()}`)
  }
}
```

### Tab Navigation

```typescript
const location = useLocation()

<button
  className={location.pathname === '/alerts' ? 'active' : ''}
  onClick={() => navigate('/alerts')}
>
  Alerts
</button>
```

---

## TypeScript with Routes

### Type-safe navigation

```typescript
type ValidRoute =
  | '/'
  | '/alerts'
  | `/ticker/${string}`
  | '/options'
  | '/strategies'
  | '/config'

const navigate = useNavigate()

const goTo = (path: ValidRoute) => {
  navigate(path)
}

// Safe usage
goTo('/')
goTo('/alerts')
goTo(`/ticker/AAPL`)

// TypeScript error - catches at compile time
// goTo('/invalid')
```

---

## Testing Navigation

### In Jest/Vitest

```typescript
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

describe('Navigation', () => {
  it('navigates to ticker detail', () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    const link = screen.getByRole('link', { name: /AAPL/ })
    expect(link).toHaveAttribute('href', '/ticker/AAPL')
  })
})
```

---

## Performance Notes

### Code Splitting
- Each page is lazy-loaded
- Routes not visited = code not downloaded
- Faster initial load

### Caching
- API data cached in stores
- Navigating back = instant data
- Reduces API calls

---

## Debugging Routes

### Browser DevTools

1. Install React DevTools extension
2. Inspect Router component
3. View route state and params

### Console Logging

```typescript
import { useParams, useLocation } from 'react-router-dom'

const MyComponent = () => {
  const params = useParams()
  const location = useLocation()

  console.log('Params:', params)
  console.log('Location:', location.pathname)
}
```

### Route Matching

Check `<Route>` definitions:
- Pattern in `path`
- Component in `element`
- Order matters (more specific first)

---

## Summary

**Key Points**:
1. Use `<Link>` for navigation
2. Use `useNavigate()` for dynamic navigation
3. Use `useParams()` to read URL parameters
4. Use `useLocation()` to check current location
5. Always validate parameters in components
6. Test navigation in your tests
7. Keep URLs RESTful and semantic

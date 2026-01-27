# Option Chain Dashboard - App Structure & Routing

## Overview

The Option Chain Dashboard frontend is a React-based single-page application (SPA) with React Router for client-side navigation. The application features a dark-mode-by-default design using Tailwind CSS and provides a comprehensive interface for analyzing options chains and market data.

**Architecture**: Three-tier layout with sidebar navigation, header, and main content area.

---

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx                 # Main app component with routing
│   ├── main.tsx                # Entry point with BrowserRouter
│   ├── index.css               # Global CSS imports
│   ├── components/             # Reusable UI components
│   │   ├── Header.tsx          # App header with health status
│   │   ├── Navigation.tsx      # Collapsible sidebar navigation
│   │   ├── ErrorBoundary.tsx   # Error handling component
│   │   ├── AlertCard.tsx       # Alert display card
│   │   └── MetricsRow.tsx      # Metrics display component
│   ├── pages/                  # Page-level components
│   │   ├── Dashboard.tsx       # Main dashboard (/)
│   │   ├── AlertFeed.tsx       # All alerts (/alerts)
│   │   ├── TickerDetail.tsx    # Single ticker view (/ticker/:symbol)
│   │   ├── OptionChains.tsx    # All chains view (/options)
│   │   ├── StrategyExplorer.tsx# Strategy builder (/strategies)
│   │   └── ConfigStatus.tsx    # Config & status (/config)
│   ├── hooks/                  # Custom React hooks
│   │   └── useApi.ts           # Data fetching hook
│   ├── store/                  # State management (Zustand)
│   │   ├── configStore.ts      # Global config state
│   │   ├── uiStore.ts          # UI state (sidebar, etc)
│   │   ├── alertStore.ts       # Alert state
│   │   └── apiStore.ts         # API client state
│   ├── utils/                  # Utility functions
│   │   ├── apiClient.ts        # Axios instance & interceptors
│   │   ├── formatters.ts       # Number/date formatting
│   │   └── constants.ts        # App constants
│   ├── types/                  # TypeScript type definitions
│   │   └── api.ts              # API response types
│   └── styles/                 # CSS styles
│       ├── tailwind.css        # Tailwind directives
│       └── globals.css         # Global component styles
├── public/                     # Static assets
├── index.html                  # HTML entry point
├── tsconfig.json               # TypeScript configuration
├── vite.config.ts              # Vite build configuration
├── tailwind.config.js          # Tailwind CSS config
└── package.json                # Dependencies
```

---

## Routing Configuration

All routes are defined in `App.tsx` using React Router v6.

### Route Map

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | Dashboard | Main landing page with overview metrics and recent alerts |
| `/alerts` | AlertFeed | Complete list of all market alerts with filtering |
| `/ticker/:symbol` | TickerDetail | Detailed view of single ticker's options chain |
| `/options` | OptionChains | Browse and analyze all available options chains |
| `/strategies` | StrategyExplorer | Multi-leg strategy builder and analyzer |
| `/config` | ConfigStatus | System settings, status, and configuration |
| `*` | Dashboard | Catch-all route redirects to Dashboard |

### Dynamic Routes

**Ticker Detail**: Uses URL parameter `symbol`
```
/ticker/AAPL    → Shows Apple options
/ticker/MSFT    → Shows Microsoft options
/ticker/SPY     → Shows SPY options
```

The `TickerDetail` component extracts the symbol from the URL using:
```typescript
const { symbol } = useParams<{ symbol: string }>()
```

---

## Component Architecture

### Layout Structure

```
App (Router wrapper)
├── BrowserRouter (main.tsx)
├── div.flex.h-screen (main layout)
│   ├── Navigation (sidebar)
│   └── div.flex-1 (main content area)
│       ├── Header (top bar)
│       └── main (content area)
│           └── Routes (page router)
│               └── Current Page Component
```

### Component Responsibilities

#### App.tsx
- Sets up routing structure
- Manages app-level state (health status)
- Provides error boundary
- Integrates Header, Navigation, and Pages

**Key Props**: None (uses store hooks)
**Key Hooks**: `useApi`, `useConfigStore`

#### main.tsx
- React entry point
- Wraps App with BrowserRouter for client-side routing
- Mounts React to DOM

#### Header.tsx
- Displays app title
- Shows health status indicator (green/red pulse)
- Shows data mode (Demo/Production)
- Shows last scan timestamp
- Provides sidebar toggle button
- Settings/menu button

**Key State**: `toggleSidebar` (from UIStore), `health` (from configStore)

#### Navigation.tsx
- Collapsible sidebar with navigation links
- Shows/hides labels based on sidebar state
- Active link highlighting
- Icon-based navigation items

**Navigation Items**:
1. Dashboard (/)
2. Alert Feed (/alerts)
3. Option Chains (/options)
4. Strategies (/strategies)
5. Configuration (/config)

#### ErrorBoundary.tsx
- Catches React errors
- Displays error UI
- Prevents white screen of death

---

## Styling System

### Dark Mode Design

The application uses a dark color scheme by default with Tailwind CSS:

**Color Palette**:
- Background: `bg-gray-900` (#111827)
- Cards: `bg-gray-800` (#1f2937)
- Borders: `border-gray-700` (#374151)
- Text: `text-white` / `text-gray-300`
- Accents: Blue (`blue-600`), Red (`red-500`), Green (`green-500`), Yellow (`yellow-500`)

### CSS Organization

**index.css**: Imports component styles
```css
@import './styles/tailwind.css';
@import './styles/globals.css';
```

**tailwind.css**: Tailwind directives
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**globals.css**: Custom component styles
- Global styles (reset, fonts)
- Component classes (`.btn-primary`, `.card`, `.alert-high`)
- Utility animations (fadeIn, slideIn, pulse, spin)
- Table and form styles
- Responsive utilities

### Component Classes

**Buttons**:
- `.btn-primary` - Blue primary button
- `.btn-secondary` - Gray secondary button
- `.btn-danger` - Red danger button
- `.btn-success` - Green success button

**Cards**:
- `.card` - Standard card with border
- `.card-highlight` - Highlighted card with blue border

**Alerts**:
- `.alert-high` - Red border, high priority
- `.alert-medium` - Yellow border, medium priority
- `.alert-low` - Green border, low priority

**Badges**:
- `.badge-success` - Green badge
- `.badge-warning` - Yellow badge
- `.badge-danger` - Red badge
- `.badge-info` - Blue badge

---

## State Management

Uses **Zustand** for lightweight state management.

### Stores

#### configStore
- `health`: Current backend health status
- `config`: Application configuration
- `isHealthy()`: Helper to check connection status
- `setHealth()`: Update health status
- `setConfig()`: Update configuration

#### uiStore
- `sidebarOpen`: Boolean for sidebar state
- `toggleSidebar()`: Toggle sidebar visibility

#### alertStore
- `alerts`: Array of current alerts
- `setAlerts()`: Update alerts list
- `resolveAlert()`: Mark alert as resolved

#### apiStore
- API client configuration and state

---

## Data Flow

### Page Rendering Flow

1. **User navigates** → Browser URL changes
2. **Router matches** → Finds matching Route in App.tsx
3. **Component renders** → Page component loads
4. **Data fetched** → `useApi()` hook calls backend
5. **State updates** → Zustand stores update
6. **Page renders** → Component displays data with dynamic content

### Example: Ticker Detail Flow

```
User clicks ticker → navigate('/ticker/AAPL')
                  ↓
Router matches /ticker/:symbol
                  ↓
TickerDetail.tsx loads
                  ↓
useParams gets 'AAPL'
                  ↓
useApi calls GET /api/tickers/AAPL
                  ↓
Data returned from backend
                  ↓
Component renders ticker details and options table
```

---

## Responsive Design

### Breakpoints (Tailwind)

- **Mobile**: < 640px (`sm`)
- **Tablet**: 640px - 1024px (`md`)
- **Desktop**: > 1024px (`lg`)
- **Large Desktop**: > 1280px (`xl`)

### Responsive Behavior

**Sidebar Navigation**:
- Full width on desktop
- Collapsible on tablet/mobile
- Icon-only or full labels based on `sidebarOpen` state

**Header Elements**:
- All visible on desktop
- Data mode hidden on mobile (`hidden sm:block`)
- Last scan time hidden on tablets (`hidden lg:block`)

**Tables**:
- Horizontal scroll on mobile
- Full width on desktop
- Font size reduced on mobile (`text-xs`)

**Grid Layouts**:
- Single column on mobile
- 2 columns on tablet (`md:grid-cols-2`)
- 3+ columns on desktop (`lg:grid-cols-3`)

---

## Key Implementation Details

### URL Parameters

**Ticker Symbol Routing**:
```typescript
// In App.tsx route definition
<Route path="/ticker/:symbol" element={<TickerDetail />} />

// In TickerDetail.tsx
const { symbol } = useParams<{ symbol: string }>()

// Construct API calls
`/api/tickers/${symbol}`
`/api/options/${symbol}`
```

### Dynamic Links

From Dashboard to Ticker Detail:
```typescript
// In Dashboard component
<Link to={`/ticker/${ticker.ticker}`}>
  {ticker.ticker}
</Link>
```

### Health Status Monitoring

App.tsx polls backend health status via `useApi`:
```typescript
const { data: health } = useApi<HealthStatus>('/api/health')

useEffect(() => {
  if (health) {
    setHealth(health)  // Update global state
  }
}, [health, setHealth])
```

Header displays this status with color coding:
- Green pulse: Healthy connection
- Red pulse: Connection error

---

## TypeScript Configuration

### Path Aliases

Configured in `tsconfig.json` for clean imports:

```typescript
// Instead of:
import Header from '../../../components/Header'

// Use:
import { Header } from '@components/Header'
```

**Aliases**:
- `@components/*` → `src/components/*`
- `@pages/*` → `src/pages/*`
- `@hooks/*` → `src/hooks/*`
- `@utils/*` → `src/utils/*`
- `@types/*` → `src/types/*`
- `@store/*` → `src/store/*`
- `@styles/*` → `src/styles/*`

---

## Development Workflow

### Adding a New Route

1. **Create page component**: `src/pages/NewPage.tsx`
2. **Add import** in `App.tsx`
3. **Add route** in Routes section
4. **Add navigation item** (optional) in `Navigation.tsx`
5. **Add styling** as needed

### Adding a New Component

1. **Create component**: `src/components/NewComponent.tsx`
2. **Export from file** as named export
3. **Import in parent** using `@components/` alias
4. **Add component class** to `globals.css` if needed

### Styling Components

1. **Use Tailwind classes** for styling
2. **Add custom classes** to `globals.css` for reuse
3. **Use component vars** for flexibility
4. **Ensure dark mode** colors (grays 800-900)

---

## Performance Considerations

### Code Splitting

React Router automatically code-splits pages:
- Each page component loaded on demand
- Reduces initial bundle size
- Improves time to interactive (TTI)

### Caching

- `useApi` hook manages data caching
- Zustand stores prevent re-renders
- Memoization used in component rendering

### Animations

- CSS animations defined in `globals.css`
- Used sparingly for visual feedback
- Optimized for 60 FPS

---

## Accessibility Features

### ARIA Labels

All interactive elements include:
- `aria-label` for icon buttons
- `title` attributes for hover tooltips
- Semantic HTML structure

### Keyboard Navigation

- Sidebar items linkable via Tab
- Focus indicators on buttons and links
- Proper color contrast (WCAG AA)

### Screen Readers

- Component structure is semantic
- Icons paired with text labels
- Form inputs properly labeled

---

## Error Handling

### Error Boundary

`ErrorBoundary.tsx` catches rendering errors:
- Prevents white screen of death
- Shows error message to user
- Allows recovery

### API Errors

`useApi` hook handles:
- Network failures
- Timeout retries
- Loading states

### Type Safety

TypeScript prevents:
- Wrong prop types
- Missing null checks
- Type mismatches at compile time

---

## Best Practices

1. **Use Hooks**: All functional components
2. **Type Everything**: No `any` types
3. **Small Components**: Single responsibility
4. **Reuse Components**: DRY principle
5. **Semantic HTML**: Proper element types
6. **Accessible**: ARIA labels and keyboard nav
7. **Responsive**: Mobile-first design
8. **Dark Mode**: Consistent color scheme
9. **Error Handling**: Try/catch patterns
10. **Comments**: Document complex logic

---

## Common Tasks

### Navigate Programmatically

```typescript
import { useNavigate } from 'react-router-dom'

const navigate = useNavigate()
navigate('/alerts')  // Go to alerts
navigate(-1)         // Go back
```

### Access URL Parameters

```typescript
import { useParams } from 'react-router-dom'

const { symbol } = useParams<{ symbol: string }>()
```

### Get Current Location

```typescript
import { useLocation } from 'react-router-dom'

const location = useLocation()
// location.pathname === '/ticker/AAPL'
```

### Update Global State

```typescript
import { useConfigStore } from '@store/configStore'

const { setConfig } = useConfigStore()
setConfig(newConfig)
```

---

## Summary

The Option Chain Dashboard is built with:
- **React 18** for UI rendering
- **React Router v6** for client-side routing
- **Zustand** for state management
- **Tailwind CSS** for styling
- **TypeScript** for type safety
- **Vite** for fast development

The architecture provides a responsive, accessible, and maintainable frontend with clear separation of concerns and a dark-mode-first design.

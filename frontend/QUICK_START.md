# Quick Start Guide - Option Chain Dashboard Frontend

## Installation & Setup (5 minutes)

### 1. Navigate to Frontend Directory
```bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Verify Backend is Running
The frontend needs the backend API running on port 8061:
```bash
# In another terminal
python -m uvicorn functions.api.main:app --host 0.0.0.0 --port 8061 --reload
```

### 4. Start Development Server
```bash
npm run dev
```

You should see:
```
  VITE v5.0.0 ready in XXX ms

  ➜ Local:   http://localhost:8060/
  ➜ press h to show help
```

### 5. Open in Browser
Navigate to: http://localhost:8060

## Available Commands

```bash
npm run dev        # Start development server (with hot reload)
npm run build      # Build for production
npm run preview    # Preview production build locally
npm run lint       # Check code quality (ESLint)
npm run type-check # Check TypeScript types
```

## Project Structure at a Glance

```
src/
├── main.tsx              # App entry point
├── App.tsx               # Router & layout
├── components/           # Reusable UI components (Header, Navigation, etc.)
├── pages/                # Route pages (Dashboard, AlertFeed, etc.)
├── hooks/                # Custom hooks (useApi, useWebSocket)
├── store/                # Global state (alertStore, configStore, uiStore)
├── types/                # TypeScript type definitions
├── utils/                # Utilities (apiClient, formatters, constants)
└── styles/               # Global CSS (tailwind, globals)
```

## Common Development Tasks

### Adding a New Page

1. Create `src/pages/YourPage.tsx`:
```typescript
import React from 'react'
import { useApi } from '@hooks/useApi'

export const YourPage: React.FC = () => {
  const { data, loading } = useApi<YourType>('/api/endpoint')
  
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Your Page</h1>
      {/* Your content */}
    </div>
  )
}

export default YourPage
```

2. Add route in `src/App.tsx`:
```typescript
<Route path="/yourpage" element={<YourPage />} />
```

3. Add navigation item in `src/components/Navigation.tsx`

### Fetching Data

```typescript
import { useApi } from '@hooks/useApi'

// Simple GET
const { data, loading, error } = useApi<DataType>('/api/endpoint')

// With dependencies (refetch when changes)
const { data, refetch } = useApi<DataType>(
  `/api/options/${ticker}`,
  { dependencies: [ticker] }
)

// POST request
const { execute, loading } = useApiPost<RequestType>('/api/endpoint')
const result = await execute(payload)
```

### Using Global State

```typescript
import { useAlertStore } from '@store/alertStore'

// In component
const { alerts, stats, removeAlert } = useAlertStore()

// Update state
removeAlert(alertId)
```

### Formatting Values

```typescript
import { 
  formatPrice, 
  formatPercent, 
  formatVolume,
  formatDate,
  getSeverityColor 
} from '@utils/formatters'

formatPrice(123.456)     // "123.46"
formatPercent(5.5)       // "+5.50%"
formatVolume(1500000)    // "1.50M"
formatDate(new Date())   // "01/26/2026"
getSeverityColor('high') // "text-orange-600 bg-orange-50"
```

### Styling Components

```typescript
// Using Tailwind classes
<div className="p-6 bg-white rounded-lg shadow-md border border-gray-200">
  <h1 className="text-3xl font-bold text-gray-900">Heading</h1>
  <button className="btn-primary">Click me</button>
</div>

// Custom component classes (in tailwind.css)
// .card, .btn-primary, .badge-critical, etc.
```

## API Endpoints Reference

All requests go to `http://localhost:8061/api/`:

| Method | Endpoint | Returns |
|--------|----------|---------|
| GET | `/health` | System health status |
| GET | `/config` | Configuration info |
| GET | `/alerts` | List of alerts |
| GET | `/alerts?limit=10` | Latest 10 alerts |
| GET | `/tickers` | Stock ticker data |
| GET | `/tickers?limit=5` | Top 5 tickers |
| GET | `/options/chain?ticker=AAPL` | Option chain for ticker |
| GET | `/strategies` | Available strategies |

## Debugging Tips

### 1. Check Console Errors
Open browser DevTools: F12 → Console

### 2. Network Requests
DevTools → Network tab → Filter by "api"

### 3. React State
```typescript
import { useAlertStore } from '@store/alertStore'

// Add to any component to log state
const state = useAlertStore()
console.log('Alerts:', state.alerts)
console.log('Stats:', state.stats)
```

### 4. API Client Debugging
```typescript
import apiClient from '@utils/apiClient'

// Check base URL
console.log(apiClient.defaults.baseURL)

// Manual API call
const data = await apiClient.get('/api/alerts')
console.log(data)
```

### 5. Type Errors
```bash
npm run type-check
```
Shows all TypeScript errors without building

## Environment Variables

Copy `.env.example` to `.env` and modify:

```bash
VITE_API_BASE_URL=http://localhost:8061
VITE_WS_URL=ws://localhost:8061/ws
VITE_ENABLE_REAL_TIME_UPDATES=true
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot find module" | Run `npm install` |
| Port 8060 already in use | `lsof -i :8060` then `kill -9 PID` |
| API returns 404 | Verify backend is running on port 8061 |
| Hot reload not working | Check Vite console for errors |
| TypeScript errors | Run `npm run type-check` to see all issues |
| Styles not applying | Clear browser cache (Ctrl+Shift+Delete) |

## Next Steps

1. **Explore the codebase** - Read through components and pages
2. **Read ARCHITECTURE.md** - Understand the full system design
3. **Start modifying** - Edit a page to see hot reload in action
4. **Add features** - Create new components and pages
5. **Test integration** - Ensure frontend works with backend

## Useful Resources

- **Tailwind CSS**: https://tailwindcss.com/docs
- **React Hooks**: https://react.dev/reference/react
- **React Router**: https://reactrouter.com/
- **Zustand**: https://github.com/pmndrs/zustand
- **TypeScript**: https://www.typescriptlang.org/docs/

## Build for Production

```bash
# Create optimized production build
npm run build

# Preview production build locally
npm run preview

# Output in dist/ folder ready to deploy
```

## Questions?

- Check existing components for code examples
- Review ARCHITECTURE.md for design patterns
- Look at `.env.example` for all available settings
- Check browser console for error messages

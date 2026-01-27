# React App Quick Reference

## File Locations

### Main Files
- **App.tsx** - Main component with routing (85 lines)
- **main.tsx** - Entry point with BrowserRouter (13 lines)
- **index.css** - CSS imports

### Pages (6 total)
- `/` → `Dashboard.tsx`
- `/alerts` → `AlertFeed.tsx`
- `/ticker/:symbol` → `TickerDetail.tsx` ⭐ NEW
- `/options` → `OptionChains.tsx`
- `/strategies` → `StrategyExplorer.tsx`
- `/config` → `ConfigStatus.tsx`

### Components (5 total)
- Header.tsx - Top bar with status
- Navigation.tsx - Sidebar with nav links
- ErrorBoundary.tsx - Error handling
- AlertCard.tsx - Alert display
- MetricsRow.tsx - Metrics display

### Styles
- styles/tailwind.css - Tailwind directives
- styles/globals.css - Component classes

## Quick Navigation

### Import Paths
```typescript
import { Header } from '@components/Header'
import Dashboard from '@pages/Dashboard'
import { useConfigStore } from '@store/configStore'
```

### Navigate in Code
```typescript
const navigate = useNavigate()
navigate('/alerts')
navigate(`/ticker/AAPL`)
```

## Key Features

✅ 6 Routes + 1 Catch-all
✅ Dark Mode (bg-gray-900)
✅ Responsive Design
✅ TypeScript Support
✅ Error Boundaries
✅ Health Status Indicator
✅ Collapsible Sidebar
✅ Component Classes (.btn-primary, .card, .alert-high)

## Color Scheme

- Background: gray-900 (#111827)
- Cards: gray-800 (#1f2937)
- Borders: gray-700 (#374151)
- Text: white / gray-300
- Accents: blue-600, red-500, green-500, yellow-500

## Component Classes

```css
.btn-primary    /* Blue button */
.btn-secondary  /* Gray button */
.btn-danger     /* Red button */
.btn-success    /* Green button */
.card           /* Standard card */
.alert-high     /* Red alert */
.alert-medium   /* Yellow alert */
.alert-low      /* Green alert */
```

## Development Commands

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Type check
npm run type-check
```

## Documentation

- **APP_STRUCTURE.md** - Complete architecture guide
- **ROUTING_GUIDE.md** - Navigation and routing reference
- **IMPLEMENTATION_COMPLETE.md** - Project summary
- **IMPLEMENTATION_CHECKLIST.md** - Requirements checklist

---

**Status**: ✅ Ready for Development
**Last Updated**: January 26, 2026

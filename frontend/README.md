# Option Chain Dashboard - Frontend

A real-time React-based frontend for analyzing option chains, monitoring alerts, and exploring trading strategies.

## Features

- Real-time alerts and notifications
- Option chain visualization and analysis
- Strategy explorer with signal generation
- System health monitoring
- Responsive design with Tailwind CSS
- TypeScript for type safety

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── Header.tsx
│   ├── Navigation.tsx
│   ├── AlertCard.tsx
│   ├── MetricsRow.tsx
│   └── ErrorBoundary.tsx
├── pages/               # Page-level components
│   ├── Dashboard.tsx
│   ├── AlertFeed.tsx
│   ├── OptionChains.tsx
│   ├── StrategyExplorer.tsx
│   └── ConfigStatus.tsx
├── hooks/               # Custom React hooks
│   ├── useApi.ts
│   ├── useWebSocket.ts
│   └── useLocalStorage.ts
├── store/               # Zustand state management
│   ├── alertStore.ts
│   ├── configStore.ts
│   └── uiStore.ts
├── types/               # TypeScript type definitions
│   ├── api.ts
│   ├── alert.ts
│   └── features.ts
├── utils/               # Utility functions
│   ├── apiClient.ts
│   ├── formatters.ts
│   └── constants.ts
└── styles/              # Global styles
    ├── tailwind.css
    └── globals.css
```

## Getting Started

### Prerequisites

- Node.js 18+ or higher
- npm or yarn

### Installation

1. Navigate to the frontend directory:
```bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment file:
```bash
cp .env.example .env
```

### Development

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:8060`

### Building

Build for production:
```bash
npm run build
```

### Preview Production Build

Preview the production build:
```bash
npm run preview
```

### Linting

Check code quality:
```bash
npm run lint
```

### Type Checking

Run TypeScript type checking:
```bash
npm run type-check
```

## Technologies

- **React 18**: Modern UI library
- **TypeScript**: Static typing for JavaScript
- **Vite**: Fast build tool and dev server
- **React Router DOM**: Client-side routing
- **Zustand**: Lightweight state management
- **Axios**: HTTP client
- **Tailwind CSS**: Utility-first CSS framework
- **PostCSS**: CSS processing

## API Integration

The frontend connects to the backend API running on `http://localhost:8061`. Ensure the backend is running before starting the frontend.

### Key API Endpoints

- `GET /api/health` - System health check
- `GET /api/config` - Configuration status
- `GET /api/alerts` - Alert feed
- `GET /api/tickers` - Ticker data
- `GET /api/options/chain` - Option chain data
- `GET /api/strategies` - Available strategies

## State Management

The application uses Zustand for global state management:

- **alertStore**: Alert data and filtering
- **configStore**: System configuration and health
- **uiStore**: UI state (sidebar, selections, view modes)

## Hooks

Custom React hooks for common functionality:

- `useApi`: Fetch data from API
- `useWebSocket`: Real-time WebSocket connections
- `useLocalStorage`: Persist data to browser storage

## Components

### Header
- Sidebar toggle
- System health indicator
- Settings access

### Navigation
- Collapsible sidebar
- Route navigation
- User profile

### AlertCard
- Alert display with severity styling
- Action buttons (resolve, dismiss)
- Data details

### MetricsRow
- Responsive metrics display
- Change indicators
- Custom icons

### ErrorBoundary
- Error catching and display
- Recovery options

## Styling

The project uses Tailwind CSS with custom configuration:

- Custom color schemes
- Reusable component classes
- Global animations
- Responsive utilities

## Environment Variables

See `.env.example` for available configuration options.

## Development Guidelines

- Use TypeScript strict mode
- Follow React hooks best practices
- Use custom hooks for API calls
- Implement error handling
- Keep components focused and reusable
- Use absolute imports with path aliases

## Build & Deployment

- Development: `npm run dev`
- Production: `npm run build` then `npm run preview`
- The frontend is bundled in `dist/` directory

## Performance Optimizations

- Code splitting via Vite
- Lazy loading of routes (TODO)
- Component memoization (TODO)
- Image optimization (TODO)

## Accessibility

- Semantic HTML
- ARIA labels where needed
- Keyboard navigation support
- Focus management

## Future Enhancements

- [ ] Dark mode support
- [ ] Advanced charting with D3/Chart.js
- [ ] Real-time WebSocket updates
- [ ] User authentication
- [ ] Export functionality
- [ ] Custom alerts configuration
- [ ] Strategy backtesting

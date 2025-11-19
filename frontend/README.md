# CatSyphon Frontend

Modern React web interface for CatSyphon - AI coding assistant analytics platform.

## Overview

The frontend is a **React 19** + **TypeScript** application built with **Vite 7**, providing an interactive dashboard for exploring AI coding assistant conversation logs.

### Key Features

- 📊 **Project Analytics** - Sentiment timelines, session filtering, tool usage charts (Epic 7)
- 🔍 **Conversation Explorer** - Search, filter, and browse AI-assisted coding sessions
- 📈 **Real-time Updates** - 15-second auto-refresh with freshness indicators
- 🎨 **Modern UI** - shadcn/ui components with Tailwind CSS 4
- ⚡ **Performance** - TanStack Query caching, code splitting, optimistic updates

## Architecture

```
frontend/src/
├── pages/                      # Route-level components
│   ├── Dashboard.tsx           # System overview (workspace stats)
│   ├── ProjectList.tsx         # All projects with CRUD
│   ├── ProjectDetail.tsx       # Epic 7: Project analytics dashboard
│   ├── ConversationList.tsx    # Search & filter conversations
│   ├── ConversationDetail.tsx  # Single conversation view
│   ├── Ingestion.tsx           # Upload & watch directory management
│   └── Setup.tsx               # Onboarding wizard
│
├── components/                 # Shared components
│   ├── ui/                     # shadcn/ui base components
│   ├── ConversationCard.tsx
│   ├── ProjectCard.tsx
│   └── ...
│
├── lib/                        # Utilities and setup
│   ├── api.ts                  # Type-safe API client
│   ├── queryClient.ts          # TanStack Query configuration
│   └── utils.ts                # Helper functions
│
├── types/                      # TypeScript interfaces
│   └── api.ts                  # API response types
│
├── App.tsx                     # Root component with routing
├── main.tsx                    # Entry point
└── index.css                   # Global styles (Tailwind)
```

### Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.0 | UI framework |
| **TypeScript** | 5.9 | Type safety |
| **Vite** | 7.0 | Build tooling |
| **React Router** | 7.0 | Client-side routing |
| **TanStack Query** | 5.0 | Data fetching & caching |
| **shadcn/ui** | Latest | UI components |
| **Tailwind CSS** | 4.0 | Styling |
| **Recharts** | Latest | Data visualization |
| **Vitest** | Latest | Testing framework |

## Getting Started

### Prerequisites

- **Node.js 20 LTS** ([Download](https://nodejs.org/))
- **pnpm** (fast package manager)
- **Backend running** on http://localhost:8000

### Installation

```bash
# From project root
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

Open http://localhost:5173 in your browser.

### Available Scripts

```bash
# Development server with HMR
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview

# Run tests (watch mode)
pnpm test

# Run tests once (CI mode)
pnpm test -- --run

# Test with coverage
pnpm run test:coverage

# Interactive test UI
pnpm run test:ui

# Type checking
pnpm tsc --noEmit

# Linting
pnpm lint

# Lint with auto-fix
pnpm lint --fix
```

## Key Features

### Epic 7: Project Detail Page

The `ProjectDetail.tsx` page provides comprehensive project analytics:

**Features:**
- 📅 **Date range filtering** (7d, 30d, 90d, all)
- 📈 **Sentiment timeline** (line chart with average sentiment per day)
- 🛠️ **Tool usage chart** (bar chart of AI tools used)
- 🔍 **Session filtering** (by developer, outcome, date range)
- 📊 **Session sorting** (by start_time, duration, messages, success rate)
- 🎨 **Visual polish** with loading states, empty states, error handling

**Components:**
- `DateRangeSelector` - Toggle buttons for date filtering
- `SentimentTimeline` - Recharts LineChart with gradient
- `ToolUsageChart` - Recharts BarChart with hover states
- `SessionTable` - Sortable, filterable session list

### Real-Time Data Fetching

TanStack Query provides automatic caching and background refetching:

```typescript
// Example: Auto-refresh project stats every 15 seconds
const { data, isLoading, error, dataUpdatedAt } = useQuery({
  queryKey: ['project-stats', projectId, dateRange],
  queryFn: () => api.getProjectStats(projectId, { date_range: dateRange }),
  refetchInterval: 15000,  // 15 seconds
  staleTime: 10000,        // Consider stale after 10s
})
```

**Features:**
- ✨ Automatic background refetching
- 🔄 Intelligent cache invalidation
- ⚡ Optimistic updates
- 🎯 Request deduplication
- 📊 Freshness indicators

### Type-Safe API Client

The `lib/api.ts` module provides type-safe API calls:

```typescript
// All API calls are fully typed
export const api = {
  // Conversations
  getConversations: (params: ConversationQueryParams): Promise<Conversation[]> => {...},
  getConversation: (id: string): Promise<ConversationDetail> => {...},

  // Projects
  getProjects: (): Promise<Project[]> => {...},
  getProjectStats: (id: string, params: StatsParams): Promise<ProjectStats> => {...},
  getProjectSessions: (id: string, params: SessionParams): Promise<Session[]> => {...},

  // Stats
  getOverviewStats: (): Promise<OverviewStats> => {...},
}
```

TypeScript ensures compile-time safety for all API interactions.

### Component Patterns

#### Page Components

Page components handle routing and data fetching:

```tsx
export default function ProjectDetail() {
  const { id } = useParams()
  const [dateRange, setDateRange] = useState('all')

  const { data: stats, isLoading } = useQuery({
    queryKey: ['project-stats', id, dateRange],
    queryFn: () => api.getProjectStats(id, { date_range: dateRange }),
    refetchInterval: 15000,
  })

  if (isLoading) return <LoadingSpinner />
  if (!stats) return <ErrorState />

  return (
    <div>
      <DateRangeSelector value={dateRange} onChange={setDateRange} />
      <SentimentTimeline data={stats.sentiment_timeline} />
      {/* ... */}
    </div>
  )
}
```

#### Reusable Components

Shared components follow composition patterns:

```tsx
interface SentimentTimelineProps {
  data: SentimentTimelinePoint[]
  loading?: boolean
}

export function SentimentTimeline({ data, loading }: SentimentTimelineProps) {
  if (loading) return <Skeleton />
  if (!data || data.length === 0) return <EmptyState />

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis domain={[-1, 1]} />
        <Tooltip />
        <Line type="monotone" dataKey="avg_sentiment" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

## Styling

### Tailwind CSS

We use **Tailwind CSS 4** with custom configuration:

```tsx
// Example: Responsive grid with Tailwind
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {projects.map(project => (
    <ProjectCard key={project.id} {...project} />
  ))}
</div>
```

### shadcn/ui Components

Pre-built, accessible components:

```tsx
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

<Card>
  <CardHeader>
    <h2>Project Stats</h2>
    <Badge variant="success">Active</Badge>
  </CardHeader>
  <CardContent>
    <Button onClick={handleRefresh}>Refresh</Button>
  </CardContent>
</Card>
```

**Available components:**
- Button, Badge, Card, Dialog, Dropdown
- Input, Select, Checkbox, Radio
- Table, Tabs, Tooltip, Sheet
- And more...

## Testing

### Test Structure

```
src/pages/
├── ProjectDetail.tsx
└── ProjectDetail.test.tsx      # Co-located tests
```

### Testing Patterns

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import ProjectDetail from './ProjectDetail'

describe('ProjectDetail', () => {
  it('should render sentiment timeline', async () => {
    // Arrange: Setup query client and mock data
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    })

    // Act: Render component
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectDetail />
      </QueryClientProvider>
    )

    // Assert: Check for expected elements
    await waitFor(() => {
      expect(screen.getByText(/sentiment timeline/i)).toBeInTheDocument()
    })
  })

  it('should filter by date range', async () => {
    const user = userEvent.setup()

    render(<ProjectDetail />)

    // Click 7d filter
    await user.click(screen.getByRole('button', { name: /7d/i }))

    // Verify API called with correct params
    await waitFor(() => {
      expect(mockApi.getProjectStats).toHaveBeenCalledWith(
        expect.any(String),
        { date_range: '7d' }
      )
    })
  })
})
```

### Test Best Practices

✅ **Do:**
- Test user behavior, not implementation
- Use `data-testid` for stable selectors
- Test loading and error states
- Mock API calls consistently
- Use `waitFor` for async operations

❌ **Don't:**
- Test UI text that changes frequently
- Test CSS class names
- Test React Query internals
- Use arbitrary timeouts

### Running Tests

```bash
# Watch mode (development)
pnpm test

# Single run (CI)
pnpm test -- --run

# Coverage report
pnpm run test:coverage

# Interactive UI
pnpm run test:ui

# Specific file
pnpm test ProjectDetail
```

## Performance Optimization

### Code Splitting

Routes are automatically code-split with React Router:

```tsx
// App.tsx - Lazy loaded routes
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'))

<Suspense fallback={<LoadingSpinner />}>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/projects/:id" element={<ProjectDetail />} />
  </Routes>
</Suspense>
```

### Query Optimization

```tsx
// Prefetch data on hover
const queryClient = useQueryClient()

<Link
  to={`/projects/${id}`}
  onMouseEnter={() => {
    queryClient.prefetchQuery({
      queryKey: ['project-stats', id],
      queryFn: () => api.getProjectStats(id),
    })
  }}
>
  View Project
</Link>
```

### Memoization

```tsx
import { useMemo, useCallback } from 'react'

// Expensive computation
const sortedSessions = useMemo(() => {
  return sessions.sort((a, b) => b.start_time - a.start_time)
}, [sessions])

// Event handlers
const handleSort = useCallback((column: string) => {
  setSortColumn(column)
}, [])
```

## Development Workflow

### 1. Create a New Page

```bash
# 1. Create page component
touch src/pages/NewPage.tsx
touch src/pages/NewPage.test.tsx

# 2. Add route in App.tsx
# 3. Add navigation link
# 4. Write tests
```

### 2. Add a New API Endpoint

```tsx
// 1. Add types in src/types/api.ts
export interface NewData {
  id: string
  name: string
}

// 2. Add API method in src/lib/api.ts
export const api = {
  getNewData: (): Promise<NewData[]> =>
    fetch(`${API_URL}/new-endpoint`).then(r => r.json()),
}

// 3. Use in component with TanStack Query
const { data } = useQuery({
  queryKey: ['new-data'],
  queryFn: api.getNewData,
})
```

### 3. Add a shadcn/ui Component

```bash
# Install new component
npx shadcn-ui@latest add calendar

# Use in your code
import { Calendar } from '@/components/ui/calendar'
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Or use different port
pnpm dev --port 3000
```

**Type errors after API changes:**
```bash
# Regenerate types from backend OpenAPI schema
# (Manual sync for now - future: automatic codegen)
pnpm tsc --noEmit
```

**Tests timing out:**
```tsx
// Increase timeout for slow tests
it('should load data', async () => {
  // ...
}, 10000)  // 10 second timeout
```

**Stale cache issues:**
```bash
# Clear React Query dev cache
# Or force refresh with Ctrl+Shift+R

# Clear npm cache
rm -rf node_modules .vite
pnpm install
```

## Contributing

### Code Style

- **TypeScript**: Strict mode enabled
- **Components**: Functional components with hooks
- **Naming**: PascalCase for components, camelCase for functions
- **Imports**: Absolute imports with `@/` alias

### Pull Request Checklist

- [ ] Tests added/updated
- [ ] Type checking passes (`pnpm tsc`)
- [ ] Linting passes (`pnpm lint`)
- [ ] All tests pass (`pnpm test -- --run`)
- [ ] No console errors in browser
- [ ] Responsive design tested (mobile, tablet, desktop)
- [ ] Accessibility tested (keyboard navigation, screen readers)

## Resources

### Documentation

- **[Main README](../README.md)** - Project overview
- **[Architecture](../ARCHITECTURE.md)** - System design
- **[Backend API](../backend/README.md)** - API documentation

### External Resources

- [React 19 Docs](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [TanStack Query](https://tanstack.com/query/latest)
- [shadcn/ui](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Recharts](https://recharts.org/)
- [Vitest](https://vitest.dev/)

---

**Built with ❤️ using modern React best practices**

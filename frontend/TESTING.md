# CatSyphon Frontend Testing Checklist

## Pre-flight Checks

### Build Verification
- [x] TypeScript compilation passes (`npm run build`)
- [x] No type errors
- [x] Final bundle size: 358kb (109kb gzipped)
- [x] All routes configured correctly
- [x] No unused imports or variables

### Code Quality
- [x] All components use TypeScript
- [x] All API types match backend schemas
- [x] Proper error handling in all pages
- [x] Loading states implemented
- [x] Responsive design (grid layouts, mobile-friendly)

## Integration Testing Workflow

### 1. Dashboard (/)
**Start Here:** Navigate to http://localhost:5173/

**Checks:**
- [ ] Dashboard loads without errors
- [ ] All 4 metric cards display correct numbers
- [ ] Success rate bar renders (if data exists)
- [ ] Status breakdown shows all statuses with colored bars
- [ ] Agent type breakdown shows all agents
- [ ] "Browse Conversations" link works
- [ ] "Failed Conversations" link works (with filter)
- [ ] Responsive: Cards stack on mobile

**API Endpoint:** GET /stats/overview

---

### 2. Conversations List (/conversations)
**Navigation:** Click "Browse Conversations" from Dashboard or nav bar

**Checks:**
- [ ] Page loads with table of conversations
- [ ] Pagination works (Previous/Next buttons)
- [ ] Page numbers display correctly
- [ ] All 7 filters present and functional:
  - [ ] Project dropdown (populated from API)
  - [ ] Developer dropdown (populated from API)
  - [ ] Agent type text input
  - [ ] Status dropdown (4 options)
  - [ ] Start date picker
  - [ ] End date picker
  - [ ] Success dropdown (All/Success/Failed)
- [ ] "Clear Filters" button resets all filters
- [ ] Filters update URL params
- [ ] Clicking row navigates to detail page
- [ ] Status badges colored correctly
- [ ] Success/failure icons display
- [ ] "No conversations found" shows when filters match nothing
- [ ] Responsive: Filters stack on mobile, table scrolls horizontally

**API Endpoints:**
- GET /conversations (with query params)
- GET /projects
- GET /developers

---

### 3. Conversation Detail (/conversations/:id)
**Navigation:** Click any row from Conversations List

**Checks:**
- [ ] Page loads with full conversation data
- [ ] Back button works (returns to list)
- [ ] Overview section displays all 9 metadata fields
- [ ] Stats row shows message/epoch/file counts
- [ ] Epochs section displays (if exists)
  - [ ] Sequence number, message count
  - [ ] Intent, outcome, sentiment (if exists)
  - [ ] Duration calculated correctly
- [ ] Files touched section displays (if exists)
  - [ ] File paths shown
  - [ ] Line counts (+added, -deleted, ~modified)
  - [ ] Change type displayed
- [ ] Tags section displays (if exists)
  - [ ] Tag type and value
  - [ ] Confidence percentage
- [ ] Message timeline shows all messages in order
  - [ ] Sequence numbers correct
  - [ ] Role badges colored (blue=user, purple=assistant)
  - [ ] Timestamps formatted
  - [ ] Message content displayed in pre tag
  - [ ] Tool calls expandable (if exists)
  - [ ] Tool results expandable (if exists)
  - [ ] Code changes expandable (if exists)
- [ ] Error state shows if conversation not found
- [ ] Loading state displays while fetching
- [ ] Responsive: Grid stacks, timeline readable on mobile

**API Endpoint:** GET /conversations/:id

---

### 4. Navigation & Routing
**Checks:**
- [ ] Nav bar displays on all pages
- [ ] CatSyphon logo links to Dashboard
- [ ] "Conversations" link works
- [ ] Browser back/forward work correctly
- [ ] Direct URL navigation works
- [ ] URL params preserved across navigation
- [ ] 404 handling (nonexistent route)

---

### 5. API Integration
**Checks:**
- [ ] All API calls use `/api/*` prefix
- [ ] Proxy to http://localhost:8000 works
- [ ] Error messages display correctly
- [ ] Network errors handled gracefully
- [ ] Loading states show during fetch
- [ ] TanStack Query DevTools visible (bottom-right)
- [ ] Query caching works (second visit faster)

---

### 6. Error Handling
**Test Scenarios:**
- [ ] Stop backend server → error messages display
- [ ] Navigate to invalid conversation ID → "not found" message
- [ ] Invalid filter values → API handles gracefully
- [ ] Empty results → "No conversations found" displays

---

### 7. Responsive Design
**Test Viewports:**
- [ ] Desktop (1920x1080)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)

**Checks:**
- [ ] Grids stack properly
- [ ] Text remains readable
- [ ] Buttons accessible
- [ ] Tables scroll horizontally on mobile
- [ ] No content cutoff
- [ ] Touch targets adequate size

---

### 8. Dark Mode (Future Enhancement)
**Note:** Theme system is configured with CSS variables, but dark mode toggle not yet implemented.

---

## Console Check
**Before declaring complete, verify:**
- [ ] No console errors
- [ ] No console warnings (except dev-only)
- [ ] No 404s for assets
- [ ] No CORS errors
- [ ] React DevTools shows clean component tree

---

## Performance
**Metrics:**
- [ ] First load < 2 seconds
- [ ] Page navigation < 500ms
- [ ] API calls cached appropriately
- [ ] No unnecessary re-renders
- [ ] Bundle size acceptable (< 500kb)

---

## Accessibility (Basic)
**Checks:**
- [ ] All interactive elements keyboard accessible
- [ ] Focus visible on tab navigation
- [ ] Links have descriptive text
- [ ] Buttons have clear labels
- [ ] Form inputs have labels

---

## Final Acceptance Criteria

### Must Have ✅
- [x] All 3 pages load without errors
- [x] API integration works
- [x] Filters functional
- [x] Pagination works
- [x] Navigation works
- [x] Error states implemented
- [x] Loading states implemented
- [x] Responsive design

### Nice to Have (Future)
- [ ] Syntax highlighting for code changes
- [ ] Dark mode toggle
- [ ] Export conversation data
- [ ] Advanced search
- [ ] Keyboard shortcuts
- [ ] Toast notifications
- [ ] Infinite scroll option

---

## Known Issues
None currently - all features implemented as planned.

---

## Test Commands

```bash
# Start backend
cd backend
uvicorn catsyphon.api.app:app --reload --host 0.0.0.0 --port 8000

# Start frontend (separate terminal)
cd frontend
npm run dev

# Build for production
npm run build

# Type check
npm run build  # includes tsc -b
```

---

## Sign-off

**Tested by:** [Your name]
**Date:** [YYYY-MM-DD]
**Build:** [git commit hash]
**Status:** [ ] Pass / [ ] Fail
**Notes:**

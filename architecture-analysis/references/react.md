# ReactJS — what to look for

React apps vary a lot (CRA, Vite, Next.js), but the architecture story is usually:
entry → routing → pages/views → components → state/data layer → API client.

## High-signal files

| Concern | Where to look |
|---------|---------------|
| Entry point | `src/index.{tsx,jsx}` or `src/main.{tsx,jsx}`; for Next.js, `app/` or `pages/` |
| Build & deps | `package.json` — note `react`, `next`, state libs, data libs |
| Routing | `react-router` `<Routes>`/`createBrowserRouter`, or Next.js file-based routes |
| Top-level shell | `src/App.{tsx,jsx}`, layout components |
| State management | Redux/Zustand/Jotai stores, React Context providers |
| Server state / data | React Query / SWR / RTK Query hooks; `fetch`/`axios` wrappers in `api/` or `services/` |
| Component structure | `components/`, `features/`, `pages/` or `views/` directories |
| Cross-cutting | auth context/guards, error boundaries, interceptors, env config |

## Mapping to the architecture doc

- **System context:** the SPA, the user's browser, the backend API(s) it calls, and
  any third-party services (auth provider, analytics, payment).
- **Component view:** routing → pages → shared components, plus the state layer and
  the API client as distinct boxes. Show how data flows from API client → state →
  components.
- **Data model:** if the app has meaningful client-side domain types, model the core
  TypeScript interfaces/DTOs as a `classDiagram` (an `erDiagram` rarely fits a
  frontend). Otherwise summarise the key API resource shapes.
- **Runtime flow:** trace one user action (e.g. "load dashboard") as a
  `sequenceDiagram`: component → hook → API client → backend → state update → render.

## Things worth calling out as decisions/ADRs

- Framework choice (CRA vs. Vite vs. Next.js) and rendering model (CSR/SSR/SSG).
- State management approach and why.
- Data-fetching strategy (React Query vs. manual).
- Styling approach (CSS modules, Tailwind, styled-components).
- Type safety (TypeScript strictness, codegen from API schemas).

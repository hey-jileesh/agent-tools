# Angular — what to look for

Angular is opinionated, so the structure is predictable: modules (or standalone
components) → routed feature areas → components + services (DI) → HTTP layer.

## High-signal files

| Concern | Where to look |
|---------|---------------|
| Workspace config | `angular.json` (projects, build targets), `package.json` |
| Entry point | `src/main.ts` → bootstraps `AppModule` or a standalone `AppComponent` |
| Root module/shell | `src/app/app.module.ts` (or standalone `app.config.ts`), `app.component.*` |
| Routing | `app-routing.module.ts` / `*.routes.ts` — `RouterModule.forRoot/forChild` |
| Feature modules | `src/app/<feature>/` folders, lazy-loaded routes (`loadChildren`/`loadComponent`) |
| Services / DI | `@Injectable()` services, `providedIn: 'root'` |
| HTTP layer | `HttpClient` usage, interceptors (`HTTP_INTERCEPTORS`) |
| State | NgRx (`StoreModule`, effects, reducers) or service-with-subject patterns |
| Models | `*.model.ts` / interfaces under `models/` or feature folders |

## Mapping to the architecture doc

- **System context:** the Angular app, the browser, backend APIs, and external
  services (auth, etc.).
- **Component view:** root module → feature modules (note which are lazy-loaded) →
  components + services, with interceptors and guards as cross-cutting boxes.
- **Data model:** core domain interfaces/models as a `classDiagram`.
- **Runtime flow:** a routed action through component → service → `HttpClient` →
  backend → (NgRx effect/reducer if present) → view, as a `sequenceDiagram`.

## Things worth calling out as decisions/ADRs

- Module-based vs. standalone components.
- Lazy loading strategy.
- State management (NgRx vs. services + RxJS subjects).
- RxJS usage patterns and change detection strategy (default vs. OnPush).
- Interceptor-based cross-cutting concerns (auth token, error handling).

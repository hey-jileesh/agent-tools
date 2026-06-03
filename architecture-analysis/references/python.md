# Python — what to look for

Python projects span web services (Django, Flask, FastAPI), libraries, and data/ML
pipelines. First identify which framework (if any) the dependencies indicate, then
read accordingly.

## Identify the flavour from dependencies

| Dependency seen | Flavour | Architecture lens |
|-----------------|---------|-------------------|
| `django` | Django web app | apps, models (ORM), views, urls, settings |
| `flask` | Flask service | app factory, blueprints, routes, extensions |
| `fastapi` | FastAPI service | routers, Pydantic models, dependencies, async |
| none / `pandas`/`torch` | library or pipeline | packages, entry scripts, data flow |

## High-signal files

| Concern | Where to look |
|---------|---------------|
| Packaging & deps | `pyproject.toml` / `requirements.txt` / `setup.py` |
| Entry point | `manage.py` (Django), `app.py`/`main.py`/`wsgi.py`/`asgi.py` |
| Routing/HTTP | Django `urls.py` + views; Flask blueprints; FastAPI `APIRouter` + path ops |
| Data model | Django models, SQLAlchemy models, Pydantic schemas |
| Config | `settings.py`, env-based config, `config.py` |
| Background work | Celery tasks, APScheduler, RQ |
| External calls | `requests`/`httpx` clients, DB sessions, cache clients |

## Mapping to the architecture doc

- **System context:** the service/app, its clients, and external systems (DB,
  cache, broker, third-party APIs).
- **Component view:** routers/views → services/use-cases → data access, plus
  config and background workers. For a library, show the package layout and public
  API surface instead.
- **Data model:** ORM models (`erDiagram`) for DB-backed apps; Pydantic schemas
  (`classDiagram`) for API contracts.
- **Runtime flow:** one request path (or one pipeline run) as a `sequenceDiagram`.

## Things worth calling out as decisions/ADRs

- Sync vs. async (WSGI vs. ASGI; FastAPI/async views).
- ORM choice (Django ORM vs. SQLAlchemy) and migration strategy.
- Validation/serialisation approach (Pydantic, marshmallow, DRF serializers).
- Task queue / scheduling.
- Dependency & environment management (poetry, pip-tools, venv).

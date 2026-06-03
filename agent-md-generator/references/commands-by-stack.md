# Typical commands by stack (fallback cheat-sheet)

Use these only when the repository does **not** define its own scripts/targets.
Always prefer a command the repo actually declares (a `package.json` script, a
Makefile target, a documented gradle/maven goal). Mark anything from this list that
you couldn't confirm in the repo as `(inferred)`.

## ReactJS / Angular (npm — swap `npm run` for `yarn`/`pnpm` as the lockfile dictates)

| Task | npm | Angular CLI |
|------|-----|-------------|
| Install | `npm ci` (or `npm install`) | `npm ci` |
| Build | `npm run build` | `ng build` |
| Run dev | `npm start` / `npm run dev` | `ng serve` |
| Test all | `npm test` | `ng test` |
| Test single | `npm test -- <pattern>` | `ng test --include='**/foo.spec.ts'` |
| Lint | `npm run lint` | `ng lint` |
| Typecheck | `npx tsc --noEmit` | `npx tsc --noEmit` |

## Java Spring Boot

| Task | Maven | Gradle |
|------|-------|--------|
| Build | `mvn clean package` | `./gradlew build` |
| Run | `mvn spring-boot:run` | `./gradlew bootRun` |
| Test all | `mvn test` | `./gradlew test` |
| Test single | `mvn -Dtest=ClassName#method test` | `./gradlew test --tests "pkg.Class.method"` |
| Skip tests | `mvn package -DskipTests` | `./gradlew build -x test` |
| Format/lint | depends on plugin (spotless, checkstyle) | depends on plugin |

## Python

| Task | pip / venv | poetry |
|------|-----------|--------|
| Install | `pip install -r requirements.txt` | `poetry install` |
| Run (Django) | `python manage.py runserver` | `poetry run python manage.py runserver` |
| Run (Flask) | `flask run` | `poetry run flask run` |
| Run (FastAPI) | `uvicorn app.main:app --reload` | `poetry run uvicorn app.main:app --reload` |
| Test all | `pytest` | `poetry run pytest` |
| Test single | `pytest path/to/test.py::TestClass::test_x` | `poetry run pytest -k test_x` |
| Lint | `ruff check .` / `flake8` | `poetry run ruff check .` |
| Format | `black .` / `ruff format .` | `poetry run black .` |
| Typecheck | `mypy .` | `poetry run mypy .` |

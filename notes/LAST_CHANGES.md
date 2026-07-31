# QuOSS — Últimos cambios y cosas a considerar

> Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).
> Última actualización: **2026-07-31** — cierre de la **Etapa 0 (cimientos)**.

---

## 1. Estado

| | |
|---|---|
| Etapa cerrada | **0 — Cimientos** |
| Siguiente | **1 — `core/`: el vocabulario común** |
| Física implementada | Ninguna todavía (por diseño) |
| Criterio de "hecho" de la etapa | `uv run pytest` pasa y CI verde → **cumplido en local** |

Verificación ejecutada:

```bash
uv run ruff check .          # All checks passed!
uv run ruff format --check . # 6 files already formatted
uv run mypy                  # Success: no issues found in 3 source files
uv run pytest                # 4 passed
```

---

## 2. Archivos creados

| Archivo | Qué es |
|---|---|
| `pyproject.toml` | Metadatos, `src-layout`, deps del núcleo, extras `viz`/`accel`/`web`, grupo `dev`, y config de ruff + mypy + pytest + coverage |
| `uv.lock` | Entorno reproducible bit a bit (1887 líneas). **Versionado** |
| `.python-version` | `3.13` — la versión que `uv` usa por defecto en este repo |
| `src/quoss/__init__.py` | Solo `__version__ = "0.1.0"`. Única fuente de verdad de la versión |
| `tests/conftest.py` | Fixtures de rutas (`project_root`, `scenarios_dir`, `data_dir`) |
| `tests/unit/test_package.py` | 4 tests: import, semver, coherencia con la metadata instalada, deps del núcleo importables |
| `.github/workflows/ci.yml` | Job `lint` (ruff check + format + mypy) y job `test` (pytest en 3.11/3.12/3.13) |
| `.gitignore` | Python, entornos, cachés de tooling, artefactos generados, `web/node_modules` |
| `README.md` | Una pantalla: qué es, instalación, uso, estructura, principios |

## 3. Cambios de estructura

- **`notes/`** (nuevo): recoge la documentación de proyecto en Markdown —
  `ROADMAP.md`, `GUIA_REIMPLEMENTACION.md` y este archivo.
  `README.md` **se queda en la raíz** a propósito: lo referencia
  `pyproject.toml` (`readme = "README.md"`), lo renderiza GitHub como portada y va
  dentro del wheel publicado.
  `docs/` se reserva para lo que dice el roadmap: manual de física autogenerado, ADRs
  y manual de usuario. No mezclar notas de proyecto con documentación generada.
- **Repositorio git inicializado** (`git init -b main`). Todo está *staged*,
  **sin commitear** — el primer commit queda a tu criterio.
- Eliminados los `.gitkeep` de los directorios que ya tienen contenido real
  (`src/quoss/`, `tests/`, `tests/unit/`). El resto se mantienen.

## 4. Entorno

- **`uv` no estaba instalado.** Instalado con `pip install --user uv` → v0.12.0 en
  `~/.local/bin/uv`, que ya está en el `PATH`.
- Versiones resueltas por el lock: numpy 2.4.6 · scipy 1.18 · pydantic 2.13.4 ·
  numba 0.66 · ruff 0.16.1 · mypy 2.3 · pytest 9.1.1 · hypothesis 6.164 · Python 3.13.14.

### Directorios de caché que aparecen al trabajar

Ninguno se versiona (todos están en `.gitignore`) y **todos son regenerables**:
borrarlos solo cuesta tiempo de recomputación, nunca datos.

| Directorio | Lo crea | Para qué | Tamaño típico |
|---|---|---|---|
| `.venv/` | `uv sync` | El entorno virtual del proyecto. Se recrea con `uv sync` | ~564 MB |
| `.mypy_cache/` | `uv run mypy` | Análisis incremental de tipos | ~15 MB |
| `.ruff_cache/` | `uv run ruff` | Lint incremental | ~24 KB |
| `.pytest_cache/` | `uv run pytest` | Últimos fallos (`--lf`), estado de plugins | ~16 KB |
| `__pycache__/` | Python | Bytecode `.pyc` compilado | pequeño |
| `~/.cache/uv/` | `uv` | Caché **global** de wheels, fuera del repo | ~574 MB |

Los ~564 MB de `.venv/` **no son 564 MB de disco nuevos**: `uv` enlaza por *hardlink*
contra `~/.cache/uv/`, así que el espacio real está compartido con cualquier otro
proyecto que use las mismas versiones. `uv cache clean` libera el global.

---

## 5. Decisiones tomadas (y por qué)

| Decisión | Razón | Coste de cambiarla después |
|---|---|---|
| `requires-python = ">=3.11"`, `.python-version` = 3.13 | 3.11 da un suelo amplio para colaboradores; 3.13 es lo que se usa a diario | Bajo ahora, medio cuando haya sintaxis específica de versión |
| Build backend **hatchling** | Estándar, sin ceremonia, lee la versión del `__init__.py` | Bajo |
| Versión **solo** en `src/quoss/__init__.py` (`dynamic = ["version"]`) | Una fuente de verdad; la procedencia de cada resultado la lee de ahí | Bajo |
| Núcleo = numpy + scipy + pydantic. `viz`/`accel`/`web` como **extras**; `dev` como **dependency-group** (PEP 735) | Los extras los instala un consumidor (`quoss[viz]`); `dev` es tooling y nunca se publica. Cumple "el núcleo debe instalarse con muy poco" | Bajo |
| **mypy estricto por módulo**, no global | `strict` no se admite en secciones per-module, así que los flags están enumerados sobre `core`, `orbits`, `channel`, `qkd`, `system`, `scenario`, `kernels`. El resto (cli, api, viz, io, tests) permisivo | Bajo |
| `warn_unused_configs = false` | Esas secciones per-module apuntan a módulos que aún no existen (etapas 1–4); avisar de ello hasta entonces es ruido que enseña a ignorar CI | Trivial — reactivar al cerrar la etapa 4 |
| **pydocstyle (`D`, convención numpy) activo desde el minuto uno** | Es el habilitador del "registro de fórmulas autogenerado" de la guía §5. Retrofitear docstrings a 30 módulos de física después es carísimo | Alto si se pospone |
| `filterwarnings = ["error"]` en pytest | Un `RuntimeWarning` de numpy (overflow, división por cero) rompe el test en vez de colarse como un número plausible. Es la versión test de "prohibido degradar en silencio" | Bajo |
| Marcadores `physics` / `golden` / `slow` declarados ya | La pirámide de tests de la guía tiene sitio desde el principio | Trivial |
| **Sin `[project.scripts]`** | Apuntaría a `quoss.cli.main`, que no existe hasta la etapa 7. Rompe la regla de oro: no escribas algo que importe lo que no existe | Trivial |
| `line-length = 100` | Las fórmulas de física con subíndices no caben cómodas en 88 | Bajo |
| Licencia **MIT** | Máxima reproducibilidad por terceros (revisores) | Medio — ver §6 |
| `UV_LOCKED=1` en CI | Convierte la deriva silenciosa entre `pyproject.toml` y `uv.lock` en un fallo ruidoso | Trivial |

---

## 6. Cosas a considerar

### Bloqueante para la etapa 1

- **Convención de unidades.** Lo dice el roadmap y es la decisión que más fricción
  ahorra o cuesta en todo el proyecto. Hay que fijar: unidad canónica interna (SI
  estricto vs. mixto km/dB), sufijos de nombres (`_km`, `_m`, `_db`, `_deg`, `_rad`),
  y si las conversiones son helpers explícitos o se hacen en el borde (I/O del
  escenario). **Elegirla y no cambiarla.** Candidata a primer ADR.

### Resuelto el 2026-07-31

- **Proyecto personal, sin afiliación institucional.** El CTTC no interviene: `QuOSS`
  vive dentro de `~/Escritorio/Adria_files/CTTC/` solo por dónde está la carpeta, no
  por titularidad. No poner atribución institucional en ningún sitio.
- **Autoría** → `Adrià Sancho <francesc.adria.sancho@gmail.com>` en `pyproject.toml:11`.
  El email anterior (`adria.sancho@ixrev.com`) venía de la cuenta de Claude Code, no
  de una decisión.
- **URLs del repo** → `https://github.com/W1Adri/QuOSS` (+ `Issues`) en
  `pyproject.toml:48-50`. El remoto `origin` ya apunta ahí.
- **Licencia MIT confirmada** y fichero `LICENSE` creado (© 2026 Adrià Sancho). Sin ese
  fichero, `license = "MIT"` en el `pyproject.toml` no concedía nada: por defecto son
  todos los derechos reservados. Verificado que el wheel lo embebe
  (`quoss-0.1.0.dist-info/licenses/LICENSE`, `License-Expression: MIT`).

- **Identidad de los commits** → resuelta: `Adrià Sancho
  <francesc.adria.sancho@gmail.com>`, configurada **local a este repo** (la global
  sigue siendo la de la UPC).

### CI: verificado en remoto

Primer run sobre el commit `12db181` (repo privado `W1Adri/QuOSS`):
**los 4 jobs en verde en 31 s** — `ruff + mypy`, y `pytest` en 3.11, 3.12 y 3.13.
Las hipótesis de fallo que se manejaron antes de ver el log (numba en 3.11,
`setup-uv` roto) eran todas falsas.

Único aviso: `actions/checkout@v4` y `astral-sh/setup-uv@v5` apuntan a Node.js 20,
deprecado; el runner los fuerza a Node 24. Resuelto subiendo a `checkout@v7` y
`setup-uv@v9`.

Corrección respecto a la versión anterior de esta nota: el guardián del lock es
**`UV_LOCKED=1`**, no `UV_FROZEN=1`. No son lo mismo:

| Variable | Qué hace | Si `uv.lock` no cuadra con `pyproject.toml` |
|---|---|---|
| `UV_FROZEN=1` | Instala desde el lock **sin comprobar nada** | Instala un entorno desactualizado en silencio; el fallo aparece más tarde como un `ImportError` confuso |
| `UV_LOCKED=1` | **Afirma** que el lock está al día | Falla de inmediato con un mensaje claro |

El workflow usa `UV_LOCKED=1` (`.github/workflows/ci.yml:14`). Cuando falle, el arreglo
es siempre el mismo: `uv lock` en local y commitear el `uv.lock` resultante.

### Decisiones diferidas (con fecha sugerida)

| Cuándo | Qué decidir |
|---|---|
| Etapa 1 | Convención de unidades (arriba). Primer ADR en `docs/adr/` |
| Etapa 1 | Añadir **import-linter** a CI para que las reglas de dependencia (`core ← física ← system ← engine ← {cli, api, viz}`) sean una propiedad verificada y no una intención. La guía §1 lo sugiere; es barato ahora y salva el diseño a los 6 meses |
| Antes de etapa 2 | **Protocolo de golden tests contra SimulCTTC**: script que congela la salida del código viejo en escenarios fijos, dónde viven esos artefactos (`tests/golden/data/`), qué tolerancia por módulo, y qué se hace cuando difieren. Sin esto acordado, "SimulCTTC es el oráculo" no es operativo |
| Etapa 4 | Formato del resultado: `xarray.Dataset` vs. Parquet + manifest |
| Etapa 7 | Añadir `[project.scripts] quoss = "quoss.cli.main:main"` |
| Etapa 8 | Reactivar `warn_unused_configs = true` en mypy (ya existirán todos los módulos) |

### Deuda pequeña ya identificada

- **`--all-extras` en CI arrastra `numba`.** Si numba tarda en soportar una Python
  nueva, bloquea todo el matrix por una dependencia opcional que aún no se usa.
  Considerar `--extra viz --extra web` hasta que `kernels/numba_backend.py` exista.
- **Suelo `numpy>=1.26` no está testeado.** El lock resuelve 2.4.6 y CI solo prueba
  esa. O se sube el suelo a `>=2.0`, o se añade un job de "oldest deps". Mentir sobre
  el suelo es peor que no soportarlo.
- **Regla `data/**/*.tle` en `.gitignore`** puede chocar con los *snapshots offline
  versionados* de la etapa 6 (que sí deben commitearse). Revisar al llegar allí.
- **`filterwarnings = ["error"]`** necesitará una allowlist concreta cuando entren
  dependencias ruidosas (sgp4, matplotlib). Añadir excepciones **por warning
  específico**, nunca relajar la regla global.
- **Higiene de repo** (guía §5): un solo sistema de metadatos de agentes, no cuatro;
  PDFs y `.tex` fuera del repo de código. Aplica al migrar cosas desde SimulCTTC.

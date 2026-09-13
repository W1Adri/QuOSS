# QuOSS — Quantum Optical Satellite Simulator

Simulador de enlaces cuánticos ópticos satélite↔tierra: órbitas → canal atmosférico →
protocolo QKD → métricas de sistema (SKR, volumen de clave, outage).

Núcleo Python puro y **vectorizado sobre el eje temporal**, sin dependencias web. La
CLI, la API y el frontend son *consumidores* del mismo motor, no parte de él.

> Estado: **Etapa 3 — `system/`**, en curso. Cerradas la **1** (`core/`), la
> **2.1** (`orbits/`: marcos, Kepler, perturbaciones zonales, propagación, TLE/SGP4,
> ángulos de visión), la **2.2** (`channel/`: atmósfera, turbulencia, haz,
> apuntado, fondo, detector y el presupuesto de enlace y de ruido) y la **2.3**
> (`qkd/`: la frontera canal→protocolo, BB84 con decoy vacío+débil, y la cota
> finite-key componible de Lim et al.). De la 3 hay ya `passes.py` y
> `key_volume.py`; siguiente, `monte_carlo.py`.
>
> **Lo que eso permite afirmar hoy:** clave por pase y por día con la cota
> finite-key aplicada al bloque que el pase realmente es
> ([ADR 0011](docs/adr/0011-the-block-is-the-pass.md)). Y lo que midió al hacerlo:
> en un día del enlace de referencia la tasa asintótica reclama **3.78 Mbit** y la
> cota finita certifica **0.43 Mbit**, con **dos de los cuatro pases en cero**
> donde la asintótica reclama 320 y 199 kbit. Por eso `pass_key_volume` devuelve
> `FINITE` y el número asintótico solo se alcanza llamando a una función que se
> llama `asymptotic_…`.
>
> Ver [`notes/ROADMAP.md`](notes/ROADMAP.md) para el orden de construcción,
> [`notes/GUIA_REIMPLEMENTACION.md`](notes/GUIA_REIMPLEMENTACION.md) para el porqué de la
> arquitectura y [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md) para el estado actual.

## Instalación

Requiere [`uv`](https://docs.astral.sh/uv/) (gestiona también la versión de Python):

```bash
uv sync                 # entorno de desarrollo reproducible desde uv.lock
uv sync --all-extras    # + viz, accel y web
```

Extras disponibles: `viz` (matplotlib), `accel` (numba), `web` (FastAPI).
El núcleo solo necesita numpy + scipy + pydantic.

## Uso

```bash
uv run pytest           # suite de tests
uv run ruff check .     # lint
uv run ruff format .    # formato
uv run mypy             # tipos (estricto en core/ y física)
```

```python
import quoss

quoss.__version__
```

La CLI (`quoss run scenario.yaml`, `quoss sweep`, `quoss serve`, `quoss validate`)
llega en la Etapa 7.

## Estructura

```
src/quoss/     core · orbits · channel · qkd · system · scenario · engine
               kernels · io · viz · cli · api
scenarios/     escenarios versionados y reproducibles (.yaml)
data/          datos estáticos read-only + snapshots offline
tests/         unit · physics · golden · api · e2e
validation/    reproducción de literatura, ejecutada en CI
benchmarks/    puerta de regresión de rendimiento
docs/          manual de física (autogenerado) y ADRs
web/           frontend (TS + Vite + Svelte), deps vendorizadas
deploy/        Dockerfile y compose — la imagen funciona offline
```

Regla de dependencia: `core ← orbits/channel/qkd ← system ← engine ← {cli, api, viz}`.
Las flechas nunca van al revés.

## Principios

- **El escenario es un dato**, no un request HTTP: modelo Pydantic serializable a YAML.
- **Prohibido degradar en silencio**: si un modelo no se puede evaluar, sale en
  `warnings[]` del resultado.
- **Procedencia en cada resultado**: hash de escenario + versión de código + versión de
  datos externos + semilla.
- **Incertidumbre de primera clase**: el motor devuelve P5/P50/P95 y outage, no escalares.
- **SimulCTTC no es un oráculo.** Nunca fue validado, y leerlo destapó defectos que
  congelar su salida habría canonizado. Cada módulo de física se cierra contra fuentes
  externas en cuatro niveles (invariantes / valores publicados / implementación
  independiente / regresión propia); ver [`tests/golden/README.md`](tests/golden/README.md).
  Lo que se reporte como validado traza a un valor publicado o a una implementación
  independiente, nunca a un snapshot propio.

## Licencia

MIT — ver [`LICENSE`](LICENSE). © 2026 Adrià Sancho.
Proyecto personal; sin afiliación institucional.

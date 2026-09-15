# QuOSS — Quantum Optical Satellite Simulator

Simulador de enlaces cuánticos ópticos satélite↔tierra: órbitas → canal atmosférico →
protocolo QKD → métricas de sistema (SKR, volumen de clave, outage).

Núcleo Python puro y **vectorizado sobre el eje temporal**, sin dependencias web. La
CLI, la API y el frontend son *consumidores* del mismo motor, no parte de él.

> **Estado, al 2026-09-14.** Las etapas **0 a 6 están cerradas**: `core/`,
> `orbits/`, `channel/`, `qkd/`, `system/`, `scenario/`, `engine/` e `io/`. Eso
> significa que `run(scenario) → result` funciona de punta a punta desde un YAML
> versionado: un día del enlace de referencia son **0.1 s** y 4 pases. De la
> etapa 7 hay `viz/` y **no** hay `cli/`; de la 8, `validation/` está a medias.
>
> **Qué hay y qué no, sin rodeos:**
>
> | | |
> |---|---|
> | **Existe y está cerrado** | `core/` · `orbits/` · `channel/` · `qkd/` · `system/` · `scenario/` · `engine/` · `io/` |
> | **Existe a medias** | `viz/` (style, plots, figures; sin el ADR 0017 que su propio código cita) · `validation/` (base, channel, micius, satquma; **falta `ntanos2021.py`, y `run_all()` lo importa, así que hoy levanta `ModuleNotFoundError`**; no hay `tests/validation/`) |
> | **No existe: solo un `.gitkeep`** | `cli/` · `api/` · `kernels/` · `web/` · `deploy/` · `benchmarks/` |
>
> **Y un defecto conocido de la suite**, que no es del paquete:
> `tests/viz/test_plots.py` importa matplotlib arriba del fichero, así que sin el
> extra `viz` la recogida de `tests/viz/` **falla** en vez de saltarse. El
> paquete sí degrada bien —`quoss.viz` levanta `ConfigurationError` diciendo qué
> instalar—; es el test el que no.
>
> **Lo que se puede afirmar hoy**, que es distinto de lo que está implementado:
> clave por pase y por día con la cota finite-key aplicada al bloque que el pase
> realmente es ([ADR 0011](docs/adr/0011-the-block-is-the-pass.md)), y que el
> motor no añade ni pierde nada al orquestarlo
> ([ADR 0016](docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md)). Lo que
> **no** se puede afirmar todavía es que los números estén validados contra la
> literatura: eso es la etapa 8, y es exactamente la parte que está a medias.
>
> **La cifra que resume el proyecto.** En un día del enlace de referencia
> (Castelldefels, 0.75 m, SSO a 700 km, noche clara, máscara de 10°) la tasa
> asintótica reclama **3.78 Mbit** y la cota finita certifica **0.43 Mbit**, con
> **dos de los cuatro pases en cero** donde la asintótica reclama 320 y 199 kbit.
> Por eso `pass_key_volume` devuelve `FINITE` y el número asintótico solo se
> alcanza llamando a una función que se llama `asymptotic_…`.
>
> Esa clave del día son **433 442 bits** vista por `run(scenario)` y **432 985**
> vista por el *fixture* de la etapa 3, y la diferencia —457 bits, el 0.106 %— no
> es un error de ninguno de los dos: es la altitud de la estación entrando, o no,
> en la integral de turbulencia. Las dos cifras se reproducen a la última cifra en
> `tests/e2e/test_reference_scenarios.py`; la que se reporta es la del motor.
>
> **Un número que este README no puede dar:** la clave depende de una
> transmitancia atmosférica que ninguna fuente abierta publica, así que
> `zenith_transmittance` es un parámetro **obligatorio y sin defecto**, y el
> escenario de referencia declara `1.0` — «sin extinción modelada». Todas las
> cifras de arriba son, por tanto, una **cota superior** sobre la atmósfera y una
> afirmación exacta sobre todo lo demás. Es el hueco 14 del
> [ADR 0009](docs/adr/0009-citation-policy.md), y hay **veintiún** huecos
> declarados y ninguno rellenado con la cita más plausible.
>
> Verificación al 2026-09-14: **3 259 tests**, 99 % de cobertura global, 100 % de
> líneas y ramas en `core/`, `orbits/`, `channel/`, `qkd/`, `system/`,
> `scenario/`, `engine/`, `io/` y `viz/`. Lo que baja el global del 100 % es
> `validation/base.py`, al 59 %, por la etapa 8 a medias.
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

Extras disponibles: `viz` (matplotlib), `export` (pyarrow, para Parquet),
`accel` (numba) y `web` (FastAPI). El núcleo solo necesita numpy + scipy +
pydantic + sgp4 + pyyaml.

La **suite**, en cambio, todavía no es tan modular como el paquete:
`tests/viz/test_plots.py` importa matplotlib en el módulo, así que sin el extra
`viz` la recogida de `tests/viz/` **falla** en vez de saltarse. Está anotado como
pendiente arriba; para correr la suite entera, `uv sync --all-extras`.

## Uso

```bash
uv run pytest           # suite de tests
uv run ruff check .     # lint
uv run ruff format .    # formato
uv run mypy             # tipos (estricto en core/ y física)
```

Un escenario versionado, de fichero a resultado:

```python
from quoss.engine.pipeline import run
from quoss.scenario.io import load_scenario

result = run(load_scenario("scenarios/reference_castelldefels.yaml"))

result.passes.n_passes                      # 4
result.daily.finite_bits.tolist()           # [433442.0]
result.daily.asymptotic_bits.tolist()       # [3779461.558061474]
[w["code"] for w in result.warnings]        # lo que el modelo no pudo afirmar
result.provenance.scenario_hash             # qué entradas produjeron esto
```

Los mismos números salen de `quoss.scenario.defaults.reference_castelldefels()`,
sin tocar el disco. `quoss.engine.sweep` corre barridos de parámetros como una
ejecución de primera clase, y `quoss.io.export.export_result` escribe el
resultado a un directorio que se describe a sí mismo (manifiesto con SHA-256 por
fichero, CSV, `arrays.npz` y, con el extra, Parquet).

**La CLI (`quoss run scenario.yaml`, `quoss sweep`, `quoss validate`) todavía no
existe**: `src/quoss/cli/` está vacío y el `project.scripts` del `pyproject.toml`
apunta a un módulo que aún no hay. Es la etapa 7.

## Estructura

Lo que hay, marcado por lo que hay de verdad:

```
src/quoss/     core ✅  orbits ✅  channel ✅  qkd ✅  system ✅
               scenario ✅  engine ✅  io ✅  viz 🚧  validation 🚧
               cli ⬜  api ⬜  kernels ⬜
scenarios/     ✅ cinco escenarios versionados y reproducibles (.yaml)
data/          ✅ catálogo de estaciones + snapshots offline con manifiesto
tests/         ✅ unit · orbits · channel · qkd · system · scenario · engine
                  · io · viz · e2e · golden      ⬜ physics · api · validation
docs/          ✅ 16 ADRs                        ⬜ manual de física autogenerado
benchmarks/    ⬜ puerta de regresión de rendimiento
web/           ⬜ frontend (TS + Vite + Svelte), deps vendorizadas
deploy/        ⬜ Dockerfile y compose — la imagen funciona offline
```

`✅` cerrado · `🚧` empezado y con huecos declarados arriba · `⬜` solo un
`.gitkeep`. El `validation/` de la raíz del repo es un `.gitkeep`; el código de
validación vive en `src/quoss/validation/`.

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

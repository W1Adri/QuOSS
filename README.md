# QuOSS — Quantum Optical Satellite Simulator

Simulador de enlaces cuánticos ópticos satélite↔tierra: órbitas → canal atmosférico →
protocolo QKD → métricas de sistema (SKR, volumen de clave, outage).

Núcleo Python puro y **vectorizado sobre el eje temporal**, sin dependencias web. La
CLI, la API y el frontend son *consumidores* del mismo motor, no parte de él.

> **Estado, al 2026-09-19.** Las etapas **0 a 8 están cerradas**: `core/`,
> `orbits/`, `channel/`, `qkd/`, `system/`, `scenario/`, `engine/`, `io/`,
> `viz/`, `cli/` y `validation/`. Eso significa que
> `quoss run escenario.yaml --out dir/` funciona de punta a punta desde un YAML
> versionado, para las dos geometrías —un día del enlace de referencia son
> **0.1 s** y 4 pases—, y que `quoss validate` tiene detrás la tabla entera.
>
> **Qué hay y qué no, sin rodeos:**
>
> | | |
> |---|---|
> | **Existe y está cerrado** | `core/` · `orbits/` · `channel/` · `qkd/` · `system/` · `scenario/` · `engine/` · `io/` · `viz/` · `cli/` · `validation/` |
> | **La tabla de validación** | [`docs/validation.md`](docs/validation.md), generada y commiteada: **35 casos de ocho fuentes** — 17 reproducidos, 3 compatibles, **8 no reproducidos** y 7 huecos declarados. Un test la compara byte a byte con lo que la CLI produce hoy |
> | **No existe: solo un `.gitkeep`** | `api/` · `kernels/` · `web/` · `deploy/` |
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
> ([ADR 0016](docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md)). Y
> desde la etapa 8, **contra qué literatura se comparó cada número y qué salió**:
> eso es [`docs/validation.md`](docs/validation.md), y lo honesto de esa tabla
> son sus ocho filas que no reproducen. «Validado» aquí no significa «coincide»,
> significa «se comparó, con una tolerancia derivada, y el resultado está escrito»
> ([ADR 0018](docs/adr/0018-validation-is-a-table-not-a-badge.md)).
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
> **Un número que este README todavía no da, y ahora se sabe cuánto vale:** las
> cifras de arriba son para una atmósfera que **no absorbe ni dispersa**. El
> escenario de referencia declara `zenith_transmittance: 1.0` —«sin extinción
> modelada»— porque el hueco 14 del
> [ADR 0009](docs/adr/0009-citation-policy.md) no tenía número que ofrecer, así
> que son una **cota superior** sobre la atmósfera y una afirmación exacta sobre
> todo lo demás.
>
> Desde el [ADR 0023](docs/adr/0023-traceable-extinction.md) hay un modelo
> —visibilidad → atenuación, por la Ec. (4) de la ITU-R P.1814— y con él la cota
> tiene tamaño: **23 km de visibilidad, la línea más limpia del código
> meteorológico de la UIT, son 0.230 dB cenitales y el 22.7 % de esos 433 442
> bits**; 10 km son el 47.7 %; con 2 km de bruma el día **no certifica nada**.
> `zenith_transmittance` sigue siendo obligatorio y sin defecto, y ahora
> `ChannelSpec` acepta o ese número o el modelo, nunca ninguno de los dos. Hay
> **veintitrés** huecos declarados y ninguno rellenado con la cita más plausible.
>
> Verificación al 2026-09-15: **3 640 tests**, **100 % de líneas y ramas** en
> todo `src/quoss` — `core/`, `orbits/`, `channel/`, `qkd/`, `system/`,
> `scenario/`, `engine/`, `io/`, `viz/` y `validation/`.
>
> Ver [`notes/ROADMAP.md`](notes/ROADMAP.md) para qué existe y qué falta,
> [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md) para las cinco últimas entradas
> de la bitácora (las anteriores, íntegras, en [`notes/archive/`](notes/archive/)),
> [`notes/INCONSISTENCIAS.md`](notes/INCONSISTENCIAS.md) para lo que hoy no se
> cumple, y [`docs/adr/`](docs/adr/) para el porqué de cada decisión no obvia.

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
uv run mypy             # tipos (estricto en core/, física y cli/)
```

Desde la línea de órdenes, que es lo que instala `pip install quoss`:

```bash
quoss run scenarios/reference_castelldefels.yaml --out out/reference
quoss run scenarios/ge1_1km.yaml --out out/ge1     # misma orden, otra geometría
quoss sweep scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml
quoss validate
```

O el mismo escenario versionado desde Python, de fichero a resultado:

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

Y un enlace de tierra, que desde el [ADR 0024](docs/adr/0024-the-horizontal-scenario.md)
es el otro miembro de una unión discriminada por el campo `link` y no un caso
especial del anterior:

```python
result = run(load_scenario("scenarios/ge1_1km.yaml"))

type(result).__name__                       # 'HorizontalResult' — sin pases ni días
result.budget.total_db                      # 11.637
result.session.finite_bits                  # 15236099.0 en 60 s de sesión
result.session.finite_bit_s                 # 253934.98
```

Un escenario horizontal **no puede** llevar elevación, máscara, viento ni altura
de estación: el esquema no tiene esos campos y `extra="forbid"` los rechaza por
su nombre. Y su bloque finite-key es la sesión que declara el operador, no un
pase que fije la geometría — lo que cambia de quién es la responsabilidad de que
la cota sea válida, y por eso cada ejecución lo dice en `warnings[]`.

Los mismos números salen de `quoss.scenario.defaults.reference_castelldefels()`,
sin tocar el disco. `quoss.engine.sweep` corre barridos de parámetros como una
ejecución de primera clase —de los dos tipos de escenario—, y
`quoss.io.export.export_result` escribe **los dos resultados** a un directorio que
se describe a sí mismo (manifiesto con SHA-256 por fichero, CSV, y con el extra
Parquet), en **dos formas** que el manifiesto nombra: la de bajada lleva
`passes.csv`, `daily.csv`, `series_<estación>.csv` y `arrays.npz`; la horizontal
lleva `budget.csv` y `session.csv`, una fila cada uno, y **ningún** `arrays.npz`,
porque no hay arrays y un archivo vacío no se distingue de uno cuyos arrays
salieron vacíos ([ADR 0028](docs/adr/0028-the-cli-computes-nothing.md)).

**La CLI existe desde el 2026-09-19:**

```bash
uv run quoss run scenarios/ge1_1km.yaml --out out/ge1
uv run quoss sweep scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml
uv run quoss validate
```

`quoss run` despacha sobre el tag `link` del fichero sin que haya que decírselo,
y **no calcula nada**: lo que escribe reconstruye un resultado igual, término a
término, a `run()` llamado a mano sobre el mismo fichero — la afirmación del
[ADR 0016](docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md) una capa
más arriba. Los `warnings[]` se imprimen **enteros** en `stderr`, nunca
resumidos ni contados, y la salida es distinta de cero cuando aparece un
`DEGRADED` que el escenario no declaró en `expected_degradations`
([ADR 0028](docs/adr/0028-the-cli-computes-nothing.md)).

## Estructura

Lo que hay, marcado por lo que hay de verdad:

```
src/quoss/     core ✅  orbits ✅  channel ✅  qkd ✅  system ✅
               scenario ✅  engine ✅  io ✅  viz ✅  cli ✅  validation ✅
               api ⬜  kernels ⬜
scenarios/     ✅ siete escenarios versionados y reproducibles (.yaml): cinco de
                  bajada (link: downlink) y dos de tierra (link: horizontal),
                  más sweeps/ con los specs de barrido
data/          ✅ catálogo de estaciones + snapshots offline con manifiesto
tests/         ✅ unit · orbits · channel · qkd · system · scenario · engine
                  · io · viz · cli · validation · e2e · golden   ⬜ physics · api
docs/          ✅ 28 ADRs + validation.md (35 casos, generado y commiteado)
                  ⬜ manual de física autogenerado
benchmarks/    ⬜ puerta de regresión de rendimiento
web/           ⬜ frontend (TS + Vite + Svelte), deps vendorizadas
deploy/        ⬜ Dockerfile y compose — la imagen funciona offline
```

`✅` cerrado · `🚧` empezado y con huecos declarados arriba · `⬜` solo un
`.gitkeep`. El `validation/` de la raíz del repo es un `.gitkeep`; el código de
validación vive en `src/quoss/validation/` y sus tests en `tests/validation/`
(siete ficheros, cobertura del 100 % del paquete en líneas y ramas).

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

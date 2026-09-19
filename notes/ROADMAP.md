# QuOSS — Roadmap de implementación

> **Qué es este fichero: estado.** Qué existe, qué falta, y en qué orden se
> construye. **No** es dónde vive el porqué de una decisión: eso son los
> [ADRs](../docs/adr/), uno por decisión, y cada línea de abajo enlaza el suyo.
> La regla se comprueba: `notes/LAST_CHANGES.md` §41 midió que **240 de los 241
> números** que este fichero llegó a citar ya vivían en un ADR, en un test o en
> un docstring, así que repetirlos aquí no guardaba nada y sí creaba una segunda
> copia que envejece sola.

**Regla de oro del orden:** nunca escribas un archivo que importe algo que aún no
existe. El grafo de dependencias es `core ← física ← system ← engine ← {cli, api, viz}`,
y este roadmap lo recorre en ese sentido.

**SimulCTTC no es un oráculo.** Nunca fue validado, y leerlo destapó defectos que
congelar su salida habría canonizado. Queda como **diff informativo y no
bloqueante**: una discrepancia es una pista, nunca un `assert`. El porqué y los
cuatro defectos concretos están en
[`GUIA_REIMPLEMENTACION.md`](GUIA_REIMPLEMENTACION.md).

**Los cuatro niveles de verificación (V1–V4)** están definidos en
[`tests/golden/README.md`](../tests/golden/README.md), que es su dueño. Resumen de
una línea para poder leer las tablas de abajo: **V1** invariantes, **V2** valor
publicado, **V3** implementación independiente, **V4** snapshot de la salida
propia — y **V4 no es validación**.

---

## Estado, de un vistazo

| Etapa | Qué | Estado |
|---|---|---|
| 0 | tooling, CI | ✅ |
| 1 | `core/` | ✅ |
| 2.1 | `orbits/` | ✅ |
| 2.2 | `channel/` | ✅ (9 módulos) |
| 2.3 | `qkd/` | ✅ (un protocolo, por decisión) |
| 2.4 | `kernels/` | ⬜ **no justificada por ninguna medida de hoy** → [0026](../docs/adr/0026-the-language-ladder.md) |
| 3 | `system/` | ✅ |
| 4 | `scenario/` | ✅ |
| 5 | `engine/` | ✅ |
| 6 | `io/` | ✅ |
| 7 | `cli/` + `viz/` | ✅ |
| 8 | `validation/` | ✅ (35 casos de ocho fuentes; `docs/validation.md` commiteado) |
| 9–11 | `api/`, `web/`, `deploy/` | ⬜ distribución, no ciencia → [0027](../docs/adr/0027-four-levels-of-distribution.md) |

**Hito A (fin de etapa 5):** simulador completo en Python, sin red y sin web.
**Alcanzado.** **Hito B (fin de etapa 8):** resultados validados contra
literatura y reproducibles por terceros — aquí es donde el proyecto es
publicable. **Alcanzado el 2026-09-19**, y conviene leer lo que significa: no es
«los números están bien», es que **cada número publicable tiene una fila que
dice contra qué se comparó, con qué tolerancia y de dónde sale esa tolerancia**,
y que ocho de esas filas dicen que no cuadra. Un hito de credibilidad se alcanza
publicando los desacuerdos, no eliminándolos.

---

## Etapa 0 — Cimientos ✅

`pyproject.toml` (src-layout, deps mínimas, grupos `dev`/`viz`/`export`/`accel`/`web`),
`.python-version`, `uv.lock`, config de `ruff` y `mypy`, `tests/conftest.py`,
`.github/workflows/ci.yml`, `README.md`.

## Etapa 1 — `core/`: el vocabulario común ✅

| Fichero | Qué | ADR |
|---|---|---|
| `core/constants.py` | constantes físicas y de la Tierra, con fuente | [0001](../docs/adr/0001-unit-conventions.md) |
| `core/units.py` | convención de unidades y sufijos (`_km`, `_db`, `_rad`) | [0001](../docs/adr/0001-unit-conventions.md) |
| `core/types.py` | `TimeGrid`, `TimeSeries`, contenedores congelados | [0001](../docs/adr/0001-unit-conventions.md) |
| `core/errors.py` | jerarquía de excepciones + `DegradationLog` | — |
| `core/rng.py` | un `np.random.Generator` inyectable con semilla registrable | — |
| `core/logging.py` | logging estructurado | — |

---

## Etapa 2 — Física pura, módulo a módulo

**Todo vectorizado sobre el eje temporal desde el primer archivo.** Funciones
puras: sin estado, sin I/O, sin red. Cada módulo se cierra con su verificación
antes de pasar al siguiente.

### 2.1 `orbits/` — geometría del problema ✅

`frames.py` va **primero**: no depende de Kepler y todo lo demás depende de él.

| Fichero | Qué | ADR |
|---|---|---|
| ✅ `frames.py` | TEME ↔ ITRF ↔ geodésico, ENU, GMST, calendario ↔ JD | [0002](../docs/adr/0002-frames-and-time-scales.md) |
| ✅ `kepler.py` | anomalías, elementos ↔ estado, casos degenerados | [0003](../docs/adr/0003-orbital-elements.md) |
| ✅ `perturbations.py` | fuerza zonal J2/J3/J4 exacta, integrador numérico, tasas seculares de **primer orden en J2** | [0004](../docs/adr/0004-zonal-perturbations.md) |
| ✅ `propagator.py` | `propagate(elementos, TimeGrid, method=…)` → `Trajectory` `(S, n, 3)`. Enum **incompleto a propósito** | [0005](../docs/adr/0005-propagation.md) |
| ✅ *(transversal)* | `ElementType` osculador/medio dentro de `ClassicalElements` | [0006](../docs/adr/0006-osculating-vs-mean-elements.md) |
| ✅ `tle.py` | parseo TLE + SGP4 envolviendo `sgp4`; **no** entra por `propagate()` | [0007](../docs/adr/0007-tle-and-sgp4-propagation.md) |
| ✅ `geometry.py` | elevación, azimut, slant range, range rate, **point-ahead** | [0019](../docs/adr/0019-acquisition-in-the-result.md), [0020](../docs/adr/0020-declared-doppler-capture-range.md) |
| ✅ `constellations.py` | Walker-Delta, SSO, traza repetida. **Escrito y aparcado** (alcance: un satélite) | [0008](../docs/adr/0008-constellation-design.md) |

### 2.2 `channel/` — el canal óptico ✅

Andrews & Phillips **no se cita** porque no se pudo abrir. Fuentes primarias:
ITU-R P.1621-2, P.1622, P.1814, P.1817-1, Ntanos et al. 2021, Kim et al. 2001.
**Veintitrés huecos declarados** en vez de rellenados con la cita más plausible →
[ADR 0009](../docs/adr/0009-citation-policy.md).

| Fichero | Qué | ADR |
|---|---|---|
| ✅ `atmosphere.py` | perfil `C_n²` (HV 5/7), viento de Bufton, 139 capas, refracción | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `turbulence.py` | varianza de log-irradiancia, promediado de apertura, `r_0`, ángulo isoplanático, régimen saturado | [0022](../docs/adr/0022-the-strong-regime.md) |
| ✅ `beam.py` | divergencia, acoplamiento geométrico, vaivén (solo subida) | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `pointing.py` | desvanecimiento por jitter como **distribución**, no como número | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `background.py` | radiancia de cielo, fondo solar/lunar, gating temporal | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `detector.py` | eficiencia, cuentas oscuras, afterpulsing, tiempo muerto | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `link_budget.py` | **ensambla** los anteriores; cuantil conjunto exacto sin Monte Carlo | [0009](../docs/adr/0009-citation-policy.md) |
| ✅ `horizontal.py` | camino horizontal: `C_n²` constante, sin elevación, onda declarada | [0021](../docs/adr/0021-horizontal-path.md), [0024](../docs/adr/0024-the-horizontal-scenario.md), [0025](../docs/adr/0025-two-terminals-one-way.md) |
| ✅ `extinction.py` | visibilidad → atenuación específica → transmitancia cenital | [0023](../docs/adr/0023-traceable-extinction.md) |

**Fuera del alcance, declarado:** Rytov en régimen fuerte por camino esférico
completo y frecuencia de Greenwood, pendientes con su fuente en vez de
implementadas a medias.

### 2.3 `qkd/` — de canal a clave ✅

| Fichero | Qué | ADR |
|---|---|---|
| ✅ `base.py` | `LinkConditions` → `KeyRate`, `QkdProtocol`, `ProtocolRegistry`. **Sin física dentro** | — |
| ✅ `bb84.py` | BB84 con pulsos coherentes débiles y decoy vacío+débil (Ma et al. 2005) | [0010](../docs/adr/0010-decoy-and-finite-key.md) |
| ✅ `finite_key.py` | cota componible de **Lim et al. 2014**, no la de Tomamichel | [0010](../docs/adr/0010-decoy-and-finite-key.md) |

**La etapa se cierra con un solo protocolo — decisión del 2026-09-12.** E91,
CV-QKD, MDI-QKD y TF-QKD **se retiran del plan**: no son el protocolo de este
trabajo, y una línea de roadmap que nadie va a escribir hace parecer incompleto
algo que está terminado. Volver cuesta **un fichero** —una clase que implemente
`_key_rate` y un nombre registrado—, porque lo único que cruza la frontera es
`LinkConditions` → `KeyRate`. Los controles negativos de `tests/qkd/test_base.py`
(ocho deletreos que el registro rechaza) se quedan donde están.

### 2.4 `kernels/` — ⬜ **no justificada por ninguna medida de hoy**

`base.py` (interfaz), `numpy_backend.py` (referencia, siempre existe),
`numba_backend.py` (con golden test contra la de referencia). La escalera de
lenguajes y las tres condiciones de entrada están en el
[ADR 0026](../docs/adr/0026-the-language-ladder.md).

**Estado reclasificado el 2026-09-19.** Esta etapa se citaba como justificada por
los 55.6 s que tardan 60 satélites un día a 1 s. Esa cifra es correcta y está
**atribuida al mecanismo equivocado**: 927 ms por satélite con S = 60 y 934 ms
con S = 1 —menos del 1 % de dispersión— son la firma de un bucle estrictamente
en serie (`orbits/propagator.py:535`), no de aritmética lenta. Para justificar la
2.4 haría falta **volver a medir después de arreglar el bucle**; hasta entonces
cualquier perfil del caso grande mide el serialismo.

Y el arreglo es **paralelizar, no vectorizar**: cada satélite lleva su propia
secuencia de pasos adaptativos dentro de DOP853, y vectorizar entre satélites
exigiría renunciar al paso adaptativo por satélite, que es lo que hace fiable al
integrador cerca de perigeo. La distinción, con lo que cuesta cada una, está en
el ADR 0026 («El bucle no se puede vectorizar; lo que admite es paralelizar»), y
el trabajo pertenece a `engine/parallel.py`, etapa 11.

---

## Etapa 3 — `system/`: de instantes a métricas de sistema ✅

| Fichero | Qué | ADR |
|---|---|---|
| ✅ `passes.py` | detección y segmentación contra una máscara **sin defecto** | [0011](../docs/adr/0011-the-block-is-the-pass.md) |
| ✅ `key_volume.py` | la integral sobre el pase → clave por pase y por día. **El bloque es el pase** | [0011](../docs/adr/0011-the-block-is-the-pass.md) |
| ✅ `monte_carlo.py` | ensembles de fading → P5/P50/P95 y outage | [0012](../docs/adr/0012-correlated-fading-and-monte-carlo.md) |
| ✅ `correlated_fading.py` | el desvanecimiento como proceso temporalmente correlacionado | [0012](../docs/adr/0012-correlated-fading-and-monte-carlo.md) |
| ✅ `pcflos.py` | probabilidad de línea de vista libre de nubes | [0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md) |
| ✅ `multi_ogs.py` | dos políticas porque son dos sistemas: `SUM` y `BEST` | [0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md) |
| ✅ `relay.py` | nodo de confianza *store-and-forward* | [0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md) |

---

## Etapa 4 — `scenario/`: el escenario como dato ✅

**El fichero más importante del proyecto** — define el contrato. Se hizo aquí, con
la física entera debajo, y por eso el esquema expresa **cada** parámetro que la
física acepta. ADR de la etapa:
[0014](../docs/adr/0014-scenario-contract-and-provenance.md).

| Fichero | Qué |
|---|---|
| ✅ `models.py` | esquema Pydantic v2 (`extra="forbid"`, `frozen`, `allow_inf_nan=False`); unidades del usuario en el nombre del campo |
| ✅ `defaults.py` | `reference_castelldefels()` y `ntanos_2021(0.75 \| 1.3 \| 2.3)` |
| ✅ `io.py` | YAML/JSON por `safe_load`/`safe_dump`; todo fallo es `ScenarioError` con la ruta del campo |
| ✅ `hash.py` | JSON canónico + SHA-256, con un digest clavado como guardia del contrato |
| ✅ `result.py` | `SimulationResult`, `HorizontalResult`, `Provenance.collect` |
| ✅ `scenarios/*.yaml` | **siete** ficheros comentados y comprobados iguales a sus constructores |
| ✅ la unión `link` | `downlink \| horizontal`, validada por `TypeAdapter` | [0024](../docs/adr/0024-the-horizontal-scenario.md) |

---

## Etapa 5 — `engine/`: el orquestador ✅

Sin dependencias web. Decisiones en el
[ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md): **el
motor no calcula nada que no calcularía una persona llamando a las funciones a
mano**, y eso lo aserta `tests/e2e/test_reference_scenarios.py` por igualdad
**exacta** de coma flotante, etapa por etapa.

| Fichero | Qué |
|---|---|
| ✅ `pipeline.py` | escenario → órbita → geometría → canal → QKD → sistema → resultado |
| ✅ `cache.py` | caché de resultados por hash de escenario |
| ✅ `parallel.py` | paralelismo por pases / estaciones / realizaciones MC |
| ✅ `sweep.py` | barridos como ciudadano de primera (las figuras del paper *son* barridos) |
| ✅ `profiling.py` | tiempos por etapa dentro del propio resultado |
| ✅ `horizontal.py` | `run()` despacha sobre el tag `link` y devuelve un `HorizontalResult` |

---

## Etapa 6 — `io/`: el mundo exterior, aislado ✅

Tarde a propósito: la física no debe depender de la red. Ningún módulo de `core`,
`orbits`, `channel`, `qkd`, `system` o `engine` importa `quoss.io`, y
`tests/io/test_cache.py::TestTheSuiteIsOffline` rompe `socket.socket` y ejecuta
todos los caminos con `fetch` falsos. Decisiones en el
[ADR 0015](../docs/adr/0015-external-data-isolation-and-snapshots.md).

| Fichero | Qué |
|---|---|
| ✅ `cache.py` | caché HTTP en disco, content-addressed, TTL obligatorio, reloj inyectado |
| ✅ `celestrak.py` | un TLE del API GP, validado por `parse_tle` antes de existir |
| ✅ `openmeteo.py` | cobertura horaria de nubes del archivo histórico (familia ERA5) |
| ✅ `snapshots.py` | `quoss/data/snapshots/<kind>/<name>.json` con manifiesto y hash comprobado |
| ✅ `export.py` | `manifest.json`, `passes.csv`, `daily.csv`, `series_*.csv`, `arrays.npz`, `result.json` |
| ✅ `stations.py` + `quoss/data/ogs.yaml` | cuatro estaciones con `source` y `coordinates_precision` obligatorios |
| ✅ `quoss/data/` | **datos de paquete**, no ficheros del checkout: el wheel los lleva y `quoss.data.DATA_ROOT` los encuentra igual instalado que en el árbol. Asertado desde una instalación por `tests/packaging/test_wheel.py` |

---

## Etapa 7 — `cli/` + `viz/`: ya es un simulador usable ✅

Con esto ya puedes escribir el paper. **La web todavía no existe, y no pasa nada.**

| Fichero | Qué | ADR |
|---|---|---|
| ✅ `cli/main.py` | entrada, subcomandos, `argparse`. Un `QuossError` sale como mensaje, no como traceback | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |
| ✅ `cli/run.py` | `quoss run <escenario.yaml> --out <dir>`, despachando sobre el tag `link` sin opción que lo repita | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |
| ✅ `cli/sweep.py` | `quoss sweep <escenario.yaml> <spec.yaml>`; el spec es un **fichero** | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |
| ✅ `cli/validate.py` | `quoss validate` → corre `quoss.validation`; un desacuerdo publicado sale 0 | [0018](../docs/adr/0018-validation-is-a-table-not-a-badge.md) |
| ✅ `cli/report.py` | los `warnings[]` **enteros**, y el estado de salida sobre el `DEGRADED` que el escenario no declara | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |
| ✅ `viz/style.py` | style sheet de publicación | [0017](../docs/adr/0017-publication-figures.md) |
| ✅ `viz/plots.py` | SKR(t) con bandas, key volume, cobertura, barridos, clave horizontal contra distancia | [0017](../docs/adr/0017-publication-figures.md) |
| ✅ `viz/figures.py` | figuras del paper, cada una desde un escenario versionado | [0017](../docs/adr/0017-publication-figures.md) |
| ✅ `io/export.py`, forma `horizontal` | `budget.csv` + `session.csv`, sin `arrays.npz`, con la forma nombrada en `manifest.json` | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |
| ✅ `scenarios/sweeps/*.yaml` | specs de barrido versionados, porque una figura se reproduce desde algo commiteado | [0028](../docs/adr/0028-the-cli-computes-nothing.md) |

**Los dos defectos que esta etapa cerró**, los dos abiertos desde antes de
existir la etapa: `[project.scripts]` apuntaba a `quoss.cli.main:main` desde la
etapa 0 y ese módulo no existía, así que **instalar el paquete dejaba un comando
roto** —hay ahora un test que lo ejecuta como subproceso, porque un `import` no
ve un entry point equivocado—; y `export_result` sobre un resultado horizontal
levantaba `AttributeError` ([INCONSISTENCIAS #15](INCONSISTENCIAS.md), cerrada).

---

## Etapa 8 — `validation/`: credibilidad ✅

Barato y el mayor multiplicador de confianza que hay. Se ejecuta en CI. ADR de la
etapa: el [**0018**](../docs/adr/0018-validation-is-a-table-not-a-badge.md).

| Fichero | Qué | Estado |
|---|---|---|
| `base.py` | los cuatro estados, y la regla que **deriva** el estado en vez de aceptarlo escrito a mano | ✅ |
| `channel.py` | ITU-R P.1621-2, P.1622, y Farid & Hranilovic | ✅ |
| `ntanos2021.py` | la fuente del enlace de referencia entero, más Ma et al. 2005 y Lim et al. 2014 | ✅ |
| `satquma.py` | dos identidades reproducidas y **dos huecos declarados** | ✅ |
| `micius.py` | datos de misión real | ✅ |
| `tests/validation/` | `cases.py`, `test_base.py`, `test_docs.py`, `test_main.py`, `test_micius.py`, `test_ntanos2021.py`, `test_satquma.py` | ✅ |
| `docs/validation.md` | autogenerado, **commiteado**, y con un test que lo compara byte a byte | ✅ |

**Estado al 2026-09-19:** **35 casos de ocho fuentes** — 17 reproducidos, 3
compatibles, **8 no reproducidos** y 7 huecos declarados.
`tests/validation/` cubre el paquete al **100 %** de líneas y ramas.

Siete de los ocho desacuerdos son de Ntanos et al. 2021, y no es un juicio sobre
el paper: es la fuente con los parámetros mejor declarados que tiene el proyecto,
así que es de la que más consecuencias impresas se pueden comprobar. Uno se queda
**sin fila y con su razón medida** —`lim2014.block-1e4-reach`, en
`PENDING_DISAGREEMENTS`—: reproducirlo exige la optimización de cinco parámetros
de Lim et al., que vive junto al test que la mide, y subirla a `src/` dejaría dos
implementaciones de una misma sección publicada.

---

## Etapas 9–11 — distribución, no ciencia ⬜

**No se tocan antes de tiempo: hacerlas pronto es exactamente lo que acopló
SimulCTTC.** Los cuatro niveles de entrega —CLI, `serve`, Docker, cloud—, el
orden en que se construyen y por qué la web es un **cliente** y no el simulador
están en el [ADR 0027](../docs/adr/0027-four-levels-of-distribution.md).

- **9. `api/`** — routers finos que traducen HTTP ↔ engine y nada más:
  `settings.py`, `deps.py`, `app.py`, `routes/{simulate,jobs,catalog}.py`,
  `cli/serve.py`.
- **10. `web/`** — TypeScript + Vite + Svelte, deps vendorizadas. El frontend
  **no calcula física**: pinta lo que devuelve el motor, `warnings[]` incluidos.
- **11. `deploy/` + rendimiento** — `Dockerfile` que funciona **offline**,
  `compose.yaml`, `benchmarks/` como puerta de regresión en CI, y `kernels/`
  solo si el profiler lo pide.

---

## Trabajo abierto que no es una etapa

> Heredado de `LAST_CHANGES.md` §13 («Pendiente de decidir» y «Deuda pequeña») al
> archivarlo. Las filas que ya estaban tachadas allí no se copian; estas son las
> que seguían vivas, **comprobadas una a una contra el árbol de hoy**.

| Dónde | Qué | Comprobado |
|---|---|---|
| `orbits/` | **Transformación osculador↔medio (Brouwer-Lyddane).** Es lo único que queda vivo de la bandera del ADR 0006, y desbloquea a la vez el modo analítico de `propagate` y los términos seculares de segundo orden. Pendiente: elegir alcance (solo período corto, o corto + largo) y oráculo | no existe |
| etapa 8 | **Transcribir Vallado §9.6** (tasas seculares) como V2, comprobando primero si el libro imprime elementos medios u osculadores | sin transcribir |
| ~~etapa 8~~ | ~~Reactivar `warn_unused_configs = true` en mypy.~~ **Cerrada el 2026-09-19.** Activada, nombró **tres** secciones muertas (`quoss.kernels.*`, `numba.*`, `pyarrow.*`) y las tres están fuera con su razón. La bandera sola no bastaba —mypy la emite como `note:` y sale 0—, así que la mitad que falla es `tests/unit/test_project_config.py`. §46 | cerrada |
| etapa 8 | ¿Reducción completa GCRF ↔ ITRF? El enum deja la puerta abierta; hoy no cambia ningún número publicable | no existe |
| etapa 11 | **Paralelismo del bucle sobre satélites.** `ZONAL_NUMERIC` integra las S órbitas en serie (`propagator.py:535`): 927 ms/satélite con S = 60 y 934 con S = 1. **Paralelizar, no vectorizar** — cada satélite lleva su propia secuencia de pasos adaptativos en DOP853 ([ADR 0026](../docs/adr/0026-the-language-ladder.md)). Pertenece a `engine/parallel.py`, no a la física, y es lo que hay que hacer **antes** de volver a medir la etapa 2.4 | en serie |
| etapa 11 | `uv sync --all-extras` en CI arrastra `numba` **y `fastapi`** en los cinco jobs. Comprobado el 2026-09-19: ninguno de los dos se importa en nada que la suite toque, así que los extras `accel` y `web` son peso muerto. Falta la medida del tiempo de CI que cuestan, que es lo que decide dónde se quitan | `ci.yml`, tres `uv sync --all-extras` |
| etapa 11 | El suelo `numpy>=1.26` no está testeado, y **no es alcanzable con el `scipy` del lock**: medido el 2026-09-19, `--with numpy==1.26.4` revienta en `scipy/sparse/_sputils.py` (`np.long`, retirado en numpy 2) porque el scipy resuelto es 1.18.0. Un entorno de mínimos de verdad —`numpy==1.26.0` + `scipy==1.11.0` sobre Python 3.11— sí se construye, y ahí el primer fallo **no es de numpy**: es `matplotlib==3.8.0` contra el `pyparsing` de hoy, con `filterwarnings = ["error"]` convirtiéndolo en error. El job de mínimos tendrá que fijar también el suelo del extra `viz` | sin job de mínimos; medido en §46 |
| cuando duela | **Coste de la suite.** Casi todo integraciones DOP853 de `test_perturbations.py`. Recortar revoluciones antes que tolerancias | ver §41 |
| si entra `sgp4` en más sitios | `filterwarnings = ["error"]` necesitará excepciones **por warning concreto**, nunca una categoría entera | — |
| si aparece un tercero | `frames._broadcast_against` y `kepler._broadcast_to_common` siguen duplicados a medias. **Difieren** en forma y en lo que aconsejan sus mensajes, y por eso no se unificaron | documentado en `orbits/_validation.py` |
| si entra un optimizador | **Elementos equinocciales** como representación primaria. Hoy el pliegue resuelve el problema real sin mantener una segunda representación | [ADR 0003](../docs/adr/0003-orbital-elements.md) |
| no corregido, documentado | La ecuación de Kepler cerca de `e = 1`: la precisión en `E` se degrada como `1/(1−e)`. No hay escenario QuOSS que llegue ahí | `orbits/kepler.py` |

---

## Numeración de ADRs

Un ADR por decisión no obvia, numerado al escribirse y **nunca renumerado**. A
2026-09-19 hay **veintiocho escritos** (0001–0028) y **ninguno reservado**.

| Nº | Etapa | Qué gobierna |
|---|---|---|
| 0001–0016 | 0–5 | escritos |
| **0017** | 7 (`viz/`) | Las **figuras de publicación**: los dos paneles, la banda plana-a-esférica que no es una barra de error, y la región de Rayleigh que se estrecha por la razón equivocada |
| **0018** | 8 (`validation/`) | **«Validado» es una tabla que se recalcula**, no una insignia: el estado derivado, los cuatro valores, y por qué un desacuerdo publicado sale 0 |
| 0019–0025 | 3, 5, 2.2, 4 | escritos |
| **0026** | 2.4 (`kernels/`) | La **escalera de lenguajes**, que gobierna una etapa que aún no existe |
| **0027** | 7, 9–11 (`cli/`, `api/`, `web/`, `deploy/`) | Los **cuatro niveles de distribución** |
| **0028** | 7 (`cli/`) + 6 (`io/export.py`) | **La CLI no calcula nada**, y un resultado horizontal tiene su propia forma de directorio |

**Los 0017 y 0018 estuvieron reservados cinco días**, del 2026-09-14 al
2026-09-19, porque `viz/plots.py` y `validation/__init__.py` ya los citaban por
su nombre exacto. Quien escribió las etapas usó **esos** números y no el
siguiente libre, que es de lo que sirve reservar. El 0028 es el primer número
nuevo desde entonces.

Y el 0026 y el 0027 siguen siendo el caso que conviene tener presente: **un ADR
registra una decisión, no una implementación**, así que una etapa sin escribir no
es objeción a que su decisión tenga dueño.

---

## Orden abreviado

```
0. tooling ── 1. core ── 2. física (orbits → channel → qkd) ── 3. system
                                                                  │
        7. cli+viz ── 6. io ── 5. engine ── 4. scenario ──────────┘
             │
             └── 8. validation ── 9. api ── 10. web ── 11. deploy + perf
```

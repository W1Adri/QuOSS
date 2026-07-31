# QuOSS — Roadmap de implementación

> Orden lógico de construcción, de dentro hacia fuera. Very high level: cada etapa
> lista los archivos en el orden en que conviene escribirlos, no su contenido.
> Ver `GUIA_REIMPLEMENTACION.md` para el porqué de la arquitectura.

**Regla de oro del orden:** nunca escribas un archivo que importe algo que aún no
existe. El grafo de dependencias es `core ← física ← system ← engine ← {cli, api, viz}`,
y este roadmap lo recorre en ese sentido.

**Regla de oro de la migración:** SimulCTTC es el **oráculo**. Cada módulo de física
portado se cierra con un golden test que compara su salida contra la del código viejo
en un escenario fijo. Si no coincide (dentro de tolerancia), uno de los dos está mal y
hay que averiguar cuál *antes* de seguir.

---

## Etapa 0 — Cimientos (medio día, se hace una vez)

Sin esto no se puede ni importar el paquete. Nada de física todavía.

1. `pyproject.toml` — metadatos, `src-layout`, deps mínimas (numpy, scipy, pydantic) y grupos `dev`/`viz`/`accel`/`web`
2. `.python-version`, `uv.lock` (`uv sync`)
3. Config de `ruff` + `mypy` (dentro de `pyproject.toml`)
4. `src/quoss/__init__.py` — solo `__version__`
5. `tests/conftest.py` + un test trivial que importe el paquete → CI verde desde el minuto uno
6. `.github/workflows/ci.yml` — ruff + mypy + pytest
7. `.gitignore`, `README.md` (una pantalla: qué es, cómo instalar, cómo correr)

**Hecho cuando:** `uv run pytest` pasa y CI está verde.

---

## Etapa 1 — `core/`: el vocabulario común

Todo lo demás importa de aquí, así que va primero. Sin física.

1. `core/constants.py` — constantes físicas y de la Tierra, con fuente en el docstring
2. `core/units.py` — convención de unidades y sufijos de nombres (`_km`, `_m`, `_db`, `_deg`, `_rad`), y helpers de conversión
3. `core/types.py` — alias de tipos y estructuras compartidas (vector de tiempo, serie temporal)
4. `core/errors.py` — jerarquía de excepciones + el mecanismo de **degradación explícita** (`Warning`/`Degraded` que viaja en el resultado, nunca un `except` silencioso)
5. `core/rng.py` — un único `np.random.Generator` inyectable, con semilla registrable
6. `core/logging.py` — logging estructurado

**Decisión a tomar aquí:** la convención de unidades. Es la que más fricción ahorra
o cuesta durante todo el proyecto. Elígela y no la cambies.

---

## Etapa 2 — Física pura, módulo a módulo

El corazón. **Todo vectorizado sobre el eje temporal desde el primer archivo** — no
"lo optimizo después": la firma escalar contamina a todos los llamantes. Cada módulo:
funciones puras → sin estado, sin I/O, sin red. Cada uno se cierra con sus tests
(unitarios + invariantes + golden contra SimulCTTC) antes de pasar al siguiente.

### 2.1 `orbits/` — geometría del problema
1. `orbits/kepler.py` — Kepler, anomalías, posición/velocidad, elementos ↔ estado
2. `orbits/perturbations.py` — J2/J3/J4, tasas seculares
3. `orbits/frames.py` — ECI ↔ ECEF ↔ geodésico, GMST, tiempo juliano
4. `orbits/propagator.py` — propagación vectorizada: devuelve arrays de estado
5. `orbits/tle.py` — parseo TLE + SGP4 (usar `sgp4`, no reimplementar)
6. `orbits/constellations.py` — Walker-Delta, SSO, traza repetida
7. `orbits/geometry.py` — elevación/azimut/slant range/Doppler estación↔satélite

### 2.2 `channel/` — el canal óptico
1. `channel/atmosphere.py` — perfiles Cn² (HV5/7, Bufton, HV modificado), airmass
2. `channel/turbulence.py` — r₀, Rytov, índice de escintilación (débil y fuerte), frecuencia de Greenwood, ángulo isoplanático
3. `channel/beam.py` — divergencia, acoplamiento geométrico/difracción, beam wander
4. `channel/pointing.py` — pérdida de apuntado, fading PAT
5. `channel/background.py` — radiancia de cielo, fondo solar/lunar, gating temporal
6. `channel/detector.py` — eficiencia, dark counts, dead time, afterpulsing
7. `channel/link_budget.py` — **ensambla** los anteriores en pérdida total y ruido total

### 2.3 `qkd/` — de canal a clave
1. `qkd/base.py` — interfaz común de protocolo (entra transmitancia+ruido, sale tasa+QBER) y registro de protocolos
2. `qkd/bb84.py` — BB84 WCP + decoy/GLLP
3. `qkd/finite_key.py` — finite-key componible (Tomamichel). **Por defecto activo**
4. `qkd/entanglement.py` — E91
5. `qkd/cv.py` — CV-QKD
6. `qkd/mdi_tf.py` — MDI-QKD y TF-QKD con relay no confiable

### 2.4 `kernels/` — solo cuando el profiler lo pida
1. `kernels/base.py` — interfaz del backend numérico
2. `kernels/numpy_backend.py` — **implementación de referencia** (siempre existe)
3. `kernels/numba_backend.py` — más adelante, con golden test contra la de referencia

**Hecho cuando:** se puede calcular una curva SKR(t) llamando funciones a mano desde
un notebook, y los golden tests contra SimulCTTC coinciden.

---

## Etapa 3 — `system/`: de instantes a métricas de sistema

Aquí aparecen las cantidades que van al paper.

1. `system/passes.py` — detección y segmentación de passes
2. `system/key_volume.py` — integración de la tasa sobre el pase → clave por pase / día
3. `system/monte_carlo.py` — ensembles de fading → **P5/P50/P95 y outage**. Estructural, no un extra
4. `system/correlated_fading.py` — proceso temporalmente correlacionado (AR(1)) — el punto de novedad
5. `system/pcflos.py` — probabilidad de línea de vista libre de nubes
6. `system/multi_ogs.py` — selección/agregación entre estaciones
7. `system/relay.py` — trusted-node store-and-forward, ISL

---

## Etapa 4 — `scenario/`: el escenario como dato

Se podría hacer antes, pero es más honesto aquí: ya sabes exactamente qué parámetros
existen. **Este es el archivo más importante del proyecto** — define el contrato.

1. `scenario/models.py` — esquema Pydantic completo (órbita, óptica, estación, atmósfera, protocolo, tiempo, opciones)
2. `scenario/defaults.py` — presets sensatos
3. `scenario/io.py` — carga/volcado YAML/JSON + validación con mensajes útiles
4. `scenario/hash.py` — hash canónico del escenario (clave de caché y de procedencia)
5. `scenario/result.py` — **esquema del resultado**: series, resumen, `warnings[]`, procedencia (hash + versión de código + versión de datos + semilla)
6. `scenarios/*.yaml` — 3–4 escenarios de referencia versionados (uno reproduce Ntanos 2021)

---

## Etapa 5 — `engine/`: el orquestador

Lo que hoy está enterrado en un handler HTTP. Sin dependencias web.

1. `engine/pipeline.py` — escenario → órbita → geometría → canal → QKD → sistema → resultado
2. `engine/cache.py` — caché de resultados por hash de escenario
3. `engine/parallel.py` — paralelismo por passes / estaciones / realizaciones MC
4. `engine/sweep.py` — barridos de parámetros como ciudadano de primera (las figuras del paper *son* barridos)
5. `engine/profiling.py` — tiempos por etapa dentro del propio resultado

**Hecho cuando:** `run(scenario) → result` funciona en una línea de Python y un
escenario de referencia da los mismos números que SimulCTTC.

---

## Etapa 6 — `io/`: el mundo exterior, aislado

Tarde a propósito: la física no debe depender de la red. Hasta aquí, todo con datos
sintéticos o de `data/`.

1. `io/cache.py` — caché HTTP en disco (todo cliente externo pasa por aquí)
2. `io/celestrak.py` — TLE
3. `io/openmeteo.py` — meteo / nubes / ERA5
4. `io/snapshots.py` — **snapshots offline versionados** → la demo no depende de que haya wifi
5. `io/export.py` — export de resultados (Parquet/NetCDF + manifest de procedencia), CSV para colaboradores
6. `data/ogs.yaml` — estaciones ópticas

---

## Etapa 7 — `cli/` + `viz/`: ya es un simulador usable

Con esto ya puedes escribir el paper. **La web todavía no existe, y no pasa nada.**

1. `cli/main.py` — entrada, subcomandos
2. `cli/run.py` — `quoss run scenario.yaml`
3. `cli/sweep.py` — `quoss sweep`
4. `viz/style.py` — style sheet de publicación (esto sustituye la ventaja de MATLAB)
5. `viz/plots.py` — figuras estándar: SKR(t) con bandas, key volume, mapas de cobertura, barridos
6. `viz/figures.py` — figuras del paper, cada una desde un escenario versionado
7. `cli/validate.py` — `quoss validate` → corre la suite de validación

---

## Etapa 8 — `validation/`: credibilidad

Barato y es el mayor multiplicador de confianza que hay. Se ejecuta en CI.

1. `validation/ntanos2021.py` — reproducir los números publicados
2. `validation/satquma.py` — comparación con el toolkit de referencia
3. `validation/micius.py` — datos de misión real
4. `docs/validation.md` — autogenerado: qué se reproduce y con qué desviación

---

## Etapa 9 — `api/`: la web, como cliente

Routers **finos**: traducen HTTP ↔ engine y nada más. Cero física, cero orquestación.

1. `api/settings.py` — `pydantic-settings`
2. `api/deps.py` — inyección explícita de dependencias (fuera globals mutables)
3. `api/app.py` — factoría de la app
4. `api/routes/simulate.py` — POST de un escenario → resultado (o job)
5. `api/routes/jobs.py` — cola de jobs (nunca bloquear el event loop)
6. `api/routes/catalog.py` — estaciones, TLE, presets
7. `cli/serve.py` — `quoss serve`

---

## Etapa 10 — `web/`: frontend

TypeScript + Vite + Svelte, deps **vendorizadas** (sin CDN). El frontend **no calcula
física**: pinta lo que devuelve el motor.

1. Scaffold Vite + TS, cliente de API tipado generado del esquema OpenAPI
2. Editor de escenario (el formulario es el esquema Pydantic — genera lo que puedas)
3. Gráficas interactivas (Plotly/uPlot)
4. Mapa 2D y globo 3D (Cesium/three)
5. Panel de resultados con `warnings[]` visibles

---

## Etapa 11 — `deploy/` + rendimiento

1. `deploy/Dockerfile` — imagen que funciona **offline**
2. `deploy/compose.yaml`
3. `benchmarks/` — puerta de regresión de rendimiento en CI
4. `kernels/numba_backend.py` / `kernels/rust/` — **solo ahora**, y solo lo que diga el profiler
5. `docs/adr/*.md` — decisiones no obvias, a medida que se toman

---

## Orden abreviado

```
0. tooling ── 1. core ── 2. física (orbits → channel → qkd) ── 3. system
                                                                  │
        7. cli+viz ── 6. io ── 5. engine ── 4. scenario ──────────┘
             │
             └── 8. validation ── 9. api ── 10. web ── 11. deploy + perf
```

**Dos hitos que importan:**
- **Hito A (fin de etapa 5):** simulador completo en Python, sin red y sin web. Ya
  produce resultados fiables. Aquí es donde el proyecto empieza a valer.
- **Hito B (fin de etapa 8):** resultados validados contra literatura y reproducibles
  por terceros. Aquí es donde el proyecto es publicable.

Las etapas 9–11 son distribución y comodidad. Importantes, pero no bloquean la ciencia
— y hacerlas antes de tiempo es exactamente lo que acopló SimulCTTC.

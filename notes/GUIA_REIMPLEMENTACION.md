# QuOSS — Guía de reimplementación (v3)

**QuOSS** — *Quantum Optical Satellite Simulator*. Paquete: `quoss`. CLI: `quoss`.

> Documento **high level** y vivo. Fija criterios y dirección, no detalles.
> Todo lo concreto se decidirá al desarrollar cada módulo.
> Fecha: 2026-07-31. Base: análisis de `../SimulCTTC`.

---

## 0. Punto de partida: qué hay hoy y qué duele

**Lo bueno de SimulCTTC (conservar):** la física. Está trabajada, referenciada
(`.agents/FORMULAS.md`) y cubre la cadena completa: órbitas (Kepler + J2/J3/J4,
Walker, SSO, TLE) → canal atmosférico (Cn², Rytov, beam wander, PAT) → link budget
(difracción, Beer-Lambert, fondo solar/lunar, gating, detector) → protocolos (BB84,
decoy-GLLP, E91, CV, MDI, TF) → métricas de sistema (key volume, relay, pCFLOS,
multi-OGS). También la separación `routers/ → services/ → physics/`.

**Lo que hay que cambiar (el diagnóstico real):**

| Área | Estado actual | Coste |
|---|---|---|
| Núcleo numérico | Física **escalar** con `math` + bucles Python por muestra; `numpy` solo en 5 de 33 módulos | `samples ≤ 900` por diseño; Monte Carlo y barridos inviables |
| Orquestación | Las ~486 líneas de pipeline viven **dentro de un handler HTTP** (`routers/solver.py`) | No hay simulador sin servidor: ni CLI, ni notebook, ni test end-to-end limpio |
| Reproducibilidad | El "escenario" solo existe como request HTTP; sin lock de dependencias (`>=` en `requirements.txt`); sin semillas registradas | Un resultado del paper no se puede volver a generar con garantías |
| Frontend | ~16k líneas de JS sin tipos, `main.js` de 3.3k, `index.html` de 1.7k, CSS de 2.3k; **deps por CDN** (Leaflet, Plotly, satellite.js, three) | Demo offline frágil; física duplicada en JS (`propagateWorker.js`) que puede divergir del backend |
| Tests | `test_all.py`: **118 KB, un archivo, framework a mano**, 203 tests, sin CI | No hay red de seguridad real ni detección de regresión numérica |
| Estado/DI | Singletons vía globals mutables (`set_store()`, `set_database()`) | Difícil de testear y de paralelizar |
| Errores | `except Exception` que degradan la física en silencio (p.ej. Cn² → sin escintilación) | Números plausibles pero silenciosamente incorrectos: lo peor posible en un paper |
| Deuda muerta | `orbital_mechanics.py` (427 líneas, sin uso), `main.py` shim, 2 plantillas + `index.html`, 4 sistemas de metadatos de agentes, PDF de 3.6 MB en el repo | Ruido |

**Conclusión de diseño:** no es un problema de lenguaje, es un problema de
**arquitectura + vectorización**. La v3 debe extraer la física a un núcleo puro y
vectorizado, y convertir la web en *uno* de sus consumidores.

---

## 1. Estructura de directorios propuesta

Cinco principios, y de ellos sale el árbol:

1. **Núcleo puro sin web.** Nada en `quoss/` (excepto `api/`) importa FastAPI.
2. **El escenario es un dato**, no un request: un modelo Pydantic serializable a YAML.
3. **Contrato de arrays**: todo el pipeline habla vectores de tiempo NumPy.
4. **Una fórmula, un sitio.** El frontend no calcula física, solo pinta.
5. **Kernels intercambiables**: acelerar es cambiar un flag, no reescribir.

```
My_simulator/
├── pyproject.toml            # uv + build backend; deps y grupos (dev, viz, accel)
├── uv.lock                   # entorno reproducible bit a bit
├── .python-version
│
├── src/quoss/                # src-layout: el paquete instalable
│   ├── core/                 # tipos, unidades, constantes, errores, RNG, logging
│   ├── orbits/               # kepler, perturbaciones, SGP4/TLE, walker, ground track
│   ├── channel/              # atmósfera, turbulencia, link budget, fondo, detector
│   ├── qkd/                  # BB84 con decoy, finite-key (sin otros protocolos)
│   ├── system/               # passes, key volume, relay, multi-OGS, scheduling
│   ├── scenario/             # esquema del escenario + carga/validación/hash
│   ├── engine/               # orquestador del pipeline, caché, paralelización
│   ├── kernels/              # backends numéricos (numpy | numba | rust) tras una interfaz
│   ├── io/                   # clientes externos (CelesTrak, Open-Meteo), caché en disco, export
│   ├── viz/                  # figuras publicación (matplotlib + style sheet)
│   ├── cli/                  # `quoss run|sweep|serve|validate`
│   └── api/                  # FastAPI: routers finos que solo traducen HTTP ↔ engine
│
├── web/                      # frontend con build propio (deps vendorizadas, sin CDN)
├── scenarios/                # escenarios versionados y reproducibles (.yaml)
├── data/                     # datos estáticos read-only (OGS, coeficientes) + snapshots offline
├── validation/               # reproducciones de literatura, ejecutadas como tests
├── tests/                    # unit / physics / golden / api / e2e
├── benchmarks/               # regresión de rendimiento
├── docs/                     # manual de física (autogenerado), ADRs, manual de usuario
└── deploy/                   # Dockerfile, compose, config de hosting
```

**Reglas de dependencia (lo que evita que esto se degrade):**
`core ← orbits/channel/qkd ← system ← engine ← {cli, api, viz}`.
Las flechas nunca van al revés. `kernels/` y `io/` se consumen por inyección, no
por import directo desde la física. Se puede vigilar con un test de arquitectura
(import-linter) — es barato y salva el diseño a los 6 meses.

---

## 2. Optimizaciones y mejoras técnicas

### 2.1 Tooling y entorno — **sí a `uv`**
- `uv` + `pyproject.toml` + `uv.lock`: instalación 10–100× más rápida, entorno
  **reproducible** (lo que `requirements.txt` con `>=` no da), gestión de la propia
  versión de Python, `uv run` sin activar venv, `uvx` para ejecutar sin instalar.
- Grupos de dependencias: `dev`, `viz`, `accel`, `web`. El núcleo debe instalarse
  con muy poco (numpy + scipy + pydantic); FastAPI es un extra, no un requisito.
- `ruff` (lint + format, sustituye a black/isort/flake8) y `mypy --strict` solo en
  `core/` y física — donde el tipado paga de verdad.

### 2.2 Rendimiento (por orden de retorno)
1. **Vectorizar todo el eje temporal.** Es la mejora número uno: 1–3 órdenes de
   magnitud, y desbloquea Monte Carlo, barridos y constelaciones completas. El
   límite de 900 muestras desaparece.
2. **Caché en tres niveles**: (a) HTTP en disco para TLE/ERA5, (b) memoización de
   funciones puras (perfiles Cn², efemérides), (c) caché de resultados
   *content-addressed* por hash de escenario. Re-ejecutar una figura debe ser gratis.
3. **Paralelismo real** por passes / estaciones / realizaciones MC. Hoy
   `run_in_threadpool` sobre Python escalar no paraleliza nada (GIL); con arrays +
   process pool sí. En la API: cola de jobs, nunca bloquear el event loop.
4. **Kernels JIT** (`numba`) para los bucles irreducibles: integrales por capas,
   ensembles MC, detección de passes.
5. **Un kernel nativo** (Rust) solo si el profiler lo pide — ver §4.

### 2.3 Calidad y confianza
- **`pytest`** con la pirámide: unitarios → invariantes de física (property-based con
  `hypothesis`: monotonía de SKR vs pérdidas, límites η→1, conservación) → **golden
  tests** con tolerancia numérica → API → e2e. Y `pytest-benchmark` como puerta de
  regresión de rendimiento.
- **CI en cada push** (ruff + mypy + pytest + benchmarks). Sin esto, "verificado
  antes de shippear" es una intención, no una propiedad.
- **Determinismo**: un único `np.random.Generator` inyectado; semilla registrada en
  cada resultado.
- **Prohibido degradar en silencio.** Si un modelo no se puede evaluar, el resultado
  lleva `warnings[]` / `degraded[]` explícitos y la UI los muestra. Nunca un `except`
  que devuelva "sin escintilación" sin decirlo.
- **Resultados tipados**, no diccionarios anidados de listas: `xarray.Dataset` o
  Parquet + manifest. Analítica, export y figuras salen gratis.
- **Procedencia**: cada resultado (y cada figura) lleva hash de escenario + versión
  de código + versión de datos externos (época TLE, query ERA5). Esto es lo que hace
  que un revisor se lo crea.

### 2.4 Interfaz y configuración
- `pydantic-settings` en vez de constantes de módulo leídas de `os.getenv`.
- Inyección de dependencias explícita (contenedor o `Depends`), fuera los globals.
- **Sin autenticación en el núcleo.** Si algún día se hospeda, va detrás de un proxy
  o SSO. Quitar SQLite/usuarios/chats simplifica mucho (y elimina bcrypt, DB, etc.).

---

## 3. Distribución y despliegue

**Recomendación: núcleo como paquete Python instalable + CLI, y la web como capa
opcional encima. Cuatro niveles, el mismo motor en todos.**

| Nivel | Qué es | Para quién |
|---|---|---|
| 0 | `uv run quoss run scenario.yaml` | Tú, día a día. Reproducible, scriptable, sin servidor. Aquí salen las figuras del paper. |
| 1 | `quoss serve` → UI en localhost | Exploración interactiva, cero infra. Sustituye a la "web privada" actual. |
| 2 | Imagen Docker publicada (GHCR) | Cualquiera: `docker run …`. **Funciona offline** → demo de conferencia a prueba de wifi. |
| 3 | Servicio cloud público | Solo si se quiere. La misma imagen en un VPS/Fly.io/Render + cola de jobs. |

**Por qué así y no otra cosa:**

- **Mantener web + Docker: sí, pero invirtiendo la jerarquía.** Hoy la web *es* el
  simulador. Debe ser un cliente. Con eso, los cuatro niveles salen del mismo código
  sin esfuerzo extra y el paper deja de depender de clicar en un navegador.
- **Binario descargable (PyInstaller/Nuitka): no lo recomiendo.** Empaquetar
  numpy/scipy da artefactos de 200–400 MB, frágiles, uno por SO, con firma/notarización
  en macOS y Windows, y **no scriptables** — un investigador no puede extenderlo ni
  meterlo en un bucle de barrido. Un wheel + `uvx quoss` da el mismo "descarga y
  ejecuta" sin perder nada. Si algún día hace falta un artefacto sin Python, ese es el
  argumento para un núcleo Rust con binario fino (§4), no antes.
- **Servicio público: viable, con condiciones.** Es carga de cómputo, así que hace
  falta cola de jobs, límites de escenario, rate limiting y presupuesto. La forma
  sensata: **demo pública acotada** (escenarios pequeños, resultados cacheados) +
  potencia completa en local/Docker. La arquitectura que lo habilita es "motor sin
  estado + caché por hash + jobs" — se diseña ahora y se activa cuando se quiera.
- **WASM/Pyodide** (simulador en el navegador, sin instalar): tentador para
  divulgación, pero el stack numérico en WASM es lento y pesado. Descartar por ahora.

---

## 4. Lenguajes: dónde y cuándo cambiar

**Python se queda como lenguaje de la física y la orquestación.** El valor del
proyecto es corrección física e iteración rápida, y el ecosistema (scipy, sgp4,
astropy, xarray, matplotlib) está ahí. Además un revisor puede leerlo.

Escalera de rendimiento, en orden. **No saltes un escalón sin datos de profiler:**

1. **NumPy vectorizado** — cubre el 90% del problema actual. El cuello no es Python:
   es que la física es escalar.
2. **Numba** (`@njit`) para bucles irreducibles. Mismo archivo, un decorador, cero
   sistema de build. Segundo escalón por defecto.
3. **Rust (PyO3 + maturin)** para un kernel realmente caliente y con contrato
   numérico estable: generación de fading temporalmente correlacionado, MC grandes,
   barridos de constelación con 10⁴–10⁶ evaluaciones de enlace. **Rust antes que
   C++**: `maturin` produce wheels multiplataforma de forma reproducible (sin dolor de
   CMake), seguridad de memoria, y paralelismo trivial con `rayon`.
4. **C++** solo si hay que reutilizar una librería C++ existente. Si no, no aporta
   sobre Rust y sí añade fricción de build.

**MATLAB: no.** No es libre ni redistribuible, lo que rompe Docker, el servicio
público y la reproducibilidad por terceros (un revisor no debería necesitar una
licencia). Tampoco tiene ecosistema para API/web. Su única ventaja real es la calidad
de las gráficas, y eso se replica con `matplotlib` + una *style sheet* de publicación
(o SciencePlots), que hoy es estándar en papers.

**Frontend: TypeScript, no JS plano.** Es la parte menos mantenible del repo actual.
Propuesta: TS + Vite + **Svelte** (menos boilerplate que React para una app dominada
por paneles de control), deps **vendorizadas** (sin CDN), Cesium/three para 3D y
Plotly/uPlot para gráficas interactivas. Las figuras del paper salen de Python, no del
navegador.

**Regla para cambiar de lenguaje:** solo tras medir, solo para un kernel con contrato
numérico estable, y **siempre** con una implementación de referencia en NumPy puro
contra la que un golden test demuestre equivalencia. Un kernel acelerado sin su
referencia es deuda, no optimización.

---

## 5. Mejoras y consideraciones adicionales

**Sobre la física (lo que sube el nivel científico):**
- **Incertidumbre de primera clase.** El motor debería devolver *distribuciones*
  (P5/P50/P95, probabilidad de outage), no escalares. En SimulCTTC el Monte Carlo
  existe pero está desconectado del solver: era el hueco más señalado en
  `MEJORAS_PROPUESTAS.md`. En la v3 debe ser estructural, no un añadido.
- **Finite-key por defecto**, asintótico como flag explícito. Un pase LEO son ~5 min:
  el asintótico sobreestima, y más cuanto peor es el enlace.
- **Fading temporalmente correlacionado** (AR(1) / espectro de escintilación) en vez
  de muestras i.i.d.: cambia el outage de "fracción de instantes malos" a "duración
  realista de los fades", que es lo que gobierna el gating y los errores a ráfagas.
  Es material de novedad, no solo de exactitud.
- **Suite de validación como tests de CI**: reproducir números publicados (Ntanos 2021
  ya está empezado en `.agents/REPRODUCTION_NTANOS2021.md`; añadir SatQuMA y Micius).
  Barato y es el mayor multiplicador de credibilidad que existe.
- **Registro de fórmulas autogenerado**: cada función de física lleva en el docstring
  su cita y su tabla de símbolos/unidades, y `docs/` se genera de ahí. Así el manual
  de física no puede divergir del código (hoy `FORMULAS.md` se mantiene a mano).

**Sobre el flujo de trabajo:**
- **Barridos como ciudadano de primera** (`quoss sweep`). Las figuras de un paper son
  barridos; hoy hay un `routers/paper.py` de 544 líneas, que es exactamente el síntoma
  de no tener barridos en el motor.
- **Notebooks / marimo sobre el mismo motor** para explorar. La web es para demo e
  interacción, no para producir resultados publicables.
- **Capa de datos externa aislada y con snapshots offline** versionados: la demo no
  puede depender de que CelesTrak u Open-Meteo respondan.
- **Observabilidad**: tiempos por etapa del pipeline dentro del propio resultado.
  Optimizar con datos, no con intuición.

**Sobre la migración (importante hacerla en este orden):**
1. Definir `scenario/` y el contrato de resultado **primero**. Todo cuelga de ahí.
2. Portar la física **módulo a módulo**, y cerrar cada uno contra **fuentes externas**
   en cuatro niveles (invariantes / valores publicados / implementación independiente /
   regresión propia). Ver `tests/golden/README.md` y la regla de oro de `ROADMAP.md`.
   **Corregido en la etapa 2.1:** SimulCTTC **no** es un oráculo — nunca fue validado,
   y leerlo destapó defectos que congelar su salida habría canonizado. Queda como diff
   informativo no bloqueante. Su valor real es la *física documentada*, no sus números.
3. Después `engine/` + CLI. Con eso ya hay simulador completo y utilizable.
4. La API y el frontend **al final**. Son los consumidores, y rehacerlos antes de
   tener el motor es lo que produjo el acoplamiento actual.
5. No portar deuda: `orbital_mechanics.py`, el shim `main.py`, las plantillas
   duplicadas, usuarios/chats/SQLite y la física duplicada en JS se quedan atrás.

**Higiene de repo:** PDFs y `.tex` fuera del repo de código (repo aparte o git-lfs);
**un** sistema de metadatos de agentes, no cuatro (`.agents/` + `.planning/` + `.gsd/`
+ `.github/agents/`); cachés y datos generados en `.gitignore`; ADRs cortos para las
decisiones no obvias (por qué Rust, por qué Svelte, por qué no MATLAB).

**Decidir pronto (afecta a la estructura):** ¿multiusuario/hospedado o herramienta de
investigador? Mi recomendación: **herramienta de investigador**, con hospedaje como
capa opcional. Simplifica todo y no cierra ninguna puerta.

**Habilitador a futuro:** un motor vectorizado y con barridos baratos hace viables el
optimizador de constelaciones (GA / optimización bayesiana sobre parámetros Walker) y
los modelos surrogate — que en SimulCTTC quedaron como *stretch goal* precisamente por
falta de velocidad. No hay que implementarlos ahora; solo no cerrarles la puerta.

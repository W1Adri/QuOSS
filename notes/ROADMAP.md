# QuOSS — Roadmap de implementación

> Orden lógico de construcción, de dentro hacia fuera. Very high level: cada etapa
> lista los archivos en el orden en que conviene escribirlos, no su contenido.
> Ver `GUIA_REIMPLEMENTACION.md` para el porqué de la arquitectura.

**Regla de oro del orden:** nunca escribas un archivo que importe algo que aún no
existe. El grafo de dependencias es `core ← física ← system ← engine ← {cli, api, viz}`,
y este roadmap lo recorre en ese sentido.

**Regla de oro de la migración (corregida en la etapa 2.1):** ~~SimulCTTC es el
oráculo~~. **SimulCTTC no es un oráculo**: nunca fue validado, y leerlo destapó
defectos que congelar su salida habría canonizado (latitud geocéntrica devuelta como
geodésica, estaciones sobre una esfera con hasta ~21 km de error, una tasa «secular»
para J3 que no tiene término secular de primer orden, época que caía silenciosamente
al reloj de pared).

Cada módulo de física se cierra contra **fuentes externas**, en cuatro niveles
(ver [`tests/golden/README.md`](../tests/golden/README.md)):

| Nivel | Qué | Prueba |
|---|---|---|
| **V1** | invariantes y property-based, sin datos externos | consistencia interna |
| **V2** | valores publicados, transcritos con su cita | **corrección absoluta** |
| **V3** | implementación independiente (astropy/ERFA, datos de verificación del paquete `sgp4`, GMAT, Orekit), congelada en `tests/golden/data/` con manifest | corrección en régimen amplio |
| **V4** | snapshot de la salida *propia* de QuOSS | que un refactor no cambió nada. **No es validación** |

SimulCTTC queda como **diff informativo y no bloqueante**: una discrepancia es una
pista que vale la pena seguir en cualquiera de las dos direcciones, nunca un `assert`.

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
(unitarios + invariantes V1 + referencia externa V2/V3) antes de pasar al siguiente.

### 2.1 `orbits/` — geometría del problema

Orden revisado: `frames.py` va **primero**, no tercero. No depende de Kepler y todo
lo demás depende de él (era la duda anotada en `LAST_CHANGES.md` §6).

1. ✅ `orbits/frames.py` — TEME ↔ ITRF ↔ geodésico, ENU, GMST, calendario ↔ JD.
   Ver [ADR 0002](../docs/adr/0002-frames-and-time-scales.md)
2. ✅ `orbits/kepler.py` — Kepler, anomalías, posición/velocidad, elementos ↔ estado.
   Ver [ADR 0003](../docs/adr/0003-orbital-elements.md)
3. ✅ `orbits/perturbations.py` — fuerza zonal J2/J3/J4 exacta **+ integrador zonal
   numérico**, y tasas seculares analíticas **de primer orden en J2**.
   Ver [ADR 0004](../docs/adr/0004-zonal-perturbations.md).
   **Corregido al implementarlo:** el numérico **no** puede validar el analítico a
   O(J2²). Una tasa secular habla de elementos *medios*, y la diferencia
   medio↔osculador es ella misma O(J2) — mil veces mayor que la corrección de
   segundo orden. Los términos `J2²`/`J4` quedan fuera hasta que exista una
   transformación de Brouwer-Lyddane (la misma que necesitará `tle.py`). Lo que
   sí se validó, y más fuerte que una cota: el residuo del primer orden es
   **exactamente proporcional a J2**. J3 sale correcto por construcción y su
   ausencia de término secular está medida, no afirmada
4. ✅ `orbits/propagator.py` — propagación vectorizada: `propagate(elementos,
   TimeGrid, method=…)` → `Trajectory` en `(S, n, 3)` con marco, época y método
   dentro. Ver [ADR 0005](../docs/adr/0005-propagation.md).
   **Enviado a propósito con el enum incompleto:** solo `TWO_BODY` y
   `ZONAL_NUMERIC`. El modo analítico de J2 que este roadmap pedía **no puede
   devolver un estado utilizable** sin la transformación de período corto de
   Brouwer-Lyddane: alimentar tasas seculares con osculadores cuesta ~1300 km tras
   un día, y lo que crece es el reloj orbital (~2.9 min/día), no un sesgo — y cuánto
   cuesta depende de en qué punto de la órbita se declaren los elementos, así que no
   hay una cifra que documentar (medido en
   `tests/orbits/test_propagator.py::TestWhatNotHavingBrouwerLyddaneCosts`,
   corregido el 2026-08-04). Un nombre
   ausente obliga a preguntar en el punto de llamada; uno presente y equivocado
   no obliga a nada. Aquí se resuelven además los dos pendientes del módulo:
   la época viaja obligatoria dentro del `TimeGrid`, y la forma multi-satélite es
   `(S, n, 3)` satellite-major
5. ✅ `orbits/tle.py` — parseo TLE + SGP4, envolviendo `sgp4` (dependencia del
   núcleo desde esta entrada, no un extra) en vez de reimplementarlo.
   Ver [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md).
   **No entra por `propagate()`** (ya decidido en el ADR 0005): SGP4 devuelve
   estado en TEME directamente, y `tle.py` no construye ningún
   `ClassicalElements` — la disciplina que impide el error de mezclar
   elementos medios de un TLE con osculadores es no escribir esa línea, no una
   guarda de tipos nueva. `PropagationMethod` gana un tercer miembro, `SGP4`,
   que `propagate()` **no sabe ejecutar** (pedirlo da `NotImplementedError`):
   es un caso distinto del enum incompleto de `propagator.py` — ahí el nombre
   está ausente del todo, aquí está presente y es correcto, solo que vive en
   `propagate_tle`. `parse_tle` valida checksum, forma de línea y el código de
   error de `sgp4`, que la propia librería deja pasar en silencio (verificado
   contra el paquete instalado). El paquete trae `SGP4-VER.TLE` y
   `tcppver.out`: datos de verificación oficiales, gratis
6. ✅ `orbits/geometry.py` — elevación/azimut/slant range/rate de rango +
   **ángulo de point-ahead**, todo desde una `Trajectory` en TEME: la rotación
   a ITRF (vía `teme_to_itrf_state`) ocurre una sola vez dentro de
   `look_angles`, así que no hay un segundo sitio donde una mezcla de marcos
   pueda colarse. La velocidad de la estación en ITRF es exactamente cero por
   construcción, así que «relativo a la estación» y «la velocidad ITRF del
   satélite» son el mismo vector — no hace falta sumar el término de la
   estación aparte. **Corregido al medir:** el ángulo de point-ahead lleva
   **factor 2**, no el `v_perp/c` de una sola vía — un terminal monostático
   tiene que adelantar la vía de transmisión y a la vez recibir por la vía que
   la luz realmente sigue. Medido para un paso a 67.1° de elevación sobre
   Castelldefels en la SSO de 700 km de este repo: **50.6 µrad**, mayor que
   los 35 µrad que este roadmap citaba antes de tener la cuenta con el factor
   2 (`tests/orbits/test_geometry.py::TestPointAheadAngle`). El Doppler
   **no** vive en este módulo: `look_angles` da `range_rate_km_s`, una
   cantidad puramente geométrica, y `doppler_shift_hz` es una función aparte
   de una línea que solo se necesita cuando se conoce la frecuencia portadora
   — la misma razón por la que `Trajectory` no lleva un modelo de gravedad.
   V3 contra el `AltAz` de astropy (nuevo `tests/golden/generators/gen_geometry_reference.py`):
   elevación y azimut concuerdan a milésimas de grado, rango a 2.2e-4
   relativo, sobre 24 combinaciones estación×satélite×época — sin oráculo
   independiente todavía para `range_rate_km_s` ni el ángulo de point-ahead,
   que quedan como V1 (ver `tests/golden/README.md`)
7. ✅ `orbits/constellations.py` — Walker-Delta (`i:T/P/F`), inclinación
   heliosíncrona (SSO) e semieje de traza repetida. Las tres funciones son
   geometría o álgebra pura sobre lo que ya existía: `walker_delta` no calcula
   ninguna física, solo reparte `T` satélites en `P` planos y los devuelve como
   **un** `ClassicalElements` de longitud `T` (nunca una lista); la SSO invierte
   en forma cerrada la propia fórmula de `secular_rates_j2` (si hiciera falta
   `scipy.optimize` ahí, sería señal de un error, no de que el problema lo
   pida); solo la traza repetida necesita `brentq`, porque `a` aparece a los
   dos lados de la condición de resonancia. **Decisión que se pudo equivocar
   al revés:** el espaciado dentro de plano se hace en anomalía **media**, no
   verdadera — para una órbita excéntrica son ángulos distintos, y solo el
   medio se mantiene exactamente constante en el tiempo bajo movimiento
   kepleriano puro (`tests/orbits/test_constellations.py::TestWalkerDeltaInvariants::test_true_anomaly_spacing_is_not_exact_once_eccentric`
   es el control negativo que lo demuestra). **El sentido del `F`** —el
   parámetro que la gente invierte— se fija con un caso `6:6/3/1` resuelto a
   mano más el chequeo de fórmula independiente de MATLAB Aerospace Toolbox;
   no se encontró un ejemplo Walker citable de Vallado con confianza
   suficiente para transcribirlo como V2, así que la corrección descansa en
   invariantes V1 (espaciado exacto de RAAN y de anomalía media, recuento
   exacto), dicho así en vez de inventar una cita. **El hueco que hereda del
   ADR 0006, sin esconderlo:** la inclinación/semieje que devuelven las dos
   funciones físicas son una afirmación sobre elementos *medios* — construirlos
   como `ClassicalElements` osculadores (el defecto de la propia clase) e
   intentar sacar un estado con `coe_to_rv` hereda el mismo desajuste ya medido
   en `kepler.py` (hasta 1290 km/día para una SSO de 700 km, y no una cifra
   única). No se remide aquí porque es la misma fórmula y el mismo régimen ya
   medidos; la guarda de tipos del ADR 0006 es lo que impide que ese error sea
   silencioso. Ver [ADR 0008](../docs/adr/0008-constellation-design.md).

**Trampa a hacer imposible por tipos:** los elementos medios de un TLE son de
Brouwer-Lyddane con corrección de Kozai, **no** los del propagador J2 analítico.
Mezclarlos es un error de km que parece funcionar.

✅ **Hecho por tipos (2026-08-01), transversal a 2.1.2–2.1.4:** `ClassicalElements`
lleva un `ElementType` (`OSCULATING` / `MEAN_BROUWER`) igual que lleva su `Frame`.
`rv_to_coe` marca osculador, `coe_to_rv` exige osculador, `secular_rates_j2` exige
medio, y no hay conversión entre los dos porque Brouwer-Lyddane sigue sin existir:
la bandera es hoy una puerta cerrada que marca dónde haría falta. Ver
[ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md).

### 2.2 `channel/` — el canal óptico

**Decisión que gobierna toda la etapa, tomada antes de escribir física:** la
referencia canónica del canal (Andrews & Phillips) **no se cita por número de
ecuación porque no se pudo abrir**. Fuentes primarias: ITU-R P.1621-2, P.1622 y
Ntanos et al. 2021, todas gratuitas y numeradas. Catorce huecos declarados en
vez de rellenados → [ADR 0009](../docs/adr/0009-citation-policy.md). **Etapa
cerrada**: los siete módulos escritos, y ninguno de los huecos rellenado con la
cita más plausible.

1. ✅ `channel/atmosphere.py` — perfil Cn² (HV 5/7), viento de Bufton, malla de
   integración de 139 capas y refracción. **Corregido al implementarlo:** la
   Ec. (7) de P.1621-2 da **grosores de capa, no altitudes** — leerlas como
   altitudes pone el techo de la atmósfera en 992 m en vez de 20 km, y ningún
   número resultante parece raro. Y su Ec. (3) **no vale 1 en sus propias
   condiciones de referencia** (se desvía 140 ppm): inconsistencia interna de la
   recomendación, documentada y fijada por un test
2. ✅ `channel/turbulence.py` — varianza de log-irradiancia, promediado de
   apertura, r₀ y ángulo isoplanático, todo sobre momentos del perfil.
   **Asimetría subida/bajada como parte del API**, no como nota: el uplink no
   recibe promediado de apertura (P.1622 §4.1.1) y su función no tiene dónde
   aceptar un diámetro. El V2 más fuerte del canal: las **ocho** varianzas
   publicadas de la Tabla 2 de P.1622, reproducidas a la precisión impresa.
   Rytov en régimen fuerte y frecuencia de Greenwood **siguen fuera** — pendientes
   con su fuente, no implementadas a medias
3. ✅ `channel/beam.py` — divergencia, acoplamiento geométrico y vaivén del haz.
   **Se aparta de la forma publicada, con la razón medida:** el producto de
   ganancias de Ntanos et al. Ecs. (3) y (5) es el límite de apertura pequeña de
   la integral de truncación gaussiana `1 − exp(−D_r²/2W²)`, y esa integral es
   la que se usa porque satura en 1 en vez de prometer más luz de la que se
   transmitió. La Ec. (5) **tal como está impresa** (`(8/w_0)²` en vez de
   `8/w_0²`) es 8 veces mayor, **9.03 dB optimista**, y con los parámetros del
   propio paper devuelve una transmitancia de **1.36**. El vaivén es
   **solo de subida** (P.1622 §4.3), y la razón vaivén/divergencia crece como
   `D_T^(5/6)`: un transmisor de 1 m pasea su haz **3.15 anchos de haz**, así
   que estrechar el haz deja de ayudar. El ensanchamiento por turbulencia queda
   fuera por autoridad de P.1622 §4.4, no por olvido
4. ✅ `channel/pointing.py` — pérdida de apuntado y **desvanecimiento** por
   jitter. La salida no es un número, es una **distribución**: jitter gaussiano
   en dos ejes → error radial Rayleigh → la transmitancia relativa sigue una
   **ley de potencias** `F(x) = x^(gamma²)` con un solo parámetro,
   `gamma = w_zeq/(2 sigma_s)`, el radio del haz medido en jitters (derivación
   de tres líneas en el docstring). **La trampa que da forma al módulo:** la
   Ec. (9) de Farid & Hranilovic lleva un factor `A_0` que **es** el
   acoplamiento geométrico de `beam.py`, así que multiplicar «pérdida
   geométrica × pérdida de apuntado» tal como está publicada cuenta `A_0` dos
   veces — **17.5 dB inventados** en la geometría de referencia. Todas las
   funciones devuelven el factor **relativo**, normalizado a 1 con apuntado
   perfecto. **Dos fuentes independientes concuerdan** en el exponente
   (`gamma² = 19.42` de Farid & Hranilovic contra `beta_p = 19.23` de Ntanos et
   al.: 0.01 dB en la pérdida al 1 % de outage), y el residuo está **atribuido**
   a la corrección de apertura finita, no tolerado. La condición de validez que
   los autores publican (`W/a > 6`) **falla** para el telescopio de 2.3 m del
   sistema de referencia, y eso sale en `warnings[]` con la medida de lo que
   cuesta. Sin boresight (hueco 3 del ADR 0009) y sin correlación temporal (eso
   es `system/correlated_fading.py`)
5. ✅ `channel/background.py` — radiancia de cielo, fondo solar/lunar y gating
   temporal. **Las dos ecuaciones publicadas son la misma ecuación** —la Ec. (1)
   de P.1621-2 y la Ec. (19) de Ntanos et al.— y discrepan en las **unidades**
   del campo de visión bajo el mismo nombre: pasar el ángulo a la forma que
   quiere estereorradianes son **41.05 dB**, y leerlo como semiángulo en vez de
   ángulo completo son **6.02 dB**. La convención va en el nombre del argumento.
   **La trampa que da forma al módulo:** su Ec. (20) llama «probability» a
   `t_gate × cps`, que es el **número esperado** de cuentas; con la luz solar
   brillante que la propia UIT tabula a 850 nm, su receptor y su puerta de 1 ns,
   esa «probabilidad» vale **3.42** (y 1.09 con su telescopio de 1.3 m). Se
   devuelve `1 - exp(-µ)`, con aviso por encima de 0.1 cuentas por puerta —
   umbral **derivado**: es donde la lectura lineal sobreestima un 5 %. El
   **gating temporal** es el único parámetro libre del presupuesto de ruido, y se
   cuantifica lo que la fuente solo nombra: el fondo escala lineal con la puerta
   y la señal como `erf(T/2√2σ)`, así que pasar de 1 ns a 100 ps con el jitter de
   50 ps declarado cuesta **0.08 dB de señal y quita 10 dB de fondo**, y el
   óptimo de `S/√B` está en **2.80σ** (5.36 dB mejor que 1 ns, y ancho: 0.55 dB
   entre 1.5σ y 5σ). **Cuatro huecos nuevos declarados y medidos**, todos en el
   [ADR 0009](../docs/adr/0009-citation-policy.md): la Tabla 1 promete radiancia
   **de la Tierra** en su título y no la trae, así que no hay fondo de subida; las
   dos fuentes discrepan **un factor diez** de noche (1.24x de ruido total a
   0.75 m, **2.83x** a 2.3 m contra 300 cps de cuentas oscuras); su «10 kcps con
   luna llena» **no es reproducible** sin elegir telescopio (8.1 / 24.4 /
   76.4 kcps); y la radiancia tabulada es **cenital**, sin dependencia angular
   publicada (4.66 dB a 20° si siguiera a la masa de aire — no se aplica, y hay
   un test que aserta que ninguna firma acepta una elevación). El hueco 4 pasa de
   declarado a **medido**: interpolar a 785 nm da 0.48 dB de diferencia entre
   reglas y **16-27 % de error** en un leave-one-out sobre la propia tabla, así
   que se interpola registrando un `DEGRADED`, nunca en silencio
6. ✅ `channel/detector.py` — cadena de eficiencia, cuentas oscuras,
   afterpulsing y tiempo muerto. **La regla que da forma al módulo: las medias
   se suman y la exponencial se hace una vez, al final** — porque las tres
   formas publicadas que reproduce son truncamientos a primer orden de eso
   (`1 - 2 p_dc` de Lim, su `D_k(1 + p_ap)`, y el `Y_0 = P_dc + P_noise` de la
   Ec. (A6) de Ntanos), excelentes en su punto de operación (7e-12, 0.16 % y
   1.2e-6) y las tres por encima de 1 en el barrido diurno de este proyecto
   (1.93, 1.006 y 3.42). **La trampa que evita:** la cadena de eficiencia se
   aplica a todo lo que entró por la apertura y a nada que naciera dentro del
   detector — aplicársela también a las cuentas oscuras esconde **0.94 dB** de
   ruido y mueve su peso del 7 % al 25 % del presupuesto nocturno. **El hallazgo
   que condiciona a `background.py`:** el gating no toca el afterpulsing, porque
   escala con la tasa de clics y no con la puerta, así que estrechar de 1 ns a
   100 ps vale **10 dB con el nanohilo de Ntanos y 0.22 dB con el APD de InGaAs
   de Lim** — «estrecha la puerta» es condicional y la condición es el detector
   (hueco 5 del [ADR 0009](../docs/adr/0009-citation-policy.md), que pasa de
   declarado a **medido**). Reproduce la `D_k` de Lim et al. a 3e-7 relativo con
   cota **derivada** (`p_dc²/(η k + 2 p_dc) ≤ p_dc/2`) y sin necesitar la
   anchura de puerta que ese paper nunca declara, porque se cancela. Dos
   umbrales derivados: los modelos de tiempo muerto se separan un 5 % en
   `R·τ = 0.3554` (11.8 Mcps a 30 ns) y los dos de afterpulsing en
   `p_ap = sqrt(1/21)`, con `WARNING` y las dos cifras dentro. El paralizable
   **no se invierte** (16.3 y 59.4 Mcps dan la misma lectura de 10 Mcps), así
   que `incident_count_rate_cps` existe solo para el otro. Y una afirmación
   publicada que **sí** reproduce: la §4.2 de Ntanos sobre no saturar por tiempo
   muerto es correcta con dos órdenes de magnitud de margen (500 kcps contra un
   techo de 33.3 Mcps, 1.5 % de pérdida). Las dos leyes de tiempo muerto y la
   fracción de puertas vivas `1/(1 + b·p)` están verificadas V1 contra Monte
   Carlo del proceso del que se derivan
7. ✅ `channel/link_budget.py` — **ensambla** los anteriores en pérdida total y
   ruido total. **El hallazgo:** dos de los seis módulos no devuelven un número
   —apuntado devuelve una distribución y turbulencia una varianza— y la práctica
   publicada de **sumar el cuantil al 1 % de cada uno** no da un presupuesto al
   1 %. Las dos colas tienen forma cerrada *en decibelios*: la de apuntado es
   **exactamente exponencial** (sustituir `L = -10 log10 x` en la ley de
   potencias `F(x) = x^(γ²)` lo demuestra en una línea) y la de escintilación
   **exactamente gaussiana**, así que su suma es una gaussiana modificada
   exponencialmente y el cuantil conjunto es **exacto, sin Monte Carlo**:
   1.668 dB donde la suma publicada da 2.312 dB. Son 0.644 dB de margen que
   nadie pidió y, sobre todo, una etiqueta falsa — ese presupuesto es del
   **0.066 %** de outage, quince veces más estricto que el 1 % impreso al lado.
   `FadeCombination` tiene dos miembros y ningún defecto escondido: `EXACT` por
   defecto, `ADDITIVE` para reproducir lo publicado, y la diferencia sale de la
   misma llamada. Verificado V1 contra 4e6 muestras del jitter gaussiano en dos
   ejes y de la lognormal, y V3 reevaluando la propia función de distribución en
   la respuesta. **La trampa que da forma al módulo:** `click_probability` toma
   una `efficiency` y un presupuesto quiere la cadena del receptor como línea,
   así que hacer las dos cosas la cuenta **dos veces — 12.71 dB en vez de
   6.36**, un factor 4.3 en tasa de clave. El API guarda las dos transmitancias
   con nombre (`transmittance` completa, `channel_transmittance` hasta la
   apertura) y ninguna es el producto de la otra por algo que haya que recordar.
   Dos cosas más que salieron: la Ec. (18) de Ntanos et al. **devuelve un número
   negativo y lo llama pérdida** (es el nivel, no la caída: sumarla como está
   impresa deja el total equivocado en el doble del desvanecimiento), y su total
   de 20 dB de §4.2.1 **no se reproduce**. Por eso la extinción es un
   **argumento obligatorio sin defecto** y no un modelo: hueco 14 del
   [ADR 0009](../docs/adr/0009-citation-policy.md), porque la UIT publica
   absorción y dispersión **solo como figuras**. **Y el término que faltaba no
   estaba en la atmósfera, estaba en el transmisor** (hueco 15): `beam.py`
   propaga una gaussiana **sin truncar**, y el borde de la apertura corta el
   13.5 % del haz. El número tentador —0.632 dB de potencia recortada— es la
   respuesta a otra pregunta: en el eje lo que integra es la **amplitud** y la
   intensidad es su cuadrado, así que el modelo sin truncar sobreestima
   `[1-exp(-α²)]²/[1-exp(-2α²)]`, que a `α = 1` son **3.352 dB**. Con él, el
   presupuesto de Ntanos et al. pasa de 15.741 a **19.094 dB** y su residuo de
   4.259 dB (que exigía `L_zen = 0.375`, absurdo) a **0.906 dB** (`L_zen =
   0.812`, ordinario). Compatible, no reproducido. Y `tests/golden/README.md`
   tenía este término predicho en 0.63 dB desde antes de que el módulo
   existiera: está corregido allí, con la forma cerrada verificada contra la
   integral de difracción por cuadratura

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
un notebook, y cada módulo tiene su verificación V1–V3 en verde (ver la regla de oro
arriba).

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
escenario de referencia reproduce números publicados (V2), no los de SimulCTTC.

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

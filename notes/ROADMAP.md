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
1. ✅ `qkd/base.py` — la frontera: `LinkConditions` (entra transmitancia +
   ruido), `KeyRate` (sale tasa + QBER), `QkdProtocol` (la interfaz) y
   `ProtocolRegistry` (el nombre que escribe un escenario). **Sin física
   dentro.** Las tres trampas que le dan forma: (1) `NoiseBudget` da una
   **media** y un protocolo necesita la **probabilidad** `Y_0 = 1 - exp(-µ)` —
   leer una por la otra sobreestima **3.58 %** con el telescopio de 2.3 m y
   **0.38 %** con el de 0.75 m bajo el día claro de 6 W/(m²·µm·sr) de Ntanos et
   al., y la conversión **es** `click_probability`, no una segunda copia de la
   exponencial; (2) la transmitancia ya lleva el receptor dentro, así que hay
   **un** campo de transmitancia y **ninguno** de eficiencia, y el doble conteo
   de 6.36 dB no tiene por dónde entrar; (3) solo se guarda la tasa **por
   pulso** y la de por segundo se deriva. La interfaz **comprueba a sus
   implementaciones** —forma, tasa de pulsos copiada y nombre— con un test de
   implementación rota a propósito detrás de cada comprobación. **Dos ausencias
   con motivo:** no hay entrada de finite-key por bloques (un bloque es una
   integral sobre el pase: `system/key_volume.py`), así que toda tasa sale
   etiquetada `ASYMPTOTIC`; y el registro no tiene ni tendrá un nombre para E91,
   CV-QKD, MDI-QKD ni TF-QKD, que quedan **fuera del alcance** y no solo sin
   escribir (ver el cierre de esta etapa, más abajo), por la regla del
   [ADR 0005](../docs/adr/0005-propagation.md). 100 % de cobertura de líneas y
   ramas, 102 tests
2. ✅ `qkd/bb84.py` — BB84 con pulsos coherentes débiles y decoy vacío+débil, la
   primera implementación de `QkdProtocol`. Modelo de Ma et al. 2005 Ecs. (7)-(11)
   y cotas decoy Ecs. (34), (35) y (37); tasa GLLP de su Ec. (1), que es la Ec. (1)
   de Ntanos et al. **Cuatro decisiones con su número:** (1) se usa el rendimiento
   **exacto** —la primera línea de su Ec. (7), que **es** `click_probability`— y no
   la aproximación `Y_0 + 1 − e^(−ηµ)` de su Ec. (10) y de la (A4) de Ntanos et
   al., que difiere **0.0000787 %** de noche y **0.070965 %** de día en el telescopio de
   0.75 m, y por encima de **7.152 cuentas por puerta devuelve una probabilidad
   mayor que uno**; (2) el QBER se escribe como **mezcla** de la moneda del fondo y
   el error de la óptica, así que `E ≤ ½` se cumple en coma flotante — el numerador
   publicado junto a la ganancia exacta lo rompe a **3.912 cuentas por puerta**, y
   el sol brillante de la ITU está un 12.6 % por debajo; (3) donde la cota no
   certifica nada se devuelve `e_1 = ½` y **no** `e_1 = 0`, que dibujaría un canal
   perfecto donde falló el análisis; (4) `q` incluye la fracción de pulsos de
   señal, así que toda tasa es **por pulso emitido**. **La intuición corregida:**
   la cota no falla por pérdida —de η = 1 a 1e-08 sigue positiva y converge a
   `Y_0`— sino por **intensidad**, por encima de µ = 3.72 con ν = 0.1.
   **Verificación:** V3 contra el **programa lineal** del que la Ec. (34) es forma
   cerrada, resuelto con `scipy.optimize.linprog` (coinciden a 1e-09); V2 contra el
   óptimo analítico de µ de su Ec. (12), **0.7687**, reproducido al **0.1 %** con
   tolerancia derivada del tamaño de lo que esa ecuación desprecia; V2 del estado
   de vacío (Ec. 33) exacto. Y una inconsistencia de la fuente escrita en vez de
   arreglada: «4:1:16» y «q = 2/5» en la misma frase de Ntanos et al. §4.1 no
   concuerdan por un factor 4.2, y el orden que reproduce su `q` es 16:1:4. 100 %
   de cobertura de líneas y ramas, 552 tests
3. ✅ `qkd/finite_key.py` — la cota finite-key componible, y **no la de
   Tomamichel que esta línea pedía**: el protocolo que hay es decoy con pulsos
   coherentes débiles, así que la fuente es **Lim et al. 2014** (*PRA* 89,
   022307), cuyas Ecs. (1)-(5) analizan exactamente eso y están construidas
   sobre la relación de incertidumbre entrópica de Tomamichel y Renner. Entra un
   bloque de cuentas acumuladas, sale una **longitud en bits** con sus dos
   probabilidades de fallo: no es una tasa con corrección, y la interfaz de
   `base.py` no podría expresarlo —una afirmación finite-key habla de un bloque,
   y un bloque es una integral sobre el pase—. **Lo que mide, en el enlace de
   referencia a cenit con el reparto 16:1:4:** un bloque de 1e10 pulsos (cien
   segundos a 100 MHz) certifica **1.1387e-05 bits por pulso** contra los
   **6.0239e-05** del límite asintótico del mismo protocolo — el **18.9 %** —, y
   a 1e9 pulsos no certifica nada. **El hallazgo que solo este módulo ve:**
   asintóticamente los pulsos decoy son coste puro y su fracción óptima es cero;
   con un bloque de pase el óptimo está **cerca del 50 %** y vale un factor
   **3.4** sobre gastar una décima parte, porque la desviación de Hoeffding la
   comparten las tres intensidades. **Verificación:** V3 entre fuentes —con
   `mu_3 = 0` y bloque grande, su Ec. (3) **es** la Ec. (34) de Ma et al. que
   implementa `bb84.py`, y el residuo cae exactamente como `1/sqrt(N)`
   (4.33e-04 a 1e16 pulsos, 4.33e-08 a 1e24)—; V2 contra su Fig. 1, cuyo cociente
   publicado de 1.75 entre bloques de 1e9 y 1e7 se reproduce en **1.79**, y ese
   cociente es además lo que **decide** una ambigüedad de su modelo de error
   (hueco 16 del [ADR 0009](../docs/adr/0009-citation-policy.md)). Lo que **no**
   se reproduce y queda escrito: su curva de bloque 1e4. Ver
   [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md). 100 % de cobertura de
   líneas y ramas, 158 tests. **El «por defecto activo» que esta línea pedía no
   se puede fijar todavía**: quien posee un pase —y por tanto un bloque— es
   `system/key_volume.py`
**La etapa 2.3 se cierra aquí, con un solo protocolo — decisión del 2026-09-12.**
Las tres líneas que ocupaban este sitio —`qkd/entanglement.py` (E91), `qkd/cv.py`
(CV-QKD) y `qkd/mdi_tf.py` (MDI-QKD y TF-QKD con relay no confiable)— **se retiran
del plan**. No es un juicio sobre esos protocolos: es que no son el protocolo de
este trabajo, y una línea de roadmap que nadie va a escribir envejece igual de mal
que un número sin test — con la diferencia de que además hace parecer incompleto
algo que está terminado. Si alguno hace falta más adelante, vuelve a esta lista
cuando haya alguien que lo vaya a escribir.

**Por qué retirarlas no cuesta nada estructural, que es la parte que hay que
defender.** El punto de extensión de este paquete no es la lista, es la pareja
`QkdProtocol` + `ProtocolRegistry` de `base.py`, y esa ya está escrita, con su
verificación y con un test que le pasa una implementación rota a propósito para
comprobar que la interfaz caza el fallo. Añadir un protocolo consiste entonces en
escribir una clase que implemente `_key_rate` y registrar su nombre: ni
`channel/`, ni `system/`, ni `engine/` se enteran, porque lo único que cruza la
frontera es `LinkConditions` → `KeyRate`, y ninguno de los cuatro protocolos
retirados cambiaría esos dos tipos —los cuatro consumen una transmitancia y un
fondo, y los cuatro producen una tasa y un QBER—. El coste de volver es **un
fichero**, no un refactor. Eso es exactamente lo que hace honesto retirarlas: si
el coste de volver fuera un refactor, retirarlas sería tomar la decisión a
escondidas.

**Lo que no se retira, y ahora guarda más que antes:** la regla de que el registro
no tiene un nombre sin implementación detrás. Los controles negativos de
`tests/qkd/test_base.py` sobre el registro real —que `resolve("e91")` levanta
`ConfigurationError`, y que ninguno de los ocho deletreos (`e91`, `entanglement`,
`cv`, `cv-qkd`, `mdi`, `mdi-qkd`, `tf`, `tf-qkd`) está presente— **se quedan
donde están**. Antes protegían contra seleccionar un módulo que aún no existía;
ahora protegen contra seleccionar uno que no va a existir, que es el caso en el
que fallar en voz alta importa más.

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

1. ✅ `system/passes.py` — detección y segmentación de passes contra una **máscara
   de elevación**, que es argumento **obligatorio y sin defecto** porque tiene
   óptimo interior (ver la línea 2). Las cuatro cosas que una implementación
   ingenua calcula mal, cada una medida en el día de referencia: (1) **los bordes
   no están en la rejilla** —tomar la primera muestra por encima de la máscara
   tira **3.79 s de 1799.79, el 0.21 %**—, así que los dos cruces se refinan por
   interpolación lineal en elevación, que es donde la curva es más recta; (2) **el
   tiempo de permanencia de una muestra no es el paso**, así que los pesos son los
   del **punto medio recortados a la ventana refinada** y suman la duración
   *exactamente* —lo que permite que los dos regímenes de la línea 2 compartan un
   solo vector de cuadratura, y lo que hace que un peso signifique «pulsos
   emitidos mientras esta muestra describía el enlace»—; (3) **la muestra más alta
   no es la culminación** —el máximo discreto queda **0.029°** bajo la verdad en
   una rejilla de 10 s y **0.51°** en una de 30 s, y el vértice de tres puntos en
   forma de Newton (válida para espaciado desigual) los baja a **0.0006°** y
   **0.081°**—; (4) **un pase cortado por el borde de la rejilla es un fragmento**,
   y sus números son cotas inferiores, así que va marcado y con `warning`. Y un
   guardia que cuenta **muestras** y no estima un error, porque una rejilla gruesa
   no difumina la clave sino que la **infla** (+2.0 % a 5 muestras por pase,
   +8.6 % a 2) y el sesgo **no es monótono** en el paso. Vectorizado sobre los dos
   ejes: dos `np.nonzero` segmentan un día de sesenta satélites a 1 s —5.2 millones
   de elevaciones, 240 pases, 0.07 s— y hay un test que lo corre. 100 % de
   cobertura de líneas y ramas, 79 tests
2. ✅ `system/key_volume.py` — la integral sobre el pase → clave **por pase y por
   día**, y con ella **el «por defecto activo» que la etapa 2.3 no podía fijar**:
   `pass_key_volume` devuelve `FINITE` y **no hay ningún argumento `regime=`**,
   porque el número asintótico solo se alcanza llamando a
   `asymptotic_pass_key_volume`. **La decisión de fondo: el bloque es el pase** —
   un bloque por muestra da **cero bits del día entero** (la cota no es aditiva
   sobre sub-bloques) y uno por día mezclaría el QBER del 1.9 % de los pases
   muertos con el 1.24 % de los buenos sobre horas en que no se envía un pulso.
   **Lo que mide:** en un día del enlace de referencia la integral asintótica
   reclama **3.78 Mbit** y la cota finita certifica **0.43 Mbit**, el **11.5 %** —
   y **dos de los cuatro pases no certifican nada** donde el asintótico reclama
   320 y 199 kbit, así que el error de reportar lo asintótico es **ilimitado** y no
   un factor. Y muere **de golpe**: el pase 4 tiene 309 867 detecciones y lo mata
   la tasa de error de fase, que devuelve `phi = 0.5` y anula el término de un
   fotón entero. **El hallazgo que solo esta etapa ve:** la máscara de elevación
   tiene **óptimo interior cerca de 8°** — la columna asintótica es monótona
   porque el recorte a cero por muestra la protege (por debajo de 5° las muestras
   extra aportan *exactamente* cero), la finita no, y bajar de 8° a 2° compra un
   **71 %** más de segundos y destruye el **6.0 %** de la clave, con el mecanismo
   medido (+2.6 % de eventos de un fotón contra +5.5 % de fuga de corrección).
   **Y la componibilidad, que casi toda leyenda de figura falla:** sumar `n` pases
   da una clave `n·eps`-segura, no `eps`-segura; `composed_security` lo calcula y
   un día honestamente `1e-10`-seguro cuesta el **6.5 %**. Los dos regímenes
   comparten **una** cuadratura y **un** objeto de configuración, con test de que
   el puente es portante. Ver
   [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md). 100 % de cobertura de
   líneas y ramas, 80 tests
3. ✅ `system/monte_carlo.py` — ensembles de fading → **P5/P50/P95 y outage**,
   estructural. **Lo primero que mide es qué número reportaba la línea 2:** la
   clave de un pase con el enlace en su cuantil del 1 % de desvanecimiento
   **durante todo el pase**, porque `LossBudget.transmittance` lleva el margen
   dentro. El mismo cálculo a la transmitancia media da **758 707 bits/día**
   contra 432 985, así que la cifra de diseño **infrarreporta la mediana un
   43 %**; los pases 2 y 4 siguen muertos —a la media no por `φ = 0.5` sino
   porque la corrección de errores adelanta al término de un fotón por 2.2 y
   8.7 veces—. Conjunto de referencia (1 000 realizaciones, `τ` = 2 ms / 20 ms,
   cuentas de Poisson): día **P5 735 329 / P50 758 314 / P95 782 391**, en
   **0.86 s**. **El hallazgo honesto:** a la `τ` física el desvanecimiento pone
   el **0.11 %** de banda P5–P95 en el pase 1 y contar pone el **9.0 %**
   —noventa veces más, desde las cuentas pequeñas de señuelo y vacío que la
   cota amplifica—; la banda del desvanecimiento crece como `sqrt(τ)` y cruza el
   1 % entre 10 y 100 ms, dos órdenes de magnitud por encima de la estimación
   física. Cuantiles de la suma por realización (P5 del día 735 329 contra
   724 553 sumando P5), `eps` compuesto como en la línea 2, Poisson + binomial
   sobre el bloque agrupado (adelgazamiento exacto, `1 − Q < 1e-3`), un hijo
   del generador por pase (el trozo no cambia un bit), y una realización
   reproduce `pass_key_volume` **bit a bit**. Realizaciones por criterio
   (`realisations_for_quantile`, error estándar del P5 al 0.2 % de la mediana a
   mil). Ver [ADR 0012](../docs/adr/0012-correlated-fading-and-monte-carlo.md).
   100 % de cobertura de líneas y ramas
4. ✅ `system/correlated_fading.py` — el proceso temporalmente correlacionado —
   el punto de novedad, y la reserva de `channel/link_budget.py` cerrada. Tres
   motores de Ornstein-Uhlenbeck (log-irradiancia; dos ejes de jitter) en la
   variable donde cada desvanecimiento es gaussiano, con la normalización de
   `link_budget.py` (`E[F_s] = 1`) y la ley de `pointing.py` (`x^(γ²)`,
   `E[F_p] = γ²/(γ²+1)`) como **oráculos V3 a un millón de sorteos**;
   discretización AR(1) **exacta** en rejillas no uniformes, autocorrelación
   `exp(−kΔt/τ)` dentro del error de su estimador. **El tiempo de correlación
   es un parámetro sin defecto** (ADR 0009): Taylor da `τ = ℓ/v`, y en un
   enlace LEO `v` es el barrido de la línea de visión —**62–85 m/s** a 7 700 m
   contra 2.3 m/s de viento— que con una anchura de Fresnel de 0.109 m da
   **1.3–1.8 ms**, con `ℓ` declarado hueco. **La decisión técnica:** el modelo
   de cuentas recibe el factor **promediado sobre la permanencia**, muestreando
   la integral del proceso exacta junto con su extremo (reducción
   `w = 2(τ/T)²(T/τ − 1 + e^{−T/τ})`, a `τ/2` para el apuntado, que va con el
   cuadrado), verificado contra fuerza bruta al 1.5 %; un sorteo i.i.d. por
   muestra sobreestimaría la fluctuación del recuento del pase entre 10 y 22
   veces, y el módulo lo avisa. **Y la duración de los desvanecimientos, con su
   divergencia dicha:** Rice diverge para un proceso no diferenciable, así que
   `fade_duration_statistics` cuenta cruces por paso, comprobados contra la
   binormal exacta; el desvanecimiento correlacionado dura **47 / 22 / 14 ms** a
   pasos de 20 / 5 / 2 ms contra 1.04 pasos i.i.d., y el recuento crece como
   `Δt^{−1/2}`. 100 % de cobertura de líneas y ramas; entre los dos módulos, 83
   tests y 15 doctests
5. ✅ `system/pcflos.py` — probabilidad de línea de vista libre de nubes, leída
   como **la probabilidad de que el pase exista** y nunca como factor sobre la
   clave. Lo exacto: `pCFLOS(cénit) = 1 − f` a partir de la fracción de
   cobertura, que es una definición y no un modelo. **El hueco, declarado con
   la firma:** la dependencia con la elevación (Lund & Shanklin 1972, 1973) no
   se pudo abrir, así que **ninguna función acepta una elevación** —asertado
   por ausencia, como en `background.py`— y cada llamada avisa de que el valor
   es cenital y **cota superior** a cualquier otra elevación. Disponibilidad
   por pase desde una serie horaria interpolada linealmente (registrado): tres
   lecturas —media ponderada por permanencia (defecto), culminación, mínimo—
   que sobre un frente sintético difieren como mucho **0.023** en los cuatro
   pases del día de referencia (techo derivado 0.047), con la diferencia en el
   registro. Diversidad: ley exacta de dos Bernoulli con `ρ = exp(−d/L)` (0.60
   correlado, **0.7517** exacto, 0.84 independiente para `p = 0.6` a 500 km),
   cota de Fréchet como `DomainError` y no como recorte (0.2182 para 0.9 y
   0.3), y para N > 2 **solo cotas** porque las correlaciones por pares no fijan
   la ley; `L` sin defecto. Separación por cuerda en el elipsoide contra la
   haversine (V3), con la cota **derivada** `1 − a(1−e²)/R = 0.558 %` y no `f`.
   100 % de cobertura de líneas y ramas, 53 tests
6. ✅ `system/multi_ogs.py` — dos políticas porque son dos sistemas: `SUM`
   (cada estación cosecha; lo que consume el relé) y `BEST_AVAILABLE` (**un**
   terminal a bordo: los pases solapados chocan). El planificador es el
   **exacto** de *weighted interval scheduling*, `O(n log n)`, comprobado
   contra fuerza bruta sobre todos los subconjuntos (Hypothesis, 300
   instancias, con y sin hueco de reorientación) y con maximalidad (no
   seleccionado ⇔ choca con uno seleccionado); el greedy por clave está al
   lado con nombre y pierde en la instancia 4+4 contra 6. La disponibilidad
   multiplica una **esperanza**, y las columnas certificada y esperada viajan
   juntas. `minimum_gap_s` con defecto 0 (sin fuente, único valor no
   inventado); el conflicto del terminal de tierra se rechaza (alcance: un
   satélite). **Medido** con Castelldefels, Calar Alto (596 km) y la OGS de
   Tenerife (2214 km): SUM **1 052 607** bits, BEST_AVAILABLE **995 682** (4
   de 10 pases; los seis descartados valían 56 925, el **5.4 %**), **2.30
   veces** la estación sola; el greedy coincide en este día y eso se mide, no
   se supone. 100 % de cobertura de líneas y ramas, 55 tests
7. ✅ `system/relay.py` — nodo de confianza *store-and-forward*: el satélite
   anuncia `K_A ⊕ K_B` y tiene las dos claves en claro. Simulación cronológica
   por **fin** de pase (el bloque es el pase), almacén FIFO por lado, y la
   **identidad** que hay que saber antes que cualquier cifra: con almacén
   ilimitado el total es `min(ΣK_A, ΣK_B)` sea cual sea el orden (Hypothesis);
   el orden decide la **latencia** (edad del bit más antiguo y media ponderada,
   definidas) y lo **varado** a bordo. Seguridad por **cota de la unión** sobre
   los bloques consumidos de ambos lados, con rechazo si llega a uno.
   **Medido:** Castelldefels → Tenerife entrega 190 581 / 38 270 / 204 134 bits
   con latencias de 6 114 / 33 780 / 5 703 s (1.6 a **9.4 h**), 129 712 bits
   varados a medianoche, `4e-10`-seguro; contra Calar Alto, 47 108 bits a
   **59 s** y 9 817 a **39 822 s**, porque FIFO empareja el segundo pase con lo
   que quedaba del primero. **ISL fuera de alcance sin stub**: un segundo
   satélite es `DomainError` con la decisión de 2026-09-10 en el mensaje. Ver
   [ADR 0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md).
   100 % de cobertura de líneas y ramas, 39 tests

**Etapa 3 cerrada (2026-09-13):** los siete módulos, 434 tests en
`tests/system/`, 100 % de cobertura de líneas y ramas en los ocho ficheros del
paquete.

---

## Etapa 4 — `scenario/`: el escenario como dato ✅

Se podría hacer antes, pero es más honesto aquí: ya sabes exactamente qué parámetros
existen. **Este es el archivo más importante del proyecto** — define el contrato.
Se hizo aquí, con la física entera debajo, y por eso el esquema expresa **cada**
parámetro que la física acepta y valida cada uno con la cota del contenedor al que
alimenta: lo que valida, convierte. ADR de la etapa:
[0014](../docs/adr/0014-scenario-contract-and-provenance.md).

1. ✅ `scenario/models.py` — esquema Pydantic v2 (`extra="forbid"`, `frozen`,
   `allow_inf_nan=False`). Unidades del usuario en el nombre del campo, conversión
   a la unidad de física como propiedad/método (`latitude_rad`, `wavelength_m`,
   `gate_s`, `to_elements()`, `to_protocol()`, `grid()`), hecha aquí y en ningún
   otro sitio. Dos campos sin defecto y con test: `zenith_transmittance` (ADR 0009
   hueco 14) y `minimum_elevation_deg` (ADR 0011 §5). Una época ingenua se rechaza
   como el defecto del reloj de pared que fue. `protocol.name` se valida contra
   el registro; `"e91"` se rechaza con la lista de lo que hay. **Desviación
   medida:** la estación lleva el viento r.m.s. (21.0 m/s) y no el de superficie,
   porque Bufton convierte 2.3 m/s en 21.018 y ese 0.085 % movía el presupuesto de
   referencia 6.8e-5
2. ✅ `scenario/defaults.py` — `reference_castelldefels()` igual campo a campo al
   enlace de `tests/system/reference.py` (presupuestos idénticos a `1e-12`), y
   `ntanos_2021(0.75 | 1.3 | 2.3)` con lo que es del paper y lo que es elección
   dicho en cada línea; las coordenadas del §2 llevan las etiquetas lat/lon
   corregidas (el paper las imprime intercambiadas), y la inclinación impresa
   (97.4°) no es la heliosíncrona a 600 km (97.79°) y se usa la impresa
3. ✅ `scenario/io.py` — YAML/JSON por `safe_load`/`safe_dump`; todo fallo es un
   `ScenarioError` que lista cada campo malo con su ruta con puntos. Ida y vuelta
   exacta (Hypothesis, 40 escenarios, fechas y enums incluidos)
4. ✅ `scenario/hash.py` — JSON canónico (claves ordenadas, flotantes por `repr`,
   enums por valor, época con `Z`, sin `name`/`description`) y SHA-256. `0.1+0.2`
   ≠ `0.3`; `1` = `1.0`. Un digest clavado como guardia del contrato de
   serialización
5. ✅ `scenario/result.py` — `SimulationResult` y contenedores congelados sobre
   arrays de solo lectura; `to_dict`/`from_dict` (listas, NaN → `null`) y
   `to_manifest_and_arrays`/`from_manifest_and_arrays` (manifiesto + `.npz`);
   `Provenance.collect` (hash, versión, commit o `None`, versiones, semilla,
   hora)
6. ✅ `scenarios/*.yaml` — cinco ficheros comentados y comprobados iguales a sus
   constructores: referencia, tres de Ntanos 2021, y un TLE real de la ISS
   (CelesTrak, 2026-09-13) con las tres etapas opcionales activadas

**Hecho:** 202 tests, 100 % de cobertura de líneas y ramas, ruff/mypy limpios.
Lo que el motor recibe de aquí no lleva ni un grado.

---

## Etapa 5 — `engine/`: el orquestador ✅

Lo que hoy está enterrado en un handler HTTP. Sin dependencias web. Decisiones en
el [ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md).

1. ✅ `engine/pipeline.py` — escenario → órbita → geometría → canal → QKD → sistema → resultado
2. ✅ `engine/cache.py` — caché de resultados por hash de escenario
3. ✅ `engine/parallel.py` — paralelismo por passes / estaciones / realizaciones MC
4. ✅ `engine/sweep.py` — barridos de parámetros como ciudadano de primera (las figuras del paper *son* barridos)
5. ✅ `engine/profiling.py` — tiempos por etapa dentro del propio resultado

**Hecho cuando:** `run(scenario) → result` funciona en una línea de Python y un
escenario de referencia reproduce números publicados (V2), no los de SimulCTTC.

**Lo que faltaba y se cerró el 2026-09-14:** la afirmación central del paquete —«el
motor no calcula nada que no calcularía una persona llamando a las funciones a
mano»— citaba `tests/e2e/test_reference_scenarios.py`, **que no existía**. Ahora
existe: 30 tests que comparan el resultado del motor con la cadena de
`tests/e2e/oracle.py` por igualdad **exacta** de coma flotante, etapa por etapa,
incluidas las tres opcionales (Monte Carlo, multi-estación, relé). De paso cerró
la discrepancia de **457 bits** entre las 432 985 bits del día de referencia que
cita la etapa 3 y las **433 442** que devuelve `run()`: es la altitud de la
estación entrando —o no— en la integral de turbulencia, y las dos cifras se
reproducen a la última cifra desde la misma cadena con un solo argumento
distinto. El número que se reporta es el del motor.

---

## Etapa 6 — `io/`: el mundo exterior, aislado ✅

Tarde a propósito: la física no debe depender de la red. Hasta aquí, todo con datos
sintéticos o de `data/`. Ahora también después: ningún módulo de `core`,
`orbits`, `channel`, `qkd`, `system` o `engine` importa `quoss.io`, y
`tests/io/test_cache.py::TestTheSuiteIsOffline` rompe `socket.socket` y ejecuta
todos los caminos del paquete con `fetch` falsos. Decisiones en el
[ADR 0015](../docs/adr/0015-external-data-isolation-and-snapshots.md).

1. ✅ `io/cache.py` — caché HTTP en disco, content-addressed por SHA-256 de la URL,
   TTL obligatorio y reloj inyectado (medido: 3599 s acierto, 3600 s fallo);
   `DataError` con URL y estado si falla la descarga; la copia caducada solo con
   `allow_stale=True` y `WARNING io.cache-stale-fallback`. `urllib.request`, sin
   dependencia nueva; es la única función del paquete que puede abrir un socket
2. ✅ `io/celestrak.py` — un TLE del API GP (`gp.php?CATNR=…&FORMAT=TLE`),
   validado por `orbits.tle.parse_tle` antes de existir; `TleRecord.data_version`
   = `"<catálogo>@<época JD>"`, que es lo que identifica un conjunto de elementos
   y lo que va a `Provenance.data_versions["tle"]`
3. ✅ `io/openmeteo.py` — cobertura horaria de nubes (`cloud_cover`, %) del archivo
   histórico de Open-Meteo (familia ERA5), como `TimeGrid` + fracción en [0, 1].
   Un `null` es `DataError`, no interpolación (sin cota, sin `DEGRADED`); la
   celda del reanálisis se registra como INFO con su distancia al punto pedido
   (7.2 km para Castelldefels); el API no nombra el modelo, así que el código
   tampoco
4. ✅ `io/snapshots.py` — `data/snapshots/<kind>/<name>.json` con manifiesto
   (URL, hora de descarga, SHA-256 del payload canónico, `data_version`, nota),
   hash comprobado al cargar, y regla `synthetic_*` ⇔ nota dice «synthetic».
   Se entregan dos **descargas reales** del 2026-09-13 (ISS, y 48 h de nubes
   sobre Castelldefels del 1-2 de enero de 2025); ninguna sintética
5. ✅ `io/export.py` — `export_result` → `manifest.json` (procedencia + lista de
   ficheros con SHA-256), `passes.csv`, `daily.csv`, `series_<estación>.csv`,
   `arrays.npz`, `result.json`; `"parquet"` por `pyarrow` (extra `quoss[export]`,
   `ConfigurationError` si falta). `manifest.json` + `arrays.npz` reconstruyen el
   `SimulationResult` real; flotantes por `repr`, NaN como celda vacía
6. ✅ `data/ogs.yaml` + `io/stations.py` — cuatro estaciones con `source` y
   `coordinates_precision` obligatorios (Castelldefels, OGS de ESA en Tenerife
   por la página del IAC, Matera y Graz por el ILRS); apertura `null` donde la
   fuente no la da, y `to_station_spec_kwargs()` la exige al escenario

**Hecho:** 197 tests, 100 % de cobertura de líneas y ramas. Pendiente de
empaquetado (no de esta etapa): `data/` se resuelve relativo al checkout; un wheel
instalado no lo lleva. Todo acepta `root`/`path` explícitos.

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

## Numeración de ADRs, y los dos reservados

Un ADR por decisión no obvia, numerado al escribirse y nunca renumerado. A
2026-09-14 hay **dieciséis**, del 0001 al 0016, y dos números **reservados** por
código que ya los cita:

| Nº | Etapa | Estado |
|---|---|---|
| 0001–0015 | 0–4, 6 | escritos |
| **0016** | 5 (`engine/`) | escrito el 2026-09-14, [aquí](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md) |
| **0019** | 3 + 5 (esquema de resultado) | escrito el 2026-09-14, [aquí](../docs/adr/0019-acquisition-in-the-result.md): Doppler y point-ahead en el resultado |
| **0017** | 7 (`viz/`) | **reservado**. `src/quoss/viz/plots.py` lo cita como `0017-publication-figures.md` para la decisión de los dos paneles contra el doble eje |
| **0018** | 8 (`validation/`) | **reservado**. `src/quoss/validation/__init__.py` lo cita como `0018-validation-is-a-table-not-a-badge.md` para la regla de que un estado de validación se **deriva** de los números y no se escribe a mano |

Las dos citas dicen en el propio código que el fichero está pendiente, porque
citar un fichero que no existe es la misma clase de afirmación sin cumplir que el
ADR 0016 corrige. Quien escriba la etapa 7 o la 8 usa **ese** número, no el
siguiente libre.

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

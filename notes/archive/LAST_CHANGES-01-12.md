# Archivo de `LAST_CHANGES.md` — §1 a §12

> **Qué es esto.** Entradas de la bitácora del proyecto, **íntegras y sin
> editar**, sacadas del camino de lectura obligatorio y no borradas. Están aquí
> porque `notes/LAST_CHANGES.md` llegó a 6 834 líneas y CLAUDE.md manda leerlo al
> empezar cada sesión: una bitácora que no cabe en la sesión que la tiene que
> leer deja de ser una bitácora y pasa a ser un archivo, y el efecto medido es
> que las sesiones leen las primeras pantallas y se saltan las entradas que
> describen el árbol de hoy.
>
> **La regla por la que una entrada llega aquí**, y no es «lo viejo fuera»: una
> entrada se archiva cuando **todo lo que carga peso en ella vive ya en otro
> sitio que se lee de verdad** — un ADR, un test, o un docstring. Si no, se
> migra primero y se archiva después. La comprobación que lo respalda está en
> `LAST_CHANGES.md` §41: de los **823 números distintos** de §1 a §35, **765 ya
> vivían** en `docs/adr/`, `src/` o `tests/`, y los 58 restantes se clasificaron
> uno a uno.
>
> **Lo que sigue valiendo de leer esto:** la prosa de *por qué* se decidió algo,
> y sobre todo las entradas que cuentan un error y su corrección. Un ADR dice lo
> que se decidió; estas entradas dicen qué se creía antes y qué lo cambió.
>
> Índice de una línea por entrada, con su cifra: [`../LAST_CHANGES.md`](../LAST_CHANGES.md).

---

**Etapa 2.1 (`orbits/`) y la auditoría que la precedió. 2026-07-31 a 2026-08-04.**

---

## 1. Estado

| | |
|---|---|
| Etapa cerrada | **1 — `core/`**, **2.1 — `orbits/`**, **2.2 — `channel/`** y **2.3 — `qkd/`** |
| En curso | **Etapa 3 — `system/`**, por sus dos primeros módulos: `passes.py` (§26) y `key_volume.py` (§27), que entre los dos cierran la decisión aplazada del ADR 0010 y hacen de la cota finite-key el **defecto activo** del proyecto. Quedan los cinco de la lista: `monte_carlo.py` (la dispersión entre pases, que es lo que estas cifras **no** dicen), `correlated_fading.py`, `pcflos.py`, `multi_ogs.py` y `relay.py`. La 2.3 cerró con **tres** módulos y no con seis: `base.py` (§23), `bb84.py` (§24) y `finite_key.py` (§25) — **E91, CV-QKD, MDI-QKD y TF-QKD se retiraron del roadmap el 2026-09-12**, el alcance es BB84 con pulsos coherentes débiles y decoy, y el punto de extensión es `QkdProtocol` + `ProtocolRegistry`, no una lista de ficheros pendientes. La política de citas ([ADR 0009](../docs/adr/0009-citation-policy.md)) sigue en **dieciséis huecos declarados y ninguno rellenado**: esta etapa no abrió ninguno nuevo ni cerró ninguno, y la transmitancia cenital sigue siendo el que hace de las cifras de §27 una cota superior sobre la atmósfera y una afirmación exacta sobre todo lo demás |
| Física implementada | Marcos y escalas de tiempo · dos cuerpos · gravedad zonal J2/J3/J4 y teoría secular de J2 · propagación sobre una rejilla temporal, con época y método explícitos · **el tipo de elemento (osculador/medio) como parte del tipo, no como aviso** · **parseo de TLE y propagación SGP4**, con época propia y sin construir jamás un `ClassicalElements` medio · **ángulos de visión, distancia oblicua, velocidad de rango y point-ahead** desde una `Trajectory` en TEME · Walker-Delta, SSO y traza repetida (escrito, aparcado) · **perfil `C_n²(h)` y refracción · escintilación, promediado de apertura, `r0` y ángulo isoplanático · divergencia, acoplamiento geométrico y vaivén del haz · desvanecimiento por jitter de apuntado, como distribución · radiancia de cielo, fondo y puerta temporal · cadena de eficiencia, cuentas oscuras, afterpulsing y tiempo muerto · presupuesto de enlace y de ruido completos, con el cuantil conjunto de los dos desvanecimientos en forma cerrada** · **la frontera canal→protocolo (`LinkConditions` → `KeyRate`), BB84 con pulsos coherentes débiles y decoy vacío+débil con las cotas de Ma et al., y la longitud de clave finite-key componible de Lim et al. sobre un bloque** · **segmentación de pases contra una máscara de elevación, con los bordes y la culminación refinados fuera de la rejilla, y la integral sobre el pase → clave por pase y por día con la cota finita aplicada al bloque correcto y el `eps` del día compuesto** |
| Novedad de esta entrada | **`system/passes.py`** (§26) y **`system/key_volume.py`** (§27), y con ellos **la cota finite-key como defecto del proyecto**. En un día del enlace de referencia la integral asintótica reclama **3.78 Mbit** y la cota finita certifica **0.43 Mbit**, el **11.5 %** — y **dos de los cuatro pases no certifican nada** donde el asintótico reclama 320 y 199 kbit, así que el error no es un factor sino algo **ilimitado** en los pases bajos. **El hallazgo que solo esta etapa ve:** la máscara de elevación tiene **óptimo interior cerca de 8°** — la columna asintótica es monótona porque el recorte a cero por muestra la protege, la finita no, y bajar de 8° a 2° compra un 71 % más de segundos y destruye el **6.0 %** de la clave. **Y el bloque es el pase:** un bloque por muestra da **cero bits del día entero** |
| Novedad de la entrada anterior | **`qkd/finite_key.py`** (§25), y con él **la Etapa 2.3 queda cerrada**. Entra un **bloque** de cuentas acumuladas y sale una **longitud en bits**, no una tasa con un factor: en el enlace de referencia a cenit con el reparto 16:1:4, un bloque de 1e10 pulsos —cien segundos de una fuente de 100 MHz— certifica **1.1387e-05 bits por pulso** contra los **6.0239e-05** del límite asintótico del mismo protocolo, el **18.9 %**; a 1e9 pulsos, nada. **El hallazgo que solo este módulo ve:** asintóticamente los pulsos decoy son coste puro y su fracción óptima es cero, pero con un bloque de pase el óptimo está **cerca del 50 %** y vale un factor **3.4**, porque la desviación de Hoeffding la comparten las tres intensidades |
| Novedad de dos entradas atrás | **`qkd/bb84.py`** (§24). Se usa el rendimiento **exacto** de Ma et al. Ec. (7) —que **es** `click_probability`— y no su aproximación Ec. (10), que por encima de **7.152 cuentas por puerta devuelve una ganancia mayor que uno**; el QBER se escribe como **mezcla** para que `E ≤ ½` se cumpla en coma flotante, cosa que el numerador publicado no hace a partir de **3.912 cuentas por puerta**. **La intuición corregida:** la cota decoy no falla por pérdida —de η = 1 a 1e-08 sigue positiva— sino por **intensidad**, por encima de µ = 3.72 |
| Novedad de tres entradas atrás | **`qkd/base.py`** (§23). La frontera, sin física dentro. *Una media no es una probabilidad*: leer las cuentas por puerta de `NoiseBudget` como `Y_0` sobreestima **3.58 %** en el telescopio de 2.3 m y **0.38 %** en el de 0.75 m bajo el día claro de Ntanos et al.; y *la transmitancia ya lleva el receptor dentro*, así que hay **un** campo de transmitancia y **ninguno** de eficiencia, y el doble conteo de 6.36 dB de §22 no tiene por dónde entrar |
| Novedad de cuatro entradas atrás | **`channel/link_budget.py`** (§22), que cerró la Etapa 2.2. Sumar dos cuantiles al 1 % **no da un presupuesto al 1 %**: el cuantil conjunto exacto son **1.668 dB** contra los **2.312 dB** de la suma publicada — un outage real del **0.066 %**, quince veces más estricto que la etiqueta. Y los 4.259 dB que le faltaban al total de 20 dB de Ntanos et al. no estaban en la atmósfera sino en el **transmisor**: truncar la gaussiana en la apertura cuesta **3.352 dB** |

Verificación ejecutada **el 2026-09-13, con los dos primeros módulos de
`system/` en el árbol** (estos números sí se han vuelto a correr, por la misma
regla que costó los «219 km» de §14.1):

```bash
uv run ruff check .          # All checks passed!
uv run ruff format --check . # 65 files already formatted
uv run mypy                  # Success: no issues found in 65 source files
uv run pytest                # 2237 passed in 36.60s
uv run pytest --cov          # 99 % global (3487 sentencias, 796 ramas, 6 sin cubrir)
```

Cobertura de `system/`: los dos módulos al **100 %** de líneas y de ramas —
`passes` 284 sentencias, `key_volume` 227—. Cobertura de `qkd/`: los tres
módulos al **100 %** —`base` 200, `bb84` 184, `finite_key` 396—. Cobertura de
`channel/`: los siete módulos —`atmosphere`, `turbulence`, `beam`, `pointing`,
`background`, `detector`, `link_budget`— y el compartido `_validation`, también
al **100 %** con ramas.

Las 6 sentencias sin cubrir del total están todas fuera de `system/`, de `qkd/` y
de `channel/`: cuatro en `orbits/constellations.py` (que está aparcado), una en
`core/rng.py` y una en `core/types.py`. Eran ocho en la entrada anterior, y han
bajado a seis **sin que nadie escribiera un test para ellas**, que es un dato
sobre la etapa y no sobre la cobertura: las dos que se cerraron son el cuerpo de
`TimeGrid.is_uniform` para una rejilla de tres muestras o más y
`TimeGrid.__repr__`, y se cerraron porque `passes.py` es el primer módulo del
proyecto que de verdad construye rejillas **no uniformes** (el vértice parabólico
está escrito para espaciado desigual y hay un test que lo ejercita) y el primero
cuyo `__repr__` embebe el de la rejilla. Comprobado corriendo la suite sin
`tests/system`: ahí `core/types.py` se queda en tres sin cubrir, las líneas 350 y
389-390. Que el total suba de 2974 a 3487 sentencias y las sin cubrir bajen de 8
a 6 es lo que importa: las 513 sentencias nuevas entraron cubiertas.

Cobertura por módulo de `orbits/`: `frames`, `kepler`, `perturbations`,
`propagator`, `geometry`, `tle` y `_validation` al **100 %**, ramas incluidas.
`constellations.py` se queda en **96 %** — las cuatro sentencias sin cubrir son
las ramas de fallo de `brentq` en la traza repetida, y quedan así a propósito
porque el módulo está aparcado.

La suite está en **35 s** (53 s con `--cov`, que instrumenta cada línea). Los 159
tests nuevos de `system/` añaden **1.6 s**, y no porque sean triviales: la
geometría del día de referencia —86 401 muestras de propagación más ángulos de
visión— está memoizada sobre `(paso, duración)` en `tests/system/reference.py`,
que es lo que hace asequible el barrido de máscaras (nueve pipelines completos) y
el de resoluciones (una docena de propagaciones). **Ninguno de los tests de esta
etapa está marcado `slow`**, y eso es deliberado: la primera versión marcó así los
siete del barrido de resolución, se midieron en 0.7 s, y una etiqueta que reclama
un coste que no existe solo consigue esconder siete mediciones de un `-m "not
slow"`. Los únicos `slow` del proyecto siguen siendo los tres de la Fig. 1 de Lim
et al., que optimizan cinco parámetros por punto y cuestan 7 s; todo el coste base
siguen siendo las integraciones DOP853, que son el oráculo de `perturbations.py` y
no tienen forma barata.

---

## 2. La decisión que bloqueaba la etapa: el oráculo ya no es SimulCTTC

Era **el** pendiente bloqueante de la etapa 1. Se resolvió invirtiéndolo: el
roadmap decía tres veces «SimulCTTC es el oráculo», y eso era falso. Leyendo el
código viejo aparecieron, en unos minutos:

| Sitio | Qué hace | Error |
|---|---|---|
| `propagation.py:180` `ecef_to_latlon` | latitud **geocéntrica** vía `atan2(z, hypot(x,y))`; `alt = \|r\| − R_eq` | hasta **0.19°** en latitud, **−21.4 km** de altitud en el polo |
| `propagation.py:190` `ecef_from_latlon` | estaciones sobre una **esfera** de radio `R_eq` | desplazadas hasta ~21 km → sesgo directo en elevación y slant range |
| `propagation.py:120` J3 «secular» | los zonales **impares no tienen término secular de primer orden**; su propio docstring lo admite y aun así lo mete como tasa | física incorrecta |
| `propagation.py:238` | `datetime.utcnow()` por defecto + `except ValueError: pass` al parsear la época | run irreproducible + degradación silenciosa |
| `propagation.py:64` | `if a <= 0: return SecularRates(0,0,0,0)` | ceros plausibles en vez de fallo |

Congelar esa salida como golden test habría **canonizado los bugs**.

### El protocolo que lo sustituye

Cuatro niveles, documentados en [`tests/golden/README.md`](../tests/golden/README.md):

| Nivel | Qué | Prueba | En CI |
|---|---|---|---|
| **V1** | invariantes, property-based, sin datos externos | consistencia interna | sí |
| **V2** | valores publicados, con su cita al lado | **corrección absoluta** | sí |
| **V3** | implementación independiente, congelada con manifest | corrección en régimen amplio | sí (contra el fichero) |
| **V4** | snapshot de la salida propia | que un refactor no cambió nada. **No es validación** | sí |

**La regla que importa:** V4 no es validación. Cualquier cosa que se reporte como
validada tiene que trazar a V2 o V3. SimulCTTC baja a *diff informativo no
bloqueante*.

### Los oráculos, verificados como disponibles

- **`sgp4` de PyPI trae los datos de verificación oficiales de Vallado**:
  `SGP4-VER.TLE` (8.6 KB) y `tcppver.out` (140 KB), de AIAA 2006-6753. Su versión
  Python pura concuerda con la C++ de referencia a **0.1 mm**. Es decir: la
  validación de SGP4 llega gratis con una dependencia que había que añadir igual.
- **astropy/ERFA** para marcos, GMST y geodesia (exacto al mm). Ya en uso.
- **GMAT** (NASA, libre, con su V&V hecho contra STK y FreeFlyer) u **Orekit**
  para J2/J4 y look angles. Pendiente, para `perturbations.py` y `geometry.py`.
- **Ejemplos numéricos de Vallado** (Kepler, COE↔RV, GMST, az/el). Son V2, el
  nivel más fuerte. **No están** en `data/` porque hay que transcribirlos del
  libro, y **inventar números plausibles y etiquetarlos «publicados» sería peor
  que no tener V2**. El hueco está escrito en el README, no tapado.

### Cómo funciona en la práctica

```
tests/golden/
├── README.md                    # los cuatro niveles y las reglas
├── data/frames_reference.json   # 13 fechas + 13 GMST + 12 sitios + 16 estados TEME
└── generators/gen_frames_reference.py   # a mano, nunca en CI
```

El generador **no importa `quoss`** (un oráculo que importa el código bajo test es
un espejo), y `astropy` vive en un grupo de dependencias **no** por defecto
(`uv run --group reference …`), así que CI sigue offline y ligero.

---

## 3. Lo que el protocolo cazó en `frames.py`

Justifica el protocolo mejor que cualquier argumento:

1. **`calendar_to_jd` estaba mal por un día.** La expresión de Vallado Alg. 14 usa
   `int(7·(y + int((m+9)/12))/4)`, que es la regla de bisiestos **juliana** («cada
   cuatro años»), así que falla al cruzar un año secular no bisiesto. Medida
   contra astropy: exacta solo entre **1900-03-01 y 2100-02-28**, y ±1 día fuera.
   Sustituida por **Fliegel–Van Flandern**, exacta en todo el calendario
   gregoriano. Hay un test explícito por año secular (1900, 2000, 2024, 2025, 2100).

2. **El presupuesto de error de marcos no era el que había escrito.** Medí 178 m
   de discrepancia contra astropy donde esperaba ~15 m. Al descomponerlo: es
   **DUT1**, no movimiento polar. Rotando por GMST(UT1) el residuo cae a **14.4 m**
   — y eso sí es movimiento polar. La tabla del docstring ahora lleva números
   medidos, y el test los mantiene honestos.

3. **Un caso de referencia caía en un segundo intercalar.** En cualquier momento
   del 2015-06-30, las dos rutas de DUT1 de astropy (`get_delta_ut1_utc()` y el
   UT1 que usa `teme_to_itrs_mat`) discrepan — 0.5 s a mediodía, 1 s a las
   23:59:59 — porque una interpola a través del salto. Ese caso medía contabilidad
   de segundos intercalares, no la rotación bajo test. Sustituido por 2015-03-15
   (DUT1 ≈ −0.55 s, ambas rutas de acuerdo a 1e-5 s). **No se relajó la tolerancia:
   se quitó una entrada fuera de alcance y se documentó por qué.**

4. **Dos afirmaciones mías en comentarios eran falsas y los tests las tumbaron:**
   la iteración geodésica converge en **7** pasadas, no en 6 (ratio medido 4.7e-3);
   y el eje Norte del ENU **no** es exactamente cero al moverse en longitud —
   la cuerda entre dos puntos de un paralelo deja un término de segundo orden
   `sin(lat)·ρ·Δlon²/2`. Es geometría, no error, así que el test acota la razón y
   además comprueba la fórmula del término.

5. **Una rama de fallo habría lanzado `NameError`.** Si `_GEODETIC_MAX_ITER` fuese
   0, el `else` del `for` leería una variable sin asignar en vez de reportar el
   último desplazamiento. Inicializada a `inf`, y hay un test que la ejerce.

---

## 4. Lo que el V2 de Vallado cazó en `kepler.py`

El hueco que `tests/golden/README.md` declaraba abierto —«los ejemplos resueltos
de Vallado no están, porque hay que transcribirlos del libro»— está cerrado para
la ecuación de Kepler y para COE↔RV. Son los **Ejemplos 2-1, 2-5 y 2-6** de la
4.ª edición, transcritos con su página y viviendo junto a su cita en
`tests/orbits/test_kepler.py`, no en `data/`: un valor V2 es un número que un
lector puede contrastar contra el libro sin ejecutar un generador.

Transcribirlos encontró tres cosas, y ninguna se tapó con una tolerancia:

1. **La inclinación del Ejemplo 2-5 no cuadra con su propio vector de estado.**
   El `r`, `v` publicado da **87.86913°**; el libro imprime **87.870°**. La
   diferencia, 0.00087°, es 1.7 veces el medio dígito que tres decimales
   permiten, y es la **única** magnitud del ejemplo que excede su propio
   redondeo — `p`, `a`, `e`, Ω, ω y ν caen todas dentro. Está anotada con su
   número en un test que la afirma explícitamente. Ensanchar el límite hasta que
   pasara habría convertido un dato V2 en un adorno.

   Que el error está en el dígito impreso y no en nuestro cálculo lo dice el
   propio ejemplo: los seis elementos extraídos reconstruyen el estado publicado
   a menos de **1 nm**, así que la inclinación es consistente con todo lo demás.

2. **Los Ejemplos 2-5 y 2-6 no son un viaje de ida y vuelta**, y tratarlos como
   tal habría exigido una tolerancia lo bastante floja como para esconder un
   error real. Los elementos de entrada del 2-6 son los del 2-5 redondeados a dos
   decimales; esa caja de redondeo admite **±1.3 km** de posición. Lo que el 2-6
   licencia de verdad son 1.3 km; lo que se mide son **25 m**. Se asertan las dos
   por separado, porque solo la primera es una afirmación V2 y la segunda es una
   guarda de regresión.

   El estado perifocal intermedio, que depende solo de `p`, `e` y ν, sí cuadra a
   **0.1 m** — y eso localiza los 25 m en la rotación, donde el libro arrastra
   menos cifras de las que imprime. Aserta las etapas intermedias que el libro
   publica: es lo que convierte «discrepa» en «discrepa aquí».

3. **El valor `u` de la transcripción era una errata del propio libro, ya
   resuelta.** La fuente daba `u = 145.60549°` como argumento de latitud del
   2-5. Al no poder reproducirlo, quedó fuera de los tests; la entrada anterior
   registraba «no verificable sin página escaneada».

   La página escaneada (Vallado, pág. 116) confirma lo publicado y además
   revela que **el error está en el propio libro**, en dos capas:

   1. **Typo en `|r|`**: el libro usa `|r| = 11456.67 km` en la sustitución,
      cuando el valor correcto calculado previamente en el mismo ejemplo es
      `11456.57 km` (transposición de dígitos, 57 → 67).
   2. **El resultado tampoco cuadra con sus propios operandos erróneos**: evaluando
      la expresión impresa con `|r| = 11456.67` se obtiene `145.7194°`, no
      `145.60549°`. No existe ninguna definición de `u` que recupere el número
      impreso.

   El valor correcto, calculado de `r` y `v` con doble precisión, es
   `u = 145.720087380597°`, confirmado por dos rutas independientes:
   - Fórmula vectorial: `cos u = (n·r)/(|n||r|)` → `145.720087°`
   - Suma de elementos: `ω + ν = 53.384931° + 92.335157° = 145.720087°`

   `u = 145.60549°` queda registrado como **errata documentada** de Vallado
   4.ª ed. El test `test_argument_of_latitude_errata` afirma el valor correcto
   por ambas rutas.

   **Revisado en esta entrada, y reforzado.** La aserción sobre la capa 1 era
   débil: comprobaba que `|145.7194° − 145.7201°| < 1e-3`, lo que habría pasado
   con cualquier número en un intervalo de ±0.001° y no demostraba nada. Ahora el
   test **reproduce la aritmética de la página**: evalúa `arccos(n·r/(|n||r|))`
   con los operandos tal como el libro los imprime — `|n| = 66374.17`,
   `|r| = 11456.67`, y las componentes del nodo redondeadas a un decimal — y
   obtiene `145.7193794974°`, coincidiendo a **1e-9 grados** con la constante
   transcrita. Eso es lo que localiza el error en vez de solo registrarlo: prueba
   que la fórmula está bien transcrita, con lo que el único elemento que no se
   explica es el **resultado impreso**.

   Las dos capas quedan además cuantificadas y comparadas entre sí: el typo de
   `|r|` vale **7.1e-4 grados**, mientras que el hueco hasta el número impreso es
   **0.1146 grados** — 160 veces mayor. La transposición 57→67 no puede explicar
   lo impreso, y nada más en la página tampoco: recuperar `145.60549°` exigiría
   `|r| = 11472.24 km` o `|n| = 66464.9`, que no son transposiciones de nada de
   lo que la página imprime.

   Y una corrección de documentación, del mismo tipo que las de §3: el docstring
   de `VALLADO_2_5_EXPECTED` afirmaba que «dos ángulos auxiliares (longitud del
   periapsis, longitud verdadera) **están asertados**». No lo estaban — no existe
   ningún test que los toque. Corregido para decir la verdad, y dejando anotados
   los valores que nuestros elementos implican (281.2832° y 13.6183°) por si la
   página escaneada los imprime: sería un par V2 gratis.

   **Cerrado después: el V2 validaba el test, no el código.** Queda un hueco
   sutil en lo de arriba, y conviene decir en qué consistía porque es un patrón
   que se puede repetir en cualquier módulo.

   El argumento de latitud `u` es «cuánto ha avanzado el satélite a lo largo de
   su órbita desde que cruzó el ecuador hacia el norte», y vale `ω + ν`. Existe
   en el código como propiedad, `ClassicalElements.argument_of_latitude_rad`.
   Pero `test_argument_of_latitude_errata` **no la llamaba**: leía `coe.argp_rad`
   y `coe.true_anomaly_rad` y los sumaba a mano dentro del test.

   El test era correcto y demostraba lo que decía —que el número impreso en el
   libro está mal— pero lo demostraba sobre una suma escrita en el fichero de
   test. Es decir: el único dato V2 que el proyecto tiene para `u` no tocaba el
   código que los futuros llamantes (`constellations.py`, Brouwer-Lyddane) van a
   usar. Si alguien rompiera la propiedad, ningún test V2 se enteraría.

   Cerrado con dos tests:

   - `test_argument_of_latitude_property_carries_the_v2_value` (V2): pasa el
     estado publicado del 2-5 por `rv_to_coe` y asserta la **propiedad** contra
     `VALLADO_2_5_U_CORRECT_DEG`. Devuelve `145.720087380597°`, las doce cifras
     de la constante.
   - `test_argument_of_latitude_wraps_past_one_turn` (V1): el 2-5 no puede
     ejercitar el envuelto, porque su `ω + ν` son 145.7° y no llega a dar la
     vuelta. Los dos operandos sí vienen ya envueltos a `[0, 2π)`, así que su
     suma puede llegar a 720° y la propiedad es el único sitio donde se pliega.
     Caso construido: `ω = 310°`, `ν = 200°` → la suma cruda es **510°** y la
     propiedad da **150°** (residuo 2.8e-14°). Se corre sobre una pila de dos
     órbitas, una que envuelve y otra que no, porque el pliegue es vectorizado y
     una rama solo se notaría cuando los dos casos comparten llamada.

Y una cuarta, del lado del código: **el plan del solver de Kepler era más
complicado de lo necesario.** §9 de la entrada anterior decía «arranque de
Markley/Danby + Halley con iteraciones fijas». Al implementarlo resultó que el
método de Markley **ya es la solución completa**: una cúbica en forma cerrada más
una cascada de tres correcciones que comparten un solo par seno/coseno. No hay
bucle, así que no puede no converger, y el residuo medido no pasa de **1.4e-15
rad** para toda `e` hasta 0.9999.

---

## 5. Lo que la medición cazó en el propio roadmap

El roadmap pedía, literalmente: «J2/J4 secular analítico + integrador zonal
numérico (el numérico valida al analítico a **O(J2²)**)». La segunda mitad de esa
frase es falsa, y descubrirlo es el hallazgo de esta entrada.

**Por qué no se puede.** Una tasa secular es una afirmación sobre elementos
**medios**. `rv_to_coe` devuelve **osculadores**. La diferencia entre unos y otros
es ella misma O(J2) ≈ 1e-3 relativo — es decir, **mil veces mayor** que la
corrección de segundo orden (`J2²`, `J4` ≈ 1e-6) que se pretendía validar con
ella. Medir el segundo orden alimentando osculadores es como pesar una carta con
una báscula de baño.

No es una sospecha, está medido, y en tres pasos:

| Prueba | Resultado |
|---|---|
| Residuo de 1.er orden vs integración, con osculadores | 1.0e-4 … 2.6e-3 relativo, según inclinación — o sea O(J2), lo esperado |
| Una fórmula candidata de 2.º orden (`J2²` + `J4`) | **mejora en unos casos y empeora en otros** (i = 51.6°: 1.3e-3 → 5.2e-4; i = 98°: 1.0e-4 → **1.4e-3**). Justo lo que se ve cuando la corrección es menor que el ruido de su argumento |
| Promediar los elementos osculadores sobre las revoluciones para «obtener» medios | **no sirve**: el residuo se queda en O(J2) en las seis configuraciones probadas. Los elementos medios de Brouwer no son el promedio temporal de los osculadores |

La pieza que falta es la transformación de período corto de **Brouwer-Lyddane**,
que este proyecto no tiene y que el [ADR 0003](../docs/adr/0003-orbital-elements.md)
avisa de no fingir. Es, además, **la misma pieza** que `tle.py` va a necesitar
para no confundir los elementos medios de un TLE con los osculadores de
`kepler.py`. Cuando entre, los términos de segundo orden pasan a ser validables y
merecerá la pena añadirlos. Antes no: sería enviar código no ejercitado cuyo
propósito entero es una corrección más pequeña que el error de sus entradas — el
mismo argumento con el que el ADR 0003 descartó las variables universales.

### Lo que sí quedó validado, y con algo mejor que una cota

> El residuo relativo de las tasas de primer orden contra la integración numérica
> es **exactamente proporcional a J2**. Escalando J2 por 1, 1/2, 1/4 y 1/8, el
> cociente residuo/J2 se mantiene constante a **cuatro cifras significativas**
> (1.184 a i = 51.6°; 0.088–0.091 a i = 98°).

Esto separa las dos hipótesis que una cota sola no puede separar:

- si la fórmula es correcta y solo está truncada, el término despreciado es
  O(J2²) y el error **relativo** cae linealmente con J2 → es lo que se ve;
- si un coeficiente estuviera mal escrito, sería un error O(J2) dentro de una
  cantidad O(J2), y el error relativo **no se movería** al escalar J2.

Es el patrón de `TestFrameErrorBudget` aplicado a otra magnitud: no decir «se
parece», sino atribuir el residuo.

### J3: la trampa del roadmap, ahora medida en vez de afirmada

El aviso llevaba dos documentos escrito («los zonales impares no tienen término
secular de primer orden»; fue uno de los defectos de SimulCTTC). Ahora está
demostrado, y barato:

> La contribución de J3 a `dΩ/dt`, medida a ω = 0°, 90°, 180° y 270°, va como
> **sin ω**: se anula en 0° y 180°, y cambia de signo entre 90° y 270°
> (±3.2e-11 rad/s). Un término secular daría lo mismo en los cuatro.

Un término que depende de dónde esté el perigeo promedia a cero sobre un ciclo
apsidal. Y aunque no lo hiciera: en su máximo es **cuatro órdenes de magnitud**
menor que la tasa de J2 que tiene al lado.

La prueba se eligió así por coste. Demostrarlo integrando un ciclo apsidal
completo son ~1600 revoluciones; la prueba del signo son cuatro integraciones de
20 y tarda un segundo. Además, `secular_rates_j2` **no tiene ningún parámetro
donde meter un J3**, y hay un test que aserta esa forma de la API para que un
refactor no pueda reintroducir el peligro en silencio.

### Tres cosas más que aparecieron al escribir los tests

1. **El paso de la diferencia finita no estaba donde yo creía.** Para verificar
   que la aceleración es el gradiente del potencial, escribí «h = 1 km está cerca
   del óptimo» y lo puse en un comentario. Falso: el truncamiento cae como `h²` y
   la cancelación crece como `1/h`, y barriendo 9 posiciones con pasos de 300 m a
   3 m el peor caso toca fondo en ~1e-9 con **h = 30 m**. El paso de 1 km era
   **250 veces peor**. La constante ahora lleva el barrido en su docstring.
2. **Calcular el potencial perturbador restando dos potenciales tira nueve
   cifras.** `U_total − U_dos_cuerpos` son ~60 km²/s² sacados de dos números de
   ~6e4: la cancelación cuesta dos órdenes de magnitud de exactitud en el
   gradiente. Evaluando la suma zonal directamente no hay cancelación, y el mismo
   test pasa de acotar los armónicos al 0.1 % del total a acotarlos al 1e-8 de
   **sí mismos**.
3. **`solve_ivp` con un intervalo de longitud cero devuelve éxito y ningún
   punto.** Una muestra en la época habría dejado una fila del array sin
   inicializar — basura silenciosa, no un fallo. Se escribe directamente desde el
   estado inicial, que además es exacto. Lo destapó el test que pide `dt = 0`.

Y una cuarta, del lado del test y no del código: dos casos de prueba que escribí
con `e = 0.1` a 7078 km tienen el **perigeo dentro de la Tierra** (6370 km). La
guarda del modelo de fuerzas los rechazó, que es exactamente su trabajo.

---

## 6. La bandera osculador/medio — las tres subdecisiones (→ [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md))

No es un módulo nuevo: es un campo en `ClassicalElements` y dos `if`. Está aquí
porque cierra el pendiente más antiguo de la etapa y porque las tres cosas que
había que decidir para escribirla no eran obvias — la nota anterior las dejó
apuntadas precisamente para no resolverlas de pasada.

### Qué es la bandera, para quien llegue nuevo

Un satélite real no sigue una elipse: la Tierra está achatada y lo empuja fuera de
ella todo el rato. Así que «la órbita» son dos cosas distintas:

- **Osculadores**: la elipse que seguiría *desde este instante* si la Tierra se
  volviera de golpe una esfera. Es tangente a la trayectoria real y cambia
  continuamente. Es lo que devuelve `rv_to_coe`, porque un vector de estado no
  puede determinar otra cosa.
- **Medios**: esa misma órbita con el bamboleo rápido ya restado. No existe en
  ningún instante, pero es de lo que habla una tasa secular.

La diferencia es O(J2) ≈ una parte en mil. Sobre 7000 km, ~7 km — y la parte que
importa **crece**: **86 km por vuelta y 1290 km al día** en along-track para una
SSO de 700 km declarada en ν = 0, que en unidades de pase son ≈11.5 s de reloj
orbital por vuelta y ≈2.9 minutos al día. Un pase dura diez minutos. (Cifras
corregidas el 2026-08-04: las que estaban aquí eran 5.9 veces menores y nunca se
reprodujeron — ver §14.1.)

Ahora `ClassicalElements` lleva un `ElementType` igual que lleva su `Frame`, con
dos miembros: `OSCULATING` (el defecto) y `MEAN_BROUWER`.

### Subdecisión 1 — `coe_to_rv` rechaza los medios, y esa es la guarda grande

La guarda que parecía la natural es la otra: `secular_rates_j2` es quien necesita
elementos medios. Pero **los kilómetros se pierden en el sentido contrario**.
Alimentar la teoría secular con osculadores cuesta O(J2) *sobre la tasa*, que es
del tamaño del término que la teoría de primer orden ya descarta; convertir unos
medios a estado como si fueran osculadores es la tabla de arriba. Comprobar en un
solo sentido habría dejado abierto el agujero grande, así que se cierran los dos.

Coste para el código de hoy: **ninguno**. `rv_to_coe → coe_to_rv` sigue siendo
osculador en las dos puntas.

Lo que apareció al implementarlo, y no es evidente: `TWO_BODY` **no** le pasa a
`coe_to_rv` los elementos del llamante. Construye una pila aplanada de `S · n`
juegos y llama una vez. Si esa pila hubiera tomado el defecto `OSCULATING`, el
modo de dos cuerpos habría **blanqueado** unos elementos medios pasándolos por
delante de la única comprobación que existe — y ninguna aserción de forma se
habría enterado, porque la forma es correcta. La pila reenvía la etiqueta, y hay
un test parametrizado sobre `PropagationMethod` que lo fija: el día que entre
`J2_SECULAR_ANALYTIC` fallará, que es cuando hay que decidir su regla propia.

### Subdecisión 2 — dos miembros, y el segundo se llama `MEAN_BROUWER`

«Medio» no es una cosa, es una por teoría: los de un TLE son de Brouwer con Kozai
y constantes WGS-72; los que quiere `secular_rates_j2` son de Brouwer-Lyddane con
EGM96. Un enum de dos valores cuyo segundo se llamara `MEAN` los haría parecer
intercambiables, que es justo el error que la bandera existe para prevenir.

El argumento que desempata: **el miedo a quedarse en dos era «añadir un tercero
después toca a todos los llamantes», y ese miedo desaparece al nombrar el miembro
por su teoría.** Nadie puede haber escrito `MEAN`, así que `MEAN_KOZAI_SGP4` se
añade el día que algo lo produzca sin tocar un solo sitio.

Y no se añade hoy porque el ADR 0005 ya decidió que `tle.py` no construye un
`ClassicalElements`: SGP4 devuelve estado en TEME y los elementos de ese estado
son osculadores. Misma regla que el enum incompleto de la entrada anterior: un
miembro que ningún código puede producir es una etiqueta que solo invita a
ponerla a mano. Un test fija el conjunto exacto de miembros y aserta además que
**no existe** un `MEAN` a secas.

### Subdecisión 3 — `relabelled_as`, y por qué no `assume_mean=True`

`TestSecularRatesAgainstIntegration` alimenta osculadores a `secular_rates_j2`
**queriendo**: un mismo juego de seis números hace de condición inicial de la
integración (osculador, obligatoriamente) y de argumento de la teoría (medio), y
de esa tensión sale la medición que sostiene el módulo — que el residuo del primer
orden es exactamente proporcional a J2 (§5).

Con la bandera esos tests necesitaban una vía explícita:

| | `assume_mean=True` en la física | **`relabelled_as` en el contenedor (elegida)** |
|---|---|---|
| Dónde vive | en la API de física | en el objeto de datos |
| Quién lo alcanza | cualquiera, incluido un YAML | quien tiene los elementos y escribe la palabra |
| Tiene default | sí, forzosamente | no aplica |
| Qué dice el nombre | «supón» | «reetiquetado»: admite que no convierte |

`relabelled_as` devuelve un objeto nuevo con **los mismos números bit a bit**, y
hay un test que lo aserta campo por campo: si algún día creciera una conversión
detrás de ese nombre, falla — y debe fallar.

La distinción fina, que es la que hace que los tests sigan diciendo la verdad: los
que solo preguntan por lo que la fórmula calcula (un signo, un límite, la
inclinación crítica) **construyen** elementos medios (`_mean_elements`), porque
eso es lo que dicen ser y nada allí los convierte en un estado; solo los que
mienten a propósito reetiquetan. Dos ayudas distintas para dos afirmaciones
distintas.

### Lo que sigue sin existir, dicho en voz alta

**No hay conversión medio↔osculador.** Brouwer-Lyddane no está, y este ADR no la
finge: la bandera de hoy es una **puerta cerrada que marca dónde haría falta**, no
un paso más en una tubería. Los mensajes de error lo dicen —nombran la
transformación que falta en vez de apuntar a una función que el lector iría a
buscar y no encontraría— y esa sigue siendo la condición de entrada del modo
analítico y de los términos seculares de segundo orden.

---

## 7. `orbits/propagator.py` — las decisiones (→ [ADR 0005](../docs/adr/0005-propagation.md))

Este módulo **no añade física**: todo lo que calcula ya estaba en `kepler.py` y
en `perturbations.py`. Lo que añade es tiempo —una época y una rejilla— y las
cuatro decisiones que los módulos anteriores dejaron abiertas a propósito.

### La decisión de esta entrada: enviar el enum incompleto

`PropagationMethod` tiene **dos** miembros, `TWO_BODY` y `ZONAL_NUMERIC`. El
tercero que el roadmap pedía —propagador analítico de J2 sobre
`secular_rates_j2`— no está, y no es un olvido.

La razón está medida y ya estaba escrita en §12 de la entrada anterior: un
propagador analítico alimentado con los osculadores que devuelve `rv_to_coe`
comete un error que **crece**, ~86 km por vuelta en along-track, ~1290 km tras un
día para una SSO declarada en ν = 0. Y lo que importa no es el tamaño sino que sea
deriva: son **≈11.5 s de error de reloj orbital por vuelta, ≈2.9 minutos al día**.
Un pase dura ~10 minutos, así que en un día las ventanas de visibilidad ya están
corridas una fracción apreciable de un pase.

Las tres opciones eran:

| Opción | Qué pasa |
|---|---|
| Enviarlo documentando el error | Devuelve un array del tipo correcto con números plausibles y nada falla. **Es literalmente la degradación silenciosa que el README prohíbe** |
| Retrasar el módulo entero hasta tener Brouwer-Lyddane | Bloquea `geometry.py`, `constellations.py` y el primer enlace calculable de punta a punta, por una pieza que el modo de referencia no necesita |
| **Enviar el enum con dos miembros** | Un nombre ausente obliga a preguntar en el punto de llamada. Y el enum crece sin tocar a nadie: nadie puede depender de un miembro que nunca existió |

Se eligió la tercera, y la incompletitud está **asertada**, no confiada a que
alguien se acuerde:

- `test_the_enum_holds_exactly_the_implemented_modes` fija el conjunto de
  miembros. Añadir `J2_SECULAR_ANALYTIC` hace fallar el test, y ese fallo es el
  recordatorio de actualizar también el ADR y el docstring.
- `test_every_declared_member_actually_propagates` está **parametrizado sobre el
  enum**, así que un miembro añadido sin implementar falla al instante en vez de
  caer en una rama muerta.

### Los dos pendientes del módulo, resueltos

**Época.** Llega dentro del `TimeGrid`, que no se puede construir sin ella. Eso
convierte el defecto de SimulCTTC —`datetime.utcnow()` por defecto— en algo
irrepresentable en vez de documentado. Pero además **nada del módulo lee
`epoch_jd` numéricamente**: la física es función de segundos transcurridos, y la
fecha juliana se transporta intacta para que GMST y la geometría solar la tomen
de un solo sitio. Hay un test que aserta que dos rejillas que solo difieren en la
época devuelven estados **idénticos bit a bit** — y que avisará el día que entre
un modelo que sí dependa de tiempo absoluto.

`t_s` puede empezar donde sea, incluir el cero o no, y ser negativa: la
propagación sale de la época en las dos direcciones, que es lo que necesita una
época en mitad de la ventana (lo que da un TLE).

**Forma multi-satélite: `(S, n, 3)`, satellite-major, siempre 3-D.** La propuesta
anterior era no decidirlo en 2.1; se decide aquí porque `geometry.py` llega antes
que la etapa 3 y tendría que inventarse una forma provisional. El argumento que
desempata es de memoria, no de gusto: `traj.r_km[s]` es un bloque **contiguo**
`(n, 3)` con el tiempo primero, que es exactamente lo que ya consumen
`teme_to_itrf` y compañía; con `(n, S, 3)` la traza de un satélite es `r[:, s]`,
una vista con salto que cada llamada aguas abajo tendría que copiar. Un satélite
es `(1, n, 3)`, igual que una estación única es `(1, 3)` en `frames.py`: nadie
ramifica por forma.

### Lo que apareció al escribirlo

1. **El aplanado del modo analítico tiene una trampa que ninguna aserción de
   forma detecta.** `TWO_BODY` construye una sola pila de `S · n` juegos de
   elementos —`np.repeat` sobre los elementos, `np.tile` sobre los tiempos— y
   llama a `coe_to_rv` **una vez**. Intercambiar `repeat` y `tile` produce un
   array de la forma correcta, con los números correctos, **en las posiciones
   equivocadas**, y todas las comprobaciones de forma seguirían pasando. Lo que
   lo caza es comparar la rodaja de cada satélite contra ese satélite propagado
   solo, y así está escrito (`test_each_slice_equals_that_orbit_propagated_alone`,
   con igualdad exacta porque las dos rutas hacen la misma aritmética).
2. **Los dos modos se validan el uno al otro, en las dos direcciones.** Con todos
   los armónicos a cero son dos implementaciones independientes de la misma
   física —Kepler en forma cerrada contra DOP853— y coinciden a **13 µm sobre una
   revolución** (cota puesta en 1 mm, derivada del `atol` de 1 nm del integrador y
   sus ~250 pasos por vuelta, no ajustada). Con los armónicos puestos **tienen que
   discrepar**, y también eso se aserta contra una predicción calculada en el
   test: rotar el plano por `ΔΩ` desplaza `r·ΔΩ·sin i` = 460 km tras un día, y lo
   medido son **720 km** (1.56 veces), donde el exceso es la precesión apsidal más
   la diferencia entre el periodo kepleriano y el anomalístico.
3. **Un error de integración tenía que decir *qué* órbita.** El bucle sobre
   satélites reetiqueta `DomainError` y `ConvergenceError` con el índice: una
   constelación de sesenta no puede reportar «una órbita falló». La rama de
   `ConvergenceError` no es alcanzable físicamente —la guarda del modelo de
   fuerzas la caza antes— así que se ejercita con un stub que falla en la
   **segunda** llamada, lo que además demuestra que el índice sigue al bucle y no
   es un cero fijo. Mismo patrón que ya usaba `test_perturbations.py`.
4. **`Vec3Array` no vale para un array `(S, n, 3)`.** El alias documenta
   «`(n, 3)` con el tiempo primero», que **cada rodaja** cumple y el array apilado
   no. Los campos de `Trajectory` se anotan `FloatArray` con un comentario que lo
   dice: reclamar el alias justo donde es falso sería ponerlo mal en el sitio
   donde más se lee.

### Las decisiones, en tabla

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **Una sola función `propagate`, con `method` obligatorio y sin default** | Un default es una decisión de modelado tomada por el llamante sin que se dé cuenta. El método viaja en el resultado, y el escenario de la etapa 4 lo escribe como un campo del YAML | Alto |
| **`method` es palabra clave y hay un test sobre la firma** | La forma de la API es la salvaguarda; un refactor no puede ablandarla en silencio. Mismo movimiento que el test que aserta que `secular_rates_j2` no tiene dónde meter un J3 | Trivial |
| **La entrada son `ClassicalElements`, no un estado** | Es lo que escribe el escenario, lleva su `Frame` dentro, y es el tipo que exigirá el modo analítico cuando entre. Quien tenga un estado escribe `rv_to_coe`, exacto y greppable | Medio |
| **`tle.py` no entra por aquí** | Un TLE se propaga con SGP4, que devuelve estado en TEME. Construir un `ClassicalElements` con sus elementos medios es el error del que avisan tres documentos. Un `propagate_tle` aparte es más honesto que un miembro más del enum | Bajo |
| **Un `ZonalGravity` para los dos modos; `TWO_BODY` lee solo `mu`** | No es la sustitución silenciosa que `secular_rates_j2` rechaza: allí el nombre prometía J2 y el objeto ofrecía más, aquí `method` es obligatorio y el llamante ya declaró qué física quiere | Bajo |
| **`Trajectory` **no** guarda el modelo de gravedad** | Una trayectoria `TWO_BODY` no depende de los armónicos; guardarlos al lado afirmaría una dependencia que no existe. El modelo es del escenario, que es lo que la etapa 4 hashea | Bajo |
| **`Trajectory` no tiene `__len__`** | Tiene dos longitudes. `len(traj)` sería una moneda al aire en cada punto de llamada; hay `n_satellites` y `n_samples` | Trivial |
| **El bucle sobre satélites vive aquí** | `propagate_zonal` es de una órbita por diseño (una EDO no se difunde sobre condiciones iniciales). Esta es la capa que sabe cuántas órbitas hay, y es donde irá un pool de procesos | Bajo |
| **`DEFAULT_ZONAL_RTOL` / `DEFAULT_ZONAL_ATOL_KM` pasan a ser públicas** | `propagate` las reenvía, y una segunda copia del número en un segundo módulo es un número que se desincroniza. Los valores no cambian | Trivial |
| **Sin `DegradationLog`, otra vez** | Elegir modelo no es degradar: es lo que el llamante pidió, y queda registrado en el resultado. Regla del ADR 0002 sin excepción | — |

---

## 8. `orbits/perturbations.py` — las decisiones (→ [ADR 0004](../docs/adr/0004-zonal-perturbations.md))

**Una sola expresión de Legendre para toda la fuerza.** Derivando el potencial
zonal una vez, la regla de la cadena da una expresión válida para todo grado:

```
a_n = (mu J_n R^n / r^(n+2)) · { [(n+1)P_n(s) + s P_n'(s)] r̂ − P_n'(s) ẑ }
```

Expandida en `n = 2` es la fórmula cartesiana de J2 de siempre. La ventaja es de
superficie de error: J3 y J4 cuestan **un polinomio cada uno** en vez de tres
componentes transcritas cada uno. Nueve oportunidades de error de signo se
convierten en tres polinomios comprobables de un vistazo — y los tests comprueban
la forma general contra la cartesiana transcrita a mano, así que no se pierde la
referencia del libro.

**El integrador vive en el módulo, no en los tests.** Es el oráculo de la teoría
secular, y `tests/golden/README.md` ya cubre el caso de un oráculo V3 que no
necesita congelarse: SciPy es dependencia del núcleo, DOP853 es determinista con
su exactitud fijada por argumentos **explícitos** (`rtol`, `atol_km` son
parámetros con valores declarados, no defaults de biblioteca), y la comparación
se hace muy por encima de su propio error.

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`secular_rates_j2` no acepta un `ZonalGravity`** | Recibir un objeto con J3 y J4 y usar solo el J2 es sustituir el modelo en silencio. Como la omisión es una elección fija y no una decisión en runtime, por la regla del ADR 0002 no lleva `DegradationLog`: se resuelve en la firma. Quien tenga el objeto escribe `j2=gravity.j2`, y el cruce se encuentra con grep — igual que `km_to_m` | Bajo |
| **`ZonalGravity` lleva `mu`, radio y armónicos juntos** | Un armónico zonal no significa nada sin el radio de su expansión: cada término multiplica `(R/r)^n`. Mezclar armónicos de EGM96 con el radio de WGS-84 da un modelo que no es ninguno de los publicados. Irrepresentable en vez de documentado | Bajo |
| **Constante nueva `EGM96_RADIUS_EQUATORIAL_KM` = 6378.1363** | **No** es `WGS84_RADIUS_EQUATORIAL_KM` = 6378.137. La diferencia es 0.7 m y vale 2.2e-7 relativo en el término J2 — despreciable frente al truncamiento del modelo, y gratis de evitar. Tres radios, tres propósitos: geodesia WGS-84, gravedad EGM96, SGP4 WGS-72 | Trivial |
| **Un estado entra, una trayectoria sale** | Una EDO se integra por órbita; no hay pila de condiciones iniciales sobre la que difundir. Una constelación es un bucle, y el bucle pertenece a quien sabe paralelizarlo (`propagator.py`) | Medio |
| **La integración sale de la época en las dos direcciones** | Una época en mitad de la rejilla es lo que da un TLE. Resolverlo dentro cuesta diez líneas; dejarlo fuera cuesta una verruga en cada llamante | Bajo |
| **Rechazar posiciones dentro del radio de referencia** | La expansión armónica no converge ahí y un satélite no está ahí. Además caza el error de meter metros donde van kilómetros. La validación es **por evaluación**, no solo sobre el estado inicial: una órbita cuyo perigeo baja de la superficie solo se detecta cuando la integración llega | Bajo |
| **El detector de paso por el nodo vive en los tests** | Ahí es el mecanismo de medida, no una función pública. Sacarlo a `src/` habría hecho que el oráculo compartiera código con lo que mide | Bajo |
| **`CRITICAL_INCLINATION_RAD` como constante pública** | 63.4349°, donde `4 − 5 sin²i` se anula. Importa en dos direcciones: es donde se vuela una Molniya, y es donde una cota **relativa** sobre `argp_dot` deja de significar nada — el test de la tasa apsidal se mantiene lejos a propósito | Trivial |

### El tercer duplicado se cortó

`_as_1d` y `_as_vec3` estaban **byte a byte idénticos** en `frames.py` y
`kepler.py`. Al necesitarlos por tercera vez, se extrajeron a
`orbits/_validation.py` y los dos módulos anteriores ahora importan de ahí. Los
mensajes de error se movieron sin tocar una coma, y los 448 tests que ya existían
lo confirmaron sin cambios.

Lo que **no** se unificó: `frames._broadcast_against` y
`kepler._broadcast_to_common` difieren en forma y en lo que aconsejan sus
mensajes. Fundirlos habría dado un helper que dice menos que cualquiera de los
dos.

---

## 9. `orbits/frames.py` — las decisiones (→ [ADR 0002](../docs/adr/0002-frames-and-time-scales.md))

**Un solo marco inercial: TEME.** Es lo que devuelve SGP4, y SGP4 no es opcional.
Convertir a GCRF y volver en cada propagación añadiría error, no exactitud.

**Un solo giro, por GMST (IAU-82), hasta el marco fijo.** Estrictamente eso es PEF;
se trata como ITRF/ECEF. Presupuesto **medido**, no afirmado:

| Aproximación | Error de posición | Efecto en el enlace |
|---|---|---|
| Movimiento polar ignorado | **14.4 m** (peor medido) | ~14 µrad a 1000 km |
| UT1 ≡ UTC (\|DUT1\| ≤ 0.9 s) | ≤ 460 m (**274 m** medido) | ≤ 0.03° en elevación |
| GMST IAU-82 vs IAU-2006 | ~2 m (0.06″, 2000–2030) | despreciable |

`TestFrameErrorBudget` **descompone** el residuo en vez de esconderlo en una
tolerancia holgada: al restaurar UT1, lo que queda es exactamente el movimiento
polar que omitimos a propósito. El test no dice «se parece»: dice que el giro es
correcto. Y hay un test que propaga el peor DUT1 hasta un **ángulo de elevación**,
que es la magnitud que le importa al link budget.

`Frame` es un `StrEnum` con `TEME`/`ITRF`/`ENU`/`GCRF`. **`GCRF` se declara y no se
implementa**: es el gancho para que, si algún día entra la reducción completa,
todo array venga ya etiquetado y los puntos de conversión se encuentren con grep.

### La regla de firma para toda la etapa 2 (era decisión diferida)

> **Una función de física recibe un `DegradationLog` solo si puede decidir en
> tiempo de ejecución calcular algo distinto de lo que su nombre promete.**

Ninguna función de `frames.py` lo recibe: sus tres aproximaciones son elecciones
de modelo fijas para todo el run, y registrarlas por llamada emitiría una entrada
por muestra temporal. Entrada mala = **error** (`DomainError`), no degradación.

### Otras decisiones

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **Geodésico siempre, WGS-84** | Es el bug de SimulCTTC. Hay tests que fijan numéricamente la diferencia geodésica/geocéntrica (0.1924° a 45°) y el error esférico en el polo (−21.385 km), para que nadie la reintroduzca por simplicidad aparente | Alto |
| **GMST en segundos de tiempo, no grados** | Una vuelta completa son exactamente `SECONDS_PER_DAY` segundos de tiempo, así que pasar a radianes es contar vueltas, no convertir grados. Respeta el guarda de `deg2rad` del ADR 0001 y usa la misma formulación que `erfa.gmst82` | Trivial |
| **`enu_from_itrf` toma un *vector*, no una posición** | Obliga a que la resta `r_sat − r_estación` quede en el llamante. Rotar una posición como si fuera un offset topocéntrico es un error silencioso | Bajo |
| **Iteración de punto fijo para geodésico, no forma cerrada** | Vermeille/Heikkinen son exactas pero fáciles de transcribir mal. La iteración converge en 7 pasadas a 1e-14, es trivialmente vectorizable, y su corrección es evidente | Trivial |
| **`_as_1d` / `_as_vec3` validan en cada función pública** | Una función que confía en sus entradas empuja el error a donde aparece el `nan`, que nunca es donde se cometió | Bajo |
| **Escalares admitidos para lat/lon de estación** | Una estación es un *parámetro*, no una serie temporal. Los arrays de tiempo sí exigen forma `(n, 3)` | Bajo |
| **Salida siempre 2-D `(n, 3)`** | Un sitio único es `(1, 3)`, así ningún llamante ramifica por forma | Bajo |
| **Tolerancias derivadas, no ajustadas** | P. ej. el jitter admitido en el paso de GMST se calcula de `np.spacing(JD_J2000)`, no de lo que el código da hoy. Una tolerancia ajustada al resultado actual no puede fallar nunca | Alto (es el valor de la suite) |

---

## 10. `orbits/kepler.py` — las decisiones (→ [ADR 0003](../docs/adr/0003-orbital-elements.md))

**Solo órbitas elípticas, `0 ≤ e < 1`.** La formulación por variables universales
cubriría las cuatro cónicas, pero **nada en este proyecto la validaría**: no hay
un caso de prueba hiperbólico con significado físico en un simulador de
satélites. Código no ejercitado es código que no funciona.

**Kepler en forma cerrada, sin bucle.** Markley 1995. Residuo medido ≤ 1.4e-15
rad sobre 20 001 puntos por excentricidad, para toda `e` hasta 0.9999, y el mismo
coste para una órbita circular que para `e = 0.99` — lo que importa dentro de un
barrido. Aun así la función **comprueba su propio residuo** en cada llamada: no
es un criterio de convergencia sino una post-condición, y hay un test que la
ejerce apretando el umbral por debajo del suelo de máquina, para que la rama
exista de verdad.

El matiz que hay que decir en voz alta: el residuo es absoluto en anomalía
*media*, y `dM/dE = 1 − e·cos E`. Cerca del periapsis de una órbita muy
excéntrica esa derivada se hunde, así que el error en `E` es el residuo dividido
por `1 − e` (≈1e-11 rad a `e = 0.9999`). A las excentricidades de LEO es 1e-15.

**Los ángulos indefinidos se pliegan, no se anulan.** Una órbita circular no
tiene ω; una ecuatorial no tiene Ω. Las dos ocurren en escenarios reales y las
dos hacen que la fórmula clásica divida por cero. En vez de devolver `nan` —que
viaja hasta la primera figura y allí ya nadie sabe de dónde salió— el ángulo
indefinido se mete en el siguiente que sí lo está, y el pliegue se reporta con
`is_circular` / `is_equatorial`.

El pliegue es **sin pérdida para el estado**: en la posición y la velocidad solo
entran sumas como `ω + ν`, así que `coe_to_rv` reconstruye los vectores exactos
en los cuatro casos degenerados — verificado a 15 nm sobre una pila que los
mezcla con órbitas ordinarias, que es lo que ejercita las máscaras vectorizadas.

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`p` como elemento primario, `a` derivado** | Sale directo de `h²/µ` sin pasar por la energía; es lo que recibe el Algorithm 10, que es el caso publicado que valida el módulo; y se mantiene finito si algún día entra `e → 1` | Bajo |
| **Umbral de degeneración 1e-11, no el 1e-8 habitual** | Medido: el suelo de ruido del vector excentricidad es 3e-16, así que a `e = 1e-11` la dirección del periapsis tiene 3e-5 rad de incertidumbre. Con 1e-8 se plegaría una LEO «circular» real (`e ~ 1e-4…1e-6`) perdiendo un ω perfectamente medible. Hay un test que fija ese caso | Bajo |
| **Las anomalías conservan las vueltas; `rv_to_coe` envuelve** | Si `E(M + 2πk)` devolviera `E(M)`, una serie propagada sería un diente de sierra y cualquier interpolación que cruzara una vuelta daría un valor sin sentido. `rv_to_coe` no tiene historia que conservar: recibe un estado, no una trayectoria | Bajo |
| **`arctan2` sobre seno y coseno explícitos, no `arccos` + cuadrante** | `arccos` pierde la mitad de sus cifras cuando su argumento se acerca a ±1 — justo donde está una órbita casi ecuatorial o casi circular, las que hay que tratar bien. El seno sale de un producto triple contra el momento angular, que además fija el cuadrante sin rama aparte | Medio |
| **`Frame` viaja en los elementos; ITRF y ENU se rechazan** | Unos elementos referidos a un marco que rota no son unos elementos. Irrepresentable en vez de documentado, como el enum del ADR 0002 un nivel más arriba | Bajo |
| **`ClassicalElements` no es un `dataclass`** | Un `__init__` generado declara **un** tipo por campo, y aquí los dos papeles difieren: se acepta `float \| FloatArray` para que un escenario se lea como un escenario, y se almacena siempre `FloatArray`. Anotar la unión empuja una rama a cada consumidor para un caso que ya no puede existir — la erosión del contrato de arrays contra la que avisa `core/types.py`. Escrita a mano: permisiva al entrar, estricta al salir | Medio |
| **Sin `DegradationLog`, otra vez** | El plegado no es una degradación: el estado que produce es exacto. Se aplica la regla del ADR 0002 sin excepción | — |

### El oráculo V3, y por qué este no se congela

`perturbations.py` iba a ser la referencia independiente de este módulo, pero
llega después. Mientras tanto la hace **SciPy**: `DOP853` integrando
`r'' = −µ·r/|r|³` no se parece en nada a la ecuación de Kepler ni a la base
perifocal, y cierra la cadena entera de una vez —`rv_to_coe → advance_mean_anomaly
→ true_from_mean_anomaly → coe_to_rv`— que ningún test de función suelta puede
hacer. Cinco regímenes parametrizados (LEO, SSO, tipo Molniya, GEO, retrógrada)
más un puñado de órbitas aleatorias, una revolución completa, a 1 m y 1 mm/s.

**No se congela a fichero**, y la regla que lo justifica está ahora escrita en
`tests/golden/README.md`: SciPy ya es dependencia del núcleo, el integrador es
determinista con su exactitud fijada por un argumento explícito, y se compara
tres órdenes de magnitud por encima de su propio error. Lo que un fichero
congelado protege —una referencia que cambia sin avisar— no aplica.

---

## 11. Archivos

| Archivo | Qué es |
|---|---|
| `src/quoss/orbits/__init__.py` | Docstring. Sin re-exports, como `core/` |
| `src/quoss/orbits/frames.py` | 11 funciones públicas + `Frame`. Tiempo, TEME↔ITRF (posición y estado), geodésico↔ITRF, ENU |
| `src/quoss/orbits/kepler.py` | 12 funciones públicas + `ClassicalElements` y **`ElementType`**. Anomalías, ecuación de Kepler, tamaño/periodo, elementos↔estado |
| `src/quoss/orbits/perturbations.py` | 5 funciones públicas + `ZonalGravity`, `SecularRates`, `CRITICAL_INCLINATION_RAD` y los presets `EGM96_ZONAL`/`WGS72_ZONAL`. Fuerza zonal J2/J3/J4, tasas seculares de J2, integrador DOP853 |
| `src/quoss/orbits/_validation.py` | `as_1d` y `as_vec3`, que estaban duplicados byte a byte en `frames.py` y `kepler.py` |
| `docs/adr/0002-frames-and-time-scales.md` | El ADR de marcos y escalas de tiempo |
| `docs/adr/0003-orbital-elements.md` | El ADR de elementos, anomalías y casos degenerados |
| `docs/adr/0004-zonal-perturbations.md` | El ADR de gravedad zonal y teoría secular: por qué la fuerza es exacta y la teoría solo de primer orden |
| `src/quoss/orbits/propagator.py` | **Nuevo.** 1 función pública + `PropagationMethod` y `Trajectory`. Elementos en una época → estados en una rejilla, con el método como parámetro obligatorio |
| `docs/adr/0005-propagation.md` | **Nuevo.** El ADR de propagación: un punto de entrada, un enum obligatorio, y por qué el enum se envía incompleto |
| `docs/adr/0006-osculating-vs-mean-elements.md` | **Nuevo.** El ADR de la bandera osculador/medio: qué son las dos elipses, la tabla de km, y las tres subdecisiones con sus alternativas descartadas |
| `tests/orbits/test_propagator.py` | 43 tests (+3 doctests en el módulo): los dos modos validándose entre sí en las dos direcciones, la rodaja por satélite contra la propagación individual, la época que se transporta y no se lee, el conjunto de miembros del enum, y que **todos** los modos rechazan elementos medios |
| `tests/orbits/test_frames.py` | 85 tests: V2 por definición, V1 invariantes/property-based, V3 contra referencia, y `TestFrameErrorBudget` |
| `tests/orbits/test_kepler.py` | 119 tests (+16 doctests en el módulo, que ejecuta `--doctest-modules`): **V2 Vallado 2-1/2-5/2-6**, V1 invariantes y casos degenerados, V3 contra la integración numérica, y `TestTheElementTypeFlag` (la bandera osculador/medio) |
| `CLAUDE.md` | Único sistema de metadatos de agentes del repo (guía §5 pide uno, no cuatro). La norma de explicación —desde cero, defendida, con ejemplo numérico— y el contexto mínimo antes de tocar nada |
| `tests/orbits/test_perturbations.py` | 69 tests (+6 doctests en el módulo): gradiente numérico del potencial, forma cartesiana transcrita, V3 contra DOP853 con el escalado en J2, J3 sin término secular, la SSO de Landsat-8, y `TestTheElementTypeGate` |
| `tests/golden/README.md` | Los cuatro niveles, las reglas de un fichero de referencia, y los huecos declarados |
| `tests/golden/generators/gen_frames_reference.py` | El generador. No importa `quoss` |
| `tests/golden/data/frames_reference.json` | Datos congelados con manifest (astropy 8.0.1, pyerfa 2.0.1.5) |

Modificados en esta entrada (la bandera osculador/medio):

- `src/quoss/orbits/kepler.py` — **`ElementType`** (`StrEnum`, dos miembros) y el
  campo `element_type` en `ClassicalElements`, con su propiedad, su hueco en
  `__slots__`, su sitio en el `__repr__` y el reenvío en `from_semi_major_axis`.
  Más el método **`relabelled_as`** y la guarda de `coe_to_rv`. `rv_to_coe` pone
  la etiqueta explícitamente en vez de dejarla al defecto, para que el único
  sitio que la acuña sea greppable.
- `src/quoss/orbits/perturbations.py` — `secular_rates_j2` exige
  `MEAN_BROUWER`. Su sección «Mean elements versus osculating elements» decía que
  la función «no pregunta de qué tipo son porque no puede saberlo»: ya puede, y
  el docstring ahora dice lo contrario del que había.
- `src/quoss/orbits/propagator.py` — el aplanado de `TWO_BODY` **reenvía**
  `element_type` a la pila `(S · n)`. Es un cambio de una línea y es el que evita
  que ese modo blanquee unos elementos medios (§6).
- `tests/orbits/test_kepler.py` — `TestTheElementTypeFlag`, 11 tests: el conjunto
  exacto de miembros y la ausencia de `MEAN`, el defecto, que `rv_to_coe` acuña
  osculadores, las dos guardas, que el mensaje nombra Brouwer-Lyddane, y que
  `relabelled_as` no toca un número.
- `tests/orbits/test_perturbations.py` — `TestTheElementTypeGate`, 5 tests, y la
  helper `_mean_elements` frente a `.relabelled_as(...)`: la primera para los
  tests que **son** sobre elementos medios, la segunda para los que mienten a
  propósito. `test_secular_rates_does_not_accept_a_j3_at_all` se acompaña ahora de
  su gemelo sobre la bandera: la firma no tiene dónde meter un `assume_mean`.
- `tests/orbits/test_propagator.py` — `test_every_mode_refuses_mean_elements`,
  parametrizado sobre el enum, más el `relabelled_as` en el test del día de J2,
  que necesita la tasa secular solo para predecir un orden de magnitud.
- `docs/adr/0006-osculating-vs-mean-elements.md` — **nuevo**. Las tres
  subdecisiones, con la tabla de km y las alternativas descartadas.
- `docs/adr/0003-orbital-elements.md`, `docs/adr/0005-propagation.md` — punteros
  al 0006; en el 0005, el «no cierra» de la bandera pasa a cerrado.
- `notes/ROADMAP.md`, `README.md` — el estado de 2.1 incluye la bandera.

Modificados en la entrada anterior (`propagator.py`):

- `src/quoss/orbits/perturbations.py` — `_DEFAULT_RTOL` y `_DEFAULT_ATOL_KM`
  pasan a ser **públicas**, `DEFAULT_ZONAL_RTOL` y `DEFAULT_ZONAL_ATOL_KM`,
  porque `propagate` las reenvía y una segunda copia del número en otro módulo se
  desincroniza. Los valores no cambian y ningún test existente se tocó.
- `notes/ROADMAP.md` — 2.1.4 hecho, con la nota de por qué el enum va incompleto.
- `README.md` — el estado pasa a «hecho `propagator.py`, siguiente `tle.py`».

Modificados en la entrada anterior (`perturbations.py`):

- `src/quoss/core/constants.py` — **constante nueva** `EGM96_RADIUS_EQUATORIAL_KM`
  (6378.1363 km), con dos tests: que los tres radios de referencia son tres
  números distintos, y que EGM96 y WGS-84 distan 0.7 m.
- `src/quoss/orbits/frames.py`, `src/quoss/orbits/kepler.py` — pierden sus copias
  de `as_1d`/`as_vec3` e importan de `_validation.py`. Cambio mecánico: los
  mensajes de error se movieron sin tocar una coma, y los 448 tests existentes lo
  confirmaron sin ninguna modificación.
- `tests/orbits/test_kepler.py` — `test_argument_of_latitude_errata` reforzado
  (§4), y un docstring que afirmaba algo falso, corregido. Después, **dos tests
  nuevos** (§4, final): `test_argument_of_latitude_property_carries_the_v2_value`
  ata el dato V2 de `u` a la propiedad que lo implementa, y
  `test_argument_of_latitude_wraps_past_one_turn` ejercita el envuelto, que el
  ejemplo de Vallado no puede alcanzar. El docstring de `VALLADO_2_5_EXPECTED`
  apunta ahora a los dos tests y dice cuál hace qué.
- `tests/golden/README.md` — el hueco de GMAT/Orekit para las tasas seculares de
  J2 se cierra por otra vía, y se explica por qué el oráculo interno prueba más
  que una tabla congelada.
- `README.md` — dos afirmaciones caducadas: decía «Etapa 0, todavía no hay
  física» y, en Principios, «SimulCTTC es el **oráculo**», que es exactamente lo
  contrario de lo que se decidió en la etapa 2.1 (§2).
- `notes/ROADMAP.md` — 2.1.3 hecho, con la corrección de lo que el propio
  roadmap afirmaba sobre validar a O(J2²).

Sin cambios en `pyproject.toml` ni en `uv.lock`.

---

## 12. Entorno

**Sin cambios en esta entrada.** `propagator.py` no añade ninguna dependencia:
solo importa de `core/`, `kepler.py` y `perturbations.py`. Tampoco la anterior:
`perturbations.py` usa `numpy` para la fuerza y `scipy.integrate.solve_ivp` para
el integrador, que ya estaba en el núcleo. El grupo `reference` sigue sin
instalarse en CI y ningún módulo de `orbits/` lo necesita.

Del cambio anterior, sin novedad: nuevo grupo **no** por defecto: `reference` con
`astropy>=6.0` (resuelve astropy 8.0.1 + astropy-iers-data + pyerfa). CI **no** lo
instala. Ejecutar un generador:

```bash
uv run --group reference python tests/golden/generators/gen_frames_reference.py
```

---

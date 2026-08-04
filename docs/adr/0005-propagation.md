# ADR 0005 — Propagación: un punto de entrada, un enum obligatorio, y un enum incompleto a propósito

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Etapa:** 2.1 (`orbits/propagator.py`)
- **Afecta a:** `tle.py`, `geometry.py`, `constellations.py`, `system/passes.py`,
  y el esquema de escenario de la etapa 4, que escribe el método como un campo.
  El [ADR 0003](0003-orbital-elements.md) fijó qué es una órbita, el
  [ADR 0004](0004-zonal-perturbations.md) cómo deja de ser kepleriana; este fija
  **quién elige** entre las dos y con qué forma sale el resultado.

---

## Contexto

Los tres módulos anteriores no tienen reloj. Una conversión de marco necesita un
instante pero no una historia; unos elementos describen una órbita, no una
trayectoria; un campo de fuerzas se evalúa en una posición. `propagator.py` es
donde la simulación adquiere **tiempo**, y no aporta física nueva: todo lo que
calcula ya está en `kepler.py` y en `perturbations.py`.

Lo que sí aporta son cuatro decisiones que los módulos anteriores dejaron
abiertas a propósito, y que si se toman mal contaminan todo lo que viene detrás:

1. **Quién elige el modelo.** `coe_to_rv` y `propagate_zonal` **no dan los mismos
   números** y no deben fingir que sí. Uno trata la Tierra como masa puntual y
   tiene forma cerrada; el otro integra el campo zonal real y cuesta un
   Runge-Kutta por órbita.
2. **La época.** Era el defecto de SimulCTTC: sin época explícita, caía a
   `datetime.utcnow()`. Un run que mañana no se puede reproducir, y ningún error
   en ningún sitio.
3. **La forma de los arrays multi-satélite.** `(n, S, 3)` o `(S, n, 3)`. Estaba
   anotada como pendiente desde la etapa 1 y ya no se puede posponer: es el tipo
   que `geometry.py` va a consumir.
4. **Qué hacer con el modo analítico de J2**, que el roadmap pedía y que hoy no
   se puede enviar entero — ver abajo.

## Decisión

**Una función `propagate`, con `method` obligatorio, palabra clave y sin valor
por defecto. Un `PropagationMethod` con dos miembros y un tercero declarado
ausente. La época llega dentro de un `TimeGrid`. Los estados salen en
`(S, n, 3)`, siempre 3-D, dentro de un `Trajectory` que lleva grid, marco y
método.**

| Cuestión | Elección |
| -------- | -------- |
| Puntos de entrada | **uno**: `propagate(elements, grid, *, method, …)` |
| `method` | obligatorio, palabra clave, **sin default** |
| Miembros del enum | `TWO_BODY` y `ZONAL_NUMERIC`. **No** hay `J2_SECULAR_ANALYTIC` |
| Condición inicial | `ClassicalElements` (osculadores). Un estado pasa antes por `rv_to_coe` |
| Época | dentro del `TimeGrid`; obligatoria, nunca leída numéricamente |
| Forma de salida | `(n_satellites, n_samples, 3)`, siempre 3-D |
| Retorno | `Trajectory`: arrays + `grid` + `frame` + `method` |
| Modelo de fuerzas | un `ZonalGravity`; `TWO_BODY` lee solo su `mu` |
| Modelo guardado en el resultado | **no**; la procedencia del modelo es del escenario |
| `DegradationLog` | ninguno, por la regla del [ADR 0002](0002-frames-and-time-scales.md) |

## Justificación

### Por qué el método es obligatorio y sin default

Un default es una decisión de modelado tomada por el llamante **sin que se dé
cuenta**. En un proyecto donde el modo de fallo característico es un número
plausible y equivocado, esa es exactamente la clase de decisión que no puede ser
implícita. Además el método viaja en el `Trajectory`, así que un resultado
siempre puede decir cómo se hizo, y el campo del YAML de la etapa 4 es un `str`
que el `StrEnum` resuelve sin conversor.

Hay un test sobre la **firma** (`inspect.signature`) que aserta que `method` es
`KEYWORD_ONLY` y que su default es `Parameter.empty`, en el mismo espíritu que el
test del ADR 0004 que aserta que `secular_rates_j2` no tiene dónde meter un J3:
la forma de la API es la salvaguarda, así que un refactor no puede ablandarla en
silencio.

### Por qué el enum se envía incompleto

El tercer modo obvio —propagador analítico de J2 sobre `secular_rates_j2`— **no
está**, y la ausencia es una decisión.

Una tasa secular habla de elementos **medios**; `rv_to_coe` y cualquier escenario
hablan de **osculadores**. La diferencia es O(J2), y en kilómetros, medida contra
`propagate_zonal` con J2 solo en los dos lados (así que la discrepancia es el
desajuste, no física distinta):

| Órbita (elementos en ν = 0) | 1 vuelta | 15 vueltas (~1 día) |
|---|---|---|
| SSO 700 km, i = 98.2° | 86.3 km | **1293 km** |
| ISS-like, i = 51.6° | 56.4 km | **845 km** |
| LEO polar, i = 90° | 88.1 km | **1319 km** |
| LEO baja i, i = 28.5° | 20.3 km | **305 km** |

> Tabla **corregida el 2026-08-04**: daba 14.6 km y 219 km para la SSO, cifras de
> una medición ad-hoc que nunca tuvo test y que resultaron 5.9 veces demasiado
> pequeñas. Reproducidas y atribuidas ahora en
> `tests/orbits/test_propagator.py::TestWhatNotHavingBrouwerLyddaneCosts`; la
> derivación y la dependencia con la fase están en el
> [ADR 0006](0006-osculating-vs-mean-elements.md).

Lo que importa de esa tabla no es el tamaño, es que **crece**. El error radial y
el cross-track se quedan quietos —son el bamboleo de período corto, que oscila y
no acumula, 0.5 km y 0.03 km tras una vuelta— pero el along-track crece
linealmente, porque un error O(J2) en el semieje es un error O(J2) en la
*velocidad angular* y eso integra. En unidades de pase: **≈11.5 s de error de
reloj orbital por vuelta, ≈2.9 minutos al día**. Un pase dura ~10 minutos, así que
en un día las ventanas de visibilidad ya están corridas una fracción apreciable de
un pase. Y el tamaño depende de en qué punto de la órbita se declaren los
elementos —factor 1100 entre ν = 0° y ν = 45°— así que no hay un número que citar,
que es un argumento más para que el modo no exista en vez de existir documentado.

Las dos alternativas a no enviarlo eran peores:

- **Enviarlo tal cual**, documentando el error. Es un modo que degrada en
  silencio: produce un array del tipo correcto, con números plausibles, y nada
  falla. Es literalmente lo que el README prohíbe.
- **Retrasar el módulo entero** hasta tener Brouwer-Lyddane. Bloquea
  `geometry.py`, `constellations.py` y el primer enlace calculable de punta a
  punta por una pieza que no hace falta para el modo de referencia.

Un nombre **ausente** obliga a preguntar en el punto de llamada; un nombre
presente y silenciosamente equivocado no obliga a nada. Y el enum crece sin tocar
a nadie: nadie puede depender de un miembro que nunca existió. Cuando entre la
transformación de período corto, se añade `J2_SECULAR_ANALYTIC`, se añade una
rama, y caen además los términos seculares de segundo orden del ADR 0004 — la
misma llave abre las dos puertas.

Dos tests sostienen esto: uno aserta el **conjunto exacto** de miembros (así que
añadir uno hace fallar el test, que es el momento de actualizar también este ADR)
y otro está **parametrizado sobre el enum**, de modo que un miembro añadido sin
implementar falla inmediatamente en vez de caer en una rama muerta.

### Por qué la condición inicial son elementos y no un estado

Es lo que escribe el escenario de la etapa 4, lleva su `Frame` dentro —que el
resultado hereda— y es el tipo que exigirá el modo analítico cuando entre con la
bandera medio/osculador. Quien tenga un estado escribe `rv_to_coe`, que es exacto
(ida y vuelta medida en ~15 nm) y **greppable**.

`tle.py` deliberadamente **no** entra por aquí. Un TLE se propaga con SGP4, que
devuelve estado en TEME directamente; construir un `ClassicalElements` con los
elementos medios de un TLE es justo el error que el ADR 0003 y `notes/` llevan
tres documentos avisando de no cometer. Un `propagate_tle` en su propio módulo es
más honesto que un miembro más de este enum.

### Por qué la época viaja en un `TimeGrid` y nunca se lee

Los elementos están dados en `grid.epoch_jd`, es decir en `t_s == 0`, y no hay
otra forma de decir de cuándo son: el `TimeGrid` no se puede construir sin época.
Eso convierte el defecto de SimulCTTC en algo irrepresentable, no en algo
documentado.

Pero **nada de este módulo lee `epoch_jd` numéricamente**: la física es función
de segundos transcurridos y la fecha juliana se transporta intacta, para que los
módulos que sí necesitan tiempo absoluto (GMST en `frames.py`, la geometría solar
más adelante) la tomen de un solo sitio en vez de que cada uno guarde la suya.
Hay un test que aserta que dos rejillas que solo difieren en `epoch_jd` devuelven
estados **idénticos bit a bit**. Ese test también avisa en la otra dirección: el
día que entre un modelo que dependa de tiempo absoluto —solar, lunar, arrastre
con atmósfera real— fallará, y ese es el momento de enterarse.

`t_s` puede empezar donde sea, incluir el cero o no, y ser negativa: la
integración sale de la época en las dos direcciones, que es lo que necesita una
época en mitad de la ventana.

### Por qué `(S, n, 3)` y no `(n, S, 3)`

Porque `traj.r_km[s]` es entonces un bloque **contiguo** `(n, 3)` con el tiempo
en el eje que va primero — exactamente el contrato de arrays que ya toma todo lo
demás del paquete (`Vec3Array`). Con `(n, S, 3)` la traza de un satélite es
`r[:, s]`, una vista con salto que cada llamada aguas abajo tendría que copiar.
Hay un test que aserta la contigüidad y que la construye a mano en la disposición
rechazada para comprobar que allí no la hay.

Siempre 3-D, también para un satélite: `(1, n, 3)`, igual que una estación única
es `(1, 3)` en `frames.py`. Un llamante que no ramifica por forma es un llamante
que no tiene esa rama mal.

Y donde el bucle acaba viviendo: `propagate_zonal` es de una órbita por diseño
(una EDO no se difunde sobre condiciones iniciales), así que `ZONAL_NUMERIC` son
S integraciones y el bucle está aquí, que es la capa que sabe cuántas órbitas
hay. `TWO_BODY`, en cambio, aplana los ejes satélite y tiempo en una sola pila de
`S · n` juegos de elementos y llama a `coe_to_rv` **una vez**.

Ese aplanado tiene una trampa que merece test propio: usa `np.repeat` sobre los
elementos y `np.tile` sobre los tiempos, y **intercambiarlos produce un array de
la forma correcta, con los números correctos, en las posiciones equivocadas**.
Ninguna aserción de forma lo detectaría. Lo que lo detecta es comparar la rodaja
de cada satélite contra ese satélite propagado solo, y así está escrito.

### Por qué un solo `ZonalGravity` para los dos modos

`TWO_BODY` lee únicamente `gravity.mu_km3_s2`, y eso **no** es la sustitución
silenciosa de modelo que `secular_rates_j2` rechaza. Allí el nombre prometía J2 y
el objeto ofrecía J3 y J4, que se habrían descartado sin decirlo; aquí el
parámetro `method` es obligatorio y explícito, así que el llamante ya ha
declarado en la llamada qué física quiere. Un mando en vez de dos parámetros
mutuamente excluyentes.

### Por qué el `Trajectory` no guarda el modelo de gravedad

Una trayectoria `TWO_BODY` no depende de los armónicos, así que guardar un
`ZonalGravity` a su lado afirmaría una dependencia que no existe. El modelo es
del escenario, que es lo que la etapa 4 hashea para la procedencia. Lo que sí
guarda es lo que no se puede reconstruir mirando los números: la rejilla, el
marco y el método.

### Por qué se hicieron públicas las tolerancias del integrador

`_DEFAULT_RTOL` y `_DEFAULT_ATOL_KM` pasan a ser `DEFAULT_ZONAL_RTOL` y
`DEFAULT_ZONAL_ATOL_KM`. `propagate` las reenvía, y una segunda copia del número
en un segundo módulo es un número que se desincroniza. Los valores no cambian.

## Consecuencias

### Lo que este módulo cierra

- **La elección de modelo es explícita en la API**, que era el pendiente
  bloqueante anotado en `LAST_CHANGES.md` §11.
- **La época deja de ser un pendiente** y el defecto de la época implícita queda
  irrepresentable.
- **La forma multi-satélite queda fijada** en `(S, n, 3)`, satellite-major.
- `geometry.py` puede escribirse: recibe `traj.r_km[s]` y lo pasa a
  `teme_to_itrf` sin copia ni reshape, con la época en `traj.grid.jd`.

### Lo que no cierra

- **El modo analítico de J2**, y con él los términos seculares de segundo orden
  del ADR 0004. Condición de entrada escrita: la transformación de período corto
  de Brouwer-Lyddane.
- ~~**La bandera osculador/medio** dentro de `ClassicalElements`.~~ **Cerrada
  después, en el [ADR 0006](0006-osculating-vs-mean-elements.md).** Existe
  `ElementType`, `coe_to_rv` exige osculadores y los dos modos de aquí pasan por
  él, así que `propagate` rechaza elementos medios sin necesitar una guarda
  propia. Un detalle que este ADR sí toca: el aplanado `(S · n)` de `TWO_BODY`
  **reenvía la etiqueta** a la pila que construye, porque dejarla caer al defecto
  la blanquearía justo antes de la única comprobación que hay.
- **Paralelismo.** El bucle sobre satélites de `ZONAL_NUMERIC` es secuencial. Es
  el sitio evidente para un pool de procesos y pertenece a `engine/parallel.py`,
  no aquí.
- **Interpolación.** Un `Trajectory` da muestras en la rejilla que se pidió; el
  refinado alrededor de un pase es de `system/passes.py`.
- **SGP4.** Ni miembro del enum ni rama: `tle.py` tendrá su propia entrada, por
  la razón de arriba.

## Alternativas descartadas

**Dos funciones, `propagate_two_body` y `propagate_zonal_numeric`.** Deja el
método fuera del resultado —hay que llevarlo a mano hasta la procedencia— y
convierte un campo del escenario en un `if` del llamante. Con el enum, el
escenario escribe una cadena y el motor no ramifica.

**Un enum completo con el modo analítico marcado como experimental.** Es la
opción que más se parece a cumplir el roadmap. Se descarta por la misma regla que
el ADR 0004 aplicó a los términos de segundo orden: código no ejercitado es
código que no funciona, y aquí además produciría resultados plausibles.

**Aceptar `(r0, v0)` en lugar de elementos.** Habría hecho de `propagate` la
entrada natural de SGP4 y de `tle.py`, que es justo lo que no se quiere: el TLE
tiene su propio camino y mezclarlo aquí reabre la confusión medio/osculador por
otra puerta.

**Devolver una tupla `(r, v)`,** como `coe_to_rv` y `propagate_zonal`. Más
pequeño de superficie, pero la época, el marco y el método dejan de viajar con
los números, y cada llamante los vuelve a acarrear a mano — que es exactamente
cómo se pierde una procedencia.

**Decidir la forma multi-satélite en la etapa 3**, como proponía la nota
original. Se descarta porque `geometry.py` llega antes que la etapa 3 y tendría
que inventarse una forma provisional.

## Referencias

- `notes/ROADMAP.md` — Etapa 2.1.4
- [ADR 0001](0001-unit-conventions.md) — unidades
- [ADR 0002](0002-frames-and-time-scales.md) — marcos, época y la regla de firma
  del `DegradationLog`
- [ADR 0003](0003-orbital-elements.md) — elementos; el aviso sobre elementos
  medios de un TLE que este ADR hereda
- [ADR 0004](0004-zonal-perturbations.md) — la fuerza zonal, la teoría secular de
  primer orden, y por qué Brouwer-Lyddane es la condición de entrada
- `tests/golden/README.md` — los cuatro niveles de verificación
- Vallado, *Fundamentals of Astrodynamics and Applications*, 4.ª ed., 2013, cap. 8

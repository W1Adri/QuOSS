# ADR 0008 — `constellations.py`: anomalía media en el espaciado, SSO por álgebra, traza repetida por `brentq`

- **Estado:** aceptada
- **Fecha:** 2026-09-10
- **Etapa:** 2.1.7 (`orbits/constellations.py`)
- **Afecta a:** cualquier escenario que declare una constelación o una órbita
  heliosíncrona/de traza repetida (etapa 4, `scenario/`), y hereda directamente
  del [ADR 0006](0006-osculating-vs-mean-elements.md).
- **Extiende** al [ADR 0004](0004-zonal-perturbations.md) (usa
  `secular_rates_j2` tal cual, sin reimplementarla) y al
  [ADR 0006](0006-osculating-vs-mean-elements.md) (hereda su bandera
  osculador/medio en vez de abrir un mecanismo nuevo).

---

## Contexto

El roadmap pedía tres cosas bajo un mismo fichero: Walker-Delta, diseño de
órbita heliosíncrona (SSO) y diseño de traza repetida. Las tres comparten
proveedor de física (`secular_rates_j2`) pero no comparten forma de problema:

| | Walker-Delta | SSO | Traza repetida |
|---|---|---|---|
| Qué es | reparto geométrico de `T` satélites en `P` planos | invertir una tasa | igualar dos tasas |
| Física | ninguna | `secular_rates_j2`, invertida | `secular_rates_j2`, en las dos partes de una igualdad |
| Incógnita | ángulos de RAAN y anomalía | la inclinación `i` | el semieje `a` |
| Cómo se resuelve | aritmética | álgebra cerrada (despejar `cos i`) | `a` aparece a los dos lados → raíz numérica |

Tres decisiones no obvias salieron de ahí, y son las que este ADR fija:

1. **¿En qué ángulo se reparten los satélites dentro de un plano?** La
   anomalía verdadera es la que aparece en casi todos los libros de texto al
   dibujar el patrón; pero para una órbita excéntrica no es la que se mantiene
   constante en el tiempo.
2. **¿Se invierte `secular_rates_j2` con álgebra o con `scipy.optimize`?** La
   fórmula de `dOmega/dt` es lineal en `cos i` una vez fijados `a` y `e`, así
   que hay una respuesta cerrada — pero es fácil no verlo y reaching for un
   solver de todos modos.
3. **¿Qué tipo de elemento (`ElementType`) llevan los números que estas
   funciones producen?** `secular_rates_j2` exige medios; sus inversas
   devuelven, por construcción, cantidades que solo tienen sentido como
   medias también.

## Decisión

**El espaciado dentro de un plano se hace en anomalía media, convertida a
verdadera una sola vez al construir. La inclinación SSO se despeja en forma
cerrada de la propia fórmula de `secular_rates_j2`, nunca reimplementada. El
semieje de traza repetida se resuelve con `scipy.optimize.brentq`, acotado por
la estimación de dos cuerpos. Ninguna de las tres funciones construye un
`ClassicalElements`: las dos físicas devuelven el número crudo (radianes,
kilómetros), y es quien las llama quien decide la etiqueta al construir.**

| Cuestión | Elección |
| -------- | -------- |
| Ángulo de espaciado en `walker_delta` | anomalía **media** |
| Forma de resolver SSO | álgebra cerrada, despejando `cos i` |
| Forma de resolver traza repetida | `scipy.optimize.brentq`, acotado por la estimación de dos cuerpos ± 5 % |
| Qué devuelven `sun_synchronous_inclination_rad`/`repeat_ground_track_semi_major_axis_km` | el número crudo, no un `ClassicalElements` |
| Verificación del sentido de `F` | invariantes V1 + caso `6:6/3/1` a mano + fórmula independiente (MATLAB Aerospace Toolbox) |
| Ejemplo Vallado citable para Walker-Delta o traza repetida | no localizado con confianza; no se inventa |

## Justificación

### Por qué anomalía media, y no la verdadera que dibuja casi todo libro de texto

Dos satélites que comparten semieje mayor comparten movimiento medio `n`, así
que sus anomalías medias son `M_1(t) = M_{1,0} + n t` y `M_2(t) = M_{2,0} + n
t`: la diferencia `M_2 - M_1` es **exactamente constante** bajo movimiento
kepleriano puro, para cualquier `t`. La anomalía verdadera no tiene esa
propiedad — `d(nu)/dt` no es constante en una órbita excéntrica, es más rápida
en el periastro — así que dos satélites separados un ángulo fijo en anomalía
verdadera se acercan y se separan en cada vuelta, exactamente el bamboleo que
le da a la traza de una órbita excéntrica su forma de analema.

Para las excentricidades casi nulas que vuela casi cualquier constelación real
(`e` de unas pocas milésimas) la elección es casi irrelevante: medias y
verdadera concuerdan a `O(e)`, décimas de grado. Deja de serlo en cuanto `e`
no es pequeña, y por eso la elección se hace explícita en vez de dejarla a
cuál anomalía resultara cómoda. `walker_delta` reparte en anomalía media y
convierte a verdadera **una sola vez**, con
`kepler.true_from_mean_anomaly` — no al revés — y hay un test que lo prueba
por control negativo:
`TestWalkerDeltaInvariants::test_true_anomaly_spacing_is_not_exact_once_eccentric`
construye una constelación con `e = 0.3` y comprueba que el espaciado en
anomalía verdadera **no** es constante, mientras que el de anomalía media sí lo
es (`test_mean_anomaly_spacing_within_plane_is_exact`).

### Por qué el sentido de `F` se fija así, y qué se hizo cuando Vallado no dio un ejemplo transcribible

La dirección del desfase entre planos —si el plano `p` va `p·F·360/T` grados
**adelantado** o **retrasado** respecto al plano 0— es «la parte que la gente
se equivoca», y equivocarla produce un patrón con el espaciado de RAAN
correcto y el espaciado dentro de plano correcto: parece bien a primera vista.
Se buscó un ejemplo Walker-Delta resuelto en Vallado (*Fundamentals of
Astrodynamics and Applications*, 4.ª ed.) transcribible con número de página,
en el mismo espíritu que las citas de `test_kepler.py`, y no se localizó con
confianza suficiente. Por la regla explícita del proyecto contra inventar
citas «V2», la corrección se apoya en:

1. **Invariantes V1** que no dependen de ninguna fuente externa: el espaciado
   de RAAN es exactamente `360/P`, el de anomalía media exactamente
   `360/(T/P)`, y el recuento total es exactamente `T` — se siguen de lo que
   «espaciado uniforme» significa, no de una tabla.
2. **Un caso resuelto a mano**, `6:6/3/1`: plano 0 = [0°, 180°], plano 1 =
   [60°, 240°], plano 2 = [120°, 300°]. Si el signo estuviera invertido, el
   plano 1 leería [300°, 120°].
3. **Acuerdo independiente** con cómo el patrón está documentado en otro
   sitio: la documentación de `walkerDelta` del MATLAB Aerospace Toolbox
   describe el paso entre planos como exactamente `F · 360/T` grados de
   anomalía verdadera — confirmado por búsqueda dirigida, no citado de
   memoria.

Esto no es un V2 y el módulo lo dice así: es corroboración informativa sobre
invariantes que ya bastan solos.

### Por qué SSO se despeja en álgebra y no se busca con `scipy.optimize`

`secular_rates_j2` da `dOmega/dt = -1.5 · n · J2 · (R/p)^2 · cos(i)`. Fijados
`a` y `e` (de donde salen `n` y `p`), esto es lineal en `cos(i)`: despejar es

```
cos(i) = -dOmega_sol / (1.5 · n · J2 · (R/p)^2)
```

una división, no una búsqueda. Meter un `brentq` ahí sería resolver con
fuerza bruta un problema que ya viene resuelto, y además reimplementar por la
puerta de atrás una fórmula que ya existe y ya está probada en
`perturbations.py` — exactamente lo que el ADR 0004 ya decidió no hacer dos
veces con los armónicos zonales. El propio docstring de la función lo dice: si
hiciera falta `scipy.optimize` aquí, es señal de que el álgebra no se hizo.

**Verificación, aprovechando lo que ya existía.** El docstring de
`secular_rates_j2` ya afirma que `a=7078.137 km, e=0.001, i=98.19°` da
`0.9859°/día`. Invertir esa misma `a`, `e` recupera `i ≈ 98.19°` a la precisión
en la que ese número está citado — no es una coincidencia, ni una segunda
medición: es la misma fórmula resuelta para la incógnita contraria. Y el viaje
de ida y vuelta —despejar `i`, meterla en `secular_rates_j2`— cierra a
precisión de máquina (`test_round_trip_through_secular_rates_j2_is_exact`,
residuo `< 1e-17` rad/s), porque las dos direcciones son álgebra sobre la
misma igualdad, no dos implementaciones que podrían coincidir por casualidad.

### Por qué traza repetida sí necesita `brentq`, y por qué esa cota y no otra

A diferencia de la SSO, aquí `a` aparece **a los dos lados** de la condición
de resonancia: tanto `dOmega/dt` y `domega/dt` (dentro de la tasa nodal) como
el propio movimiento medio `n` dependen de `a`. No hay despeje algebraico
posible, así que hace falta una raíz numérica. Se usa `scipy.optimize.brentq`
en vez de una iteración de Newton escrita a mano porque `brentq` converge
garantizado para cualquier corchete donde la función cambia de signo y no
necesita derivada — el mismo argumento que ya usa el solver iterativo de
`frames.py` para la inversión geodésica.

El corchete de búsqueda es la estimación de dos cuerpos (ignorando J2 por
completo) ensanchada un 5 % a cada lado. Por qué el 5 % es generoso y no
ajustado: la contribución de J2 a la condición de resonancia es `O(J2)` ~
1e-3 relativo, y el término de rotación terrestre se corrige como mucho un par
de puntos porcentuales (`dOmega/dt` de una SSO llega a ~5°/día contra los
360.99°/día de la Tierra, ~1.4 %) — así que la raíz real está, en todo caso de
interés para este proyecto (LEO, casi circular), muy por dentro del 5 %. Con
`j2 = 0` el corchete **es** la raíz exacta, lo que da una comprobación de
autoconsistencia barata
(`TestRepeatGroundTrackResonance::test_reduces_to_the_two_body_closed_form_when_j2_is_zero`).

**Cuándo el corchete falla, y por qué eso está bien.** Con excentricidad alta
el término J2 se infla por `(R/p)^2`, `p = a(1-e²)`, y puede desbordar
cualquier margen construido solo a partir del período de dos cuerpos. Medido
por búsqueda directa: `orbits=16, days=1, i=63.4°, e=0.9` deja el residuo de
resonancia del **mismo signo** en los dos extremos del corchete del 5 % (+3.27e-4
y +3.78e-4 rad/s), así que no hay nada que `brentq` pueda bisectar. La función
levanta `ConvergenceError` en vez de ensanchar el corchete a ciegas o devolver
lo que `brentq` diera fuera de rango —
`TestRepeatGroundTrackConvergenceError` fija exactamente ese caso.

**Lo que no se pudo verificar contra un caso publicado.** WRS-2 de Landsat-8
(233 órbitas / 16 días, `i = 98.2°`, ~705 km) da una comprobación de
plausibilidad, no un V2: el semieje resuelto por esta función corresponde a
~699.6 km de altitud, **5.4 km (0.08 %) por debajo** de la cifra publicada, y
esa brecha **no** se explica por la precisión publicada de la inclinación
(±0.05° mueve la solución solo ~0.08 km, medido por búsqueda directa) ni de
la excentricidad (~0.00002 km). La explicación más probable es que «705 km»
sea una cifra nominal redondeada y no un semieje preciso, o que entren efectos
que esta teoría de primer orden en J2 no modela (maniobras de mantenimiento,
J2²/J4). Se deja anotado así, sin forzar el número a que encaje — ver
`TestRepeatGroundTrackAgainstLandsat8` en
`tests/orbits/test_constellations.py`.

### Por qué ninguna de las tres funciones construye un `ClassicalElements`

`walker_delta` sí lo construye — es su trabajo, es geometría pura y no hay
ambigüedad de qué elipse describe. Las otras dos no: `secular_rates_j2` es una
afirmación sobre elementos **medios** (ADR 0006), así que la inclinación o el
semieje que sus inversas devuelven son correctos como cantidades medias, y
**no** como el semieje/inclinación osculador de una época concreta —
convertir uno en otro es la transformación de Brouwer-Lyddane que QuOSS no
tiene. Devolver el número crudo, no un `ClassicalElements` con una etiqueta
puesta por defecto, es la misma elección que ya hace
`kepler.semi_major_axis_from_period_km`: quien llama decide la etiqueta al
construir, y **si construye osculador por defecto y pasa por `coe_to_rv`**,
hereda el mismo desajuste ya medido en `kepler.py` (hasta 1290 km/día para una
SSO de 700 km) — no una cifra nueva, la misma, porque es la misma fórmula y el
mismo régimen. La guarda de tipos del ADR 0006 es lo que convierte ese error
en un `DomainError` en el momento en que alguien intenta sacar un estado sin
pasar por `relabelled_as` y decirlo por escrito, en vez de un número plausible
y equivocado.

## Consecuencias

### Lo que esto cierra

- El roadmap 2.1.7 queda completo: Walker-Delta, SSO y traza repetida, los
  tres construidos sobre `secular_rates_j2` sin reimplementar nada de
  `perturbations.py`.
- El patrón «devuelve el número crudo, no un contenedor» se repite una tercera
  vez (`semi_major_axis_from_period_km`, ahora estas dos), así que es ya una
  convención del paquete, no una elección aislada.

### Lo que no cierra

- **Brouwer-Lyddane sigue sin existir.** El semieje/inclinación de SSO y traza
  repetida siguen siendo cantidades medias que nadie puede convertir a
  osculador dentro de QuOSS. Igual que en el ADR 0006, la bandera es una
  puerta cerrada, no un paso.
- **Ningún ejemplo Walker-Delta ni de traza repetida citado con página de
  Vallado.** Queda como hueco declarado en `tests/golden/README.md` y en
  `notes/LAST_CHANGES.md`, no como V2 inventado.
- **Visibilidad, CLI y esquema de escenario.** Fuera de alcance de esta
  entrada por diseño — son las etapas `orbits/geometry.py` (ya hecha),
  `scenario/` y `cli/`.

## Alternativas descartadas

**Espaciar en anomalía verdadera, como casi todo libro de texto dibuja el
patrón.** Se descarta porque no se mantiene constante en el tiempo para una
órbita excéntrica — ver justificación arriba.

**Resolver la SSO con `scipy.optimize.brentq`, por uniformidad con la traza
repetida.** Se descarta porque el problema es lineal en `cos(i)`: usar un
solver numérico donde hay álgebra cerrada es reimplementar `secular_rates_j2`
con más pasos y más superficie de error, sin ganar nada.

**Devolver un `ClassicalElements` ya etiquetado `MEAN_BROUWER` desde las
funciones físicas.** Se consideró, porque cerraría el hueco mean/osculador de
raíz. Se descarta porque obligaría a fijar en la firma el resto de elementos
(RAAN, argp, anomalía) con valores arbitrarios que la función no tiene motivo
para decidir — exactamente lo que `walker_delta` sí necesita decidir y estas
dos no. Devolver el número crudo dejando la construcción a quien llama es más
composable y es el patrón que el resto del paquete ya sigue.

## Referencias

- `notes/ROADMAP.md` — Etapa 2.1.7
- [ADR 0004](0004-zonal-perturbations.md) — la teoría secular que se invierte
  y se resuelve aquí, nunca reimplementada
- [ADR 0006](0006-osculating-vs-mean-elements.md) — la bandera osculador/medio
  que este módulo hereda sin abrir un mecanismo nuevo
- `tests/golden/README.md` — los cuatro niveles, y por qué no se inventa un V2
- Walker, J. G., «Continuous Whole-Earth Coverage by Circular-Orbit Satellite
  Patterns», Royal Aircraft Establishment Technical Report 77044, 1977
- Vallado, *Fundamentals of Astrodynamics and Applications*, 4.ª ed., 2013,
  §9.6 y §11.4

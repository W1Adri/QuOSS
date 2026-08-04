# ADR 0004 — Perturbaciones zonales: fuerza exacta, teoría secular de primer orden

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Etapa:** 2.1 (`orbits/perturbations.py`)
- **Afecta a:** `propagator.py`, `tle.py`, `constellations.py`, `geometry.py`, y
  cualquier escenario de más de un día. El [ADR 0003](0003-orbital-elements.md)
  fijó qué es una órbita; este fija cómo deja de ser kepleriana.

---

## Contexto

La Tierra no es una masa puntual. El abultamiento ecuatorial vale ~1e-3 del
término central, y de él salen tres cosas que un simulador de enlaces no puede
redondear: la regresión del nodo (varios grados por día en LEO), la precesión del
perigeo, y la diferencia entre el periodo kepleriano y el nodal — el que gobierna
si una traza se repite.

Hay dos formas de contarlo y no son intercambiables:

| | Fuerza exacta | Teoría secular |
|---|---|---|
| Qué es | el gradiente del potencial zonal, sin promediar | las tasas medias a las que J2 arrastra Ω, ω y M |
| Coste | una integración numérica por órbita | una expresión cerrada |
| Qué necesita | un estado | unos elementos **medios** |
| Para qué sirve | ser la verdad contra la que medir | barridos, diseño SSO, traza repetida |

Cuatro tensiones reales:

1. **¿Qué armónicos, y escritos cómo?** Las componentes cartesianas de J2, J3 y
   J4 se transcriben a mano en casi todos los libros: nueve expresiones, y los
   errores de signo viven exactamente ahí.
2. **¿Hasta qué orden la teoría secular?** El roadmap pedía «J2/J4 secular».
   Los términos de segundo orden (`J2²`, `J4`) valen ~1e-6 relativo.
3. **J3.** Los zonales impares **no tienen término secular de primer orden**.
   SimulCTTC enviaba una tasa «secular» de J3 cuyo propio docstring lo admitía.
   Es uno de los defectos que motivaron el protocolo V1–V4.
4. **Elementos medios vs osculadores.** Una tasa secular es una afirmación sobre
   elementos *medios*. `rv_to_coe` devuelve osculadores. La diferencia es O(J2).

   **Ya no es un coste tolerado.** Cuando se escribió este ADR el desajuste
   quedaba documentado y nada lo impedía; hoy `secular_rates_j2` **rechaza** unos
   elementos que no estén etiquetados `MEAN_BROUWER`, con `DomainError`, y la vía
   para saltárselo a propósito —lo que hacen los tests que miden el desajuste— se
   llama `relabelled_as` y admite en su nombre que no convierte nada. Ver
   [ADR 0006](0006-osculating-vs-mean-elements.md).

## Decisión

**La fuerza zonal J2/J3/J4 exacta, escrita como una sola expresión general de
Legendre. La teoría secular, solo primer orden en J2. El integrador numérico
dentro del módulo, como oráculo de la teoría. Ninguna tasa secular de J3.**

| Cuestión | Elección |
| -------- | -------- |
| Forma de la aceleración | una expresión parametrizada por grado, no tres juegos de componentes |
| Armónicos en la fuerza | J2, J3, J4 (cualquiera puede ser cero) |
| Orden de la teoría secular | **primero, solo J2**. `J2²` y `J4` no se implementan |
| Tasa secular de J3 | no existe, y la firma no admite dónde ponerla |
| Tipo de elemento que acepta `secular_rates_j2` | **exige `MEAN_BROUWER`**, con `DomainError` si no. Añadido después, ver [ADR 0006](0006-osculating-vs-mean-elements.md) |
| Constantes de los elementos medios | **no** las fija la etiqueta: viajan con el modelo (esta tabla, fila «Modelo de gravedad»), no con los elementos. Ver ADR 0006 |
| Integrador | `solve_ivp(DOP853)`, `rtol` y `atol` como argumentos explícitos |
| Modelo de gravedad | `ZonalGravity` lleva `mu`, radio de referencia y armónicos juntos |
| Constante nueva | `EGM96_RADIUS_EQUATORIAL_KM` (6378.1363 km), ≠ WGS-84 |
| `DegradationLog` | ninguna función lo recibe |

## Justificación

### Por qué una sola expresión y no las componentes cartesianas

Derivando `U = μ/r [1 − Σ Jₙ (R/r)ⁿ Pₙ(s)]` con `s = z/r` una sola vez, la regla
de la cadena da una expresión que vale para todo grado:

```
aₙ = (μ Jₙ Rⁿ / r^(n+2)) · { [(n+1)Pₙ(s) + s Pₙ'(s)] r̂ − Pₙ'(s) ẑ }
```

Expandida en `n = 2` es la fórmula cartesiana de J2 de toda la vida. La ventaja
es de superficie de error: J3 y J4 cuestan **un polinomio de Legendre cada uno**
en vez de tres componentes transcritas cada uno. Nueve oportunidades de error de
signo se convierten en tres polinomios que un lector comprueba de un vistazo.

Y se verifica por dos rutas independientes:

1. **Contra el gradiente numérico del potencial.** Es la afirmación más fuerte
   disponible sobre una fuerza conservativa y no necesita datos externos: si la
   aceleración no es el gradiente de `U`, no hay tolerancia que lo tape.
2. **Contra la forma cartesiana transcrita** de Vallado/Montenbruck, escrita a
   mano en el test. Dos transcripciones independientes que coinciden.

El paso de la diferencia finita **se midió, no se eligió**: el error de
truncamiento cae como `h²` y el de cancelación crece como `1/h`, así que hay un
óptimo, y no está donde dice la intuición. Barrido sobre 9 posiciones y pasos de
300 m a 3 m, el peor caso toca fondo en ~1e-9 con **h = 30 m**. Un paso de 1 km
—el primer candidato obvio— es 250 veces peor.

### Por qué la teoría secular se queda en primer orden

Esta es la decisión que se aparta del roadmap, y se aparta **por medición**.

El plan era implementar también los términos de segundo orden (`J2²` y `J4`).
Al intentar validarlos contra el integrador apareció el problema:

- Una tasa secular de primer orden es una afirmación sobre elementos **medios**.
- La diferencia entre un elemento medio y uno osculador es ella misma **O(J2)**,
  es decir ~1e-3 relativo — **mil veces mayor** que la corrección de segundo
  orden que se quería añadir.
- Medido: con elementos osculadores, el residuo de primer orden es 1e-4…2.6e-3
  según la inclinación, y una fórmula de segundo orden candidata **mejoraba en
  unos casos y empeoraba en otros**, que es exactamente lo que se espera cuando
  la corrección es más pequeña que el ruido del argumento.
- Promediar los elementos osculadores sobre las revoluciones **no** resuelve
  nada: el residuo se queda en O(J2) en las seis configuraciones probadas. Los
  elementos medios de Brouwer no son el promedio temporal de los osculadores.
- Convertir entre unos y otros exige la transformación de período corto de
  Brouwer-Lyddane, que este proyecto no tiene y que el ADR 0003 avisa
  explícitamente de no fingir (el mismo aviso que hereda `tle.py`).

Conclusión: **nada de lo que QuOSS ejecuta hoy distingue una fórmula de segundo
orden correcta de una mal tecleada.** Implementarla sería enviar código no
ejercitado —justo el argumento con el que el ADR 0003 descartó las variables
universales— cuyo propósito entero es una corrección más pequeña que el error ya
presente en sus entradas.

Lo que **sí** está validado, y con una prueba más fuerte que una cota:

> El residuo relativo de las tasas de primer orden contra la integración
> numérica es **exactamente proporcional a J2**. Escalando J2 por 1, 1/2, 1/4 y
> 1/8, el cociente residuo/J2 se mantiene constante a **cuatro cifras**
> (1.184 a i = 51.6°, 0.088–0.091 a i = 98°).

Eso separa las dos hipótesis que una cota sola no puede separar: un coeficiente
mal escrito dejaría un residuo relativo *independiente* de J2. El test vive en
`TestSecularRatesAgainstIntegration::test_the_residual_is_proportional_to_j2`.

La puerta queda abierta y con condición escrita: **el día que entre una
transformación osculador↔medio, los términos de segundo orden pasan a ser
validables y merece la pena añadirlos.** No antes.

### Por qué J3 no tiene tasa secular, y cómo se demuestra

No es una simplificación, es una propiedad de los armónicos impares. Lo que J3
produce es un término de **período largo**, y la diferencia es medible:

> La contribución de J3 a `dΩ/dt` va como **sin ω**: medida a ω = 0°, 90°, 180°
> y 270°, se anula en 0° y 180°, y cambia de signo entre 90° y 270°
> (±3.2e-11 rad/s). Un término secular daría lo mismo en los cuatro.

Un término que depende de dónde esté el perigeo promedia a cero sobre un ciclo
apsidal; un término secular, por definición, no depende de él. Además, incluso en
su máximo el efecto es **cuatro órdenes de magnitud** menor que la tasa secular
de J2 que tiene al lado.

La medición se eligió así por coste: demostrarlo integrando un ciclo apsidal
completo son ~1600 revoluciones; la prueba del signo son cuatro integraciones de
20 y tarda un segundo.

Y la firma lo hace irrepresentable: `secular_rates_j2` **no tiene ningún
parámetro donde meter un J3**. Hay un test que aserta esa forma de la API, para
que un refactor no pueda reintroducir el peligro en silencio.

### Por qué `secular_rates_j2` no acepta un `ZonalGravity`

Sería más cómodo y sería un **error de modelo silencioso**: recibir un objeto que
lleva J3 y J4 y usar solo el J2 es sustituir el modelo sin decirlo, que es
exactamente lo que `core/errors.py` existe para impedir. Como la omisión es una
elección fija y no una decisión en tiempo de ejecución, por la regla del
[ADR 0002](0002-frames-and-time-scales.md) no lleva `DegradationLog`: se resuelve
en la firma. Quien tenga un `ZonalGravity` escribe `j2=gravity.j2`, y el cruce se
encuentra con grep — el mismo movimiento que `km_to_m` en `core/units.py`.

### Por qué `ZonalGravity` existe

Un armónico zonal no significa nada sin el radio al que está referida su
expansión: cada término multiplica `(R/r)ⁿ`. Mezclar armónicos de EGM96 con el
radio de WGS-84, o armónicos de WGS-72 con el `mu` de EGM96, produce un modelo
que no es ninguno de los publicados. Manteniendo el juego en un objeto, esa
mezcla es irrepresentable en vez de estar documentada.

De ahí sale también la constante nueva: `EGM96_RADIUS_EQUATORIAL_KM = 6378.1363`,
que **no** es `WGS84_RADIUS_EQUATORIAL_KM = 6378.137`. La diferencia es de 0.7 m
y su efecto en el término J2 es 2.2e-7 relativo — despreciable frente al
truncamiento del propio modelo, y gratis de evitar. Tres radios, tres propósitos:
geodesia WGS-84, gravedad EGM96, SGP4 WGS-72.

### Por qué el integrador vive aquí

Es el oráculo del módulo, y `tests/golden/README.md` §«cuándo un oráculo V3 no
necesita congelarse» ya cubre el caso: SciPy es dependencia del núcleo, DOP853 es
determinista con su exactitud fijada por argumentos explícitos, y la comparación
se hace muy por encima de su propio error. Por eso `rtol` y `atol_km` son
parámetros con valores declarados y no defaults de biblioteca: una versión nueva
de SciPy no puede mover un resultado publicado.

**Un estado entra, una trayectoria sale.** Una EDO se integra por órbita; no hay
pila de condiciones iniciales sobre la que difundir. Una constelación es un
bucle, y el bucle pertenece a quien sabe paralelizarlo — `propagator.py`.

Dos detalles que los tests destaparon y que quedan documentados en el código:

- `solve_ivp` con un intervalo de longitud cero **devuelve éxito y ningún
  punto**. Una muestra en la época se escribe directamente desde el estado
  inicial: es exacta, y pedírsela al integrador dejaría una fila sin inicializar.
- Hacia atrás, `t_eval` tiene que ir **descendente**. La integración sale de la
  época en las dos direcciones que se le pidan, así que una época en mitad de la
  rejilla —lo que da un TLE— no necesita nada del llamante.

## Consecuencias

### Lo que este módulo cierra

- La promesa del docstring de `kepler.orbital_period_s` («los periodos nodal y
  anomalístico difieren de él en unos segundos por J2») tiene ahora dónde
  cumplirse: `SecularRates.nodal_period_s` y `.anomalistic_period_s`. Medido:
  −4.2 s a i = 51.6°, +7.2 s a i = 98°, y el nodal predicho concuerda con el
  tiempo nodo-a-nodo de la integración a 3e-4 relativo.
- `propagator.py` recibe la fuerza y las tasas; no tiene que decidir nada de
  esto.
- `constellations.py` recibe lo que necesita para SSO y traza repetida: la tasa
  nodal y el periodo nodal.
- La duplicación de `_as_1d`/`_as_vec3` entre `frames.py` y `kepler.py` se cortó
  al necesitarse por tercera vez: viven en `orbits/_validation.py`.

### Lo que no cierra

- **Términos seculares de segundo orden** (`J2²`, `J4`). Ver arriba: falta el
  oráculo, no las ganas.
- **Transformación osculador↔medio** (Brouwer-Lyddane). Es la pieza que
  desbloquea lo anterior, y **también** el modo analítico de `propagator.py`, que
  sin ella no puede devolver un estado utilizable ([ADR 0005](0005-propagation.md)).

  **Corregido:** este punto decía además que era «la misma que `tle.py`
  necesitará para no confundir los elementos medios de un TLE con los osculadores
  de `kepler.py`». Eso está sobredimensionado y contradecía al ADR 0006. Un TLE se
  propaga con SGP4, cuyo `Satrec.sgp4_array` devuelve **posición y velocidad en
  TEME** — estado osculador — porque SGP4 ya hace por dentro la transformación de
  medios a estado, términos de período corto incluidos. Así que el camino
  TLE → posición no pasa por ninguna pieza nuestra de Brouwer-Lyddane. Lo que
  `tle.py` necesita no es una transformación sino la **disciplina** de no construir
  un `ClassicalElements` con los elementos medios de un TLE, que es lo que la
  bandera del ADR 0006 hace cumplir. Y si algún día hiciera falta interpretarlos
  directamente, Brouwer-Lyddane genérico tampoco serviría: harían falta las
  convenciones concretas de SGP4 (Kozai, WGS-72), que son otra pieza.
- **Arrastre atmosférico**, presión de radiación, tercer cuerpo. Ninguno es
  gravedad zonal y ninguno entra aquí.
- **Armónicos teselares** (`J22` y compañía). Rompen la simetría axial, que es
  justo lo que permite que este módulo no necesite un argumento de marco. El
  nombre del módulo dice «zonal» por eso.
- **Un oráculo externo** (GMAT/Orekit) para las tasas seculares. Sigue declarado
  como hueco en `tests/golden/README.md`; el integrador interno lo suple para el
  primer orden pero no aportaría nada nuevo hasta que entre el segundo.

## Alternativas descartadas

**Implementar las tasas de segundo orden igualmente, marcadas como no
validadas.** Es la opción que más se parecía a cumplir el roadmap. Se descarta
porque el proyecto ya tiene una regla para esto y es la buena: código no
ejercitado es código que no funciona, y un número «validado» que no traza a V2 o
V3 no puede reportarse como validado (`tests/golden/README.md`).

**Tres juegos de componentes cartesianas transcritas.** Es lo que hacen casi
todos los libros. Se descarta por superficie de error; y la forma general se
comprueba contra la transcrita en los tests, así que no se pierde la referencia.

**Sacar el integrador a `propagator.py`.** Habría dejado a `perturbations.py`
sin su propio oráculo y a la teoría secular sin nada contra lo que medirse dentro
del módulo que la define. El roadmap ya lo ponía aquí.

**Detectar el paso por el nodo dentro del módulo.** El evento de cruce vive en
los tests, donde es el mecanismo de medida, no una función pública. Sacarlo a
`src/` habría hecho que el oráculo compartiera código con lo que mide.

## Referencias

- `notes/ROADMAP.md` — Etapa 2.1.3
- [ADR 0001](0001-unit-conventions.md) — unidades
- [ADR 0002](0002-frames-and-time-scales.md) — marcos, y la regla de firma del
  `DegradationLog`
- [ADR 0003](0003-orbital-elements.md) — elementos; el aviso sobre elementos
  medios que este ADR hereda
- `tests/golden/README.md` — los cuatro niveles, y cuándo un oráculo V3 no se
  congela
- Vallado, *Fundamentals of Astrodynamics and Applications*, 4.ª ed., 2013,
  §8.6 y §9.6
- Brouwer, «Solution of the problem of artificial satellite theory without
  drag», *Astron. J.* 64, 378-397, 1959
- Kozai, «The motion of a close earth satellite», *Astron. J.* 64, 367-377, 1959
- Montenbruck & Gill, *Satellite Orbits*, Springer, 2000, §3.2

# ADR 0003 — Elementos orbitales, anomalías y casos degenerados

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Etapa:** 2.1 (`orbits/kepler.py`)
- **Afecta a:** `perturbations.py`, `propagator.py`, `tle.py`, `constellations.py`,
  `geometry.py` y el esquema de escenario de la etapa 4. Cualquier módulo que
  hable de una órbita en vez de una posición.

---

## Contexto

El [ADR 0002](0002-frames-and-time-scales.md) fijó *dónde* está un satélite. Este
fija *qué órbita sigue*. Son seis números, y hay más de una forma razonable de
elegirlos; la que se elija aquí la heredan todos los módulos de arriba, porque un
propagador devuelve elementos y un escenario los escribe.

Cuatro tensiones reales:

1. **Los seis elementos clásicos no están siempre definidos.** Una órbita
   circular no tiene periapsis, así que ω no existe. Una ecuatorial no tiene nodo
   ascendente, así que Ω no existe. Las dos ocurren en escenarios de verdad — una
   SSO escrita como `e = 0` en un YAML, una órbita ecuatorial de relay — y las
   dos hacen que la fórmula clásica divida por cero.
2. **La ecuación de Kepler es la única parte iterativa de la mecánica orbital de
   dos cuerpos**, y su fama es no converger justo donde más se la necesita. Un
   `ConvergenceError` en mitad de un barrido de 10⁵ evaluaciones no es un error
   recuperable: es una figura que no sale.
3. **`a` o `p` como elemento de tamaño.** La literatura usa los dos; Vallado
   `RV2COE` devuelve los dos y `COE2RV` recibe `p`.
4. **Ángulos envueltos o no.** Un ν envuelto a `[0, 2π)` es lo canónico, pero
   convierte una serie propagada en un diente de sierra e invalida cualquier
   interpolación que la cruce.

El coste de equivocarse es el mismo de siempre en este proyecto: no da un error,
da una curva plausible y desplazada.

## Decisión

**Solo órbitas elípticas. `p` como elemento primario. Kepler en forma cerrada,
sin iterar. Las conversiones de anomalía conservan el número de vueltas; `rv_to_coe`
envuelve. Los ángulos indefinidos se *pliegan* en el siguiente que sí lo está, y
el pliegue se reporta con una bandera.**

| Cuestión | Elección |
| -------- | -------- |
| Rango de excentricidad | `0 <= e < 1`. `DomainError` fuera |
| Elemento de tamaño | semi-latus rectum `p`, con `a` como propiedad derivada |
| Ecuación de Kepler | Markley 1995, forma cerrada + cascada de tres correcciones |
| Anomalías `M <-> E <-> nu` | conservan las vueltas |
| Salida de `rv_to_coe` | todo ángulo envuelto a `[0, 2 pi)` |
| Circular (`e < 1e-11`) | `argp = 0`; `nu` pasa a ser el argumento de latitud |
| Ecuatorial (`\|sin i\| < 1e-11`) | `raan = 0`; `argp` pasa a ser la longitud del periapsis |
| Marco | `Frame` viaja en los elementos; ITRF y ENU se rechazan |
| Osculador/medio | añadido después: `ElementType` viaja igual que `Frame` — ver [ADR 0006](0006-osculating-vs-mean-elements.md) |
| `DegradationLog` | ninguna función lo recibe |

## Justificación

### Por qué solo elípticas

La formulación por variables universales cubre las cuatro cónicas con una sola
expresión, y es la respuesta "correcta" de libro. Se descarta porque **nada en
este proyecto la validaría**: QuOSS simula satélites en órbita ligada, no sondas
de escape, así que no habría ni un caso de prueba hiperbólico con significado
físico. Código no ejercitado es código que no funciona. Una `e >= 1` en un
escenario es una errata, y como errata se trata.

### Por qué `p` y no `a`

Tres razones, en orden de peso:

1. `rv_to_coe` lo obtiene directo de `h^2 / mu`, sin pasar por la energía. Un
   elemento que sale de una sola operación es un elemento con un error menos.
2. El Algorithm 10 de Vallado — el caso publicado que valida este módulo —
   **recibe `p`**. Tomar `a` obligaría a convertir la entrada del test, que es
   exactamente donde se cuela un error de transcripción.
3. `p` se mantiene finito cuando `e -> 1`, donde `a` diverge. Hoy no importa
   porque `e >= 1` se rechaza, pero no cuesta nada dejar la puerta abierta.

`a` se expone como propiedad derivada, y `from_semi_major_axis` es la vía por la
que entra un escenario, porque una altitud da `a`, no `p`.

### Por qué Kepler en forma cerrada

`notes/LAST_CHANGES.md` planteaba «arranque de Markley/Danby + Halley con
iteraciones fijas». Al implementarlo resultó que **no hace falta la parte
iterativa**: el método de Markley es la solución cerrada de una cúbica seguida de
una cascada de tres correcciones (Newton, Halley y una de tercer orden) que
comparten una sola evaluación de seno y coseno. Medido sobre 20 001 puntos por
excentricidad, el residuo `|E - e sin E - M|` no pasa de **1.4e-15 rad** para
toda `e` hasta 0.9999.

Consecuencia práctica: **no hay bucle, así que no puede no converger**. El coste
es el mismo para una órbita circular que para `e = 0.99`, lo que importa cuando
el solver está dentro de un barrido.

Aun así la función **comprueba su propio residuo** en cada llamada y levanta
`ConvergenceError` si lo excede. No es un criterio de convergencia — no hay nada
que converja — sino una post-condición: si alguna vez se dispara, significa que
la expresión cerrada se evaluó fuera del régimen en que su autor la demostró.
Cuesta un seno más sobre los cuatro que ya hace, y hay un test que la ejerce
apretando el umbral por debajo del suelo de máquina, para que la rama exista de
verdad y no lance `NameError` el día que importe.

**El matiz que hay que decir en voz alta:** el residuo es absoluto en anomalía
*media*, y `dM/dE = 1 - e cos E`. Cerca del periapsis de una órbita muy excéntrica
esa derivada se hunde, así que el error en `E` es el residuo dividido por `1 - e`
— unos 1e-11 rad a `e = 0.9999`. A las excentricidades de LEO o SSO es 1e-15 y no
se nota, pero está escrito en el docstring porque es invisible de otra forma.

### Por qué las anomalías conservan las vueltas

Si `E(M + 2πk)` devolviera `E(M)`, una serie propagada sobre varias órbitas sería
un diente de sierra: el gráfico tendría saltos falsos y cualquier interpolación
que cruzara una vuelta daría un valor sin sentido. Conservar `k` cuesta un
`floor` y una resta.

`rv_to_coe` no puede hacer lo mismo porque **no tiene historia**: recibe un
estado, no una trayectoria, y no hay ninguna vuelta que conservar. Ahí la
convención es la clásica, `[0, 2π)`.

### Por qué plegar los ángulos degenerados y no devolver `nan`

Las alternativas eran tres:

|                             | `nan` en el ángulo indefinido | Ángulos especiales aparte | **Plegado + bandera (elegida)** |
| --------------------------- | ----------------------------- | ------------------------- | ------------------------------- |
| `coe_to_rv` reconstruye el estado | no, propaga `nan`        | solo si el llamante ramifica | **sí, exacto** |
| Cuántos campos tiene la estructura | 6                       | 9                         | 6 |
| El llamante tiene que ramificar   | sí, siempre             | sí, para saber cuál leer  | solo si le interesa la etiqueta |
| El ángulo indefinido se distingue de un cero real | sí | sí        | sí, por la bandera |

El plegado es **sin pérdida para el estado**: en la posición y la velocidad solo
entran sumas como `ω + ν` y `Ω + ω`, así que meter el ángulo indefinido en el
siguiente deja los vectores intactos — verificado a 15 nm sobre una pila que
mezcla los cuatro casos. Lo único que se pierde es la *etiqueta* de un ángulo que
nunca fue medible, y para eso están `is_circular` e `is_equatorial`.

Devolver `nan` habría sido más "honesto" en apariencia y peor en la práctica: el
`nan` viaja hasta la primera figura y allí ya nadie sabe de dónde salió.

### Por qué el umbral es 1e-11 y no el 1e-8 habitual

Medido, no elegido. Tanto el vector excentricidad como el vector nodo se
construyen restando cantidades comparables, así que arrastran un suelo de ruido
absoluto de unas pocas veces el épsilon de `float64`: **3e-16** medido sobre un
estado generado de elementos exactamente circulares, y exactamente cero para el
módulo del nodo en uno ecuatorial.

El umbral tiene que estar donde la *dirección* de esos vectores deja de llevar
información. A `e = 1e-11` la dirección del periapsis tiene una incertidumbre de
`3e-16 / 1e-11 = 3e-5` rad, y crece como `1/e` hasta pasar el miliradián sobre
`e ~ 3e-13`. Con 1e-11 se pliega solo cuando el ángulo ya no significa nada.

El 1e-8 convencional plegaría una órbita LEO "circular" real — una efemérides da
`e ~ 1e-4` a `1e-6` — perdiendo un argumento de periapsis perfectamente medible.
Hay un test que fija ese caso.

### Por qué `ClassicalElements` no es un `dataclass`

Un `__init__` generado tiene que declarar **un** tipo por campo, y aquí los dos
papeles del campo no coinciden: se *acepta* `float | FloatArray` para que un
escenario se lea como un escenario, y se *almacena* siempre `FloatArray` de la
longitud común. Anotar la unión empuja a cada consumidor una rama para un caso
que ya no puede existir cuando `__init__` retorna — justo la erosión del contrato
de arrays contra la que avisa `core/types.py`.

La clase se escribe a mano: `__init__` por palabra clave, `__slots__`, y seis
propiedades de solo lectura que devuelven `FloatArray`. Permisiva al entrar,
estricta al salir. Cuesta unas cuarenta líneas de propiedades y ahorra un `cast`
en cada llamante durante el resto del proyecto.

### Por qué el marco viaja en los elementos

Un conjunto de elementos referido a un marco que rota no es un conjunto de
elementos. `ClassicalElements` lleva un `Frame` y rechaza `ITRF` y `ENU` con
`DomainError`, así que la confusión es irrepresentable en vez de estar
documentada. Es el mismo movimiento que el enum del ADR 0002, un nivel más
arriba.

## Consecuencias

### Lo que este módulo cierra

- El propagador de la etapa 2.1.4 no tiene que decidir nada de esto: recibe
  elementos etiquetados y devuelve estados etiquetados.
- `tle.py` hereda el aviso que ya estaba en el roadmap — los elementos medios de
  un TLE son de Brouwer-Lyddane con corrección de Kozai, **no** estos — y ahora
  tiene dónde ponerlo: pasando `WGS72_MU_KM3_S2` y sin construir un
  `ClassicalElements` con ellos. **Actualizado:** ese aviso dejó de ser solo un
  aviso; el [ADR 0006](0006-osculating-vs-mean-elements.md) lo convierte en un
  `ElementType` que viaja dentro y que `coe_to_rv` y `secular_rates_j2`
  comprueban.
- El esquema de escenario de la etapa 4 tiene su contrato: `a`, `e`, `i`, `Ω`,
  `ω`, `ν` en grados en el YAML, convertidos en `scenario/io.py`, entrando por
  `from_semi_major_axis`.

### Lo que no cierra

- **Elementos equinocciales.** Son la respuesta estructural a la degeneración:
  seis parámetros sin singularidad para ninguna órbita. No entran ahora porque
  añaden una segunda representación que mantener sincronizada, y el plegado
  resuelve el problema real (que el estado sobreviva) sin ese coste. Si algún día
  entra un optimizador de constelaciones que derive respecto a los elementos,
  este es el sitio donde volver.
- **Trayectorias no ligadas.** Ver arriba.
- **La ecuación de Kepler cerca de `e = 1`.** Funciona, pero la precisión en `E`
  se degrada como `1/(1-e)`. Documentado, no corregido: no hay escenario QuOSS
  que llegue ahí.

### Lo que la verificación V2 encontró

Los ejemplos resueltos de Vallado (4.ª ed., 2013) entran aquí como el **primer
dato V2 del proyecto**, y eso cierra el hueco que `tests/golden/README.md`
declaraba abierto. Tres hallazgos, todos registrados en el propio test en vez de
absorbidos en una tolerancia:

1. **Ejemplo 2-1 reproduce a 1e-14 rad**, las quince cifras que imprime el libro.
   Es la aserción V2 más apretada del proyecto, y lo es porque la fuente es
   exacta. Además se comprueba que el `E` publicado satisface `M = E - e sin E`
   sin consultar el código bajo test, que es lo que detectaría una transcripción
   mal copiada.
2. **La inclinación del Ejemplo 2-5 no cuadra con su último dígito impreso.** El
   estado publicado da 87.86913°, y el libro imprime 87.870°. La diferencia,
   0.00087°, es 1.7 veces el medio dígito que tres decimales permiten, y es la
   única magnitud del ejemplo que excede su propio redondeo. Se deja anotada con
   su número en vez de ensanchar la tolerancia hasta que pase: un test V2 cuyo
   límite se afloja hasta que pasa ha dejado de ser V2. Los seis elementos
   reconstruyen el estado publicado a menos de un micrómetro, así que la
   inclinación es consistente con todo lo demás.
3. **Los Ejemplos 2-5 y 2-6 no son un viaje de ida y vuelta.** Los elementos de
   entrada del 2-6 son los del 2-5 redondeados a dos decimales, y esa caja de
   redondeo admite ±1.3 km de posición. Lo que el 2-6 licencia de verdad es 1.3 km;
   lo que se mide son 25 m. Las dos cosas se asertan por separado, porque solo la
   primera es una afirmación V2 y la segunda es una guarda de regresión. El
   estado perifocal intermedio, que depende solo de `p`, `e` y `ν`, sí cuadra a
   0.1 m — lo que localiza los 25 m en la rotación, donde el libro arrastra menos
   cifras de las que imprime.

Una cuarta observación ya no queda como hallazgo abierto: la fuente de la que se
transcribieron los ejemplos daba también `u = 145.60549°` como argumento de
latitud del 2-5. La página escaneada (Vallado, p. 116) confirma ese número
impreso y revela **dos errores en la propia página**:

1. `|r|` se usa como `11456.67 km` en la sustitución, cuando el valor correcto
   calculado antes en el mismo ejemplo es `11456.57 km` (transposición 57 → 67).
2. Evaluando la expresión impresa con ese `|r|` erróneo se obtiene `145.7194°`,
   no `145.60549°`. No existe ninguna definición de `u` que recupere el número
   impreso.

El valor correcto es `u = 145.720087380597°`, confirmado por `ω + ν` y por la
fórmula vectorial. `u = 145.60549°` queda registrado como errata documentada de
Vallado 4.ª ed., y el test `test_argument_of_latitude_errata` lo afirma.

### El oráculo V3, y por qué no está congelado

`perturbations.py` iba a ser la referencia independiente de este módulo, pero
llega después. Mientras tanto la hace **SciPy**: `DOP853` integrando
`r'' = -mu r / |r|^3` es una implementación independiente de la misma física —
nada de lo que hace se parece a la ecuación de Kepler ni a la base perifocal — y
cierra la cadena entera de una vez, `rv_to_coe -> advance_mean_anomaly ->
true_from_mean_anomaly -> coe_to_rv`, que ningún test de función suelta puede
hacer.

A diferencia de los datos de astropy, este oráculo **no se congela a fichero**.
La regla 1 de `tests/golden/README.md` existe para que CI no dependa de la red ni
de una dependencia opcional; SciPy ya es dependencia del núcleo, el integrador es
determinista, y la comparación se hace a una tolerancia tres órdenes de magnitud
más floja que el error propio del integrador, así que un cambio de versión no
puede moverla. Lo que un fichero congelado protege — una referencia que cambia
sin avisar — no aplica a un solver cuya exactitud la fija un argumento explícito.

## Alternativas descartadas

**Newton o Halley iterativos con tope de iteraciones.** Era el plan anotado. Se
descarta porque la forma cerrada llega a precisión de máquina sin bucle, así que
el tope de iteraciones y su `ConvergenceError` serían código muerto que solo
puede fallar.

**Devolver `nan` en los ángulos indefinidos.** Ver la tabla de arriba.

**Nueve elementos, con los ángulos especiales como campos aparte.** Es lo que
hace la implementación de referencia de Vallado (`arglat`, `truelon`, `lonper`
junto a los seis, con `999999.1` como centinela). Se descarta por el centinela:
un valor numérico que significa "no aplica" es un `nan` con peor disfraz, y
obliga al llamante a saber cuál de los nueve campos leer antes de poder leer
ninguno.

**Elementos equinocciales como representación primaria.** Ver arriba.

**`arccos` con test de cuadrante para recuperar los ángulos.** Es la forma en que
está escrito el Algorithm 9. Se descarta por condicionamiento: `arccos` pierde la
mitad de sus cifras significativas cuando su argumento se acerca a ±1, que es
justo donde está una órbita casi ecuatorial o casi circular — las que este ADR
existe para tratar bien. En su lugar cada ángulo sale de un `arctan2` sobre un
seno y un coseno explícitos, con el seno construido como producto triple contra
el momento angular, que además fija el cuadrante sin una rama aparte.

## Referencias

- `notes/ROADMAP.md` — Etapa 2.1
- `notes/LAST_CHANGES.md` §7 — el planteamiento previo del solver de Kepler
- [ADR 0001](0001-unit-conventions.md) — unidades; `mu` en km³/s², ángulos en rad
- [ADR 0002](0002-frames-and-time-scales.md) — marcos, y la regla de firma del
  `DegradationLog` que este módulo hereda
- `tests/golden/README.md` — los cuatro niveles de verificación
- Vallado, *Fundamentals of Astrodynamics and Applications*, 4.ª ed., 2013,
  §2.2, §2.4-2.5, Algorithms 9 y 10, Ejemplos 2-1, 2-5 y 2-6
- Markley, «Kepler equation solver», *Celest. Mech. Dyn. Astron.* 63, 101-111, 1995
- Bate, Mueller & White, *Fundamentals of Astrodynamics*, Dover, 1971, cap. 2

# ADR 0007 — TLE y propagación SGP4: un módulo aparte, un enum que crece sin cablear, y una dependencia de terceros a la que no se le presta confianza gratis

- **Estado:** aceptada
- **Fecha:** 2026-09-10
- **Etapa:** 2.1 (`orbits/tle.py`)
- **Afecta a:** `orbits/propagator.py` (crece `PropagationMethod`),
  `geometry.py` y `constellations.py` (consumen el `Trajectory` que sale de
  aquí), y `system/passes.py`. El [ADR 0005](0005-propagation.md) dejó escrita
  la decisión de fondo — «`tle.py` no entra por `propagate`» — y el
  [ADR 0006](0006-osculating-vs-mean-elements.md) dejó preparado el tipo
  (`ElementType.MEAN_KOZAI_SGP4`) que esta pieza deliberadamente no usa. Este
  ADR es donde las dos promesas se cumplen.

---

## Contexto

### Qué es un TLE, desde cero

Un **TLE** («Two-Line Element set», juego de dos líneas de elementos) es el
formato con el que casi toda la comunidad de seguimiento de satélites —el
Comando Espacial de EE.UU., CelesTrak, y por tanto cualquier operador que
publique sus efemérides— distribuye la órbita de un objeto. Son literalmente
dos líneas de texto de 69 caracteres cada una, de columnas fijas, por ejemplo
para la ISS:

```
1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996
2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781
```

No son seis números cualesquiera: son los parámetros de entrada de un modelo
analítico concreto, **SGP4** («Simplified General Perturbations 4»), publicado
por Hoots y Roehrich en 1980 y descrito con detalle por Vallado, Crawford,
Hujsak y Kelso en *Revisiting Spacetrack Report #3* (AIAA 2006-6753). SGP4 no
es una curiosidad histórica: es la única forma correcta de convertir un TLE en
una posición, porque los seis números del TLE están ajustados —por quien los
publicó— **para ese modelo y ningún otro**. Meterlos en la mecánica de dos
cuerpos de `kepler.py`, o en las tasas seculares de `perturbations.py`, no da
un resultado peor: da un resultado que parece correcto y no lo es, que es
exactamente el modo de fallo que el README prohíbe.

### Por qué no se reimplementa

`notes/ROADMAP.md` §2.1.5 ya lo decía: «usar `sgp4`, no reimplementar». SGP4
tiene detrás cuarenta años de correcciones acumuladas —términos de resonancia
para órbitas cerca de 12 y 24 horas, un tratamiento especial del arrastre para
perigeos bajos, singularidades evitadas a mano en la excentricidad y la
inclinación crítica— que no aportan nada nuevo a este proyecto y sí un riesgo
real de introducir una discrepancia de kilómetros por una coma mal puesta.
Reimplementarlo sería gastar el presupuesto de riesgo del proyecto en volver a
escribir algo que ya existe, verificado, en el índice de PyPI. Por eso
`sgp4>=2.23` entra en `pyproject.toml` como dependencia **del núcleo**, no de
un extra: un TLE sin propagador para leerlo no sirve para nada, así que no
tiene sentido que sea opcional.

### Lo que ya estaba decidido y este ADR no reabre

Dos piezas de este módulo se decidieron **antes** de escribirlo, en los dos
ADR anteriores, y aquí solo se documentan como cerradas:

1. **`tle.py` no entra por `propagate()`.** Ya lo dice el ADR 0005, sección
   «Por qué la condición inicial son elementos y no un estado»: «Un TLE se
   propaga con SGP4, que devuelve estado en TEME directamente; construir un
   `ClassicalElements` con los elementos medios de un TLE es justo el error
   que el ADR 0003 y `notes/` llevan tres documentos avisando de no cometer.
   Un `propagate_tle` en su propio módulo es más honesto que un miembro más de
   este enum.»
2. **Nunca se construye un `ClassicalElements` con los elementos medios de un
   TLE.** El ADR 0006 dejó preparado el hueco para el día en que hiciera
   falta —`MEAN_KOZAI_SGP4`, sección «Subdecisión 2»— y explícitamente **no lo
   añadió** porque nada lo necesitaba todavía: «un miembro que ningún código
   puede producir es una etiqueta que solo invita a ponerla a mano». Ese día
   sigue sin llegar: `tle.py` no construye ningún `ClassicalElements`, ni
   osculador ni medio. La disciplina de este ADR es no hacerlo; no hace falta
   una guarda de tipos porque no hay ningún punto del código donde alguien
   pudiera intentarlo por accidente y que un tipo lo detuviera.

## Decisión

**`orbits/tle.py` añade dos funciones públicas, `parse_tle` y
`propagate_tle`, y un tercer miembro de `PropagationMethod`, `SGP4`, que
`propagate()` deliberadamente no sabe ejecutar. `parse_tle` valida lo que
`sgp4.api.Satrec.twoline2rv` no valida y usa siempre WGS-72. `propagate_tle`
construye su propio `TimeGrid` a partir de la época del TLE, nunca acepta uno
externo, y convierte tiempo transcurrido a fecha juliana partiendo la parte
fraccionaria para no perder precisión.**

| Cuestión | Elección |
| -------- | -------- |
| Punto de entrada | `parse_tle(line1, line2) -> Satrec`, `propagate_tle(satrec, t_s) -> Trajectory` |
| `PropagationMethod` | gana `SGP4 = "sgp4"`. `propagate()` sigue sin rama para él: pedirlo lanza `NotImplementedError` |
| `ClassicalElements` | `tle.py` no construye ninguno, ni osculador ni medio |
| Validación que `Satrec.twoline2rv` no hace | longitud y prefijo de línea, checksum, `satrec.error` tras la llamada — las tres con `DomainError` |
| Modelo de gravedad del `Satrec` | WGS-72 explícito, nunca WGS-84, aunque `sgp4` ya usa WGS-72 por defecto |
| Época de la trayectoria | la del TLE (`satrec.jdsatepoch + satrec.jdsatepochF`); no se acepta un `TimeGrid` externo con otra |
| Conversión tiempo transcurrido → JD | `(jd, fr)` con `fr` reducido a `[0, 1)` en cada muestra, no dejado crecer |
| Verificación V3 | los ficheros `SGP4-VER.TLE` / `tcppver.out` que trae el propio paquete `sgp4` (caso AIAA 2006-6753) |

## Justificación

### 1 — Por qué `tle.py` no entra por `propagate()`

Esto es una cita del ADR 0005, no una decisión nueva: se documenta aquí porque
es la primera pieza que hace la promesa real. La razón de fondo, dicha con la
norma de `CLAUDE.md`: `propagate()` recibe **osculadores** —la elipse que un
satélite seguiría *a partir de este instante* si la Tierra se volviera esfera,
tangente a la trayectoria real, definida en el ADR 0006— y los convierte en
estado con `coe_to_rv` o con la integración numérica. SGP4 no funciona así: su
entrada son los elementos **medios** de Brouwer con la corrección de Kozai
(1959), y su salida es directamente un vector de estado en TEME, con toda la
conversión de medio a osculador —incluidos los términos de período corto que
este proyecto no tiene, la pieza de Brouwer-Lyddane que el ADR 0006 deja
pendiente— ya hecha por dentro. No hay ningún punto intermedio donde un
`ClassicalElements` de este proyecto pudiera insertarse sin tirar precisión: o
se le dan a SGP4 los seis números del TLE tal cual, o el resultado deja de ser
la órbita que el TLE describe.

Por eso hay una función propia, `propagate_tle(satrec, t_s)`, con su propia
firma, en vez de forzar la entrada por `propagate(elements, grid, method=...)`.
La alternativa —aceptar `(r0, v0)` en `propagate()`— ya se descartó en el ADR
0005 por el mismo motivo: habría reabierto la confusión medio/osculador por
otra puerta.

### 2 — Por qué nunca se construye un `ClassicalElements` con elementos medios de un TLE

**Qué son los elementos medios de un TLE.** No son «unos elementos medios
cualesquiera»: son de la teoría de Brouwer con la modificación de Kozai, y
están referidos a las constantes de gravedad WGS-72. El ADR 0006 ya insistió
en que «medio» no es una cosa, es una por teoría — los que necesita
`secular_rates_j2` son de Brouwer-Lyddane, con EGM96. Son dos teorías
distintas que dan un significado distinto a los mismos seis nombres de campo.

**Por qué mezclarlos es el error de kilómetros que el ADR 0006 existe para
prevenir.** Si alguien tomara los seis números impresos en las líneas 2 de un
TLE — inclinación, RAAN, excentricidad, argumento del perigeo, anomalía
media, movimiento medio — y los metiera en un `ClassicalElements` etiquetado
`OSCULATING` (el defecto de la clase), `coe_to_rv` los aceptaría sin quejarse:
son seis números con la forma correcta, dentro de sus rangos válidos. Lo que
saldría sería un estado calculado como si esos números fueran la elipse
tangente a la trayectoria real en ese instante, cuando en realidad son la
elipse promedio con el bamboleo rápido ya restado. Es exactamente el error
medido en el ADR 0006: 86 km por vuelta y 1290 km al día para una SSO a 700
km, creciendo sin límite. `tle.py` nunca hace esa conversión porque nunca
construye el contenedor que la haría posible: los seis números del TLE viven
solo dentro del `Satrec` de `sgp4`, que sabe interpretarlos correctamente, y
salen de `tle.py` ya convertidos a estado (posición y velocidad), nunca como
elementos.

**Por qué no hace falta una guarda de tipos.** La disciplina que impide el
error no es un `if` en ningún sitio: es que el código de `tle.py`
simplemente no tiene ninguna línea que llame al constructor de
`ClassicalElements`. `MEAN_KOZAI_SGP4`, el miembro que el ADR 0006 dejó
previsto para este día exacto, **sigue sin usarse** — y sigue siendo correcto
que no se use, porque añadirlo hoy sería la misma trampa que el ADR 0006 ya
identificó para `PropagationMethod`: «un miembro que ningún código puede
producir es una etiqueta que solo invita a ponerla a mano». Si en el futuro
alguna pieza de QuOSS necesitara de verdad construir un `ClassicalElements` a
partir de los elementos medios de un TLE — por ejemplo, para compararlos
contra los medios de Brouwer-Lyddane una vez esa transformación exista — ese
es el momento de añadir el miembro y de escribir la guarda de tipos que haga
falta. Hoy esa necesidad no existe, y fingir la guarda sin la necesidad sería
código no ejercitado, que es exactamente lo que el ADR 0004 ya rechazó para
los términos seculares de segundo orden.

### 3 — `PropagationMethod` gana `SGP4`, y `propagate()` sigue sin saber ejecutarlo

Esta es la decisión más delicada del ADR, porque a primera vista parece
contradecir la anterior: si `tle.py` no entra por `propagate()`, ¿por qué
tocar el enum de `propagate()`?

**Qué es `Trajectory.method`, y por qué obliga la mano.** `Trajectory` es el
contenedor que sale tanto de `propagate()` como de `propagate_tle()` — los
mismos campos, arrays de posición y velocidad, una rejilla de tiempo, un
marco. Su campo `method` está tipado como `PropagationMethod` precisamente
porque es el campo que responde a la pregunta «¿cómo se produjo esta
trayectoria?», y esa pregunta la tiene que poder responder **cualquier**
`Trajectory`, no solo las que salen de `propagate()`. Si `propagate_tle`
devolviera un `Trajectory` con `method` puesto a algo que no fuera un
`PropagationMethod` de verdad —una cadena suelta, o dejando el campo con un
valor prestado de otro modo—, el mismo campo significaría cosas distintas
según de dónde viniera el objeto, que es el tipo de inconsistencia que la
auditoría del 2026-08-04 ya cazó una vez con `Frame` guardado como cadena
(`notes/LAST_CHANGES.md` §14.2).

**La alternativa obvia, y por qué se descarta.** Dejar `PropagationMethod`
intacto —tal como el ADR 0005 lo definió, con la lectura estricta de «qué
modelo sabe correr `propagate()`»— e inventar un tipo de campo distinto para
`Trajectory.method`, o una clase de trayectoria separada solo para SGP4. Esto
se descarta por dos razones, una de diseño y una de test ya escrito:

- Habría dos formas distintas de decir «cómo se produjo esto» en el mismo
  proyecto — un `PropagationMethod` para las trayectorias de `propagate()` y
  otra cosa para las de `propagate_tle()` — cuando ambas responden
  exactamente a la misma pregunta sobre el mismo tipo de contenedor.
- El test `test_the_enum_holds_exactly_the_implemented_modes` de
  `test_propagator.py` (ADR 0005) ya trata el enum como **el registro
  completo de procedencias que existen en el proyecto**, no como «lo que sabe
  ejecutar `propagate()`». Añadir una segunda taxonomía paralela habría hecho
  que ese test mintiera sobre lo que dice medir.

**La consecuencia que hay que aceptar por escrito.**
`propagate(elements, grid, method=PropagationMethod.SGP4)` **no funciona**.
`propagate()` sigue sin tener una rama para `SGP4` —no tiene sentido que la
tenga: SGP4 no toma un `ClassicalElements`, toma un `Satrec`, que es un objeto
completamente distinto construido por `parse_tle`— y su `else` de cierre, que
el ADR 0005 dejó escrito con el comentario `# pragma: no cover - unreachable
until the enum grows`, pasa a ser **alcanzable** ahora que el enum tiene un
tercer miembro. Eso es exactamente lo que se quería: pedirle a `propagate()`
el modo `SGP4` falla alto y claro con un `NotImplementedError`, no en
silencio y no con un resultado que parezca razonable.

**Las dos categorías de "por qué un miembro no corre en `propagate()`", y por
qué no hay que confundirlas.** El ADR 0005 dejó un enum incompleto a
propósito —`J2_SECULAR_ANALYTIC` no existe como nombre en ningún sitio,
porque construirlo hoy exigiría alimentarlo con osculadores y el resultado
sería el error de kilómetros del ADR 0006. Ese es un caso de **ausencia
total**: no hay ningún nombre que buscar. `SGP4` es un caso distinto,
**presencia con ruta propia**: el nombre existe, aparece en el enum, y es
**correcto** — simplemente vive en otra función. Confundir los dos sería un
error de lectura real: alguien que viera `SGP4` en el enum y dedujera que
`propagate()` debería saber ejecutarlo estaría cometiendo el mismo tipo de
error que alguien que buscara `J2_SECULAR_ANALYTIC` y no lo encontrara —
pero la reacción correcta es distinta en cada caso. Ante `J2_SECULAR_ANALYTIC`
ausente, la reacción correcta es «este modo no existe todavía en ningún
sitio». Ante `SGP4` presente pero fallando en `propagate()`, la reacción
correcta es «este modo existe, busco dónde» — y `NotImplementedError` en vez
de un `KeyError` de nombre desconocido es la pista que apunta en esa
dirección en vez de dejar al lector pensando que se equivocó de nombre.

El test que sostiene esto se divide en dos, siguiendo la misma disciplina que
ya usa el ADR 0005 para la incompletitud del enum: uno que sigue iterando
solo sobre los miembros que `propagate()` sabe ejecutar (`TWO_BODY`,
`ZONAL_NUMERIC`), y uno nuevo que confirma explícitamente que pedir `SGP4` a
`propagate()` da `NotImplementedError` y que la única vía que produce una
trayectoria con `method=PropagationMethod.SGP4` es `propagate_tle`.

### 4 — `parse_tle` valida lo que `Satrec.twoline2rv` no valida

**Por qué no basta con confiar en la librería de terceros.** El README es
explícito en que está «prohibido degradar en silencio», y esa regla no deja de
aplicar en la frontera con una dependencia externa: si `sgp4` acepta una
entrada corrupta sin avisar, el resultado sigue siendo un número plausible y
equivocado saliendo de este proyecto, y a quien lo mire no le va a importar
en qué línea de qué paquete se coló. Esto no es una sospecha: se comprobó
instalando `sgp4` en un entorno aparte y probándolo a mano, con la línea 1 de
la ISS de arriba.

**Trampa 1 — el checksum no se comprueba.** Cada línea de un TLE termina en un
dígito de control: la suma, módulo 10, de todos los caracteres de las columnas
1 a 68, contando cada `-` como 1 y cualquier otro carácter no numérico como 0.
Corrompiendo el último carácter de la línea 1 de la ISS (el propio dígito de
checksum) y llamando a `Satrec.twoline2rv` con la línea corrupta: **se acepta
sin ningún error**. El checksum es la única defensa contra un TLE truncado a
mitad de transmisión o editado a mano por error, y `sgp4` simplemente no lo
mira.

**Trampa 2 — la entrada basura no lanza excepción.** Llamando
`Satrec.twoline2rv("garbage", "more garbage")`: no se lanza nada. Devuelve un
objeto con `satnum=0` y dentro, **en silencio**, deja puesto
`satrec.error == 2` — un código de `sgp4.api.SGP4_ERRORS`, que en esa
tabla significa «nm is less than zero» (el movimiento medio calculado salió
negativo, señal inequívoca de que la entrada no era un TLE). Nadie lo ve si no
se comprueba a propósito: el flujo normal de Python sigue adelante con un
`Satrec` que parece un objeto válido.

**Lo que `parse_tle` hace en consecuencia, las tres con `DomainError`:**

1. Valida longitud (69 caracteres) y prefijo (`'1 '` / `'2 '`) de cada línea,
   antes de pasarla a `sgp4`.
2. Recalcula el checksum de cada línea y lo compara contra el dígito impreso
   en la columna 69.
3. Comprueba `satrec.error` inmediatamente después de llamar a
   `Satrec.twoline2rv`, y lo traduce a un mensaje legible en vez de dejarlo
   dormido en un atributo que nadie mira.

Es el mismo principio que ya aplica la tabla de decisión del ADR 0005 — «un
default silencioso es peor que un nombre ausente» — aplicado esta vez a una
dependencia de terceros en vez de al propio código: una librería que no avisa
es, para quien la envuelve, indistinguible de un `except: pass` propio si no
se comprueba lo que deja sin decir.

### 5 — WGS-72 explícito, nunca WGS-84

**Qué es el modelo de gravedad de un `Satrec`, y por qué importa cuál.** SGP4
necesita una constante de gravitación (`mu`) y el radio ecuatorial de la
Tierra para su aritmética interna, igual que `ZonalGravity` los necesita en
`perturbations.py`. `Satrec.twoline2rv(line1, line2)` sin tercer argumento usa
por defecto el modelo **WGS-72** — comprobado en el mismo entorno de prueba:
`mu = 398600.8 km³/s²`, idéntico a pasar `WGS72` de forma explícita, y
distinto de `WGS84`, que da `mu = 398600.5 km³/s²`. La diferencia entre las
dos, 0.3 km³/s², parece pequeña, pero no es una elección de estilo: **es parte
de la especificación de SGP4, no una decisión de quien lo usa**. Los seis
números de un TLE fueron ajustados por quien lo publicó usando precisamente
las constantes WGS-72 — es literalmente lo que dice el propio Spacetrack
Report #3 — así que evaluarlos con WGS-84 no da «una precisión ligeramente
distinta»: da una trayectoria calculada con una física ligeramente distinta de
aquella para la que los números fueron ajustados.

**Por qué se pasa explícito de todos modos, si el defecto ya es el
correcto.** Porque una TLE **se define** respecto a WGS-72, no **da la
casualidad** de que el defecto de la librería coincida con lo correcto hoy.
Confiar en que un defecto de una dependencia de terceros siga siendo el mismo
en la próxima versión mayor es exactamente el tipo de acoplamiento implícito
que este proyecto evita en su propio código — es el mismo argumento por el
que el ADR 0005 exige `method` obligatorio y sin default en `propagate()`. El
proyecto ya tiene la distinción hecha explícita en otro sitio:
`quoss.core.constants.WGS72_MU_KM3_S2` (= 398 600.8) existe precisamente
porque no es el valor de WGS-84, con el comentario «*Note: not the WGS-84
value*» ya en el propio fichero. Es la misma disciplina que separó
`EGM96_RADIUS_EQUATORIAL_KM` (6378.1363 km) de
`WGS84_RADIUS_EQUATORIAL_KM` (6378.137 km) en `perturbations.py` — 0.7 m de
diferencia, tres radios para tres propósitos (geodesia WGS-84, gravedad
EGM96, SGP4 WGS-72), documentado en `notes/LAST_CHANGES.md` §8. `parse_tle`
pasa `gravity_model=WGS72` explícito a `Satrec.twoline2rv` por la misma razón
por la que `perturbations.py` obliga a declarar qué juego de constantes se
está usando: un número correcto por casualidad de hoy es un número que puede
dejar de serlo en la próxima actualización de una dependencia sin que nada lo
avise.

### 6 — La época del TLE es la única época posible

**Por qué `propagator.py` sí acepta un `TimeGrid` externo y `propagate_tle`
no.** Un `ClassicalElements` no lleva su propia época: son seis números —
tamaño, forma, orientación, posición en la órbita— sin ninguna noción de
«cuándo». Por eso `propagate()` necesita que el llamante se la dé dentro de
un `TimeGrid`, y el ADR 0005 lo hizo obligatorio precisamente para que el
defecto de SimulCTTC —caer en silencio a `datetime.utcnow()`— fuera
irrepresentable. Un `Satrec`, en cambio, **ya lleva su época dentro**:
`satrec.jdsatepoch + satrec.jdsatepochF` es la fecha juliana exacta a la que
se refieren los seis elementos del TLE, y viene fijada por quien publicó el
TLE, no por quien lo usa.

**Qué pasaría si se aceptara un `TimeGrid` externo, y por qué eso es peor que
la asimetría.** Si `propagate_tle(satrec, grid)` aceptara un `TimeGrid` ya
construido por el llamante, con su propio `epoch_jd`, se abriría la puerta a
construir uno con una época **distinta** de la del TLE. El resultado sería
una `Trajectory` cuyo `grid.epoch_jd` **mentiría** sobre a qué instante están
referidos los elementos que la generaron — exactamente el tipo de estado
irrepresentable que este proyecto prefiere cerrar por construcción, no con
una comprobación en tiempo de ejecución que alguien podría olvidar añadir.
Es el mismo espíritu que «unos elementos en un marco que rota no son unos
elementos» del ADR 0002, o que el propio `ElementType` del ADR 0006: la forma
de la API es la que impide el error, no un aviso al lado. Por eso
`propagate_tle(satrec, t_s)` construye internamente
`TimeGrid(epoch_jd=tle_epoch_jd(satrec), t_s=t_s)` y no deja ningún parámetro
por el que un llamante pudiera colar una época distinta.

### 7 — La conversión JD/segundos preserva precisión partiendo `fr`

**Qué es el par `(jd, fr)`, y por qué SGP4 lo pide así.** Un día juliano (JD)
es un número que ronda 2 460 000 hoy — un `float64` tiene 52 bits de mantisa,
así que un número de esa magnitud solo puede representar tiempo con una
resolución de microsegundos, no porque el reloj sea impreciso sino porque los
bits que sobran para la parte entera del número (siete dígitos ya gastados en
«2460000») son bits que ya no están disponibles para la parte decimal. SGP4
recibe el tiempo partido en dos: `jd`, la parte entera del día juliano, y
`fr`, la parte fraccionaria — literalmente porque la documentación del propio
paquete (`sgp4.conveniences.jday_datetime`) dice que la segunda cifra «can,
unlike the first float, be accurate down to very small fractions of a second»
cuando se mantiene pequeña. Un `fr` pequeño (siempre `< 1`) no compite por
mantisa con ningún dígito de la parte entera del día, así que conserva toda
su precisión.

**Qué hace `propagate_tle`, y por qué no es solo `fr = jdsatepochF +
t_s/86400`.** Para cada muestra de `t_s` (segundos transcurridos desde la
época del TLE, que puede ser negativo o cubrir muchos días):

```
whole_days = floor(satrec.jdsatepochF + t_s / 86400)
jd = satrec.jdsatepoch + whole_days
fr = satrec.jdsatepochF + t_s / 86400 - whole_days
```

de modo que `fr` se queda siempre en `[0, 1)`, sin importar cuántos días de
`t_s` hayan transcurrido. La forma ingenua —dejar
`fr = satrec.jdsatepochF + t_s / 86400` crecer sin límite y no tocar `jd`—
funciona igual de bien el primer día, pero a medida que `t_s` crece, `fr`
también crece más allá de 1, 2, 30... y entonces vuelve a ser un número
grande compitiendo por los mismos bits de mantisa que se querían liberar
pasando el tiempo como dos números en vez de uno. Restar `whole_days` en cada
muestra es lo que mantiene `fr` pequeño **durante toda la propagación**, no
solo en la muestra `t_s = 0`.

**Medido, no asumido, en `tests/orbits/test_tle.py::TestJdFrSplitPrecision`:**
propagando la misma TLE de la ISS a `t_s = 30 días` por las dos vías —
partiendo `fr` como arriba, y dejándolo crecer sin normalizar— la diferencia
en posición y en velocidad es **exactamente cero, hasta el último bit de un
`float64`**, no solo «pequeña». La lectura honesta no es que la normalización
sobrara: es que esta build concreta de `sgp4` (la extensión C compilada,
`vallado_cpp.abi3.so`) ya reduce `jd + fr` internamente en doble precisión
antes de operar con ello, así que ninguna versión futura de esa dependencia
está obligada a seguir haciéndolo igual. Partir `fr` sigue siendo lo correcto
por higiene y por ceñirse al contrato que la propia documentación de `sgp4`
declara (`jday_datetime`, citada arriba) — no porque este test pueda medir un
error que hoy no existe.

### 8 — La verificación V3 llega gratis

**Qué son `SGP4-VER.TLE` y `tcppver.out`, y por qué son un oráculo V3 legítimo
sin necesitar congelarse aparte.** El paquete `sgp4` de PyPI trae, dentro de
su propio directorio instalado, los dos ficheros de datos oficiales del caso
de verificación estándar de la industria: `SGP4-VER.TLE` (los TLE de prueba)
y `tcppver.out` (la salida de referencia, calculada con la implementación C++
original), del artículo AIAA 2006-6753 de Vallado, Crawford, Hujsak y Kelso,
*Revisiting Spacetrack Report #3* (2006). `tests/golden/README.md` ya
establece las tres condiciones bajo las que un oráculo V3 no necesita
congelarse aparte en `tests/golden/data/` con su propio manifest —el mismo
argumento que ya se usó para el integrador DOP853 de `perturbations.py`
(`notes/LAST_CHANGES.md` §8): dependencia del núcleo, determinista, y
comparado muy por encima de su propio error. Los tres se cumplen aquí:
`sgp4` ya es dependencia obligatoria (§ «Por qué no se reimplementa» arriba),
la comparación numérica entre dos ejecuciones de SGP4 sobre el mismo TLE es
determinista bit a bit, y el propio README del paquete cita que su versión
Python pura concuerda con la referencia C++ a 0.1 mm — una cota que
`notes/LAST_CHANGES.md` §2 ya recoge como «verificado como disponible».

**Medido en `tests/orbits/test_tle.py::TestAgainstVallado2006VerificationData`**,
sobre cuatro regímenes (LEO de bajo arrastre, LEO de arrastre moderado, tipo
Molniya con `e = 0.6877`, y un caso de decaimiento fuerte): el peor residuo de
posición es **7.3e-9 km** (7.3 micrómetros) y el peor de velocidad **7.7e-10
km/s** (0.77 micrómetros por segundo). Esto no compara dos implementaciones de
SGP4 independientes — el C++ de referencia de Vallado y la llamada a
`Satrec.sgp4_array` de este módulo son, para lo que aquí importa, la misma
teoría evaluada dos veces — así que lo que se mide no es una diferencia física
sino el redondeo del propio fichero de texto: `tcppver.out` imprime la
posición a 8 decimales (p.ej. `7022.46529266`), una resolución de 1e-8 km, y
el residuo medido es consistente con ese redondeo, no con un error de
implementación. Las tolerancias del test, 1e-7 km y 1e-8 km/s, quedan un orden
de magnitud por encima de lo medido: suficientemente ajustadas para que una
constante de gravedad equivocada o un split jd/fr transpuesto fallasen por
muchos órdenes de magnitud, y suficientemente holgadas para no repetir el
propio redondeo del fichero ASCII.

## Consecuencias

### Lo que este módulo cierra

- **Un TLE se puede leer y propagar** sin pasar por ninguna pieza de física
  propia que no esté preparada para sus elementos, y sin reimplementar SGP4.
- **La trampa de tipos que el roadmap avisaba de no cometer** —construir un
  `ClassicalElements` con los elementos medios de un TLE— queda cerrada por
  disciplina de diseño: `tle.py` sencillamente no tiene ninguna línea que
  pudiera cometerla.
- **`PropagationMethod` pasa a ser, de verdad, el registro completo de
  procedencias del proyecto**, no solo de las que sabe ejecutar `propagate()`
  — con la distinción entre ausencia total (`J2_SECULAR_ANALYTIC`) y
  presencia con ruta propia (`SGP4`) dicha explícitamente para que nadie las
  confunda.
- **La verificación V3 de SGP4 no cuesta nada nuevo**: viene versionada junto
  al paquete que había que instalar de todos modos.

### Lo que no cierra

- **`MEAN_KOZAI_SGP4` sigue sin usarse.** Sigue siendo correcto que no se use:
  nada en el proyecto construye hoy un `ClassicalElements` a partir de los
  elementos medios de un TLE, y añadir el miembro sin un consumidor sería la
  misma trampa que el ADR 0006 ya evitó una vez.
- **Brouwer-Lyddane sigue sin existir**, y este ADR no la finge en ningún
  sentido: SGP4 no la necesita (hace su propia conversión medio→osculador por
  dentro, con las convenciones de Kozai/WGS-72), así que este módulo no
  desbloquea ni necesita esa pieza. Sigue siendo condición de entrada,
  exclusivamente, del modo analítico de `propagator.py` y de los términos
  seculares de segundo orden — el acoplamiento con `tle.py` que
  `notes/LAST_CHANGES.md` §13 («El acoplamiento BL ↔ `tle.py` que el roadmap
  afirma está sobredimensionado») ya corrigió por escrito.
- **`geometry.py`.** `propagate_tle` deja una `Trajectory` con
  `frame=Frame.TEME`, exactamente como las de `propagate()`, así que
  `geometry.py` puede consumir cualquiera de las dos sin distinguir de dónde
  vino — pero `geometry.py` en sí (elevación, azimut, slant range, Doppler,
  ángulo de point-ahead) no existe todavía.

## Alternativas descartadas

**Un cuarto argumento en `propagate()`, algo como `propagate(satrec, grid,
method=PropagationMethod.SGP4)`.** Habría exigido que `propagate()` aceptara
dos tipos de primer argumento completamente distintos (`ClassicalElements` o
`Satrec`) según el `method`, lo que rompe la firma que el ADR 0005 fijó y
comprueba con un test sobre `inspect.signature`. Descartada por la misma razón
por la que el ADR 0005 ya rechazó «Aceptar `(r0, v0)` en lugar de elementos»:
mezclar el camino del TLE con el de `propagate()` reabre la confusión
medio/osculador por otra puerta.

**Dejar `PropagationMethod` con dos miembros y que `propagate_tle` devuelva
una cadena suelta o un tipo nuevo para `Trajectory.method`.** Descartada en la
sección 3 de arriba: habría dado dos formas de decir «cómo se hizo esto» en el
mismo proyecto, y habría hecho mentir al test que ya trata el enum como el
registro completo de procedencias.

**No validar lo que `Satrec.twoline2rv` no valida, y confiar en que la
mayoría de los TLE de producción (CelesTrak, Space-Track) ya vienen bien
formados.** Cierto para la mayoría de los casos de uso, pero el propio README
del proyecto no admite excepciones de «la mayoría de los casos»: un checksum
que falla en silencio es indistinguible, desde fuera, del `except: pass` que
el README prohíbe explícitamente, y la comprobación cuesta unas pocas líneas
frente al riesgo de propagar un TLE corrompido sin que nadie se entere.

**Confiar en el defecto de `Satrec.twoline2rv` para el modelo de gravedad, ya
que hoy coincide con WGS-72.** Descartada en la sección 5: un defecto de
tercero que hoy es correcto es un acoplamiento implícito con la versión
instalada de esa dependencia, y el propio proyecto ya rechazó ese patrón para
sí mismo en el ADR 0005 (`method` sin default).

## Referencias

- `notes/ROADMAP.md` — Etapa 2.1.5
- `notes/LAST_CHANGES.md` §13 («Para el siguiente módulo (`tle.py`)» y «El
  acoplamiento BL ↔ `tle.py` que el roadmap afirma está sobredimensionado»)
- [ADR 0002](0002-frames-and-time-scales.md) — `Frame`, y la regla de que
  unos elementos en un marco que rota no son unos elementos
- [ADR 0003](0003-orbital-elements.md) — los seis elementos y el aviso, ya de
  tres documentos, sobre los elementos medios de un TLE
- [ADR 0005](0005-propagation.md) — `PropagationMethod`, `Trajectory`, y la
  decisión ya tomada de que `tle.py` no entra por `propagate()`
- [ADR 0006](0006-osculating-vs-mean-elements.md) — `ElementType`, la tabla
  de kilómetros del desajuste medio/osculador, y `MEAN_KOZAI_SGP4` previsto y
  aún sin usar
- `tests/golden/README.md` — los cuatro niveles de verificación, y las tres
  condiciones bajo las que un oráculo V3 no necesita congelarse
- Hoots, Roehrich, *Spacetrack Report #3*, 1980
- Vallado, Crawford, Hujsak, Kelso, «Revisiting Spacetrack Report #3», AIAA
  2006-6753, 2006
- Kozai, «The motion of a close earth satellite», *Astronomical Journal* 64,
  367-377, 1959
- Brouwer, «Solution of the problem of artificial satellite theory without
  drag», *Astronomical Journal* 64, 378-397, 1959

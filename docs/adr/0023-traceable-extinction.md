# ADR 0023 — Extinción trazable: la visibilidad como entrada, y una unidad mal impresa en la UIT

- **Estado:** aceptada
- **Fecha:** 2026-09-15
- **Etapa:** 2.2 (`channel/`), etapa 1.1 del plan de fases.
- **Afecta a:** `channel/extinction.py` (nuevo), `channel/link_budget.py`
  (docstring del módulo), `channel/horizontal.py` (docstring),
  `scenario/models.py` (`ExtinctionSpec`, `ChannelSpec`), `engine/pipeline.py`.
- **Extiende** al [ADR 0009](0009-citation-policy.md): tres fuentes nuevas
  abiertas, el **hueco 14 estrechado y no cerrado**, y dos huecos nuevos (22, 23).

---

## Contexto

### Qué es la extinción, para quien llegue nuevo

La luz que cruza aire pierde potencia de dos maneras que **no** tienen nada que
ver con la turbulencia. La **absorción** es una molécula que se come un fotón y
lo convierte en calor. La **dispersión** es una molécula o una partícula en
suspensión que lo manda en otra dirección. Las dos juntas son la **extinción**:
luz que salió del transmisor y no llega al receptor, desaparecida en vez de
simplemente movida.

La distinción importa porque el canal de QuOSS ya modelaba las otras dos cosas y
son distintas:

- La **turbulencia** reordena la luz. Un fotón que se va por escintilación este
  milisegundo vuelve el siguiente, y por eso su efecto es una *distribución* con
  media uno (`channel/turbulence.py`, `channel/pointing.py`).
- La **nube** no es una pérdida, es una **caída del enlace**: el pase no existe
  (`system/pcflos.py`, [ADR 0013](0013-cloud-availability-and-station-aggregation.md)).
- La **extinción** es una pérdida seca, constante mientras el aire no cambie, y
  multiplicativa con todo lo demás.

Se mide como **atenuación específica**, decibelios por kilómetro de camino. La
ley de Beer-Lambert dice que la pérdida en decibelios crece linealmente con la
longitud, así que una atenuación específica por una longitud es una pérdida; y
una columna vertical de aire tiene un número propio, la **transmitancia
cenital** `L_zen`, la fracción de luz que sobrevive hacia arriba a través de toda
la atmósfera. Es la base de la Ec. (7) de Ntanos et al., `L_a = L_zen^(1/cos ζ)`.

### Por qué esto era un hueco y no una omisión

El [ADR 0009](0009-citation-policy.md) declaró el **hueco 14** con esta forma
exacta: la **ley de escala está publicada y el número que escala no**. La Ec. (7)
de Ntanos et al. está numerada y es verificable; su `L_zen` no aparece en el
paper. Y la ITU-R P.1621-2 —la fuente primaria del canal— publica la absorción
(§2) y la dispersión (§3) **solo como figuras**: las Figs. 1, 2 y 4 son gráficas,
sin tabla ni forma cerrada al lado. Leer un valor de una curva y presentarlo como
publicado es exactamente lo que esa política prohíbe.

La consecuencia fue una firma: `zenith_transmittance` es argumento **obligatorio
y sin defecto** de `atmospheric_transmittance` y de `downlink_loss_budget`, y
`extinction_db_per_km` lo es de `horizontal_loss_budget`
([ADR 0021](0021-horizontal-path.md) §4). Quien no tiene extinción escribe `1.0`
y con eso lo declara.

**Y todos los escenarios de `scenarios/` escriben `1.0`.** Es decir: todas las
cifras que este proyecto ha producido hasta hoy son para un aire que no absorbe
ni dispersa. Eso era honesto y era, además, caro — sin medir cuánto.

### Lo que el hueco 14 no vio

El hueco 14 se escribió mirando dos documentos: Ntanos et al. y la P.1621-2. Hay
una **tercera recomendación de la UIT**, la P.1814, que ya estaba en la tabla de
fuentes del ADR 0009 (por su Ec. (8) de escintilación y su Tabla 4), y su §4.2.1
imprime una forma cerrada, numerada, para el término dominante. Buscar de nuevo
antes de escribir código fue lo que la encontró.

---

## Decisión

**Un módulo nuevo, `channel/extinction.py`, que calcula la extinción a partir de
la visibilidad con la ley que la ITU-R P.1814 publica, con las dos leyes de
exponente que existen expuestas como elección sin defecto, y con la absorción
molecular declarada hueco porque ninguna fuente abierta publica un número.**

### Las fuentes: cuáles se abrieron, cuáles no, y en qué versión

Por la regla del ADR 0009, esto va primero y con la versión.

| Documento | Versión | ¿Abierta? | Qué se usa |
|---|---|---|---|
| **ITU-R P.1814** | 08/2007 | **Sí**, PDF de la UIT | §4.1 (frase sobre absorción), §4.2.1 **Ecs. (4) y (5)**: la ley de visibilidad |
| **ITU-R P.1817-1** | 02/2012 | **Sí**, PDF de la UIT | §3 **Ecs. (3) y (4)** (dispersión molecular), §12 **Ec. (12)** (Koschmieder) y la tabla del *International visibility code* |
| **Kim, McArthur & Korevaar 2001**, *Proc. SPIE* 4214:26 | — | **Sí**, manuscrito que aloja el segundo autor | **Ecs. (5), (6), (9)** y **Tablas 2 y 4** |
| **ITU-R P.1621-2** | 07/2015, con enmiendas editoriales de 2026 | **Sí**, PDF de la UIT | §2 y §3: **confirmado que solo son figuras**. El hueco 14 dice la verdad |
| **Gruneisen et al. 2021**, *PRApplied* 16, 014067 | arXiv:2006.07745 | **Sí** | §III A: el cociente MODTRAN 775/1550 nm y su `η_trans` |
| **HITRAN** | hitran.org, 2026-09-15 | **Responde, y no sirve** | Ver el hueco 23 |
| **MODTRAN** | — | **No.** Es software de pago | Solo a través de lo que Gruneisen et al. publican de sus corridas |
| **Andrews & Phillips** | — | **No** (hueco 1) | Nada |

**Sobre HITRAN, porque la pregunta era explícita.** `hitran.org` responde
(HTTP 200) y su base de líneas requiere cuenta registrada para descargar. Pero
el problema de fondo no es el registro: **una lista de líneas no es una
atenuación específica**. Convertir una en la otra es un cálculo de transferencia
radiativa de la clase LBLRTM/MODTRAN —perfiles de presión, temperatura y mezcla,
ensanchamiento por colisión y Doppler, continuos— que este proyecto no tiene y
que habría que verificar a su vez. Implementarlo a medias para poner un número
es precisamente lo que el ADR 0009 prohíbe. Así que la absorción molecular queda
**hueco 23**, con lo que dicen las dos fuentes que sí se abrieron: que es
despreciable en las ventanas que usa un enlace óptico, **sin número**.

### La ley, y la unidad que la P.1814 imprime mal

La **visibilidad** (o alcance visual) está *definida* como la distancia a la que
la luz cae al 2 % de su potencia, y se registra cada hora en todos los
aeropuertos del mundo. Invertir la definición da el coeficiente de extinción a
550 nm, la longitud de onda a la que la visibilidad se define (P.1817-1 §12):

```
exp(-σ·V) = 0.02   ⇒   σ(550 nm) = ln(1/0.02) / V = 3.912 / V
```

La P.1817-1 Ec. (12) imprime esa relación de Koschmieder con **3.912**; la
P.1814 Ec. (4) y Kim et al. Ec. (6) imprimen **3.91**. La diferencia es
**0.051 %** —0.0001 dB/km en aire muy claro— y el código usa 3.91, que es la
constante de la ecuación que implementa y de las dos tablas contra las que se
comprueba.

Escalar a otra longitud de onda necesita un exponente, y esa es la Ec. (4):

```
σ(λ) = (3.91 / V) · (λ / 550 nm)^(-q)
```

**Y aquí está la trampa que da forma al módulo: la Ec. (4) de la P.1814 dice que
`γ_fog(λ)` está en dB/km, y lo que devuelve está en nepers por kilómetro.** Son
un factor 4.343 — **9.9 dB/km en una niebla de 1 km**, o 10.6 dB/km a 785 nm.

Esto no se afirma, se demuestra con dos tablas publicadas:

- La **Tabla 2 de Kim et al.**, calculada por sus autores desde esa misma
  ecuación, imprime **14 dB/km** a 1 km de visibilidad y 785 nm, donde la
  ecuación devuelve 3.175. `4.343 × 3.175 = 13.79`.
- La tabla del *International visibility code* de la **P.1817-1 §12** imprime
  **13.8** en el mismo punto.

Es decir: una recomendación de la UIT contradice la etiqueta de unidad de otra
recomendación de la UIT, y el paper del que las dos toman la ecuación está del
lado de la segunda. El texto se leyó **renderizando la página 5 como imagen**,
no del extractor de texto, porque una etiqueta de unidad es justo lo que un
extractor estropea; la afirmación está asertada en
`tests/channel/test_extinction.py::TestTheUnitOfEquationFour`, con el 4.343 fijado
desde las dos tablas para que "arreglar" el módulo a la unidad impresa falle.

Ni Kim et al. declaran la unidad de su `σ`, así que el sub-hueco de unidades se
resuelve por las tablas de ambos y no por una frase.

### Las dos leyes de exponente, y por qué la elección no tiene defecto

`VisibilityScalingLaw` tiene dos miembros y **ningún defecto**, por la misma
razón que `PathWave` no lo tiene ([ADR 0021](0021-horizontal-path.md) §3).

| | `ITU_P1814` | `KIM_2001` |
|---|---|---|
| `V > 50 km` | 1.6 | 1.6 |
| `6 < V < 50 km` | 1.3 | 1.3 |
| `1 < V < 6 km` | `0.585 V^(1/3)` | `0.16 V + 0.34` |
| `0.5 < V < 1 km` | `0.585 V^(1/3)` | `V − 0.5` |
| `V < 0.5 km` | `0.585 V^(1/3)` | **0** |

La de la izquierda es la de Kruse, que es la que imprimen tanto la P.1814
Ecs. (4)-(5) como la Ec. (6) de Kim et al. La de la derecha es la **corrección
que Kim et al. proponen** en su Ec. (9), y su argumento no es una preferencia:
los datos a los que Löhle ajustó `0.585 V^(1/3)` se tomaron «en niebla y bruma
densa», que Middleton ya había marcado como dudosos por debajo de 1 km, y las
medidas que sí existen en niebla real no muestran dependencia con la longitud de
onda. Físicamente: una gota de niebla mide varios micrómetros, veinte veces una
longitud de onda, que es el régimen **no selectivo** donde vale la óptica
geométrica y el color no puede importar (Tabla 1 de la propia P.1814:
`Q ~ λ^0` para `r >> λ`).

**Lo que la elección decide, medido.** A 50 m de visibilidad:

| | 785 nm | 1550 nm | ventaja de 1550 |
|---|---|---|---|
| `ITU_P1814` | 314.6 dB/km | 271.7 dB/km | **42.9 dB/km** |
| `KIM_2001` | 339.6 dB/km | 339.6 dB/km | **0** |

Es una decisión de hardware —«¿compro 1550 nm porque atraviesa la niebla?»— y
las dos respuestas están publicadas. Por eso está en la firma.

### Las discontinuidades de la ley, y una que se come un residuo publicado

La Ec. (5) de la P.1814 imprime desigualdades **estrictas**, así que `V = 6` y
`V = 50` no pertenecen a ninguna rama. El módulo lee los intervalos
**semiabiertos hacia arriba** —`[6, 50)` con 1.3 y `[50, ∞)` con 1.6— y eso no
es una moneda al aire: la tabla de la P.1817-1 imprime **0.19 dB/km** en
exactamente 50 km, que es el valor de `q = 1.6` (0.192) y no el de `q = 1.3`
(0.214).

**Dos de las cuatro uniones son saltos, y solo en una de las dos leyes.** La
tercera rama de la P.1814 llega a `0.585 · 6^(1/3) = 1.063` donde la siguiente
empieza en 1.300: un escalón del **22.3 %** en `q`, que a 1550 nm son **21.8 %**
de atenuación específica (0.941 → 0.736 dB/km). La Ec. (9) de Kim et al. quita
ese salto —`0.16·6 + 0.34` es exactamente 1.3, y sus uniones en 500 m y 1 km son
exactas también— y su paper lo dice: la Ec. (9) «transitions better to a q value
of 1.3». Ninguna de las dos quita el salto de 50 km, del 23.1 %.

**El escalón hace inalcanzables algunos valores, y uno de ellos es un número que
este proyecto cita.** A través de una capa de aerosol de 1.2 km de altura de
escala a 1550 nm, **ninguna visibilidad produce una pérdida cenital entre 0.883
y 1.129 dB**. Y el residuo de **0.906 dB** del presupuesto de 20 dB de Ntanos et
al. —el que el hueco 14 lee como `L_zen = 0.812`— cae dentro de esa ventana. El
valor alcanzable más cercano está a **0.021 dB**, y es el de **6 km de
visibilidad**: lo que la propia tabla de la P.1817 llama *light fog*, no aire
claro.

Con el otro extremo del rango de la literatura, 2 km de altura de escala, el
residuo sí es alcanzable y corresponde a **9.8 km de visibilidad**: bruma
tampoco, pero no el cielo despejado que implica un «best case».

**Así que la frase del ADR 0009 —«una transmitancia cenital de cielo claro
perfectamente ordinaria»— no sobrevive a tener un modelo detrás.** Sigue siendo
cierto que el residuo es de tamaño plausible; deja de ser cierto que sea de
cielo claro. La compatibilidad se mantiene, la etiqueta cambia. Está corregido en
el ADR 0009 y asertado en
`tests/channel/test_extinction.py::TestAgainstPublishedZenithTransmittances`.

Y la monotonía tiene el mismo carácter condicional: la ley es decreciente en la
visibilidad **solo por encima de 550 nm**. Por debajo, `(λ/550)^-q` crece con
`q`, el salto hacia arriba en 6 km invierte el orden, y a 400 nm aclarar el aire
**empeora** la atenuación un **7.8 %**. Ningún enlace óptico opera ahí, y por eso
es un test con control negativo y no una nota: es la parte de la ley que
descubriría un lector del código, no un usuario.

### La columna vertical: la forma es un convenio, la altura de escala un hueco

Los aerosoles viven en la capa límite —los pocos kilómetros de aire que el suelo
remueve— y su concentración cae aproximadamente de forma exponencial con la
altura. Escribiendo `β(h) = β_v exp(-(h - h_v)/H)`, con `h_v` la altitud a la que
se midió la visibilidad y `H` la **altura de escala** (la altura en que el
aerosol se diluye en un factor `e`), la integral desde la estación hacia arriba es

```
τ = β_v · H · exp(-(h_s - h_v) / H)
```

Dos consecuencias que hay que tener presentes antes de leer un número:

1. **Si la visibilidad se midió en la estación, la altitud se cancela
   exactamente** y `τ = β·H`. Es el caso ordinario —una estación meteorológica o
   un aeropuerto informa de su propia visibilidad— y es la razón por la que
   `visibility_altitude_m` es un argumento **separado** y obligatorio: la *otra*
   lectura, una visibilidad climatológica de nivel del mar aplicada a un sitio de
   montaña, es una profundidad óptica muy distinta, y nada en una cifra de
   visibilidad dice cuál de las dos es. Con 23 km al nivel del mar y `H = 1.2 km`,
   la OGS del Teide a 2390 m se queda con `exp(-1.99) = 0.137` de la columna:
   **0.031 dB contra 0.230**.
2. **Ninguna fuente abierta publica `H`.** Los valores en uso van de unos 1.2 a
   2 km, y eso es un factor **1.67** en profundidad óptica —0.230 contra 0.384 dB
   a 23 km de visibilidad y 1550 nm—, más grande que varios de los términos que
   este módulo existe para añadir. Es el **hueco 22**, y por eso el argumento no
   tiene defecto.

La altitud es altura sobre el elipsoide WGS-84, la misma `StationSpec.altitude_m`
que el [ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md) fijó para la
integral de turbulencia. El geoide está a unos 50 m del elipsoide en Europa, que
son un 4 % de una altura de escala de 1.2 km y **0.009 dB** a 23 km de
visibilidad: menos que la incertidumbre de la propia altura de escala, y dicho
aquí en vez de dejado como ejercicio.

### El esquema: dos formas de declarar la extinción, y ninguna tercera

`ChannelSpec` acepta **exactamente una** de dos cosas, con la misma forma que
`BackgroundSpec` ya usaba para la radiancia:

- `zenith_transmittance`, un número del que responde quien escribe el escenario;
- `extinction`, un `ExtinctionSpec` con visibilidad, altitud de la visibilidad,
  altura de escala y ley.

Declarar las dos se rechaza, y declarar ninguna también. Un defecto en
cualquiera de las dos sería una atmósfera inventada hecha autoritativa por
ocupar una posición en una firma, que es la forma exacta en que el hueco 14 se
cerraría por accidente.

La conversión vive **en el esquema**, donde viven todas
([ADR 0014](0014-scenario-contract-and-provenance.md)):
`ChannelSpec.zenith_transmittance_at(wavelength_m=, station_altitude_m=,
degradations=)` devuelve el número declarado tal cual, o lo calcula con el
modelo. Es un **método y no una propiedad** porque necesita dos cosas que viven
en otros modelos —la longitud de onda del transmisor y la altitud de la
estación—, y el motor es quien las junta. Eso tiene una consecuencia útil: con
una visibilidad declarada al nivel del mar, **un escenario multi-estación da tres
atmósferas distintas a tres estaciones** desde una sola declaración.

---

## Lo que esto mide

### El término que el presupuesto recibía vale un quinto del día

Escenario de referencia, Castelldefels, misma órbita, misma máscara de 10°, misma
tabla de pases. Lo único que cambia es `zenith_transmittance`, de `1.0` a lo que
el modelo devuelve para una visibilidad declarada y medida en la estación, con
`H = 1.2 km` y la ley de Kim et al. La descomposición es la del
[ADR 0022](0022-the-strong-regime.md): `x = mean(ln T)`, `y = ln(bits)`,
`E = dy/dx`.

| Aire sobre Castelldefels | `L_zen` | cenital | `dx` (canal) | `E` (cota) | `dy` (clave) | bits/día |
|---|---|---|---|---|---|---|
| ninguno (lo de hoy) | 1.0 | 0 dB | — | — | — | **433 442** |
| 23 km, «very clear air» | 0.9483 | 0.230 dB | −15.6 % | 1.52 | **−22.7 %** | 334 883 |
| 10 km, «clear» | 0.8851 | 0.530 dB | −32.3 % | 1.67 | **−47.7 %** | 226 583 |
| 2 km, «light mist» | 0.3061 | 5.142 dB | −97.7 % | — | **−100 %** | **0** |

Tres cosas que decir de esa tabla:

- **Un cuarto de decibelio cenital es un quinto del día.** 23 km de visibilidad
  es la línea más limpia del código meteorológico de la propia P.1817-1, y
  cuesta el 22.7 % de la clave certificada, porque `E = 1.52` y no 1.
- **La elasticidad no es una propiedad de la estación.** La misma Castelldefels
  daba `E = 0.473` para una *ganancia* de escintilación en el ADR 0022. Es una
  derivada local de una cota con suelo en cero, medida aquí sobre un paso ocho
  veces mayor y en la otra dirección. Citar cualquiera de las dos como «la
  elasticidad de Castelldefels» sería reportar una tangente como una constante.
- **A 2 km de visibilidad el día no certifica nada** mientras el asintótico
  sigue reclamando 424 kbit. Es el patrón del
  [ADR 0011](0011-the-block-is-the-pass.md): el error de reportar lo asintótico
  no es un factor, es una división por cero.

`tests/e2e/test_reference_scenarios.py::TestWhatTheExtinctionModelIsWorth`.

### La identidad que hace seguro aterrizarlo

Una visibilidad de 1e300 km da **exactamente 1.0** —el `3.91/V` de la ley es un
cero verdadero, no un desbordamiento a cero— así que el escenario que modela aire
infinitamente limpio y el que declara `zenith_transmittance: 1.0` son **la misma
corrida, bit a bit**. `ENGINE_FINITE_DAY_BITS` no se movió, y por eso las 3 600
aserciones de igualdad exacta de `tests/e2e/` no hubo que reescribirlas.

### Verificación

- **V2, el anclaje fuerte:** las **32 celdas** de las Tablas 2 y 4 de Kim et al.
  —las dos leyes, sus dos longitudes de onda, tres órdenes de magnitud de
  visibilidad— reproducidas dentro de **media cifra impresa**, con la peor celda
  de cada tabla al **94 %** de esa tolerancia. La tolerancia es de la
  transcripción (una celda impresa como `0.4` dice `[0.35, 0.45)`), no ajustada.
- **Entre fuentes:** la tabla del *International visibility code* de la
  P.1817-1 §12, que **no dice su longitud de onda**, es la ley de la P.1814 a
  **785 nm**: sus 15 celdas se reproducen al **2.8 %** ahí, y al 2.1 % en la
  longitud de onda que mejor ajusta, 780.5 nm. Queda una dispersión del 2 % en
  cualquier longitud de onda, así que lo afirmable es «la misma ley cerca de
  780 nm», no «esta tabla se calculó a 785.0 nm». El control es 1550 nm, donde
  las mismas celdas se equivocan entre 1.16 y 2.94 veces.
- **V1:** monotonía (y su control negativo a 400 nm), el límite de visibilidad
  infinita exacto, las ramas del exponente, la continuidad de las uniones (que
  una de las dos leyes **no** cumple, con los dos saltos medidos), y el
  intervalo `(0, 1]` que el presupuesto exige.
- **Compatible, no reproducido:** el cociente MODTRAN de Gruneisen et al. Su
  «atmospheric transmission near zenith is about 90 % of that at 1550 nm» a
  775 nm fija, **sin necesitar la altura de escala**, una profundidad óptica
  cenital a 1550 nm de **0.0720 Np** (`L_zen = 0.9305`), porque 775 y 1550 son
  exactamente un factor dos y el cociente es `exp(-(2^q - 1) τ)`. El modelo lo
  reproduce a la visibilidad que ese cociente implica, **16.9 km**, bruma
  ordinaria. Lo que **no** cierra: la misma sección toma `η_trans = 0.9` a 780 nm,
  y las dos afirmaciones juntas exigen `L_zen(1550) = 1.000` exactamente, que no
  hace ninguna atmósfera; a la profundidad óptica que su cociente fija, este
  modelo pone 775 nm en **0.837** y no en 0.90.
- **Cobertura:** 100 % de líneas y ramas del módulo nuevo, 81 tests.

---

## Alternativas descartadas

- **Leer un valor de la Fig. 4 de la P.1621-2.** Es una gráfica de atenuación
  específica de Rayleigh y Mie a nivel del mar, y leer una curva y etiquetarla
  «publicada» es lo que el ADR 0009 existe para prohibir. Se abrió el documento
  para confirmarlo, no para leer la curva.
- **Poner un defecto de `L_zen = 0.9`** («un cielo claro cualquiera»). Es un
  número que nadie publica, y la tabla de arriba dice lo que costaría
  equivocarse en él: 0.230 contra 0.530 dB son 25 puntos de clave del día.
- **Corregir la dispersión molecular dentro de la ley de visibilidad.** Es el
  **hueco 22**: la visibilidad a 550 nm la fija la extinción *total*, moléculas
  incluidas, y la ley escala el coeficiente entero por un exponente de aerosol de
  1.3 o 1.6 donde la parte molecular va como la cuarta potencia. Medido: la parte
  molecular es el 3.1 % del coeficiente a 10 km de visibilidad y el **15.2 % a
  50 km**, y llevarla a 1550 nm con el exponente de aerosol deja el total **2.9 %
  alto a 10 km y 14.0 % alto a 50 km**. Restar a 550 y volver a sumar a `λ` no lo
  publica ninguna de las dos fuentes, así que no se hace: se mide.
- **Implementar la absorción molecular desde HITRAN.** Hueco 23, arriba.
- **Cambiar la firma de `atmospheric_transmittance` para que tome una
  visibilidad.** El trabajo de esa función es una línea de un presupuesto:
  transmitancia elevada a la masa de aire. El modelo necesita tres cosas que no
  pertenecen a la lista de argumentos de un presupuesto de enlace, y una de ellas
  sigue sin valor publicado.

---

## Consecuencias

### Lo que cierra

- **La extinción se puede calcular** desde una visibilidad —el dato
  meteorológico más disponible que existe— con una ley de la UIT abierta y
  numerada, y desde un fichero de escenario.
- **Pone número a lo que el hueco 14 costaba**: 22.7 % del día de referencia en
  el aire más limpio de la tabla de la UIT, el 100 % con bruma ligera.
- **Corrige una etiqueta del propio ADR 0009**: el residuo de 0.906 dB de
  Ntanos et al. no es «cielo claro ordinario», es 6 km de visibilidad —y a
  `H = 1.2 km` no lo produce ninguna visibilidad, porque cae dentro del salto de
  la ley.
- **Cierra la fila de la tabla de fuentes del ADR 0009** que decía «Extinción por
  visibilidad | Kim, McArthur & Korevaar 2001 | (6)» y no correspondía a ningún
  código, igual que el ADR 0022 cerró la de régimen fuerte.

### Lo que no cierra

- **Hueco 14, estrechado y no cerrado.** El término de aerosol tiene modelo; la
  absorción molecular no (hueco 23). `zenith_transmittance` sigue siendo
  obligatorio y sin defecto, y `1.0` sigue significando «declarado, no modelado».
- **Hueco 22 — la altura de escala y la dispersión molecular dentro de la ley.**
  Las dos medidas arriba.
- **Hueco 23 — la absorción molecular.** Dos fuentes dicen «despreciable» en
  palabras y ninguna imprime un número. Cerrarlo es un cálculo de transferencia
  radiativa, no una cita.
- **La distribución de la visibilidad.** Este módulo toma **una** visibilidad.
  Una afirmación de disponibilidad («el enlace cierra el 99 % del año») necesita
  la **distribución** horaria de visibilidad del sitio, que es lo que Kim et al.
  §3 describe como el uso normal de su Ec. (6) y lo que el archivo de la NOAA
  contiene. Es lo mismo que `io/openmeteo.py` hace con las nubes, y no está hecho
  para la visibilidad.
- **Niebla, lluvia y nieve como procesos.** La P.1814 publica leyes de lluvia
  (Ec. (6), con `k` y `α` por país) y de nieve (Ec. (7)), y la P.1817-1 repite
  las dos. No se implementan: un enlace QKD no opera bajo lluvia, y el modo de
  fallo relevante es la nube, que ya es una caída y no una pérdida.

---

## Referencias

- [ADR 0009](0009-citation-policy.md) — la política de citas, el hueco 14 que
  esto estrecha y los huecos 22 y 23 que añade.
- [ADR 0014](0014-scenario-contract-and-provenance.md) — por qué la conversión
  vive en el esquema.
- [ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md) — qué es
  `StationSpec.altitude_m`.
- [ADR 0021](0021-horizontal-path.md) — `extinction_db_per_km`, que ahora tiene
  de dónde salir.
- [ADR 0022](0022-the-strong-regime.md) — la descomposición `dx` / `E` / `dy`
  que esta entrada reutiliza.
- Recomendación UIT-R P.1814, *Prediction methods required for the design of
  terrestrial free-space optical links*, 08/2007.
- Recomendación UIT-R P.1817-1, *Propagation data required for the design of
  terrestrial free-space optical links*, 02/2012.
- I. I. Kim, B. McArthur y E. Korevaar, «Comparison of laser beam propagation at
  785 nm and 1550 nm in fog and haze for optical wireless communications»,
  *Proc. SPIE* **4214**:26, 2001.
- M. T. Gruneisen et al., «Adaptive-Optics-Enabled Quantum Communication: A
  Technique for Daytime Space-To-Earth Links», *Phys. Rev. Applied* **16**,
  014067, 2021.

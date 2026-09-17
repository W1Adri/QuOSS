# ADR 0022 — Régimen moderado-a-fuerte: un modelo compartido, y por qué **no** es el predeterminado

- **Estado:** aceptada
- **Fecha:** 2026-09-15
- **Etapa:** 2.2 (`channel/`), etapa 1.2 del plan de fases.
- **Afecta a:** `channel/turbulence.py` (`ScintillationRegime`, `PathWave`,
  `saturated_log_irradiance_variance`), `channel/horizontal.py`,
  `channel/link_budget.py` (`downlink_loss_budget`) y, desde el anexo del
  2026-09-15, `scenario/models.py` (`ChannelSpec.scintillation_regime`) y
  `engine/pipeline.py`.
- **Extiende** al [ADR 0009](0009-citation-policy.md): una fuente nueva y dos
  huecos nuevos (20, 21); cierra la parte de escintilación del hueco «régimen
  fuerte» que el [ADR 0021](0021-horizontal-path.md) dejó abierta.
- **Anexo del 2026-09-15:** la elección pasa a ser un campo del escenario, y el
  precio de cambiar el predeterminado queda medido. Al final del fichero.

---

## Contexto

### Qué es la saturación de la escintilación, para quien llegue nuevo

**Escintilación** es el parpadeo de una estrella: el aire caliente hace de lente
y la potencia que llega al detector fluctúa. Se mide con la **varianza de
log-irradiancia** `σ²_lnI`, en Np² («nepers al cuadrado» solo quiere decir que
el logaritmo es natural). 0.1 Np² son oscilaciones del 30 % en potencia.

Todo lo que QuOSS tenía hasta ahora es **teoría de Rytov de primer orden**: se
supone que la perturbación es pequeña, se calcula a primer orden, y sale la
**varianza de Rytov** `σ_R²`. Esa suposición se muerde la cola: el resultado
*es* la perturbación, así que cuando `σ_R²` se acerca a 1 la teoría está diciendo
que la perturbación es grande, es decir, que ella misma no valía.

Lo que hace el aire real cuando la turbulencia crece no es parpadear cada vez
más: **satura**. El haz se rompe en muchos moteados independientes, y añadir más
turbulencia añade más moteados, no moteados más profundos. La estadística tiende
a la del moteado plenamente desarrollado, cuyo **índice de escintilación**
`σ_I²` —la varianza relativa de la irradiancia, no de su logaritmo— vale 1. La
teoría de primer orden no puede ver eso, porque solo sabe multiplicar.

El coste concreto: en el día de referencia de QuOSS, a 10° de elevación, la
`σ_R²` de la Ec. (4a) de P.1622 llega a **1.48 Np²**. La saturación dice
**0.63**. Son **6.1 dB** de desvanecimiento al 1 % de outage que no existen.

### Por qué esto es una decisión y no un parche

Porque hay dos números defendibles para el mismo canal, y la elección mueve un
resultado de diseño. Las dos afirmaciones son ciertas a la vez:

- La Ec. (4a) de P.1622 es una **recomendación de la UIT, citable por número**,
  y es contra sus tablas que se anclan todas las verificaciones V2 del canal.
- Por debajo de 20° esa ecuación **sobreestima**, y por debajo de 20° es donde se
  decide la máscara de elevación.

---

## Decisión

1. **Un modelo, `saturated_log_irradiance_variance`, en `turbulence.py`.**
   Toma una varianza de Rytov y una `PathWave`, devuelve `σ²_lnI`:

   ```
   σ²_lnI = 0.49 s / (1 + c s^(6/5))^(7/6) + 0.51 s / (1 + 0.69 s^(6/5))^(5/6)
   ```

   con `s = σ_R²` y `c = 1.11` (plana) o `0.56` (esférica). Es exactamente el
   corchete de la Ec. (12) de Ntanos et al., que es `ln(1 + σ_I²)`; devolver el
   corchete y no `σ_I²` evita exponenciar para volver a tomar logaritmo.

2. **Se elige con `ScintillationRegime`, y el predeterminado es `WEAK`.** Ver
   «la decisión incómoda» abajo.

3. **`PathWave` se muda de `horizontal.py` a `turbulence.py`**, y se reexporta.
   El modelo lo necesita y lo comparten los dos caminos; dejarlo donde estaba
   habría hecho que `turbulence` importara de `horizontal`, que es la dirección
   contraria a la que tiene el paquete.

4. **La saturación se aplica a la varianza *de punto*, antes del promediado de
   apertura.** No en `_assembled_loss_budget`, que es donde el ADR 0021 dijo que
   iría: para cuando una varianza llega ahí ya está promediada, y las Ecs. (12) y
   (A9) son resultados de detector puntual. Lo que comparten la bajada y el
   camino horizontal es **el modelo**, no el punto de llamada.

5. **El aviso cambia de código, no desaparece.** Por encima de 1 Np² de `σ_R²`:
   `turbulence.weak-fluctuation-limit-exceeded` en `WEAK` (nombrando la
   alternativa) y `turbulence.scintillation-saturated` en `MODERATE_TO_STRONG`,
   con los dos valores y su cociente. El umbral está sobre `σ_R²` y no sobre la
   salida porque la salida saturada no puede llegar a 1 —su techo es 0.6948— así
   que probar la salida sería no avisar nunca.

### La decisión incómoda: el predeterminado sigue siendo `WEAK`

El modelo saturado **nunca es peor**: reduce a `σ_R²` a primer orden. Aun así el
predeterminado es `WEAK`, por una razón medida:

> En el punto que fija la Tabla 2 de la **ITU-R P.1622** —75° de elevación,
> estación a 5.5 m, 21 m/s— la `σ_R²` es 0.0659 Np² y el modelo saturado da
> 0.0636: **3.4 % por debajo**, en pleno régimen débil, donde quien aproxima es
> el ajuste heurístico y no la recomendación.

Poner el heurístico de predeterminado movería **todos** los anclajes V2 del
canal por una corrección que solo importa por debajo de ~20°, y convertiría
«este número es de la P.1622» en falso en todo el proyecto. La regla del ADR
0009 es que un número publicado se reproduce o se declara; no que se mejore en
silencio.

**Y el 3.4 % es la celda más favorable de las ocho, no el tamaño del efecto.**
Esa cifra es la de 1550 nm y 21 m/s, que es la longitud de onda de este
proyecto; a lo largo de la Tabla 2 el desplazamiento llega al **21.1 %** y
**seis de las ocho celdas** dejarían de reproducirse dentro de medio dígito
impreso. Está medido, celda a celda, en el anexo del final.

Lo que sí cambia es que la elección está **en la firma**, medida, y el aviso
nombra la otra opción. Elegir `MODERATE_TO_STRONG` para un estudio de máscara es
una línea.

---

## Cómo se comprueba (la defensa de las fuentes)

**Tres fuentes abiertas imprimen la misma ecuación, y una la imprime mal.**

| Fuente | Ecuación | Onda | Segundo exponente |
|---|---|---|---|
| **Ntanos et al. 2021**, *Photonics* 8(12):544 | (12) | plana | `5/6` |
| **Gruneisen et al. 2021**, *PRApplied* 16, 014067 (arXiv:2006.07745) | (A8), (A9) | plana y esférica | `5/6` |
| **Kaushal & Kaddoum**, arXiv:1506.04836 | (17) | plana | `7/6` |

Las tres citan a Andrews & Phillips, que es el **hueco 1** del ADR 0009 y no se
pudo abrir. Así que esto es V2 contra fuente secundaria, y decirlo es parte del
resultado.

Dos contra uno no es una razón, así que lo decide el límite: con el `7/6` que
imprime Kaushal & Kaddoum, el término de pequeña escala cae como `σ_R^(-4/5)` y
el índice «saturado» **decae a 0.031** con `σ_R² = 10 000`, donde el canal está
en su momento más violento. Un modelo de parpadeo que devuelve menos parpadeo
cuanto más turbulento el aire no es una diferencia de redondeo.

**El anclaje numérico, y por qué vale más de lo que parece.** Gruneisen et al.
imprimen «the maximum theoretical value for `σ_I² slant-path` is approximately
1.24». El modelo da **1.2432**, en `σ_R² = 10.31`. Ese máximo no es un
coeficiente que alguien tecleó: está donde el término de gran escala ya murió y
el de pequeña escala aún no se ha asentado, así que reproducirlo a tres cifras
ejercita **los dos cortes, los dos exponentes y la potencia de la varianza en
los dos denominadores** a la vez. Dos de esos cinco estaban mal en el primer
borrador de este módulo y ese aserto es lo que lo dijo:

- `σ_R^(12/5)` es la potencia de la **desviación típica**, así que en términos de
  la varianza es `s^(6/5)`. Escribir `s^(12/5)` deja todas las salidas finitas y
  positivas, y da un máximo de **0.71** en vez de 1.24.
- El `7/6` de Kaushal & Kaddoum da 0.60 y decae.

**Lo derivado, no ajustado.** La asíntota `0.51 / 0.69^(5/6) = 0.6948 Np²` sale
de los coeficientes, no de una medición; equivale a `σ_I² = 1.0033`, que es la
saturación a la unidad que describe la literatura de régimen fuerte. Y el límite
débil no tiene tolerancia elegida: los dos denominadores son `1 + c s^(6/5)`, así
que la desviación está acotada por `(7/6) max(c) s^(6/5)`, que a `s = 0.01` son
el 0.5 %.

**Entre fuentes, sobre la varianza de Rytov que alimenta al modelo.** La Ec. (13)
de Ntanos et al. y la (A4) de Gruneisen et al. imprimen `2.25`; la (4a) de
P.1622, `2.253`. Están a `1.3e-3`, dentro de lo que permiten tres cifras. Si las
dos ecuaciones significaran cantidades distintas, componerlas sería absurdo.

---

## Lo que esto mide (el resultado de la etapa 1.2)

### El óptimo interior de la máscara se mueve de 8° a 4.5°

Mismo día, misma órbita, misma tabla de pasos, mismo protocolo; lo único que
cambia es el régimen.

| Máscara | `WEAK` | saturado | cambio |
|---|---|---|---|
| 2° | 408 946 | 458 862 | +12.2 % |
| **4.5°** | 424 448 | **462 945** | +9.1 % |
| 5° | 426 988 | 462 936 | +8.4 % |
| **8°** | **434 938** | 457 663 | +5.2 % |
| 10° | 432 985 | 449 514 | +3.8 % |
| 20° | 360 978 | 364 740 | +1.0 % |

El óptimo sigue siendo **interior** y baja tres grados y medio; el día gana
**6.4 %**. El mecanismo es el mismo que crea el óptimo: una muestra baja aporta
fuga de corrección de errores más deprisa que sucesos de un fotón certificados, y
lo que la hace cara es su margen de desvanecimiento. Quitarle 6.1 dB a las
muestras más bajas hace que empiecen a pagarse solas.

El aumento es **monótono en lo bajo que esté la máscara**, +12.2 % a 2° contra
+1.0 % a 20°, que es la firma de que todo el efecto viene de las muestras bajas.

### Y se descompone en canal y cota, que no coinciden

Con `x = mean(ln T)` y `y = ln(bits del día)`, la elasticidad `E = dy/dx` de
`TestWhyTheHigherStationGainsLess` —escrita, literalmente, para este momento—:

| Estación | culmina | `dx` (canal) | `E` (cota) | `dy` (clave) |
|---|---|---|---|---|
| Castelldefels | 26° | **+7.90 %** | 0.473 | +3.66 % |
| Calar Alto | 21–37° | +3.05 % | **2.91** | **+9.12 %** |
| Teide OGS | 57–72° | +1.78 % | 0.673 | +1.20 % |

Los dos órdenes son **opuestos**. El canal de Castelldefels gana dos veces y
media más que el de Calar Alto, porque sus pasos son los más bajos del cielo; la
clave de Calar Alto gana dos veces y media más que la de Castelldefels, porque
Calar Alto está en el acantilado de certificación y amplifica por 2.91 mientras
los otros dos **amortiguan** (`E < 1`: más luz trae más detecciones, y la
corrección de errores se cobra sobre todas ellas mientras la amplificación de
privacidad solo certifica la parte de un fotón).

El número más grande que produce la etapa 1.2 en todo el día de referencia es el
segundo paso de Calar Alto, **+17.7 % de clave**, y es casi todo cota: su canal
solo mejora un 2.50 %, con `E = 6.60`. Citarlo sin `E` al lado sería reportar la
demostración de seguridad como si fuera la atmósfera.

### En el camino horizontal: la elección de onda valía cuatro veces menos

El ADR 0021 cita «21.7 contra 15.1 dB» a 5 km como lo que vale no saber si el
haz es plano o esférico: 6.67 dB, el número más grande de ese ADR. Con el modelo
saturado son **8.41 contra 9.94 dB**, y **el signo se invierte**: a 5 km la
`σ_R²` de la onda plana es 3.80 y la de la esférica 1.55, así que la saturación
le quita mucho más a la plana, y lo que queda es el promediado de apertura, que
favorece a la plana.

Es decir: **la mayor parte de esos 6.67 dB era el modelo débil evaluado cuatro
veces más allá de su propio límite**, no un coste real de no conocer el haz. El
hueco de la onda gaussiana (hueco 18) no desaparece —1.53 dB siguen siendo
1.53 dB— pero se estaba citando a cuatro veces su tamaño.

Y pone número a algo que el ADR 0021 decía en prosa: las dos celdas de la
columna «High» de la Tabla 4 de la P.1814 que la propia recomendación no debería
haber impreso valen **12.25 dB impresos contra 7.19 saturados**, y **16.00
contra 7.57**. Cinco y ocho decibelios y medio de desvanecimiento que no están.

---

## Alternativas descartadas

- **Poner `MODERATE_TO_STRONG` de predeterminado.** Movería los anclajes V2
  donde el heurístico es el que aproxima: entre el 3.4 % y el 21.1 % según la
  celda, y seis de las ocho de la Tabla 2 dejarían de reproducirse. Medido en el
  anexo, junto con las 84 aserciones que se pondrían rojas.
- **Meterlo en `_assembled_loss_budget`**, como prometía el ADR 0021. Ahí la
  varianza ya está promediada por apertura, y las Ecs. (12) y (A9) son de
  detector puntual. Saturar allí saturaría la cantidad equivocada.
- **Devolver `σ_I²` en vez de `ln(1 + σ_I²)`.** Las leyes de desvanecimiento
  toman la log-varianza; el viaje de ida y vuelta por `exp`/`log1p` solo pierde
  dígitos.
- **Seguir a Kaushal & Kaddoum (17) tal como está impresa.** Decae a cero en
  régimen fuerte. Ver arriba.
- **Cambiar también el promediado de apertura a la Ec. (15) de Ntanos et al.**
  Sería coherente con la (12), pero es un modelo distinto del de la P.1622 (una
  `ρ_I` con su propia forma), y mezclarlo a medias sería un tercer convenio que
  no imprime nadie. Declarado como hueco 21, con su número: 0.39 dB.

---

## Consecuencias

### Lo que cierra

- La parte de escintilación del «régimen fuerte» que el ADR 0021 dejó pendiente,
  para la bajada y para el camino horizontal, con la misma función.
- La fila de la tabla del ADR 0009 que decía «escintilación en régimen fuerte |
  Ntanos et al. 2021 | (12), (13)» y no correspondía a ningún código.
- Da número a dos afirmaciones que estaban en prosa: lo que sobreestiman las dos
  celdas de la Tabla 4 de P.1814, y lo que vale la elección de onda a 5 km.

### Lo que no cierra

- **El promediado de apertura en régimen saturado** (hueco 21). 0.39 dB a 10°.
- **La onda gaussiana** (hueco 18), ahora con su tamaño real: 1.53 dB a 5 km.
- **Escala interna y externa.** El modelo supone Kolmogorov sin escala externa
  finita, lo que lo hace una **cota superior** del valor saturado.
- **La distribución sigue siendo log-normal.** La Ec. (17) de Ntanos et al. usa
  log-normal y dice que vale para régimen débil y moderado. En régimen fuerte la
  irradiancia es gamma-gamma, y las colas —que es lo que un outage al 1 % lee—
  no son las mismas. La varianza que este ADR corrige es la correcta; la forma
  de la distribución con que se convierte en decibelios, no necesariamente.
- **Nada de esto es V2 de punta a punta.** Las cifras de clave de arriba son V4:
  salida propia de QuOSS sobre supuestos declarados.
---

## Anexo (2026-09-15): la elección es ahora un campo del escenario

Este ADR se aceptó con el modelo escrito y **sin cableado**: `ChannelSpec` no
tenía dónde declarar el régimen y `engine/pipeline.py` no lo pasaba, así que
todas las cifras de «Lo que esto mide» se obtuvieron llamando al canal, a la
tabla de pasos y al protocolo **a mano**, una máscara cada vez. Un resultado de
diseño que solo reproduce un script suelto es un resultado que nadie puede
volver a sacar de un fichero de escenario, y —peor— es un número que no entra en
la procedencia: dos días que se diferencian un 3.66 % compartirían hash.

### Lo que se añadió

6. **`ChannelSpec.scintillation_regime`**, con predeterminado `WEAK`, pasado a
   `downlink_loss_budget` desde `_channel`. El campo entra en el JSON canónico,
   así que entra en el SHA-256 del escenario y por tanto en
   `Provenance.scenario_hash` y en la clave de la caché de resultados. Los cinco
   `scenarios/*.yaml` lo escriben explícitamente aunque sea el valor por defecto,
   por la razón del ADR 0014: un defecto invisible es un parámetro que todo el
   mundo recibe sin haberlo elegido.

`SCHEMA_VERSION` **no** sube (caso 2 de `tests/scenario/test_hash.py`: campo
opcional nuevo, ningún fichero cambia de significado), y el digest de referencia
se repincha a `303a3729…`, con la entrada de `DIGEST_HISTORY` que lo demuestra
borrando exactamente ese campo.

### El día de referencia, ahora desde `run()`

Mismo escenario, mismo día, misma máscara de 10°; lo único que cambia es el campo:

| régimen | clave del día | pasos 1 y 3 | cambio |
|---|---|---|---|
| `weak` | 433 442 | 190 807 / 242 635 | — |
| `moderate-to-strong` | **449 308** | 198 673 / 250 635 | **+3.66 %** |

Y el barrido de máscara de la tabla de arriba es ahora **un `SweepSpec` de dos
ejes** (`passes.minimum_elevation_deg` × `channel.scintillation_regime`, modo
`grid`), ocho puntos, cada uno con su hash:

| máscara | `weak` | saturado | cambio |
|---|---|---|---|
| 2° | 409 584 | 458 076 | +11.8 % |
| **4.5°** | 425 073 | **462 358** | +8.8 % |
| 8° | **435 462** | 457 341 | +5.0 % |
| 20° | 361 199 | 364 774 | +1.0 % |

**Los dos óptimos sobreviven** —8° en débil, 4.5° saturado, los dos interiores—
y la ganancia sigue siendo monótona en lo baja que esté la máscara, que es la
firma de que el efecto vive en las muestras bajas. El titular de este ADR
—«el día gana 6.4 % en su propio óptimo»— sale **+6.18 %** por esta cadena
(462 358 contra 435 462), por la misma razón de los 30 m que la sección
siguiente mide.

### Por qué estas cifras no son las de la tabla de arriba, y por qué no hay tolerancia

La tabla de «Lo que esto mide» imprime 408 946 / 424 448 / 434 938 / 360 978 y
458 862 / 462 945 / 457 663 / 364 740: hasta **786 bits** de diferencia. No es
ruido ni tolerancia. Es el mismo desajuste del
[ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md): aquella tabla sale
de `tests/system/reference.py`, que deja el perfil de turbulencia en 0 m,
mientras que el motor cablea los **30 m** de `StationSpec.altitude_m`.

Así que no se compara contra una tolerancia elegida, se cierra por los dos
extremos, y los dos son exactos:

- las ocho celdas barridas **son** `oracle.hand_link` a 30 m, bit a bit;
- las ocho celdas publicadas **son** la misma cadena a 0 m, bit a bit;
- luego cada residuo **es igual** a `hand(30 m) − hand(0 m)`, celda a celda, y no
  queda nada que una tolerancia pudiera absorber.

### El residuo cambia de signo, y eso es física

Los 30 m valen **+457 bits** en régimen débil —el titular del ADR 0016— y
**−206 bits** en régimen saturado: 449 514 a nivel del mar contra 449 308 en la
estación. El signo se invierte, y el mecanismo son los dos factores del producto
de la Ec. (8) de la P.1622, `σ² = A · σ²_punto`, que se mueven en direcciones
opuestas al subir la estación. Medido a 10° de elevación:

| | 0 m | 30 m | cambio |
|---|---|---|---|
| `σ²_punto` (débil, Ec. 4b) | 1.5446 | 1.4780 | **−4.31 %** |
| `σ²_punto` (saturado) | 0.63542 | 0.62602 | **−1.48 %** |
| `A` (Ec. 7) | 0.072572 | 0.075102 | **+3.49 %** |
| producto (débil) | 0.112092 | 0.111004 | −0.97 % |
| producto (saturado) | 0.046113 | 0.047015 | **+1.96 %** |

Quitar los primeros 30 m de aire baja la varianza de Rytov un 4.31 %, pero cerca
de la saturación ese cambio **casi no llega a la salida**: el modelo saturado
solo baja un 1.48 %. Mientras tanto `A` —el promediado de apertura, que depende
de la *altura* de la turbulencia a través de la `z_0` de la Ec. (9)— sube un
3.49 % en los dos regímenes por igual, porque la saturación no lo toca. En
débil gana el primer factor; en saturado gana el segundo.

El cruce está en **27.02°** de elevación: por encima la varianza saturada sigue
bajando con la altura, por debajo sube. El día de referencia pasa el **67.7 %**
de sus segundos en pase por debajo de ese cruce (elevación mediana 17.4°),
porque un pase pasa la mayor parte de su duración cerca del horizonte, así que
el total del día hereda el signo de las muestras bajas.

**Esto no dice que una montaña sea mal sitio para un telescopio.** Dice que el
**hueco 21** —el promediado de apertura en régimen saturado, que aquí se mantiene
en el convenio de la P.1622— es exactamente la elección de modelado de la que
depende ese signo, y sigue declarado abierto. Y dice que una cantidad medida en
un régimen no se traslada al otro ni siquiera en el signo.

---

## Lo que costaría cambiar el predeterminado, medido

La decisión de arriba —`WEAK` de predeterminado— **no cambia en esta ronda**, y
esta sección existe para que cambiarla sea una decisión con precio y no una
línea. Se midió flipando los defectos y corriendo la suite entera.

### Flipar solo el esquema (`ChannelSpec.scintillation_regime`)

**30 aserciones rojas**, y **ninguna es V2**: son el digest de referencia, las
cadenas ruta-contra-ruta del motor, y —esto es lo interesante—
`tests/scenario/test_scenario_files.py::TestFilesEqualTheirBuilders`, porque los
cinco `scenarios/*.yaml` ahora **escriben** `scintillation_regime: weak`. Es
decir: los escenarios comprometidos seguirían significando lo que significan
hoy; lo que cambiaría es lo que recibe quien no declara nada.

### Flipar también los defectos de la física (las siete firmas)

**84 aserciones rojas**, y aquí sí están los anclajes V2:

- **Seis de las ocho celdas de la Tabla 2 de la ITU-R P.1622** dejan de
  reproducirse dentro de medio dígito impreso. El 3.4 % que este ADR cita es
  **la celda más favorable**, 1550 nm y 21 m/s; a lo largo de la tabla el
  desplazamiento va de **−3.4 % a −21.1 %** (532 nm, 30 m/s: 0.3618 → 0.2855
  contra un 0.36 impreso).

  | λ (µm) | viento | impreso | débil | saturado | desplaz. | ¿fuera de ±0.005? |
  |---|---|---|---|---|---|---|
  | 0.532 | 21 | 0.23 | 0.2293 | 0.1984 | −13.5 % | **sí** |
  | 0.85 | 21 | 0.12 | 0.1328 | 0.1227 | −7.5 % | no |
  | 1.064 | 21 | 0.09 | 0.1022 | 0.0964 | −5.6 % | **sí** |
  | 1.55 | 21 | 0.07 | 0.0659 | 0.0636 | −3.4 % | **sí** |
  | 0.532 | 30 | 0.36 | 0.3618 | 0.2855 | −21.1 % | **sí** |
  | 0.85 | 30 | 0.19 | 0.2094 | 0.1837 | −12.3 % | **sí** |
  | 1.064 | 30 | 0.14 | 0.1612 | 0.1461 | −9.3 % | **sí** |
  | 1.55 | 30 | 0.10 | 0.1039 | 0.0979 | −5.7 % | no |

- **La tabla de validación deja de decir «reproduced».**
  `quoss.validation.channel.cases()` recalcula esas ocho celdas y deriva su
  estado de los números (la regla del ADR 0018, reservado): con el defecto
  flipado, seis pasan a «disagrees», y el doctest que imprime
  `['reproduced', 'reproduced']` es uno de los 84.
- Once celdas de `tests/channel/test_horizontal.py` y cinco de
  `tests/channel/test_link_budget.py`, incluidos los anclajes contra Ntanos et
  al., más diecisiete doctests de `src/` que son el manual de física.

### La lectura

El precio del flip no es «mover un 3.4 % los anclajes», que es como lo decía la
primera versión de este ADR: es **perder seis de los ocho anclajes V2 más
fuertes que tiene el canal**, y con ellos la frase «este número es de la
P.1622». Lo que se compraría a cambio está medido igual de bien: +3.66 % de
clave en el día de referencia, y una máscara óptima tres grados y medio más
baja.

La forma de tener las dos cosas sin pagar ninguna es la que ya está: el campo
existe, el aviso nombra la alternativa en los dos sentidos, y elegir el saturado
para un estudio de máscara es **una línea de YAML**.

---

## Anexo (2026-09-17): el defecto no desaparece, se muda a las firmas

**Qué cambia.** `ChannelSpec.scintillation_regime` pasa a ser **obligatorio y sin
defecto**. Las siete firmas de física —`downlink_loss_budget`,
`log_irradiance_variance`, `downlink_log_irradiance_variance`,
`uplink_log_irradiance_variance`, `horizontal_point_log_irradiance_variance`,
`horizontal_log_irradiance_variance` y `horizontal_loss_budget`— **conservan su
`ScintillationRegime.WEAK`**. No es un flip: es una mudanza, y las dos mitades
tienen defensa separada.

### Lo que no se hace, y por qué

**No se flipa el defecto a saturado.** La sección anterior lo mide: costaría
**seis de las ocho celdas** de la Tabla 2 de la ITU-R P.1622, que son seis de los
ocho anclajes V2 más fuertes que tiene el canal. Esa medición sigue siendo la
misma y la decisión sigue siendo la misma.

**Y no se deja el defecto invisible donde estaba.** Un defecto en el esquema es
un parámetro que recibe todo el que no lo declara, que es exactamente lo que el
[ADR 0014](0014-scenario-contract-and-provenance.md) refusa para un campo que
mueve una decisión de diseño. La defensa que tenía —«los cinco `scenarios/*.yaml`
lo escriben igualmente, así que el defecto no lo recibe nadie»— era cierta
mientras el único enlace del esquema fuera la bajada.

### Por qué deja de ser cierta: el camino horizontal es el otro miembro de la unión

Desde el [ADR 0024](0024-the-horizontal-scenario.md) el escenario es una unión
discriminada, `link: downlink | horizontal`. Y los dos miembros no están en el
mismo régimen:

- En la **bajada** de referencia el modelo débil es el ordinario y el saturado es
  la corrección que importa por debajo de ~20° de elevación: vale **+3.66 %** del
  día.
- En un **camino horizontal** de `C_n^2 = 1e-14` a 1550 nm la teoría débil deja
  de ser citable a **2413 m** (`weak_theory_path_limit_m`), y GE-1 se dimensiona
  entre 200 m y 5 km. Es decir: **en más de la mitad del barrido que la PR C
  existe para hacer, el defecto sería el modelo equivocado**, y lo sería en
  silencio salvo por un `WARNING` en un log.

Un defecto que es correcto para un miembro de la unión y equivocado para el otro
no es un defecto, es un sesgo. Por eso el campo del escenario deja de tener uno:
el autor del escenario elige, y la elección entra en el SHA-256 y por tanto en la
procedencia y en la clave de caché.

### Por qué en las firmas de física sí vale un defecto, que es la otra mitad

Porque una firma de física **no es un escenario**: es donde se hacen las
comparaciones contra un número impreso. `tests/channel/test_turbulence.py` llama
a `log_irradiance_variance` con los parámetros de la Tabla 2 de la P.1622 y
compara contra sus ocho celdas; ese punto de llamada no está eligiendo un modelo
de física, está preguntando «¿qué dice la recomendación?», y el modelo que
responde a esa pregunta es el suyo, el débil de su Ec. (4a).

Dicho de otra forma: el defecto de las firmas significa **«la P.1622 tal como
está impresa»**, que es una afirmación bibliográfica y estable; el defecto del
esquema significaba **«el aire que este experimento tiene»**, que es una
afirmación física y depende del experimento. Son dos preguntas distintas bajo un
nombre, y separarlas es lo que permite que flipar una no arrastre a la otra.

**Y la asimetría queda asertada, no confiada.** El test que comprobaba que los
dos defectos coincidían (`test_the_regime_default_is_the_physics_default…`) pasa
a comprobar el arreglo nuevo en las dos direcciones:
`ChannelSpec.model_fields["scintillation_regime"].is_required()`, y las **siete**
firmas con `WEAK` —el recuento incluido, para que una firma nueva sin defecto, o
con el otro, sea un test rojo en vez de una asimetría callada—. Está en
`tests/scenario/test_models.py::TestTheStationSpecConversions::test_the_schema_has_no_regime_default_and_the_physics_signatures_keep_theirs`.

### Lo que cuesta, medido

Cinco ficheros de `scenarios/` ya escribían el campo, así que **ningún escenario
comprometido cambia de significado ni de digest**: el digest de referencia sigue
en `303a3729…`. Lo que cambia es que `ChannelSpec(zenith_transmittance=1.0)` en
Python pasa a ser un `ValidationError` — ocho puntos de llamada en `src/` y
`tests/`, todos actualizados en la misma PR, y ninguno de ellos era un escenario
de física: eran constructores de prueba que ahora dicen qué régimen prueban.

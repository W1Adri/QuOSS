# Archivo de `LAST_CHANGES.md` — §37 y §38

> **Qué es esto.** Dos entradas de la bitácora del proyecto, **íntegras y sin
> editar**, sacadas del camino de lectura obligatorio y no borradas. La razón
> general es la misma que la de [`LAST_CHANGES-01-12.md`](LAST_CHANGES-01-12.md)
> y sus dos hermanos: `notes/LAST_CHANGES.md` guarda las cinco últimas entradas
> completas y el resto vive aquí, con una línea por entrada en el índice del
> fichero vivo.
>
> **Por qué estas dos y por qué ahora.** No por antigüedad: **§37 está entero en
> el [ADR 0022](../../docs/adr/0022-the-strong-regime.md) y §38 en el
> [ADR 0023](../../docs/adr/0023-traceable-extinction.md)**, que es la regla de
> archivo de §41 —una entrada se archiva cuando todo lo que carga peso en ella
> vive ya en un ADR, en un test o en un docstring— y no el recuento de líneas.
>
> **Y se volvió a medir en vez de darlo por bueno**, con el mismo extractor que
> §41: todo número de tres cifras significativas o en notación científica de
> cada entrada, buscado en `docs/adr/*.md`, `src/**/*.py`, `tests/**` y los
> YAML de datos.
>
> | | Números distintos | Con dueño | Huérfanos |
> |---|---|---|---|
> | §37 | 103 | **100** | 3 |
> | §38 | 77 | **76** | 1 |
>
> Los cuatro huérfanos son de la clase que §41 ya clasificó como archivable sin
> migrar: **tres recuentos históricos de la suite** (3 478, 3 541 y 3 640
> `passed`) y **un identificador de run de CI** (34988518923). Son el estado de
> un día, no una afirmación sobre física, y el recuento de hoy lo imprime
> `uv run pytest` — que es un sitio que no envejece.
>
> **Lo que sigue valiendo de leer esto:** la narración. Un ADR guarda la
> conclusión; estas dos entradas guardan qué se creía antes —que el régimen
> fuerte no hacía falta, que la extinción podía ser una entrada del escenario— y
> qué medición lo cambió.
>
> Índice de una línea por entrada, con su cifra: [`../LAST_CHANGES.md`](../LAST_CHANGES.md).

---

## 37. Etapa 1.2 — régimen moderado-a-fuerte, y tres números del ADR 0021 que estaban mal citados

**Fecha:** 2026-09-15. **ADR nuevo:** [0022](../docs/adr/0022-the-strong-regime.md).
**ADRs tocados:** 0009 (una fuente nueva, dos huecos nuevos, el 19 investigado),
0021 (la tabla de ejemplo, los límites de operación, dos consecuencias).

### T4 — El job de macOS pasó

El `portability` de la ronda anterior no se pudo verificar sin empujar la rama.
Está en `main` desde el merge de la PR #12: run **34988518923**, job
`pytest (macOS arm64, py3.13)`, **3 478 passed en 82 s**, verde. Los seis jobs
del run pasaron. Los dos literales que fallaban en otra máquina no volvieron a
fallar.

### T1 — El titular del camino horizontal cruzaba su propio hueco, y no por donde parecía

La pregunta era si `_warn_if_the_wave_contradicts_the_beam` se había disparado en
el caso de 10 cm. **Sí se disparó**, y en las dos filas de la tabla, no en una.

Lo que la pregunta suponía —que la lente de 10 cm era el transmisor, y que las
dos filas estaban en regímenes distintos (3.16 `z_R` contra 0.20)— no es lo que
`ge1_key` calcula: el **transmisor** está fijo en 2.5 cm en las dos filas y lo que
varía es la **lente receptora**. El rango de Rayleigh solo depende del
transmisor, `z_R = 316.7 m`, así que **`L/z_R = 3.158` en las dos**.

Lo cual hace el problema peor, no mejor: las dos filas se calcularon con
`PathWave.PLANE` a 3.16 rangos de Rayleigh, que es el lado equivocado, y el
módulo lo dijo —`horizontal.plane-wave-beyond-the-rayleigh-range`, con el 3.158 en
los detalles— en un log que nadie leyó. Las dos filas esféricas salen limpias.

**La tabla honesta, con el régimen visible:**

| Lente | `L/z_R` | Clave plana | Clave esférica |
|---|---|---|---|
| 2.5 cm | 3.158 | 56.8 kbit/s | **70.2 kbit/s** |
| 10 cm | 3.158 | 636.2 kbit/s | **589.9 kbit/s** |
| factor | — | 11.20 | **8.41** |

A 3.16 `z_R` el haz se ha ensanchado 3.3 veces: **la esférica es la citable**.
Lo que se puede afirmar es un intervalo: la lente vale **entre 8.4 y 11.2**, y el
enlace de 10 cm da **entre 590 y 636 kbit/s**.

**Y el intervalo no está ordenado como uno esperaría.** Una onda esférica
escintila 2.46 veces menos en un punto, pero se promedia peor con una lente
ancha (0.214 contra 1.07): a 2.5 cm la plana es el borde pesimista y a 10 cm es
el optimista. Por eso el intervalo hay que calcularlo y no razonarlo desde el
2.46. Está en `TestTheHeadlineLensComparisonIsABracket`.

### T2 — GE-1 con retrorreflector: no es modelable, y ahora se sabe por qué

Se buscó fuente **antes** de intentar implementarlo, que era lo pedido.

**El signo del efecto está decidido y es el malo.** En geometría monoestática
—emisor y receptor juntos, que es lo que es un retrorreflector— la escintilación
de vuelta está **realzada**, no reducida: la ida y la vuelta cruzan aire
correlacionado y los dos desvanecimientos se suman en fase. Mahon, Moore,
Ferraro, Rabinovich y Suite (*Appl. Opt.* 51(25):6147, 2012) midieron un enlace
retrorreflectado **horizontal de 1.1 km** —la escala exacta de GE-1— durante
cuatro días: «substantially **enhanced** due to the correlations», con varianzas
de flujo saturando en **~10** durante el día.

**Y la teoría es Andrews otra vez.** Andrews, Phillips y Miller, *Appl. Opt.*
36(3):698 (1997). Es decir: el hueco 19 no es «nadie lo ha estudiado», es «lo ha
estudiado la misma fuente que el hueco 1 dice que no se puede abrir», y de los
dos artículos solo se leyó el **resumen**, que es lo que permite afirmar el signo
y no la magnitud.

**El dimensionado de un solo sentido, con dos terminales**, que sí es modelable
hoy (2.5 cm de transmisor, 10 cm de lente, `C_n^2 = 1e-14`, y las dos ondas como
intervalo):

| `L` | `L/z_R` | `σ_R²` | Clave plana | Clave esférica |
|---|---|---|---|---|
| 200 m | 0.63 | 0.010 | 896 kbit/s | 888 kbit/s |
| 500 m | 1.58 | 0.056 | 825 | 798 |
| 1 km | 3.16 | 0.199 | 636 | 590 |
| 2 km | 6.32 | 0.709 | 208 | 183 |
| 2.41 km | 7.62 | 1.000 | 122 | 107 |
| 5 km | 15.79 | 3.802 | 4.0 | 4.4 |

Nótese que a 200 y 500 m el enlace está **dentro o cerca** del rango de Rayleigh,
donde ninguna de las dos ondas es la correcta: el intervalo se estrecha (1 %)
pero por la razón equivocada. El caso limpio es 1–2 km.

**La recomendación:** dos terminales, un solo sentido, 1 km. Es la única de las
dos arquitecturas que este proyecto puede dimensionar con fuentes, y esa sola
diferencia es más grande que cualquier ventaja de coste del retrorreflector.

### T3 — Los límites de operación son ahora funciones con test

- **`weak_theory_path_limit_m(cn2_m23=, wavelength_m=)`** — la longitud a la que
  `σ_R² = 1`. Para `1e-14` a 1550 nm, **2 413 m**. Un test comprueba que coincide
  con la longitud a la que el presupuesto empieza a avisar, por los dos lados:
  un límite que no coincidiera con el aviso del propio código sería una segunda
  opinión, que es peor que ninguna.
- **`equivalent_bench_cn2_m23(...)`** — **8.87e-10** para que 2 m igualen 1 km
  moderado, y un test que comprueba que las dos varianzas de Rytov coinciden a
  precisión de máquina, en vez de fiarse del exponente.

**Sobre si un SLM llega a 8.9e-10, que era la pregunta.** La respuesta corta es
que **la pregunta está mal planteada, y esa es la respuesta útil**. Un emulador
no produce un `C_n^2` sobre una longitud: produce una **pantalla de fase** con
un `r_0` dado. La escintilación es distorsión de fase convertida en amplitud
**por la propagación**, así que una pantalla necesita distancia detrás: una
pantalla al principio de un banco de 2 m tiene 2 m para desarrollar lo que un
kilómetro de aire distribuido desarrolla continuamente. Por eso la práctica de
laboratorio es igualar los **números adimensionales** —`D/r_0` y el número de
Rytov— con varias pantallas y óptica de relé entre ellas, y no igualar un
`C_n^2`; el trabajo que se cita para turbulencia profunda en banco usa **cinco**
SLM con trombones ópticos entre ellos precisamente para poder fijar `r_0`, el
ángulo isoplanático y la varianza de Rytov de forma independiente.

Así que `equivalent_bench_cn2_m23` da una condición **necesaria y no
suficiente**, y eso queda escrito en su docstring y como **hueco 20**. Lo que
GE-0b tiene que preguntarle a un fabricante no es «¿llegas a 8.9e-10?» sino
«¿qué `D/r_0` y qué número de Rytov alcanzas, y con cuántas pantallas?».

### 1.2 — El régimen fuerte, y la fuente estaba citada desde hace meses

**Lo que resultó ser la mejor fuente ya estaba en la tabla del ADR 0009 sin
código detrás.** La fila «Rytov en camino inclinado; escintilación en régimen
fuerte | Ntanos et al. 2021 | (12), (13)» apuntaba a la **Ec. (12)** del paper de
referencia de punta a punta de este proyecto, que es exactamente el modelo de
Andrews-Phillips de escala grande y escala pequeña. Abierta, numerada, y del
mismo paper del que salen el receptor, el ruido y el escenario.

```
σ²_lnI = 0.49 s / (1 + c s^(6/5))^(7/6) + 0.51 s / (1 + 0.69 s^(6/5))^(5/6)
```

Tres fuentes abiertas la imprimen: Ntanos et al. (12), Gruneisen et al. (A8) y
(A9) —que añade la onda esférica que el camino horizontal necesita y el máximo
publicado de 1.24— y Kaushal & Kaddoum (17). Las tres citan a Andrews & Phillips,
que es el hueco 1. Así que es **V2 contra fuente secundaria**, y decirlo importa.

**Y una de las tres la imprime mal.** Kaushal & Kaddoum (17) lleva `7/6` en el
segundo denominador donde las otras dos llevan `5/6`. Dos contra uno no es una
razón, así que lo decide el límite: con el `7/6`, el índice «saturado» **decae a
0.031** con `σ_R² = 10 000`, donde el canal está en su momento más violento. Un
modelo de parpadeo que devuelve menos parpadeo cuanto más turbulento el aire.

**Dos de cinco números estaban mal en el primer borrador, y el anclaje los
cazó.** Gruneisen et al. imprimen «the maximum theoretical value ... is
approximately 1.24». El módulo da **1.2432**, en `σ_R² = 10.31`. Ese máximo está
donde el término de gran escala ya murió y el de pequeña escala aún no se asentó,
así que reproducirlo ejercita los dos cortes, los dos exponentes y la potencia de
la varianza a la vez:

- `σ_R^(12/5)` es potencia de la **desviación típica**; en términos de la varianza
  es `s^(6/5)`. Escribirlo como `s^(12/5)` deja todo finito y positivo y da un
  máximo de **0.71**.
- El `7/6` de Kaushal & Kaddoum da **0.60** y decae.

Los dos fallos están asertados como tests, para que volver a cometerlos sea rojo.

### El predeterminado sigue siendo el débil, y está medido por qué

`ScintillationRegime.WEAK` es el predeterminado aunque el saturado nunca sea
peor, porque **en el punto que fija la Tabla 2 de la P.1622** —75°, régimen
plenamente débil— el heurístico lee un **3.4 % por debajo** de la recomendación.
Poner el heurístico de predeterminado movería todos los anclajes V2 del canal un
3.4 % por una corrección que solo importa por debajo de ~20°. La elección está en
la firma, medida, y el aviso nombra la otra opción.

### El resultado: el óptimo de la máscara se mueve de 8° a 4.5°

| Máscara | `WEAK` | saturado | cambio |
|---|---|---|---|
| 2° | 408 946 | 458 862 | +12.2 % |
| **4.5°** | 424 448 | **462 945** | +9.1 % |
| 8° | **434 938** | 457 663 | +5.2 % |
| 20° | 360 978 | 364 740 | +1.0 % |

Sigue siendo **interior**, baja tres grados y medio, y el día gana **6.4 %**. La
ganancia es **monótona en lo baja que esté la máscara**, que es la firma de que
todo el efecto viene de las muestras bajas.

### Y separado en canal y cota, que no coinciden

Con `x = mean(ln T)`, `y = ln(bits)`, `E = dy/dx`, la maquinaria que
`TestWhyTheHigherStationGainsLess` escribió literalmente para este momento:

| Estación | culmina | `dx` (canal) | `E` (cota) | `dy` (clave) |
|---|---|---|---|---|
| Castelldefels | 26° | **+7.90 %** | 0.473 | +3.66 % |
| Calar Alto | 21–37° | +3.05 % | **2.91** | **+9.12 %** |
| Teide OGS | 57–72° | +1.78 % | 0.673 | +1.20 % |

**Los dos órdenes son opuestos.** El canal de Castelldefels gana dos veces y
media más, porque sus pasos son los más bajos; la clave de Calar Alto gana dos
veces y media más, porque está en el acantilado de certificación. En las otras
dos estaciones `E < 1`: más luz compra **menos que proporcionalmente** más clave,
porque la corrección de errores se cobra sobre todas las detecciones nuevas y la
amplificación de privacidad solo certifica la parte de un fotón.

El número más grande de toda la etapa es el segundo paso de Calar Alto,
**+17.7 %**, y es casi todo cota: su canal solo mejora un **2.50 %**, con
`E = 6.60`. Citarlo sin `E` al lado sería reportar la demostración de seguridad
como si fuera la atmósfera.

### Lo que 1.2 le hizo a dos cifras del ADR 0021

- **La elección de onda a 5 km valía cuatro veces menos de lo que se citaba.**
  21.73 contra 15.06 dB pasa a **8.41 contra 9.94**, y **el signo se invierte**.
  La mayor parte de esos 6.67 dB era el modelo débil evaluado cuatro veces más
  allá de su propio límite. El hueco de la onda gaussiana no desaparece —1.53 dB
  siguen siendo 1.53 dB— pero se estaba citando a cuatro veces su tamaño.
- **Las dos celdas que la P.1814 no debería haber impreso**, ahora con número:
  **12.25 dB impresos contra 7.19 saturados**, y **16.00 contra 7.57**.

### Lo que no cierra (huecos 20 y 21, nuevos)

- **Hueco 21 — el promediado de apertura en régimen saturado.** La Ec. (8) de la
  P.1622 multiplica la **log-varianza** por `A`; la Ec. (14) de Ntanos et al.
  define `A` como cociente de **índices**. En régimen débil es lo mismo; aquí no.
  Medido a 10° con el telescopio de 0.75 m: **2.29 contra 2.68 dB**, **0.39 dB**.
  Se mantiene el convenio de la P.1622 porque la `A` que se usa es la Ec. (7) de
  la P.1622, definida como cociente de log-varianzas.
- **Hueco 20 — los emuladores.** Arriba.
- **La distribución sigue siendo log-normal.** Se corrige la varianza, no la
  forma. En régimen fuerte la irradiancia es gamma-gamma y las colas —que es lo
  que lee un outage al 1 %— no son las mismas.

### Verificación

`uv run pytest`: **3 541 passed**, 0 fallos. `ruff check`, `ruff format --check`
y `mypy` limpios sobre 141 ficheros.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/channel/turbulence.py` | `PathWave` (mudado), `ScintillationRegime`, `saturated_log_irradiance_variance`, los cinco coeficientes, `regime` en tres funciones |
| `src/quoss/channel/horizontal.py` | `weak_theory_path_limit_m`, `equivalent_bench_cn2_m23`, `_saturated_and_logged`, `regime` en tres funciones, `PathWave` reexportado |
| `src/quoss/channel/link_budget.py` | `regime` en `downlink_loss_budget`; corregida la promesa de `_assembled_loss_budget` |
| `tests/channel/test_turbulence.py` | V2 contra el máximo de 1.24, V1 del límite débil y la asíntota, los dos fallos cazados, el régimen elegido y dicho |
| `tests/channel/test_horizontal.py` | el intervalo del titular, los dos límites de operación, el régimen saturado en horizontal |
| `tests/system/test_key_volume.py` | el desplazamiento del óptimo de la máscara |
| `tests/e2e/test_reference_scenarios.py` | la descomposición canal/cota |
| `tests/system/reference.py`, `tests/e2e/oracle.py` | `regime` a través de las dos cadenas de referencia |
| `docs/adr/0022-the-strong-regime.md` | nuevo |
| `docs/adr/0009`, `0021`, `tests/golden/README.md`, `README.md` | huecos, tabla corregida, límites |

---

## 38. Etapa 1.1 — la extinción deja de ser una entrada, y una unidad mal impresa en la UIT

**Fecha:** 2026-09-15. **ADR nuevo:** [0023](../docs/adr/0023-traceable-extinction.md).
**ADRs tocados:** 0009 (tres fuentes nuevas, el hueco 14 **estrechado y con una
etiqueta corregida**, dos huecos nuevos), 0021 (de dónde sale ahora
`extinction_db_per_km`).

**La cifra que resume la entrada: 0.230 dB cenitales — el aire más limpio del
código meteorológico de la UIT — cuestan el 22.7 % de la clave certificada del
día de referencia.** Ese término estaba puesto a cero en todos los escenarios del
repo, honestamente, porque no había número que poner.

### El problema, y por qué no era una omisión

`ChannelSpec.zenith_transmittance` y `horizontal_loss_budget(extinction_db_per_km=…)`
eran entradas obligatorias sin modelo: el presupuesto **no calculaba** la
atmósfera, la **recibía**. Eso lo fijó el hueco 14 del ADR 0009 con una forma
precisa —la ley de escala está publicada (Ec. (7) de Ntanos et al.) y el número
que escala no— y era cierto de los dos documentos que se habían mirado. Faltaba
mirar un tercero.

### Las fuentes: cuáles se abrieron y cuáles no

| Documento | Versión | ¿Abierta? | Qué aporta |
|---|---|---|---|
| **ITU-R P.1814** | 08/2007 | **Sí** | §4.2.1 **Ecs. (4)-(5)**: visibilidad → atenuación específica |
| **ITU-R P.1817-1** | 02/2012 | **Sí** | §3 **Ecs. (3)-(4)** (Rayleigh), §12 **Ec. (12)** y su tabla de código de visibilidad |
| **Kim, McArthur & Korevaar 2001** | *Proc. SPIE* 4214:26 | **Sí**, manuscrito del segundo autor | **Ecs. (5), (6), (9)** y **Tablas 2 y 4** |
| **ITU-R P.1621-2** | 07/2015 (+ enmiendas editoriales 2026) | **Sí** | Confirmado: sus §2 y §3 son **solo figuras**. El hueco 14 decía la verdad |
| **Gruneisen et al. 2021** | arXiv:2006.07745 | **Sí** | §III A: el cociente MODTRAN 775/1550 nm |
| **HITRAN** | hitran.org, 2026-09-15 | **Responde y no sirve** | Ver abajo |
| **MODTRAN** | — | **No**, software de pago | Solo por lo que Gruneisen et al. publican |

### La trampa que da forma al módulo: la Ec. (4) dice dB/km y devuelve nepers

La ley es la relación de Koschmieder escalada en longitud de onda:

```
σ(λ) = (3.91 / V) · (λ / 550 nm)^(-q)
```

El `3.91` es `ln(1/0.02)` redondeado —la definición del 2 % de la visibilidad,
invertida—, así que lo que devuelve está en **nepers por kilómetro**. La P.1814
dice **dB/km**. Son un factor 4.343: **9.9 dB/km en una niebla de 1 km** a
1550 nm, 10.6 a 785 nm.

No se afirma, se decide con dos tablas publicadas que salen de **esa misma
ecuación**: la Tabla 2 de Kim et al. imprime **14 dB/km** a 1 km de visibilidad y
785 nm, y el código internacional de visibilidad de la **P.1817-1 §12** imprime
**13.8** en el mismo punto, donde la ecuación devuelve 3.175. La etiqueta se leyó
**renderizando la página 5 como imagen**, no del extractor de texto, que es la
regla que ya costó dos veces en este repo.

### Y la tabla de la P.1817 no dice su longitud de onda

Es la ley de la P.1814 a **785 nm** —la de Kim et al.—: sus 15 celdas se
reproducen al **2.8 %** ahí y al 2.1 % en el mejor ajuste, 780.5 nm; a 1550 nm se
equivocan entre 1.16 y 2.94 veces. Queda un 2 % de dispersión en cualquier
longitud de onda, así que lo afirmable es «la misma ley cerca de 780 nm» y no
«se calculó a 785.0». Es un cruce entre fuentes, no un anclaje V2 del modelo.

De paso decide el convenio de frontera: la tabla imprime **0.19 dB/km en
exactamente 50 km**, que es el valor de `q = 1.6` y no el de `q = 1.3`, y la
Ec. (5) deja `V = 50` sin rama porque imprime desigualdades estrictas.

### Las dos leyes, sin defecto, porque en niebla difieren 42.9 dB/km

| `V` | `ITU_P1814` (Kruse) | `KIM_2001` |
|---|---|---|
| > 50 km | 1.6 | 1.6 |
| 6–50 km | 1.3 | 1.3 |
| 1–6 km | `0.585 V^(1/3)` | `0.16 V + 0.34` |
| 0.5–1 km | `0.585 V^(1/3)` | `V − 0.5` |
| < 0.5 km | `0.585 V^(1/3)` | **0** |

A 50 m de visibilidad: Kruse da **314.6 dB/km a 785 nm y 271.7 a 1550**, una
ventaja de **42.9 dB/km** para el infrarrojo; Kim et al. dan **339.6 a las dos**.
Es la respuesta a «¿compro 1550 nm porque atraviesa la niebla?», y las dos están
publicadas, así que la elección está en la firma. El argumento de Kim et al. no
es una preferencia: los datos que ajustaron `0.585 V^(1/3)` se tomaron «en niebla
y bruma densa», que Middleton ya marcó como dudosos, y una gota de niebla mide
veinte longitudes de onda — el régimen no selectivo, donde el color no puede
importar.

### La discontinuidad, y el residuo publicado que se come

La tercera rama de Kruse llega a `0.585·6^(1/3) = 1.063` donde la siguiente
empieza en 1.3: un salto del **22.3 %** en `q`, **21.8 %** de atenuación a
1550 nm. La Ec. (9) de Kim et al. lo quita (sus tres uniones son exactas); el
salto de 50 km, del 23.1 %, no lo quita ninguna.

**Y el salto hace inalcanzables algunos valores.** A través de una capa de
aerosol de 1.2 km de altura de escala a 1550 nm, **ninguna visibilidad produce
una pérdida cenital entre 0.883 y 1.129 dB** — y el residuo de **0.906 dB** del
presupuesto de 20 dB de Ntanos et al. cae dentro. El valor alcanzable más cercano
está a 0.021 dB y es el de **6 km de visibilidad**, que la tabla de la propia UIT
llama *light fog*.

**Así que la frase del ADR 0009 «una transmitancia cenital de cielo claro
perfectamente ordinaria» no sobrevive a tener un modelo detrás.** Sigue siendo
compatible; deja de ser cielo claro. Corregido en el ADR 0009 y en
`tests/golden/README.md`, que es la **segunda** vez que esa entrada se corrige
por una medición.

### La columna vertical, y por qué la altitud de estación aparece dos veces

`τ = β_v · H · exp(-(h_s - h_v)/H)`. Dos cosas que hay que saber antes de leer
un número:

- **Si la visibilidad se midió en la estación, la altitud se cancela
  exactamente.** Es el caso ordinario, y por eso `visibility_altitude_m` es un
  campo aparte: la otra lectura —una visibilidad climatológica de nivel del mar
  en un sitio de montaña— es otra profundidad óptica, y nada en una cifra de
  visibilidad dice cuál es. Con 23 km al nivel del mar, el Teide a 2390 m se
  queda con el 13.7 % de la columna: **0.031 dB contra 0.230**. Un escenario
  multi-estación saca tres atmósferas de una declaración.
- **`H` no lo publica ninguna fuente abierta** (hueco 22). 1.2 contra 2 km es un
  factor **1.67**: 0.230 contra 0.384 dB. Por eso no tiene defecto — y por eso el
  residuo de Ntanos pasa de «inalcanzable» a «9.8 km de visibilidad» según cuál
  se elija.

### Lo que mide, que es lo que esta etapa existía para medir

Escenario de referencia, Castelldefels, máscara de 10°. Descomposición del
[ADR 0022](../docs/adr/0022-the-strong-regime.md): `x = mean(ln T)`,
`y = ln(bits)`, `E = dy/dx`.

| Aire | `L_zen` | cenital | `dx` (canal) | `E` (cota) | `dy` (clave) | bits/día |
|---|---|---|---|---|---|---|
| ninguno (lo de hoy) | 1.0 | 0 dB | — | — | — | **433 442** |
| 23 km, «very clear air» | 0.9483 | 0.230 dB | −15.6 % | 1.52 | **−22.7 %** | 334 883 |
| 10 km, «clear» | 0.8851 | 0.530 dB | −32.3 % | 1.67 | **−47.7 %** | 226 583 |
| 2 km, «light mist» | 0.3061 | 5.142 dB | −97.7 % | — | **−100 %** | **0** |

- **Un cuarto de decibelio cenital es un quinto del día**, porque `E = 1.52`.
- **La elasticidad no es una propiedad de la estación.** La misma Castelldefels
  daba `E = 0.473` para una ganancia de escintilación en el ADR 0022. Es una
  derivada local de una cota con suelo en cero; citar cualquiera de las dos como
  «la elasticidad de Castelldefels» sería reportar una tangente como constante.
- **Con 2 km de visibilidad el día no certifica nada** mientras el asintótico
  sigue reclamando 424 kbit: el patrón del ADR 0011, división por cero y no
  factor.

### La identidad que lo hizo seguro de aterrizar

Una visibilidad de 1e300 km da **exactamente 1.0** —el `3.91/V` es un cero
verdadero, no un desbordamiento—, así que modelar aire infinitamente limpio y
declarar `zenith_transmittance: 1.0` son **la misma corrida, bit a bit**.
`ENGINE_FINITE_DAY_BITS` no se movió y las 3 600 aserciones de igualdad exacta de
`tests/e2e/` no hubo que tocarlas.

### El esquema: dos formas, ninguna tercera

`ChannelSpec` acepta **exactamente una** de `zenith_transmittance` (un número) o
`extinction` (un `ExtinctionSpec`), con la misma forma que `BackgroundSpec` ya
usaba para la radiancia. Las dos a la vez se rechazan; ninguna también. La
conversión vive en el esquema:
`ChannelSpec.zenith_transmittance_at(wavelength_m=, station_altitude_m=,
degradations=)`, un **método** y no una propiedad porque necesita dos cosas que
viven en otros modelos, y el motor es quien las junta.

**Digest repinchado, caso 2:** `0108a01f…`. El canónico gana `"extinction":null`
y nada más; `zenith_transmittance` pasó de obligatorio a opcional sin cambiar de
significado, unidad ni serialización, así que `SCHEMA_VERSION` sigue en 1 y el
`DIGEST_HISTORY` lo demuestra borrando el campo nuevo.

### Lo que no cierra

- **Hueco 14, estrechado y no cerrado.** El aerosol tiene modelo; la absorción
  molecular no.
- **Hueco 23 — la absorción molecular.** Dos fuentes dicen «despreciable» en
  palabras y ninguna imprime una cifra; las Figs. 1 y 2 de la P.1621-2 son
  gráficas (releídas para comprobarlo). **HITRAN responde** y pide cuenta, pero
  el problema no es el registro: una lista de líneas **no es** una atenuación
  específica, y convertirla es transferencia radiativa de la clase
  LBLRTM/MODTRAN que este proyecto no tiene y habría que verificar a su vez.
- **Hueco 22 — la altura de escala, y la dispersión molecular dentro de la ley.**
  La visibilidad a 550 nm la fija la extinción total, moléculas incluidas, y la
  ley escala el coeficiente entero por un exponente de aerosol. Medido con las
  Ecs. (3)-(4) de la P.1817: la parte molecular es el 3.1 % del coeficiente a
  10 km de visibilidad y el **15.2 % a 50 km**, y llevarla a 1550 nm al exponente
  de aerosol deja el total **2.9 % alto a 10 km y 14.0 % alto a 50 km**.
  Corregirlo no lo publica nadie, así que se mide.
- **La distribución de visibilidad.** El módulo toma **una** visibilidad. Una
  afirmación de disponibilidad necesita la distribución horaria del sitio —lo que
  Kim et al. §3 describe como el uso normal de su ecuación, y lo que archiva la
  NOAA—, que es lo que `io/openmeteo.py` ya hace con las nubes y no con esto.

### Verificación

`uv run pytest`: **3 640 passed**. `ruff check`, `ruff format --check` y `mypy`
limpios sobre 143 ficheros. `channel/extinction.py` al **100 % de líneas y
ramas**, 81 tests. V2: las **32 celdas** de las Tablas 2 y 4 de Kim et al., con
la peor al 94 % de media cifra impresa.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/channel/extinction.py` | nuevo |
| `src/quoss/scenario/models.py` | `ExtinctionSpec`, `ChannelSpec` con dos formas y `zenith_transmittance_at` |
| `src/quoss/engine/pipeline.py` | resuelve la transmitancia por estación en vez de leer un campo |
| `src/quoss/channel/{__init__,link_budget,horizontal}.py` | docstrings: hay modelo, y sigue siendo entrada de esas funciones |
| `tests/channel/test_extinction.py` | nuevo |
| `tests/e2e/{oracle,test_reference_scenarios}.py` | `zenith_transmittance` en la cadena a mano, y lo que el modelo vale |
| `tests/scenario/{test_models,test_hash,test_defaults}.py` | las dos formas, el digest repinchado |
| `docs/adr/0023-traceable-extinction.md` | nuevo |
| `docs/adr/0009-citation-policy.md` | tres fuentes, hueco 14 estrechado, huecos 22 y 23, caveat de la P.1814 |
| `notes/ROADMAP.md`, `README.md`, `tests/golden/README.md` | estado, cifras y huecos |


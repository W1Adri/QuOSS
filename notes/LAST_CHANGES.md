# QuOSS — Últimos cambios

> **Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).**
> Última entrada: **§48, 2026-09-19** — cuatro directorios que prometían cosas,
> y dos suelos de dependencia que no estaban sin probar sino equivocados.
>
> **Qué hay aquí y qué no.** Este fichero guarda **las cinco últimas entradas
> completas**. Todo lo anterior está en [`archive/`](archive/), íntegro y sin
> editar, con una línea por entrada en el índice de abajo. Es un cambio de forma
> y no de contenido: no se ha borrado nada.
>
> **Por qué.** El fichero llegó a **6 834 líneas** y `CLAUDE.md` manda leerlo al
> empezar cada sesión. Una bitácora que no cabe en la sesión que la tiene que
> leer deja de ser una bitácora y pasa a ser un archivo — y el efecto real,
> observado, es que se leen las primeras pantallas y se saltan las entradas que
> describen el árbol de hoy. La regla del archivo y la comprobación que la
> respalda están en §41.
>
> **La regla, en una línea:** una entrada se archiva cuando **todo lo que carga
> peso en ella vive ya en un ADR, en un test o en un docstring**; si no, se
> migra primero. Y se aserta: `tests/unit/test_notes.py`.

---

## Índice de lo archivado (§1–§43)

| § | Fecha | La cifra o la regla que la resume | Dónde |
|---|---|---|---|
| §1 | 2026-07-31 | Estado al cerrar `orbits/` a medias: 2 237 tests, 99 % de cobertura, las 513 sentencias nuevas entraron cubiertas | [archivo](archive/LAST_CHANGES-01-12.md) |
| §2 | 2026-08-04 | **SimulCTTC deja de ser el oráculo.** Cuatro defectos suyos, entre ellos estaciones sobre una esfera con hasta ~21 km de error y una época que caía al reloj de pared | [archivo](archive/LAST_CHANGES-01-12.md) |
| §3 | 2026-08-04 | `calendar_to_jd` fallaba **±1 día** fuera de 1900-2100 (usaba la regla de bisiestos juliana). Y los 178 m contra astropy eran **DUT1, no movimiento polar**: rotando por GMST(UT1) caen a 14.4 m | [archivo](archive/LAST_CHANGES-01-12.md) |
| §4 | 2026-08-04 | **Errata de Vallado 4.ª ed.**: imprime `u = 145.60549°` donde el estado que publica da `145.720087°`. El hueco es de **0.1146°, 160 veces** el typo de `|r|` que lo acompaña | [archivo](archive/LAST_CHANGES-01-12.md) |
| §5 | 2026-08-04 | **Los términos seculares de 2.º orden se quedan fuera, por medición:** a `i = 98°` —la inclinación de este proyecto— empeoran el residuo de 1.0e-4 a **1.4e-3** | [archivo](archive/LAST_CHANGES-01-12.md) |
| §6 | 2026-08-04 | La bandera osculador/medio y sus tres subdecisiones → [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md). El aviso que llevaba tres documentos escrito pasa a `DomainError`, en las **dos** direcciones | [archivo](archive/LAST_CHANGES-01-12.md) |
| §7 | 2026-08-04 | `propagator.py` → [ADR 0005](../docs/adr/0005-propagation.md). **Enum enviado incompleto a propósito:** un nombre ausente obliga a preguntar, uno presente y equivocado no obliga a nada | [archivo](archive/LAST_CHANGES-01-12.md) |
| §8 | 2026-08-04 | `perturbations.py` → [ADR 0004](../docs/adr/0004-zonal-perturbations.md). Una sola expresión de Legendre para toda la fuerza zonal; J3 no tiene término secular de primer orden, medido y no afirmado | [archivo](archive/LAST_CHANGES-01-12.md) |
| §9 | 2026-08-04 | `frames.py` → [ADR 0002](../docs/adr/0002-frames-and-time-scales.md). Un solo marco inercial (TEME) y un solo giro. Presupuesto medido: 14.4 m de movimiento polar, **274 m** de DUT1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §10 | 2026-08-04 | `kepler.py` → [ADR 0003](../docs/adr/0003-orbital-elements.md). Markley 1995 en forma cerrada, residuo **≤ 1.4e-15 rad** hasta `e = 0.9999`, y la función comprueba su propia post-condición | [archivo](archive/LAST_CHANGES-01-12.md) |
| §11 | 2026-08-04 | Inventario de ficheros de la etapa 2.1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §12 | 2026-08-04 | Entorno y versiones de la etapa 2.1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §13 | 2026-08-04 | «Cosas a considerar»: la tabla **Pendiente de decidir** y la **Deuda pequeña**. Lo que seguía vivo está hoy en [`ROADMAP.md` § Trabajo abierto](ROADMAP.md); lo cerrado, tachado allí | [archivo](archive/LAST_CHANGES-13-24.md) |
| §14 | 2026-08-04 | **Las siete entradas de la auditoría, cerradas el mismo día.** La grande no era una inconsistencia sino C1: los «219 km» citados en quince sitios **no se reproducían** — la cifra real es **5.9 veces mayor**, y no existe una cifra única | [archivo](archive/LAST_CHANGES-13-24.md) |
| §15 | 2026-09-10 | `tle.py` → [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md). SGP4 envuelto, no reimplementado; `parse_tle` caza un checksum corrupto y una entrada basura que `sgp4` deja pasar en silencio | [archivo](archive/LAST_CHANGES-13-24.md) |
| §16 | 2026-09-10 | **El ángulo de point-ahead lleva factor 2**, no el `v_perp/c` de una vía: **50.6 µrad** a 67.1° de elevación, contra los 35 µrad que el roadmap citaba antes de tener la cuenta hecha | [archivo](archive/LAST_CHANGES-13-24.md) |
| §17 | 2026-09-10 | `constellations.py` → [ADR 0008](../docs/adr/0008-constellation-design.md). Espaciado en anomalía **media**, con control negativo; el `rtol` de `brentq` pasa de literal a `4 * eps` con nombre | [archivo](archive/LAST_CHANGES-13-24.md) |
| §18 | 2026-09-10 | **La Ec. (5) de Ntanos et al. imprime `(8/w_0)²` donde cierra `8/w_0²`: 8 veces, 9.03 dB optimista.** Con sus propios parámetros devuelve una transmitancia de **1.36**, más luz recogida que transmitida | [archivo](archive/LAST_CHANGES-13-24.md) |
| §19 | 2026-09-10 | **El `A_0` de Farid & Hranilovic Ec. (9) *es* el acoplamiento geométrico de `beam.py`**, así que multiplicarlos como está publicado inventa **17.5 dB**. Y la pérdida media son 0.22 dB contra **1.03 dB** una vez de cada cien | [archivo](archive/LAST_CHANGES-13-24.md) |
| §20 | 2026-09-10 | **La Ec. (20) llama «probability» a un número esperado de cuentas que con la luz solar tabulada por la UIT vale 3.42.** El gating es el único parámetro libre del ruido: de 1 ns a 100 ps quita **10 dB de fondo por 0.08 dB de señal** | [archivo](archive/LAST_CHANGES-13-24.md) |
| §21 | 2026-09-10 | **Aplicar la cadena de eficiencia también a las cuentas oscuras esconde 0.94 dB de ruido.** Y el gating vale **10 dB con el nanohilo de Ntanos y 0.22 dB con el APD de Lim**: «estrecha la puerta» es condicional, y la condición es el detector | [archivo](archive/LAST_CHANGES-13-24.md) |
| §22 | 2026-09-12 | **Sumar el cuantil al 1 % de cada término no da un presupuesto al 1 %.** El cuantil conjunto exacto son **1.668 dB donde la suma publicada da 2.312**, y esa etiqueta «1 %» es en realidad **0.066 %**. Más el doble conteo del receptor: 12.71 dB en vez de 6.36 | [archivo](archive/LAST_CHANGES-13-24.md) |
| §23 | 2026-09-12 | `qkd/base.py`: la frontera canal↔protocolo. **Una media no es una probabilidad** — leer una por otra sobreestima **3.58 %** en el telescopio de 2.3 m | [archivo](archive/LAST_CHANGES-13-24.md) |
| §24 | 2026-09-12 | **La Ec. (10) de Ma et al. devuelve una ganancia mayor que uno por encima de 7.152 cuentas por puerta**, así que se usa la exacta. Y «4:1:16» contra «q = 2/5» en la misma frase de Ntanos discrepan por **4.2** | [archivo](archive/LAST_CHANGES-13-24.md) |
| §25 | 2026-09-12 | **La cota finite-key no es la asintótica por un factor:** 1.1387e-05 contra 6.0239e-05 bits por pulso, el **18.9 %**, y a 1e9 pulsos **nada**. La fuente es Lim et al. 2014, no Tomamichel | [archivo](archive/LAST_CHANGES-25-36.md) |
| §26 | 2026-09-13 | `passes.py` → [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md). No refinar la rejilla cuesta **3.79 s del día, el 0.032 % de los bits**, y por eso `find_passes` no interpola la trayectoria | [archivo](archive/LAST_CHANGES-25-36.md) |
| §27 | 2026-09-13 | **El bloque es el pase.** El día asintótico reclama 3.78 Mbit y la cota finita certifica **0.43 Mbit, el 11.5 %** — y **dos de los cuatro pases no certifican nada**. La máscara de elevación tiene **óptimo interior, cerca de 8°** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §28 | 2026-09-14 | **La clave de un pase es una distribución, no un número.** La cifra de diseño —margen devuelto, apuntado en su media— **infrarreporta el día típico un 43 %** (×1.752), y los dos pases muertos siguen muertos | [archivo](archive/LAST_CHANGES-25-36.md) |
| §29 | 2026-09-14 | **Las nubes deciden si el pase existe.** Con un terminal la diversidad compra **2.30 veces** la clave de Castelldefels sola, y los seis pases descartados valían **56 925 bits, el 5.4 %**. La clave relevada espera hasta **9.4 horas** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §30 | 2026-09-14 | `scenario/` → [ADR 0014](../docs/adr/0014-scenario-contract-and-provenance.md). **Lo que valida, convierte:** lo que el motor recibe de aquí no lleva ni un grado. La estación lleva el viento r.m.s. (21.0 m/s), no el de superficie | [archivo](archive/LAST_CHANGES-25-36.md) |
| §31 | 2026-09-14 | `io/` → [ADR 0015](../docs/adr/0015-external-data-isolation-and-snapshots.md). El único sitio que puede abrir un socket, y `TestTheSuiteIsOffline` rompe `socket.socket` para demostrarlo | [archivo](archive/LAST_CHANGES-25-36.md) |
| §32 | 2026-09-14 | **Dos tests que informaban de su entorno en vez de del código.** Un test que pasa por cómo está montada la máquina no prueba nada del árbol | [archivo](archive/LAST_CHANGES-25-36.md) |
| §33 | 2026-09-14 | **El README decía «Etapa 3 en curso» con las etapas 0-6 en el árbol.** Una afirmación que el árbol no sostiene es la misma clase de defecto que un número sin test | [archivo](archive/LAST_CHANGES-25-36.md) |
| §34 | 2026-09-14 | Doppler y point-ahead **salen al resultado** → [ADR 0019](../docs/adr/0019-acquisition-in-the-result.md), [ADR 0020](../docs/adr/0020-declared-doppler-capture-range.md). Point-ahead de **24.685920 a 50.652309 µrad** en el día de referencia; deriva de 41.5 MHz/s | [archivo](archive/LAST_CHANGES-25-36.md) |
| §35 | 2026-09-15 | Dos literales del puente e2e fallaban por **9 ULP** en una máquina que no era la suya; ahora se comparan contra una cota derivada. Y **`combined_fade_db` devolvía 1.602 dB donde la respuesta es 0.101** con apuntado despreciable | [archivo](archive/LAST_CHANGES-25-36.md) |
| §36 | 2026-09-15 | `channel/horizontal.py`: presupuesto y QBER de un banco y de un enlace de unos kilómetros, con la Tabla 4 de la ITU-R P.1814 como V2. **Para GE-1 a 1 km, una lente de 10 cm da 11 veces la clave de una de 2.5 cm** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §37 | 2026-09-15 | `turbulence.py` entra en **régimen moderado-a-fuerte** → [ADR 0022](../docs/adr/0022-the-strong-regime.md). El titular horizontal era un **intervalo, no un número**: la lente de 10 cm vale **entre 8.4 y 11.2**, porque las dos filas se habían calculado con onda plana a **3.16 rangos de Rayleigh** | [archivo](archive/LAST_CHANGES-37-38.md) |
| §38 | 2026-09-15 | `extinction.py` → [ADR 0023](../docs/adr/0023-traceable-extinction.md). La extinción deja de ser una **entrada** del escenario: **0.230 dB cenitales —el aire más limpio del código meteorológico de la UIT— cuestan el 22.7 % de la clave certificada** del día de referencia | [archivo](archive/LAST_CHANGES-37-38.md) |
| §39 | 2026-09-15 | El **régimen de escintilación pasa a ser un campo** del escenario, y con ello entra en el hash. Los 30 m de la estación valen **+457 bits en régimen débil y −206 en saturado**: el cruce está en 27.02° y el día pasa el 67.7 % de sus segundos por debajo | [archivo](archive/LAST_CHANGES-39.md) |
| §40 | 2026-09-17 | El **camino horizontal pasa de biblioteca a escenario** → [ADR 0024](../docs/adr/0024-the-horizontal-scenario.md), [0025](../docs/adr/0025-two-terminals-one-way.md). GE-1 a 1 km certifica **253 935 bit/s** en una sesión de 60 s, y el **acantilado de los 5 km** es lo que impide dimensionar con el número asintótico | [archivo](archive/LAST_CHANGES-40.md) |
| §41 | 2026-09-19 | **Las notas dejan de caber en la sesión que las tiene que leer.** `LAST_CHANGES.md` llegó a **6 834 líneas**; la regla de las cinco entradas vivas y sus dos cotas derivadas se asertan en `tests/unit/test_notes.py`. **240 de los 241 números** del ROADMAP ya vivían en un ADR, un test o un docstring | [archivo](archive/LAST_CHANGES-41.md) |
| §42 | 2026-09-19 | **Las dos decisiones que llevaban cincuenta días sin dueño lo tienen**: los ADR [0026](../docs/adr/0026-the-language-ladder.md) y [0027](../docs/adr/0027-four-levels-of-distribution.md). Y los **55.6 s** de sesenta satélites resultaron medir un bucle en serie, no la aritmética | [archivo](archive/LAST_CHANGES-42.md) |
| §43 | 2026-09-19 | **La CLI existe** → [ADR 0028](../docs/adr/0028-the-cli-computes-nothing.md). Un resultado horizontal tiene **su propia forma de directorio**, y el despacho es sobre qué método ofrece el resultado, **sin un método en común** | [archivo](archive/LAST_CHANGES-43.md) |

---

## 44. La fila que faltaba, y la tabla de validación deja de ser un comando

**Fecha:** 2026-09-19. **ADRs nuevos:** ninguno — la etapa 8 ya tenía el suyo,
el [0018](../docs/adr/0018-validation-is-a-table-not-a-badge.md), escrito en §43
cinco días antes de que existiera lo que gobierna.

**La cifra que resume la entrada: la tabla pasa de 22 casos de tres fuentes a
35 de ocho, y de un desacuerdo publicado a ocho — siete de ellos del paper del
que sale el enlace de referencia entero, que hasta hoy no tenía ni una fila.**

### 1. El problema, que no era escribir un módulo

`validation/` existía desde §42 con `base.py`, `channel.py`, `satquma.py` y
`micius.py`: 22 casos, el 100 % de cobertura, y una regla que **deriva** el
estado de cada comparación en vez de aceptarlo escrito a mano. Lo que no tenía
era a Ntanos et al. 2021.

Y eso no es «una fuente menos». Ese paper aporta el receptor (los nanohilos
superconductores, su tiempo muerto, su puerta, su tasa de cuentas oscuras), el
transmisor (la apertura de 0.15 m y los 0.75 µrad de jitter de apuntado), los
parámetros del protocolo (las dos intensidades señuelo y la razón de estados), la
radiancia de la noche de estudio y las tres estaciones griegas. Prácticamente
todo lo de `scenarios/reference_castelldefels.yaml` que no es una coordenada de
Castelldefels salió de ahí.

**Una tabla que cubre las recomendaciones de la UIT y dos sistemas externos, y
deja fuera el paper del que está montado el enlace, dice «validado» sobre
exactamente las partes que nadie tenía en duda.** El `__init__.py` lo decía con
todas las letras —«anything reported as validated against Ntanos et al. traces
to the assertions in `tests/channel/` and `tests/qkd/`, not to a row here»— y
esta PR es la que lo cierra.

### 2. Lo primero fue volver a medir, y una cifra estaba mal escrita

`PENDING_DISAGREEMENTS` guardaba seis desacuerdos conocidos, cada uno en una
línea, **descritos pero no alcanzables**: ningún caso los producía, así que
ningún test podía comprobarlos en ninguna dirección. Antes de escribir nada se
recorrieron los seis contra el árbol de hoy, que ha cambiado desde que se
midieron: han entrado la extinción trazable (ADR 0023), el régimen saturado
(0022) y el camino horizontal (0024).

**Cinco reproducen exactamente lo que decían.** La Ec. (5) sigue siendo 8 veces
mayor (ratio `8.000000000000`, 9.03 dB, transmitancia 1.358 con sus propios
parámetros); el «4:1:16» contra «q = 2/5» sigue discrepando por 4.2 (0.09524
contra 0.4); la luna llena sigue dando 76 385.6 cps donde el paper dice 10 kcps
como mucho; los 20 dB de §4.2.1 siguen dando 19.0935 dB con 0.906 dB de residuo.

**La sexta estaba escrita con un número que no es.** La entrada decía que la
razón de aperturas de §4.3.2 —«about four times» entre Helmos (2.3 m) y Skinakas
(1.3 m)— vale «3.06 **at every elevation tested**». Medido ahora, la razón es
3.056 en el cenit y **3.249 a los 20°** que es su propio suelo de elevación:

| elevación | razón Helmos/Skinakas |
|---|---|
| 90° | **3.056** |
| 45° | 3.088 |
| 20° | **3.249** |

El 3.06 era el valor cenital leído como si fuera una meseta. La conclusión
cualitativa no cambia —la afirmación falla en todo su rango, por entre el 19 % y
el 24 %— pero **la cifra citada era una sola donde hay un intervalo**, que es
exactamente el defecto de §14.1 y de §37 otra vez. Sube como fila con el
intervalo medido y con el test que lo mide.

### 3. Las trece filas nuevas, y por qué son tres fuentes en un módulo

`ntanos2021.py` colecciona **tres** fuentes y no una, porque no son
independientes: Ntanos et al. evalúan su enlace con las fórmulas de estado
señuelo de **Ma et al. 2005** (su Apéndice A son las Ecs. (10)–(11) de Ma con
otros símbolos) y este proyecto cobra el bloque finito de un pase con la cota de
**Lim et al. 2014**. Separarlas en tres ficheros pondría la ganancia del mismo
enlace en tres sitios.

| fila | estado | qué dice |
|---|---|---|
| `divergence-full-angle` | reproducido | 13.157 µrad contra «about 13». El **ángulo completo**: leerlo como semiángulo borra 6 dB |
| `eq5-printed-gain-product` | **no reproducido** | 1.358 contra 0.156. Factor 8 exacto, y una transmitancia de 1.358 es un receptor recogiendo un 36 % más luz de la emitida |
| `eq18-scintillation-quantile` | reproducido | −1.28190 contra −1.28188 dB. Reproduce, y **el hallazgo es el signo** |
| `best-case-total-loss` | compatible | 20 dB contra 19.0935. El residuo de 0.906 dB cabe en una extinción que el paper no declara |
| `zenith-transmittance` | hueco | su Ec. (7) necesita `L_zen` y el paper no lo da en ninguna parte |
| `eq20-background-click-probability` | **no reproducido** | 3.4153 contra 0.9671. La forma impresa **no es una probabilidad** |
| `full-moon-background` | **no reproducido** | 76 385.6 cps contra «10 kcps at most» |
| `protocol-efficiency-as-printed` | **no reproducido** | 0.09524 contra 0.4, factor 4.2, dentro de una sola frase suya |
| `single-pass-peak-skr` | **no reproducido** | 1.053e-3 contra 3.33e-4 bits/pulso |
| `aperture-ratio-helmos-skinakas` | **no reproducido** | 3.056 contra «about four times» |
| `skinakas-latitude-as-printed` | **no reproducido** | 35.2118 contra los 24.8981 que el §2 etiqueta «latitude» |
| `ma2005.eq10-gain-adds-instead-of-uniting` | compatible | el solape doblemente contado, calculado **exacto** |
| `lim2014.printed-detection-rate` | reproducido | 5.010744e-4, la ancla de que la cota finita recibe el canal contra el que se publicó |

### 4. El hallazgo de la ronda: dos afirmaciones suyas no son compatibles entre sí

`single-pass-peak-skr` es la fila que no existía en ninguna forma, ni siquiera
como línea en `PENDING_DISAGREEMENTS` medida. §4.3.1 imprime un pico de
**3.33e-4 bits secretos por pulso**; con su protocolo, su ruido nocturno y su
propia mejor geometría este proyecto da **1.053e-3**, 3.16 veces más.

Eso por sí solo sería un desacuerdo más. Lo que lo convierte en un hallazgo
**sobre el paper y no sobre este proyecto** es expresar la diferencia en la
unidad en la que el paper también se pronuncia. Los bits secretos por pulso son
monótonos en la pérdida total, así que hay **una sola** pérdida que aterriza en
3.33e-4, y es de **24.074 dB** (raíz por `brentq`, no transcrita). Su §4.2.1
declara el mejor caso en **20 dB**.

**Ninguna pérdida compatible con su §4.2.1 produce el pico de su §4.3.1: las dos
afirmaciones impresas están a 4.07 dB una de otra**, bajo cualquier análisis de
señuelo que reproduzca su propio Apéndice A. Las dos entran en la tabla, y
ninguna de las dos se usa como ancla.

### 5. La otra mitad del patrón: una media no es una probabilidad, tres veces

Tres de las filas son el mismo error hecho tres veces en dos papers, y merece
nombrarse junto:

- La Ec. (20) de Ntanos llama «probability» a `t_gate × cps`, que es el número
  **esperado** de cuentas: con la luz solar brillante que tabula la UIT a 850 nm
  y su telescopio de 2.3 m vale **3.42**, y **1.09** con el intermedio.
- La Ec. (A6) suya escribe `Y_0 = P_dc + P_noise`, una suma donde la unión es
  `1 − (1−P_dc)(1−P_noise)`.
- La Ec. (10) de Ma et al. escribe la ganancia como `Y_0 + (1 − e^{−ηµ})`, que
  dobla la cuenta de las puertas donde disparan los dos. Por encima de **7.152
  cuentas por puerta** pasa de 1, y `KeyRate` la rechaza.

La de Ma entra como **`COMPATIBLE`** y no como desacuerdo, y es la fila que mejor
usa la maquinaria del ADR 0018: el residuo entre la forma impresa y la exacta
**no se acota, se calcula** —es exactamente `Y_0 (1 − e^{−ηµ})`, el solape—, así
que el `AccountedTerm` tiene intervalo degenerado y la tolerancia puede ser
1e-12 relativo. Medido, la diferencia entre el residuo y el término es **4e-17
absoluto**. De noche el solape son 6.2e-10 y nadie necesitaba la corrección; con
el cielo modelado aquí la forma impresa va alta un 0.078 % y sigue subiendo.

La regla de este proyecto, en una línea, y es la misma en los tres sitios: **las
medias se suman y la exponencial se hace una vez, al final.**

### 6. Las tolerancias, que es donde una tabla así se cae

Ninguna fila que reproduce pasa por una anchura elegida. Dos de las tres son
identidades y se pueden enseñar:

- **`eq18-scintillation-quantile`, 1.3e-5 relativo.** No es un margen: el paper
  imprime el factor néper-a-decibelio como `4.343` donde vale
  `10/ln 10 = 4.342944819`, y `4.343 / (10/ln 10) − 1 = 1.2706e-5` **es el
  residuo entero**. No queda nada más que separe las dos expresiones.
- **`lim2014.printed-detection-rate`, 3e-7 relativo.** Derivada del truncamiento:
  este proyecto calcula la unión exacta de dos detectores `(1 − p_dc)²` y el
  paper imprime su primer orden `1 − 2 p_dc`, así que el valor publicado es mayor
  en `p_dc² e^{−x}`, que relativo a `D_k` es como mucho `p_dc/2 = 3e-7`. Medido:
  **7.2e-10**, tres órdenes por debajo de su propia cota.

Y la de la Ec. (5), que es la que más trabajo costó defender, porque la fila
**falla** y una tolerancia generosa ahí es conservadora: **10 % del valor
publicado**, sacada de lo que la lectura *que sí conserva la energía* se separa
de la integral gaussiana en las tres estaciones del paper — 0.94 %, 2.8 % y
8.8 % a 0.75, 1.3 y 2.3 m, porque la forma de producto lineariza `1 − exp(−x)` y
usa el radio de campo lejano `w_0 z` en vez del `W(z)` exacto. El 10 % cubre las
tres y sigue dejando el factor 8 fuera por ochenta veces.

### 7. `docs/validation.md` se commitea, y por qué eso necesita un test

El fichero se genera con
`uv run python -m quoss.validation --write docs/validation.md` y **entra en el
repositorio**. Las dos audiencias son distintas y solo una puede ejecutar algo:
el comando sirve a quien tiene checkout; el fichero commiteado sirve a quien lee
el repositorio en una página web, a quien revisa una PR y —el caso que lo
decide— a quien quiere saber **qué ha cambiado**. Un fichero generado que no se
commitea no tiene diff, así que un refactor que moviera la varianza de la Tabla 2
de la P.1622 a 1.55 µm de 0.0659 a 0.0759 cambiaría un estado y no dejaría
rastro en el historial.

Y commitearlo obliga al test, porque **un fichero generado commiteado es una
afirmación sobre el código**. En cuanto el documento diga `reproduced` de un caso
que el código ya llama `not reproduced`, es peor que si no existiera: es
exactamente la insignia que el ADR 0018 existe para impedir, impresa en Markdown
y con una tabla alrededor para parecer comprobada. `tests/validation/test_docs.py`
lo compara **byte a byte** —el renderizador se escribió para eso: sin marcas de
tiempo, sin tiempos de ejecución, cuatro cifras significativas y fuentes en orden
de primera aparición— y el mensaje de fallo dice el comando que lo arregla y que
el diff es la parte interesante.

### 8. Lo que **no** entra, y su razón medida

`lim2014.block-1e4-reach` se queda en `PENDING_DISAGREEMENTS`, ahora como única
entrada y con la razón escrita. Lim et al. afirman que «even if we use a block
size of 1e4, cryptographic keys can still be distributed over a fiber length of
135 km», y este proyecto no lo reproduce: con un bloque de 1e4 detecciones en la
base de clave no certifica **nada a ninguna distancia**, y la curva que sí llega
a 135 km es la de una década más.

Está medido y asertado en `tests/qkd/test_finite_key.py::TestLim2014Evaluation`.
Lo que falta para convertirlo en fila es su optimización sobre cinco parámetros
libres, unas **120 líneas** de transcripción que viven junto a ese test. Subirlas
a `src/` para comprar una fila dejaría al proyecto con **dos implementaciones de
una misma sección publicada**, y una fórmula en dos sitios es el defecto que el
[ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md) existe
para evitar: se separan, y la que se separa es la que nadie ejecuta. Un hueco
declarado con su medición nombrada es la respuesta honesta más barata, que es la
misma regla que el ADR 0009 aplica a las citas.

### 9. Dos citas rotas que aparecieron por el camino

Las dos eran a tests que no existen, que es la clase de defecto que cerró la
inconsistencia #17 para las citas a la guía:

- `base.py` decía que el coste de `run_all` estaba medido en
  `TestRunAll::test_the_whole_table_runs_in_under_ten_seconds`. **No existe ni
  existió.** Sustituido por lo que sí hay y lo que sí se mide: las 35 filas
  tardan unas **0.2 s** juntas, porque todas son formas cerradas o una sola
  integral sobre la rejilla de 139 capas de la UIT.
- `tests/validation/cases.py` decía que «the one file that does use the real
  table is `test_table.py`». Tampoco existe; los que usan la tabla real son
  `test_base.py::TestTheTableRuns` y, desde hoy, `test_docs.py`.

Ninguna de las dos la caza `test_every_guide_section_cited_from_the_code_exists`,
que solo recorre citas con número de apartado a los ficheros de `notes/`. Se
anotan aquí en vez de abrir inconsistencia porque están arregladas, pero **la
clase sigue abierta**: nada comprueba hoy que un identificador de nodo pytest
citado en un docstring exista. Lo que sí se comprueba, desde §42, es que el
*fichero* exista, que es la mitad barata.

### 10. Verificación

`uv run pytest`: **3 866 passed**, 0 fallos (3 853 antes). `ruff check`,
`ruff format --check` y `mypy` limpios sobre **163 ficheros**. Cobertura de
líneas **y ramas al 100 %** en todo `src/quoss` — 9 025 sentencias y 2 146 ramas,
sin una sola sin cubrir —, incluido `validation/ntanos2021.py` (117 sentencias,
0 ramas) y el paquete `validation/` entero (433 sentencias, 72 ramas).

`uv run python -m quoss.validation --quiet` sale 0, que es lo que tiene que
hacer con ocho desacuerdos en la tabla: **un desacuerdo publicado no es un fallo
del generador**, y la puerta que sí falla ante uno inesperado es
`tests/validation/test_base.py` contra `EXPECTED_DISAGREEMENTS`, en las dos
direcciones.

**El camino de lectura obligatorio sube otra vez**, y conviene decirlo en vez de
redondearlo: de 1 578 a **1 725 líneas** (`LAST_CHANGES.md` 1 141 → 1 276 con §39
archivado y §44 dentro, `ROADMAP.md` 351 → 363, `GUIA_REIMPLEMENTACION.md` 86).
Archivar §39 quitó 143 líneas y esta entrada pone 273, así que el saldo es +147
pese al archivo. **La cota que decide si eso está bien no es el total** —§41
midió por qué no puede serlo— sino la estructural de `tests/unit/test_notes.py`,
y se cumple con margen: cinco entradas vivas (§40–§44), la más larga 273 contra
un techo de 320, cabecera en 67 contra `60 + 2 × 39 = 138`.

### 11. Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/validation/ntanos2021.py` | nuevo. Trece casos de tres fuentes, y las cuatro ecuaciones publicadas transcritas |
| `src/quoss/validation/base.py` | `CASE_MODULES` vuelve a cuatro; `EXPECTED_DISAGREEMENTS` pasa de 1 a 8 y `PENDING_DISAGREEMENTS` de 6 a 1, con su razón; la cita rota del coste |
| `src/quoss/validation/__init__.py` | el párrafo «lo que falta» pasa a ser el recuento de hoy, sin borrar por qué faltaba |
| `docs/validation.md` | **nuevo y commiteado.** 207 líneas, 35 filas, generado |
| `tests/validation/test_ntanos2021.py` | nuevo. Las dos afirmaciones de §4.3 que nadie había medido, el hueco asertado como hueco, y la mezcla de estados |
| `tests/validation/test_docs.py` | nuevo. El fichero commiteado contra un render fresco, byte a byte |
| `tests/validation/test_base.py` | el test de ausencia se invierte y dice que se invirtió; la entrada pendiente que queda |
| `tests/validation/cases.py` | la cita a `test_table.py`, que no existe |
| `notes/ROADMAP.md`, `README.md` | etapa 8 cerrada, hito B alcanzado y qué significa, 35 casos |
| `notes/LAST_CHANGES.md`, `notes/archive/LAST_CHANGES-39.md` | §39 archivado con la comprobación de dónde vive cada cosa suya |
| `pyproject.toml` | los «40 MB» de pyarrow, medidos: son **152 MiB** |

### 12. Un número falso que defendía una dependencia, de paso

El comentario del extra `export` en `pyproject.toml` decía que pyarrow «is 40 MB
and not a physics dependency». Medido
(`du -sh .venv/lib/python3.13/site-packages/pyarrow`, CPython 3.13, Linux
x86-64): **152 MiB**, 3.8 veces lo que afirmaba, y **más que numpy y scipy
juntos** (31.6 + 90.4 = 122 MB de bytes de fichero contra los 157 de pyarrow).

Se arregla y se comprueba lo segundo, que es lo que pedía la regla: **la decisión
que ese número defendía sigue en pie, y con la cifra real es la única lectura que
queda.** Un extra, nunca un requisito del núcleo de física — porque este formato
opcional resulta ser lo más grande que el proyecto puede arrastrar, más que toda
la pila numérica sobre la que está construido. Un comentario que defiende una
dependencia con un número que nadie comprobó es el mismo defecto que persigue el
[ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md), una
capa fuera de la física.
---

## 45. El wheel lleva sus datos, y una cita a un fichero deja de poder envejecer sola

**Fecha:** 2026-09-19. **Ningún módulo de física tocado.** ADRs tocados:
[0015](../docs/adr/0015-external-data-isolation-and-snapshots.md) («Lo que esto
cuesta», que tenía este defecto escrito como aplazado) y
[0027](../docs/adr/0027-four-levels-of-distribution.md) (el segundo de los dos
defectos de nivel 0 que su medición destapó). **Cierra la
[inconsistencia #18](INCONSISTENCIAS.md).**

**La cifra que resume la entrada: el wheel pasa de 90 a 95 entradas, y con ellas
un `pip install quoss` deja de ser una promesa incumplida. Y la comprobación que
lo demuestra no es que los ocho tests nuevos pasen, es que devolviendo el defecto
a mano fallan cinco de los ocho — y los tres que pasan son los tres escenarios.**

### Qué es un «dato de paquete», antes de nada

Un proyecto Python tiene dos clases de fichero que no son código. Están los del
**repositorio**: el `README`, los tests, los escenarios de ejemplo, el `.github/`.
Y están los que el programa **necesita para funcionar**: aquí, el catálogo de
estaciones ópticas (`ogs.yaml`, cuatro telescopios con sus coordenadas) y los dos
*snapshots* —respuestas reales de Celestrak y de Open-Meteo, congeladas con su
fecha y su SHA-256, para que la demo corra sin wifi.

La diferencia no es de contenido, es de **quién los tiene que ver**. Un test solo
lo ejecuta quien clona el repositorio. El catálogo lo abre el programa, y el
programa lo puede estar ejecutando alguien que nunca ha clonado nada: `pip
install quoss` y `quoss run`. Un fichero de la segunda clase se llama **dato de
paquete**, y la regla que lo define es física antes que conceptual: **tiene que
estar físicamente dentro del directorio del paquete**, porque el directorio del
paquete es lo único que se copia dentro del `.whl`.

Un **wheel** (`.whl`) es un ZIP con un nombre normalizado. `pip install` lo
descomprime dentro de `site-packages` y no hace nada más listo que eso. Lo que no
estaba en el ZIP no existe en la instalación, y no hay mensaje que lo diga.

### Qué pasaba, y por qué la suite entera no podía verlo

`data/ogs.yaml` y `data/snapshots/` vivían en la **raíz del repositorio**, fuera
de `src/quoss/`. Los dos lectores los encontraban subiendo tres directorios desde
sí mismos:

```python
DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parents[3] / "data" / "ogs.yaml"
```

Desde `<repo>/src/quoss/io/stations.py`, tres niveles arriba es `<repo>`. Correcto,
y correcto **solo mientras el módulo esté dentro del repositorio**. Desde
`<venv>/lib/python3.13/site-packages/quoss/io/stations.py`, tres niveles arriba es
`<venv>/lib/python3.13/`, que es del intérprete y no tiene nada que ver con QuOSS.
Medido el 2026-09-19 con el wheel instalado en un `.venv` limpio fuera del
checkout, `load_station_catalogue()` levantaba:

```
DataError: Station catalogue not found at
  /tmp/.../venv/lib/python3.13/data/ogs.yaml
```

Ruidoso, que es la regla del proyecto funcionando —«prohibido degradar en
silencio»— y **aun así una promesa incumplida**, porque no había ninguna ruta que
el usuario pudiera haber puesto: el fichero no estaba en el wheel. Sus 90 entradas
eran `quoss/**/*.py` y el `dist-info`, y nada más.

**Y por qué 3 875 tests en verde no lo veían.** Porque todos corren sobre el
checkout. `uv run pytest` pone `src/` en el path y la física no se entera de si el
paquete está instalado: en el árbol, los datos **sí** están tres directorios
arriba, así que cualquier aserción escrita contra el checkout pasa igual antes y
después del arreglo y no prueba nada. Este es el mismo argumento que obligó al
test del *console script* de la etapa 7 a lanzar `quoss` como subproceso: un
`import` no ve una cadena de *entry point* equivocada, y un checkout no ve una
entrada que falta en un ZIP.

### El arreglo: una sola ancla, dentro de lo que se copia

`data/` pasa a `src/quoss/data/`, y `src/quoss/data/__init__.py` define la única
ancla:

```python
DATA_ROOT = Path(__file__).resolve().parent
```

**Un** directorio por encima de sí misma, no tres por encima de otro módulo. La
diferencia es que ese directorio está *dentro* de lo que el backend de
construcción copia, así que la expresión da el mismo resultado en el checkout y
en `site-packages`. `DEFAULT_CATALOGUE_PATH` y `DEFAULT_SNAPSHOT_ROOT` se derivan
de ella, de modo que los dos lectores coinciden por construcción y no porque dos
copias de la misma expresión sigan en paso.

Es también la razón de que sea un módulo con `__init__.py` y no un directorio
suelto: `quoss.data` importable es lo que garantiza que **cualquier** backend lo
trate como paquete, no solo hatchling con esta configuración concreta.

Lo que **no** cubre, dicho en su docstring en vez de descubrirse: un paquete
zipimportado (`python app.pyz`), donde `__file__` nombra una entrada dentro de un
archivo y no hay directorio que abrir. Ninguno de los cuatro niveles de
distribución del ADR 0027 distribuye así.

### La comprobación, y por qué la negativa es la que vale

`tests/packaging/test_wheel.py`, ocho tests: construye el wheel en un directorio
temporal (**no** en `<repo>/dist` — un test que escribe dentro del checkout que
está midiendo ha cambiado lo que mide), crea un `.venv` limpio **fuera del
checkout** —comprobado con un `assert` sobre la ruta, no supuesto—, instala el
wheel y desde ahí carga el catálogo, los dos snapshots con su SHA-256 y corre los
tres escenarios.

| Antes | Después |
|---|---|
| 90 entradas, 648 KB | **95 entradas, 671 KB** |
| `<venv>/lib/python3.13/data/ogs.yaml` → `DataError` | `<venv>/lib/python3.13/site-packages/quoss/data/ogs.yaml` → cuatro estaciones |

**Y la parte que de verdad prueba algo.** Un test de empaquetado que solo ha visto
un paquete que funciona es una fotografía de un paquete que funciona. Se devolvió
el defecto a mano —un `exclude` en `[tool.hatch.build.targets.wheel]` que deja
`quoss/data/` fuera del wheel— y **fallaron cinco de los ocho**: las tres entradas
de datos y los dos lectores.

Los otros tres pasaron. Son los tres escenarios, y **pasaron con los datos
ausentes**. Eso no es un agujero, es la medida que explica por qué los dos tests
de lectura tienen que existir: los escenarios commiteados llevan su estación y su
TLE en línea, así que `quoss run` nunca abre `quoss/data/` y no puede notar que no
está. Es literalmente lo que la inconsistencia #18 reportaba —«corre los tres
escenarios y sale 0» mientras el catálogo no cargaba—, reproducido aquí como
control del instrumento.

**Lo que cuesta:** 17.7 s los ocho, de los cuales 15 son física (0.74 s el
horizontal, 4.86 s la bajada, 9.27 s el TLE) y 0.85 s el empaquetado entero
—0.63 s construir el wheel, 0.22 s crear el venv e instalar— con la caché de `uv`
caliente. Barato, así que corre en los cinco jobs de CI y no en uno aparte; y
porque un `skip` que nadie ve es un test que no existe, CI exporta
`QUOSS_REQUIRE_PACKAGING_TESTS=1` y ahí el `skip` por falta de `uv` es un fallo.

### La otra mitad: una cita a un fichero tampoco puede envejecer sola

Mover ficheros es la operación que en §42 rompió catorce citas a apartados de la
guía ([inconsistencia #17](INCONSISTENCIAS.md)). El remedio que allí funcionó fue
un test que resuelve cada cita; aquí había **la misma clase de cita sin cubrir**:
`test_every_guide_section_cited_from_the_code_exists` comprueba que un **apartado**
citado existe, y nada comprobaba que un **fichero** citado exista. Este cambio
movía quince referencias a `data/`, así que el test se escribió **antes** de mover
nada, no después.

`test_every_path_cited_from_the_code_exists` recorre `src/`, `tests/`, `docs/`,
`pyproject.toml`, `CLAUDE.md`, `README.md` y `notes/ROADMAP.md`, y resuelve cada
ruta citada contra tres anclas —la raíz, `src/` y `src/quoss/`— porque el árbol
usa de verdad las tres grafías (`docs/adr/0018-….md`, `quoss/data/ogs.yaml`,
`channel/atmosphere.py`) e imponer una sola haría fallar 140 citas perfectamente
legibles. **Medido: 186 rutas distintas citadas.** Siete no existen, y las siete
están en `PATHS_DECLARED_ABSENT` con su razón escrita —seis son ficheros de las
etapas 9-11 y 2.4 que el propio ADR declara no escritos en la misma frase, y la
séptima es un marcador dentro de un doctest—; cada una lleva además un test que
**aserta que sigue ausente**, de modo que la lista se encoge sola el día que
alguien escriba uno de esos ficheros.

**Comprobado rompiendo una a mano**, como se hizo con las catorce: renombrando
`scenarios/ge1_1km.yaml` a `.yml`, el test falla nombrando **26 líneas** que la
citan; restaurado, vuelve a pasar.

**Lo que no cubre, dicho en voz alta.** Solo comprueba rutas que acaban en una
extensión conocida, así que una cita a un **directorio** —`data/snapshots/`— le es
invisible. No es pereza: en prosa un nombre terminado en barra es indistinguible
de una lista separada por barras, y el árbol tiene el contraejemplo exacto,
`core ← orbits/channel/qkd ← system` en `README.md:205`, que cualquier regla de
forma-directorio lee como una cita de `src/quoss/orbits/channel/`. Un escaneo que
salte con esa frase se apaga en una semana, y un test apagado no protege nada.

### Verificación

`ruff check`, `ruff format --check`, `mypy` (165 ficheros) y **3 883 tests** en
verde, 3 875 antes: los ocho nuevos son los de empaquetado, y los dos de citas
sustituyen a ninguno. Cobertura **100 %** de líneas y ramas sobre las 9 032
sentencias del paquete, el mismo porcentaje que antes — `quoss/data/__init__.py`
entra cubierto, por su doctest.

Y el wheel se construyó e instaló de verdad, que es lo único que esta entrada
podía dar por supuesto y no ha hecho.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/data/__init__.py` | **nuevo.** `DATA_ROOT`, y la defensa entera de por qué el ancla se mueve dentro del paquete |
| `src/quoss/data/ogs.yaml`, `src/quoss/data/snapshots/**` | movidos desde `<repo>/data/` |
| `src/quoss/io/stations.py`, `src/quoss/io/snapshots.py` | las dos rutas por defecto derivan de `DATA_ROOT`; la «limitación» del docstring de `snapshots.py` deja de ser una limitación |
| `src/quoss/io/celestrak.py`, `src/quoss/io/openmeteo.py`, `src/quoss/io/__init__.py` | las citas a los ficheros movidos |
| `tests/packaging/test_wheel.py` | **nuevo.** Los ocho tests, el control negativo y lo que cuesta |
| `tests/unit/test_notes.py` | `test_every_path_cited_from_the_code_exists` y su gemelo que vacía la lista de excepciones |
| `tests/conftest.py`, `tests/io/test_stations.py`, `tests/io/test_snapshots.py` | `data_dir` apunta al paquete; dos tests renombrados para que digan lo que comprueban |
| `.github/workflows/ci.yml` | `QUOSS_REQUIRE_PACKAGING_TESTS=1` |
| ADRs 0015 y 0027, `INCONSISTENCIAS.md`, `ROADMAP.md` | el defecto pasa de aplazado a cerrado, con su medida |

---

## 46. Una cita a un nodo tampoco puede envejecer sola, y una excusa de mypy caducada

**Fecha:** 2026-09-19. **Ninguna física tocada.** ADRs tocados:
[0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md),
[0014](../docs/adr/0014-scenario-contract-and-provenance.md) y
[0022](../docs/adr/0022-the-strong-regime.md), los tres solo en citas.

**La cifra que resume la entrada: once citas a nodos de test estaban rotas, y
una de ellas nombraba un test que no se había escrito nunca — para justificar
que tirar entradas de un registro de degradación no pierde nada.**

### Qué es un «nodo de pytest», y por qué citarlos importa aquí

Un **nodo** es la dirección de un test dentro de la suite:
`fichero.py::Clase::metodo`. Es la unidad que `pytest` sabe ejecutar suelta, así
que una cita a un nodo es una **invitación a comprobar**: el docstring dice «esto
está medido» y el nodo dice dónde correr la medición.

Este proyecto vive de eso. La regla de `CLAUDE.md` —«medido en este repo»
significa medido por un test que corre— convierte cada afirmación numérica en
una cita a un nodo. Hay **132** en el árbol.

### Qué fallaba, y por qué no se veía

§44 dejó dicha la clase: nada comprobaba que un nodo citado exista; solo que el
fichero exista. Un fichero sigue existiendo cuando la clase de dentro se
renombra, así que la cita resuelve a medias y **se lee como perfectamente
específica**. Es el mismo modo de fallo de la inconsistencia #17 —una cita que
resuelve al sitio equivocado en vez de a ninguno— un nivel más abajo.

`test_every_pytest_node_cited_from_the_code_exists` encontró **once**, de cuatro
clases:

| Clase | Cuántas | Ejemplo |
|---|---|---|
| Método citado sin su clase | 4 | `test_the_published_answer_satisfies_keplers_equation` es de `TestPublishedVallado21` |
| Clase renombrada | 3 | `TestTheMaskSweep` por `TestTheMaskSweepInBothRegimes` |
| Sintaxis de nodo para una constante | 1 | `REFERENCE_DAY_NUMBER` de `tests/system/reference.py`, que no es un nodo |
| **Un test que no existía** | 1 | `TestNothingIsDroppedWithTheScratchLog` |

**La última es la que importa.** `engine/horizontal.py`, en su etapa `result`,
recalcula dos cantidades con un `DegradationLog` de usar y tirar, y tirar
entradas de un registro de degradación es exactamente lo que el proyecto
prohíbe. El código llevaba la defensa escrita: el presupuesto hizo las mismas dos
llamadas con el registro de verdad un momento antes, así que todo código que el
registro de pega pueda tener ya está en `degradations`, y tirarlo no pierde nada.
La frase terminaba **«That is asserted, not assumed, by …»** y la clase no
existía. Una afirmación de que algo está asertado, cuando no lo está, es peor que
no decir nada: le quita al siguiente lector la razón para comprobarlo.

Se cerró **escribiendo el test**, no suavizando el comentario. Y se escribió sin
repetir la lista de argumentos —reproducir a mano la llamada que el código hace
es un test que se pone verde justo cuando la copia se desincroniza del original—:
se sustituye el `DegradationLog` que el módulo construye por una subclase que
guarda cada instancia, así que lo que se compara es el registro de pega real.
Con dos longitudes, que son el control del propio test: a 1 km de GE-1 solo habla
la llamada de apuntado, y a 5 km —el acantilado que midió §40, usado aquí como
instrumento— la varianza de Rytov pasa de 1 Np² y habla también la de turbulencia.
Con una sola longitud el test no podría distinguir «la propiedad se cumple» de
«no avisó nadie».

**Comprobado rompiendo una a mano**, como las catorce de §42: renombrando
`TestTheMaskSweepInBothRegimes`, el test falla nombrando la cita de
`engine/sweep.py:57`.

**Lo que hace y lo que no.** Resuelve por **AST**, no pidiéndole a pytest que
recolecte: `pytest` dentro de `pytest` es un problema de estado de plugins, y —la
razón que de verdad decide— la recolección solo ve *tests*, mientras que el árbol
cita legítimamente cosas que no lo son, como la fixture
`tests/channel/test_horizontal.py::ge1_key`. Y une los nodos partidos en dos
líneas, que la prosa produce constantemente: **siete** en el árbol, y sin unirlos
se comprobarían 125 citas en vez de 132.

### La otra mitad: `warn_unused_configs`, una excusa que caducó

`pyproject.toml` lo tenía en `false` desde la etapa 0, con una razón **cierta
cuando se escribió**: las secciones por módulo eran anticipatorias, nombraban
paquetes que el roadmap aún no había creado, y avisar de todas ellas habría sido
ruido puro. Las etapas 1-8 están escritas, así que la excusa caducó — y nada
tenía por qué notarlo. Lo notó una fila del ROADMAP.

Puesto a `true`, nombró **tres** secciones muertas:

- `quoss.kernels.*` en la lista estricta: rigor prometido a un paquete que no
  existe, y que el [ADR 0026](../docs/adr/0026-the-language-ladder.md) declara no
  justificado por ninguna medida de hoy.
- `numba.*` y `pyarrow.*` en la de *stubs* ausentes: ninguno de los dos se importa
  donde mypy mira. numba es de la 2.4; pyarrow se alcanza **solo** por
  `importlib.import_module` en `io/export.py`, a propósito, para que Parquet siga
  siendo un extra — y un módulo que mypy nunca ve no necesita que le perdonen los
  stubs.

Las tres fuera, cada una con su razón escrita en el sitio del que salió.

**Y la bandera sola no cierra la fila**, que es lo que hacía falta decir: mypy la
emite como `note:` y **sale 0**. Una comprobación que no puede fallar no prueba
nada —la regla de tolerancias de `CLAUDE.md`—, así que reportaría la próxima
sección muerta a un log de CI que nadie lee. La mitad que falla es
`tests/unit/test_project_config.py`: cada patrón `quoss.*` tiene que nombrar un
paquete que exista en `src/quoss/`, y cada patrón de terceros, una distribución
que el proyecto declare. Los dos lados por separado y no el mismo, porque
significan cosas distintas: si un `override` de stubs **hace falta** depende de
qué esté instalado, y un test que dependa de los extras es un test que informa de
su entorno en vez de del árbol (§32).

### Lo que esta ronda **no** cierra, y por qué

De las siete tareas vivas del ROADMAP, esta entrada cierra **una** y deja seis,
todas comprobadas contra el árbol de hoy antes de tocarlas. Dos merecen su
medida, porque se empezaron y lo que salió es información:

- **El suelo `numpy>=1.26` no es alcanzable con el `scipy` del lock.** Medido:
  `uv run --with "numpy==1.26.4"` revienta en `scipy/sparse/_sputils.py` con
  `AttributeError: module 'numpy' has no attribute 'long'`, porque el scipy
  resuelto (1.18.0) es de la era numpy 2. Un entorno de mínimos de verdad
  —`numpy==1.26.0` con `scipy==1.11.0` sobre Python 3.11— **sí** se construye, y
  ahí el primer fallo que aparece **no es de numpy**: es `matplotlib==3.8.0`
  contra el `pyparsing` de hoy, `PyparsingDeprecationWarning` convertida en error
  por `filterwarnings = ["error"]`. O sea que el suelo que está sin justificar no
  es solo el de numpy, y el job de mínimos que la fila pide tendrá que fijar
  también el del extra `viz`. La fila se queda abierta **con esta medida escrita**
  en vez de cerrarse con un suelo elegido a ojo.
- **`--all-extras` en CI:** comprobado que ni `numba` ni `fastapi` se importan en
  ningún sitio que la suite toque, así que los extras `accel` y `web` son peso
  muerto en los cinco jobs. Lo que falta es la medida del tiempo que cuestan en
  CI, que es lo que la fila pide y no se ha hecho.

Las otras cuatro —Brouwer-Lyddane, Vallado §9.6, la reducción GCRF↔ITRF completa
y el paralelismo del bucle sobre satélites— siguen como estaban, y ninguna es de
esta ronda: las cuatro son trabajo de una etapa, no de una fila.

**Y `benchmarks/` sigue vacío.** La puerta de regresión que la etapa 11 pide no
está escrita, y decirlo aquí es preferible a un directorio con un `.gitkeep` que
parece que sí.

### Verificación

`ruff check`, `ruff format --check`, `mypy` (166 ficheros, ahora con
`warn_unused_configs` activo y sin nota) y la suite en verde.

### Ficheros

| Fichero | Qué |
|---|---|
| `tests/unit/test_notes.py` | `test_every_pytest_node_cited_from_the_code_exists`, su gemelo que vacía la lista de excepciones, y el unido de nodos partidos en dos líneas |
| `tests/engine/test_horizontal.py` | `TestNothingIsDroppedWithTheScratchLog`, el test que el comentario decía que existía |
| `tests/unit/test_project_config.py` | **nuevo.** La mitad que falla de `warn_unused_configs` |
| `pyproject.toml` | `warn_unused_configs = true` y las tres secciones muertas fuera, cada una con su razón |
| `tests/channel/test_atmosphere.py`, `tests/io/test_export.py`, `tests/e2e/test_reference_scenarios.py` | citas arregladas |
| `src/quoss/scenario/models.py`, `src/quoss/engine/sweep.py` | citas arregladas |
| ADRs 0013, 0014 y 0022 | citas arregladas; la del 0014 además dice que desde el ADR 0023 lo que se aserta es el par |
| `notes/ROADMAP.md` | la fila de `warn_unused_configs`, cerrada; las de numpy y los extras, con su medida |

---

## 47. Los tres expedientes: el simulador deja de ser código y pasa a ser respuesta

**Fecha:** 2026-09-19. **ADR nuevo:**
[0029](../docs/adr/0029-a-dossier-is-generated.md). **Física tocada: ninguna** —
ni un modelo, ni una constante, ni una tolerancia.

**La cifra que resume la entrada: tres documentos de 382 líneas que nadie
escribió a mano, y tres cifras que el resultado no llevaba y que subieron al
resultado en vez de bajar al informe.**

### Qué es un expediente, y por qué no lo cubría nada de lo que ya había

Hasta hoy este proyecto producía **números**: un objeto resultado, un CSV, una
fila de `docs/validation.md`. Lo que no producía es el documento con el que
alguien **decide** — si comprar una lente de 10 cm, si prestar un banco óptico,
si una estación de montaña vale su carretera.

Un **expediente** es ese documento. No es un artículo y no es un ADR: un ADR
registra una decisión que este proyecto ya tomó, y un expediente dice lo que el
modelo afirma sobre un experimento **que todavía no existe**, con cada cifra
llevando su unidad y la decisión que cambia. Son tres, en `docs/experiments/`,
generados desde los escenarios por `quoss dossier`:

| Documento | Desde | Líneas | Qué decide |
|---|---|---|---|
| [`GE-1.md`](../docs/experiments/GE-1.md) | `scenarios/ge1_1km.yaml` | 157 | arquitectura, presupuesto, lente, distancia, bloque |
| [`GE-0b.md`](../docs/experiments/GE-0b.md) | `scenarios/ge0b_bench.yaml` | 87 | qué pregunta de GE-1 contesta el banco y cuál no |
| [`reference-link.md`](../docs/experiments/reference-link.md) | `scenarios/reference_castelldefels.yaml` | 138 | qué pases programar, dónde la máscara, cuál enlace de Ntanos |

### Por qué se generan y se commitean, que es la decisión entera

**Porque el modo de fallo contrario está medido dos veces en este repositorio.**
Los «219 km» vivieron en quince sitios, defendidos en prosa cada vez, y eran
**5.9 veces menores** que la respuesta (§14). §46 cerró la misma familia en los
docstrings. Nada lo cazó porque nada podía: **la prosa no corre**.

**Y un expediente es peor que un docstring en exactamente una cosa: se lleva a
una reunión.** Un docstring rancio engaña a quien abre el fichero, que tiene el
código delante. Un expediente rancio engaña a una orden de compra, y su lector
**no tiene checkout ni motivo para tenerlo**. Para ese lector el fichero
commiteado *es* el artefacto.

Así que el arreglo es el de tres piezas que `docs/validation.md` tiene desde la
etapa 8: se genera, se commitea, y `tests/dossier/test_docs.py` lo vuelve a
renderizar y compara **byte a byte**. El renderizado está hecho para permitirlo:
sin marcas de tiempo, sin tiempos de etapa, sin el commit de git, cuatro cifras
significativas. Lo único volátil de la cabecera es la versión de QuOSS, y está a
propósito.

**El ejemplo que lo hace no hipotético:** `GE-1.md` dice que a **5 km el enlace
certifica cero bits mientras el cálculo asintótico sigue reclamando 267 678** en
la misma sesión. Si un cambio movía ese acantilado a 3 km y el documento seguía
diciendo 5, el documento sería peor que no existir: un argumento con fuentes y
con hash a favor de montar un enlace que no cierra.

### La mitad de la regla que es fácil saltarse, y lo que costó

**Un constructor puede pedirle corridas al motor y no puede evaluar física.** El
[ADR 0028](../docs/adr/0028-the-cli-computes-nothing.md) lo dice de la CLI; un
generador de informes es esa capa un paso más afuera, y el fallo sería peor,
porque un número calculado en la capa de presentación es un número que **ningún
test de la física cubre**, impreso para quien no puede comprobarlo.

Escribir `GE-1.md` pidió tres cifras que el resultado no llevaba: el promediado
de apertura `A`, el rango de Rayleigh del transmisor, y la longitud a la que
deja de valer la teoría débil. Las tres son **una llamada** a
`quoss.channel`, y hacerla en el informe habría costado una línea. Subieron a
`HorizontalBudgetResults`, donde las rellena el motor y las comprueba
`tests/e2e/test_horizontal_scenario.py` contra la cadena escrita a mano. **La
línea que se habría ahorrado era una línea de física que ningún test de extremo
a extremo alcanza.**

Y las tres tenían ya razón independiente para estar ahí: el
[ADR 0017 §4](../docs/adr/0017-publication-figures.md) prohíbe que
`plot_horizontal_key_against_distance` **adivine** sus dos marcas —«una marca
adivinada parece medida»— y las exige como argumentos; antes de estos campos, la
única forma de dárselas era que el llamante importara `quoss.channel`.

La regla se comprueba leyendo el AST del paquete:
`tests/dossier/test_docs.py::TestTheGeneratorEvaluatesNoPhysics` falla si
aparece un import de `quoss.channel`, `quoss.qkd`, `quoss.system` o
`quoss.orbits`.

### El número que el test cazó, que es el argumento de la ronda en miniatura

El primer borrador de `GE-0b.md` decía que la varianza log-irradiancia del
receptor es «la fila de arriba por la de más arriba» — `A` por la varianza de
Rytov. **Es falso, y de la peor manera: cierto en el banco y falso en el
campo.** La Rytov que el resultado reporta es la de **onda plana** —la cifra de
referencia contra la que los dos enlaces se afinaron—, y lo que ve el detector
es `A` por la varianza puntual de la onda **declarada**:

| | declarada | `A` × `σ_R²` | lo que reporta | factor |
|---|---|---|---|---|
| GE-0b | `plane` | 8.849e-06 | 8.849e-06 | **1, exacto** |
| GE-1 | `spherical` | 0.04745 | 0.01931 | **2.457** |

Ese 2.457 es la razón entre las dos formas cerradas. Lo cazó el test que aserta
los tres campos nuevos, no la lectura del documento — que es exactamente lo que
esta entrada sostiene que pasa cuando una cifra se escribe a mano. El documento
lleva hoy la nota que lo explica, y `A` es un campo propio precisamente porque
dividir una varianza por la otra acierta en el banco y falla por 2.46 en el
campo.

### Lo que los tres documentos dicen, que es lo que se pidió que dijeran

**GE-1.** La arquitectura de dos terminales y su razón (ADR 0025); el
presupuesto término a término; la clave certificada contra distancia con la
banda plana-esférica y la convención del [ADR 0017](../docs/adr/0017-publication-figures.md)
en el texto —**no es una barra de error**, y no está ordenada igual en las dos
lentes—; el acantilado de los 5 km con la cifra asintótica **al lado**; el bloque
declarado a 15/30/60/120 s, que es decisión del operador y no de la geometría
(ADR 0024); y qué compra la apertura, con el factor medido:

| | 25 mm | 100 mm | factor |
|---|---|---|---|
| certificado, `plane` | 882 428 | 16 546 391 | 18.75 |
| certificado, `spherical` | 1 190 150 | 15 236 099 | 12.8 |
| asintótico, `plane` | 3 415 647 | 38 243 273 | **11.2** |
| asintótico, `spherical` | 4 216 914 | 35 461 378 | **8.409** |

Las dos últimas filas **reproducen el intervalo 8.4–11.2** que §37 publicó, sin
haberlo transcrito: salen del barrido. Y el orden se invierte entre lentes, que
es lo que impide tratar la banda como «centro ± anchura».

**Y el cierre obligatorio, con los huecos 20, 21, 22 y 23 y su coste.** El
documento incluye una sección cuyo único propósito es **poner precio a un
decibelio**, porque una salvedad sin magnitud no se puede usar: medido en el
barrido, **un decibelio no modelado cuesta 3 435 865 bits, el 22.6 % de la
sesión**. El hueco 22 —la altura de escala del aerosol, factor 1.67 en
profundidad óptica— vale en GE-1 **exactamente cero bits**, medido de 1200 a
2000 m, porque el escenario declara la visibilidad a la altura a la que corre el
enlace; el documento dice también la condición bajo la que ese cero deja de
valer. El 21 va con su medida de §44: **el término de altitud saturado aterriza
en +4 bits de 449 308** bajo el otro convenio, o sea entero dentro del hueco.

**GE-0b.** Lo de §40, generado en vez de citado: el banco iguala la varianza de
Rytov a precisión de máquina (0.1988 los dos) y deja **2 183 veces menos
varianza en el receptor y 1.416 dB menos de margen**. Y la pregunta al
fabricante escrita para copiar y pegar —qué `D/r_0`, qué número de Rytov y con
cuántas pantallas, **no** si llega a 8.874e-10—, con el criterio de aceptación
que el proveedor no puede adivinar.

**reference-link.** El día (433 442 bits certificados contra 3 779 462
asintóticos), los **dos pases de cuatro que no certifican nada** mientras el
asintótico reclama 520 538 sobre ellos, la máscara con óptimo interior **y en qué
régimen** —8° en `weak`, 5° en `moderate-to-strong` sobre diez ángulos
muestreados, y el documento dice que es una muestra y no una optimización—, y
las tres estaciones con su término de altitud:

| Estación | Altitud (m) | Apertura (m) | Término de altitud (bits/día) |
|---|---|---|---|
| castelldefels | 30 | 0.75 | +490 |
| cholomondas | 850 | 0.75 | +6 193 |
| skinakas | 1 750 | 1.3 | +19 360 |
| helmos | 2 340 | 2.3 | **−25 310** |

**La cuarta fila cambia de signo**, que es el hallazgo: en la estación más alta
de las tres, estar alto **cuesta** clave certificada. El documento pone el aviso
del hueco 21 justo al lado, porque ese hueco decide el signo de esa columna, y
advierte de que lo que la tabla mide no es la cifra publicada que se le parece:
mover una estación al nivel del mar mueve **el arranque del integral de
turbulencia y además su posición geodésica**, mientras los +457 bits publicados
mueven solo lo primero; las dos concuerdan en un ~7 %, que es el tamaño de la
mitad geométrica.

**Y el apartado que esta ronda volvió obligatorio: cuál de los dos enlaces de
referencia de Ntanos se usa.** Su §4.2.1 declara 20 dB de mejor caso y su §4.3.1
imprime un pico que exige 24.07 dB; están **a 4.07 dB**, las dos están impresas,
y no pueden ser ciertas las dos bajo ningún análisis decoy que reproduzca su
Apéndice A. El documento enlaza las dos filas de `docs/validation.md`
—`ntanos2021.best-case-total-loss` (compatible) y
`ntanos2021.single-pass-peak-skr` (no reproducida)— y dice que **ninguna es
ancla**.

### Y los `warnings[]` entran en el documento, no solo en la consola

Los tres llevan una sección con cada código que la física registró al calcular
sus cifras, deduplicado y contado, con el mensaje **entero**. `quoss.cli.report`
ya los imprime en `stderr`, y eso sirve a quien corrió la orden; no sirve a quien
lee el documento, que nunca la correrá. Un `DEGRADED` significa que se
**sustituyó** un modelo, y esa es una frase que quien decide una compra tiene que
poder encontrar sin un terminal. GE-1 registra 169 entradas, el de referencia
329, el banco 8.

### Verificación

| | |
|---|---|
| Suite | **3 952 passed**, 0 fallos (eran 3 904) |
| Coste añadido | **158 s** contra 138 s de base, medido en esta máquina: **+20 s**, el 14 % |
| Generar los tres | **3.65 s**, de los cuales casi todo son las cuatro corridas de día completo |
| `ruff check` / `ruff format --check` / `mypy` | limpios; `quoss.dossier.*` entra en la lista estricta de mypy |

**El coste de los 20 s merece su línea**, porque es lo que este arreglo cuesta
de verdad: el test byte a byte tiene que **correr la física otra vez**, y no hay
forma de que no la corra. Lo que sí se hizo es que no la corra de más —
`tests/dossier/test_main.py` tiene tres tests y no seis, cada uno haciendo todas
las aserciones que puede desde **una** llamada, porque cada llamada regenera los
tres documentos y CI corre la suite cinco veces.

### Ficheros

| Fichero | Qué |
|---|---|
| `docs/adr/0029-a-dossier-is-generated.md` | nuevo. Las cuatro decisiones y lo que costó la segunda |
| `docs/experiments/{GE-1,GE-0b,reference-link}.md` | nuevos, generados y commiteados |
| `src/quoss/dossier/` | nuevo: `base.py`, un constructor por experimento, `__main__.py` |
| `src/quoss/cli/dossier.py` | nuevo. `quoss dossier <escenario> --out <doc.md>`; `--out` obligatorio a propósito |
| `src/quoss/scenario/result.py` | `HorizontalBudgetResults` gana `aperture_averaging`, `rayleigh_range_m` y `weak_theory_path_limit_m` |
| `src/quoss/engine/horizontal.py` | los rellena, con la razón escrita donde se calculan |
| `tests/dossier/` | `test_docs.py` (byte a byte, el cierre obligatorio, el AST) y `test_main.py` |
| `tests/cli/test_dossier.py` | el subcomando escribe exactamente lo que el generador produce |
| `tests/e2e/test_horizontal_scenario.py` | los tres campos nuevos contra una llamada directa, y el 2.457 que el borrador negaba |
| `notes/archive/LAST_CHANGES-42.md` | §42 archivada por la cota estructural, con su comprobación |
| `notes/ROADMAP.md`, `README.md` | la etapa 7 incluye `dossier/`; ADRs a veintinueve |

---

## 48. Cuatro directorios que prometían cosas, y dos suelos que no estaban sin probar sino equivocados

**Fecha:** 2026-09-19. **Ningún ADR nuevo. Física tocada: ninguna.**

**La cifra que resume la entrada: `numpy>=1.26` y `scipy>=1.11` llevaban desde
la etapa 0 publicados en los metadatos del wheel, y el entorno que describen
**no existe** — la suite no corre ahí y las dos versiones no son instalables
juntas. Ahora hay un job que construye los suelos, y por eso los suelos son
otros.**

### 1. Los cuatro directorios vacíos, borrados

La raíz tenía `benchmarks/`, `deploy/`, `web/` y `validation/`: cuatro
directorios con un `.gitkeep` dentro y **cero bytes** de contenido, desde el
2026-07-31.

**Por qué borrarlos y no dejarlos.** Decir que la puerta de regresión de
rendimiento no está escrita es mejor que fingirla — pero un directorio vacío la
**finge**, y la finge de la única forma que nada puede comprobar: no hay test
que distinga «aún no escrito» de «se borró y nadie lo notó». El peor de los
cuatro era `validation/`, que con `src/quoss/validation/` lleno al lado se leía
como **una segunda implementación**.

**Y arrastraban configuración muerta.** `[tool.ruff.lint.per-file-ignores]`
tenía `"benchmarks/**"` y `"validation/**"` desde la etapa 0, apuntando a los dos
directorios sin código. Una excepción de lint sobre un directorio vacío no puede
estar haciendo nada, **y no se distingue de una que sí** — y a diferencia de
mypy, `ruff` no tiene `warn_unused_configs`: no lo dice ni como nota. El
`"validation/**"` era el peor de los dos por la misma razón que el directorio:
se leía como si cubriera el código de validación, y no lo cubría, porque ese
código está en `src/quoss/validation/` y ninguna entrada de la tabla lo alcanza.
La excepción y el código que parecía excusar **nunca estuvieron en el mismo
sitio**.

La tabla pasa de tres entradas a una, y
`tests/unit/test_project_config.py::test_every_ruff_per_file_ignore_names_something_that_exists`
es lo único que puede volver a cazarlo.

**Decisión tomada, escrita donde se busca:** la puerta de regresión es de la
**etapa 11**, junto al paralelismo del bucle de `propagator.py:535` que es lo
que mediría. Está en `ROADMAP.md`, que es estado y no promete nada por existir.

### 2. Los suelos de dependencias: medidos, y dos eran falsos

La fila abierta decía «el suelo `numpy>=1.26` no está testeado». Construirlo dijo
algo peor:

| Suelo | Declarado | Qué pasa ahí | Hoy |
|---|---|---|---|
| numpy | `>=1.26` | **La suite no corre.** `np.trapezoid` no existe antes de 2.0 (`tests/orbits/test_geometry.py`), y un doctest de `src/quoss/system/correlated_fading.py` imprime `np.float64(0.951)`, que es el `repr` de escalar de numpy 2 y `0.951` antes. **No hay una sola grafía que sirva para las dos**: `np.trapz` está deprecado *después* de 2.0, y `filterwarnings = ["error"]` convierte eso en fallo | `>=2.0` |
| scipy | `>=1.11` | **No es instalable con el numpy de al lado**: 1.11 y 1.12 fijan `numpy<2`. Y `scipy==1.11.0` está **retirado de PyPI** por violación de licencia, así que el suelo nombraba una versión a la que nadie debería resolver | `>=1.13` |
| pyarrow (`export`) | `>=15` | pyarrow 15 fija `numpy<2`; el par es literalmente insatisfacible, `uv` lo dice así | `>=16` |
| matplotlib (`viz`) | `>=3.8` | **Toda matplotlib por debajo de 3.11 llama APIs que el pyparsing de hoy depreca al importar**, dentro de `_rc_params_in_file`: `parseString` hasta 3.8, `oneOf` hasta 3.10.6. Con `filterwarnings = ["error"]`, eso es un fallo de recogida. Medido contra pyparsing 3.3.2: fallan 3.8.4, 3.9.0, 3.9.2, 3.10.0, 3.10.3 y 3.10.6; **3.11.0 es la primera que no** | `>=3.11` |

pydantic, sgp4 y pyyaml se quedan donde estaban, y ahora con un job detrás. El
job fija el suelo declarado; **no busca uno más bajo**, así que «suelo» aquí
significa «este conjunto exacto pasa», no «nada por debajo podría».

**Y los dos extras que nada importa pierden el suyo.** `accel` (numba) y `web`
(fastapi, uvicorn, pydantic-settings) no los importa ningún módulo de este
repositorio: la etapa 2.4 no está escrita ([ADR 0026](../docs/adr/0026-the-language-ladder.md))
y la 9 tampoco ([ADR 0027](../docs/adr/0027-four-levels-of-distribution.md)). Así
que **ningún job puede fijarlos y averiguar si funcionan**, y un `>=` que ningún
entorno construye no es un suelo: es una esperanza publicada en los metadatos del
wheel, que es la misma clase de afirmación incumplida que persigue el ADR 0016,
una capa fuera de la física. El día que se escriba `kernels/` o `api/`, recuperan
suelo **y** una fila en el job, en el mismo commit.

**La regla es de dos caras y se aserta:**
`test_every_shipped_requirement_is_either_floored_and_pinned_or_neither` exige
que cada requisito que el paquete envía o declare suelo **y** esté fijado por el
job `minimums`, o no declare ninguno **y** esté en `FLOORLESS` con su razón. No
hay tercer estado, porque el tercer estado es lo que había. Y el listado
`FLOORLESS` se aserta en el otro sentido también, como
`PATHS_DECLARED_ABSENT`: una excepción que solo puede crecer es una que nadie
puede fechar.

**El job.** `minimums` en `ci.yml`, Python 3.11 —el más viejo soportado, porque
un suelo que solo se sostiene en el intérprete nuevo no es el suelo que dicen los
clasificadores—, `--isolated --no-project --with-editable .` en vez de
`uv sync`, porque el objetivo es construir el entorno que el lock **no**
describe. Medido: **3 968 passed en 165 s**.

**Y de eso sale un resultado que no se buscaba:** los tres expedientes de §47 se
comparan byte a byte en ese entorno también. Es decir, `docs/experiments/*.md`
son reproducibles sobre **dos pilas numéricas distintas** —numpy 2.0.2 + scipy
1.13.0 y las del lock—, no una fotografía de una máquina.

### 3. `--all-extras` fuera de los cinco jobs, y la medida que lo decide

La fila abierta pedía «la medida del tiempo de CI que cuestan». Medida, y **el
tiempo no era el coste**:

| | caché de uv | entorno instalado | sync en frío | sync en caliente |
|---|---|---|---|---|
| `--all-extras` | 709 MiB | 708 MiB | 4.44 s | 0.56 s |
| `--extra viz --extra export` | 499 MiB | 497 MiB | 3.88 s | 0.17 s |

**210 MiB, el 30 %**, y casi todo es `llvmlite` (172 MiB); el extra `web` entero
son unos 5 MiB. Medio segundo por job en caliente no es una razón para nada.

**La razón que sí lo es:** `--all-extras` se lee como la afirmación de que la
suite ejercita todos los extras, y no lo hace. Los cinco jobs sincronizan
`--extra viz --extra export`. `viz` es obligatorio —`tests/viz` importa
matplotlib en el módulo, así que sin él la recogida **falla** en vez de
saltarse—; `export` no lo es —los tests de Parquet se saltan sin pyarrow— y se
sincroniza igual, porque un test que se salta en todos los entornos es un test
que nadie corre.

### 4. Las cuatro que quedan: tres no tenían etapa viva

La comprobación que pedía la ronda, y devolvió un defecto en vez de un visto
bueno:

| Trabajo | Dónde estaba | Dónde está |
|---|---|---|
| Brouwer-Lyddane | fila suelta, columna «`orbits/`» — **ninguna etapa** | **etapa 2.5** |
| Vallado §9.6 como V2 | fila suelta, columna «etapa 8» — **y la etapa 8 está cerrada** | **etapa 2.5** |
| Reducción GCRF↔ITRF | fila suelta, columna «etapa 8» — **cerrada también** | **etapa 2.5** |
| Paralelismo del bucle | etapa 11 | etapa 11, sin cambios |

**Tres de las cuatro apuntaban a un sitio al que ya nadie vuelve.** Una fila que
nombra una etapa terminada es trabajo que nadie va a leer en el momento en que
importa, que es exactamente el defecto que el directorio vacío de arriba comete
en el otro sentido. La **etapa 2.5** existe ahora, colocada entre las etapas de
física y no después de la distribución, porque ahí es donde está en el orden de
dependencias. Y dice lo que hay que decir de las tres: **ninguna bloquea nada**,
el hito B está alcanzado sin ellas, y ninguna cambia hoy un número publicable.
Ninguna se hace en esta PR.

### Verificación

| | |
|---|---|
| Suite, entorno del lock | **3 968 passed**, 0 fallos, 156 s |
| Suite, suelos declarados (py3.11) | **3 968 passed**, 0 fallos, 165 s |
| `ruff check` / `ruff format --check` / `mypy` | limpios |
| `uv lock` | re-resuelto por los suelos nuevos: 8 líneas |

### Ficheros

| Fichero | Qué |
|---|---|
| `benchmarks/`, `deploy/`, `web/`, `validation/` | **borrados**; eran cuatro `.gitkeep` |
| `pyproject.toml` | suelos medidos; `accel` y `web` sin suelo, con la razón; dos `per-file-ignores` fuera |
| `.github/workflows/ci.yml` | job `minimums`; `--all-extras` → `QUOSS_CI_EXTRAS` en los cinco jobs, con la medición al lado |
| `tests/unit/test_project_config.py` | la regla de dos caras de los suelos, `FLOORLESS`, y los `per-file-ignores` |
| `tests/unit/test_notes.py` | los cuatro nombres siguen en `CITED_ROOTS`, y ahora para lo contrario: hacen **fallar** una cita bajo ellos |
| `tests/io/test_export.py` | los «40 MB» de pyarrow que §44 había medido en 152 MiB y que aquí seguían |
| `docs/adr/0027-…` | la cita a `pyproject.toml:48` pasa a nombrar el extra: un número de línea es una cita que envejece sola |
| `notes/ROADMAP.md` | **etapa 2.5**; la puerta de regresión decidida en la 11; dos filas abiertas cerradas |
| `README.md` | los cuatro directorios, los suelos probados, y `--all-extras` con su coste |
| `notes/archive/LAST_CHANGES-43.md` | §43 archivada por la cota estructural, con su comprobación |

# QuOSS — Últimos cambios

> **Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).**
> Última entrada: **§41, 2026-09-19** — las notas dejan de ser ilegibles.
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

## Índice de lo archivado (§1–§36)

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

---

## 39. El régimen de escintilación deja de ser un argumento y pasa a ser un campo

**Fecha:** 2026-09-15. **ADR tocado:** [0022](../docs/adr/0022-the-strong-regime.md),
con un anexo al final y una cifra suya corregida.

### Qué pasaba

La etapa 1.2 (§37) dejó `ScintillationRegime` y
`saturated_log_irradiance_variance` en `channel/turbulence.py`, y midió con
ellos el resultado de diseño más grande que ha dado el proyecto: **el óptimo de
la máscara de elevación se mueve de 8° a 4.5° y el día gana un 6.4 %**. Pero
`ChannelSpec` no tenía el campo y `engine/pipeline.py` no lo pasaba, así que
**todo eso se midió llamando a las funciones a mano** y `run()` no lo
reproducía.

Por qué importa, más allá de la comodidad: un régimen que no está en el
escenario tampoco está en su SHA-256, ni por tanto en `Provenance.scenario_hash`
ni en la clave de `engine/cache.py`. Dos días que se diferencian un 3.66 %
habrían compartido entrada de caché — la peor clase de caché, que es la que
acierta rápido sobre la física equivocada.

### Lo que hay ahora

`ChannelSpec.scintillation_regime`, predeterminado `WEAK`, pasado a
`downlink_loss_budget` desde `_channel`. Los cinco `scenarios/*.yaml` lo
escriben explícitamente aunque sea el valor por defecto (ADR 0014: un defecto
invisible es un parámetro que todo el mundo recibe sin haberlo elegido), y el
régimen es además **eje de barrido**: `SweepSpec` aplica el punto sobre la forma
JSON del escenario, así que `"moderate-to-strong"` viaja como la cadena que
llevaría un YAML y vuelve como miembro del enum.

`SCHEMA_VERSION` no sube —caso 2: campo opcional nuevo, ningún fichero cambia de
significado— y el digest de referencia se repincha a **`303a3729…`**, con la
entrada de `DIGEST_HISTORY` que lo demuestra borrando exactamente ese campo y
recuperando el `0108a01f…` del día anterior.

### El día de referencia, ahora desde `run()`

| régimen | clave del día | pasos 1 y 3 | cambio |
|---|---|---|---|
| `weak` | 433 442 | 190 807 / 242 635 | — |
| `moderate-to-strong` | **449 308** | 198 673 / 250 635 | **+3.66 %** |

Y el barrido de máscara, que antes era un script, es **un `SweepSpec` de dos
ejes** con ocho puntos y ocho hashes. **Los dos óptimos sobreviven:** 8° en
débil, 4.5° saturado, los dos interiores, y la ganancia sigue siendo monótona en
lo baja que esté la máscara (+11.8 % a 2° contra +1.0 % a 20°).

### La tolerancia derivada, que resultó ser una identidad

El barrido del motor da 409 584 / 425 073 / 435 462 / 361 199 y 458 076 /
462 358 / 457 341 / 364 774, y la tabla del ADR 0022 imprime hasta **786 bits**
menos. No es ruido: es el desajuste del [ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md)
—la tabla del ADR sale de `tests/system/reference.py`, que deja el perfil de
turbulencia en 0 m, y el motor cablea los 30 m de `StationSpec.altitude_m`—. Así
que no se comparó contra una tolerancia elegida sino que se cerró por los dos
extremos, y los dos son **exactos**: las ocho celdas barridas son
`oracle.hand_link` a 30 m bit a bit, las ocho publicadas son la misma cadena a
0 m bit a bit, y por tanto cada residuo **es igual** a `hand(30 m) − hand(0 m)`.
No queda nada que una tolerancia pudiera absorber.

### El hallazgo que salió de ahí: los 457 bits cambian de signo

Los 30 m de la estación valen **+457 bits** en régimen débil —el titular del ADR
0016— y **−206 bits** en régimen saturado. Podría parecer un fallo de cableado y
no lo es; son los dos factores de la Ec. (8) de la P.1622, `σ² = A · σ²_punto`,
moviéndose en direcciones opuestas. Medido a 10°:

| | 0 m | 30 m | cambio |
|---|---|---|---|
| `σ²_punto` débil | 1.5446 | 1.4780 | **−4.31 %** |
| `σ²_punto` saturado | 0.63542 | 0.62602 | **−1.48 %** |
| `A` (promediado de apertura) | 0.072572 | 0.075102 | **+3.49 %** |
| producto débil | 0.112092 | 0.111004 | −0.97 % |
| producto saturado | 0.046113 | 0.047015 | **+1.96 %** |

Quitar los primeros 30 m de aire baja la varianza de Rytov un 4.31 %, pero cerca
de la saturación ese cambio casi no llega a la salida (−1.48 %), mientras que
`A` —que depende de la **altura** de la turbulencia y no de su fuerza— sube un
3.49 % en los dos regímenes por igual. El cruce está en **27.02°**, y el día de
referencia pasa el **67.7 %** de sus segundos en pase por debajo de él
(elevación mediana 17.4°), así que el total hereda el signo de las muestras
bajas. El **hueco 21** del ADR 0009 —el promediado de apertura en régimen
saturado— es exactamente la elección de la que depende ese signo, y sigue
abierto.

### Y una cifra del ADR 0022 y de §37 que estaba corta

Las dos decían que poner el saturado de predeterminado «movería todos los
anclajes V2 del canal un **3.4 %**». Ese 3.4 % es la celda de **1550 nm y
21 m/s**, que es la longitud de onda de este proyecto y **la más favorable de
las ocho**. Medido ahora celda a celda, el desplazamiento va de **−3.4 % a
−21.1 %** (532 nm y 30 m/s: 0.3618 → 0.2855 contra un 0.36 impreso), y **seis de
las ocho celdas** de la Tabla 2 de la P.1622 quedarían fuera de medio dígito
impreso. Está en
`tests/channel/test_turbulence.py::test_what_the_default_would_cost_across_the_whole_published_table`,
que es lo que separa «medido en este repo» de un número que alguien recuerda.

### Lo que costaría el flip, para decidirlo (no se hace en esta ronda)

Medido flipando los defectos y corriendo la suite entera:

| Qué se flipa | Aserciones rojas | De ellas, V2 |
|---|---|---|
| solo `ChannelSpec.scintillation_regime` | **30** | **ninguna** |
| también las siete firmas de la física | **84** | seis celdas de la Tabla 2, la tabla de `validation/`, once de `test_horizontal`, cinco de `test_link_budget` |

Lo interesante del primer caso: entre las 30 está
`TestFilesEqualTheirBuilders`, **porque los cinco `scenarios/*.yaml` ahora
escriben el campo**. Es decir, los escenarios comprometidos seguirían
significando lo que significan; lo que cambiaría es lo que recibe quien no
declara nada.

El precio del segundo no es «mover un 3.4 % los anclajes»: es **perder seis de
los ocho anclajes V2 más fuertes del canal**, y con ellos la frase «este número
es de la P.1622». Lo que se compraría está medido igual de bien: +3.66 % de
clave y una máscara óptima tres grados y medio más baja. **La decisión es del
lector del ADR**, y mientras tanto elegir el saturado para un estudio de máscara
es una línea de YAML.

### Verificación

`uv run pytest`: **3 662 passed**, 0 fallos. `ruff check`, `ruff format --check`
y `mypy` limpios sobre 143 ficheros. Cobertura de líneas **y ramas al 100 %** en
todo `src/quoss` (8 309 sentencias, 2 030 ramas).

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/scenario/models.py` | `ChannelSpec.scintillation_regime` y la defensa del defecto |
| `src/quoss/engine/pipeline.py` | `regime=` hasta `downlink_loss_budget`, y por qué esa línea es la que faltaba |
| `scenarios/*.yaml` | los cinco declaran el régimen, con su comentario |
| `tests/e2e/test_reference_scenarios.py` | los dos regímenes contra la cadena a mano, el barrido de dos ejes, y el signo de los 457 bits |
| `tests/engine/test_sweep.py` | un enum como eje de barrido, y uno inválido rechazado en el punto |
| `tests/scenario/test_models.py` | el defecto del esquema es el de la física, y se comprueba |
| `tests/scenario/test_hash.py` | digest repinchado a `303a3729…`, entrada de `DIGEST_HISTORY` |
| `tests/channel/test_turbulence.py` | lo que costaría el flip, en las ocho celdas |
| `docs/adr/0022-the-strong-regime.md` | anexo del cableado, el precio del flip, y el 3.4 % corregido |
| `notes/ROADMAP.md` | casillas de la etapa 4 y de 2.2 |

---

## 40. El camino horizontal deja de ser una biblioteca y pasa a ser un escenario

**Fecha:** 2026-09-17. **ADRs nuevos:** [0024](../docs/adr/0024-the-horizontal-scenario.md)
(el escenario horizontal, su bloque y la forma de su resultado) y
[0025](../docs/adr/0025-two-terminals-one-way.md) (dos terminales y un sentido
para GE-1). **ADRs tocados:** 0009 (huecos 20 y 21, los dos subidos de categoría
con medida), 0021 (ya no es una biblioteca suelta; la arquitectura decidida),
0022 (anexo: el defecto del régimen se muda a las firmas).

**La cifra que resume la entrada: el enlace de GE-1 de 1 km certifica 253 935
bit/s en una sesión de 60 s — y a 5 km certifica exactamente cero mientras el
cálculo asintótico sigue reclamando 4.4 kbit/s.**

### El problema, y por qué no era «solo cablear»

Desde §36 y §37 `channel/horizontal.py` sabía calcular todo lo de un camino
horizontal, y estaba anclado contra la Tabla 4 de la P.1814. **Y nadie lo
importaba.** Ni `scenario/`, ni `engine/`, ni `system/`. Las consecuencias, de
menos a más grave: no se podía exportar, no se podía barrer, no se podía
dimensionar desde un fichero — y **no había hash**, que es lo que ata una figura
a sus entradas. Todas las cifras publicadas de GE-1 salen de llamadas a mano
dentro de un test, exactamente el problema que §39 arregló para el régimen de
escintilación en la bajada.

### La decisión de forma: una unión discriminada, no campos opcionales

`link: downlink | horizontal`, con `AnyScenario` validada por un `TypeAdapter`.
Lo que compra, y es la razón de elegirla sobre un `Scenario` con `orbit`,
`stations` y `passes` opcionales:

> La regla del ADR 0021 —«ninguna firma acepta elevación»— estaba asertada por
> ausencia y por un recorrido del AST. Ahora lo está **también por el esquema**:
> `HorizontalScenario` no tiene `passes`, y como `SpecModel` lleva
> `extra="forbid"`, escribir `passes:` en un fichero horizontal es un error de
> validación **que nombra el campo**. Nadie tiene que acordarse de comprobarlo.

**Digest repinchado, caso 2:** `17f44003…`. El canónico gana `"link":"downlink"`
y nada más; `SCHEMA_VERSION` sigue en 1 y la entrada de `DIGEST_HISTORY` lo
demuestra borrando ese campo y recuperando el `303a3729…` del día anterior.

### La decisión que más prosa necesitaba: quién es responsable del bloque

El [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md) fijó que el bloque
finite-key **es un pase**, y el argumento no era de comodidad: es que **la
geometría lo fija**. Entre dos pases el satélite está bajo el horizonte y no se
emite ni un pulso.

Un enlace horizontal es estacionario. Nada para los datos. El bloque es lo que el
operador decida, y eso **cambia de quién es la responsabilidad de que la cota sea
válida**: en la bajada el esquema puede impedir que alguien se equivoque; aquí no
puede. Lo único que el código puede hacer es que no se mude en silencio, y hace
tres cosas: el campo es obligatorio y sin defecto, entra en el hash, y cada
ejecución registra `horizontal.block-is-the-declared-session` diciendo la
duración, los pulsos y que nada en la geometría la fija.

**Y lo que vale un bloque está medido**, que es lo que impide leerlo como una
formalidad (GE-1, solo cambia la sesión):

| sesión | bits certificados | bit/s |
|---|---|---|
| 15 s | 3 115 905 | 207 727 |
| 30 s | 7 027 898 | 234 263 |
| 60 s | 15 205 091 | **253 418** |
| 120 s | 32 059 995 | 267 167 |

Doblar el bloque compra **2.164 veces** la clave, no dos: el peaje fijo de 260
bits de la Ec. (1) de Lim et al. y, mucho más grande, las desviaciones de
Hoeffding y de muestreo, que crecen como la raíz del bloque. Leído al revés:
**una sesión declarada más larga de lo que el enlace estuvo estable compra
exactamente ese 16 % de clave que nadie ganó.**

### El resultado es un contenedor propio, y la razón es un número

No un `SimulationResult` con las etapas orbitales vacías. **Arrays de longitud
cero pasan el tipado y son peores que `None`:** una suma sobre un eje vacío es
`0.0`, así que `daily.finite_bits.sum()` reportaría **un enlace horizontal que
certificó 15.2 Mbit como cero bits al día**, sin error en ninguna parte y sin que
ningún consumidor pudiera distinguirlo de un enlace que no cerró.

Las etapas ausentes están **ausentes**: `HORIZONTAL_STAGES` son tres
(`channel`, `key`, `result`) y no siete, porque una etapa que dice tardar cero
segundos se lee como una que corrió deprisa.

### La extinción, reutilizada y no reinventada

`ExtinctionSpec` sigue siendo **un solo tipo**. Lo único que cambia es a qué se
evalúa, y es un paso de integración: la bajada integra la columna
(`zenith_transmittance_from_visibility`), el horizontal **evalúa el coeficiente a
su altura** (`specific_attenuation_at_altitude_db_per_km`, nuevo). Las dos leen
el mismo perfil y comparten el factor exponencial en una privada, así que no
pueden discrepar sobre hacia dónde apunta el exponente.

El campo nuevo es `HorizontalPathSpec.altitude_m`, y está defendido en el ADR
0024: entra **solo** por `exp(-(h - h_v)/H)`, así que en el caso ordinario —la
visibilidad medida donde corre el enlace— **se cancela exactamente** y la altura
de escala del hueco 22 no influye en ningún número. El hueco 23 (absorción
molecular) sigue abierto y sigue diciéndose; no se tapa con la dispersión.

### Los barridos reproducen las tablas medidas a mano

Todo lo que §36 y §37 midieron llamando al canal a mano lo reproduce ahora
`run()` a través de `SweepSpec`. **El residuo es una identidad**, cerrada por los
dos extremos como en §39: el punto del barrido y la cadena a mano son las mismas
llamadas con los mismos argumentos, así que se compara con igualdad exacta y las
cifras impresas a dos decimales se comprueban aparte, como afirmación sobre lo
que se publicó.

| lente | onda | kbit/s asintóticos |
|---|---|---|
| 2.5 cm | plana | 56.82 |
| 2.5 cm | esférica | 70.15 |
| 10 cm | plana | 636.20 |
| 10 cm | esférica | 589.92 |

Factor **11.20** plana, **8.41** esférica — y **el intervalo no está ordenado
igual en las dos lentes**: a 2.5 cm la plana es el borde pesimista y a 10 cm el
optimista, porque el promediado de apertura trabaja sobre el otro factor. Hay
test explícito, y también de que el factor 2.46 de las varianzas de punto es el
mismo en las dos, así que **no** es lo que invierte el orden.

Distancia (10 cm, asintótico): 896/888 a 200 m, 636/590 a 1 km, 122/107 a 2.41 km
(el límite de la teoría débil, comprobado por los dos lados contra el aviso del
propio módulo), 4.0/4.4 a 5 km. `C_n^2` en cuatro décadas, con la varianza de
Rytov exactamente lineal en él. **Y la anchura de puerta, que resulta no ser una
palanca aquí:** 25 veces más ancha mueve la clave un **0.09 %**, porque de noche
a 1 km el ruido entero son 6e-7 cuentas por puerta contra 4e-2 de señal. Medirlo
es lo que impide que alguien la optimice.

### Los dos hallazgos, que son lo mejor de la ronda

**1. A 5 km GE-1 no certifica nada.** Con 60 s de sesión, a 4 km la clave
certificada son 672–843 bit/s y a 5 km es **exactamente cero**, mientras el
asintótico sigue dando 4.0–4.4 kbit/s. Es el acantilado del ADR 0011 —división
por cero en la tasa de error de fase, no un factor— aparecido por primera vez en
un enlace de tierra, y es justo el régimen en que un dimensionado asintótico
diría que el enlace funciona. El resultado lo dice:
`horizontal.session-without-key` lleva la cifra asintótica al lado.

**2. El banco iguala la varianza de Rytov de GE-1 y no iguala lo que ve su
receptor.** El `C_n^2` de `equivalent_bench_cn2_m23` hace coincidir las dos
varianzas de Rytov a precisión de máquina (0.198845). Pero esa es la de un
detector puntual, y lo que llega a la clave es la promediada por la apertura, que
depende de **a qué distancia** está la turbulencia:

| enlace | `σ_R²` | promediado `A` | margen al 1 % |
|---|---|---|---|
| GE-1, 1 km | 0.198845 | 0.2386 | **1.446 dB** |
| GE-0b, 2 m | 0.198845 | 4.45e-5 | **0.030 dB** |

**2 183 veces menos varianza en el receptor, 1.42 dB menos de margen.** Es la
segunda mitad del hueco 20, y a diferencia de la primera —el argumento de las
pantallas de fase, que queda fuera de lo que QuOSS modela— **esta se puede medir
dentro del modelo**. No hace inútil el banco: hace que la pregunta que contesta
sea otra, y está escrita en `scenarios/ge0b_bench.yaml` para que la lea quien vaya
a comprar algo.

### Los dos cambios que arrastraba la PR #15

**a) `ChannelSpec.scintillation_regime` pasa a obligatorio.** No se flipa el
defecto a saturado —seguiría costando seis de las ocho celdas de la Tabla 2 de la
P.1622— y no se deja invisible. Se **muda a las siete firmas de física**, donde
significa «la P.1622 tal como está impresa» (una afirmación bibliográfica,
estable) en vez de «el aire de este experimento» (una física, que depende del
experimento). La razón de la mudanza es el otro miembro de la unión: en un camino
horizontal la teoría débil deja de ser citable a **2413 m**, así que un defecto
correcto para la bajada sería el modelo equivocado en más de la mitad del barrido
que esta PR existe para hacer. La asimetría está asertada con el **recuento** de
firmas, para que una nueva sin defecto sea un test rojo. Anexo del ADR 0022.

**b) El hueco 21 sube de categoría, con la cifra hasta bits/día.** Se citaba con
«0.39 dB» y se leía como una discrepancia pequeña. No lo es, por dos razones que
solo se ven midiendo hasta el final.

*Primera: el 0.39 dB era la celda más favorable.* Es el régimen saturado a 10°
con el telescopio de 0.75 m; en régimen débil, que es el predeterminado de las
siete firmas, el mismo punto vale **1.69 dB**.

*Segunda, y es la que lo sube de categoría: el convenio fija el signo del cruce
de 27.02°.* Propagado a bits/día (día de referencia, un solo término cambiado):

| régimen | convenio P.1622 | convenio Ntanos | cambio | término de altitud (0 → 30 m) |
|---|---|---|---|---|
| `weak` | 433 442 | 419 162 | **−3.29 %** | +457 → **+1237 bits** |
| `moderate-to-strong` | 449 308 | 441 870 | **−1.66 %** | −206 → **+4 bits** |

**El término de altitud saturado cambia de signo con el convenio y aterriza
prácticamente en cero** (+4 bits de 449 308, 9e-6 del día). Es decir: los −206
bits que el anexo del ADR 0022 explica con un mecanismo correcto están **enteros
dentro de este hueco**, y la pregunta «¿suma o resta la altitud de la estación?»
no tiene respuesta hasta que alguien decida en qué espacio vive `A`. El cruce se
mueve de **27.02°** a **18.95°**, con el 67.7 % y el 56.1 % de los segundos del
día por debajo. El hueco **no se cierra** —elegir el otro convenio por el
resultado que da sería ajustar la física al número— pero se cierra la ignorancia
sobre cuánto cuesta.

### La figura

`viz.plots.plot_horizontal_key_against_distance`: clave contra distancia con el
intervalo plana-a-esférica como **banda**, la marca de `weak_theory_path_limit_m`
(2413 m) y la región de dentro del rango de Rayleigh sombreada con su propia
etiqueta —porque ahí la banda **se estrecha por la razón equivocada** y leerla
como «bien determinado» es la conclusión opuesta a la correcta—. La banda no es
una barra de error y el docstring lo dice: son dos modelos exactos acotando un
tercero que no está implementado. Y una distancia que no certifica nada **no se
pierde** en el eje logarítmico: se dibuja como un `×` con un «0» encima, que es
el punto más importante de la figura.

### Verificación

`uv run pytest`: **3 763 passed**, 0 fallos. `ruff check`, `ruff format --check`
y `mypy` limpios sobre 146 ficheros. Cobertura de líneas **y ramas al 100 %** en
todo `src/quoss` — 8 658 sentencias y 2 100 ramas, sin una sola sin cubrir —,
incluidos los cinco ficheros nuevos o muy tocados (`engine/horizontal.py`,
`scenario/result.py`, `scenario/models.py`, `engine/sweep.py`, `viz/plots.py`).

### Lo que queda para la PR D, dicho aquí para que no se pierda

`io/export.py` escribe un `SimulationResult` y **no sabe escribir un
`HorizontalResult`**. No es un descuido de esta PR: es el trabajo de la etapa 7,
donde `quoss run scenarios/ge1_1km.yaml --out out/` lo necesita. Hasta entonces
un resultado horizontal se serializa con `to_dict()` (no tiene arrays, así que el
JSON **es** su formato de archivo) y no con `export_result`.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/scenario/models.py` | `LinkKind`, `HorizontalPathSpec`, `SessionSpec`, `HorizontalScenario`, `AnyScenario`; `Scenario.link`; `scintillation_regime` obligatorio; `sky_radiance_w_m2_um_sr` admite 0.0 (un banco cerrado) |
| `src/quoss/scenario/io.py` | `TypeAdapter(AnyScenario)`, y el tag ausente con un mensaje que nombra los dos valores en vez de la queja interna de Pydantic |
| `src/quoss/scenario/hash.py` | canoniza por `physics_dict()`, que tienen los dos miembros |
| `src/quoss/scenario/result.py` | `HorizontalBudgetResults`, `HorizontalSessionResults`, `HorizontalResult`, `AnyResult` |
| `src/quoss/scenario/defaults.py` | `ge1_two_terminals()`, `ge0b_bench()` y sus constantes |
| `src/quoss/engine/horizontal.py` | nuevo: cinco llamadas y el `INFO` del bloque |
| `src/quoss/engine/pipeline.py` | `run()` despacha sobre el tag; la caché se declina en voz alta |
| `src/quoss/engine/sweep.py` | dos juegos de raíces de métrica que no se solapan |
| `src/quoss/channel/extinction.py` | `specific_attenuation_at_altitude_db_per_km` y el factor exponencial compartido |
| `src/quoss/viz/plots.py` | `plot_horizontal_key_against_distance` y `_vertical_mark` |
| `scenarios/ge1_1km.yaml`, `scenarios/ge0b_bench.yaml` | nuevos; los cinco de bajada ganan `link: downlink` |
| `tests/e2e/test_horizontal_scenario.py`, `tests/engine/test_horizontal.py` | nuevos |
| `tests/e2e/oracle.py` | `hand_horizontal`, la cadena a mano del horizontal |
| `tests/e2e/test_reference_scenarios.py` | `TestWhatTheApertureAveragingConventionCosts` (hueco 21) |
| `docs/adr/0024`, `docs/adr/0025` | nuevos |
| `docs/adr/0009`, `0021`, `0022` | huecos 20 y 21 medidos, la arquitectura decidida, el anexo del defecto |
| `notes/ROADMAP.md`, `README.md` | etapas 2.2, 4 y 5; siete escenarios; 23 ADRs |

---

## 41. Las notas dejan de caber en la sesión que las tiene que leer

**Fecha:** 2026-09-19. **Ningún `.py` de `src/` tocado.** ADR tocado:
[0004](../docs/adr/0004-zonal-perturbations.md) (dos celdas que le faltaban).

**La cifra que resume la entrada: el camino de lectura obligatorio pasa de
8 038 líneas a 1 623, y no se ha borrado nada.** `LAST_CHANGES.md` va de 6 834 a
1 170, `ROADMAP.md` de 935 a 321 y `GUIA_REIMPLEMENTACION.md` de 267 a 130; las
**6 382 líneas** que salen están en [`archive/`](archive/), íntegras y sin
editar.

Y la cifra que explica por qué se podía hacer sin perder nada: **de los 823
números distintos de §1 a §35, 765 —el 93.0 %— ya vivían en un ADR, en `src/` o
en `tests/`.**

### El problema, y no es que el fichero fuera largo

`CLAUDE.md` manda leer `LAST_CHANGES.md` al empezar cualquier sesión. Con 6 834
líneas eso no ocurre: se leen las primeras pantallas y se abandona. Y las
primeras pantallas eran **lo peor que podía leerse**, porque la cabecera había
crecido por apilamiento —cada entrada nueva empujaba a la anterior a un párrafo
«Entrada anterior:…» y ninguno se retiraba— hasta **352 líneas, el 5.2 % del
fichero**, que resumían §14 a §36. Es decir: lo primero que leía una sesión era
la tercera copia de cosas que ya estaban en su entrada y en su ADR, y lo que no
llegaba a leer eran §30–§40, que son las que describen el árbol de hoy.

**El coste no es hipotético y está fechado.** La PR C la escribió una sesión que
no había leído lo que la PR B dejó dicho. Dos días después, otra sesión abrió la
etapa 7 afirmando que la PR C no existía ([INCONSISTENCIAS #16](INCONSISTENCIAS.md)).
Son dos fallos distintos —uno de lectura, otro de sincronización— y los dos
terminan igual: trabajo hecho sobre un estado del proyecto que no era el real.

### La regla para archivar, que no es «lo viejo fuera»

Una entrada §N se archiva cuando **todo lo que carga peso en ella vive ya en
otro sitio que se lee de verdad**: un ADR, un test, o un docstring. Si no, se
migra primero y se archiva después.

**Por qué esa regla y no «archiva lo de hace más de un mes».** Una bitácora es
el único sitio del proyecto donde vive la *narración* de una decisión — qué se
creía antes, qué medición lo cambió. Un ADR guarda la conclusión; el ADR 0004
dice que los términos de segundo orden se quedan fuera, pero la entrada §5 es la
que cuenta que se intentaron y que empeoraban. Archivar por antigüedad borra del
camino de lectura cosas que todavía sostienen código. Archivar por cobertura no
puede: si algo sostiene código, o está junto al código o no se archiva.

**Y el ejemplo de lo que la regla evita.** §13 parecía la entrada más
archivable del fichero: se llama «Cosas a considerar», es de agosto, y no tiene
un módulo detrás. Tenía dentro una tabla **Pendiente de decidir** y una lista
**Deuda pequeña** que seguían **vivas** — `warn_unused_configs = true` sin
reactivar, `uv sync --all-extras` arrastrando `numba` en los tres jobs de CI,
el suelo `numpy>=1.26` sin testear, Vallado §9.6 sin transcribir,
Brouwer-Lyddane sin existir. Archivarla por antigüedad habría enterrado siete
tareas abiertas en un fichero que nadie abre.

### Cómo se clasificó, porque «lo revisé una a una» no es una medida

A ojo, treinta y cinco entradas de prosa técnica son una opinión. Así que la
clasificación se hizo con el árbol: extraer de cada entrada todo número con tres
cifras significativas o notación científica, normalizar los separadores de
millares, y buscarlo en `docs/adr/*.md`, `src/**/*.py` y `tests/**`.

| | §1–§35 | `ROADMAP.md` |
|---|---|---|
| Números distintos | **823** | **241** |
| Ya en un ADR, en `src/` o en un test | **765** (93.0 %) | **240** (99.6 %) |
| Sin dueño | **58** | **1** |

Los 58 se miraron uno a uno en su contexto, y se separan solos:

| Clase | Cuántos | Qué se hizo |
|---|---|---|
| Números de sección leídos como cifras (`18.2`, `20.1`, `21.5`…) | 21 | nada: falsos positivos del extractor |
| Recuentos históricos de la suite y de cobertura (2 237, 1 027, 1 131, 2 058, 3 487…) | 12 | se archivan: son el estado de un día, no una afirmación sobre física |
| Intermedios recalculados por un test que sí existe (las filas de las tablas de §18 y §21, los operandos de §4) | 21 | se archivan: el test los produce, no los transcribe |
| **Sin dueño y cargando peso** | **4** | **migrados, abajo** |

El único huérfano del `ROADMAP.md`, `0.7687` (el óptimo analítico de µ de la
Ec. (12) de Ma et al.), es del tercer tipo: `tests/qkd/test_bb84.py` **resuelve
la ecuación publicada** en vez de teclear su resultado, con una tolerancia
derivada del tamaño de los términos que esa ecuación desprecia.

### Lo que hubo que migrar antes de archivar

1. **§5 → [ADR 0004](../docs/adr/0004-zonal-perturbations.md).** El ADR decía
   que una fórmula de segundo orden candidata «mejoraba en unos casos y
   empeoraba en otros» **sin imprimir ningún caso**, que es una impresión y no
   una medida. Ahora lleva las dos celdas: a `i = 51.6°` mejora de 1.3e-3 a
   5.2e-4, y a **`i = 98°` empeora de 1.0e-4 a 1.4e-3**. Y lleva la frase que
   las dos celdas juntas permiten y ninguna por separado: **la inclinación que
   empeora catorce veces es la de este proyecto**, así que el caso favorable es
   el que no se usa.
2. **§13 → [`ROADMAP.md`](ROADMAP.md), sección «Trabajo abierto que no es una
   etapa».** Las filas ya tachadas no se copiaron; las vivas sí, y **se
   comprobaron una a una contra el árbol de hoy** en vez de copiarse de
   confianza. Es la columna «Comprobado» de esa tabla: `pyproject.toml:175`
   sigue en `false`, `ci.yml` tiene `--all-extras` en las líneas 40, 68 y 112.

### El ROADMAP, que era la segunda copia

935 líneas, y la mayor parte no era estado sino justificación: cada entrada
citaba su ADR **y a continuación volvía a explicar la decisión**. La medición de
arriba dice que el 99.6 % de sus números ya estaban en ese ADR o en un test, así
que la repetición no guardaba nada y sí creaba un documento que envejece por su
cuenta — como ya había pasado: su tabla de ADRs decía «hay dieciséis, del 0001
al 0016» con veintitrés en el árbol.

Queda en **321 líneas** de estado: una tabla por etapa, fichero → qué es → su
ADR, con `✅`/`🟨`/`⬜`.

### La guía de reimplementación, que era la tercera copia

`GUIA_REIMPLEMENTACION.md` (267 líneas, 2026-07-31) es el documento que propuso
reescribir SimulCTTC. **Esa reimplementación ya ocurrió**, así que sus §1
(estructura de directorios), §2 (tooling, rendimiento, calidad) y §5 (mejoras de
física y de flujo) describen decisiones hoy tomadas — y las describen **en
paralelo** a `ROADMAP.md`, a `CLAUDE.md` y a los ADRs. Ese es el caso concreto
de tercera fuente de verdad: tres ficheros afirmando lo mismo, de los cuales dos
se actualizan y el tercero no. Íntegro en
[`archive/GUIA_REIMPLEMENTACION-v3.md`](archive/GUIA_REIMPLEMENTACION-v3.md).

Queda en **130 líneas**, con lo único que no tenía otro dueño: el diagnóstico de
SimulCTTC —que es lo que **sostiene** la regla «SimulCTTC no es un oráculo», hoy
citada en tres sitios sin su defensa— y la escalera de lenguajes.

**Y ahí está el hallazgo que no se podía resolver en esta PR.** La escalera de
lenguajes (Python → Numba → Rust → C++, con «MATLAB no», «PyInstaller no» y
«WASM no») y los cuatro niveles de distribución **son decisiones con forma de
ADR y no tienen ADR**: son no obvias, siguen vigentes, gobiernan trabajo futuro
(`kernels/` de la 2.4, `deploy/` de la 11) y viven en un fichero de notas. No se
ha inventado un ADR para ellas, porque un ADR se numera al escribirse y eso es
una decisión de quien lo vaya a mantener, no un efecto secundario de reordenar
notas. Queda escrito al final del propio fichero.

### Lo que se miró y **no** hizo falta migrar, que también es un resultado

Tres cosas parecían huérfanas y no lo eran, y vale la pena que conste porque el
reflejo era migrarlas:

- **La errata de Vallado (§4).** Su exclusión —«ningún `|r|` ni `|n|` que la
  página imprima recupera `145.60549°»`— está en `tests/orbits/test_kepler.py`,
  que además **reproduce la aritmética de la página** en vez de solo registrar
  el desacuerdo. Lo que sigue sin asertarse es la inversa concreta (qué `|r|`
  haría falta: 11 472.24 km), y convertirlo en test es tocar un `.py`, que esta
  PR no hace.
- **El control de dos cuerpos (§13, «0.083 mm sobre 15 vueltas»).** Vive en
  `test_with_j2_off_both_paths_are_the_same_two_body_problem`, **con cota
  derivada** (1 mm, del `atol` de 1 nm del integrador sobre sus ~250 pasos por
  vuelta) y no elegida.
- **El `4 * eps` de `brentq` (§17).** Ya es `_BRENTQ_RTOL` con docstring en
  `constellations.py`; el literal `8.881784197001252e-16` es historia.

### Lo que no se pudo cumplir, con su aritmética

El objetivo era **por debajo de 900 líneas con las cinco últimas entradas
completas**. Las dos cosas no caben a la vez, y no por poco:

| | Líneas |
|---|---|
| §37 | 245 |
| §38 | 212 |
| §39 | 143 |
| §40 | 247 |
| **Las cuatro anteriores, solas y sin cabecera** | **847** |
| Cabecera nueva + índice de 36 filas | 66 |
| §41 (esta) | 257 |
| **Total** | **1 170** |

**Las cuatro entradas anteriores, solas y sin cabecera, ya son el 94 % del
presupuesto de 900.** Con la cabecera van 913, así que el objetivo se pasa
**antes de que exista una quinta entrada**. Y no es que falte poco: las 36
entradas archivadas suman 5 638 líneas, **157 de media**, y las cinco que se
quedan promedian **221**. «Cinco entradas completas» vale, por construcción,
entre 785 y 1 170 líneas — y el presupuesto de 900 tiene que cubrir además la
cabecera, un índice que crece una fila por entrada archivada, y la entrada que
documenta el cambio.

**Esa última es la parte que conviene mirar de frente: esta entrada son 257
líneas, la más larga de las cinco.** Documentar honestamente por qué el fichero
era ilegible cuesta más que la media de lo que archiva. No es una paradoja, es
la medida: **el presupuesto de 900 no está mal calculado, está calculado para un
fichero con menos entradas de las que se le piden**.

**Queda declarado como hueco y no ajustado.** No se ha recortado ninguna entrada
para que la cifra salga —empezando por esta—: una entrada recortada para caber
es exactamente la clase de documento que esta PR existe para no volver a
producir.

**Las tres opciones, medidas, para que la decisión sea del lector y no mía:**

| Qué se queda | Líneas | ¿Cumple 900? |
|---|---|---|
| §37–§41 (cinco, lo entregado) | **1 170** | no |
| §38–§41 (cuatro) | **925** | **no, por 25 líneas** |
| §39–§41 (tres) | **713** | sí |

Que cuatro entradas se queden a **25 líneas** del objetivo es la mejor
prueba de que 900 es el número de un fichero que ya no existe. Y las dos que
habría que archivar para cumplirlo son archivables **hoy** por la regla de esta
misma PR: §37 (régimen moderado-a-fuerte) está entero en el
[ADR 0022](../docs/adr/0022-the-strong-regime.md) y §38 (la extinción) en el
[ADR 0023](../docs/adr/0023-traceable-extinction.md). Es una línea de decisión,
no de trabajo.

### La regla se aserta, no se recuerda

`tests/unit/test_notes.py`, y la parte que importa es **qué** se aserta. Una
cota de líneas sola no sirve: cinco entradas largas pueden pesar más que seis
cortas, así que un número redondo no distingue «la regla se rompió» de «las
entradas de este mes son largas». Lo que se aserta es la regla:

1. `LAST_CHANGES.md` tiene **como mucho cinco** entradas `## N.`.
2. El índice cubre **todas** las archivadas, exactamente una vez, sin huecos ni
   duplicados en la numeración, y **cada enlace de archivo resuelve**.
3. Ninguna entrada aparece **a la vez** en el fichero y en el archivo.
4. La **cabecera más el índice** —que es lo que de verdad creció hasta 352
   líneas— se queda bajo `60 + 2 × (entradas archivadas)`. Hoy: **66 contra
   132**.
5. **Ninguna entrada pasa de 320 líneas.** La más larga que ha escrito el
   proyecto en 41 entradas es §29, con **307**; 320 es esa con un 4 % de
   holgura, así que pasa para todo lo que existe y salta para cualquier cosa
   más larga que todas ellas.

**Y no hay una cota del total, a propósito.** Se intentó, con 1 100, y fue esta
misma entrada la que la rompió — lo cual es la demostración del problema y no un
accidente: un total no distingue «la regla se rompió» de «las entradas de este
mes son largas». Cualquier número es inalcanzable (900) o incapaz de fallar
(1 732), y una cota que no puede fallar no prueba nada, que es la regla de
tolerancias de `CLAUDE.md`. Acotar la cabecera y cada entrada por separado acota
el total **por construcción**, en `132 + 5 × 320 = 1 732`, y ese número es una
consecuencia en vez de una elección.

### Verificación

`uv run pytest`: **3 773 passed**, 0 fallos (3 763 antes, más los 10 de
`tests/unit/test_notes.py`). `ruff check`, `ruff format --check` y `mypy`
limpios.

**Ninguna entrada perdida, y se comprueba sola:** las 41 entradas siguen siendo
1…41 sin huecos ni duplicados, repartidas entre el fichero (§37–§41) y el
archivo (§1–§36), y ninguna está en los dos sitios. Eso es lo que asertan los
tests 2, 3 y 4 — y es mejor garantía que contar líneas, porque una línea perdida
al reformatear no es lo mismo que una entrada perdida.

### Ficheros

| Fichero | Qué |
|---|---|
| `notes/LAST_CHANGES.md` | 6 834 → **1 170** líneas: cabecera nueva, índice de §1–§36, y §37–§41 completas |
| `notes/archive/LAST_CHANGES-{01-12,13-24,25-36}.md` | nuevos; 6 098 líneas, las entradas íntegras, más la cabecera acumulativa de 352 líneas como apéndice |
| `notes/ROADMAP.md` | 935 → 321 líneas: estado, no justificación. Sección «Trabajo abierto» heredada de §13 |
| `notes/GUIA_REIMPLEMENTACION.md` | 267 → 130 líneas; el resto a `archive/GUIA_REIMPLEMENTACION-v3.md` |
| `notes/INCONSISTENCIAS.md` | entrada 16 (la verificación contra un árbol rancio) |
| `docs/adr/0004-zonal-perturbations.md` | las dos celdas de §5 |
| `tests/unit/test_notes.py` | nuevo; 10 tests sobre las reglas de arriba |
| `CLAUDE.md`, `README.md` | norma 0 (sincronizar) y el orden de lectura de una sesión, con líneas y con «¿siempre?» |

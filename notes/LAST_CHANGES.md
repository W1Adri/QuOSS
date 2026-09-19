# QuOSS — Últimos cambios

> **Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).**
> Última entrada: **§42, 2026-09-19** — las tres decisiones que §41 dejó abiertas.
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

## Índice de lo archivado (§1–§38)

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

### El objetivo de 900 líneas — **retirado en §42**

Esta entrada se escribió con un objetivo declarado: **por debajo de 900 líneas
con las cinco últimas entradas completas**. Midió que las dos cosas no caben a
la vez —las cuatro entradas anteriores, solas y sin cabecera, ya eran 847
líneas, el 94 % del presupuesto— y dejó la decisión abierta con tres opciones.

**Ya no está abierta, y el objetivo no sobrevive.** §42 lo retira: 900 era un
número elegido a mano, y lo que lo sustituye es la cota estructural que esta
misma entrada dejó asertada —cabecera acotada, entrada acotada, cinco entradas—
que acota el total **por construcción** sin que nadie tenga que elegir una cifra.
La aritmética completa —la tabla de las cinco entradas y la de las tres
opciones— está en el historial de git de este fichero, en el commit de §41, y
su conclusión operativa está en §42.

**Lo que sí se conserva de aquella medición**, porque es lo que sostiene la cota
de hoy: un total de líneas no distingue «la regla se rompió» de «las entradas de
este mes son largas», así que cualquier total es inalcanzable o incapaz de
fallar. Eso está escrito donde se comprueba, en el docstring de
`tests/unit/test_notes.py`.

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

---

## 42. Las tres decisiones que la ronda anterior dejó abiertas

**Fecha:** 2026-09-19. **ADRs nuevos:**
[0026](../docs/adr/0026-the-language-ladder.md) (la escalera de lenguajes) y
[0027](../docs/adr/0027-four-levels-of-distribution.md) (los cuatro niveles de
distribución). **Ningún `.py` tocado.**

**La cifra que resume la entrada: el camino de lectura obligatorio baja de 1 623
a 1 288 líneas, y las dos decisiones que llevaban cincuenta días sin dueño ya lo
tienen.** §41 dejó tres cosas escritas y sin cerrar; esta entrada las cierra las
tres, que es todo lo que hace.

### 1. §37 y §38 se archivan, y se volvió a medir en vez de darlo por bueno

§41 midió que las dos son archivables **hoy** —§37 está entero en el
[ADR 0022](../docs/adr/0022-the-strong-regime.md) y §38 en el
[ADR 0023](../docs/adr/0023-traceable-extinction.md)— y dejó la decisión al
lector. Tomada.

**Y la medición se rehízo**, con el mismo extractor de §41, porque «§41 ya lo
dijo» es exactamente la clase de afirmación heredada que este proyecto pide
comprobar:

| | Números distintos | Con dueño en un ADR, en `src/` o en un test | Huérfanos |
|---|---|---|---|
| §37 | 103 | **100** (97.1 %) | 3 |
| §38 | 77 | **76** (98.7 %) | 1 |

Los cuatro huérfanos son de la clase que §41 ya había clasificado como
archivable sin migrar: **tres recuentos de la suite** (3 478, 3 541 y 3 640
`passed`) y **un identificador de run de CI** (34988518923). Son el estado de un
día. El recuento de hoy lo imprime `uv run pytest`, que es un sitio que no
envejece, y por eso no hace falta migrarlos a ninguna parte.

Van a [`archive/LAST_CHANGES-37-38.md`](archive/LAST_CHANGES-37-38.md), íntegras
y sin editar, con sus dos filas en el índice.

### 2. El objetivo de 900 líneas queda retirado, no aplazado

§41 se escribió contra un objetivo de **menos de 900 líneas con las cinco
últimas entradas completas**, midió que las dos cosas no caben —las cuatro
entradas anteriores, solas y sin cabecera, ya eran 847— y lo dejó declarado como
hueco.

**Retirado.** No porque sea difícil de cumplir, sino porque **es un número
elegido a mano**, y este proyecto ya tiene escrita la regla que lo descalifica:
una cota elegida para que salga el resultado de hoy no puede fallar nunca, así
que no prueba nada. Lo que lo sustituye no es otro número: es la **cota
estructural** que la propia §41 dejó asertada en `tests/unit/test_notes.py`
—como mucho cinco entradas, cabecera bajo `60 + 2 × archivadas`, ninguna entrada
sobre 320 líneas—, que acota el total **por construcción** en
`132 + 5 × 320 = 1 732` sin que nadie elija la cifra.

Borrado de donde estaba escrito, que era el único sitio: la sección de §41 que
lo declaraba abierto. La aritmética sigue en el historial de git; lo que no
sigue es un objetivo que alguien pudiera perseguir. `tests/unit/test_notes.py`
ya lo citaba **como ejemplo de cota inalcanzable**, que es el uso correcto y el
único que se queda.

### 3. Las dos decisiones sin ADR: 0026 y 0027

Es el hallazgo con el que §41 terminó, y no lo pudo cerrar por una razón que
sigue siendo buena: un ADR se numera al escribirse, y eso es una decisión de
quien lo vaya a mantener, no un efecto secundario de reordenar notas.

**Un ADR registra una decisión, no una implementación.** Que `kernels/` y
`deploy/` no existan no es objeción: las dos decisiones están **tomadas desde el
2026-07-31** y han gobernado el proyecto desde entonces desde un fichero de
notas, que no es donde se buscan las decisiones.

Y los dos traen la medición que el texto original no tenía, porque un ADR de
este proyecto trae sus cifras:

**[ADR 0026 — la escalera de lenguajes](../docs/adr/0026-the-language-ladder.md).**
Python → Numba → Rust → C++, con las tres condiciones de entrada (perfil que
nombre la función, contrato numérico estable, referencia NumPy con golden test).
Lo que se midió aquí para escribirlo:

| Qué | Medida |
|---|---|
| El día de referencia completo | **121 ms**, del que `orbit` son 52.4 (43 %) |
| `ZONAL_NUMERIC`, 1 satélite, un día a 1 s (86 401 muestras) | 0.934 s |
| `ZONAL_NUMERIC`, 10 satélites | 9.306 s (931 ms/sat) |
| `ZONAL_NUMERIC`, 60 satélites | **55.6 s** (927 ms/sat) |
| `TWO_BODY`, 60 satélites | **2.9 s** (48 ms/sat) |

**El hallazgo, que cambia a qué etapa pertenece el trabajo.** Las tres filas de
`ZONAL_NUMERIC` dan la misma cifra por satélite con menos del 1 % de dispersión
entre S = 1 y S = 60: eso es la firma de un bucle estrictamente en serie, y está
a la vista en `propagator.py:535`. **El factor 19 contra `TWO_BODY` no mide la
velocidad de la aritmética, mide que una rama recorre los satélites de uno en
uno y la otra no.** La lectura ingenua de «55 segundos» es «hace falta Numba»;
la correcta es que el escalón 1 —vectorizar y paralelizar— no está agotado, y
que lo que falta es de `engine/parallel.py`, etapa 11. Numba aquí aceleraría la
evaluación del campo dentro de cada paso de DOP853 y dejaría intacto el 100 %
del serialismo.

**[ADR 0027 — los cuatro niveles de distribución](../docs/adr/0027-four-levels-of-distribution.md).**
CLI → `serve` en `localhost` → imagen Docker offline → servicio cloud opcional,
con la web como **cliente** y no como el simulador. La decisión no es la tabla:
es que el nivel 0 va primero y que los otros tres son clientes suyos, que es lo
que hace verificable la frase «el frontend no calcula física». Lo medido:

| Artefacto | Tamaño |
|---|---|
| `quoss-0.1.0-py3-none-any.whl` | **644 KB**, 85 ficheros |
| `numpy` + `scipy` instalados | 33 + 91 = **124 MB** |
| `pyarrow` (extra `export`) | **152 MB** |
| `numba` + `llvmlite` (extra `accel`) | 17 + 172 = **189 MB** |
| `.venv` de desarrollo completo | **742 MB** |

**El código de QuOSS es el 0.09 % de su propio entorno**, y esa asimetría es lo
que descarta el binario descargable: empaquetar el stack numérico mueve 124 MB
como suelo para acompañar 644 KB de física, uno por sistema operativo y sin ser
scriptable. De paso corrige una cifra del propio `pyproject.toml:48`, que llama
a `pyarrow` «40 MB»: son **152**, casi cuatro veces más — y el comentario tenía
razón en la conclusión, que es por lo que `pyarrow` es un extra.

**Y los 85 ficheros del wheel son el defecto que esto destapa:** son
`quoss/**/*.py` y nada más. `data/ogs.yaml` y `data/snapshots/` **no viajan**, y
se resuelven relativos al checkout, así que un `quoss run` desde una instalación
no encontraría ni las estaciones ni los snapshots. Queda escrito en el ADR 0027
y abierto en [`INCONSISTENCIAS.md`](INCONSISTENCIAS.md) #18, porque cerrarlo es
tocar el empaquetado y esta entrada no toca `.py`.

### La guía deja de ser la tercera fuente de verdad

`GUIA_REIMPLEMENTACION.md` pierde sus apartados 2 y 3 —que son justamente los
dos ADRs— y queda en **86 líneas** con lo único que sigue sin otro dueño: el
diagnóstico de SimulCTTC, que es lo que sostiene «SimulCTTC no es un oráculo»
(citada en el README, en `ROADMAP.md` y en `tests/golden/README.md`, los tres sin
su defensa) y el «la web es un cliente» del ADR 0027.

**No están en los dos sitios**, que es el punto entero: una justificación
duplicada es una que se queda quieta en una de las dos copias.

### Lo que no se pudo cerrar, con su medida

**Once de las catorce citas a `GUIA_REIMPLEMENTACION.md` apuntan a secciones que
ese fichero no tiene.** El recorte de §41 renumeró el documento (el v3 tenía
§0–§5; el recortado tenía §1–§3) sin tocar quién lo citaba, así que
`src/quoss/viz/style.py` cita un §4 que ya no existe, tres ficheros citan un
§2.2 que tampoco, y cinco citan un §5. Peor que no resolver: **`viz/__init__.py`
cita un §1 que sí existe y ahora dice otra cosa** —«qué era SimulCTTC» donde el
v3 tenía la estructura de directorios—, que es una cita que resuelve al sitio
equivocado en silencio. Va a [`INCONSISTENCIAS.md`](INCONSISTENCIAS.md) #17 con
el recuento; se cierra en la PR que toque `.py`.

### Verificación

`uv run pytest`: **3 773 passed**, 0 fallos — los mismos que §41, porque esta
entrada no toca `.py`. `tests/unit/test_notes.py` es el que importa aquí: 10
passed sobre el fichero recortado, incluido el índice, que ahora cubre §1–§38
sin huecos ni duplicados. `ruff check`, `ruff format --check` y `mypy`: limpios.

**El camino de lectura obligatorio**, que es la cifra que §41 introdujo:

| Fichero | §41 | Hoy |
|---|---|---|
| `LAST_CHANGES.md` | 1 170 | **867** |
| `ROADMAP.md` | 321 | 335 |
| `GUIA_REIMPLEMENTACION.md` | 130 | **86** |
| **Total** | **1 623** | **1 288** |

**Y conviene leer el 864 con cuidado, porque no es lo que parece.** Archivar §37
y §38 quitó 455 líneas y dejó el fichero en 683; esta entrada añade 184. El
balance neto es −303, no −487, y el que sube es el `ROADMAP.md`: catorce líneas,
por las dos filas nuevas de su tabla de ADRs y los dos enlaces desde las etapas
2.4 y 9–11. Es estado nuevo, no justificación repetida — que es el criterio, y
no el signo del número.

### Ficheros

| Fichero | Qué |
|---|---|
| `docs/adr/0026-the-language-ladder.md` | nuevo. La escalera, sus tres condiciones de entrada, y el perfil que dice que hoy no toca |
| `docs/adr/0027-four-levels-of-distribution.md` | nuevo. Los cuatro niveles, y los dos defectos del nivel 0 que medirlos destapó |
| `notes/archive/LAST_CHANGES-37-38.md` | nuevo; §37 y §38 íntegras, con la medición que las autoriza a estar ahí |
| `notes/LAST_CHANGES.md` | 1 170 → 683; índice a §38, el objetivo de 900 retirado |
| `notes/GUIA_REIMPLEMENTACION.md` | 130 → 86; los apartados 2 y 3 se fueron con sus ADRs |
| `notes/ROADMAP.md` | tabla de ADRs a veinticinco, y las etapas 2.4 y 9–11 enlazan el suyo |
| `notes/INCONSISTENCIAS.md` | #17 (las citas a secciones que no existen) y #18 (`data/` fuera del wheel) |
| `README.md` | 23 → 25 ADRs |

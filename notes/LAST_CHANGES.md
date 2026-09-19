# QuOSS — Últimos cambios

> **Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).**
> Última entrada: **§44, 2026-09-19** — la fila que faltaba, y la tabla de
> validación commiteada.
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

## Índice de lo archivado (§1–§39)

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

---

## 43. La CLI existe, y un resultado horizontal tiene forma de directorio propia

**Fecha:** 2026-09-19. **ADRs nuevos:**
[0017](../docs/adr/0017-publication-figures.md) (las figuras de publicación, el
número reservado desde el 2026-09-14),
[0018](../docs/adr/0018-validation-is-a-table-not-a-badge.md) («validado» es una
tabla que se recalcula, el otro reservado) y
[0028](../docs/adr/0028-the-cli-computes-nothing.md) (la CLI no calcula nada, y
las dos formas de directorio). **ADRs tocados:** 0003 (la errata de Vallado sube
del comentario de un test), 0026 (por qué el bucle sobre satélites no se puede
vectorizar), 0027 (dos cifras que esta PR mueve y un defecto que cierra), 0001,
0011 y 0015 (citas).

**La cifra que resume la entrada: un `quoss` instalado en un `.venv` limpio
fuera del checkout corre los tres escenarios probados y sale 0 — el mismo
comando que `[project.scripts]` promete desde la etapa 0 y que llevaba desde
entonces reventando con `ModuleNotFoundError`, sin que ningún test pudiera
verlo, porque un `import` no ve un entry point.**

### 1. La CLI, y la única regla que la forma

`cli/` son cinco ficheros: `main.py` (el parser y el estado de salida),
`run.py`, `sweep.py`, `validate.py` y `report.py` (lo que los tres comparten).
La regla, del [ADR 0028](../docs/adr/0028-the-cli-computes-nothing.md), es que
**la CLI no calcula nada**: no decide qué geometría corre —lo decide el campo
`link` del fichero, y `engine.pipeline.run` despacha sobre él—, no decide qué
ficheros escribe el export —lo decide la forma del resultado—, no evalúa una
métrica y no renderiza la tabla de validación.

**Y se aserta como el [ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md)
aserta lo mismo del motor, una capa más arriba:** el `result.json` que
`quoss run` escribe reconstruye un resultado **igual término a término** al que
devuelve `run()` llamado a mano sobre el mismo fichero, para las dos geometrías.
Se excluyen dos campos y se nombran —`provenance.created_utc` y `timings`, que
son lecturas de reloj de pared—; entra todo lo demás, incluidos el hash, el
escenario entero y la lista de avisos. Y se comprueba además que reconstruye
**la clase correcta**: la igualdad de `to_dict()` pasaría para dos contenedores
distintos con los mismos números, y el punto entero de los dos contenedores del
ADR 0024 es que una ejecución horizontal no vuelva como una de bajada con
agujeros.

El spec de `quoss sweep` es un **fichero**, no una cadena en línea, por la misma
razón por la que el escenario es un fichero: una figura tiene que ser
reproducible desde algo commiteado, y un historial de shell no está versionado
ni se hashea. El primero es `scenarios/sweeps/ge1_distance.yaml`, y reproduce
por el camino de la CLI el hallazgo de §40:

| distancia | bits certificados | bits asintóticos |
|---|---|---|
| 200 m | 23 696 707 | 53 289 110 |
| 1 km | 15 236 099 | 35 461 378 |
| 2410 m | 2 098 831 | 6 470 247 |
| **5 km** | **0** | **267 678** |

La última fila es por lo que el spec pide las dos métricas: a 5 km un
dimensionado asintótico diría que hay un enlace de 4.46 kbit/s.

### 2. El export horizontal: dos formas de directorio, no un método de compatibilidad

Esto es la [inconsistencia #15](INCONSISTENCIAS.md), abierta desde §40 y dejada
explícitamente para esta etapa. `export_result` estaba tipado sobre un protocolo
que pide `to_manifest_and_arrays`, y un `HorizontalResult` no lo tiene:
`AttributeError` en la primera línea.

**La opción corta era darle el método devolviendo un diccionario de arrays
vacío. Es la que hay que rechazar, y la razón está medida en §40 una capa más
abajo.** Un `HorizontalResult` que satisficiera `ExportableResult` exportaría
por el camino de bajada, no encontraría `passes` ni `daily` en su manifiesto,
registraría dos `INFO` de «tabla ausente» y escribiría un `arrays.npz` **sin
nada dentro** — un directorio que se parece al de un enlace de bajada que no
certificó nada. Es el mismo fallo que los arrays de longitud cero que el ADR
0024 rechazó (`daily.finite_bits.sum()` sobre un eje vacío es `0.0`, y **un
enlace que certificó 15.2 Mbit se reportaría como cero bits al día**), con un
fichero en vez de un array.

Lo que se hace: **dos formas, nombradas en `manifest.json` bajo `export.shape`**.

| | `downlink` | `horizontal` |
|---|---|---|
| tablas | `passes.csv`, `daily.csv`, `series_<estación>.csv` | `budget.csv`, `session.csv`, una fila cada uno |
| arrays | `arrays.npz` | **ninguno**; pedir `npz` registra `io.export-no-arrays` y no escribe nada |
| envoltorio | `manifest.json`, `README.txt`, `result.json` | igual |

**Las dos formas no comparten ni un nombre de fichero de datos** —solo el
envoltorio—, y hay test de la disyunción: es la propiedad que hace que la
ausencia de `passes.csv` sea inequívoca en vez de una lectura que el consumidor
tenga que adivinar entre «el export falló», «no se pidió CSV» y «este enlace no
tiene pases».

**El despacho es por qué método ofrece el resultado**, `ExportableResult` contra
`ScalarBlockResult`, y no por un `isinstance` sobre la clase: `io/` no importa
nada de `scenario/` hoy y el protocolo existe para que siga siendo así. Los dos
protocolos **no comparten ni un método**, y eso es una aserción y no una
costumbre: mientras sean disjuntos el type checker rechaza el camino equivocado
antes de que se pueda tomar; el día que uno gane un método que el otro también
tenga, `isinstance` deja de estrechar.

Un bloque es **una fila** y no una columna de términos, para que N exports se
concatenen en una tabla de N filas — que es lo que un barrido sobre distancia es
en disco. Y hay test de que el directorio escrito **reconstruye el resultado
real**, campo a campo, más el de que cada SHA-256 del manifiesto coincide con
los bytes del fichero.

### 3. `expected_degradations`, y por qué está fuera del hash

`quoss run` sale distinto de cero cuando aparece un `DEGRADED` que el escenario
no declaró. Hacía falta un sitio donde declararlo, y es un campo nuevo en los dos
miembros de la unión, con valor por defecto vacío.

**Está excluido del digest**, con `name` y `description`, y no por la misma
razón que ellos: no es una etiqueta, es una afirmación sobre **qué tolera el
lector**. El mismo escenario produce exactamente los mismos números esté o no
listado un código, así que dos ficheros que difieren solo ahí tienen que
compartir entrada de caché — **aceptar un aviso no puede reejecutar un día de
Monte Carlo**. Hay test del digest y hay test de que los dos escenarios producen
el mismo presupuesto, la misma sesión y la misma lista de avisos, difiriendo solo
en el estado de salida. El digest fijado de `reference_castelldefels` sigue
siendo `17f44003…`, que es la comprobación de que el contrato no se movió.

### 4. Los avisos se imprimen enteros, y el caso que lo exige

Cada entrada con sus cinco campos —`severity`, `code`, `where`, `message`,
`details`—, en `stderr`, sin resumir y sin sustituirse por un recuento. El caso
que lo exige es el horizontal: ahí viven
`horizontal.block-is-the-declared-session` y `horizontal.session-without-key`,
que **lleva la cifra asintótica al lado del cero certificado**. Un lector que ve
«2 avisos» tiene el recuento y no el hallazgo.

Se imprime el **log completo** y no `result.warnings`, y los dos difieren:
exactamente en lo que registró el *export*, que el resultado no puede llevar
porque ya estaba construido. `io.export-no-arrays` es una de ellas, y es la
línea que explica por qué un directorio horizontal no tiene `arrays.npz`.

### 5. El entry point, y por qué su test es un subproceso

`[project.scripts]` declara `quoss = "quoss.cli.main:main"` desde el primer
commit del proyecto. El instalador **no comprueba que el objetivo exista**, así
que escribía el script igualmente: `.venv/bin/quoss`, 343 bytes, muerto en su
primera línea efectiva.

**Nada podía cazarlo.** Un test que importara `quoss.cli.main` sería un import y
no ve una cadena de entry point equivocada, ni un `__init__.py` que falta, ni un
atributo que no es invocable, ni un script que el instalador nunca escribió. El
test ejecuta el fichero instalado **como subproceso**, y hay una segunda guarda
por el otro lado que lee `[project.scripts]` del `pyproject.toml` y comprueba que
el módulo y el atributo existen; las dos fallan con mensajes distintos.

Medido después, instalando el wheel en un `.venv` limpio fuera del checkout:
`quoss --version` responde, y `quoss run` corre los tres escenarios probados
—horizontal, bajada y TLE—, sale 0 y escribe su directorio. El wheel pasa de
**85 a 90 entradas** y de 644 a **648 KB**: seis `quoss/cli/*.py` nuevos menos el
`quoss/cli/.gitkeep` que ya no hace falta.

### 6. Las catorce citas a la guía, y el test que las mantiene

[Inconsistencia #17](INCONSISTENCIAS.md), abierta en §42 y cerrada aquí porque
esta PR sí toca `.py`. Once citas apuntaban a un apartado que el fichero
recortado ya no tiene; una —`viz/__init__.py`— **resolvía en silencio al
apartado equivocado**, que es la peor: cita «§1» para «una fórmula, un sitio» y
el §1 de hoy es «qué era SimulCTTC».

Diez pasan a `notes/archive/GUIA_REIMPLEMENTACION-v3.md`, donde la numeración
vieja está congelada, y cuatro al dueño de hoy: el ADR 0026 (MATLAB y sus
figuras), el ADR 0027 (la web es un cliente), el `ROADMAP.md` (la escalera de
dependencias) y `CLAUDE.md` — esta última porque
`tests/e2e/test_reference_scenarios.py` atribuía a la guía la regla de
«una tolerancia que no puede fallar», **y la guía nunca la tuvo**.

**Y se aserta**, que es lo que impide que el próximo recorte las vuelva a
romper: `test_every_guide_section_cited_from_the_code_exists` recorre `src/`,
`tests/`, `docs/`, `pyproject.toml`, `CLAUDE.md` y `README.md`, extrae cada cita
con número de apartado, y falla cuando el fichero citado no tiene ese apartado.
Comprobado que falla: devolviendo una sola cita a su forma rota, el mensaje dice
qué fichero, qué línea, qué apartado y cuáles existen.

`notes/` queda fuera del recorrido a propósito: es donde la renumeración se
*describe* —«el v3 tenía §0–§5»— y prosa sobre qué apartados existían no es una
cita de ellos.

### 7. La errata de Vallado sube al ADR que posee la comparación, con una capa más

La errata de la p. 116 vivía como comentario de treinta líneas dentro de
`tests/orbits/test_kepler.py`. Es una **exclusión del conjunto V2** —un número
publicado que este proyecto declara no utilizable— y una exclusión guardada en
un comentario de test se pierde en el primer refactor del test, mientras el
número sigue impreso en el libro. Sube al
[ADR 0003](../docs/adr/0003-orbital-elements.md) y el test **la cita**.

Y se le añade la capa que faltaba, que es la que convierte «está mal» en «no es
utilizable». Las dos primeras dicen que `|r|` lleva una transposición (11456.67
por 11456.57) y que con los operandos de la página la fórmula de la página da
145.7193795° y no 145.60549°. Queda abierta la lectura de que el ángulo impreso
venga de otro `|r|` que la página redondeó. **No viene de ninguno:** despejando
`|r|` de la propia expresión para que devuelva el número impreso salen
**11 472.237 km**, que no aparece en ningún sitio de la página y está a
**15.57 km** del `|r|` que la página imprime y a **15.67 km** del correcto — un
0.136 %, contra el 8.7e-4 % que vale la transposición. Dos órdenes de magnitud no
son un redondeo. `test_no_printed_radius_recovers_the_printed_angle`.

### 8. La etapa 2.4 se reclasifica: no la justifica ninguna medida de hoy

Del [ADR 0026](../docs/adr/0026-the-language-ladder.md) salía que 60 satélites un
día a 1 s tardan 55.6 s. La cifra es correcta y estaba **atribuida al mecanismo
equivocado**: 927 ms/satélite con S = 60 y 934 con S = 1 —menos del 1 % de
dispersión— son la firma de un bucle en serie (`propagator.py:535`), no de
aritmética lenta. El roadmap lo dice ahora así, y marca la 2.4 como **no
justificada por esa medida**: para justificarla haría falta volver a medir
**después** de arreglar el bucle.

**Y el remedio no es vectorizar, es paralelizar**, que en este proyecto no es una
distinción de vocabulario. Vectorizar es hacer que una sola operación de NumPy
recorra los S satélites a la vez, y **no se puede aquí**: DOP853 es de paso
adaptativo y cada satélite produce su propia secuencia de pasos —el que pasa por
perigeo más rápido necesita pasos más cortos justo ahí—, así que vectorizar
entre satélites exige renunciar al paso adaptativo por satélite, que es lo que
hace fiable al integrador cerca de perigeo. Lo que admite es repartir las
llamadas entre procesos: escala con núcleos y no con anchura SIMD, y tiene coste
de arranque y de serialización. Es la diferencia entre un escalón 1 agotable con
un refactor barato y uno que no. Está en el ADR 0026 y en el `ROADMAP.md`.

El factor 19 contra `TWO_BODY`, de paso, compara un problema con forma vectorial
con otro que no la tiene: `TWO_BODY` no integra nada, resuelve la ecuación de
Kepler sobre la misma rejilla de tiempos para todos.

### Verificación

`uv run pytest`: **3 853 passed**, 0 fallos (3 773 antes). `ruff check`,
`ruff format --check` y `mypy` limpios sobre 160 ficheros — `quoss.cli.*` entra
en la lista de módulos estrictos de `mypy`, con los mismos flags que la física.
Cobertura de líneas **y ramas al 100 %** en todo `src/quoss` — 8 908
sentencias y 2 146 ramas, sin una sola sin cubrir —, incluidos los seis
ficheros de `cli/` (211 sentencias, 34 ramas).

Fuera de la suite, porque no se puede asertar desde el árbol: wheel construido
con `uv build`, instalado en un `.venv` limpio, y `quoss run` ejecutado sobre los
tres escenarios desde `/tmp`.

**El camino de lectura obligatorio sube**, que es la cifra que §41 introdujo y
§42 siguió: de 1 288 a **1 578 líneas** (`LAST_CHANGES.md` 867 → 1 141,
`ROADMAP.md` 335 → 351, `GUIA_REIMPLEMENTACION.md` 86). Las 268 líneas de esta
entrada son lo que cuesta una PR que toca treinta ficheros, y la cota que decide
si eso está bien no es el total sino la estructural de
`tests/unit/test_notes.py` —cinco entradas como mucho, ninguna sobre 320 líneas,
cabecera bajo `60 + 2 × archivadas`—, que se cumple con margen. El total volverá
a bajar cuando §39 se archive, y eso toca cuando llegue §44, no ahora.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/cli/{__init__,main,run,sweep,validate,report}.py` | nuevos. El paquete entero |
| `src/quoss/io/export.py` | `ScalarBlockResult`, `AnyExportable`, `SHAPES`, `ExportManifest.shape`, `_tables_from_blocks`, `io.export-no-arrays` |
| `src/quoss/scenario/result.py` | `HorizontalResult.to_manifest_and_blocks` |
| `src/quoss/scenario/models.py` | `expected_degradations` en los dos miembros; `HASH_EXCLUDED_FIELDS` se muda aquí y gana su tercera entrada |
| `src/quoss/scenario/hash.py` | re-exporta la constante y explica la tercera exclusión |
| `scenarios/sweeps/ge1_distance.yaml` | nuevo. El primer spec de barrido versionado |
| `pyproject.toml` | `quoss.cli.*` en los estrictos de mypy; la cita a la guía, al archivo |
| `docs/adr/0017`, `0018`, `0028` | nuevos. Los dos reservados y el de esta etapa |
| `docs/adr/0003` | la errata de la p. 116, con su tercera capa medida |
| `docs/adr/0026` | «El bucle no se puede vectorizar; lo que admite es paralelizar» |
| `docs/adr/0027` | el defecto 1 cerrado, el wheel remedido, el 2 ahora alcanzable y medido |
| `docs/adr/0001`, `0011`, `0015` | citas a la guía, al archivo o al dueño de hoy |
| `src/quoss/{engine,io,viz,scenario}/*.py`, `CLAUDE.md` | las once citas restantes |
| `tests/cli/` | nuevo: `conftest.py` y cuatro ficheros de test |
| `tests/io/test_export.py` | la forma horizontal: protocolos disjuntos, directorio, bloques, reconstrucción |
| `tests/unit/test_notes.py` | el test de las citas |
| `tests/orbits/test_kepler.py` | el comentario baja a una cita; la tercera capa de la errata |
| `tests/scenario/test_hash.py` | la lista de exclusión son tres, y aceptar un aviso no mueve el digest |
| `notes/ROADMAP.md`, `README.md`, `notes/INCONSISTENCIAS.md` | etapa 7 cerrada, 2.4 reclasificada, 28 ADRs, #15 y #17 cerradas, #18 remedida |

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

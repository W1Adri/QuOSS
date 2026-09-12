# QuOSS — Últimos cambios y cosas a considerar

> Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).
> Última actualización: **2026-09-12** — **tercer módulo de la Etapa 2.3**,
> `qkd/finite_key.py` (§25): la cota finite-key componible, y con ella el
> [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md) que la etapa tenía
> aplazado. **La fuente no es la que el roadmap pedía:** decía «Tomamichel» y lo
> implementado es **Lim et al. 2014**, porque el protocolo que hay es decoy con
> pulsos coherentes débiles y el de Tomamichel et al. supone fuente de un fotón —
> y no es apartarse de ellos, es usar el resultado que aplica su relación de
> incertidumbre entrópica al protocolo que tenemos.
>
> **Lo que entra y sale es de otra especie:** entra un **bloque** de cuentas
> acumuladas, sale una **longitud en bits** con dos probabilidades de fallo al
> lado. No es la tasa asintótica por un factor, y tres cosas lo impiden: hay un
> coste fijo de **260 bits por bloque** que no escala con nada; la desviación de
> Hoeffding la comparten las tres intensidades, así que la que se envía 1/21 de
> las veces carga una incertidumbre relativa 21 veces mayor; y el protocolo de
> Lim et al. —base sesgada, clave de las tres intensidades, error estimado en la
> otra base— **no es** el de `bb84.py`.
>
> **La cifra que resume la etapa:** en el enlace de referencia a cenit con el
> reparto 16:1:4, un bloque de 1e10 pulsos —cien segundos de una fuente de
> 100 MHz— certifica **1.1387e-05 bits por pulso** contra los **6.0239e-05** del
> límite asintótico del mismo protocolo. El **18.9 %**. Y a 1e9 pulsos, nada.
>
> **El hallazgo que solo este módulo puede ver:** asintóticamente los pulsos
> decoy son coste puro y su fracción óptima es cero —lo dice el docstring de
> `protocol_efficiency`, y es cierto—; con un bloque de pase el óptimo está
> **cerca del 50 %** y vale un factor **3.4** sobre gastar una décima parte.
>
> **Verificación:** V3 **entre fuentes** —con `mu_3 = 0` y bloque grande, la
> Ec. (3) de Lim et al. **es** la Ec. (34) de Ma et al. que implementa
> `bb84.py`, y el residuo cae exactamente como `1/sqrt(N)`: 4.33e-04 a 1e16
> pulsos, 4.33e-06 a 1e20, 4.33e-08 a 1e24—; y V2 contra su Fig. 1, cuyo cociente
> publicado de **1.75** entre bloques de 1e9 y 1e7 se reproduce en **1.79**. Ese
> cociente es además lo que **decide** una ambigüedad de su modelo de error, y lo
> que **no** se reproduce —su curva de bloque 1e4— queda escrito como hueco 16
> del ADR 0009 y como un test que asierta el desacuerdo.
>
> Entrada anterior: **segundo módulo de la Etapa 2.3**,
> `qkd/bb84.py` (§24): BB84 con pulsos coherentes débiles y estados decoy, la
> primera implementación de `QkdProtocol`. **Cuatro decisiones con su número:**
> (1) se usa el rendimiento **exacto** de Ma et al. Ec. (7) primera línea —que
> **es** `click_probability`— y no su aproximación Ec. (10), que por encima de
> **7.152 cuentas por puerta devuelve una ganancia mayor que uno**; (2) el QBER se
> escribe como **mezcla** para que `E ≤ ½` se cumpla en coma flotante, cosa que el
> numerador publicado no hace a partir de **3.912 cuentas por puerta** —el sol
> brillante de la ITU está un 12.6 % por debajo—; (3) donde la cota decoy no
> certifica nada se devuelve `e_1 = ½` y **no** `e_1 = 0`; (4) `q` cuenta los
> pulsos gastados en decoys. **La intuición que hubo que corregir:** la cota no
> falla por pérdida —de η = 1 a 1e-08 sigue positiva— sino por **intensidad**,
> por encima de µ = 3.72. **Verificación:** V3 contra el programa lineal del que
> la Ec. (34) es forma cerrada (`linprog`, 1e-09), y V2 contra el óptimo analítico
> de µ de la Ec. (12) al 0.1 %, con tolerancia derivada.
>
> Entrada anterior: **primer módulo de la Etapa 2.3**,
> `qkd/base.py` (§23): la frontera entre el canal y un protocolo. Qué entra
> (`LinkConditions`), qué sale (`KeyRate`), qué interfaz se implementa
> (`QkdProtocol`) y qué nombre puede escribir un escenario (`ProtocolRegistry`).
> Sin física dentro: toda fórmula sobre BB84 es de `bb84.py`.
>
> **Las tres trampas que le dan forma.** (1) *Una media no es una probabilidad*:
> `NoiseBudget` da cuentas por puerta como **media** y un protocolo necesita la
> **probabilidad** `Y_0 = 1 - exp(-µ)`. Medido con el día claro de 6 W/(m²·µm·sr)
> que Ntanos et al. citan a 1550 nm, leer la media como probabilidad sobreestima
> **un 3.58 %** en su telescopio de 2.3 m y **un 0.38 %** en el de 0.75 m —
> pequeño, silencioso y a favor del enlace (la versión patológica, 3.42 «de
> probabilidad», ya estaba tasada en §20). La conversión **es**
> `click_probability` con señal cero, no una segunda copia de la exponencial.
> (2) *La transmitancia ya lleva el receptor dentro*, así que `LinkConditions`
> tiene un campo de transmitancia y **ninguno** de eficiencia: no hay par que
> multiplicar, y el doble conteo de 6.36 dB de §22 no tiene por dónde entrar.
> (3) *Por pulso no es por segundo*: solo se guarda la forma por pulso y la otra
> se deriva, como en `LossBudget`.
>
> **La interfaz comprueba a sus implementaciones.** `key_rate` es concreto y
> delega en `_key_rate`, y al volver comprueba tres cosas que se pueden equivocar
> sin que nada parezca raro: la forma (un producto exterior da un `(n, n)` con la
> diagonal correcta), la tasa de pulsos (se copia, no se recalcula) y el nombre.
> Cada una tiene detrás un test con una implementación rota a propósito.
>
> **Y dos ausencias con motivo:** no hay entrada de finite-key por bloques —una
> cota finite-key habla de un bloque, y un bloque es una integral sobre el pase,
> que es `system/key_volume.py`—, así que toda tasa de esta interfaz es
> `ASYMPTOTIC` y lo dice en su propio campo; y el registro no tendrá jamás un
> nombre para E91, CV-QKD, MDI-QKD ni TF-QKD mientras no estén implementados
> (regla del [ADR 0005](../docs/adr/0005-propagation.md), con control negativo
> sobre el registro real).
>
> Entrada anterior: **séptimo y último módulo de la Etapa
> 2.2**, `channel/link_budget.py` (§22): todas las pérdidas en un sitio. **Con
> esto la Etapa 2.2 queda cerrada.**
>
> **El hallazgo:** dos de los seis módulos que ensambla no devuelven un número
> —apuntado devuelve una distribución, turbulencia una varianza— y la práctica
> publicada de **sumar el cuantil al 1 % de cada uno no da un presupuesto al
> 1 %**. Las dos colas tienen forma cerrada *en decibelios*: la de apuntado es
> **exactamente exponencial** y la de escintilación **exactamente gaussiana**,
> así que su suma es una gaussiana modificada exponencialmente y el cuantil
> conjunto es exacto sin Monte Carlo — **1.668 dB donde la suma publicada da
> 2.312 dB**. Son 0.644 dB de margen que nadie pidió y, sobre todo, una etiqueta
> falsa: ese presupuesto es del **0.066 % de outage**, quince veces más estricto
> que el 1 % impreso a su lado.
>
> **La trampa que da forma al módulo:** `click_probability` toma una `efficiency`
> y un presupuesto quiere la cadena del receptor como línea, así que hacer las
> dos cosas la cuenta **dos veces — 12.71 dB en vez de 6.36**, un factor 4.3 en
> tasa de clave. El API guarda las dos transmitancias con nombre y ninguna es el
> producto de la otra por algo que haya que recordar.
>
> **El segundo hallazgo, y salió de perseguir un V2 que no cerraba:** el total
> de bajada de 20 dB de Ntanos et al. §4.2.1 dejaba **4.259 dB** sin explicar, y
> cerrarlos con extinción exigía `L_zen = 0.375` — un orden de magnitud más de lo
> creíble a 1550 nm. **Los decibelios que faltaban no estaban en la atmósfera,
> estaban en el transmisor.** `beam.py` propaga una gaussiana **sin truncar** y
> el borde de la apertura corta el 13.5 % del haz; el número tentador —0.632 dB
> de potencia recortada— es la respuesta a otra pregunta, porque en el eje lo que
> integra es la **amplitud** y la intensidad es su cuadrado. El modelo sin
> truncar sobreestima `[1-exp(-α²)]²/[1-exp(-2α²)]`, que a `α = 1` son
> **3.352 dB**. Con ese término el presupuesto sube a **19.094 dB** y el residuo
> baja a **0.906 dB** (`L_zen = 0.812`, ordinario): **compatible, no
> reproducido**. Y `tests/golden/README.md` llevaba este término predicho en
> **0.63 dB** desde antes de que el módulo existiera — corregido allí, con la
> forma cerrada verificada contra la integral de difracción por cuadratura.
> Hueco 15 del [ADR 0009](../docs/adr/0009-citation-policy.md).
>
> **La extinción atmosférica sigue siendo un hueco declarado**, y por eso
> `zenith_transmittance` es un **argumento obligatorio sin defecto**: la ley de
> escala está publicada y numerada, el número que escala no, porque la UIT
> publica absorción y dispersión **solo como figuras** (hueco 14). Dos cosas más
> de la misma fuente:
> su Ec. (18) **devuelve un número negativo y lo llama pérdida** (es el nivel, no
> la caída — sumarla como está impresa deja el total equivocado en el doble del
> desvanecimiento), y una log-varianza no es un índice de escintilación
> (convertir dos veces cuesta 0.005 dB donde el enlace opera y 2.36 dB en el
> límite de la teoría).
>
> Y un defecto de los hermanos que solo aparece al ensamblarlos: un **eje
> temporal vacío** hacía reventar a `beam`, `turbulence`, `pointing` y
> `background` en el `np.max` con el que deciden si avisan. `detector.py` ya
> tenía la guarda desde §21; ahora la tienen los cinco.
>
> Entrada anterior: **sexto módulo de la Etapa 2.2**, `channel/detector.py`
> (§21): la cadena de eficiencia, las cuentas oscuras, el afterpulsing y el
> tiempo muerto. Lo que el detector pierde, lo que se inventa, y cuándo no está
> escuchando. **La regla que da forma al módulo:** las medias se suman y la
> exponencial se hace una vez, al final — porque las **tres** formas publicadas
> que reproduce son truncamientos a primer orden de eso, excelentes en su punto
> de operación (7e-12, 0.16 % y 1.2e-6) y las tres por encima de 1 en el barrido
> diurno de este proyecto (**1.93, 1.006 y 3.42**). **La trampa:** la cadena de
> eficiencia se aplica a todo lo que entró por la apertura y a nada que naciera
> dentro del detector; aplicársela también a las cuentas oscuras esconde
> **0.94 dB de ruido**. **Y el hallazgo que pone una condición a
> `background.py`:** el gating no toca el afterpulsing, así que estrechar de 1 ns
> a 100 ps vale **10 dB con el nanohilo de Ntanos et al. y 0.22 dB con el APD de
> InGaAs de Lim et al.**
>
> Entrada anterior: **quinto módulo de la Etapa 2.2**,
> `channel/background.py` (§20) — la luz que llega cuando no se envió nada, y la
> Ec. (20) que llama «probability» a un número esperado de cuentas que con la luz
> solar tabulada por la UIT vale 3.42. (La cabecera no se actualizó al cerrar esa
> entrada; queda anotado aquí para que el orden de la bitácora no engañe.)
>
> Entrada anterior: **cuarto módulo de la Etapa 2.2**,
> `channel/pointing.py` (§19): el desvanecimiento por jitter de apuntado, que es
> el efecto que más castiga el enlace y que **devuelve una distribución, no un
> número**. Jitter gaussiano en dos ejes → error radial Rayleigh → ley de
> potencias `F(x) = x^(gamma²)` con un solo parámetro: el radio del haz medido
> en jitters. Medido: la pérdida **media** son 0.22 dB y la que se supera 1 vez
> de cada 100 son **1.03 dB**; con 2 µrad de jitter, 1.35 dB y **7.32 dB**.
> Diseñar con la media es diseñar para un enlace que no existe.
>
> **La trampa que da forma al módulo:** el `A_0` de la Ec. (9) de Farid &
> Hranilovic **es** el acoplamiento geométrico de `beam.py`, así que multiplicar
> «pérdida geométrica × pérdida de apuntado» tal como está publicada cuenta
> `A_0` dos veces — **17.5 dB inventados de la nada**, y un total de 35 dB es
> tan plausible a la vista como el correcto de 17.6 dB. Todas las funciones
> devuelven el factor **relativo**, normalizado a exactamente 1 con apuntado
> perfecto.
>
> Y dos cosas que el oráculo exacto (su Ec. (8), integrada numéricamente) dijo:
> **la fórmula de `beam.py` tiene ahora una segunda fuente publicada
> independiente** —concuerdan a ocho dígitos, una por ganancias de antena y otra
> por integral de superficie— y **la condición de validez que los propios
> autores publican (`W/a > 6`) falla para el telescopio de 2.3 m del sistema de
> referencia**, que es justo la configuración de su mejor presupuesto de enlace.
> Sale en `warnings[]`, con la medida de lo que cuesta al lado: 0.36 % donde el
> jitter pone el haz de verdad, 35 % a tres radios de haz.
>
> Entrada anterior del mismo día: **tercer módulo de la Etapa 2.2**,
> `channel/beam.py` (§18), y con él la etapa entra en la bitácora: §18 recoge
> también lo que la verificación cazó en `atmosphere.py` y `turbulence.py`, que
> hasta ahora vivía solo en los docstrings y en el
> [ADR 0009](../docs/adr/0009-citation-policy.md).
>
> `beam.py` es el término más grande del presupuesto de enlace —decenas de dB
> contra un par de dB de todo lo demás— y sale de algo muy simple: un haz que
> sale de un telescopio de 15 cm mide 8 m de ancho tras 600 km, y un telescopio
> de 0.75 m en tierra intercepta menos del 2 % de él. **El hallazgo de esta
> entrada:** la Ec. (5) de Ntanos et al. 2021 imprime la ganancia de transmisión
> como `(8/w_0)²` cuando la forma que cierra la identidad con la integral
> gaussiana es `8/w_0²` — 8 veces, **9.03 dB optimista**. No hace falta discutir
> qué lectura se quiso: con los propios parámetros del paper (2.3 m a 600 km) la
> forma impresa devuelve una transmitancia de **1.36**, más luz recogida que
> transmitida. QuOSS usa la integral exacta, que satura en 1.
>
> Y la conclusión de diseño que no era obvia: agrandar el telescopio transmisor
> estrecha el haz como `1/D_T` pero reduce el vaivén por turbulencia solo como
> `D_T^(-1/6)`, así que **la razón vaivén/divergencia crece como `D_T^(5/6)`**.
> Un transmisor de subida de 1 m pasea su haz **3.15 anchos de haz**: estrechar
> el haz no ayuda a una subida más allá del punto en que el haz es más fino que
> su propio temblor.
>
> Entrada anterior del mismo día: **la Etapa 2.1 (`orbits/`) queda cerrada** con
> sus dos últimos módulos, `geometry.py` (§16) y `constellations.py` (§17).
>
> `geometry.py` es el módulo que convierte una órbita en lo que un telescopio ve:
> elevación, azimut, distancia oblicua («slant range», la línea recta
> estación↔satélite, que no es la altitud), velocidad de acercamiento, y el
> **ángulo de point-ahead** — cuánto hay que apuntar por delante de donde se ve
> el satélite, porque en el tiempo que la luz tarda en ir y volver el satélite se
> ha movido. La corrección al roadmap la dio la medición: ese ángulo lleva
> **factor 2**, no el `v_perp/c` de una sola vía, porque un terminal monostático
> transmite adelantado y a la vez recibe por donde la luz realmente viene.
> Medido para un paso a 67.1° de elevación sobre Castelldefels en la SSO de
> 700 km de este repo: **50.6 µrad**, contra los 35 µrad que el roadmap citaba
> antes de tener la cuenta hecha.
>
> `constellations.py` (Walker-Delta, inclinación heliosíncrona, traza repetida)
> **queda escrito y aparcado**: la decisión de alcance del 2026-09-10 es hacer un
> solo satélite, así que no se construye nada encima de él por ahora.
>
> Entrada anterior del mismo día: **quinto módulo de la Etapa 2.1**
> (`orbits/tle.py`): parseo de TLE («Two-Line Element set») y propagación con
> SGP4 (`sgp4` de PyPI, sin reimplementar) → [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md).
> `PropagationMethod` gana un tercer miembro, `SGP4`, que `propagate()`
> **deliberadamente no sabe ejecutar** — pedírselo da `NotImplementedError`, no un
> resultado plausible. `tle.py` no construye ningún `ClassicalElements`: la
> disciplina que el ADR 0006 dejó preparada (`MEAN_KOZAI_SGP4`, aún sin usar) se
> cumple por no escribir esa línea, no por una guarda de tipos. Y `parse_tle`
> valida dos trampas reales de `sgp4.api.Satrec.twoline2rv` que la librería deja
> pasar en silencio: un checksum corrupto y una entrada basura, las dos
> verificadas a mano contra el paquete instalado antes de decidir la guarda.
>
> Entrada anterior: **2026-08-04** — **las siete entradas de
> [`INCONSISTENCIAS.md`](INCONSISTENCIAS.md), cerradas** (§14). La grande no era una
> de las seis inconsistencias sino la consideración C1: los «219 km» citados en
> quince sitios, incluido un mensaje de error, **no se reproducían** — la cifra real
> es 5.9 veces mayor, y además no existe una cifra única porque el coste depende de
> en qué punto de la órbita se declaren los elementos.
>
> Entrada anterior a esa: **2026-08-01** — **la bandera osculador/medio**, que no es
> un módulo nuevo sino la pieza que faltaba entre los tres que ya hay. Con sus
> tres subdecisiones resueltas y medidas (→ [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md)).
> El aviso que llevaba tres documentos escrito pasa a ser un `DomainError`, y en
> las **dos** direcciones, no solo en la que parecía.
>
> Entrada anterior del mismo día: cuarto módulo de la Etapa 2.1
> (`orbits/propagator.py`). La simulación adquiere tiempo, y el módulo se envía
> con el enum de métodos **incompleto a propósito**: es mejor un nombre ausente
> que un modo que degrada en silencio.
>
> Y la anterior a esa: tercer módulo (`orbits/perturbations.py`). La Tierra deja
> de ser una masa puntual, y el roadmap se corrige donde la medición dijo que
> estaba equivocado.

---

## 1. Estado

| | |
|---|---|
| Etapa cerrada | **1 — `core/`**, **2.1 — `orbits/`** y **2.2 — `channel/`** |
| En curso | **2.3 — `qkd/`**, sin empezar. La 2.2 cierra con sus siete módulos: `atmosphere.py`, `turbulence.py`, `beam.py` (§18), `pointing.py` (§19), `background.py` (§20), `detector.py` (§21) y `link_budget.py` (§22). Es donde el proyecto se jugaba la credibilidad, porque ahí nadie detecta a ojo que 45 dB debería ser 39 dB: ver la política de citas ([ADR 0009](../docs/adr/0009-citation-policy.md)), con **catorce huecos declarados y ninguno rellenado** |
| Física implementada | Marcos y escalas de tiempo · dos cuerpos · gravedad zonal J2/J3/J4 y teoría secular de J2 · propagación sobre una rejilla temporal, con época y método explícitos · **el tipo de elemento (osculador/medio) como parte del tipo, no como aviso** · **parseo de TLE y propagación SGP4**, con época propia y sin construir jamás un `ClassicalElements` medio · **ángulos de visión, distancia oblicua, velocidad de rango y point-ahead** desde una `Trajectory` en TEME · Walker-Delta, SSO y traza repetida (escrito, aparcado) · **perfil `C_n²(h)` y refracción · escintilación, promediado de apertura, `r0` y ángulo isoplanático · divergencia, acoplamiento geométrico y vaivén del haz · desvanecimiento por jitter de apuntado, como distribución · radiancia de cielo, fondo y puerta temporal · cadena de eficiencia, cuentas oscuras, afterpulsing y tiempo muerto · presupuesto de enlace y de ruido completos, con el cuantil conjunto de los dos desvanecimientos en forma cerrada** |
| Novedad de esta entrada | **`channel/link_budget.py`** (§22), y con él **la Etapa 2.2 queda cerrada**. Dos hallazgos. (1) Sumar dos cuantiles al 1 % **no da un presupuesto al 1 %**: las dos colas tienen forma cerrada en dB (exponencial y gaussiana), su suma es una gaussiana modificada exponencialmente, y el cuantil conjunto exacto son **1.668 dB** contra los **2.312 dB** de la suma publicada — un outage real del **0.066 %**, quince veces más estricto que la etiqueta. (2) Persiguiendo los 4.259 dB que le faltaban al total de 20 dB de Ntanos et al., apareció un término que no estaba en la atmósfera sino en el **transmisor**: truncar la gaussiana en la apertura cuesta **3.352 dB** y no los 0.63 dB que el propio repo tenía predichos. Residuo final **0.906 dB** (`L_zen = 0.812`): compatible, no reproducido |
| Novedad de la entrada anterior | **`channel/detector.py`** (§21). **Las medias se suman y la exponencial se hace una vez, al final**, porque las tres formas publicadas que reproduce pasan de 1 en el barrido diurno (1.93, 1.006 y 3.42). Aplicar la cadena de eficiencia a las cuentas oscuras esconde **0.94 dB** de ruido, y el gating **no toca el afterpulsing**: estrechar la puerta vale 10 dB con un nanohilo y **0.22 dB** con un APD de InGaAs |
| Novedad de dos entradas atrás | **`channel/background.py`** (§20). Las dos ecuaciones publicadas son la misma y discrepan en las **unidades** del campo de visión (41.05 dB pasarlo mal, 6.02 dB leerlo como semiángulo), y la Ec. (20) llama «probability» a un número esperado de cuentas que con la luz solar tabulada por la UIT vale **3.42** |

Verificación ejecutada **el 2026-09-12, con `channel/link_budget.py` en el
árbol** (estos números sí se han vuelto a correr, por la misma regla que costó
los «219 km» de §14.1):

```bash
uv run ruff check .          # All checks passed!
uv run ruff format --check . # 52 files already formatted
uv run mypy                  # Success: no issues found in 52 source files
uv run pytest                # 1227 passed in 24.42s
uv run pytest --cov          # 99 % global (2194 sentencias, 454 ramas, 8 sin cubrir)
```

Cobertura de `channel/`: los siete módulos —`atmosphere`, `turbulence`, `beam`,
`pointing`, `background`, `detector`, `link_budget`— y el compartido
`_validation` al **100 %**, ramas incluidas. Las 8 sentencias sin cubrir del
total están todas fuera de `channel/`: cuatro en `orbits/constellations.py` (que
está aparcado), una en `core/rng.py` y tres en `core/types.py`.

Cobertura por módulo de `orbits/`: `frames`, `kepler`, `perturbations`,
`propagator`, `geometry`, `tle` y `_validation` al **100 %**, ramas incluidas.
`constellations.py` se queda en **96 %** — las cuatro sentencias sin cubrir son
las ramas de fallo de `brentq` en la traza repetida, y quedan así a propósito
porque el módulo está aparcado.

La suite está en **36 s**. El coste añadido de esta entrada son los dos Monte
Carlo de 4e6 muestras que verifican el cuantil conjunto (marcados `physics`);
todo el coste base siguen siendo las integraciones DOP853, que son el oráculo de
`perturbations.py` y no tienen forma barata.

---

## 2. La decisión que bloqueaba la etapa: el oráculo ya no es SimulCTTC

Era **el** pendiente bloqueante de la etapa 1. Se resolvió invirtiéndolo: el
roadmap decía tres veces «SimulCTTC es el oráculo», y eso era falso. Leyendo el
código viejo aparecieron, en unos minutos:

| Sitio | Qué hace | Error |
|---|---|---|
| `propagation.py:180` `ecef_to_latlon` | latitud **geocéntrica** vía `atan2(z, hypot(x,y))`; `alt = \|r\| − R_eq` | hasta **0.19°** en latitud, **−21.4 km** de altitud en el polo |
| `propagation.py:190` `ecef_from_latlon` | estaciones sobre una **esfera** de radio `R_eq` | desplazadas hasta ~21 km → sesgo directo en elevación y slant range |
| `propagation.py:120` J3 «secular» | los zonales **impares no tienen término secular de primer orden**; su propio docstring lo admite y aun así lo mete como tasa | física incorrecta |
| `propagation.py:238` | `datetime.utcnow()` por defecto + `except ValueError: pass` al parsear la época | run irreproducible + degradación silenciosa |
| `propagation.py:64` | `if a <= 0: return SecularRates(0,0,0,0)` | ceros plausibles en vez de fallo |

Congelar esa salida como golden test habría **canonizado los bugs**.

### El protocolo que lo sustituye

Cuatro niveles, documentados en [`tests/golden/README.md`](../tests/golden/README.md):

| Nivel | Qué | Prueba | En CI |
|---|---|---|---|
| **V1** | invariantes, property-based, sin datos externos | consistencia interna | sí |
| **V2** | valores publicados, con su cita al lado | **corrección absoluta** | sí |
| **V3** | implementación independiente, congelada con manifest | corrección en régimen amplio | sí (contra el fichero) |
| **V4** | snapshot de la salida propia | que un refactor no cambió nada. **No es validación** | sí |

**La regla que importa:** V4 no es validación. Cualquier cosa que se reporte como
validada tiene que trazar a V2 o V3. SimulCTTC baja a *diff informativo no
bloqueante*.

### Los oráculos, verificados como disponibles

- **`sgp4` de PyPI trae los datos de verificación oficiales de Vallado**:
  `SGP4-VER.TLE` (8.6 KB) y `tcppver.out` (140 KB), de AIAA 2006-6753. Su versión
  Python pura concuerda con la C++ de referencia a **0.1 mm**. Es decir: la
  validación de SGP4 llega gratis con una dependencia que había que añadir igual.
- **astropy/ERFA** para marcos, GMST y geodesia (exacto al mm). Ya en uso.
- **GMAT** (NASA, libre, con su V&V hecho contra STK y FreeFlyer) u **Orekit**
  para J2/J4 y look angles. Pendiente, para `perturbations.py` y `geometry.py`.
- **Ejemplos numéricos de Vallado** (Kepler, COE↔RV, GMST, az/el). Son V2, el
  nivel más fuerte. **No están** en `data/` porque hay que transcribirlos del
  libro, y **inventar números plausibles y etiquetarlos «publicados» sería peor
  que no tener V2**. El hueco está escrito en el README, no tapado.

### Cómo funciona en la práctica

```
tests/golden/
├── README.md                    # los cuatro niveles y las reglas
├── data/frames_reference.json   # 13 fechas + 13 GMST + 12 sitios + 16 estados TEME
└── generators/gen_frames_reference.py   # a mano, nunca en CI
```

El generador **no importa `quoss`** (un oráculo que importa el código bajo test es
un espejo), y `astropy` vive en un grupo de dependencias **no** por defecto
(`uv run --group reference …`), así que CI sigue offline y ligero.

---

## 3. Lo que el protocolo cazó en `frames.py`

Justifica el protocolo mejor que cualquier argumento:

1. **`calendar_to_jd` estaba mal por un día.** La expresión de Vallado Alg. 14 usa
   `int(7·(y + int((m+9)/12))/4)`, que es la regla de bisiestos **juliana** («cada
   cuatro años»), así que falla al cruzar un año secular no bisiesto. Medida
   contra astropy: exacta solo entre **1900-03-01 y 2100-02-28**, y ±1 día fuera.
   Sustituida por **Fliegel–Van Flandern**, exacta en todo el calendario
   gregoriano. Hay un test explícito por año secular (1900, 2000, 2024, 2025, 2100).

2. **El presupuesto de error de marcos no era el que había escrito.** Medí 178 m
   de discrepancia contra astropy donde esperaba ~15 m. Al descomponerlo: es
   **DUT1**, no movimiento polar. Rotando por GMST(UT1) el residuo cae a **14.4 m**
   — y eso sí es movimiento polar. La tabla del docstring ahora lleva números
   medidos, y el test los mantiene honestos.

3. **Un caso de referencia caía en un segundo intercalar.** En cualquier momento
   del 2015-06-30, las dos rutas de DUT1 de astropy (`get_delta_ut1_utc()` y el
   UT1 que usa `teme_to_itrs_mat`) discrepan — 0.5 s a mediodía, 1 s a las
   23:59:59 — porque una interpola a través del salto. Ese caso medía contabilidad
   de segundos intercalares, no la rotación bajo test. Sustituido por 2015-03-15
   (DUT1 ≈ −0.55 s, ambas rutas de acuerdo a 1e-5 s). **No se relajó la tolerancia:
   se quitó una entrada fuera de alcance y se documentó por qué.**

4. **Dos afirmaciones mías en comentarios eran falsas y los tests las tumbaron:**
   la iteración geodésica converge en **7** pasadas, no en 6 (ratio medido 4.7e-3);
   y el eje Norte del ENU **no** es exactamente cero al moverse en longitud —
   la cuerda entre dos puntos de un paralelo deja un término de segundo orden
   `sin(lat)·ρ·Δlon²/2`. Es geometría, no error, así que el test acota la razón y
   además comprueba la fórmula del término.

5. **Una rama de fallo habría lanzado `NameError`.** Si `_GEODETIC_MAX_ITER` fuese
   0, el `else` del `for` leería una variable sin asignar en vez de reportar el
   último desplazamiento. Inicializada a `inf`, y hay un test que la ejerce.

---

## 4. Lo que el V2 de Vallado cazó en `kepler.py`

El hueco que `tests/golden/README.md` declaraba abierto —«los ejemplos resueltos
de Vallado no están, porque hay que transcribirlos del libro»— está cerrado para
la ecuación de Kepler y para COE↔RV. Son los **Ejemplos 2-1, 2-5 y 2-6** de la
4.ª edición, transcritos con su página y viviendo junto a su cita en
`tests/orbits/test_kepler.py`, no en `data/`: un valor V2 es un número que un
lector puede contrastar contra el libro sin ejecutar un generador.

Transcribirlos encontró tres cosas, y ninguna se tapó con una tolerancia:

1. **La inclinación del Ejemplo 2-5 no cuadra con su propio vector de estado.**
   El `r`, `v` publicado da **87.86913°**; el libro imprime **87.870°**. La
   diferencia, 0.00087°, es 1.7 veces el medio dígito que tres decimales
   permiten, y es la **única** magnitud del ejemplo que excede su propio
   redondeo — `p`, `a`, `e`, Ω, ω y ν caen todas dentro. Está anotada con su
   número en un test que la afirma explícitamente. Ensanchar el límite hasta que
   pasara habría convertido un dato V2 en un adorno.

   Que el error está en el dígito impreso y no en nuestro cálculo lo dice el
   propio ejemplo: los seis elementos extraídos reconstruyen el estado publicado
   a menos de **1 nm**, así que la inclinación es consistente con todo lo demás.

2. **Los Ejemplos 2-5 y 2-6 no son un viaje de ida y vuelta**, y tratarlos como
   tal habría exigido una tolerancia lo bastante floja como para esconder un
   error real. Los elementos de entrada del 2-6 son los del 2-5 redondeados a dos
   decimales; esa caja de redondeo admite **±1.3 km** de posición. Lo que el 2-6
   licencia de verdad son 1.3 km; lo que se mide son **25 m**. Se asertan las dos
   por separado, porque solo la primera es una afirmación V2 y la segunda es una
   guarda de regresión.

   El estado perifocal intermedio, que depende solo de `p`, `e` y ν, sí cuadra a
   **0.1 m** — y eso localiza los 25 m en la rotación, donde el libro arrastra
   menos cifras de las que imprime. Aserta las etapas intermedias que el libro
   publica: es lo que convierte «discrepa» en «discrepa aquí».

3. **El valor `u` de la transcripción era una errata del propio libro, ya
   resuelta.** La fuente daba `u = 145.60549°` como argumento de latitud del
   2-5. Al no poder reproducirlo, quedó fuera de los tests; la entrada anterior
   registraba «no verificable sin página escaneada».

   La página escaneada (Vallado, pág. 116) confirma lo publicado y además
   revela que **el error está en el propio libro**, en dos capas:

   1. **Typo en `|r|`**: el libro usa `|r| = 11456.67 km` en la sustitución,
      cuando el valor correcto calculado previamente en el mismo ejemplo es
      `11456.57 km` (transposición de dígitos, 57 → 67).
   2. **El resultado tampoco cuadra con sus propios operandos erróneos**: evaluando
      la expresión impresa con `|r| = 11456.67` se obtiene `145.7194°`, no
      `145.60549°`. No existe ninguna definición de `u` que recupere el número
      impreso.

   El valor correcto, calculado de `r` y `v` con doble precisión, es
   `u = 145.720087380597°`, confirmado por dos rutas independientes:
   - Fórmula vectorial: `cos u = (n·r)/(|n||r|)` → `145.720087°`
   - Suma de elementos: `ω + ν = 53.384931° + 92.335157° = 145.720087°`

   `u = 145.60549°` queda registrado como **errata documentada** de Vallado
   4.ª ed. El test `test_argument_of_latitude_errata` afirma el valor correcto
   por ambas rutas.

   **Revisado en esta entrada, y reforzado.** La aserción sobre la capa 1 era
   débil: comprobaba que `|145.7194° − 145.7201°| < 1e-3`, lo que habría pasado
   con cualquier número en un intervalo de ±0.001° y no demostraba nada. Ahora el
   test **reproduce la aritmética de la página**: evalúa `arccos(n·r/(|n||r|))`
   con los operandos tal como el libro los imprime — `|n| = 66374.17`,
   `|r| = 11456.67`, y las componentes del nodo redondeadas a un decimal — y
   obtiene `145.7193794974°`, coincidiendo a **1e-9 grados** con la constante
   transcrita. Eso es lo que localiza el error en vez de solo registrarlo: prueba
   que la fórmula está bien transcrita, con lo que el único elemento que no se
   explica es el **resultado impreso**.

   Las dos capas quedan además cuantificadas y comparadas entre sí: el typo de
   `|r|` vale **7.1e-4 grados**, mientras que el hueco hasta el número impreso es
   **0.1146 grados** — 160 veces mayor. La transposición 57→67 no puede explicar
   lo impreso, y nada más en la página tampoco: recuperar `145.60549°` exigiría
   `|r| = 11472.24 km` o `|n| = 66464.9`, que no son transposiciones de nada de
   lo que la página imprime.

   Y una corrección de documentación, del mismo tipo que las de §3: el docstring
   de `VALLADO_2_5_EXPECTED` afirmaba que «dos ángulos auxiliares (longitud del
   periapsis, longitud verdadera) **están asertados**». No lo estaban — no existe
   ningún test que los toque. Corregido para decir la verdad, y dejando anotados
   los valores que nuestros elementos implican (281.2832° y 13.6183°) por si la
   página escaneada los imprime: sería un par V2 gratis.

   **Cerrado después: el V2 validaba el test, no el código.** Queda un hueco
   sutil en lo de arriba, y conviene decir en qué consistía porque es un patrón
   que se puede repetir en cualquier módulo.

   El argumento de latitud `u` es «cuánto ha avanzado el satélite a lo largo de
   su órbita desde que cruzó el ecuador hacia el norte», y vale `ω + ν`. Existe
   en el código como propiedad, `ClassicalElements.argument_of_latitude_rad`.
   Pero `test_argument_of_latitude_errata` **no la llamaba**: leía `coe.argp_rad`
   y `coe.true_anomaly_rad` y los sumaba a mano dentro del test.

   El test era correcto y demostraba lo que decía —que el número impreso en el
   libro está mal— pero lo demostraba sobre una suma escrita en el fichero de
   test. Es decir: el único dato V2 que el proyecto tiene para `u` no tocaba el
   código que los futuros llamantes (`constellations.py`, Brouwer-Lyddane) van a
   usar. Si alguien rompiera la propiedad, ningún test V2 se enteraría.

   Cerrado con dos tests:

   - `test_argument_of_latitude_property_carries_the_v2_value` (V2): pasa el
     estado publicado del 2-5 por `rv_to_coe` y asserta la **propiedad** contra
     `VALLADO_2_5_U_CORRECT_DEG`. Devuelve `145.720087380597°`, las doce cifras
     de la constante.
   - `test_argument_of_latitude_wraps_past_one_turn` (V1): el 2-5 no puede
     ejercitar el envuelto, porque su `ω + ν` son 145.7° y no llega a dar la
     vuelta. Los dos operandos sí vienen ya envueltos a `[0, 2π)`, así que su
     suma puede llegar a 720° y la propiedad es el único sitio donde se pliega.
     Caso construido: `ω = 310°`, `ν = 200°` → la suma cruda es **510°** y la
     propiedad da **150°** (residuo 2.8e-14°). Se corre sobre una pila de dos
     órbitas, una que envuelve y otra que no, porque el pliegue es vectorizado y
     una rama solo se notaría cuando los dos casos comparten llamada.

Y una cuarta, del lado del código: **el plan del solver de Kepler era más
complicado de lo necesario.** §9 de la entrada anterior decía «arranque de
Markley/Danby + Halley con iteraciones fijas». Al implementarlo resultó que el
método de Markley **ya es la solución completa**: una cúbica en forma cerrada más
una cascada de tres correcciones que comparten un solo par seno/coseno. No hay
bucle, así que no puede no converger, y el residuo medido no pasa de **1.4e-15
rad** para toda `e` hasta 0.9999.

---

## 5. Lo que la medición cazó en el propio roadmap

El roadmap pedía, literalmente: «J2/J4 secular analítico + integrador zonal
numérico (el numérico valida al analítico a **O(J2²)**)». La segunda mitad de esa
frase es falsa, y descubrirlo es el hallazgo de esta entrada.

**Por qué no se puede.** Una tasa secular es una afirmación sobre elementos
**medios**. `rv_to_coe` devuelve **osculadores**. La diferencia entre unos y otros
es ella misma O(J2) ≈ 1e-3 relativo — es decir, **mil veces mayor** que la
corrección de segundo orden (`J2²`, `J4` ≈ 1e-6) que se pretendía validar con
ella. Medir el segundo orden alimentando osculadores es como pesar una carta con
una báscula de baño.

No es una sospecha, está medido, y en tres pasos:

| Prueba | Resultado |
|---|---|
| Residuo de 1.er orden vs integración, con osculadores | 1.0e-4 … 2.6e-3 relativo, según inclinación — o sea O(J2), lo esperado |
| Una fórmula candidata de 2.º orden (`J2²` + `J4`) | **mejora en unos casos y empeora en otros** (i = 51.6°: 1.3e-3 → 5.2e-4; i = 98°: 1.0e-4 → **1.4e-3**). Justo lo que se ve cuando la corrección es menor que el ruido de su argumento |
| Promediar los elementos osculadores sobre las revoluciones para «obtener» medios | **no sirve**: el residuo se queda en O(J2) en las seis configuraciones probadas. Los elementos medios de Brouwer no son el promedio temporal de los osculadores |

La pieza que falta es la transformación de período corto de **Brouwer-Lyddane**,
que este proyecto no tiene y que el [ADR 0003](../docs/adr/0003-orbital-elements.md)
avisa de no fingir. Es, además, **la misma pieza** que `tle.py` va a necesitar
para no confundir los elementos medios de un TLE con los osculadores de
`kepler.py`. Cuando entre, los términos de segundo orden pasan a ser validables y
merecerá la pena añadirlos. Antes no: sería enviar código no ejercitado cuyo
propósito entero es una corrección más pequeña que el error de sus entradas — el
mismo argumento con el que el ADR 0003 descartó las variables universales.

### Lo que sí quedó validado, y con algo mejor que una cota

> El residuo relativo de las tasas de primer orden contra la integración numérica
> es **exactamente proporcional a J2**. Escalando J2 por 1, 1/2, 1/4 y 1/8, el
> cociente residuo/J2 se mantiene constante a **cuatro cifras significativas**
> (1.184 a i = 51.6°; 0.088–0.091 a i = 98°).

Esto separa las dos hipótesis que una cota sola no puede separar:

- si la fórmula es correcta y solo está truncada, el término despreciado es
  O(J2²) y el error **relativo** cae linealmente con J2 → es lo que se ve;
- si un coeficiente estuviera mal escrito, sería un error O(J2) dentro de una
  cantidad O(J2), y el error relativo **no se movería** al escalar J2.

Es el patrón de `TestFrameErrorBudget` aplicado a otra magnitud: no decir «se
parece», sino atribuir el residuo.

### J3: la trampa del roadmap, ahora medida en vez de afirmada

El aviso llevaba dos documentos escrito («los zonales impares no tienen término
secular de primer orden»; fue uno de los defectos de SimulCTTC). Ahora está
demostrado, y barato:

> La contribución de J3 a `dΩ/dt`, medida a ω = 0°, 90°, 180° y 270°, va como
> **sin ω**: se anula en 0° y 180°, y cambia de signo entre 90° y 270°
> (±3.2e-11 rad/s). Un término secular daría lo mismo en los cuatro.

Un término que depende de dónde esté el perigeo promedia a cero sobre un ciclo
apsidal. Y aunque no lo hiciera: en su máximo es **cuatro órdenes de magnitud**
menor que la tasa de J2 que tiene al lado.

La prueba se eligió así por coste. Demostrarlo integrando un ciclo apsidal
completo son ~1600 revoluciones; la prueba del signo son cuatro integraciones de
20 y tarda un segundo. Además, `secular_rates_j2` **no tiene ningún parámetro
donde meter un J3**, y hay un test que aserta esa forma de la API para que un
refactor no pueda reintroducir el peligro en silencio.

### Tres cosas más que aparecieron al escribir los tests

1. **El paso de la diferencia finita no estaba donde yo creía.** Para verificar
   que la aceleración es el gradiente del potencial, escribí «h = 1 km está cerca
   del óptimo» y lo puse en un comentario. Falso: el truncamiento cae como `h²` y
   la cancelación crece como `1/h`, y barriendo 9 posiciones con pasos de 300 m a
   3 m el peor caso toca fondo en ~1e-9 con **h = 30 m**. El paso de 1 km era
   **250 veces peor**. La constante ahora lleva el barrido en su docstring.
2. **Calcular el potencial perturbador restando dos potenciales tira nueve
   cifras.** `U_total − U_dos_cuerpos` son ~60 km²/s² sacados de dos números de
   ~6e4: la cancelación cuesta dos órdenes de magnitud de exactitud en el
   gradiente. Evaluando la suma zonal directamente no hay cancelación, y el mismo
   test pasa de acotar los armónicos al 0.1 % del total a acotarlos al 1e-8 de
   **sí mismos**.
3. **`solve_ivp` con un intervalo de longitud cero devuelve éxito y ningún
   punto.** Una muestra en la época habría dejado una fila del array sin
   inicializar — basura silenciosa, no un fallo. Se escribe directamente desde el
   estado inicial, que además es exacto. Lo destapó el test que pide `dt = 0`.

Y una cuarta, del lado del test y no del código: dos casos de prueba que escribí
con `e = 0.1` a 7078 km tienen el **perigeo dentro de la Tierra** (6370 km). La
guarda del modelo de fuerzas los rechazó, que es exactamente su trabajo.

---

## 6. La bandera osculador/medio — las tres subdecisiones (→ [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md))

No es un módulo nuevo: es un campo en `ClassicalElements` y dos `if`. Está aquí
porque cierra el pendiente más antiguo de la etapa y porque las tres cosas que
había que decidir para escribirla no eran obvias — la nota anterior las dejó
apuntadas precisamente para no resolverlas de pasada.

### Qué es la bandera, para quien llegue nuevo

Un satélite real no sigue una elipse: la Tierra está achatada y lo empuja fuera de
ella todo el rato. Así que «la órbita» son dos cosas distintas:

- **Osculadores**: la elipse que seguiría *desde este instante* si la Tierra se
  volviera de golpe una esfera. Es tangente a la trayectoria real y cambia
  continuamente. Es lo que devuelve `rv_to_coe`, porque un vector de estado no
  puede determinar otra cosa.
- **Medios**: esa misma órbita con el bamboleo rápido ya restado. No existe en
  ningún instante, pero es de lo que habla una tasa secular.

La diferencia es O(J2) ≈ una parte en mil. Sobre 7000 km, ~7 km — y la parte que
importa **crece**: **86 km por vuelta y 1290 km al día** en along-track para una
SSO de 700 km declarada en ν = 0, que en unidades de pase son ≈11.5 s de reloj
orbital por vuelta y ≈2.9 minutos al día. Un pase dura diez minutos. (Cifras
corregidas el 2026-08-04: las que estaban aquí eran 5.9 veces menores y nunca se
reprodujeron — ver §14.1.)

Ahora `ClassicalElements` lleva un `ElementType` igual que lleva su `Frame`, con
dos miembros: `OSCULATING` (el defecto) y `MEAN_BROUWER`.

### Subdecisión 1 — `coe_to_rv` rechaza los medios, y esa es la guarda grande

La guarda que parecía la natural es la otra: `secular_rates_j2` es quien necesita
elementos medios. Pero **los kilómetros se pierden en el sentido contrario**.
Alimentar la teoría secular con osculadores cuesta O(J2) *sobre la tasa*, que es
del tamaño del término que la teoría de primer orden ya descarta; convertir unos
medios a estado como si fueran osculadores es la tabla de arriba. Comprobar en un
solo sentido habría dejado abierto el agujero grande, así que se cierran los dos.

Coste para el código de hoy: **ninguno**. `rv_to_coe → coe_to_rv` sigue siendo
osculador en las dos puntas.

Lo que apareció al implementarlo, y no es evidente: `TWO_BODY` **no** le pasa a
`coe_to_rv` los elementos del llamante. Construye una pila aplanada de `S · n`
juegos y llama una vez. Si esa pila hubiera tomado el defecto `OSCULATING`, el
modo de dos cuerpos habría **blanqueado** unos elementos medios pasándolos por
delante de la única comprobación que existe — y ninguna aserción de forma se
habría enterado, porque la forma es correcta. La pila reenvía la etiqueta, y hay
un test parametrizado sobre `PropagationMethod` que lo fija: el día que entre
`J2_SECULAR_ANALYTIC` fallará, que es cuando hay que decidir su regla propia.

### Subdecisión 2 — dos miembros, y el segundo se llama `MEAN_BROUWER`

«Medio» no es una cosa, es una por teoría: los de un TLE son de Brouwer con Kozai
y constantes WGS-72; los que quiere `secular_rates_j2` son de Brouwer-Lyddane con
EGM96. Un enum de dos valores cuyo segundo se llamara `MEAN` los haría parecer
intercambiables, que es justo el error que la bandera existe para prevenir.

El argumento que desempata: **el miedo a quedarse en dos era «añadir un tercero
después toca a todos los llamantes», y ese miedo desaparece al nombrar el miembro
por su teoría.** Nadie puede haber escrito `MEAN`, así que `MEAN_KOZAI_SGP4` se
añade el día que algo lo produzca sin tocar un solo sitio.

Y no se añade hoy porque el ADR 0005 ya decidió que `tle.py` no construye un
`ClassicalElements`: SGP4 devuelve estado en TEME y los elementos de ese estado
son osculadores. Misma regla que el enum incompleto de la entrada anterior: un
miembro que ningún código puede producir es una etiqueta que solo invita a
ponerla a mano. Un test fija el conjunto exacto de miembros y aserta además que
**no existe** un `MEAN` a secas.

### Subdecisión 3 — `relabelled_as`, y por qué no `assume_mean=True`

`TestSecularRatesAgainstIntegration` alimenta osculadores a `secular_rates_j2`
**queriendo**: un mismo juego de seis números hace de condición inicial de la
integración (osculador, obligatoriamente) y de argumento de la teoría (medio), y
de esa tensión sale la medición que sostiene el módulo — que el residuo del primer
orden es exactamente proporcional a J2 (§5).

Con la bandera esos tests necesitaban una vía explícita:

| | `assume_mean=True` en la física | **`relabelled_as` en el contenedor (elegida)** |
|---|---|---|
| Dónde vive | en la API de física | en el objeto de datos |
| Quién lo alcanza | cualquiera, incluido un YAML | quien tiene los elementos y escribe la palabra |
| Tiene default | sí, forzosamente | no aplica |
| Qué dice el nombre | «supón» | «reetiquetado»: admite que no convierte |

`relabelled_as` devuelve un objeto nuevo con **los mismos números bit a bit**, y
hay un test que lo aserta campo por campo: si algún día creciera una conversión
detrás de ese nombre, falla — y debe fallar.

La distinción fina, que es la que hace que los tests sigan diciendo la verdad: los
que solo preguntan por lo que la fórmula calcula (un signo, un límite, la
inclinación crítica) **construyen** elementos medios (`_mean_elements`), porque
eso es lo que dicen ser y nada allí los convierte en un estado; solo los que
mienten a propósito reetiquetan. Dos ayudas distintas para dos afirmaciones
distintas.

### Lo que sigue sin existir, dicho en voz alta

**No hay conversión medio↔osculador.** Brouwer-Lyddane no está, y este ADR no la
finge: la bandera de hoy es una **puerta cerrada que marca dónde haría falta**, no
un paso más en una tubería. Los mensajes de error lo dicen —nombran la
transformación que falta en vez de apuntar a una función que el lector iría a
buscar y no encontraría— y esa sigue siendo la condición de entrada del modo
analítico y de los términos seculares de segundo orden.

---

## 7. `orbits/propagator.py` — las decisiones (→ [ADR 0005](../docs/adr/0005-propagation.md))

Este módulo **no añade física**: todo lo que calcula ya estaba en `kepler.py` y
en `perturbations.py`. Lo que añade es tiempo —una época y una rejilla— y las
cuatro decisiones que los módulos anteriores dejaron abiertas a propósito.

### La decisión de esta entrada: enviar el enum incompleto

`PropagationMethod` tiene **dos** miembros, `TWO_BODY` y `ZONAL_NUMERIC`. El
tercero que el roadmap pedía —propagador analítico de J2 sobre
`secular_rates_j2`— no está, y no es un olvido.

La razón está medida y ya estaba escrita en §12 de la entrada anterior: un
propagador analítico alimentado con los osculadores que devuelve `rv_to_coe`
comete un error que **crece**, ~86 km por vuelta en along-track, ~1290 km tras un
día para una SSO declarada en ν = 0. Y lo que importa no es el tamaño sino que sea
deriva: son **≈11.5 s de error de reloj orbital por vuelta, ≈2.9 minutos al día**.
Un pase dura ~10 minutos, así que en un día las ventanas de visibilidad ya están
corridas una fracción apreciable de un pase.

Las tres opciones eran:

| Opción | Qué pasa |
|---|---|
| Enviarlo documentando el error | Devuelve un array del tipo correcto con números plausibles y nada falla. **Es literalmente la degradación silenciosa que el README prohíbe** |
| Retrasar el módulo entero hasta tener Brouwer-Lyddane | Bloquea `geometry.py`, `constellations.py` y el primer enlace calculable de punta a punta, por una pieza que el modo de referencia no necesita |
| **Enviar el enum con dos miembros** | Un nombre ausente obliga a preguntar en el punto de llamada. Y el enum crece sin tocar a nadie: nadie puede depender de un miembro que nunca existió |

Se eligió la tercera, y la incompletitud está **asertada**, no confiada a que
alguien se acuerde:

- `test_the_enum_holds_exactly_the_implemented_modes` fija el conjunto de
  miembros. Añadir `J2_SECULAR_ANALYTIC` hace fallar el test, y ese fallo es el
  recordatorio de actualizar también el ADR y el docstring.
- `test_every_declared_member_actually_propagates` está **parametrizado sobre el
  enum**, así que un miembro añadido sin implementar falla al instante en vez de
  caer en una rama muerta.

### Los dos pendientes del módulo, resueltos

**Época.** Llega dentro del `TimeGrid`, que no se puede construir sin ella. Eso
convierte el defecto de SimulCTTC —`datetime.utcnow()` por defecto— en algo
irrepresentable en vez de documentado. Pero además **nada del módulo lee
`epoch_jd` numéricamente**: la física es función de segundos transcurridos, y la
fecha juliana se transporta intacta para que GMST y la geometría solar la tomen
de un solo sitio. Hay un test que aserta que dos rejillas que solo difieren en la
época devuelven estados **idénticos bit a bit** — y que avisará el día que entre
un modelo que sí dependa de tiempo absoluto.

`t_s` puede empezar donde sea, incluir el cero o no, y ser negativa: la
propagación sale de la época en las dos direcciones, que es lo que necesita una
época en mitad de la ventana (lo que da un TLE).

**Forma multi-satélite: `(S, n, 3)`, satellite-major, siempre 3-D.** La propuesta
anterior era no decidirlo en 2.1; se decide aquí porque `geometry.py` llega antes
que la etapa 3 y tendría que inventarse una forma provisional. El argumento que
desempata es de memoria, no de gusto: `traj.r_km[s]` es un bloque **contiguo**
`(n, 3)` con el tiempo primero, que es exactamente lo que ya consumen
`teme_to_itrf` y compañía; con `(n, S, 3)` la traza de un satélite es `r[:, s]`,
una vista con salto que cada llamada aguas abajo tendría que copiar. Un satélite
es `(1, n, 3)`, igual que una estación única es `(1, 3)` en `frames.py`: nadie
ramifica por forma.

### Lo que apareció al escribirlo

1. **El aplanado del modo analítico tiene una trampa que ninguna aserción de
   forma detecta.** `TWO_BODY` construye una sola pila de `S · n` juegos de
   elementos —`np.repeat` sobre los elementos, `np.tile` sobre los tiempos— y
   llama a `coe_to_rv` **una vez**. Intercambiar `repeat` y `tile` produce un
   array de la forma correcta, con los números correctos, **en las posiciones
   equivocadas**, y todas las comprobaciones de forma seguirían pasando. Lo que
   lo caza es comparar la rodaja de cada satélite contra ese satélite propagado
   solo, y así está escrito (`test_each_slice_equals_that_orbit_propagated_alone`,
   con igualdad exacta porque las dos rutas hacen la misma aritmética).
2. **Los dos modos se validan el uno al otro, en las dos direcciones.** Con todos
   los armónicos a cero son dos implementaciones independientes de la misma
   física —Kepler en forma cerrada contra DOP853— y coinciden a **13 µm sobre una
   revolución** (cota puesta en 1 mm, derivada del `atol` de 1 nm del integrador y
   sus ~250 pasos por vuelta, no ajustada). Con los armónicos puestos **tienen que
   discrepar**, y también eso se aserta contra una predicción calculada en el
   test: rotar el plano por `ΔΩ` desplaza `r·ΔΩ·sin i` = 460 km tras un día, y lo
   medido son **720 km** (1.56 veces), donde el exceso es la precesión apsidal más
   la diferencia entre el periodo kepleriano y el anomalístico.
3. **Un error de integración tenía que decir *qué* órbita.** El bucle sobre
   satélites reetiqueta `DomainError` y `ConvergenceError` con el índice: una
   constelación de sesenta no puede reportar «una órbita falló». La rama de
   `ConvergenceError` no es alcanzable físicamente —la guarda del modelo de
   fuerzas la caza antes— así que se ejercita con un stub que falla en la
   **segunda** llamada, lo que además demuestra que el índice sigue al bucle y no
   es un cero fijo. Mismo patrón que ya usaba `test_perturbations.py`.
4. **`Vec3Array` no vale para un array `(S, n, 3)`.** El alias documenta
   «`(n, 3)` con el tiempo primero», que **cada rodaja** cumple y el array apilado
   no. Los campos de `Trajectory` se anotan `FloatArray` con un comentario que lo
   dice: reclamar el alias justo donde es falso sería ponerlo mal en el sitio
   donde más se lee.

### Las decisiones, en tabla

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **Una sola función `propagate`, con `method` obligatorio y sin default** | Un default es una decisión de modelado tomada por el llamante sin que se dé cuenta. El método viaja en el resultado, y el escenario de la etapa 4 lo escribe como un campo del YAML | Alto |
| **`method` es palabra clave y hay un test sobre la firma** | La forma de la API es la salvaguarda; un refactor no puede ablandarla en silencio. Mismo movimiento que el test que aserta que `secular_rates_j2` no tiene dónde meter un J3 | Trivial |
| **La entrada son `ClassicalElements`, no un estado** | Es lo que escribe el escenario, lleva su `Frame` dentro, y es el tipo que exigirá el modo analítico cuando entre. Quien tenga un estado escribe `rv_to_coe`, exacto y greppable | Medio |
| **`tle.py` no entra por aquí** | Un TLE se propaga con SGP4, que devuelve estado en TEME. Construir un `ClassicalElements` con sus elementos medios es el error del que avisan tres documentos. Un `propagate_tle` aparte es más honesto que un miembro más del enum | Bajo |
| **Un `ZonalGravity` para los dos modos; `TWO_BODY` lee solo `mu`** | No es la sustitución silenciosa que `secular_rates_j2` rechaza: allí el nombre prometía J2 y el objeto ofrecía más, aquí `method` es obligatorio y el llamante ya declaró qué física quiere | Bajo |
| **`Trajectory` **no** guarda el modelo de gravedad** | Una trayectoria `TWO_BODY` no depende de los armónicos; guardarlos al lado afirmaría una dependencia que no existe. El modelo es del escenario, que es lo que la etapa 4 hashea | Bajo |
| **`Trajectory` no tiene `__len__`** | Tiene dos longitudes. `len(traj)` sería una moneda al aire en cada punto de llamada; hay `n_satellites` y `n_samples` | Trivial |
| **El bucle sobre satélites vive aquí** | `propagate_zonal` es de una órbita por diseño (una EDO no se difunde sobre condiciones iniciales). Esta es la capa que sabe cuántas órbitas hay, y es donde irá un pool de procesos | Bajo |
| **`DEFAULT_ZONAL_RTOL` / `DEFAULT_ZONAL_ATOL_KM` pasan a ser públicas** | `propagate` las reenvía, y una segunda copia del número en un segundo módulo es un número que se desincroniza. Los valores no cambian | Trivial |
| **Sin `DegradationLog`, otra vez** | Elegir modelo no es degradar: es lo que el llamante pidió, y queda registrado en el resultado. Regla del ADR 0002 sin excepción | — |

---

## 8. `orbits/perturbations.py` — las decisiones (→ [ADR 0004](../docs/adr/0004-zonal-perturbations.md))

**Una sola expresión de Legendre para toda la fuerza.** Derivando el potencial
zonal una vez, la regla de la cadena da una expresión válida para todo grado:

```
a_n = (mu J_n R^n / r^(n+2)) · { [(n+1)P_n(s) + s P_n'(s)] r̂ − P_n'(s) ẑ }
```

Expandida en `n = 2` es la fórmula cartesiana de J2 de siempre. La ventaja es de
superficie de error: J3 y J4 cuestan **un polinomio cada uno** en vez de tres
componentes transcritas cada uno. Nueve oportunidades de error de signo se
convierten en tres polinomios comprobables de un vistazo — y los tests comprueban
la forma general contra la cartesiana transcrita a mano, así que no se pierde la
referencia del libro.

**El integrador vive en el módulo, no en los tests.** Es el oráculo de la teoría
secular, y `tests/golden/README.md` ya cubre el caso de un oráculo V3 que no
necesita congelarse: SciPy es dependencia del núcleo, DOP853 es determinista con
su exactitud fijada por argumentos **explícitos** (`rtol`, `atol_km` son
parámetros con valores declarados, no defaults de biblioteca), y la comparación
se hace muy por encima de su propio error.

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`secular_rates_j2` no acepta un `ZonalGravity`** | Recibir un objeto con J3 y J4 y usar solo el J2 es sustituir el modelo en silencio. Como la omisión es una elección fija y no una decisión en runtime, por la regla del ADR 0002 no lleva `DegradationLog`: se resuelve en la firma. Quien tenga el objeto escribe `j2=gravity.j2`, y el cruce se encuentra con grep — igual que `km_to_m` | Bajo |
| **`ZonalGravity` lleva `mu`, radio y armónicos juntos** | Un armónico zonal no significa nada sin el radio de su expansión: cada término multiplica `(R/r)^n`. Mezclar armónicos de EGM96 con el radio de WGS-84 da un modelo que no es ninguno de los publicados. Irrepresentable en vez de documentado | Bajo |
| **Constante nueva `EGM96_RADIUS_EQUATORIAL_KM` = 6378.1363** | **No** es `WGS84_RADIUS_EQUATORIAL_KM` = 6378.137. La diferencia es 0.7 m y vale 2.2e-7 relativo en el término J2 — despreciable frente al truncamiento del modelo, y gratis de evitar. Tres radios, tres propósitos: geodesia WGS-84, gravedad EGM96, SGP4 WGS-72 | Trivial |
| **Un estado entra, una trayectoria sale** | Una EDO se integra por órbita; no hay pila de condiciones iniciales sobre la que difundir. Una constelación es un bucle, y el bucle pertenece a quien sabe paralelizarlo (`propagator.py`) | Medio |
| **La integración sale de la época en las dos direcciones** | Una época en mitad de la rejilla es lo que da un TLE. Resolverlo dentro cuesta diez líneas; dejarlo fuera cuesta una verruga en cada llamante | Bajo |
| **Rechazar posiciones dentro del radio de referencia** | La expansión armónica no converge ahí y un satélite no está ahí. Además caza el error de meter metros donde van kilómetros. La validación es **por evaluación**, no solo sobre el estado inicial: una órbita cuyo perigeo baja de la superficie solo se detecta cuando la integración llega | Bajo |
| **El detector de paso por el nodo vive en los tests** | Ahí es el mecanismo de medida, no una función pública. Sacarlo a `src/` habría hecho que el oráculo compartiera código con lo que mide | Bajo |
| **`CRITICAL_INCLINATION_RAD` como constante pública** | 63.4349°, donde `4 − 5 sin²i` se anula. Importa en dos direcciones: es donde se vuela una Molniya, y es donde una cota **relativa** sobre `argp_dot` deja de significar nada — el test de la tasa apsidal se mantiene lejos a propósito | Trivial |

### El tercer duplicado se cortó

`_as_1d` y `_as_vec3` estaban **byte a byte idénticos** en `frames.py` y
`kepler.py`. Al necesitarlos por tercera vez, se extrajeron a
`orbits/_validation.py` y los dos módulos anteriores ahora importan de ahí. Los
mensajes de error se movieron sin tocar una coma, y los 448 tests que ya existían
lo confirmaron sin cambios.

Lo que **no** se unificó: `frames._broadcast_against` y
`kepler._broadcast_to_common` difieren en forma y en lo que aconsejan sus
mensajes. Fundirlos habría dado un helper que dice menos que cualquiera de los
dos.

---

## 9. `orbits/frames.py` — las decisiones (→ [ADR 0002](../docs/adr/0002-frames-and-time-scales.md))

**Un solo marco inercial: TEME.** Es lo que devuelve SGP4, y SGP4 no es opcional.
Convertir a GCRF y volver en cada propagación añadiría error, no exactitud.

**Un solo giro, por GMST (IAU-82), hasta el marco fijo.** Estrictamente eso es PEF;
se trata como ITRF/ECEF. Presupuesto **medido**, no afirmado:

| Aproximación | Error de posición | Efecto en el enlace |
|---|---|---|
| Movimiento polar ignorado | **14.4 m** (peor medido) | ~14 µrad a 1000 km |
| UT1 ≡ UTC (\|DUT1\| ≤ 0.9 s) | ≤ 460 m (**274 m** medido) | ≤ 0.03° en elevación |
| GMST IAU-82 vs IAU-2006 | ~2 m (0.06″, 2000–2030) | despreciable |

`TestFrameErrorBudget` **descompone** el residuo en vez de esconderlo en una
tolerancia holgada: al restaurar UT1, lo que queda es exactamente el movimiento
polar que omitimos a propósito. El test no dice «se parece»: dice que el giro es
correcto. Y hay un test que propaga el peor DUT1 hasta un **ángulo de elevación**,
que es la magnitud que le importa al link budget.

`Frame` es un `StrEnum` con `TEME`/`ITRF`/`ENU`/`GCRF`. **`GCRF` se declara y no se
implementa**: es el gancho para que, si algún día entra la reducción completa,
todo array venga ya etiquetado y los puntos de conversión se encuentren con grep.

### La regla de firma para toda la etapa 2 (era decisión diferida)

> **Una función de física recibe un `DegradationLog` solo si puede decidir en
> tiempo de ejecución calcular algo distinto de lo que su nombre promete.**

Ninguna función de `frames.py` lo recibe: sus tres aproximaciones son elecciones
de modelo fijas para todo el run, y registrarlas por llamada emitiría una entrada
por muestra temporal. Entrada mala = **error** (`DomainError`), no degradación.

### Otras decisiones

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **Geodésico siempre, WGS-84** | Es el bug de SimulCTTC. Hay tests que fijan numéricamente la diferencia geodésica/geocéntrica (0.1924° a 45°) y el error esférico en el polo (−21.385 km), para que nadie la reintroduzca por simplicidad aparente | Alto |
| **GMST en segundos de tiempo, no grados** | Una vuelta completa son exactamente `SECONDS_PER_DAY` segundos de tiempo, así que pasar a radianes es contar vueltas, no convertir grados. Respeta el guarda de `deg2rad` del ADR 0001 y usa la misma formulación que `erfa.gmst82` | Trivial |
| **`enu_from_itrf` toma un *vector*, no una posición** | Obliga a que la resta `r_sat − r_estación` quede en el llamante. Rotar una posición como si fuera un offset topocéntrico es un error silencioso | Bajo |
| **Iteración de punto fijo para geodésico, no forma cerrada** | Vermeille/Heikkinen son exactas pero fáciles de transcribir mal. La iteración converge en 7 pasadas a 1e-14, es trivialmente vectorizable, y su corrección es evidente | Trivial |
| **`_as_1d` / `_as_vec3` validan en cada función pública** | Una función que confía en sus entradas empuja el error a donde aparece el `nan`, que nunca es donde se cometió | Bajo |
| **Escalares admitidos para lat/lon de estación** | Una estación es un *parámetro*, no una serie temporal. Los arrays de tiempo sí exigen forma `(n, 3)` | Bajo |
| **Salida siempre 2-D `(n, 3)`** | Un sitio único es `(1, 3)`, así ningún llamante ramifica por forma | Bajo |
| **Tolerancias derivadas, no ajustadas** | P. ej. el jitter admitido en el paso de GMST se calcula de `np.spacing(JD_J2000)`, no de lo que el código da hoy. Una tolerancia ajustada al resultado actual no puede fallar nunca | Alto (es el valor de la suite) |

---

## 10. `orbits/kepler.py` — las decisiones (→ [ADR 0003](../docs/adr/0003-orbital-elements.md))

**Solo órbitas elípticas, `0 ≤ e < 1`.** La formulación por variables universales
cubriría las cuatro cónicas, pero **nada en este proyecto la validaría**: no hay
un caso de prueba hiperbólico con significado físico en un simulador de
satélites. Código no ejercitado es código que no funciona.

**Kepler en forma cerrada, sin bucle.** Markley 1995. Residuo medido ≤ 1.4e-15
rad sobre 20 001 puntos por excentricidad, para toda `e` hasta 0.9999, y el mismo
coste para una órbita circular que para `e = 0.99` — lo que importa dentro de un
barrido. Aun así la función **comprueba su propio residuo** en cada llamada: no
es un criterio de convergencia sino una post-condición, y hay un test que la
ejerce apretando el umbral por debajo del suelo de máquina, para que la rama
exista de verdad.

El matiz que hay que decir en voz alta: el residuo es absoluto en anomalía
*media*, y `dM/dE = 1 − e·cos E`. Cerca del periapsis de una órbita muy
excéntrica esa derivada se hunde, así que el error en `E` es el residuo dividido
por `1 − e` (≈1e-11 rad a `e = 0.9999`). A las excentricidades de LEO es 1e-15.

**Los ángulos indefinidos se pliegan, no se anulan.** Una órbita circular no
tiene ω; una ecuatorial no tiene Ω. Las dos ocurren en escenarios reales y las
dos hacen que la fórmula clásica divida por cero. En vez de devolver `nan` —que
viaja hasta la primera figura y allí ya nadie sabe de dónde salió— el ángulo
indefinido se mete en el siguiente que sí lo está, y el pliegue se reporta con
`is_circular` / `is_equatorial`.

El pliegue es **sin pérdida para el estado**: en la posición y la velocidad solo
entran sumas como `ω + ν`, así que `coe_to_rv` reconstruye los vectores exactos
en los cuatro casos degenerados — verificado a 15 nm sobre una pila que los
mezcla con órbitas ordinarias, que es lo que ejercita las máscaras vectorizadas.

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`p` como elemento primario, `a` derivado** | Sale directo de `h²/µ` sin pasar por la energía; es lo que recibe el Algorithm 10, que es el caso publicado que valida el módulo; y se mantiene finito si algún día entra `e → 1` | Bajo |
| **Umbral de degeneración 1e-11, no el 1e-8 habitual** | Medido: el suelo de ruido del vector excentricidad es 3e-16, así que a `e = 1e-11` la dirección del periapsis tiene 3e-5 rad de incertidumbre. Con 1e-8 se plegaría una LEO «circular» real (`e ~ 1e-4…1e-6`) perdiendo un ω perfectamente medible. Hay un test que fija ese caso | Bajo |
| **Las anomalías conservan las vueltas; `rv_to_coe` envuelve** | Si `E(M + 2πk)` devolviera `E(M)`, una serie propagada sería un diente de sierra y cualquier interpolación que cruzara una vuelta daría un valor sin sentido. `rv_to_coe` no tiene historia que conservar: recibe un estado, no una trayectoria | Bajo |
| **`arctan2` sobre seno y coseno explícitos, no `arccos` + cuadrante** | `arccos` pierde la mitad de sus cifras cuando su argumento se acerca a ±1 — justo donde está una órbita casi ecuatorial o casi circular, las que hay que tratar bien. El seno sale de un producto triple contra el momento angular, que además fija el cuadrante sin rama aparte | Medio |
| **`Frame` viaja en los elementos; ITRF y ENU se rechazan** | Unos elementos referidos a un marco que rota no son unos elementos. Irrepresentable en vez de documentado, como el enum del ADR 0002 un nivel más arriba | Bajo |
| **`ClassicalElements` no es un `dataclass`** | Un `__init__` generado declara **un** tipo por campo, y aquí los dos papeles difieren: se acepta `float \| FloatArray` para que un escenario se lea como un escenario, y se almacena siempre `FloatArray`. Anotar la unión empuja una rama a cada consumidor para un caso que ya no puede existir — la erosión del contrato de arrays contra la que avisa `core/types.py`. Escrita a mano: permisiva al entrar, estricta al salir | Medio |
| **Sin `DegradationLog`, otra vez** | El plegado no es una degradación: el estado que produce es exacto. Se aplica la regla del ADR 0002 sin excepción | — |

### El oráculo V3, y por qué este no se congela

`perturbations.py` iba a ser la referencia independiente de este módulo, pero
llega después. Mientras tanto la hace **SciPy**: `DOP853` integrando
`r'' = −µ·r/|r|³` no se parece en nada a la ecuación de Kepler ni a la base
perifocal, y cierra la cadena entera de una vez —`rv_to_coe → advance_mean_anomaly
→ true_from_mean_anomaly → coe_to_rv`— que ningún test de función suelta puede
hacer. Cinco regímenes parametrizados (LEO, SSO, tipo Molniya, GEO, retrógrada)
más un puñado de órbitas aleatorias, una revolución completa, a 1 m y 1 mm/s.

**No se congela a fichero**, y la regla que lo justifica está ahora escrita en
`tests/golden/README.md`: SciPy ya es dependencia del núcleo, el integrador es
determinista con su exactitud fijada por un argumento explícito, y se compara
tres órdenes de magnitud por encima de su propio error. Lo que un fichero
congelado protege —una referencia que cambia sin avisar— no aplica.

---

## 11. Archivos

| Archivo | Qué es |
|---|---|
| `src/quoss/orbits/__init__.py` | Docstring. Sin re-exports, como `core/` |
| `src/quoss/orbits/frames.py` | 11 funciones públicas + `Frame`. Tiempo, TEME↔ITRF (posición y estado), geodésico↔ITRF, ENU |
| `src/quoss/orbits/kepler.py` | 12 funciones públicas + `ClassicalElements` y **`ElementType`**. Anomalías, ecuación de Kepler, tamaño/periodo, elementos↔estado |
| `src/quoss/orbits/perturbations.py` | 5 funciones públicas + `ZonalGravity`, `SecularRates`, `CRITICAL_INCLINATION_RAD` y los presets `EGM96_ZONAL`/`WGS72_ZONAL`. Fuerza zonal J2/J3/J4, tasas seculares de J2, integrador DOP853 |
| `src/quoss/orbits/_validation.py` | `as_1d` y `as_vec3`, que estaban duplicados byte a byte en `frames.py` y `kepler.py` |
| `docs/adr/0002-frames-and-time-scales.md` | El ADR de marcos y escalas de tiempo |
| `docs/adr/0003-orbital-elements.md` | El ADR de elementos, anomalías y casos degenerados |
| `docs/adr/0004-zonal-perturbations.md` | El ADR de gravedad zonal y teoría secular: por qué la fuerza es exacta y la teoría solo de primer orden |
| `src/quoss/orbits/propagator.py` | **Nuevo.** 1 función pública + `PropagationMethod` y `Trajectory`. Elementos en una época → estados en una rejilla, con el método como parámetro obligatorio |
| `docs/adr/0005-propagation.md` | **Nuevo.** El ADR de propagación: un punto de entrada, un enum obligatorio, y por qué el enum se envía incompleto |
| `docs/adr/0006-osculating-vs-mean-elements.md` | **Nuevo.** El ADR de la bandera osculador/medio: qué son las dos elipses, la tabla de km, y las tres subdecisiones con sus alternativas descartadas |
| `tests/orbits/test_propagator.py` | 43 tests (+3 doctests en el módulo): los dos modos validándose entre sí en las dos direcciones, la rodaja por satélite contra la propagación individual, la época que se transporta y no se lee, el conjunto de miembros del enum, y que **todos** los modos rechazan elementos medios |
| `tests/orbits/test_frames.py` | 85 tests: V2 por definición, V1 invariantes/property-based, V3 contra referencia, y `TestFrameErrorBudget` |
| `tests/orbits/test_kepler.py` | 119 tests (+16 doctests en el módulo, que ejecuta `--doctest-modules`): **V2 Vallado 2-1/2-5/2-6**, V1 invariantes y casos degenerados, V3 contra la integración numérica, y `TestTheElementTypeFlag` (la bandera osculador/medio) |
| `CLAUDE.md` | Único sistema de metadatos de agentes del repo (guía §5 pide uno, no cuatro). La norma de explicación —desde cero, defendida, con ejemplo numérico— y el contexto mínimo antes de tocar nada |
| `tests/orbits/test_perturbations.py` | 69 tests (+6 doctests en el módulo): gradiente numérico del potencial, forma cartesiana transcrita, V3 contra DOP853 con el escalado en J2, J3 sin término secular, la SSO de Landsat-8, y `TestTheElementTypeGate` |
| `tests/golden/README.md` | Los cuatro niveles, las reglas de un fichero de referencia, y los huecos declarados |
| `tests/golden/generators/gen_frames_reference.py` | El generador. No importa `quoss` |
| `tests/golden/data/frames_reference.json` | Datos congelados con manifest (astropy 8.0.1, pyerfa 2.0.1.5) |

Modificados en esta entrada (la bandera osculador/medio):

- `src/quoss/orbits/kepler.py` — **`ElementType`** (`StrEnum`, dos miembros) y el
  campo `element_type` en `ClassicalElements`, con su propiedad, su hueco en
  `__slots__`, su sitio en el `__repr__` y el reenvío en `from_semi_major_axis`.
  Más el método **`relabelled_as`** y la guarda de `coe_to_rv`. `rv_to_coe` pone
  la etiqueta explícitamente en vez de dejarla al defecto, para que el único
  sitio que la acuña sea greppable.
- `src/quoss/orbits/perturbations.py` — `secular_rates_j2` exige
  `MEAN_BROUWER`. Su sección «Mean elements versus osculating elements» decía que
  la función «no pregunta de qué tipo son porque no puede saberlo»: ya puede, y
  el docstring ahora dice lo contrario del que había.
- `src/quoss/orbits/propagator.py` — el aplanado de `TWO_BODY` **reenvía**
  `element_type` a la pila `(S · n)`. Es un cambio de una línea y es el que evita
  que ese modo blanquee unos elementos medios (§6).
- `tests/orbits/test_kepler.py` — `TestTheElementTypeFlag`, 11 tests: el conjunto
  exacto de miembros y la ausencia de `MEAN`, el defecto, que `rv_to_coe` acuña
  osculadores, las dos guardas, que el mensaje nombra Brouwer-Lyddane, y que
  `relabelled_as` no toca un número.
- `tests/orbits/test_perturbations.py` — `TestTheElementTypeGate`, 5 tests, y la
  helper `_mean_elements` frente a `.relabelled_as(...)`: la primera para los
  tests que **son** sobre elementos medios, la segunda para los que mienten a
  propósito. `test_secular_rates_does_not_accept_a_j3_at_all` se acompaña ahora de
  su gemelo sobre la bandera: la firma no tiene dónde meter un `assume_mean`.
- `tests/orbits/test_propagator.py` — `test_every_mode_refuses_mean_elements`,
  parametrizado sobre el enum, más el `relabelled_as` en el test del día de J2,
  que necesita la tasa secular solo para predecir un orden de magnitud.
- `docs/adr/0006-osculating-vs-mean-elements.md` — **nuevo**. Las tres
  subdecisiones, con la tabla de km y las alternativas descartadas.
- `docs/adr/0003-orbital-elements.md`, `docs/adr/0005-propagation.md` — punteros
  al 0006; en el 0005, el «no cierra» de la bandera pasa a cerrado.
- `notes/ROADMAP.md`, `README.md` — el estado de 2.1 incluye la bandera.

Modificados en la entrada anterior (`propagator.py`):

- `src/quoss/orbits/perturbations.py` — `_DEFAULT_RTOL` y `_DEFAULT_ATOL_KM`
  pasan a ser **públicas**, `DEFAULT_ZONAL_RTOL` y `DEFAULT_ZONAL_ATOL_KM`,
  porque `propagate` las reenvía y una segunda copia del número en otro módulo se
  desincroniza. Los valores no cambian y ningún test existente se tocó.
- `notes/ROADMAP.md` — 2.1.4 hecho, con la nota de por qué el enum va incompleto.
- `README.md` — el estado pasa a «hecho `propagator.py`, siguiente `tle.py`».

Modificados en la entrada anterior (`perturbations.py`):

- `src/quoss/core/constants.py` — **constante nueva** `EGM96_RADIUS_EQUATORIAL_KM`
  (6378.1363 km), con dos tests: que los tres radios de referencia son tres
  números distintos, y que EGM96 y WGS-84 distan 0.7 m.
- `src/quoss/orbits/frames.py`, `src/quoss/orbits/kepler.py` — pierden sus copias
  de `as_1d`/`as_vec3` e importan de `_validation.py`. Cambio mecánico: los
  mensajes de error se movieron sin tocar una coma, y los 448 tests existentes lo
  confirmaron sin ninguna modificación.
- `tests/orbits/test_kepler.py` — `test_argument_of_latitude_errata` reforzado
  (§4), y un docstring que afirmaba algo falso, corregido. Después, **dos tests
  nuevos** (§4, final): `test_argument_of_latitude_property_carries_the_v2_value`
  ata el dato V2 de `u` a la propiedad que lo implementa, y
  `test_argument_of_latitude_wraps_past_one_turn` ejercita el envuelto, que el
  ejemplo de Vallado no puede alcanzar. El docstring de `VALLADO_2_5_EXPECTED`
  apunta ahora a los dos tests y dice cuál hace qué.
- `tests/golden/README.md` — el hueco de GMAT/Orekit para las tasas seculares de
  J2 se cierra por otra vía, y se explica por qué el oráculo interno prueba más
  que una tabla congelada.
- `README.md` — dos afirmaciones caducadas: decía «Etapa 0, todavía no hay
  física» y, en Principios, «SimulCTTC es el **oráculo**», que es exactamente lo
  contrario de lo que se decidió en la etapa 2.1 (§2).
- `notes/ROADMAP.md` — 2.1.3 hecho, con la corrección de lo que el propio
  roadmap afirmaba sobre validar a O(J2²).

Sin cambios en `pyproject.toml` ni en `uv.lock`.

---

## 12. Entorno

**Sin cambios en esta entrada.** `propagator.py` no añade ninguna dependencia:
solo importa de `core/`, `kepler.py` y `perturbations.py`. Tampoco la anterior:
`perturbations.py` usa `numpy` para la fuerza y `scipy.integrate.solve_ivp` para
el integrador, que ya estaba en el núcleo. El grupo `reference` sigue sin
instalarse en CI y ningún módulo de `orbits/` lo necesita.

Del cambio anterior, sin novedad: nuevo grupo **no** por defecto: `reference` con
`astropy>=6.0` (resuelve astropy 8.0.1 + astropy-iers-data + pyerfa). CI **no** lo
instala. Ejecutar un generador:

```bash
uv run --group reference python tests/golden/generators/gen_frames_reference.py
```

---

## 13. Cosas a considerar

### Para el siguiente módulo (`tle.py`)

- **No entra por `propagate`, y eso ya está decidido en el ADR 0005.** Un TLE se
  propaga con SGP4, que devuelve estado en TEME —osculador— así que el camino
  TLE → posición no pasa por ninguna pieza nuestra. Lo que `tle.py` necesita no
  es una transformación, es la disciplina de **no construir un
  `ClassicalElements`** con los elementos medios de un TLE. Un `propagate_tle`
  con su propia firma es más honesto que un miembro más de `PropagationMethod`:
  el enum es «qué modelo corre sobre unos elementos», y un TLE no es unos
  elementos nuestros.
- **Y aun así hay que decidir qué devuelve.** Lo natural es el mismo
  `Trajectory`, con `frame=Frame.TEME` y la época del TLE como `epoch_jd` de la
  rejilla; así `geometry.py` no distingue de dónde salió una traza. Falta
  comprobar que la rejilla que SGP4 quiere (fechas absolutas, JD) y la que
  `TimeGrid` da (época + segundos) se convierten sin perder precisión: `float64`
  guarda un JD a ~20 µs, y SGP4 acepta el par `(jd, fr)` justo para eso.
- **Reutilizar el detector de paso por el nodo.** Vive en
  `tests/orbits/test_perturbations.py` como mecanismo de medida. `system/passes.py`
  va a querer algo muy parecido; cuando llegue, la pregunta es si sube a `src/`
  o si `passes.py` necesita otra cosa (allí el evento es la elevación, no `z = 0`).

### El desajuste medio↔osculador, medido — y por qué el enum va incompleto

Sigue vigente y ahora es la razón documentada de que `J2_SECULAR_ANALYTIC` no
exista (§7). Se conserva aquí porque es la medición, no la conclusión.

- **El asunto medio↔osculador, medido en
  kilómetros.** Un propagador analítico que reciba los osculadores de
  `rv_to_coe` y aplique tasas seculares comete un error O(J2) desde el primer
  paso. Hasta ahora eso estaba dicho como «1e-3 relativo», que es un número que
  no le dice nada a nadie. Medido contra `propagate_zonal` (J2 solo en los dos
  lados, así que la diferencia es *solo* el desajuste, no física distinta),
  descomponiendo el error en radial / along-track (a lo largo del movimiento) /
  cross-track (perpendicular al plano):

  > **Esta tabla estaba equivocada y se corrigió el 2026-08-04 (§14.1).** Se
  > conserva aquí solo el texto corregido; los valores originales —14.6 / 219 /
  > 144 / 224 / 66 km, con radiales de 5–13 km— nunca se reprodujeron, y al
  > escribirles por fin un test resultaron 5.9 veces menores que la medición. Los
  > radiales citados eran además geometría de la cuerda, no error radial.

  | Órbita (elementos en ν = 0) | 1 vuelta | 15 vueltas (~1 día) | radial (1 vuelta) | cross-track (1 vuelta) |
  |---|---|---|---|---|
  | SSO 700 km, i = 98.2° | 86.3 km | **1293 km** | 0.53 km | 0.03 km |
  | ISS-like, i = 51.6° | 56.4 km | **845 km** | 0.23 km | 0.07 km |
  | LEO polar, i = 90° | 88.1 km | **1319 km** | 0.55 km | ~0 |
  | LEO baja i, i = 28.5° | 20.3 km | **305 km** | 0.03 km | 0.01 km |

  Control del instrumento: con `j2 = 0` en los dos lados, el camino analítico es
  dos cuerpos exacto y el residuo cae a **0.083 mm** sobre 15 vueltas. Así que la
  tabla es física, no un fallo de la comparación — y ese control es lo único de la
  medición original que sí se reprodujo.

  **Lo que hay que leer en esa tabla no es el tamaño, es que crece.** El error
  radial y el cross-track se quedan quietos (0.5 km y 0.03 km tras una vuelta): son
  el bamboleo de período corto, que oscila y no acumula. El along-track **crece
  linealmente**, ~86 km por vuelta. La razón: la propiedad `a` (semieje) de un
  juego osculador difiere de la del medio en O(J2), y el movimiento medio va como
  `a^(-3/2)`, así que un error O(J2) en `a` es un error O(J2) en la *velocidad
  angular*, y eso integra — cuantitativamente, `3π·δa` por vuelta, que predice las
  cuatro filas a mejor del 2 % (§14.1). En unidades útiles: **≈11.5 s de error de
  reloj por vuelta, ≈2.9 minutos al día**.

  Y eso es lo que decide el diseño, ahora con más fuerza que cuando se escribió:
  minutos al día de deriva en el reloj orbital no es un detalle de precisión, un
  pase dura ~10 minutos. Y el tamaño depende de en qué punto de la órbita se
  declaren los elementos —factor 1100 entre ν = 0° y ν = 45° (§14.1)— así que no hay
  una cifra que documentar. El camino analítico
  **no puede devolver un estado utilizable sin la parte de período corto de
  Brouwer-Lyddane**, y por tanto BL no es solo la llave del segundo orden
  secular (§5): es requisito del propio modo analítico.

  **Resuelto en esta entrada** (§7), y de la única forma que no miente: el modo
  analítico no se envía. La tabla de arriba es lo que se lee en su lugar cuando
  alguien pregunte por qué falta.

### La bandera osculador/medio: las tres subdecisiones, resueltas

Estaban abiertas y bloqueaban escribirla. **Cerradas en esta entrada** (§6 y
[ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md)); se resumen aquí
porque este es el sitio donde alguien las buscará:

1. **`coe_to_rv` con elementos medios → `DomainError`.** Se confirma la propuesta,
   y por la razón que la motivaba: los kilómetros se pierden en esa dirección, no
   en la de `secular_rates_j2`. Un matiz que la propuesta daba por hecho y que **no
   se cumplió**: decía «quien quiera un estado desde elementos medios pasa primero
   por `mean_to_osculating`», y esa función **no existe** ni se ha creado — sería
   Brouwer-Lyddane. El mensaje de error nombra la transformación que falta en vez
   de una función que el lector iría a buscar y no encontraría.

2. **Dos valores: `OSCULATING` y `MEAN_BROUWER`.** El nombre es lo que resuelve la
   tensión: el riesgo de quedarse en dos era que añadir un tercero después tocara
   a todos los llamantes, y nadie puede escribir `MEAN`, así que no toca a nadie.
   El riesgo de un `MEAN` genérico —hacer pasar por intercambiables Brouwer-Lyddane
   /EGM96 y Brouwer-Kozai/WGS-72— desaparece por la misma vía.

3. **`relabelled_as`, tal como se propuso**, con el docstring que dice que no
   convierte nada, y con `assume_mean=True` descartado por escrito y con un test
   que aserta que la firma de `secular_rates_j2` no tiene dónde meterlo.

### El acoplamiento BL ↔ `tle.py` que el roadmap afirma está sobredimensionado

El roadmap y §13 dicen tres veces que Brouwer-Lyddane es «la misma pieza en dos
sitios: la que `tle.py` necesita para leer bien un TLE y la que desbloquea el
segundo orden secular». La segunda mitad es cierta. **La primera, revisada, no lo
parece**, y conviene corregirlo antes de planificar en base a ella:

Un TLE se lee con SGP4, y el plan (roadmap 2.1.5) es usar el paquete `sgp4`, no
reimplementarlo. `Satrec.sgp4_array` recibe fechas y devuelve **posición y
velocidad en TEME** — es decir, un estado osculador. SGP4 ya hace por dentro toda
la transformación de elementos medios a estado, incluidos los términos de período
corto. Así que el camino TLE → posición **no pasa por ninguna pieza nuestra de
BL**. Si además se quieren elementos, `rv_to_coe` sobre ese estado da osculadores
correctos.

Dónde sí haría falta algo parecido a BL con TLEs: para ir en la dirección
contraria (estado → TLE, que QuOSS no necesita), o para interpretar los elementos
medios del TLE directamente como una órbita. Y para eso **BL genérico tampoco
sirve**: harían falta las convenciones concretas de SGP4 (Kozai, WGS-72), que son
otra pieza. Ver el punto 2 de arriba.

Consecuencia práctica: BL se justifica **por el modo analítico de `propagator.py`
y por el segundo orden secular**, no por `tle.py`. Lo que `tle.py` necesita no es
una transformación, es la disciplina de no construir un `ClassicalElements` con
los elementos medios de un TLE — que es lo que la bandera hace cumplir.

### Lo que queda abierto de este módulo

- **Términos seculares de segundo orden** (`J2²`, `J4`). Falta el oráculo, no las
  ganas: ver §5. La condición de entrada está escrita — una transformación
  osculador↔medio (Brouwer-Lyddane).
- **El V2 de Vallado §9.6 sigue sin transcribir.** Era el plan y no se ha hecho:
  la entrada anterior anotaba «ahí es donde se cierra el V2 de J2». Lo que hay
  hoy es V3 (integración numérica) más un ancla de misión publicada (Landsat-8).
  Transcribir los ejemplos del libro seguiría aportando, y con la misma disciplina
  de siempre: entradas y salidas por separado, y asertar las etapas intermedias.
  **Ojo**: los ejemplos de §9.6 casi con seguridad usan elementos medios, así que
  lo primero a comprobar al transcribirlos es cuál de los dos tipos imprime.
- **La suite pasa de 4.9 s a ~26 s**, todo en integraciones. Si molesta, el sitio
  donde recortar es el número de revoluciones, no las tolerancias.

### Decidido en esta etapa, aplica a toda la 2

- **Orden de 2.1 revisado**: `frames` primero (era la duda de la etapa 1).
- **Regla de firma de física** (arriba). Era decisión diferida a la etapa 2.
- **Protocolo de verificación V1–V4.** Era el bloqueante de la etapa 2.
- **Marcos y escalas de tiempo** → ADR 0002.
- **Elementos, anomalías y casos degenerados** → ADR 0003. En particular: `p`
  como elemento de tamaño, el pliegue de ángulos indefinidos, y que un
  `ClassicalElements` lleva su `Frame` y rechaza los que rotan.
- **Cuándo un oráculo V3 no necesita congelarse** → `tests/golden/README.md`.
  Tres condiciones: dependencia del núcleo, determinista con tolerancia
  explícita, y comparado muy por encima de su propio error.
- **Gravedad zonal y teoría secular** → ADR 0004. En particular: una sola
  expresión de Legendre para toda la fuerza, la teoría secular solo a primer
  orden en J2 con su razón medida, y que un modelo de gravedad viaja como un
  objeto con su radio de referencia dentro.
- **Propagación** → ADR 0005. En particular: un solo punto de entrada con el
  método obligatorio y sin default, la época dentro del `TimeGrid`, la forma
  `(S, n, 3)` satellite-major, y que **un enum se envía incompleto antes que con
  un miembro roto**.
- **La bandera osculador/medio** → ADR 0006. En particular: que la etiqueta viaja
  dentro de los elementos como el `Frame`, que se comprueba en las **dos**
  direcciones porque los kilómetros se pierden en la que no parecía, que un
  miembro de enum se nombra por su teoría (`MEAN_BROUWER`) y no por su categoría
  (`MEAN`), y que la vía para saltarse una comprobación a propósito vive en el
  contenedor y se llama como lo que hace.
- **Cómo se envía un módulo con un modo que falta.** Generalizable, y es la
  aportación de esta entrada: un nombre **ausente** obliga a preguntar en el
  punto de llamada; uno presente y silenciosamente equivocado no obliga a nada.
  La incompletitud se aserta con dos tests —el conjunto de miembros, y un test
  parametrizado sobre el enum— para que ni quedarse corto ni añadir un miembro a
  medias pasen desapercibidos. Aplicable a cualquier registro que crezca por
  etapas: los protocolos de `qkd/base.py`, los perfiles de `channel/atmosphere.py`.
- **Cómo se valida una teoría truncada.** Generalizable, y es la aportación
  metodológica de la entrada anterior: no basta con acotar el residuo, hay que
  **atribuirlo** — escalar el parámetro pequeño y comprobar que el error relativo
  escala con él. Una cota dice «se parece»; el escalado dice «lo que sobra es el
  término que decidí no calcular». Aplicable a cualquier expansión que venga
  después (Rytov débil vs fuerte, decoy asintótico vs finite-key).

### Pendiente de decidir, con fecha

| Cuándo | Qué |
|---|---|
| ~~`perturbations.py`~~ | ~~Confirmar el integrador zonal numérico como referencia interna~~ **Hecho**: `propagate_zonal` con `rtol`/`atol` explícitos, y es el oráculo de las tasas seculares |
| ~~`propagator.py`~~ | ~~Analítico o numérico como elección explícita~~ **Hecho (2026-08-01)**: una función `propagate` con `PropagationMethod` obligatorio, palabra clave y sin default, que viaja en el `Trajectory`. Con el modo analítico **declarado ausente** en vez de enviado roto (§7, ADR 0005) |
| ~~`propagator.py`~~ | ~~Qué hacer con el desajuste medio↔osculador~~ **Hecho (2026-08-01)**: `ElementType` dentro de `ClassicalElements`, igual que el `Frame`. `rv_to_coe` marca osculador; `coe_to_rv` exige osculador y `secular_rates_j2` exige medio, los dos con `DomainError`; `relabelled_as` para reetiquetar sin convertir. Las tres subdecisiones que bloqueaban escribirla, resueltas en §6 y en el [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md). **La conversión Brouwer-Lyddane sigue sin existir**, y por eso la bandera es hoy una puerta cerrada: ver la fila de más abajo, que es la que queda viva |
| ~~`propagator.py`~~ | ~~**Forma de arrays multi-satélite**: `(n, S, 3)` vs `(S, n, 3)`~~ **Hecho (2026-08-01)**: `(S, n, 3)`, satellite-major, siempre 3-D. Se adelanta a la etapa 3 porque `geometry.py` llega antes y tendría que inventarse una forma provisional. Desempata la memoria: `traj.r_km[s]` es contiguo y entra tal cual en `teme_to_itrf`; `r[:, s]` habría que copiarlo en cada llamada |
| ~~`propagator.py`~~ | ~~**Época**: de dónde sale y si es obligatoria~~ **Hecho (2026-08-01)**: llega dentro del `TimeGrid`, que no se puede construir sin ella, y **no se lee numéricamente** — hay un test que aserta que dos rejillas que solo difieren en `epoch_jd` dan estados idénticos bit a bit |
| `propagator.py` / `engine/` | **Paralelismo del bucle sobre satélites.** Hoy `ZONAL_NUMERIC` integra las S órbitas en serie. Es el sitio evidente para un pool de procesos, pero pertenece a `engine/parallel.py` (etapa 5), no a la capa de física. Medir antes: para una constelación de 60 y un día de rejilla, ¿cuánto tarda? |
| `system/passes.py` | **Refinado de rejilla alrededor de un pase.** Un `Trajectory` da muestras en la rejilla que se le pidió y nada más — no interpola. Quien quiera resolución fina solo en los pases, o pide una rejilla no uniforme (que `TimeGrid` admite) o propaga dos veces. Decidir cuál cuando `passes.py` sepa qué necesita |
| `tle.py` | **No construir un `ClassicalElements` con elementos medios de un TLE.** Son de Brouwer-Lyddane con corrección de Kozai, no los osculadores de `kepler.py`; y van con `WGS72_MU_KM3_S2`, no con EGM96. Ahora hay además `WGS72_ZONAL`, que es el juego consistente a usar. **Sigue siendo disciplina, no un tipo**: la bandera impide *usar* unos medios donde van osculadores, pero nadie impide etiquetar unos medios de TLE como `OSCULATING` a mano. Si `tle.py` acaba necesitando construirlos, ahí es cuando entra `MEAN_KOZAI_SGP4` (ADR 0006, subdecisión 2) |
| `propagator.py` (adelantado desde `tle.py`) | **Transformación osculador↔medio (Brouwer-Lyddane).** Se adelanta porque el modo analítico no puede devolver un estado utilizable sin ella (§13, tabla de km). Sigue desbloqueando los términos seculares de segundo orden (§5). **Corregido:** que fuera «la misma pieza que `tle.py` necesita» está sobredimensionado — ver «El acoplamiento BL ↔ `tle.py`» arriba. **Es lo único que queda vivo de la bandera**: `ElementType` ya está (§6) y marca exactamente los dos puntos donde esta función se llamaría. Pendiente: elegir alcance (solo período corto, o corto + largo) y oráculo de validación |
| `tle.py` | Añadir `sgp4` a dependencias **del núcleo** (no un extra). Verificar que la extensión C++ compila: `Satrec.sgp4_array` solo es vectorizada de verdad si lo hace, y no hay que fingir vectorización si cae al fallback Python |
| `geometry.py` | **Refracción atmosférica: ¿dentro o fuera?** Propuesta: `geometry.py` devuelve elevación **geométrica sin refractar** (explícito en el nombre) y la corrección vive en `channel/atmosphere.py`, junto al airmass que la necesita. A 10° la refracción son ~5′ y **sí** cambia el airmass |
| `geometry.py` | **Convención de Doppler**: signo (positivo = alejándose) y qué se devuelve (km/s, Hz para una λ, o factor). `v/c ≈ 2.5e-5` ⇒ primer orden clásico basta, pero hay que escribirlo |
| Etapa 4 | Formato del resultado: `xarray.Dataset` vs Parquet + manifest |
| Etapa 4 | El escenario escribe `a`, `e`, `i`, `Ω`, `ω`, `ν` en grados y entra por `ClassicalElements.from_semi_major_axis`, con la conversión en `scenario/io.py`. Decidido de hecho por el ADR 0003; falta escribirlo en el esquema |
| Si entra un optimizador | **Elementos equinocciales.** Son la respuesta estructural a la degeneración (seis parámetros sin singularidad). Hoy el pliegue resuelve el problema real —que el estado sobreviva— sin mantener una segunda representación. El sitio donde volver es un optimizador de constelaciones que derive respecto a los elementos |
| Etapa 7 | Añadir `[project.scripts] quoss = "quoss.cli.main:main"` |
| Etapa 8 | Reactivar `warn_unused_configs = true` en mypy |
| Etapa 8 | ¿Reducción completa GCRF ↔ ITRF? El enum ya deja la puerta abierta; hoy no cambia ningún número publicable |
| Etapa 8 | **Transcribir Vallado §9.6** (tasas seculares) como V2, comprobando primero si el libro imprime elementos medios u osculadores |
| Cuando duela | **Coste de la suite**: ~26 s, casi todo integraciones DOP853 de `test_perturbations.py`. Recortar revoluciones antes que tolerancias |

### Deuda pequeña (heredada, sigue viva)

> Auditoría del **2026-08-04**: seis inconsistencias entre lo que el código o los
> documentos afirman y lo que se cumple —ninguna la detectaba la suite— más el
> hueco de que **219 km era un número sin test**. **Las siete están cerradas el
> mismo día**; ver §14, y [`INCONSISTENCIAS.md`](INCONSISTENCIAS.md), que se queda
> sin entradas abiertas. Las tres primeras (marco como cadena, «Immutable» que no
> lo era, aliasing de `relabelled_as`) eran **preexistentes**, no de la bandera.

- **`--all-extras` en CI arrastra `numba`.** Sigue pendiente. Nota: el grupo
  `reference` **no** se ve afectado, porque los grupos PEP 735 no por defecto no
  los instala `uv sync --all-extras`.
- **Suelo `numpy>=1.26` no está testeado.** Igual que antes.
- **`filterwarnings = ["error"]`**: al entrar `sgp4` habrá que añadir excepciones
  **por warning concreto**. Ya hay un precedente cercano: el generador de
  referencia provoca `ErfaWarning` («dubious year») para 1900 y 2100, y eso vive
  fuera de pytest precisamente porque el generador está excluido de la recolección.
- **`TimeSeries` no es el esquema del resultado.** Sin cambios; decisión de etapa 4.
  Ni `frames.py`, ni `kepler.py`, ni `perturbations.py` lo usan: devuelven arrays
  desnudos, porque ni un marco, ni un juego de elementos, ni un campo de fuerzas
  son una serie temporal. `propagate_zonal` es el primero que devuelve algo que
  *casi* lo es —una trayectoria sobre una rejilla de tiempos— y aun así toma
  segundos transcurridos, no un `TimeGrid`: quien tiene época es `propagator.py`.
- **`_broadcast_against` y `_broadcast_to_common` siguen duplicados a medias.**
  A diferencia de `as_1d`/`as_vec3`, estos dos **difieren** en forma y en lo que
  aconsejan sus mensajes, así que no se unificaron. Si aparece un tercero,
  reconsiderarlo.
- **La ecuación de Kepler cerca de `e = 1`.** Funciona, pero la precisión en `E`
  se degrada como `1/(1−e)`. Documentado, no corregido: no hay escenario QuOSS
  que llegue ahí.
- **Higiene de repo** (guía §5): un solo sistema de metadatos de agentes; PDFs y
  `.tex` fuera del repo de código. Aplica al migrar desde SimulCTTC.

---

## 14. Los arreglos de la auditoría del 2026-08-04

Esta sección va al final y no en el §2 que le tocaría por fecha, para no invalidar
las referencias `§N` que el resto del fichero y `ROADMAP.md` ya hacen entre sí.

Las **seis inconsistencias** de `INCONSISTENCIAS.md` más la consideración **C1**,
cerradas. Ninguna la detectaba la suite —eso era lo que las hacía dignas de estar
escritas— y una de ellas resultó ser peor de lo que la propia auditoría creía.

### 14.1 El titular: los 219 km eran falsos, y no hay ningún número que los sustituya

C1 pedía un test para las cifras «14.6 km por vuelta, 219 km al día» que estaban
citadas en 15 sitios, **incluido el texto de un `DomainError` que un usuario lee**.
Al escribir el test, las cifras no salieron. Lo que salió, para la misma SSO de
700 km declarada en ν = 0:

| Órbita (elementos en ν = 0) | 1 vuelta | 15 vueltas (~1 día) | radial (1 vuelta) | cross-track (1 vuelta) | reloj |
|---|---|---|---|---|---|
| SSO 700 km, i = 98.2° | **86.3 km** | **1293 km** | 0.53 km | 0.03 km | 11.5 s/vuelta |
| ISS-like, i = 51.6° | 56.4 km | 845 km | 0.23 km | 0.07 km | 7.4 s/vuelta |
| LEO polar, i = 90° | 88.1 km | 1319 km | 0.55 km | ~0 | 11.7 s/vuelta |
| LEO baja i, i = 28.5° | 20.3 km | 305 km | 0.03 km | 0.01 km | 2.7 s/vuelta |

**5.9 veces más grande** que lo documentado, y en las cuatro órbitas.

Que el instrumento es el mismo que usó la medición vieja lo dice su propio control:
con `j2 = 0` en los dos lados el residuo cae a **0.083 mm** sobre 15 vueltas, que
es el «0.09 mm» que la bitácora ya tenía escrito. Es decir: no es que la
comparación se hiciera de otra forma, es que el número no se reprodujo nunca.

**Y hay un hallazgo que vale más que la corrección.** El tamaño **depende de en qué
punto de la órbita se declaren los elementos**, porque el término de período corto
de J2 hace oscilar el semieje osculador alrededor del medio (18.3 km de pico a pico
en esta órbita) y lo que fija la deriva es cuánto se aparta la época del cruce:

| La misma SSO, declarada en | `a(época) − ⟨a⟩` | 15 vueltas |
|---|---|---|
| ν = 0° | 9.15 km | 1293 km |
| ν = 45° | −0.014 km | 1.1 km |

Un **factor de 1100** entre dos escenarios que solo difieren en cuándo se
escribieron los seis números. Eso explica por qué una medición ad-hoc pudo caer en
cualquier sitio, y refuerza la decisión del ADR 0005: si no hay una cifra que
poner en un aviso, la guarda tiene que ser un rechazo.

**Lo que el test hace y una cota no haría: atribuir.** El along-track no se acota,
se predice, con lo que ya existe en el repo:

> along-track por vuelta = `2π · a · 1.5 · δa/a` = **`3π · δa`**,
> con `δa` = semieje osculador en la época − su propio promedio sobre una vuelta.

Para la SSO: `3π · 9.147 km` = 86.2 km predichos contra 86.3 medidos. Las cuatro
filas cuadran a mejor del **2 %**, y de ahí sale la tolerancia del 5 % del test —
derivada del orden del predictor (sustituye el promedio temporal por el semieje
medio de Brouwer, que difiere en O(J2)), no ajustada al resultado. Es el patrón del
§5 aplicado otra vez: no decir «se parece», decir «lo que sobra es el término que
decidí no calcular».

**Un artefacto de la tabla vieja, además.** Daba «radial 11.7 km» a 15 vueltas. A
15 vueltas el along-track son 1290 km, o **10.4° de arco**, y la cuerda hasta un
punto tan lejano sobre una órbita curva tiene componente radial
`a(1 − cos 10.4°)` = **117 km**: geometría de la medida, no error radial. La
descomposición solo significa algo mientras la separación es pequeña, así que la
tabla nueva la da a **una** vuelta — donde el along-track es 164 veces el radial y
2800 veces el cross-track, que es la afirmación que se quería hacer.

`TestWhatNotHavingBrouwerLyddaneCosts`, 8 tests, 1.5 s: la atribución sobre las
cuatro órbitas, la linealidad (ratio 14.92 contra 15.0 exacto), la descomposición,
el control con `j2 = 0`, y la dependencia con la fase. El propagador analítico que
la medición necesita vive **en el test**, no en `src/`, y usa `relabelled_as` en las
**dos** direcciones — el uso más elocuente que la bandera tiene.

### 14.2 El marco se guardaba como cadena (inconsistencia 1)

`Frame` es un `StrEnum`, así que `"teme" == Frame.TEME` es `True` y la validación
`if frame not in (Frame.TEME, Frame.GCRF)` **aceptaba** la cadena y guardaba la
cadena. Repr idéntico, todos los tests pasando, y el primer consumidor que
escribiera `if traj.frame is Frame.TEME` —la forma idiomática, la que ya usan los
tests de `frames.py`— habría tomado la rama equivocada **sin error**.

`frames.resolve_frame` (público, y por la misma razón por la que
`DEFAULT_ZONAL_RTOL` se hizo público: lo necesitan dos módulos). Resuelve y **nada
más**; que un marco concreto sea admisible sigue siendo regla del llamante, con su
mensaje. Eran dos fallos distintos y siguen teniendo dos mensajes: «no es un
marco» (que además dice dónde fue a parar ECEF) y «unos elementos en un marco que
rota no son unos elementos». `ClassicalElements` y `Trajectory` lo llaman antes de
juzgar.

Las aserciones nuevas son de **identidad**, no de igualdad: un test con `==`
pasaría contra el bug.

### 14.3 «Immutable» era falso en los tres contenedores (2 y 3)

`frozen=True` y `__slots__` congelan el *binding*, no el buffer. El caso peor no
era teórico: `TimeGrid(t_s=[99, 60])` se **rechaza** en construcción por no ser
creciente, y se llegaba a ese estado mutando después — con `duration_s` e
`is_uniform` respondiendo como si nada, y con el docstring dando permiso explícito
a los consumidores para no re-comprobar.

Dos helpers en `core/types.py` — **no** en `orbits/_validation.py`, que era el
sitio evidente y habría roto la regla `core ← orbits`: `TimeGrid` vive en `core` y
no puede importar de `orbits`. Que el arreglo de una inconsistencia estuviera a
punto de crear otra es la anécdota útil de esta entrada.

| Contenedor | Qué hace | Por qué |
|---|---|---|
| `TimeGrid`, `ClassicalElements` | `frozen_copy` — copia y congela | reciben arrays **del llamante**, así que congelar sin copiar dejaría al llamante con una referencia escribible al mismo buffer. La copia es de tamaño `n`: irrelevante |
| `Trajectory` | `frozen_view` — congela una **vista**, sin copiar | sus arrays los produce el propio módulo y no hay segunda referencia. Copiar `(S, n, 3)` son 24 MB por array para un millón de muestras |

`frozen_view` devuelve una vista y no el argumento porque `writeable` es del objeto
array, no del buffer: congelar el argumento haría de solo lectura el array del
llamante como **efecto secundario de pasarlo**. Hay un test que lo fija.

Esto cierra la 3 de paso: `relabelled_as` compartía `p`, `e` e `i` con el original
y **no** `Ω`, `ω`, `ν` (esos los creaba `_wrap_two_pi`) — medio aliaseado, que es
peor que cualquiera de las dos cosas de forma consistente. El test que existía
comparaba valores, así que habría pasado igual; el nuevo compara `shares_memory` en
los seis.

Coste medido: **ninguno visible**. La suite pasa de 586 a 625 tests y de ~11 s a
~12 s, y la cobertura es la misma antes y después (99 % global, 100 % en los cuatro
módulos de `orbits/`).

### 14.4 Las tres documentales (4, 5, 6)

- **`MEAN_BROUWER` afirmaba fijar unas constantes que no fija.** Decía «referred to
  the EGM96 constants», y el propio repo lo desmentía con un test legítimo que
  evalúa elementos `MEAN_BROUWER` con constantes WGS-72. La afirmación honesta, ya
  escrita en el docstring y en el ADR 0006: **la etiqueta nombra la teoría**, las
  constantes viajan con el modelo (regla del ADR 0004), y la coherencia entre las
  dos **no se comprueba porque no se puede**. El matiz que no se pierde: unos
  elementos medios *sí* dependen de con qué constantes se promediaron, así que la
  etiqueta no es del todo ajena a ellas — pero meterlas en la etiqueta sería
  afirmar algo que el código no verifica nunca. La subdecisión 2 sigue en pie por
  la **teoría**, que es lo que cambia el significado del semieje.
- **El ADR 0004 contradecía al 0006.** Dos filas nuevas en su tabla (el tipo de
  elemento que exige `secular_rates_j2`, y que las constantes no las fija la
  etiqueta), su punto de contexto 4 actualizado —el desajuste ya no es un coste
  tolerado, es un `DomainError`— y el bullet del acoplamiento con `tle.py`
  corregido en el sitio donde estaba mal, con el análisis de por qué SGP4 no
  necesita ninguna pieza nuestra de Brouwer-Lyddane.
- **Dos huecos menores.** El `Raises` de `propagate` nombra ahora los elementos
  medios y dice que la guarda es la de `coe_to_rv`, la misma para los dos modos. Y
  el ejemplo de «explicación mala» de `CLAUDE.md` sigue siendo válido **como
  estilo** pero avisa de que como hecho está caducado: hoy eso no introduce un
  error, levanta un `DomainError`.

Y una vuelta de tuerca en `CLAUDE.md` que no pedía la auditoría pero que es la
lección de C1: la norma 1 exige «un ejemplo con números, preferiblemente medido en
este repo». Queda escrito que **«medido en este repo» significa medido por un test
que corre**, y que si no hay test, lo honesto es decir de dónde salió el número.

### 14.5 Ficheros

Código: `core/types.py` (los dos helpers + `TimeGrid`), `orbits/frames.py`
(`resolve_frame`), `orbits/kepler.py` (marco resuelto, seis campos copiados y
congelados, docstrings), `orbits/propagator.py` (`Trajectory` congelado y con marco
resuelto, `Raises`, tabla), `orbits/_validation.py` (una nota sobre por qué las
congeladoras no están ahí).

Tests: `test_types.py` (`TestTimeGridImmutabilityIsReal`), `test_frames.py`
(`TestFrameResolution`), `test_kepler.py` (`TestElementsAreActuallyImmutable`,
`TestFrameIsStoredAsAMember`, y el `shares_memory` de `relabelled_as`),
`test_propagator.py` (`TestTrajectoryIsWhatItSaysItIs` y
`TestWhatNotHavingBrouwerLyddaneCosts`).

Documentos: ADR 0004, 0005 y 0006; `CLAUDE.md`; `ROADMAP.md`;
`INCONSISTENCIAS.md`, que se queda **sin ninguna entrada abierta**.

Verificación: `ruff`, `ruff format`, `mypy` (28 ficheros), **625 tests en 12 s**,
99 % de cobertura global.

---

## 15. `orbits/tle.py` — las decisiones (→ [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md))

> Esta sección va al final, como la 14, y por la misma razón: no invalidar las
> referencias `§N` que el resto del fichero y `ROADMAP.md` ya hacen entre sí.

### Qué es un TLE, para quien llegue nuevo

Un TLE («Two-Line Element set», juego de dos líneas de elementos) es el formato
con el que casi toda la comunidad de seguimiento de satélites publica una
órbita: dos líneas de texto de 69 caracteres, columnas fijas. No son seis
números cualesquiera — son los parámetros de entrada de un modelo analítico
concreto, **SGP4**, y solo tienen sentido físico si se interpretan con ese
modelo. Este módulo envuelve el paquete `sgp4` de PyPI (que ahora es
dependencia **del núcleo** en `pyproject.toml`, no un extra: un TLE sin
propagador para leerlo no sirve de nada) en vez de reimplementar SGP4, tal como
pedía `notes/ROADMAP.md` §2.1.5.

### Las tres piezas que ya estaban decididas, y que este módulo solo cumple

1. **No entra por `propagate()`.** Ya lo decía el ADR 0005: SGP4 devuelve
   estado en TEME directamente, así que el camino TLE → posición no pasa por
   `coe_to_rv` ni por `secular_rates_j2`. Hay una función propia,
   `propagate_tle`, con su propia firma.
2. **Nunca se construye un `ClassicalElements` con los elementos medios de un
   TLE.** Son de Brouwer con la corrección de Kozai, referidos a WGS-72 — no
   los osculadores de `rv_to_coe`, y mezclarlos es el error de kilómetros que
   `ElementType` (ADR 0006) existe para prevenir. `tle.py` no construye
   ningún `ClassicalElements`, así que no hace falta una guarda de tipos: la
   disciplina es no escribir esa línea. `MEAN_KOZAI_SGP4`, el miembro que el
   ADR 0006 dejó previsto para este momento exacto, **sigue sin usarse** —
   correctamente, porque nada lo necesita todavía.
3. **`PropagationMethod` gana `SGP4`.** Es la decisión de diseño de esta
   entrada que más defensa necesita, y se desarrolla abajo.

### La decisión de esta entrada: `SGP4` en el enum, y `propagate()` sin rama para él

`Trajectory.method` está tipado como `PropagationMethod` porque es el campo
que responde a «¿cómo se produjo esta trayectoria?», y esa pregunta la tiene
que poder responder cualquier `Trajectory` — también las que salen de
`propagate_tle`, no solo las de `propagate()`.

La alternativa obvia era **no** tocar `PropagationMethod` (que hasta ahora
documentaba estrictamente «qué modelo sabe correr `propagate()`») e inventar
un tipo de campo distinto para `Trajectory.method`, o una clase de trayectoria
aparte para SGP4. Se descartó por dos razones:

- Habría dos formas de decir «cómo se hizo esto» en el mismo proyecto.
- El test `test_the_enum_holds_exactly_the_implemented_modes` de
  `test_propagator.py` (ADR 0005) ya trata el enum como **el registro completo
  de procedencias**, no solo «lo que sabe ejecutar `propagate()`». Una segunda
  taxonomía paralela lo habría hecho mentir sobre lo que mide.

**La consecuencia que hay que aceptar por escrito:**
`propagate(elements, grid, method=PropagationMethod.SGP4)` **no funciona**.
`propagate()` sigue sin rama para `SGP4` —no tiene sentido que la tenga: SGP4
no toma un `ClassicalElements`, toma un `Satrec`— y su `else: raise
NotImplementedError` de cierre, que ya existía comentado `# pragma: no cover -
unreachable until the enum grows` (ADR 0005), pasa a ser **alcanzable y
correcto**: pedirle a `propagate()` el modo `SGP4` falla alto y claro, no en
silencio. El test `test_every_declared_member_actually_propagates` se divide
en dos: uno que sigue iterando solo sobre los miembros que `propagate()` sabe
ejecutar, y uno nuevo que confirma que `SGP4` da `NotImplementedError` ahí y
solo se produce vía `propagate_tle`.

**Dos categorías de «por qué un miembro no corre en `propagate()`», y por qué
no hay que confundirlas** — el mismo argumento que ya sostiene el enum
incompleto del ADR 0005, aplicado ahora a un caso distinto:

| Miembro | Categoría | Qué significa |
|---|---|---|
| `J2_SECULAR_ANALYTIC` | **Ausencia total** | Ni siquiera existe como nombre. No hay ningún sitio donde buscarlo, porque construirlo hoy exigiría alimentarlo con osculadores (ADR 0005, ADR 0006) |
| `SGP4` | **Presencia con ruta propia** | Existe, es correcto, y vive en `propagate_tle`, no en `propagate()`. `NotImplementedError` en vez de un nombre desconocido es la pista de que hay que buscar, no de que el nombre está mal escrito |

### `parse_tle` valida lo que `Satrec.twoline2rv` no valida — verificado, no asumido

Comprobado en un entorno de comprobación aparte (pip install `sgp4`, probado a
mano), con la línea real de la ISS
(`1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996` /
`2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781`):

- **El checksum no se comprueba.** Corrompiendo el último carácter de la
  línea 1 (el propio dígito de checksum) y llamando a `Satrec.twoline2rv`:
  **se acepta sin error**. El checksum de un TLE es la suma de las columnas
  1-68 (cada `-` cuenta 1, cualquier otro carácter no numérico cuenta 0)
  módulo 10, comparada con la columna 69 — y `sgp4` no lo mira.
- **La entrada basura no lanza excepción.**
  `Satrec.twoline2rv("garbage", "more garbage")` no lanza nada: devuelve un
  objeto con `satnum=0` y deja, **en silencio**, `satrec.error == 2` (código
  de `sgp4.api.SGP4_ERRORS`, «nm is less than zero») — nadie lo ve si no se
  comprueba a propósito.

`parse_tle` hace tres cosas que `Satrec.twoline2rv` no hace, las tres con
`DomainError`: valida longitud (69) y prefijo de cada línea, recalcula y
compara el checksum, y comprueba `satrec.error` tras la llamada. Es el mismo
principio de la tabla de decisión del ADR 0005 («un default silencioso es
peor que un nombre ausente»), aplicado a una dependencia de terceros: una
librería que no avisa es, para quien la envuelve y no lo comprueba,
indistinguible de un `except: pass` propio.

### WGS-72 explícito, aunque ya sea el defecto

Verificado: `Satrec.twoline2rv(line1, line2)` sin tercer argumento usa WGS-72
por defecto (`mu = 398600.8 km³/s²`, igual que pasando `WGS72` explícito, y
distinto de `WGS84`, que da `mu = 398600.5`). `parse_tle` lo pasa explícito de
todos modos: una TLE **se define** respecto a WGS-72 —parte de la
especificación de SGP4, no una elección de quien la usa— y confiar en que el
defecto de una dependencia siga siendo el mismo mañana es el acoplamiento
implícito que el ADR 0005 ya rechazó para `method` en `propagate()`. El
proyecto ya tiene la distinción hecha explícita:
`quoss.core.constants.WGS72_MU_KM3_S2` (= 398 600.8), con su comentario «*Note:
not the WGS-84 value*», y `WGS72_RADIUS_EQUATORIAL_KM` (= 6378.135 km) —
distinto de `EGM96_RADIUS_EQUATORIAL_KM` (6378.1363 km) y de
`WGS84_RADIUS_EQUATORIAL_KM`, la misma disciplina de tres radios para tres
propósitos que documenta §8.

### La época del TLE es la única época posible

`propagate_tle(satrec, t_s)` construye internamente
`TimeGrid(epoch_jd=tle_epoch_jd(satrec), t_s=t_s)` en vez de aceptar un
`TimeGrid` ya construido por el llamante. Un `ClassicalElements` no lleva
época propia —por eso `propagate()` la exige dentro del `TimeGrid`—, pero un
`Satrec` **ya la lleva dentro** (`satrec.jdsatepoch + satrec.jdsatepochF`).
Aceptar una época externa distinta abriría la puerta a una `Trajectory` cuyo
`grid.epoch_jd` mintiera sobre a qué instante están referidos los elementos —
el mismo espíritu que «unos elementos en un marco que rota no son unos
elementos» del ADR 0002, o el propio `ElementType` del ADR 0006: la forma de
la API cierra el error por construcción, no con una comprobación que alguien
podría olvidar.

### La conversión JD/segundos parte `fr` para no perder precisión

SGP4 recibe el tiempo como `(jd, fr)` —parte entera y fraccionaria del día
juliano— porque, literalmente según `sgp4.conveniences.jday_datetime`, `fr`
«can, unlike the first float, be accurate down to very small fractions of a
second» mientras se mantenga pequeño (un `float64` en torno a JD ≈ 2 460 000
ya gasta siete dígitos de mantisa en la parte entera). `propagate_tle` calcula,
por muestra:

```
whole_days = floor(satrec.jdsatepochF + t_s / 86400)
jd = satrec.jdsatepoch + whole_days
fr = satrec.jdsatepochF + t_s / 86400 - whole_days
```

de modo que `fr` se queda en `[0, 1)` sin importar cuántos días de `t_s` hayan
pasado, en vez de dejar crecer `fr = satrec.jdsatepochF + t_s/86400` sin
límite — que empezaría a competir otra vez por los mismos bits de mantisa que
partir el tiempo en dos pretendía liberar.

**Medido en `tests/orbits/test_tle.py::TestJdFrSplitPrecision`:** propagando la
misma TLE a `t_s` = 30 días por las dos vías, la diferencia en posición y en
velocidad es **exactamente cero, hasta el último bit**. Esto no dice que
partir `fr` sea innecesario: dice que esta build concreta de `sgp4` (la
extensión C, `vallado_cpp.abi3.so`) ya reduce `jd + fr` en doble precisión por
dentro, así que ninguna versión futura de la dependencia está obligada a
seguir haciéndolo. Partir `fr` sigue siendo lo correcto por higiene y por
ceñirse al contrato que documenta el propio paquete — no porque este test
pueda medir hoy un error que no existe. Exactamente el tipo de hallazgo que la
norma 1 de `CLAUDE.md` pide reportar tal cual sale, sin forzarlo a sonar como
una corrección que no fue.

### La verificación V3 llega gratis

El paquete `sgp4` trae, en su propio directorio instalado, `SGP4-VER.TLE` y
`tcppver.out` — los datos de verificación oficiales del caso AIAA 2006-6753
(Vallado, Crawford, Hujsak, Kelso, *Revisiting Spacetrack Report #3*, 2006),
la referencia estándar de la industria. Cumple las tres condiciones de
`tests/golden/README.md` para un oráculo V3 que no necesita congelarse aparte
—dependencia del núcleo, determinista, comparado muy por encima de su propio
error—, el mismo argumento que ya vale para el integrador DOP853 de
`perturbations.py` (§8).

**Medido en `tests/orbits/test_tle.py::TestAgainstVallado2006VerificationData`**,
sobre cuatro regímenes (LEO de bajo y de moderado arrastre, Molniya con
`e = 0.6877`, y un caso de decaimiento fuerte): el peor residuo es **7.3e-9 km**
en posición y **7.7e-10 km/s** en velocidad — consistente con el redondeo a 8
decimales que imprime el propio `tcppver.out` (1e-8 km de resolución), no con
una diferencia física, porque las dos rutas evalúan la misma teoría SGP4. Las
tolerancias del test quedan un orden de magnitud por encima de lo medido. Esto
sí es una medición de este repo, distinta de la cita de §2 sobre el acuerdo de
0.1 mm entre la versión Python pura de `sgp4` y su referencia C++ — esa cita
sigue sin tener test propio y no debe confundirse con esta.

### Las decisiones, en tabla

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`tle.py` no entra por `propagate()`; `propagate_tle` en su propio módulo** | Un TLE se propaga con SGP4, que devuelve estado en TEME directamente. Forzar la entrada por `propagate()` reabriría la confusión medio/osculador por otra puerta (ADR 0005) | Alto |
| **`tle.py` nunca construye un `ClassicalElements`** | Los elementos medios de un TLE son de Brouwer-Kozai/WGS-72, no los osculadores de `kepler.py`. La disciplina es no escribir la línea, no una guarda de tipos — no hace falta un tipo nuevo hoy | Medio |
| **`PropagationMethod` gana `SGP4`, y `propagate()` no lo ejecuta** | `Trajectory.method` es «cómo se produjo esto» para cualquier `Trajectory`, no solo las de `propagate()`. Dos taxonomías paralelas habrían hecho mentir al test que ya trata el enum como registro completo de procedencias | Alto |
| **`parse_tle` valida checksum, forma de línea y `satrec.error`** | `Satrec.twoline2rv` acepta un checksum corrupto sin error y deja `satrec.error` puesto en silencio ante entrada basura — verificado a mano, no asumido. Callar sobre ello es indistinguible de un `except: pass` propio | Bajo |
| **WGS-72 explícito en `Satrec.twoline2rv`, aunque ya sea el defecto** | Una TLE se define respecto a WGS-72; confiar en el defecto de una dependencia es el mismo acoplamiento implícito que el ADR 0005 ya rechazó para `method` | Trivial |
| **`propagate_tle` construye su propio `TimeGrid`, no acepta uno externo** | Un `Satrec` ya lleva su época dentro (`jdsatepoch + jdsatepochF`). Aceptar otra abriría la puerta a una `Trajectory` cuyo `epoch_jd` mintiera sobre a qué elementos se refiere | Medio |
| **`fr` se reduce a `[0, 1)` en cada muestra en vez de dejarlo crecer** | SGP4 solo preserva precisión de sub-segundo en `fr` mientras se mantenga pequeño; dejarlo crecer con `t_s` vuelve a gastar los mismos bits de mantisa que partir el tiempo pretendía liberar. Medido a 30 días: diferencia cero con esta build de `sgp4` — higiene y contrato documentado, no una corrección de un error medible hoy | Trivial |
| **La verificación V3 usa `SGP4-VER.TLE`/`tcppver.out` del propio paquete, sin congelar aparte** | Cumple las tres condiciones de `tests/golden/README.md`: dependencia del núcleo, determinista, muy por encima de su propio error | — |

### Alternativas descartadas

**Un cuarto argumento en `propagate()` para SGP4.** Habría exigido que
`propagate()` aceptara dos tipos de primer argumento distintos
(`ClassicalElements` o `Satrec`) según `method`, rompiendo la firma que el ADR
0005 fija con un test sobre `inspect.signature`.

**`Trajectory.method` con un tipo distinto para las trayectorias de SGP4.**
Habría dado dos formas de decir «cómo se hizo esto» en el mismo proyecto —ver
arriba.

**Confiar en que los TLE de producción (CelesTrak, Space-Track) ya vienen bien
formados y no comprobar checksum.** El README no admite excepciones de «la
mayoría de los casos»: un checksum que falla en silencio es, desde fuera,
indistinguible del `except: pass` que el README prohíbe.

**Confiar en el defecto WGS-72 de `Satrec.twoline2rv` sin pasarlo explícito.**
Es un acoplamiento implícito con la versión instalada de una dependencia — el
mismo patrón que el ADR 0005 ya rechazó para `method` sin default.

### Lo que queda abierto de este módulo

- **`MEAN_KOZAI_SGP4` sigue sin usarse**, correctamente: nada en el proyecto
  construye hoy un `ClassicalElements` a partir de los elementos medios de un
  TLE.
- **Brouwer-Lyddane sigue sin existir**, y este módulo no la necesita: SGP4
  hace su propia conversión medio→osculador por dentro, con las convenciones
  de Kozai/WGS-72. El acoplamiento «BL ↔ `tle.py`» que §13 ya corrigió por
  escrito («El acoplamiento BL ↔ `tle.py` que el roadmap afirma está
  sobredimensionado») queda confirmado, no reabierto.
- **`geometry.py`**, el siguiente módulo del roadmap (2.1.6): elevación,
  azimut, slant range, Doppler y el ángulo de point-ahead. `propagate_tle`
  deja lista una `Trajectory` con `frame=Frame.TEME`, indistinguible en forma
  de las que produce `propagate()`, así que `geometry.py` no tendrá que
  ramificar según de dónde vino la trayectoria.

Verificación ejecutada:

```bash
uv run ruff check .          # All checks passed!
uv run ruff format --check . # 30 files already formatted
uv run mypy                  # Success: no issues found in 30 source files
uv run pytest                # 656 passed
uv run pytest --cov          # 99 % global · orbits/tle.py 100 %
```

De 655 a 656 tests: 27 nuevos en `tests/orbits/test_tle.py` más uno añadido
después para cerrar la única rama sin cubrir de `_validate_tle_line` (columna
69 presente pero no numérica — ninguno de los casos anteriores la alcanzaba,
porque el de longitud incorrecta y el de basura fallan antes, en la
comprobación de longitud o de prefijo).

---

## 16. `orbits/geometry.py` — de trayectoria a lo que ve un telescopio

### Qué hace este módulo, para quien llegue nuevo

Todo lo anterior en `orbits/` responde «dónde está el satélite» — un vector en
un marco que gira con las estrellas, no con la Tierra (TEME, ver ADR 0002).
Una estación en tierra necesita otra pregunta: hacia dónde giro el telescopio
(**azimut**, medido desde el norte geográfico, en sentido horario), cuánto lo
inclino (**elevación**, 0° en el horizonte, 90° en el cenit), y a qué
distancia está (**slant range**, la línea recta, no la distancia sobre el
suelo). Las tres se miden contra la **vertical local** — la dirección de una
plomada, que en una Tierra achatada *no* apunta al centro del planeta — y ese
marco topocéntrico (ENU, East-North-Up) ya existía: `frames.enu_from_itrf` lo
construye desde la normal geodésica WGS-84. Lo único que faltaba era
alimentarlo con el vector correcto (satélite menos estación, expresados en el
mismo marco) y leer elevación/azimut/rango de sus tres componentes — eso es
`look_angles`.

### Por qué hay que rotar a ITRF antes de restar nada

Una `Trajectory` vive en TEME (inercial); una estación vive fija sobre la
Tierra, que gira. Restar la posición ITRF de la estación de la posición TEME
del satélite mezclaría dos vectores de marcos distintos y daría un número que
no significa nada: la estación parecería barrer el cielo a la velocidad de
rotación de la Tierra incluso para un satélite parado. `look_angles` rota
primero (`frames.teme_to_itrf_state`, la misma rotación por GMST que ya existía)
y todo lo que devuelve —elevación, azimut, rango, tasa de rango, ángulo de
point-ahead— sale de ese único vector ya rotado. Un solo sitio donde un error
de marco podría esconderse, no cinco.

### La velocidad de la estación no hace falta sumarla — y por qué

Tasa de rango y ángulo de point-ahead necesitan una velocidad *relativa*. La
velocidad de la estación en ITRF es exactamente cero por construcción —eso es
lo que significa «fijo sobre la Tierra»—, así que «relativo a la estación» y
«la velocidad ITRF del satélite» son el mismo vector. Hacerlo en TEME en
cambio obligaría a sumar aparte el término `omega x r` de la estación (el
mismo que `teme_to_itrf_state` ya documenta para el satélite) — exactamente el
tipo de término que una implementación con prisa olvida.

### El ángulo de point-ahead, y el factor de 2 que es fácil perder

La luz tarda un tiempo `tau = R/c` en cruzar el rango `R`. En ese tiempo el
satélite se mueve, así que apuntar a su posición *aparente* (la que se observa
ahora) no apunta a donde estará cuando llegue el haz transmitido — ni un haz
transmitido hacia esa posición aparente vuelve por la misma línea a un
terminal coubicado, porque esa señal también se habrá movido para cuando
regrese. Solo importa la componente de velocidad relativa **transversal** a la
línea de visión (un acercamiento o alejamiento puramente radial no cambia
hacia dónde hay que apuntar, solo el rango), así que el módulo proyecta la
velocidad relativa sobre el plano perpendicular a esa línea.

Para una sola vía (un telescopio en tierra que dispara hacia un satélite que
recibirá los fotones tras `tau`), el blanco se ha movido `v_perp * tau =
v_perp * R / c`, un ángulo `v_perp / c` visto desde el emisor. Este módulo
devuelve **el doble** de eso, `PAA = 2 v_perp / c`, porque un segmento QKD en
tierra no es un emisor de una sola vía: es un terminal monostático que tiene
que transmitir adelantado por una vía y a la vez recibir por la vía que la luz
realmente sigue, y esas dos vías divergen el mismo ángulo en sentidos
opuestos — el mismo factor 2 que aparece en la literatura de enlaces ópticos
inter-satélite para un terminal bidireccional [2].

**Medido, no afirmado:** para un paso que alcanza 67.1° de elevación sobre
Castelldefels (estación propia del CTTC, 41.2750° N, 1.9875° E, 30 m) en la
SSO de 700 km que ya usa este repo (los mismos números del ejemplo de
`secular_rates_j2` en `perturbations.py`), `tests/orbits/test_geometry.py::TestPointAheadAngle`
encuentra un ángulo de point-ahead de **50.6 µrad** en ese punto de máxima
elevación — mayor que los 35 µrad que citaba antes `notes/ROADMAP.md`, porque
esa cifra no llevaba el factor 2. Las dos cifras siguen siendo mayores que el
jitter de apuntado que este proyecto modelará más adelante, que es la única
afirmación que hacía la nota del roadmap.

### El Doppler, deliberadamente fuera de este módulo

`look_angles` se detiene en `range_rate_km_s` — una cantidad puramente
geométrica, km/s, que no sabe a qué longitud de onda transmite un terminal.
`doppler_shift_hz` convierte una tasa de rango en un desplazamiento de
frecuencia dada una portadora, y es una función aparte de una línea en vez de
un campo de `LookAngles`, por la misma razón que `propagator.Trajectory` no
guarda un modelo de gravedad (ver el docstring de ese módulo): la frecuencia
portadora pertenece al terminal óptico, un concepto de la capa channel/system
que todavía no existe (`notes/ROADMAP.md` etapa 2.2), y meterlo en un tipo de
la capa `orbits/` afirmaría una dependencia que no existe.

### Las decisiones, en tabla

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **`look_angles` exige `Trajectory.frame is Frame.TEME`** | Es el único marco que producen los propagadores de este paquete (`propagate` y `propagate_tle` por igual); aceptar otro sin comprobarlo repetiría el error de marco que la rotación de este módulo existe para cerrar | Medio |
| **La rotación a ITRF ocurre una sola vez, dentro de `look_angles`** | Elevación, azimut, rango, tasa de rango y point-ahead salen todos del mismo vector ya rotado — un solo sitio donde un error de marco podría esconderse en vez de cinco | Alto |
| **La velocidad relativa se calcula como la velocidad ITRF del satélite, sin sumar un término de estación** | La velocidad ITRF de un punto fijo en tierra es cero por construcción; sumar un término que vale cero no cambia el resultado pero sí abre un sitio para un error de signo | Bajo |
| **El ángulo de point-ahead lleva factor 2** | Un terminal monostático transmite adelantado y recibe por la vía real a la vez; las dos vías divergen el mismo ángulo en sentidos opuestos — perder el factor 2 subestima el ángulo a la mitad | Alto (es exactamente el error que un lector apurado comete) |
| **`doppler_shift_hz` es una función aparte, no un campo de `LookAngles`** | La frecuencia portadora es un parámetro del terminal óptico (capa channel/system, `notes/ROADMAP.md` 2.2), no de la geometría orbital — la misma separación que ya aplica `Trajectory` para el modelo de gravedad | Medio |
| **Las coordenadas de la estación son escalares, no vectorizables a varias estaciones** | Seleccionar o agregar entre estaciones es `system/multi_ogs.py` (etapa 3); vectorizarlo aquí adelantaría una decisión que no le toca a este módulo | Bajo |

### Alternativas descartadas

**Devolver el desplazamiento Doppler directamente desde `look_angles`.**
Habría obligado a esta función a recibir una frecuencia portadora que no tiene
nada que ver con la geometría orbital, y a inventar un valor por defecto (o
exigirlo siempre) para una cantidad que hoy no tiene dueño en el proyecto —
ver `notes/ROADMAP.md` etapa 2.2.

**Point-ahead sin el factor 2, como en un enlace de una sola vía.** Es la
lectura más simple de la fórmula del retraso de luz, y es la que da la cifra
de 35 µrad que este roadmap citaba antes de tener la cuenta hecha. Un
terminal QKD en tierra transmite y recibe a la vez por vías que divergen
geométricamente, así que la cifra de una sola vía subestima el ángulo real a
la mitad — el tipo de error que «funciona» hasta que alguien mide el pase real.

**Filtrar por visibilidad (elevación mínima) dentro de `look_angles`.** Es la
etapa 3 del roadmap (`system/passes.py`), una decisión distinta de «qué
elevación tiene el satélite ahora». Mezclar las dos habría obligado a este
módulo a inventar un umbral que no le corresponde.

### Verificación V3: el hueco de `tests/golden/README.md` para look angles, cerrado parcialmente

`tests/golden/README.md` nombraba explícitamente «GMAT o Orekit cross-checks
para look angles, para `orbits/geometry.py`» como hueco sin llenar.
`tests/golden/generators/gen_geometry_reference.py` lo cierra con `astropy`
en vez de GMAT/Orekit (ya es dependencia del grupo `reference`, el mismo que
usa `gen_frames_reference.py`): construye un marco `TEME` de astropy, lo
transforma a `AltAz` en la `EarthLocation` de la estación con refracción
atmosférica desactivada (`pressure=0`, el valor por defecto de astropy —la
misma cantidad puramente geométrica que calcula `look_angles`) y registra
elevación, azimut y rango. Medido sobre 24 combinaciones estación × estado ×
época (4 estaciones ya usadas en `gen_frames_reference.py`, 3 estados TEME
plausibles, 2 épocas): elevación y azimut concuerdan a milésimas de grado,
rango a 2.2e-4 relativo — muy por debajo de lo que produciría un bug de forma,
de signo o de mezcla de marcos (decenas de grados, o un rango de signo
equivocado).

**Lo que sigue sin oráculo independiente:** `range_rate_km_s` y el ángulo de
point-ahead. `AltAz` es una función solo de la posición, así que no dice nada
de una velocidad. Quedan como V1 — comprobados contra una diferencia finita
del propio `range_km` que este módulo también calcula (que valida que la
fórmula analítica es realmente la derivada de ese rango, no que ambas sean
físicamente correctas) y contra geometrías construidas a mano donde el
resultado se conoce por construcción (velocidad puramente radial → point-ahead
cero; velocidad puramente transversal → point-ahead exactamente `2v/c`). Un
hueco declarado, per el README, es mejor que un V2 o V3 inventado.

### Lo que queda abierto de este módulo

- **`system/multi_ogs.py`** (etapa 3) es quien decide entre varias estaciones;
  `look_angles` solo acepta una.
- **`system/passes.py`** (etapa 3) es quien decide qué elevación cuenta como
  visible; este módulo no filtra ni avisa, solo informa (incluida la
  elevación negativa).
- El siguiente módulo del roadmap, **2.1.7 `orbits/constellations.py`**
  (Walker-Delta, SSO, traza repetida), no depende de este: genera conjuntos de
  `ClassicalElements`, no ángulos de visión.

Verificación ejecutada:

```bash
uv run ruff check .                                  # All checks passed!
uv run ruff format --check .                         # 35 files already formatted
uv run mypy                                            # Success: no issues found in 34 source files
uv run pytest tests/orbits/test_geometry.py -q         # 27 passed
uv run pytest tests/orbits/test_geometry.py --cov=quoss.orbits.geometry --cov-report=term-missing
                                                        # 100 % (82/82 sentencias, 18/18 ramas)
uv run pytest -q --deselect \
  tests/unit/test_conventions.py::TestUnitConventionIsEnforced::test_angle_conversion_only_at_the_boundary \
  --ignore=tests/orbits/test_constellations.py         # 688 passed
```

La deselección de `test_angle_conversion_only_at_the_boundary` y el
`--ignore` de `test_constellations.py` son por el módulo 2.1.7, en desarrollo
en paralelo en el momento de escribir esta entrada — no por nada en
`geometry.py`, cuyo propio `ruff check`/`mypy`/`pytest` están limpios sin
ninguna exclusión.

## 17. `orbits/constellations.py` — Walker-Delta, SSO y traza repetida (→ [ADR 0008](../docs/adr/0008-constellation-design.md))

### Qué hace este módulo, para quien llegue nuevo

`kepler.py` sabe describir una órbita; `perturbations.py` sabe cómo deriva bajo
J2. Ninguno de los dos responde la pregunta que un escenario real hace:
«¿cuántos satélites, en qué planos, y con qué inclinación/altitud, para cubrir
la Tierra con el calendario que quiero?». Este módulo responde tres versiones
de esa pregunta, cada una con una forma de problema distinta — geometría pura,
álgebra cerrada, y una raíz numérica — y las tres se apoyan en lo que ya
existía en vez de reimplementar nada:

- **`walker_delta(...)`**: reparte `T` satélites en `P` planos con la notación
  estándar `i:T/P/F` (Walker, 1977) y devuelve **un** `ClassicalElements` de
  longitud `T` — nunca una lista ni un bucle que el llamante tenga que correr,
  porque ese es exactamente el contrato de array que
  `notes/GUIA_REIMPLEMENTACION.md` fija para todo el proyecto.
- **`sun_synchronous_inclination_rad(a, e)`**: despeja la inclinación que hace
  que el nodo regrese exactamente al ritmo del Sol medio — invierte en forma
  cerrada la propia fórmula de `secular_rates_j2`, sin volver a escribirla.
- **`repeat_ground_track_semi_major_axis_km(orbitas, días, i, e)`**: despeja el
  semieje que hace que la traza sobre tierra se repita cada `orbitas`
  revoluciones en `días` — aquí sí hace falta una raíz numérica
  (`scipy.optimize.brentq`), porque `a` aparece a los dos lados de la
  ecuación.

Las tres decisiones no triviales de esta entrada están desarrolladas en el
[ADR 0008](../docs/adr/0008-constellation-design.md); aquí van con los números
que las miden, en el estilo de la norma 1 de `CLAUDE.md`: qué es, por qué así,
y un ejemplo medido por un test que corre.

### Decisión 1 — el espaciado dentro de plano es en anomalía media, no verdadera

**Qué es.** Un patrón Walker-Delta reparte `T/P` satélites por plano a
intervalos iguales de un ángulo. Hay dos candidatos: la anomalía verdadera
`nu` (el ángulo real, medido desde el periastro, que casi todo libro de texto
usa para dibujar el patrón) y la anomalía media `M` (un ángulo que avanza a
ritmo constante `n = sqrt(mu/a^3)` y que **no** es la posición real del
satélite salvo en una órbita circular).

**Por qué así.** Dos satélites que comparten semieje comparten movimiento
medio `n`, así que `M_1(t) = M_{1,0} + n t` y `M_2(t) = M_{2,0} + n t`: su
diferencia `M_2 - M_1` es **exactamente constante**, para cualquier `t`, bajo
movimiento kepleriano puro. La anomalía verdadera no tiene esa propiedad —
`d(nu)/dt` no es constante en una órbita excéntrica, es más rápida cerca del
periastro — así que un patrón espaciado en anomalía verdadera se deforma y se
reconstruye en cada vuelta: es el mismo bamboleo que le da a la traza de una
órbita excéntrica su forma de analema. Para las excentricidades casi nulas que
vuela casi cualquier constelación real la diferencia es casi nula (concuerdan
a `O(e)`), pero como el módulo acepta cualquier `e < 1`, la elección se hace
explícita en vez de dejarla al azar de cuál anomalía resultara cómoda de
escribir.

**Medido en este repo.** Construyendo un patrón `12:12/3/1` con `e = 0.3`
(`tests/orbits/test_constellations.py::TestWalkerDeltaInvariants`):

- El espaciado en anomalía **media**, recuperado con `kepler.mean_from_true_anomaly`
  a partir de lo que el módulo realmente almacena (anomalía verdadera), es
  `360/4 = 90°` entre satélites consecutivos del mismo plano, **exacto a
  1e-12 rad** (`test_mean_anomaly_spacing_within_plane_is_exact`).
- El espaciado en anomalía **verdadera** del mismo patrón **no** es constante
  — los pasos difieren entre sí en más de `1e-6` rad, muy por encima del ruido
  de redondeo (`test_true_anomaly_spacing_is_not_exact_once_eccentric`, el
  control negativo).

### Decisión 2 — el sentido de `F`, y qué se hizo al no encontrar un ejemplo Vallado citable

**Qué es.** `F` (con `0 <= F < P`) desplaza cada plano un múltiplo de
`360/T` respecto al plano anterior, en la **misma** dirección en que crece el
índice de plano (y por tanto el RAAN). Invertir ese signo —desplazar el plano
`p` **hacia atrás** en vez de hacia delante— produce un patrón con el
espaciado de RAAN correcto y el espaciado dentro de plano correcto: a simple
vista parece bien, y es exactamente el error que este apartado existe para
que no se cuele.

**Por qué así.** Se buscó un ejemplo Walker-Delta de Vallado (*Fundamentals of
Astrodynamics and Applications*, 4.ª ed.) resuelto con número de página, para
transcribirlo como V2 igual que `test_kepler.py` transcribe sus ejemplos de
Kepler. No se localizó con la confianza que ese estándar exige, así que —por
la regla explícita del proyecto contra inventar una cita— **no se afirma
ningún V2 aquí**. La corrección descansa en tres cosas: los invariantes V1 que
no necesitan ninguna fuente externa (espaciado de RAAN exacto, espaciado de
anomalía media exacto, recuento total exacto), un caso resuelto a mano, y el
acuerdo con cómo el patrón está documentado de forma independiente en la
documentación de `walkerDelta` de MATLAB Aerospace Toolbox (que describe el
paso entre planos como exactamente `F * 360/T` grados) — verificado por
búsqueda dirigida, no citado de memoria.

**Medido en este repo.** El caso a mano, `6:6/3/1`
(`tests/orbits/test_constellations.py::TestPhasingDirectionAgreesWithConvention::test_six_six_three_one_by_hand`,
reproducido también como doctest del módulo): plano 0 = `[0°, 180°]`, plano 1 =
`[60°, 240°]`, plano 2 = `[120°, 300°]`. Si el signo estuviera invertido, el
plano 1 leería `[-60°, 120°] = [300°, 120°]` en su lugar — los dos patrones
tienen el mismo RAAN por plano y el mismo espaciado interno, así que solo el
signo del desfase los distingue.
`test_phase_offset_between_planes_is_exactly_f_times_360_over_t` repite el
chequeo sobre cuatro patrones más (`24/6/1`, `24/3/2`, `60/5/3`, `8/4/3`).

### Decisión 3 — la SSO se despeja, la traza repetida se busca con `brentq`

**Qué es.** `secular_rates_j2` da `dOmega/dt = -1.5 n J2 (R/p)^2 cos(i)`.
Fijados `a` y `e`, es una ecuación **lineal en `cos(i)`**: despejar es una
división. La condición de traza repetida, en cambio, iguala la tasa nodal del
satélite (que depende de `a` a través de `n`, `dOmega/dt` y `domega/dt`) con
la rotación terrestre relativa al nodo (que depende de `a` a través de
`dOmega/dt` otra vez): `a` aparece a los dos lados, así que no hay despeje
posible y hace falta una raíz numérica.

**Por qué así, y no al revés en los dos casos.** Meter `scipy.optimize` en la
SSO sería resolver con fuerza bruta un problema que ya viene resuelto, y de
paso reimplementar por la puerta de atrás una fórmula que `perturbations.py`
ya tiene probada — el mismo argumento que el ADR 0004 ya aplicó a los
armónicos zonales. `brentq` (no un Newton escrito a mano) para la traza
repetida, porque converge garantizado para cualquier corchete que cambie de
signo, sin necesitar una derivada — el mismo argumento que ya documenta el
solver iterativo de `frames.py` para la inversión geodésica. El corchete es la
estimación de dos cuerpos (ignorando J2 del todo) ensanchada un 5 % a cada
lado: generoso porque la contribución de J2 a la condición de resonancia es
`O(J2)` ~ 1e-3 relativo y la corrección de rotación terrestre no pasa de ~1.4 %
en los regímenes de este proyecto.

**Medido en este repo.**

- Invertir `a=7078.137 km, e=0.001` (el mismo caso que el docstring de
  `secular_rates_j2` cita con `i=98.19°` → `0.9859°/día`) recupera
  `i = 98.19°` a la precisión con la que ese número está citado
  (`TestSunSynchronousClosedForm::test_recovers_the_secular_rates_j2_docstring_example`).
  El viaje de ida y vuelta —despejar `i`, meterla otra vez en
  `secular_rates_j2`— cierra con un residuo `< 1e-17` rad/s: no es una
  segunda medición que coincide, es la misma igualdad resuelta para la
  incógnita contraria
  (`test_round_trip_through_secular_rates_j2_is_exact`).
- Con `j2 = 0` la condición de traza repetida se reduce idénticamente a la de
  dos cuerpos, y el semieje que devuelve `brentq` coincide con
  `semi_major_axis_from_period_km` aplicado al período de dos cuerpos, a
  `1e-6` km
  (`TestRepeatGroundTrackResonance::test_reduces_to_the_two_body_closed_form_when_j2_is_zero`).
- El corchete del 5 % **puede** fallar, y se buscó deliberadamente un caso que
  lo hiciera para probar que la función lo dice en vez de devolver un número
  fuera de rango: `orbitas=16, días=1, i=63.4°, e=0.9` deja el residuo de
  resonancia del **mismo signo** en los dos extremos del corchete
  (`+3.27e-4` y `+3.78e-4` rad/s), así que `brentq` no tiene nada que
  bisectar y la función levanta `ConvergenceError`
  (`TestRepeatGroundTrackConvergenceError`).
- WRS-2 de Landsat-8 (233 órbitas / 16 días, `i=98.2°`, ~705 km publicados,
  misma fuente NASA/USGS que ya usa `test_perturbations.py::TestPublishedSunSynchronous`)
  da una comprobación de plausibilidad, **no un V2**: el semieje resuelto
  corresponde a ~699.6 km de altitud, **5.4 km (0.08 %) por debajo** de la
  cifra publicada. Esa brecha **no** se explica por la precisión publicada de
  la inclinación (±0.05° mueve la solución solo ~0.08 km, medido por
  búsqueda directa) ni de la excentricidad (~0.00002 km) — así que queda
  anotada como una discrepancia real, probablemente por «705 km» ser una
  cifra nominal redondeada o por efectos (maniobras, J2²/J4) que esta teoría
  de primer orden no modela, en vez de forzar el número a que encaje
  (`TestRepeatGroundTrackAgainstLandsat8`).

### El hueco que este módulo hereda del ADR 0006, sin esconderlo

`sun_synchronous_inclination_rad` y `repeat_ground_track_semi_major_axis_km`
devuelven el número crudo (radianes, kilómetros), nunca un `ClassicalElements`
— la misma elección que ya hace `kepler.semi_major_axis_from_period_km`, y por
la misma razón: es quien llama quien decide la etiqueta al construir. La razón
de fondo es más seria que estilo: esos números son correctos como cantidades
**medias** (son la salida de invertir/resolver `secular_rates_j2`, que exige
`MEAN_BROUWER`), no como el semieje/inclinación **osculador** de una época
concreta. Construirlos con `ClassicalElements.from_semi_major_axis(...)` —cuyo
`element_type` por defecto es `OSCULATING`— y pasarlos por `coe_to_rv` hereda
el mismo desajuste ya medido en `kepler.py`: hasta **86 km tras una vuelta y
1290 km tras un día** para una SSO de 700 km, y no una cifra única porque
depende de en qué punto de la órbita se declaren los elementos. No se
vuelve a medir aquí — es la misma fórmula y el mismo régimen ya medidos, y
remedirlo sería fingir una medición nueva sobre un número que ya existe. La
guarda de tipos del ADR 0006 es lo que convierte ese error en un
`DomainError` explícito en el momento en que alguien intenta sacar un estado
sin pasar por `relabelled_as` y decirlo por escrito, en vez de un número
plausible y equivocado que ninguna aserción de forma detecta.

### Las decisiones, en tabla

| Decisión | Razón | Coste de cambiarla |
|---|---|---|
| **Espaciado dentro de plano en anomalía media, no verdadera** | Solo la anomalía media se mantiene exactamente constante entre satélites que comparten semieje, bajo movimiento kepleriano puro; la verdadera se deforma y reconstruye cada vuelta en una órbita excéntrica | Medio |
| **Sentido de `F`: el plano `p` avanza, no retrocede** | Es la convención estándar (Walker 1977), reproducida de forma independiente por MATLAB Aerospace Toolbox; invertirla da un patrón que parece correcto a simple vista | Alto (es exactamente el error que la gente comete) |
| **Ningún ejemplo Walker-Delta ni de traza repetida citado como V2 de Vallado** | No se localizó uno transcribible con la confianza que el estándar del proyecto exige; se prefiere decir el hueco a inventar una cita | — |
| **SSO por álgebra cerrada, no `scipy.optimize`** | La ecuación es lineal en `cos(i)`; un solver numérico ahí sería reimplementar `secular_rates_j2` con más pasos y más superficie de error | Alto (perdería la garantía de "misma fórmula, ida y vuelta") |
| **Traza repetida por `brentq`, acotado por la estimación de dos cuerpos ± 5 %** | `a` aparece a los dos lados de la condición de resonancia; `brentq` converge garantizado sin derivada para cualquier corchete que cambie de signo | Medio |
| **`ConvergenceError`, no un corchete más ancho por defecto, cuando no hay cambio de signo** | Un caso de excentricidad alta lo prueba: ensanchar a ciegas escondería que el problema pedido está lejos de cualquier estimación de dos cuerpos razonable | Bajo |
| **Las dos funciones físicas devuelven el número crudo, nunca un `ClassicalElements`** | Son cantidades *medias*; etiquetarlas `OSCULATING` por defecto sería exactamente el desajuste que el ADR 0006 existe para bloquear con un `DomainError` en vez de dejarlo pasar | Alto |

### Alternativas descartadas

**Espaciar en anomalía verdadera.** Es lo que casi todo libro de texto dibuja
al presentar el patrón. Se descarta porque no se mantiene constante en el
tiempo para una órbita excéntrica — ver Decisión 1.

**Resolver la SSO con `scipy.optimize.brentq`, por uniformidad con la traza
repetida.** El problema es lineal en `cos(i)`; usar un solver numérico donde
hay álgebra cerrada no gana nada y sí pierde la garantía de "misma fórmula
resuelta en las dos direcciones" que hace exacto el viaje de ida y vuelta.

**Devolver un `ClassicalElements` ya etiquetado `MEAN_BROUWER` desde las
funciones físicas en vez del número crudo.** Habría cerrado el hueco
mean/osculador de raíz, pero habría obligado a la firma a decidir el resto de
elementos (RAAN, argumento de periastro, anomalía) con valores arbitrarios que
la función no tiene motivo para fijar. El número crudo, con la construcción a
cargo de quien llama, es el patrón que ya sigue
`semi_major_axis_from_period_km`.

### Lo que queda abierto de este módulo

- **Brouwer-Lyddane sigue sin existir.** El semieje/inclinación de SSO y traza
  repetida siguen siendo cantidades medias que nada en QuOSS puede convertir a
  osculador. La bandera del ADR 0006 es una puerta cerrada, no un paso —igual
  que en cada entrada anterior que toca este tema.
- **Ningún ejemplo Walker-Delta ni de traza repetida con página de Vallado
  citada.** Queda como hueco declarado, no como V2 inventado — ver Decisión 2
  y la nota de Landsat-8 en Decisión 3.
- **Visibilidad, CLI y esquema de escenario** siguen sin tocar, por diseño:
  son las etapas `scenario/` y `cli/` (`orbits/geometry.py`, ya hecho, es
  quien calcula elevación/azimut una vez existe una `Trajectory`, y no
  depende de este módulo ni al revés — genera conjuntos de `ClassicalElements`,
  no ángulos de visión).
- **`TROPICAL_YEAR_S`**, la única constante nueva de esta entrada
  (`core/constants.py`), no tiene test propio que la mida contra una fuente —
  es un valor citado directamente (365.2421897 días), en el mismo estilo que
  `MEAN_SIDEREAL_DAY_S` ya usa para el día sidéreo medio.

Verificación ejecutada:

```bash
uv run ruff check .                          # All checks passed!
uv run ruff format --check .                 # 35 files already formatted
uv run mypy                                  # Success: no issues found in 35 source files
uv run pytest -q                             # 740 passed
uv run pytest tests/orbits/test_constellations.py \
  --cov=quoss.orbits.constellations --cov-report=term-missing
                                              # 96 % (106/110 sentencias, 36/38 ramas)
```

Sin exclusiones: la deselección de `test_angle_conversion_only_at_the_boundary`
y el `--ignore` de `test_constellations.py` que la entrada 16 necesitó durante
el desarrollo en paralelo ya no hacen falta — las dos únicas llamadas a
`np.rad2deg` que este módulo tenía fuera de un docstring se movieron a
`quoss.core.units.rad_to_deg`, la misma convención que ya sigue `kepler.py`.

**Revisado tras la primera entrega (mismo día):** el `rtol` de `brentq` era un
literal sin explicar, `8.881784197001252e-16` — exactamente `4 * eps`, el
mínimo que `scipy.optimize.brentq` acepta, pero escrito como si fuera un
número elegido en vez de un límite del solver. Se reemplazó por
`_BRENTQ_RTOL = 4.0 * np.finfo(np.float64).eps`, con docstring, siguiendo la
misma disciplina que `_BRENTQ_XTOL_KM` y `_BRACKET_RELATIVE_HALF_WIDTH` ya
tenían al lado. De 91 % a 96 % de cobertura en `constellations.py`: tres
ramas de `DomainError` sin ejercitar (`mu_km3_s2`/`r_equatorial_km`/`j2`
inválidos y longitudes que no hacen broadcast en
`sun_synchronous_inclination_rad`, y excentricidad fuera de rango en
`repeat_ground_track_semi_major_axis_km`) ganaron test. Quedan sin cubrir
`_resonance_residual_rad_s == 0.0` exactamente en un extremo del corchete —
una coincidencia de punto flotante que forzarla a propósito exigiría resolver
primero qué combinación de entradas la produce, y el propio código ya trata
ese caso (asigna el extremo y sigue) en vez de dejarlo caer a `brentq`, así
que no es una rama sin guardia, solo una difícil de alcanzar por accidente.

---

## 18. Etapa 2.2 — `channel/`: `atmosphere.py`, `turbulence.py`, `beam.py`

### Qué hace este paquete, para quien llegue nuevo

`orbits/` termina en la pregunta «¿dónde está el satélite y en qué dirección se
ve?». `channel/` empieza en la siguiente: **de los fotones que salen del
satélite, ¿cuántos llegan al detector, y cuántas cuentas que no son señal
llegan con ellos?**. Y hay una razón por la que este paquete se construye con
más ceremonia que `orbits/`: aquí **nadie puede detectar a ojo que 45 dB
debería ser 39 dB**. En órbitas, un error de marco de referencia produce un
satélite en Australia cuando debía estar en Cataluña; en el canal produce un
número plausible.

Tres módulos escritos hasta ahora, en orden de dependencia:

- **`atmosphere.py`** — el perfil `C_n²(h)`: cuánta turbulencia hay a cada
  altura, más la malla de integración de la ITU y la refracción. Todo lo que el
  canal dice sobre turbulencia sale de integrales de este perfil.
- **`turbulence.py`** — qué le hace ese perfil a un haz que lo cruza en
  diagonal: escintilación (el centelleo, y la razón de que el enlace se
  desvanezca), promediado de apertura, parámetro de Fried `r0`, ángulo
  isoplanático.
- **`beam.py`** — la pregunta plana que hay debajo: **cuánta potencia llega**,
  en el vacío, con apuntado perfecto. Es el término más grande del presupuesto
  de enlace, decenas de dB, frente a un par de dB de absorción y otro par de
  escintilación.

La política de citas que gobierna los tres es el
[ADR 0009](../docs/adr/0009-citation-policy.md), y su decisión de fondo es que
**la referencia canónica del canal (Andrews & Phillips) no se cita por número
de ecuación porque no se pudo abrir**. Las fuentes primarias son ITU-R P.1621-2
y P.1622 (gratuitas, numeradas, con tablas de valores) y Ntanos et al. 2021
(*Photonics* 8(12):544, acceso abierto).

### 18.1 Lo que la verificación cazó en `atmosphere.py` y `turbulence.py`

Tres cosas, y son el argumento de por qué esta etapa va despacio. Ninguna la
habría detectado una aserción de rango: las tres devuelven números del tamaño
correcto.

| # | Qué | Por qué es silencioso |
|---|---|---|
| 1 | La **Ec. (7) de P.1621-2 da grosores de capa, no altitudes**. La recomendación es explícita («layer thickness or integration step size in height should increase exponentially, from 0.001 km at the lowest layer to 1 km at an altitude of 20 km»), y las altitudes son la suma acumulada | Leerlas como altitudes pone el techo de la atmósfera en **992 m** en vez de 20 km. El perfil sigue siendo decreciente, el integral sigue siendo positivo, y ningún número resultante parece raro |
| 2 | La **Ec. (3) de P.1621-2 no vale 1 en sus propias condiciones de referencia** — se desvía **140 ppm**. Es una inconsistencia interna de la recomendación, no un error de transcripción | Es demasiado pequeña para verse y demasiado grande para ser redondeo. Ahora está documentada y **fijada por un test**, así que si alguien «arregla» la fórmula el test dice que la fuente dice otra cosa |
| 3 | Un bug propio: el coeficiente **1.1e7 de la Ec. (7) de P.1622 está escrito para micrómetros**, no metros, porque `(1e6)^(7/6) = 1e7` exactamente | Con metros, un telescopio de 1 m suprimía la escintilación por un factor **2e9** — físicamente imposible — y devolvía un número entre 0 y 1 que ninguna aserción de rango habría cuestionado. Lo cazó un doctest, y lo fija ahora la **escala de Fresnel**: el promediado tiene que arrancar cuando la apertura supera `sqrt(lambda L)` ≈ 11 cm |

El V2 más fuerte del canal hasta ahora sigue siendo la **Tabla 2 de P.1622**:
sus ocho varianzas de log-irradiancia (cuatro longitudes de onda × dos vientos)
se reproducen a la precisión impresa, con todas las condiciones que la
recomendación declara.

### 18.2 `beam.py` — qué hace y con qué se cierra

Tres cantidades:

- **`divergence_half_angle_rad`** — cuánto se abre el haz. La luz no se
  colima perfectamente: la difracción en la apertura de transmisión fuerza una
  apertura angular de «longitud de onda partido por diámetro», así que un
  transmisor **más grande** da un haz **más estrecho**.
- **`geometric_transmittance`** — la fracción de la potencia transmitida que
  entra en la apertura de recepción. Estas son las decenas de dB.
- **`uplink_beam_wander_*`** — el vaivén («beam wander»): la turbulencia cerca
  del transmisor inclina el haz **entero**, así que su centro pasea alrededor
  del punto de mira en vez de quedarse en él. Es **solo de subida**, por una
  razón que P.1622 §4.3 dice literalmente, y los nombres lo llevan escrito.

V2 contra Ntanos et al. Ecs. (3)–(6) y P.1622 Ecs. (11a)/(11b); V1 en
exponentes, cotas y monotonías; **sin V3** (declarado en
`tests/golden/README.md`).

### 18.3 Decisión 1 — la integral de truncación gaussiana, no el producto de ganancias publicado

**Qué es.** La literatura de FSO escribe el acoplamiento geométrico como un
producto de tres factores de radio: ganancia de transmisión × ganancia de
recepción × pérdida de espacio libre (Ntanos et al. Ecs. (3) y (5)). QuOSS no
lo usa. Usa la integral exacta de una gaussiana sobre un círculo:

```
eta_geo = 1 - exp(-2 a^2 / W^2) = 1 - exp(-D_r^2 / (2 W^2))
```

donde `W` es el radio del haz a `1/e²` (el radio donde la irradiancia ha caído
al 13.5 % del valor en el eje; dentro va el 86.5 % de la potencia) y `a` el
radio de la apertura receptora.

**Por qué así.** Las dos formas **son la misma física**, y eso está asertado,
no supuesto: el producto de ganancias es exactamente el **límite de apertura
pequeña** de la integral, hasta el último dígito. La diferencia es qué pasa
cuando la apertura *no* es pequeña. El producto linealizado **pasa de 1 sin
protestar** — es decir, promete recoger más luz de la que se transmitió — y la
integral satura en 1, que es lo que hace un telescopio que ya captó todo el
haz. Además la integral es la conservadora: donde difieren, da más pérdida.

**Y aquí la verificación encontró algo, que es el tercer «no cuadra» de este
paper** (los otros dos ya estaban en el ADR 0009). Ntanos et al. Ec. (5)
imprime la ganancia de transmisión como `G_t = (8/w_0)²`. Con la forma estándar
de antena óptica, `G_t = 8/w_0²`, el producto reproduce la integral gaussiana
al último dígito. **Tal como está impresa es 8 veces mayor: 9.03 dB
optimista.** Y no hace falta un presupuesto de enlace ni una opinión para saber
cuál de las dos lecturas se quiso: con los propios parámetros del paper — 0.15 m
de transmisor, 2.3 m de receptor, 600 km, 1550 nm — la forma impresa devuelve
una transmitancia de **1.36**, más luz recogida que transmitida.

**Medido en este repo** (`tests/channel/test_beam.py::TestPublishedGainProduct`,
y el enlace de referencia del propio paper):

| Receptor | `eta_geo` (esta forma) | Pérdida | Producto impreso `(8/w_0)²` |
|---|---|---|---|
| 0.75 m | 0.01788 | **17.48 dB** | 0.144 → 8.41 dB |
| 1.3 m | 0.05278 | 12.78 dB | 0.434 → 3.63 dB |
| 2.3 m | 0.15610 | **8.07 dB** | **1.36 → −1.33 dB (imposible)** |

Corroboración indirecta, etiquetada como tal porque el paper no tabula sus
términos: su §4.2.1 dice que la pérdida total a 600 km «can get as low as 20 dB
in total» con un telescopio grande. Sumando solo las pérdidas fijas que el
propio paper declara (detectores al 85 %, receptor 2.65 dB, filtro 3 dB,
polarización 0.3 dB = 6.66 dB) más los 8.07 dB de esta forma, salen 14.7 dB y
quedan ~5 dB para absorción, escintilación y apuntado — que el paper sí modela.
Con la forma impresa el término geométrico es **negativo** y no hay atmósfera
que cierre un hueco de 15 dB.

### 18.4 Decisión 2 — `W(z)` gaussiano exacto, no el atajo de campo lejano

**Qué es.** Todo el mundo escribe `W = theta_div · z`. `beam_radius_m` usa la
hipérbola exacta, `W(z) = w_t sqrt(1 + (z/z_R)²)`, donde `z_R = pi w_t²/lambda`
es la **distancia de Rayleigh**: donde el haz ha crecido `sqrt(2)` veces su
cintura, y la frontera entre «el haz todavía mide como el telescopio» (campo
cercano) y «el haz crece proporcional a la distancia» (campo lejano).

**Por qué así.** No porque el atajo esté mal en este régimen — está bien — sino
porque cuesta una raíz cuadrada y convierte una afirmación («campo lejano,
obviamente») en un número comprobable. Y el signo del error importa: la
hipérbola está **siempre por encima** de su asíntota, así que el atajo siempre
sobreestima la potencia recogida.

**Medido en este repo** (`TestBeamRadiusInvariants`, terminal de 15 cm a
1550 nm): el atajo se queda corto **1.8e-4 relativo a 600 km**, 6.5e-3 a
100 km, y un factor `sqrt(2)` en la propia distancia de Rayleigh (11.4 km),
donde ya no describe un haz. 1.8e-4 en radio son 3.6e-4 en potencia, 0.0016 dB
— el atajo habría sido defendible; lo que cambia es que ahora la cifra está en
un test y no en la memoria de nadie.

Como subproducto, la simetría de campo lejano «da igual doblar el transmisor o
el receptor, el acoplamiento depende del producto `D_T·D_r`» **se rompe al
5.4e-3** cambiando 0.30 m de transmisor por 0.10 m de receptor — y ese número
no es holgura de la tolerancia: es exactamente el término de campo cercano,
`(z_R/z)²`, que crece como `D_T²` y por tanto es dieciséis veces mayor para el
transmisor de 0.30 m. El test predice la desviación desde las dos distancias de
Rayleigh en vez de ensanchar la tolerancia hasta que pase.

### 18.5 Decisión 3 — el vaivén es solo de subida, y la apertura tira para los dos lados

**Qué es.** P.1622 §4.3, literal: «Beam wander is significant in the
Earth-to-space direction and can be on the order of a beamwidth», y «Beam
wander is not a significant problem in the space-to-Earth direction. Beams
travelling in this direction only propagate through turbulence in the final 10
to 20 km of the path». Un haz de bajada llega ya con varios metros de ancho, así
que inclinar los últimos 20 km de su camino lo mueve centímetros.

**Por qué así (la forma del API).** Misma disciplina que
`uplink_log_irradiance_variance` en `turbulence.py`: los nombres llevan
`uplink_`, y `geometric_transmittance` **no acepta elevación, ni turbulencia,
ni un término de vaivén** — no hay dónde meterlo, así que colarlo en un
presupuesto de bajada tendría que ser una línea nueva y visible en el diff, no
un parámetro por defecto (`test_the_downlink_functions_have_nowhere_to_put_a_wander`).

**La conclusión de diseño que no es obvia, y que sí se mide aquí.** Agrandar el
telescopio transmisor estrecha el haz como `1/D_T`, que es toda la razón para
querer un telescopio grande. Pero reduce el vaivén solo como `D_T^(-1/6)`,
porque el vaivén es la inclinación del frente de onda promediada sobre la
apertura, y promediar sobre más apertura quita inclinación despacio. Así que la
razón **vaivén/divergencia crece como `D_T^(5/6)`**: estrechar el haz no ayuda
a una subida más allá del punto en que el haz es más fino que su propio
temblor.

Medido a 1550 nm, perfil ITU nominal, cenit
(`TestTheTransmitApertureCutsBothWays`):

| `D_T` | divergencia (semiángulo) | vaivén r.m.s. | vaivén/divergencia |
|---|---|---|---|
| 5 cm | 19.7 µrad | 5.12 µrad | 0.26 |
| 15 cm | 6.58 µrad | 4.27 µrad | 0.65 |
| 1 m | 0.99 µrad | 3.11 µrad | **3.15** |

Un transmisor de subida de clase metro se pasa la mayor parte del tiempo
apuntando su haz a otro sitio, y ninguna cantidad de apertura extra lo arregla.
Es también la frase en prosa de la ITU («on the order of a beamwidth»)
convertida en número: 2.56 m de desplazamiento r.m.s. a 600 km contra un radio
de haz de 3.95 m, o sea 0.65 anchos de haz al cenit, cruzando el ancho de haz a
20° de elevación.

Por eso existe `uplink_wander_to_divergence_ratio`, que es la única función del
módulo que toma un `DegradationLog`: al pasar de 1, el enlace ha dejado de ser
un nivel y es un proceso de desvanecimiento, y `geometric_transmittance` —que
supone el haz centrado en el receptor— está contestando una pregunta que nadie
hizo. La cifra devuelta no cambia; lo que cambia es que el llamante se entera.

### 18.6 Lo que `beam.py` deja fuera, declarado

- **Ensanchamiento por turbulencia**, y por autoridad de la propia fuente:
  P.1622 §4.4 dice que «is typically very small with respect to divergence and
  does not account for an appreciable loss of signal in either the
  Earth-to-space or space-to-Earth directions». El radio del haz es por tanto
  el de difracción en vacío, y eso es una decisión citada, no un término
  olvidado.
- **Los 0.63 dB del truncamiento en el transmisor.** Tomar la cintura del haz
  como `w_t = D_T/2` (lo que implica la Ec. (6) de Ntanos et al.) significa que
  la propia apertura del transmisor recorta las colas de la gaussiana: sale el
  `1 - exp(-2) = 86.5 %`. Toda transmitancia de este módulo es una fracción **de
  la potencia que hay en el haz**, no de la que hay en el láser. Es un número
  fijo, va donde se juntan las pérdidas fijas, y ese sitio es `link_budget.py`.
- **Error de apuntado y su desvanecimiento** → `pointing.py`, el módulo
  siguiente. El vaivén es la turbulencia moviendo el haz; el error de apuntado
  es el terminal apuntándolo mal. Y el equivalente de bajada del vaivén —la
  turbulencia moviendo el frente de onda **que llega**, P.1622 Ec. (10)— también
  va ahí, porque lo que perturba es el lazo de seguimiento, no el ancho del haz.
- **La discrepancia interna de P.1622 que no se toca.** Su Ec. (10) da la
  varianza del ángulo de llegada como `2.914·mu·D_R^(-1/3)/sin(theta)`; elevar
  al cuadrado el 2.08 de la Ec. (11b) da `4.326·mu·D_T^(-1/3)/sin(theta)` — la
  misma forma con una constante **1.485 veces mayor**. La explicación plausible
  (la Ec. (10) es una onda plana llenando la apertura, la (11b) un haz estrecho
  saliendo de ella) **no está escrita en la recomendación**, así que las dos se
  transcriben tal cual y ninguna se usa para «corregir» a la otra.

### 18.7 `channel/_validation.py` — por qué aparece ahora

Tres argumentos se repiten en todo el paquete (elevación, longitud de onda,
apertura) y cada uno tiene **su** forma característica de llegar mal: la
elevación llega en grados o por debajo del horizonte (`look_angles` la reporta
sin filtrar, a propósito), la longitud de onda llega en nanómetros, la apertura
en centímetros. Los mensajes de error son la documentación en el punto de
fallo, así que tenerlos idénticos en todas partes es el objetivo, y para eso
hay un solo sitio donde se escriben.

Mismo patrón y misma justificación que `orbits/_validation.py`: se extrae
cuando aparece la segunda copia y la tercera ya está a la vista
(`pointing.py`). `turbulence.py` pasa a usarlo sin cambiar **ni un byte** de
sus mensajes, que es lo que hace que sus tests de validación sigan siendo la
prueba de que no cambió nada.

---

## 19. `channel/pointing.py` — el desvanecimiento por jitter, que es una distribución y no un número

### Qué hace este módulo, para quien llegue nuevo

`beam.py` calcula cuánta potencia entra en el telescopio cuando el haz apunta
**exactamente** a él. Nada apunta exactamente. Un terminal de satélite sigue una
estación en movimiento con cardanes y un espejo rápido contra un sensor de
estrellas, y lo que queda cuando el lazo de control ha hecho lo que puede es un
error angular residual de un microradián y pico, que **se mueve en el tiempo**.

Y ahí está la razón de que este módulo devuelva una distribución y no una
cifra: el error es aleatorio, así que el enlace pasa una fracción de su tiempo
mucho más desapuntado que su media — y un enlace QKD se juzga por sus malos
momentos, no por su promedio. Medido en la geometría de referencia de este repo
(0.75 µrad de jitter, 600 km): la pérdida **media** son 0.22 dB y la pérdida
que se supera 1 vez de cada 100 son **1.03 dB**, casi cinco veces más. Con
2 µrad la media pasa a 1.35 dB y la cola a **7.32 dB**. Diseñar con la media es
diseñar para un enlace que no existe.

**Apuntado no es vaivén**, y por eso están en módulos distintos: el vaivén
(`beam.uplink_beam_wander_angle_rad`) es la **turbulencia** inclinando el haz, lo
manda `C_n²` y solo ocurre de subida; el error de apuntado es el **terminal**
apuntando mal, es una propiedad del hardware y ocurre en las dos direcciones. Se
suman en cuadratura si son independientes, y por eso el módulo toma el jitter
**total** como argumento en vez de calcularlo: el que quiera los dos pasa la
raíz de la suma de cuadrados y lo dice.

### 19.1 La trampa que da forma al módulo — 17.5 dB contados dos veces

**Qué es.** La Ec. (9) de Farid & Hranilovic escribe la fracción recogida con un
desplazamiento `r` como

```
h_p(r) = A_0 · exp(-2 r² / w_zeq²)
```

y ese `A_0` —el valor en `r = 0`— **es** el acoplamiento geométrico, la misma
cantidad que devuelve `beam.geometric_transmittance`.

**Por qué importa.** Un presupuesto de enlace que multiplica «la pérdida
geométrica» por «la pérdida de apuntado», tomando la de apuntado como el `h_p`
publicado, cuenta `A_0` **dos veces**. En la geometría de referencia `A_0` vale
0.0179, así que son **17.5 dB de pérdida inventados de la nada** — y el total
equivocado (35 dB) es tan plausible a la vista como el correcto (17.6 dB). Es
exactamente el modo de fallo que el README describe: un número plausible y
equivocado.

**Cómo se cierra.** No con un comentario, con la forma del API: **todas** las
funciones del módulo devuelven el factor **relativo**, el `exp` solo,
normalizado a exactamente 1 con apuntado perfecto. La regla queda escrita en el
docstring como una línea:

```
total = beam.geometric_transmittance(...) × pointing.<lo que sea>
```

y `tests/channel/test_pointing.py::TestTheDoubleCountingTrap` mide los 17.48 dB
que la forma del API impide, más la aserción de que el apuntado perfecto
devuelve **exactamente** 1.0 (no 0.9999), que es lo que hace seguro
multiplicar.

### 19.2 Por qué la ley de desvanecimiento es una ley de potencias

**Qué es.** La derivación completa cabe en tres líneas y está en el docstring
del módulo, porque la forma del resultado no es obvia y saberla de memoria no
sirve. Con `x = h_p/A_0` el factor relativo:

1. `x = exp(-2r²/w_zeq²)`, luego `r² = -(w_zeq²/2)·ln x`.
2. El error radial `r` es el módulo de un vector con dos componentes gaussianas
   independientes de media cero (una en elevación, otra en cruz-elevación), y eso
   es **Rayleigh**: `P(r ≥ R) = exp(-R²/2σ_s²)` (Ec. (10) de la fuente).
3. Como `x` decrece con `r`, «estar por debajo de `x`» y «estar más allá del
   radio correspondiente» son el mismo suceso:

```
F(x) = P(r ≥ r(x)) = exp( (w_zeq²/4σ_s²)·ln x ) = x^(gamma²),  gamma = w_zeq/(2σ_s)
```

**Por qué importa.** Un solo parámetro adimensional, y es interpretable: `gamma`
es **el radio del haz medido en jitters**. Todo lo demás del módulo sale de esa
línea — la media es `gamma²/(gamma²+1)`, el cuantil es `p^(1/gamma²)` — así que
si esa línea está mal, todo lo está, y por eso tiene su propio test: un sorteo
Monte Carlo de 200 000 pares de gaussianas empujados por la Ec. (9), contra la
ley analítica, con **tolerancia derivada y no elegida** (cuatro errores estándar
binomiales, `sqrt(p(1-p)/n)`, que escala sola sobre los cinco niveles
comprobados aunque sus probabilidades vayan de 4.9e-5 a 0.82). Poner `gamma` en
vez de `gamma²` en el exponente falla por cientos de sigmas, y **pasa todos los
tests contra valores publicados**.

### 19.3 Dos fuentes independientes, y concuerdan

| Fuente | Cómo lo escribe | Variables |
|---|---|---|
| Farid & Hranilovic 2007, Ec. (11) | `gamma² = (w_zeq/2σ_s)²` | **longitudes** en el plano del receptor |
| Ntanos et al. 2021, Ec. (9) | `beta_p = (theta_div/2σ_p)²` | **ángulos** |

Son la misma razón dividida arriba y abajo por la distancia, salvo que Ntanos
usa la divergencia lisa donde Farid usa la equivalente, que lleva la corrección
por el tamaño finito de la apertura receptora.

**Medido:** `gamma² = 19.42` contra `beta_p = 19.23`. Un 1 %, que son **0.01 dB**
en la pérdida al 1 % de outage (1.030 dB contra 1.040 dB). Dos papers, catorce
años y dos notaciones aparte, concordando a la centésima de decibelio.

Y el residuo está **atribuido, no tolerado**: el test aserta que el cociente
`gamma²/beta_p` es *exactamente* `(w_zeq/(theta_div·z))²`, la corrección de
apertura, con `rel=1e-12`. Un 1 % de acuerdo se podría haber conseguido con dos
fórmulas distintas que casualmente casan; que el residuo sea exactamente la
corrección de apertura no.

### 19.4 El oráculo exacto, y lo que dijo

El paper imprime **las dos**: la fracción recogida exacta (Ec. (8), una integral
doble sobre el área del detector desplazado) y la forma cerrada que el módulo
usa (Ec. (9)). Así que la aproximación central del módulo es comprobable en vez
de heredada: `tests/channel/test_pointing.py::TestAgainstTheExactIntegral`
integra la Ec. (8) numéricamente con `scipy.integrate.quad` —oráculo en proceso
que no hace falta congelar, mismo argumento que el DOP853 de
`perturbations.py`— y mide la cerrada contra ella. Tres cosas salieron:

1. **La Ec. (8) en `r = 0` es exactamente la fórmula de `beam.py`.** Concuerdan
   a ocho dígitos, porque son la misma integral. Es una **segunda fuente
   publicada e independiente** para el acoplamiento geométrico: la primera fue
   el producto de ganancias de Ntanos, por la ruta de las ganancias de antena;
   esta llega por una integral de superficie. Dos papers, catorce años, el mismo
   número.
2. **El `A_0 = erf(v)²` publicado es él mismo una aproximación**, y QuOSS no la
   usa. El valor exacto es `1 − exp(−2a²/W²)`; se diferencian en **−4.2e-4**
   (0.0018 dB) en la geometría de referencia y −3.6e-3 en la estación de 2.3 m.
   Se queda el exacto, así que los dos módulos multiplican al acoplamiento
   exacto en `r = 0` y no al ajuste.
3. **La condición de validez que los autores publican falla para el telescopio
   grande del sistema de referencia.** Dicen «good agreement when `w_z/a > 6`»;
   un telescopio de 2.3 m a 600 km da `W/a = 3.4`. Y es justo la configuración
   para la que Ntanos reporta su mejor presupuesto de enlace, así que un modelo
   que se callara ahí se callaría exactamente donde importa. `warnings[]`, no
   silencio.

   **Con la medida al lado, porque «fuera del rango publicado» y «equivocado» no
   son la misma afirmación:** contra la integral exacta, la forma cerrada sigue
   dentro del **0.36 %** sobre los desplazamientos que un jitter de 0.75 µrad
   produce de verdad (más allá de cuatro sigmas queda 3.4e-4 de la
   distribución), dentro del 0.7 % hasta un radio de haz entero, y solo se
   rompe en la cola profunda — 8 % a dos radios, 35 % a tres. Esa cola se
   alcanza con probabilidad ~1e-17 al jitter de referencia. O sea: **importa
   cuando el jitter se acerca al radio del haz, y no importa cuando no**. El
   mensaje del aviso dice cómo distinguir los dos casos.

**Lo que no se reprodujo, declarado:** la **Tabla I** del paper, que imprime el
NMSE entre sus Ecs. (8) y (9) para seis valores de `W/a`. No declara ni el rango
de promediado sobre el desplazamiento ni la normalización, y ninguna convención
plausible reproduce las cifras impresas —los intentos caen entre 100 y 1000
veces por debajo—, además de que sus dos últimas entradas (0.159e-3 y 0.153e-3)
casi no se diferencian, que es a lo que se parece un suelo numérico y no una
tendencia. Lo que sí se aserta es **la afirmación que la tabla sostiene**: el
error decrece monótonamente al crecer `W/a`, del 46 % en `W/a = 2` al 0.2 % en
12, medido contra la Ec. (8).

### 19.5 Decisiones menores que no lo son

| Decisión | Por qué |
|---|---|
| **El jitter entra en radianes, no en metros** | La fuente usa `σ_s` como desplazamiento en el plano del receptor; la especificación de un terminal es angular. Se convierte en la entrada (`σ_s = jitter_rad × distancia`), y como el radio del haz también crece con la distancia, **`gamma` es casi constante a lo largo de un pase** — 0.5 % de variación sobre un factor cuatro en distancia, contra un factor 3 del acoplamiento geométrico. Es el único término del canal que no depende del pase, y saberlo antes de graficarlo ahorra buscar un bug que no existe |
| **`jitter_rad = 0` es un `DomainError`, no «apuntado perfecto»** | El exponente `gamma²` diverge ahí. Y la respuesta que el llamante quiere en ese caso ya existe con otro nombre: es `beam.geometric_transmittance`, el valor de este modelo en desplazamiento cero. El mensaje lo dice |
| **`probability` es escalar, no array** | Es una decisión de diseño («¿qué outage estoy dispuesto a aceptar?»), no una cantidad por muestra. Aceptar un array invitaría a indexarlo contra el eje temporal, con el que no comparte nada |
| **La media existe, con su advertencia escrita** | Es la cantidad correcta para una tasa media en una sesión larga y la equivocada para un presupuesto QKD. La distribución está sesgada a la izquierda, así que la media (0.218 dB) queda **por debajo** de la mediana (0.155 dB) y muy por encima de la cola: «peor que lo típico» no es lo mismo que «conservador», y solo el cuantil lo es. El test aserta el orden completo `cola < media < mediana < 1` |
| **No hay generador aleatorio en el módulo** | La función cuantil **es** el muestreador: darle una uniforme es un sorteo exacto por transformada inversa. Así `system/monte_carlo.py` se queda con el único `RandomSource` inyectable del proyecto y este módulo no necesita saber que existe. El test lo comprueba **sobre los imports** (AST), no sobre el texto, porque el docstring nombra `RandomSource` a propósito —para decir dónde vive la aleatoriedad— y un grep marcaría justo la frase que documenta la regla |

### 19.6 Lo que `pointing.py` deja fuera, declarado

- **Boresight distinto de cero.** El modelo supone jitter de media cero: el
  terminal apunta bien en promedio y tiembla alrededor. Un desvío
  **sistemático** (un sensor de estrellas mal calibrado, un sesgo térmico) hace
  que `r` sea Rice y no Rayleigh (Beckmann o Hoyt en la literatura FSO), y **no
  se localizó fuente libre verificada** — es el hueco 3 del
  [ADR 0009](../docs/adr/0009-citation-policy.md). No se aproxima: un boresight
  **conocido** se puede pasar a `pointing_transmittance` como desplazamiento
  determinista, que es exacto, pero la **distribución** con boresight está
  ausente en vez de adivinada.
- **La convolución con la turbulencia.** El estado completo del canal es el
  producto del desvanecimiento por turbulencia y el de apuntado, y su
  distribución es la Ec. (14) de la fuente. Combinarlos es una decisión de
  presupuesto de enlace (qué modelo de turbulencia, qué régimen) y va donde se
  ensamblan los términos.
- **Correlación temporal.** Todo aquí es una distribución **marginal**: dice qué
  fracción del tiempo el enlace está desvanecido, no cuánto rato seguido. El
  error de apuntado tiene tiempos de correlación de milisegundos a decenas de
  milisegundos, que es lo que decide cómo lo ve un bloque de post-proceso QKD.
  Eso es `system/correlated_fading.py`, el AR(1), y es el punto de novedad del
  roadmap — no un olvido de aquí.

---

## 20. `channel/background.py` — la luz que llega cuando no se envió nada

### Qué hace este módulo, para quien llegue nuevo

Un detector de fotón único no distingue un fotón de señal de un fotón de luz
solar dispersada, ni ninguno de los dos de un clic térmico suyo. Todo lo que
entrega son **cuentas**. El resto de `channel/` responde a «qué fracción de los
fotones transmitidos llega»; este módulo responde a la otra mitad —**cuántas
cuentas llegan que no son señal**— para la parte de ese ruido que viene del
cielo y no del detector (el detector es `detector.py`).

El cielo no es un término pequeño, y conviene ver la escala antes de nada. Un
telescopio apuntado a un satélite está también apuntado a unos cuantos cientos
de kilómetros cúbicos de aire iluminado, y ese aire dispersa luz solar hacia la
apertura a lo largo de toda la línea de visión. Medido con el receptor que
declara Ntanos et al. §4.1 (campo de visión 100 µrad, filtro de 0.2 nm,
telescopio de 2.3 m): **7.6e3 cuentas por segundo** en una noche clara sin luna
y **3.4e9 cuentas por segundo** con la luz solar brillante que tabula la
UIT-R a 850 nm. Seis órdenes de magnitud, el mismo telescopio, la misma señal.
Por eso los presupuestos QKD publicados de esta literatura son presupuestos
**nocturnos**, y decirlo es parte del modelo y no una nota al pie.

El módulo tiene tres cantidades en cadena: **radiancia** (lo brillante que está
el cielo, que sale de una tabla y no de una fórmula), **potencia de fondo** (lo
que el receptor recoge, que es la radiancia por las tres cosas que el receptor
elige: ángulo sólido, área y ancho de filtro) y **cuentas por puerta** (la
potencia dividida por la energía de un fotón, por el tiempo que el detector
escucha).

### 20.1 Las dos ecuaciones publicadas son la misma, y no dicen lo mismo

**Qué es.** La Ec. (1) de la Rec. UIT-R P.1621-2 escribe

```
P_back = π θ_r² A_r Δλ H / 4        (θ_r en rad)
```

y la Ec. (19) de Ntanos et al. 2021 escribe

```
P_back = H_rad · Ω_FOV · A_r · Δλ   (Ω_FOV en sr)
```

Son **una sola ecuación**, porque `π θ²/4` *es* el ángulo sólido de un cono de
ángulo completo `θ`. Los tests las transcriben por separado, desde los dos
documentos, y comprueban que coinciden.

**Por qué importa, y aquí está el hallazgo.** Las dos fuentes dan el campo de
visión del receptor **en unidades distintas bajo el mismo nombre**, y Ntanos et
al. declaran su valor como «a narrow FOV of 100 µrad» — un ángulo. Meter
100 µrad en la fórmula que quiere estereorradianes multiplica el fondo por
**1.27e4, que son 41.05 dB**, y produce un número que sigue teniendo pinta de
tasa de cuentas. Y hay una segunda bifurcación más silenciosa: ninguna de las
dos fuentes dice si el FOV es ángulo **completo** o **semiángulo**. Leerlo del
otro modo es un factor cuatro exacto, **6.02 dB** de fondo.

**Cómo se cierra.** El argumento se llama `field_of_view_full_angle_rad`, con la
convención en el nombre y no en un comentario, y la convención se elige con la
aritmética de la propia UIT: `π θ²/4` es el ángulo sólido de pequeño ángulo de
un cono de **semiángulo** `θ/2`, luego su `θ_r` es el ángulo completo. Los dos
errores están medidos en
`tests/channel/test_background.py::TestTheTwoPublishedEquationsAreOne`, y el
guarda de `2π` es lo que atrapa el caso grosero de pasar estereorradianes.

### 20.2 La trampa que da forma al módulo — una media no es una probabilidad

**Qué es.** La Ec. (20) de Ntanos et al. dice

```
P_noise = t_gate × cps_background
```

y llama al resultado «the probability of the detector firing due to a background
noise photon». No es una probabilidad: es el **número esperado** de cuentas de
fondo en la puerta, que solo es una probabilidad mientras sea mucho menor que
uno. Las llegadas de fondo son Poisson, así que la probabilidad de que caiga al
menos una es `1 - exp(-µ)`.

**Por qué importa.** No es una esquina exótica. Con la radiancia de luz solar
brillante que **la propia UIT-R tabula a 850 nm** (122.3 W/m²/µm/sr, la
tabulada más cercana a la banda de 780-810 nm que le interesa a este proyecto),
el receptor de Ntanos et al. y su puerta de 1 ns, la Ec. (20) devuelve una
«probabilidad» de **3.42**. La respuesta correcta es 0.967. Su telescopio
intermedio, el de 1.3 m, devuelve **1.09** — por encima de la unidad, con
parámetros publicados, y sin que ningún paso intermedio parezca raro.

**Cómo se cierra.** Dos funciones con dos nombres:
`background_counts_per_gate` devuelve `µ` y está documentada como una media (es
la cantidad correcta: es el parámetro de Poisson, y es lo que suma linealmente
entre fuentes de ruido independientes antes de que ninguna sea una
probabilidad); `background_click_probability` devuelve `1 - exp(-µ)`.

Y el umbral del aviso **está derivado, no elegido**: leer la media como
probabilidad sobreestima en un factor `µ/(1-exp(-µ))`, que llega al 5 % en
`µ = 0.0984`; la constante `LINEAR_CLICK_PROBABILITY_LIMIT = 0.1` es esa raíz
redondeada a un dígito (donde el exceso es 5.08 %). El test la vuelve a
despejar con `brentq` en vez de creerse la constante.

El aviso es **WARNING y no DEGRADED**, a propósito: no se ha sustituido ningún
modelo, el número devuelto es el exacto. Lo que dice el aviso es el **punto de
operación** — 0.1 cuentas de fondo por puerta es un fotón de ruido cada diez
puertas, y de ahí no sale clave — así que un resultado con ese código en
`warnings[]` describe un enlace que no funciona, no una fórmula que se ha
quedado corta.

### 20.3 El ángulo sólido exacto en vez de la forma publicada

**Qué es.** `receiver_solid_angle_sr` devuelve `2π(1 - cos(θ/2))`, el ángulo
sólido exacto de un cono, del que la forma de la UIT es el límite de ángulo
pequeño.

**Por qué, si la diferencia es invisible.** Porque lo es: a 100 µrad las dos
coinciden a **6.1e-9 relativo**, doce dígitos más allá de lo medible. La razón
de elegir la exacta es la misma que en `beam.py` con la integral de truncación
frente al producto de ganancias: **la aproximación no tiene techo**. Es 1 % alta
a 39.6° de ángulo completo, 5.3 % a 90°, y a 360° devuelve **31.0 sr para una
esfera entera que tiene 4π = 12.6**. Una fórmula que puede informar de dos
esferas y media de cielo no es una que se deje en el camino de un barrido de
parámetros.

### 20.4 El gating temporal — el único parámetro libre del presupuesto de ruido

**Qué es.** Todo lo demás de un presupuesto de enlace lo fija el hardware. El
ancho de la puerta de detección no, y son los decibelios más baratos del canal,
porque los dos términos escalan distinto:

- El **fondo escala linealmente** con la puerta. Mitad de puerta, mitad de
  ruido. Y las cuentas oscuras del detector también, así que estrechar la puerta
  no lo roba ninguna de las dos.
- La **señal no**. Los fotones de señal llegan todos casi al mismo instante
  —dispersados solo por el jitter temporal del detector y el sincronismo— así
  que una puerta de varios jitters de ancho los conserva todos. Solo cuando la
  puerta se acerca al jitter empieza a costar señal, y entonces cuesta como una
  `erf`: `fracción = erf(T/(2√2 σ))`, con `σ = FWHM/2.3548`.

**El ejemplo con números.** Con el jitter de 50 ps que declara Ntanos et al.,
pasar de su puerta de 1 ns a 100 ps recorta el fondo **10.0 dB** y la señal
**0.08 dB**. Si la figura de mérito es la relación limitada por ruido de
disparo `S/√B`, el óptimo es una puerta de **2.80 desviaciones típicas de
jitter** (1.19 FWHM, aquí 59.5 ps), que le gana 5.36 dB a la puerta de 1 ns:
12.26 dB de fondo eliminado por 0.77 dB de señal. El propio paper nombra el
remedio —«short detector gate time opening at Bob station»— sin cuantificarlo;
esto es la cuantificación, y es una derivación V1 del modelo gaussiano de
jitter, no algo publicado.

**Lo que la constante no es.** El óptimo sale de la condición de
estacionariedad `(4/√π) x e^{-x²} = erf(x)`, cuya raíz da
`2√2 x* = 2.799970553756`. **No es 2.8**: difiere en la quinta decimal, el
parecido es una casualidad de la notación decimal y no hay ninguna identidad
detrás. Está escrito con todos los dígitos y hay un test que lo dice, porque un
número casi redondo sin vigilancia se convierte en «el óptimo es exactamente
2.8σ» en un docstring posterior, y en una derivación que nadie puede reproducir.

**Y lo que la figura de mérito no dice.** `S/√B` es la figura de mérito de una
medida limitada por su propio ruido de disparo, no de un protocolo QKD, cuyo
objetivo es una tasa de clave secreta y vive en `qkd/`. Las dos afirmaciones que
sobreviven al cambio de objetivo están asertadas: la **razón** fondo/señal
`x/erf(x)` es monótona creciente (así que estrechar siempre mejora el QBER, y no
hay óptimo interior para ese objetivo), y el óptimo de `S/√B` es **ancho** —
cualquier puerta entre 1.5σ y 5σ está a 0.55 dB del mejor, medido.

También está medida la trampa de unidades del jitter: leer los 50 ps de FWHM
como si fueran `σ` da 0.4478 en vez de 0.8385 en la puerta óptima, **2.72 dB**
de error en dirección **pesimista** — que es justo por lo que sobreviviría a una
revisión, porque un presupuesto demasiado conservador parece cuidadoso.

### 20.5 Las fuentes discrepan de noche por un factor diez, y se mide qué cuesta

**Qué es.** La P.1621-2 §3.1 dice que «a reasonable value of H during
night-time operations is (1-2)·10⁻⁶ W/m²/µm/sr for most frequencies of
interest». Ntanos et al. ponen la noche clara sin luna en **1.5e-5** a 1550 nm.
Misma cantidad, dos fuentes abiertas, un **factor diez**.

**Cómo se cierra.** Igual que la discrepancia de los coeficientes de Bufton en
`atmosphere.py`: las dos se exponen como constantes con nombre y con su fuente
(`ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR`,
`NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR`), **ninguna es un defecto**, y la
discrepancia se mide en vez de promediarse.

**Y lo que cuesta depende del telescopio**, que es la parte que sirve para
decidir. Contra las 300 cps de cuentas oscuras que declara el mismo paper para
sus detectores, las dos radiancias candidatas dan **1.24x** de ruido total a
0.75 m —el cielo está por debajo del propio detector en los dos casos— y
**2.83x** a 2.3 m, donde el cielo ya manda. Así que la discrepancia no hace
falta resolverla para diseñar una estación de 0.75 m, y sí hace falta para
fiarse de una de 2.3 m — que es exactamente la estación de la que ese paper
reporta su mejor presupuesto.

De día, en cambio, **las dos fuentes concuerdan**, y eso también se aserta: la
columna de 1500 nm de la Tabla 1 da 6.00 (sol normal) y 4.44 (cubierto), y el
rango de día despejado de Ntanos et al. a 1550 nm es 0.1 a 6.

### 20.6 El hueco 4 del ADR 0009, ahora con la medida al lado

**Qué era.** «Radiancia de cielo a 785 y 810 nm»: la Tabla 1 tabula 530, 850,
965, 1060 y 1500 nm, e interpolar entre ellos y presentarlo como valor publicado
sería inventar un V2.

**Qué se ha hecho.** Dos funciones, no una:
`tabulated_sky_radiance_w_m2_um_sr` **rechaza** cualquier longitud de onda que no
esté en la rejilla (con un `DomainError` que nombra las cinco y la alternativa),
y `interpolated_sky_radiance_w_m2_um_sr` interpola y **registra un DEGRADED**
cuando lo hace, con el valor de la regla alternativa dentro del propio registro.
Nada se registra si la longitud de onda sí está tabulada, porque entonces el
valor **es** publicado y diluir la bandera la haría inútil.

**Y el tamaño del hueco está medido, que es lo nuevo.** Dos reglas defendibles
—ley de potencias en log-log y lineal en λ— difieren **0.48 dB a 785 nm** y
0.33 dB a 810 nm. Pero lo que importa es que **la precisión medida es peor que
esa diferencia**: quitar uno de los puntos interiores de la tabla y predecirlo
desde sus dos vecinos falla entre **16 % y 27 %** con la regla que usa el módulo
(y entre 2 % y 32 % con la lineal), porque dentro de la rejilla está la banda de
vapor de agua de 940 nm y la columna de sol normal **ni siquiera es monótona**
ahí (25.12 a 965 nm y 25.32 a 1060 nm; hay un test que lo aserta como control
negativo de la transcripción). Así que una radiancia interpolada es un número
con del orden de un decibelio de error no cuantificado: se puede usar, y no se
puede llamar publicada.

Con dos cautelas escritas en el propio test, porque callarlas sería la versión
de segundo orden del mismo error: los tramos medidos son **más anchos** que el
que contiene a 785 nm, y todos contienen la banda de 940 nm, que es el peor caso
de la rejilla. La tabla **no tiene ningún punto interior entre 530 y 850 nm**,
así que el error de interpolación *ahí* no se puede medir con la tabla — solo
acotar por analogía.

La extrapolación se **rechaza** en vez de saturarse, y ese guarda tiene un
motivo concreto: `numpy.interp` devuelve el valor del extremo fuera de la
rejilla **sin queja**, así que pedir 400 nm —donde el cielo es más brillante que
en cualquier punto tabulado, porque el espectro solar tiene su máximo cerca de
500 nm— devolvería el valor de 530 nm, en la dirección insegura y con pinta de
consulta a tabla.

### 20.7 Lo que la Tabla 1 promete y no trae: la radiancia de la Tierra

**Qué es.** El título de la Tabla 1 es «Radiance, H (W/m²/µm/sr), of the sky
**and Earth** for several frequencies», y la tabla imprime **solo** las tres
columnas de cielo. Las columnas de Tierra que anuncia el título no están en la
recomendación, aunque su §3.1 sí dice explícitamente que «spacecraft pointed at
the Earth will also encounter noise from sunlight reflected from the Earth's
surface».

**Consecuencia, declarada y no rellenada.** Un receptor en el satélite mirando
una Tierra iluminada **no tiene radiancia publicada** en ninguna de las dos
fuentes, así que aquí no hay fondo de subida. Ntanos et al. consideran solo
bajada. Es un hueco nuevo del ADR 0009, y es de la misma familia que la Ec. (3)
de la misma recomendación que no vale 1 en sus propias condiciones de
referencia: inconsistencias internas de una fuente que se ha abierto, que es lo
que se encuentra cuando se abre.

### 20.8 La afirmación de los 10 kcps, no reproducible

**Qué es.** Ntanos et al. §4.2.2 añaden una consecuencia comprobable de su
propia Ec. (19): «even in the case of full moon, the background radiance
corresponds to 10 kcps in the photon counter at most».

**Qué da la ecuación con sus propios parámetros.** 8.1 kcps con el telescopio de
0.75 m, 24.4 kcps con el de 1.3 m y **76.4 kcps** con el de 2.3 m. La frase no
dice cuál de sus tres telescopios, y «at most» apunta al grande, que es el que
falla por **7.6x**. El rescate obvio tampoco cierra: aplicando las pérdidas que
la misma sección declara (3 dB de inserción del filtro, 2.65 dB del receptor,
85 % de eficiencia) el de 2.3 m da 17.7 kcps, todavía 1.8x por encima.

**Cómo se cierra.** Declarada como hueco, con los tres candidatos asertados en
`TestTheFullMoonClaim`, para que quien vuelva vea qué lectura necesitaría la
frase. Es el mismo patrón que la Tabla I de Farid & Hranilovic en `pointing.py`:
un V2 cuyo valor absoluto no cierra sigue siendo información, pero solo si se
declara cuál de sus afirmaciones se está usando.

### 20.9 Una corrección al propio ADR 0009

La tabla de fuentes verificadas del [ADR 0009](../docs/adr/0009-citation-policy.md)
situaba la radiancia de cielo y la potencia de fondo en «ITU-R P.1621-2 §4,
Tabla 1». **Están en §3.1** (Rayleigh scattering); el §4 de esa recomendación es
refracción. Corregido allí. Lo digo aquí porque el ADR 0009 es precisamente el
documento que exige que una cita lleve al sitio exacto, y una sección equivocada
en él es del tipo de error que ese ADR existe para no cometer.

### 20.10 Decisiones menores que no lo son

| Decisión | Por qué |
|---|---|
| **La radiancia va en W/m²/µm/sr y el ancho de filtro en metros** | Convención mixta a propósito. El ancho de filtro es una longitud óptica y va en metros por el [ADR 0001](../docs/adr/0001-unit-conventions.md); la radiancia es un **valor de tabla transcrito** y conserva la unidad en la que está publicada, para que un lector que compare 122.3 contra la página de la UIT vea el mismo número. La conversión ocurre en un solo sitio (`MICROMETRES_PER_METRE`, ya existente) y la unidad va en el nombre del argumento, así que la mezcla no puede ser silenciosa |
| **La radiancia es el argumento vectorizado** | Es la única entrada que legítimamente varía a lo largo de un pase (el sol se mueve, la línea de visión barre el cielo). El FOV, la apertura y el filtro son propiedades del instrumento y son escalares |
| **`SkyCondition` no tiene miembro `NIGHT`** | El valor nocturno tiene otra procedencia: es prosa, no tabla, no está resuelto en longitud de onda, y las dos fuentes discrepan por un factor diez. Un cuarto miembro haría que la misma llamada devolviera números de dos pedigríes distintos. Son constantes separadas, una por fuente, y así el llamante **elige** |
| **La radiancia cero se acepta; la negativa es `DomainError`** | Cero es el límite exacto de «sin fondo» y no divide por nada. Una radiancia negativa no es un cielo oscuro, es un error de signo. El mensaje además nombra la trampa de unidades: por **micrómetro**, no por nanómetro, que es un factor 1000 |
| **`-expm1(-µ)` y no `1 - exp(-µ)`** | Con la media nocturna de referencia (7.6e-6 cuentas por puerta) la forma ingenua cancela los dígitos de cabeza de dos números que coinciden en la sexta decimal y pierde unos diez bits. Hay un test que compara las dos contra la serie exacta |
| **La cadena óptica no se aplica aquí** | La pérdida de inserción del filtro, la del receptor y la eficiencia cuántica atenúan el fondo **exactamente igual** que la señal, así que se cancelan en cualquier razón y se aplican una sola vez en `detector.py`/`link_budget.py`. Aplicarlas también aquí es el mismo error de doble cuenta que da forma a `pointing.py` |
| **Ninguna función acepta una elevación** | Y hay un test que lo aserta *por ausencia*, recorriendo las firmas. La radiancia depende de a dónde apunte el telescopio —la Tabla 1 es radiancia **cenital** y a 20° de elevación el camino de dispersión son 2.92 masas de aire, que serían 4.66 dB si la radiancia siguiera a la masa de aire— pero **ninguna de las dos fuentes publica esa dependencia**. Así que la radiancia es un argumento y el módulo no inventa el escalado. Si algún día aparece una firma con elevación, debería llegar con una cita, y ese test es lo que lo va a notar |

### 20.11 Lo que `background.py` deja fuera, declarado

- **Fondo de subida** (§20.7): sin radiancia de Tierra publicada.
- **La luna en función de fase o separación angular.** Lo único publicado es un
  intervalo —1.5e-5 sin luna a 1.5e-3 con luna llena a 1550 nm, un factor 100— y
  un intervalo es lo que se expone. Convertir «luna llena a 43° y dos días
  pasada» en una radiancia necesitaría un modelo de irradiancia lunar (ROLO o
  equivalente) que ninguna fuente libre verificada dio.
- **Estrellas, planetas, luces de ciudad, aurora, airglow.** La §3.1 de la
  P.1621-2 los lista y no tabula ninguno. Una estación cerca de una ciudad tiene
  el cielo nocturno más brillante que cualquier número de aquí.
- **La dependencia con la elevación, el azimut y el ángulo solar** (§20.10).
- **Cuentas oscuras, afterpulsing, tiempo muerto**: `detector.py`.
- **Un desplazamiento de sincronismo en la puerta.** El modelo de gating supone
  la puerta **centrada** en la señal; un offset la convierte en una diferencia de
  dos `erf`, que es barato de añadir y está ausente a propósito, porque el offset
  es una cantidad de sistema (un modelo de reloj, una corrección de range-rate) y
  no una propiedad del canal.
- **Una serie temporal de radiancia.** El eje de array está ahí, pero nada aquí
  la genera.

**Estado de la etapa 2.2:** hechos `atmosphere.py`, `turbulence.py`, `beam.py`,
`pointing.py`, `background.py` y el compartido `_validation.py`. Quedan
`detector.py` y `link_budget.py`. La suite está en 1027 tests, y `channel/`
entero al 100 % de cobertura de líneas y ramas.

---

## 21. `channel/detector.py` — lo que el detector pierde, lo que se inventa, y cuándo no está escuchando

### Qué hace este módulo, para quien llegue nuevo

Todo lo anterior de `channel/` pasa **fuera** del receptor: la atmósfera atenúa,
el haz se abre, el cielo añade fotones. Este módulo es lo que pasa de la apertura
hacia dentro, y un detector de fotón único le hace tres cosas distintas a un
enlace — por eso las tres viven en un módulo y no en tres:

1. **Pierde fotones de verdad.** No todo fotón que entra en el telescopio produce
   una cuenta: la óptica absorbe, el filtro absorbe, y el detector convierte solo
   una fracción de lo que le llega. Esa cadena es `receiver_efficiency`.
2. **Se inventa cuentas que nunca fueron fotones.** Una **cuenta oscura** es un
   clic sin luz: en un fotodiodo de avalancha un portador hace túnel o se libera
   térmicamente y arranca la misma avalancha que arrancaría un fotón; en un
   nanohilo superconductor es una fluctuación térmica. Un **afterpulse** es un
   clic causado por el clic anterior — portadores atrapados durante una avalancha
   que escapan un momento después y arrancan otra. Ninguno de los dos se
   distingue de una cuenta de señal una vez ha salido del detector.
3. **Se queda ciego después de cada cuenta.** El **tiempo muerto** es el
   intervalo tras un clic en el que el detector no puede producir otro, porque
   hay que apagar la avalancha o dejar que el nanohilo se enfríe por debajo de su
   corriente crítica. Eso hace que la tasa que reporta sea una función que
   satura de la tasa real.

La primera es una pérdida como cualquier otra del presupuesto. Las otras dos no:
una añade ruido que ningún filtro óptico quita, y la otra vuelve el instrumento
no lineal justo en el régimen en el que un enlace rápido quiere trabajar.

### 21.1 La regla que da forma al módulo — las medias se suman, la exponencial se hace una vez

**Qué es.** Una **media** —el número esperado de cuentas en una puerta, `µ`— es
un número no negativo sin cota superior. Una **probabilidad** está en `[0, 1]`.
Procesos de Poisson independientes tienen medias que se suman, así que señal,
fondo y cuentas oscuras se combinan como medias y se convierten **una sola vez**:

```
p_clic = 1 - exp(-(η (µ_señal + µ_fondo) + µ_oscuras))
```

**Por qué importa, y por qué es una regla y no un detalle.** Porque las **tres**
formas publicadas que este módulo reproduce rompen esa regla de la misma manera,
y las tres devuelven algo por encima de 1 dentro del espacio de parámetros que
este proyecto barre:

| Forma publicada | Qué trunca | Error en su punto de operación | Qué devuelve en el barrido diurno |
|---|---|---|---|
| `D_k = 1 - (1 - 2 p_dc) exp(-η_sys k)`, Lim et al. | la unión de las cuentas oscuras de sus **dos** detectores, cuya forma exacta es `(1 - p_dc)²` | 7e-12 con su `p_dc = 6e-7` | **1.93** con el `p_dc = 0.967` de fondo diurno; y `1 - 2 p_dc` se hace negativo por encima de 0.5 |
| `R_k = D_k (1 + p_ap)`, Lim et al. | la cascada de afterpulses, cuya suma geométrica es `1/(1 - p_ap)`; y multiplica una **probabilidad** por un factor de cuentas | 0.16 % con su `p_ap = 4e-2` | **1.006** con el 0.967 de clic diurno |
| `Y_0 = P_dc + P_noise`, Ec. (A6) de Ntanos et al. | la unión `1 - (1-P_dc)(1-P_noise)` | 1.2e-6 de noche, que es exactamente `µ/2` con `µ = 2.37e-6` | **3.42** con su propio fondo diurno, contra 0.967 |

Las tres son excelentes donde sus autores las usaron. Ninguna sobrevive a un
barrido, y un barrido es lo que hace este proyecto.

**El ejemplo con números.** La reproducción de la `D_k` de Lim et al. a cuatro
longitudes de fibra (µ = 0.5, 0.2 dB/km, sus dos APD de InGaAs):

| Fibra | `η_sys` | `D_k` publicada | `D_k` exacta | Sobreestimación |
|---|---|---|---|---|
| 0 km | 1.0e-1 | 4.877172e-2 | igual | 7.0e-12 |
| 50 km | 1.0e-2 | 4.988715e-3 | igual | 7.2e-11 |
| 100 km | 1.0e-3 | 5.010744e-4 | igual | 7.2e-10 |
| 200 km | 1.0e-5 | 6.199982e-6 | 6.199981e-6 | 5.8e-8 |

La tolerancia del test es **derivada**, no elegida: el truncamiento es
`p_dc²/(η_sys k + 2 p_dc)`, que está acotado por `p_dc/2 = 3e-7` y se alcanza
solo en el límite en que las cuentas oscuras son toda la tasa de detección. Y la
dirección importa: la forma impresa lee siempre **alto**, porque `1 - 2 p_dc` es
menor que `(1 - p_dc)²` y resta menos.

**Un detalle que hace posible la reproducción:** no hace falta la anchura de
puerta que Lim et al. **nunca declaran**, porque su modelo solo usa la
probabilidad por puerta y la puerta se cancela en el viaje
probabilidad → tasa → probabilidad.

### 21.2 La trampa — la cadena de eficiencia se aplica a los fotones y a nada más

**Qué es.** «Aplicar la eficiencia del receptor al ruido» es la frase natural, y
es incorrecta para una cuarta parte del ruido. Los fotones de fondo **son**
fotones: la óptica y la eficiencia cuántica los atenúan exactamente igual que a
la señal — por eso `background.py` se detiene deliberadamente en la apertura y no
aplica ninguna cadena óptica. Las cuentas oscuras **no** son fotones: se generan
*detrás* de la óptica, así que multiplicarlas por la cadena no es una decisión de
modelado, es un término que falta.

**Por qué importa.** Porque no se ve. Medido con el receptor de Ntanos et al.
§4.1 (detectores al 85 %, filtro 3 dB, receptor 2.65 dB → cadena de 6.36 dB) y el
telescopio de 2.3 m en su noche de estudio:

| Cantidad | Cuentas por puerta | Peso en el ruido |
|---|---|---|
| Fondo de cielo en la apertura | 7.64e-6 | 92.7 % |
| Fondo de cielo tras la cadena de 6.36 dB | 1.77e-6 | 74.7 % |
| Cuentas oscuras, dos detectores a 300 cps | 6.00e-7 | 25.3 % |

La cadena mueve las cuentas oscuras del 7 % del ruido al 25 %. Aplicarle la
cadena también a ellas hace que el ruido total salga **1.242 veces menor**, que
son **0.94 dB de ruido que desaparecen en silencio**, y el QBER sale un poco
mejor de lo que es. El test no congela el 1.242: aserta la identidad algebraica
`(η µ_fondo + µ_oscuras) / (η (µ_fondo + µ_oscuras))` de la que sale.

**Y tiene una consecuencia de diseño**, que es la parte útil: el fondo escala con
el área del telescopio y las cuentas oscuras no. La estación de 0.75 m está
**por debajo de sus propios detectores** (1.9e-7 de cielo contra 6e-7 de oscuras),
que es exactamente por qué la discrepancia nocturna entre las dos fuentes de
`background.py` cuesta 1.24x a 0.75 m y 2.83x a 2.3 m.

### 21.3 El hallazgo que pone una condición a `background.py` — el gating no toca el afterpulsing

**Qué es.** La §20.4 midió que estrechar la puerta es lo más barato del canal: de
1 ns a 100 ps cuesta 0.08 dB de señal y quita 10 dB de cielo. Las cuentas oscuras
también escalan con la puerta, así que no le roban nada. **Los afterpulses no
escalan con la puerta en absoluto**, porque un afterpulse lo dispara un *clic*
anterior, no una duración: su tasa es proporcional a la tasa de cuentas, y la
tasa de cuentas es lo que produce el enlace.

**El ejemplo con números.** Con el `p_ap = 4e-2` de Lim et al. y una probabilidad
de clic de 1e-3 por puerta (el centro del rango publicado: un enlace de 30 dB con
µ = 0.5):

| Puerta | Cielo | Oscuras | Afterpulses | Total |
|---|---|---|---|---|
| 1 ns | 1.77e-6 | 6.00e-7 | 4.00e-5 | 4.24e-5 |
| 100 ps | 1.77e-7 | 6.00e-8 | 4.00e-5 | 4.02e-5 |

Diez veces más estrecha compra **0.22 dB**, donde el cálculo de solo-cielo promete
10. Así que los dos juegos de detectores publicados **no están de acuerdo en si
el gating vale algo**, y el desacuerdo es un hecho de la tecnología y no del
modelo: la §4.1 de Ntanos et al. escribe «and no after-pulsing effect» *literal*
para sus nanohilos —un nanohilo no tiene avalancha, así que no tiene portadores
atrapados que liberar— mientras el APD de InGaAs de Lim et al. tiene 4e-2.

**Por qué esto es el hallazgo y no una curiosidad.** Porque «estrecha la puerta»
es una frase condicional y hasta ahora estaba escrita sin condición. Este módulo
es donde la condición queda anotada, y hay un test que compara los dos
detectores con el mismo enlace y la misma noche para que no se pueda leer una de
las dos conclusiones sin ver la otra.

Y el mismo `p_ap` decide un segundo cruce, este dentro del modelo de error de Lim
et al. (`e_k = p_dc + e_mis[1 - exp(-η_ch k)] + p_ap D_k/2`): el término de
afterpulsing supera al de cuentas oscuras en cuanto `D_k > 2 p_dc/p_ap = 3e-5`,
o sea **por debajo de 42 dB de pérdida total** con µ = 0.5. Los presupuestos
publicados están entre 20 y 40 dB, así que con este detector el afterpulsing es
el término dominante en todo el rango útil. El QBER es de `qkd/`; el cruce es del
detector y está asertado aquí.

### 21.4 Tiempo muerto — dos modelos, y uno no se puede invertir

**Qué es.** Dos modelos, y la diferencia entre ellos es una propiedad del
hardware, no una aproximación:

- **No paralizable** (el defecto): la ventana muerta es fija tras cada cuenta
  *registrada*, y los fotones que llegan dentro se pierden sin extenderla.
  `m = R/(1 + R τ)`, que satura en `1/τ` = **33.3 Mcps** con los 30 ns de Ntanos.
- **Paralizable** (extensible): *cada* llegada reinicia la ventana, se registre o
  no. `m = R exp(-R τ)`, que tiene un **máximo** en `1/(e τ)` = 12.3 Mcps y
  después *baja*.

**Por qué llevar los dos.** Porque fallan en direcciones distintas. Pasado su
máximo, el paralizable manda **dos** tasas incidentes a la misma lectura: 16.3 y
59.4 Mcps se reportan las dos como 10 Mcps. Así que una medida no se puede
corregir sin saber en qué rama está, y el no paralizable sí es invertible en todo
`m < 1/τ`. Consecuencia en el código: `incident_count_rate_cps` existe **solo**
para el no paralizable, y la ambigüedad es una **función que falta** en vez de una
suposición escondida — hay un test que aserta que su firma no tiene un parámetro
`paralysable`. Los dos coinciden a primer orden y se separan un 5 % en
`R·τ = 0.3554` (umbral derivado, re-derivado con `brentq` en el test), que son
11.8 Mcps a 30 ns, y ahí se registra un `WARNING` con las dos respuestas dentro.

**Y una afirmación publicada que sí reproduce**, que merece decirse en un
documento donde casi todas las demás no. La §4.2 de Ntanos et al. argumenta que
«the photon loss due to link attenuation [...] prevents the detectors of Bob
station to be saturated due to their dead time». Con sus propios números —fuente
de 100 MHz, 30 ns, µ = 0.5 y su mejor caso de 20 dB de pérdida total, que es
donde la saturación aparecería primero— entran 500 kcps y la pérdida por tiempo
muerto es del **1.5 %** (0.043 dB en la forma con puerta). A 30 dB es del 0.15 %.
Es correcta, y con dos órdenes de magnitud de margen.

**La forma con puerta, que es la que usa un receptor QKD de verdad.** Un receptor
con puertas no pierde segundos, pierde **puertas enteras**, así que el coste es un
entero: `bloqueadas = ceil(τ/T_rep) - 1`, las aperturas estrictamente dentro de la
ventana muerta. Con 30 ns y puertas cada 10 ns son **2**, no 3 — la última
tercera parte del tiempo muerto expira entre dos puertas y no cuesta nada, así que
la pérdida con puerta es 2/3 de la continua (1.0 % contra 1.5 %). Y la fracción de
puertas vivas es `f = 1/(1 + b p)`, que es **exacta y no aproximada**: el reparo
obvio —que dos clics cercanos solapen sus ventanas— no aplica, porque un clic solo
puede ocurrir en una puerta viva y las `b` siguientes están bloqueadas, así que
dos clics están separados por construcción. A 1 GHz con 30 ns son 29 puertas
bloqueadas por clic, y con 1 % de probabilidad de clic eso son **1.1 dB** de lo
que produce la fuente — que es la razón por la que un enlace satelital no compra
tasa simplemente subiendo la frecuencia de repetición.

Las tres leyes (las dos continuas y la de puertas) están verificadas **V1 contra
Monte Carlo del proceso del que se derivan**, no contra otra fórmula: llegadas
exponenciales con una ventana ciega de 30 ns para la no paralizable, la misma
tirada con la ventana reiniciada en cada *llegada* para la paralizable, y una
simulación puerta a puerta para `1/(1 + b p)`. La tolerancia de esa última es tres
errores estándar **derivados del proceso**: el conteo de vivas es `n - b·clics`,
así que su dispersión es `b` veces la de Poisson del número de clics,
`b·sqrt(n f p)/n`. Leerla como binomial sobre la fracción viva la subestima cinco
veces con `b = 29`, y eso es exactamente el tipo de tolerancia que falla una vez
al año sin motivo.

### 21.5 El hueco 5 del ADR 0009, ahora medido

**Qué era.** «No se localizó fuente libre y autoritativa con una tabla de valores
típicos de detector SPAD.» Sigue sin localizarse: cerrarlo es leer las hojas de
datos de Excelitas e ID Quantique, que son públicas, y transcribirlas con su
revisión.

**Qué cambió.** Que el hueco está **medido**, y eso lo hace priorizable en vez de
solo recordable. Los dos juegos publicados no son «valores típicos con
dispersión», son **dos instrumentos** a 10 dB de eficiencia y a un factor
infinito de afterpulsing, y la diferencia decide una conclusión de diseño
(§21.3), no un dígito. Por eso cada constante lleva su fuente en el nombre
(`NTANOS_*`, `LIM_*`) y hay un test que aserta que ninguna se llama en genérico:
`DARK_COUNT_RATE_CPS` a secas se leería como «la» tasa de cuentas oscuras.

**Y un sub-hueco nuevo, que es de unidades.** Las dos fuentes publican la cuenta
oscura en convenciones distintas —Ntanos una **tasa** (300 cps), Lim una
**probabilidad por puerta** (6e-7)— y **Lim et al. no declara ninguna anchura de
puerta en todo el paper**, así que la conversión no se puede hacer con sus
números. `dark_count_rate_from_probability_cps` pide la puerta como argumento y la
suposición es del llamante, explícitamente. Leído a la puerta de 1 ns de Ntanos,
el 6e-7 de Lim son 600 cps, el doble del nanohilo; leído a 10 ns son 60, la mitad.

**La coincidencia que no es corroboración.** Los dos nanohilos de Ntanos a 300 cps
en su propia puerta de 1 ns dan exactamente **6e-7** por puerta, el mismo número
que Lim publica **por detector** para otra tecnología en otro paper. Por detector
—la única forma en que las dos son comparables— difieren en un factor dos, y la
igualdad existe solo a una puerta que una de las dos fuentes nunca declara. Está
asertada *como coincidencia*, con el test que cambia la puerta supuesta y muestra
que el «acuerdo» se mueve con ella, para que nadie la lea como dos fuentes
independientes confirmándose. Es el mismo cuidado que la §20.8 con los 10 kcps de
luna llena, en la dirección contraria: ahí un número publicado que no cierra, aquí
uno que cierra demasiado bien.

**Dos huecos nuevos, y no son valores sino modelos** (huecos 12 y 13 del ADR
0009): si un afterpulse puede a su vez producir otro afterpulse —`1 + p_ap` contra
`1/(1 - p_ap)`, 0.16 % con el valor publicado y 5 % en `p_ap = sqrt(1/21)`— y si
el tiempo muerto es extensible (§21.4). Ninguna hoja de datos responde al primero.

### 21.6 Decisiones menores que no lo son

| Decisión | Por qué |
|---|---|
| **`AFTERPULSE_CASCADE_LIMIT` es `sqrt(1/21)` y se escribe con doce dígitos** | Es una forma cerrada: los dos modelos difieren en `1/(1 - p_ap²)`, así que el cruce del 5 % está donde `p_ap² = 1/21`. El test la re-deriva con un buscador de raíces y aserta que **no** es 0.22, por la misma razón que `GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS` aserta que no es 2.8: para que nadie la «simplifique» |
| **El 5 % es la misma tolerancia en los dos umbrales derivados, y en `background.py`** | Una convención de umbral en todo el presupuesto de ruido en vez de una por módulo. Está nombrada una vez (`_FIVE_PER_CENT`) para que las dos constantes y los tests que las re-derivan no puedan separarse |
| **`receiver_efficiency` devuelve un escalar y no tiene eje temporal** | Todo lo que hay dentro es propiedad del instrumento: los recubrimientos, el filtro, la polarización del detector. Nada de eso varía a lo largo de un pase, y darle un eje invitaría a meter ahí un término dependiente de la elevación — que sería un término real, y sería de la atmósfera |
| **La pérdida de polarización de 0.3 dB de Ntanos **no** está en la cadena del receptor** | Su propia frase la llama «the polarization decoherence loss of **the link**». Ponerla aquí se la aplicaría también al fondo de cielo, y la luz de fondo no está polarizada: no la decohera nada. Va a `link_budget.py` |
| **`detector_count` es un `int` y `True` se rechaza** | «1.5 detectores» no es un receptor que exista, y el abuso que se quiere cazar —pasar una eficiencia, o la probabilidad de unión de dos detectores— lo caza el mismo chequeo. `True` es un `int` en Python y no es un detector, así que se rechaza explícitamente |
| **Dos validadores separados para «cuentas por puerta» y «probabilidad»** | Y no uno con un flag. Todo el punto es que la cota de 1 se aplica a una y no a la otra, así que los dos chequeos no deben compartir un camino de código al que se le pueda pasar la cota equivocada. El mensaje de cada uno nombra el otro y la función que convierte |
| **Se aceptan medias por encima de 1** | 3.42 cuentas por puerta es un punto de operación **real** —es lo que recoge el receptor de referencia con el cielo diurno de la UIT— y rechazarlo sería rechazar el caso que el módulo existe para hacer bien. Lo que no se acepta es una *probabilidad* por encima de 1 |
| **`validated_duration_s` se sube a `_validation.py`** | Segunda copia (la primera está en `background.py`), y la regla del commit «Share the channel input validators before the third copy appears» es moverla antes de escribir la tercera. Los mensajes de `background.py` no cambian ni un byte, así que sus tests de validación son la prueba de que no cambió nada |
| **La ley `erf` de la puerta **no** se duplica aquí** | La constante de jitter es una propiedad del detector y vive aquí; la ley que la convierte en fracción de señal conservada es de `background.py`, porque la puerta es contra lo que el jitter se cambia. Partir un intercambio de dos términos entre dos módulos es cómo se olvida uno de los dos. Hay un test que aserta la ausencia |

### 21.7 Lo que `detector.py` deja fuera, declarado

- **Rendimientos, QBER y cualquier cosa por base.** El `p_ap D_k/2` de Lim et al.
  y el `1 - (1 - Y_0)(1 - η)^n` de un estado de `n` fotones son cantidades de
  protocolo: `qkd/`. Lo que cruza la frontera desde aquí es una probabilidad de
  clic y las medias que hay detrás.
- **El resultado de doble clic.** Lim et al. nombran cuatro resultados de medida,
  `{0, 1, vacío, ambos}`; contar el doble clic necesita saber qué detector
  corresponde a qué valor de bit, que es un hecho de protocolo.
- **Cuentas oscuras no poissonianas.** El afterpulsing las vuelve *agrupadas*, así
  que la varianza es mayor que la media aunque la media esté bien. Importa para
  una cota de clave finita, no para las tasas medias de aquí, y corregirlo
  necesita una distribución temporal de afterpulses medida que ninguna fuente
  verificada da.
- **Temperatura, corriente de polarización, latching, crosstalk y transitorios de
  recuperación.** La eficiencia de un SNSPD real depende de la corriente de
  polarización; la tasa oscura de un APD real casi se duplica cada 10 K; los dos
  pueden quedarse latcheados. Todo eso es de hoja de datos y lo cubre el hueco 5.
- **La dependencia con la longitud de onda.** El 85 % está declarado «at 1550 nm»
  y la eficiencia es una curva, no un número. Ninguna fuente verificada la da, así
  que la eficiencia es un argumento y hay un test que aserta que **ninguna** firma
  del módulo acepta una longitud de onda, una elevación ni una temperatura.
- **Saturación no lineal más allá del tiempo muerto.** Un detector real cerca de
  su techo tiene más cosas que un tiempo muerto constante.

**Estado de la etapa 2.2:** hechos `atmosphere.py`, `turbulence.py`, `beam.py`,
`pointing.py`, `background.py`, `detector.py` y el compartido `_validation.py`.
Queda **`link_budget.py`**, que es el que ensambla. La suite está en 1131 tests, y
`channel/` entero al 100 % de cobertura de líneas y ramas.

---

## 22. `channel/link_budget.py` — todas las pérdidas en un sitio, y las dos que no son números

### Qué hace este módulo, para quien llegue nuevo

Los seis módulos anteriores responden cada uno a una pregunta sobre el canal.
Este los suma. Suena a contabilidad y no lo es, porque **dos de los seis no
devuelven un número**:

- `pointing.py` devuelve una **distribución**: con jitter mecánico la
  transmitancia relativa no es un valor, es una variable aleatoria con una ley
  de potencias `F(x) = x^(γ²)`.
- `turbulence.py` devuelve una **varianza**: `σ²_lnI`, la anchura de las
  fluctuaciones de intensidad, no una pérdida.

Una línea de presupuesto tiene que ser **un** número en decibelios. Convertir
esas dos en uno exige elegir, y esa elección es todo el contenido del módulo.

La salida son dos objetos, separados a propósito: un `LossBudget` (cuánta luz
llega, partida en términos que un revisor puede comprobar de uno en uno) y un
`NoiseBudget` (cuántas cuentas por puerta llegan que no eran señal).

Un presupuesto de enlace es el objeto más revisable de una simulación y el más
fácil de equivocar en silencio, porque todos los términos son decibelios y los
decibelios se suman. Meter un término dos veces, o con el signo cambiado, da un
total equivocado exactamente por el tamaño de ese término y **igual de plausible
a la vista** que el correcto.

### El hallazgo: dos permisos al 1 % no hacen un permiso al 1 %

Un **desvanecimiento** (*fade*) es una pérdida que varía sola en el tiempo. Este
enlace tiene dos —el jitter de apuntado y la escintilación atmosférica— y un
presupuesto no puede citar una variable aleatoria, así que cita un **cuantil**:
«la pérdida que no se supera el 99 % del tiempo», el permiso al 1 % de *outage*.

La práctica publicada, que Ntanos et al. 2021 siguen explícitamente (§4.1 para
apuntado, Ec. (18) para escintilación, las dos a su `p_0 = 1 %`), es calcular el
cuantil al 1 % de cada una y **sumar los dos decibelios**. Está mal, y está mal
en una dirección y una cantidad que se pueden decir exactas, porque las dos colas
tienen forma cerrada **en decibelios**:

- **Apuntado.** Sustituyendo `L = -10 log10 x` en `F(x) = x^(γ²)`:

      P(L > l) = exp(-l · γ² · ln10 / 10)

  El desvanecimiento de apuntado en dB es **exactamente exponencial**, de tasa
  `a = γ²/4.343`. Una línea de álgebra, y no hace falta creerse nada más.
- **Escintilación.** La lognormal normalizada a media unidad de la Ec. (17) tiene
  `ln I ~ N(-σ²/2, σ²)`. La misma sustitución la vuelve **exactamente gaussiana**
  en dB, de media `4.343·σ²/2` y desviación `4.343·σ`.

Su suma es entonces una **gaussiana modificada exponencialmente**, cuya función
de distribución es forma cerrada. El cuantil conjunto no necesita Monte Carlo ni
aproximación: `combined_fade_db` lo invierte por bisección vectorizada hasta el
último bit.

Medido, en el enlace de referencia de este repo (telescopio de 0.75 m, 600 km,
1550 nm, transmisor de 0.15 m, 0.75 µrad de jitter, 20° de elevación):

| | outage 1 % | outage 0.1 % |
|---|---|---|
| Permiso de apuntado solo | 1.030 dB | 1.545 dB |
| Permiso de escintilación solo | 1.282 dB | 1.692 dB |
| Su suma, como suman los presupuestos publicados | 2.312 dB | 3.237 dB |
| **El cuantil conjunto verdadero** | **1.668 dB** | **2.217 dB** |
| Margen añadido que nadie pidió | 0.644 dB | 1.020 dB |
| Outage que la suma compra de verdad | **0.066 %** | **0.0011 %** |

El error es **conservador** —la suma exagera el desvanecimiento—, así que nada
construido encima es inseguro. Lo que es, es **mal etiquetado**: un diseño que
reporta «20 dB al 1 % de outage» está reportando la pérdida al 0.066 % de outage,
quince veces más estricto que el número impreso a su lado, y una tasa de clave
citada «al 1 % de outage» no es la tasa disponible al 1 % de outage. Dos sistemas
comparados al mismo outage declarado **no están comparados al mismo outage** a no
ser que sus términos de desvanecimiento tengan la misma forma.

Por eso `FadeCombination` tiene dos miembros y ningún defecto que esconda la
elección: `EXACT` es lo que el módulo usa si no se le dice otra cosa, `ADDITIVE`
existe para reproducir un presupuesto publicado, y la diferencia entre los dos
sale de la misma llamada (`effective_outage_probability`).

**Verificado a tres niveles a la vez**, que es lo que hace que esto sea un
hallazgo y no una afirmación: **V1** contra 4e6 muestras de los dos procesos
físicos —jitter gaussiano en dos ejes metido por `pointing_transmittance`, y la
lognormal de la Ec. (17)—, con tolerancia **derivada** del error estándar de un
cuantil empírico y la densidad local estimada de la propia muestra; **V3**
reevaluando la función de distribución en la respuesta que devuelve la bisección
(tiene que dar `1 - p` a 1e-12, lo que caza un bracket mal puesto, un contador de
iteraciones corto o un signo dentro del exponente); y **V2** porque la
convención aditiva es la publicada y el módulo la conserva medida en vez de
descartarla.

### La trampa que da forma al módulo: la cadena del receptor, dos veces

`detector.click_probability` toma un argumento `efficiency` y se lo aplica a la
señal y al fondo. Un presupuesto de enlace también quiere la cadena del receptor
como línea, porque **6.36 dB** de filtro, óptica y eficiencia cuántica son el
segundo término más grande del receptor de referencia. Hacer las dos cosas la
cuenta dos veces: **12.71 dB en vez de 6.36**, un factor **4.3** en tasa de
clave, y todos los números intermedios siguen pareciendo normales.

Es la misma forma de error que el doble conteo de `A_0` que `pointing.py` existe
para evitar (§19), y la defensa es la misma: la ambigüedad se quita del **API**,
no de la documentación. `LossBudget.transmittance` es el factor **completo**, con
cadena incluida, así que el número medio de fotones multiplicado por él ya son
fotones *detectados* y la llamada que sigue es `click_probability(...,
efficiency=1.0)`. Para la otra ruta está `LossBudget.channel_transmittance`, que
se para en la apertura y es la que se empareja con una `efficiency` explícita.
Las dos se guardan, hay un test que comprueba que las dos rutas dan el mismo
número, y ninguna es el producto de la otra por algo que haya que recordar.

### La extinción atmosférica es un argumento, no un modelo

«Extinción» es la luz que la atmósfera quita por absorción en bandas moleculares
y por dispersión en moléculas y aerosoles. No es lo mismo que la turbulencia, que
**redistribuye** la luz en vez de quitarla, ni que las nubes, que no son una
pérdida sino un corte.

`atmospheric_transmittance` implementa la Ec. (7) de Ntanos et al.,
`L_a = L_zen^(1/cos ζ)`: la transmitancia vertical elevada a la masa de aire. Es
Beer-Lambert disfrazado —una profundidad óptica multiplicada por la masa de aire
es lo mismo que una transmitancia elevada a ella—, y por eso la elevación entra
en el **exponente** y no en la base.

**La ley de escala está publicada y numerada. El número que escala, no.** Ntanos
et al. citan una referencia para la Ec. (7) y no dan nunca `L_zen`; la ITU-R
P.1621-2 publica absorción (§2) y dispersión (§3) **solo como figuras** —las
Figs. 1, 2 y 4 son gráficas, sin tabla ni forma cerrada al lado—. Leer un valor
de una curva y presentarlo como publicado es exactamente lo que prohíbe el
[ADR 0009](../docs/adr/0009-citation-policy.md).

Así que `zenith_transmittance` es un argumento **obligatorio, sin defecto**.
Quien tenga una extinción medida o modelada la pasa; quien no tenga ninguna
escribe `1.0` y con eso lo declara **en su propio código**. No hay ningún valor
del argumento que signifique en silencio «no lo he pensado», y hay un test que
aserta que el parámetro no tiene defecto, porque la forma fácil de cerrar este
hueco por accidente es ponerle uno. Es el **hueco 14** del ADR 0009.

**Lo que el hueco cuesta, medido — y lo que perseguirlo destapó.** Ntanos et al.
§4.2.1 afirman que su pérdida total de bajada «can get as low as 20 dB in total»
para 600 km con telescopio grande. Todos los demás términos son reproducibles
desde sus propios parámetros declarados:

| Término | dB |
|---|---|
| Geométrico (0.15 m → 2.3 m a 600 km) | 8.066 |
| **Truncamiento de la apertura transmisora** (ver la sección siguiente) | **3.352** |
| Desvanecimiento (apuntado + escintilación, su convención aditiva, 1 %) | 1.019 |
| Cadena del receptor (85 % · 3 dB filtro · 2.65 dB óptica) | 6.356 |
| Decoherencia de polarización (declarada, §4.1) | 0.300 |
| **Total** | **19.094** |
| Publicado (§4.2.1) | 20.0 |
| **Residuo** | **0.906** |

Leído por su Ec. (7), ese residuo es `L_zen = 0.812`: una transmitancia cenital
de cielo claro perfectamente ordinaria a 1550 nm. Así que su 20 dB es
**compatible** con este presupuesto más una extinción no declarada de tamaño
plausible, y hasta ahí llega la afirmación — **un residuo que cae en un rango
creíble no es prueba de ser la cosa a la que se parece**, y el paper no declara
extinción en ninguna parte. Compatible, no reproducido.

**Y la mitad interesante es la fila en negrita.** Sin ella el presupuesto sumaba
15.741 dB y el residuo eran **4.259 dB**, que exigían `L_zen = 0.375` — una
extinción vertical de 4.26 dB a 1550 nm con cielo despejado, un orden de
magnitud por encima de cualquier valor creíble. Lo que faltaba no estaba en la
atmósfera. El test aserta las **dos** lecturas y los dos `L_zen` implícitos,
precisamente para que se vea cuál de los dos hallazgos hace el trabajo.

El residuo tampoco es la convención de desvanecimiento: en el cenit las dos
reglas de combinación se separan **0.067 dB**, una décima parte de él.

### El transmisor recorta su propio haz, y cuesta más de lo que parece

`beam.py` propaga una gaussiana **sin truncar** —una cuya potencia se integra
sobre todo el plano infinito— con un radio de cintura igual al **radio** de la
apertura transmisora, que es lo que implica la Ec. (6) de Ntanos et al. Una
apertura real es un agujero, y con esa cintura el borde del telescopio corta
`exp(-2) = 13.5 %` del haz.

El número tentador es ese 13.5 %: **0.632 dB** de luz que nunca sale. Es la
respuesta correcta a **otra pregunta**. En el eje y en campo lejano lo que
integra es la **amplitud** —`I(0) = |∫E dA|²/(λL)²`— y la intensidad es su
cuadrado, así que perder la cola de la integral de amplitud cuesta **dos veces**
mientras la normalización de potencia la recupera **una**. Con `α = a/w_t`:

    ∫E dA         = π w² [1 - exp(-α²)]
    potencia lanzada = |E|² π w²/2 [1 - exp(-2α²)]

    η_trunc(α) = [1 - exp(-α²)]² / [1 - exp(-2α²)]

que a `α = 1` vale 0.4621: **3.352 dB**, no 0.63.

Hay **tres** números y cada uno tiene su potencia de referencia. Decirlos los
tres es lo que impide que se adopte el equivocado más adelante:

| Cantidad | A `α = 1` | Potencia de referencia |
|---|---|---|
| Luz que el borde bloquea | 0.632 dB | el láser |
| **Lo que el modelo sin truncar sobreestima** | **3.352 dB** | **lo que salió de la apertura** |
| Las dos juntas, `[1-exp(-α²)]²` | 3.984 dB | el láser |

Y son **una identidad, no tres medidas**: el producto de las dos primeras es la
tercera, y hay un test que lo aserta. `link_budget.py` aplica la de en medio,
porque la potencia de transmisión de un presupuesto de enlace es la que salió
del telescopio. Si la `µ` del llamante está definida **en la fuente**, los
0.632 dB extra van en `static_loss_db`, y esa decisión es del llamante porque
ninguna fórmula puede saber qué convención usa su `µ`.

Tres consecuencias que conviene separar. Es una propiedad **del transmisor**,
así que es un escalar, no varía a lo largo de un pase, y se reporta como línea
propia del presupuesto. Es el **único** término de aquí que un expansor de haz
quita: a `α = 2` son 0.16 dB y a `α = 3` ha desaparecido, lo que convierte a `α`
en una variable de diseño. Y el defecto es `α = 1` **porque es el único valor
consistente** con los radios de haz que calcula `beam.py`, no porque nadie lo
publique — hay un test que lo aserta contra la constante privada de ese módulo,
para que cambiar la convención allí no deje este término huérfano.

**Verificado V3, no derivado a mano:** la forma cerrada se compara contra la
integral de difracción evaluada por cuadratura a seis valores de `α`, con las
dos integrales hechas en el test sin nada de álgebra en común con el módulo.
Coinciden a 1e-9 relativo.

**Y una predicción del propio repo que estaba mal.** `tests/golden/README.md`
llevaba este término escrito en **0.63 dB** desde que se cerró `beam.py`, antes
de que `link_budget.py` existiera: era el número de potencia recortada, no el
del error del modelo. Está corregido allí con la derivación al lado. Merece
decirse porque es exactamente el modo de fallo que este proyecto teme —un número
plausible y equivocado, escrito con confianza en un documento de referencia— y
lo que lo cazó no fue una revisión sino **tener que usarlo**.

### La masa de aire, y dónde la secante deja de serlo

`1/cos ζ` trata la atmósfera como una losa plana: exacto en el cenit, y divergente
en el horizonte donde el camino real es finito. La comparación honesta aquí **no
es una cita, es geometría** — el camino por una capa esférica de espesor `H`
alrededor de una esfera de radio `R`:

    X(ζ) = sqrt((R/H)² sin²θ + 2R/H + 1) - (R/H) sinθ

Con `R = 6371 km` y 8.5 km de altura de escala, la secante se pasa un **0.20 % a
30°, 0.50 % a 20°** —el suelo de elevación del propio paper, así que ahí no cuesta
nada—, **2.1 % a 10°** y **8.1 % a 5°**. El 5 % cae en **6.427°**, que es
`SECANT_AIRMASS_ELEVATION_LIMIT_RAD`, **derivado con un buscador de raíces en el
test** y no elegido. Por debajo sale un `WARNING` con las dos masas de aire
dentro, y el valor devuelto **sigue siendo el del modelo publicado**: sustituirlo
en silencio por el esférico dejaría al módulo sin reproducir nada.

### Dos convenciones de signo, dichas una vez

**La Ec. (18) de Ntanos et al. devuelve un número negativo y lo llama pérdida.**
Escrita entera es `4.343 [erf⁻¹(2p₀-1)·sqrt(2σ²_lnI) - σ²_lnI/2]`, que es
`10 log10` del cuantil `p₀` de la **irradiancia**: el *nivel* de señal respecto de
la media, no la caída desde ella. Al 1 % y en la geometría de referencia vale
**−1.282 dB**. Sumada a un presupuesto de pérdidas positivas tal como está
impresa, **resta** el desvanecimiento en vez de sumarlo, y el total queda
equivocado en **el doble** de su profundidad. `scintillation_fade_db` devuelve la
forma negada, y el test lleva la Ec. (18) transcrita literalmente al lado para
que la diferencia sea **entre dos expresiones del mismo fichero** y no una
afirmación sobre una.

**Una varianza de log-irradiancia no es un índice de escintilación.** La Ec. (18)
está escrita en `σ²_I` —la varianza normalizada de la *irradiancia*— y convierte
con `σ²_lnI = ln(σ²_I + 1)`. Lo que devuelve
`turbulence.log_irradiance_variance` **ya es** `σ²_lnI`, porque la Ec. (4b) de
ITU-R P.1622 calcula esa cantidad directamente. Aplicar la conversión una segunda
vez es un error silencioso de **0.005 dB** en la varianza de referencia
(0.0153 Np²) y de **2.36 dB** en el límite de 1.0 Np² de la teoría de
fluctuaciones débiles. El módulo toma la log-varianza, su argumento lo dice en el
nombre, y la conversión no se aplica aquí.

### Lo que el módulo deja fuera, dicho en voz alta

- **La subida.** Todos los términos de desvanecimiento del `LossBudget` son de
  bajada. Una subida tiene un tercero —el vaivén del haz de
  `beam.uplink_beam_wander_angle_rad`— cuya distribución **no tiene la misma
  forma** que ninguna de estas dos, así que la gaussiana modificada
  exponencialmente que hace exacta a `combined_fade_db` deja de serlo. Y no tiene
  fondo en absoluto, porque el hueco 7 del ADR 0009 registra que ninguna fuente
  verificada publica la radiancia de una Tierra iluminada. **Un presupuesto de
  subida equivocado es peor que uno ausente**, y hay un test que aserta por
  ausencia que no existe ninguna función `uplink_*` en el módulo.
- **Las nubes.** La línea de vista libre de nubes es una probabilidad de que el
  enlace exista, no una cifra en decibelios, y va en `system/pcflos.py` donde se
  puede aplicar a un pase entero. Meter una probabilidad de nube dentro de una
  atenuación convertiría un corte en un promedio y haría que un enlace que **no
  funciona nunca** pareciera un enlace que funciona mal.
- **La correlación temporal.** Los dos desvanecimientos se citan aquí como
  cuantiles marginales **en un instante**. Un pase real se desvanece a ráfagas de
  milisegundos, así que el número de puertas *consecutivas* que se pierden no es
  el que implica un muestreo independiente. Eso es
  `system/correlated_fading.py`, y hasta que exista **ninguna afirmación de este
  módulo sobre clave por puerta implica una sobre clave por pase**.
- **Doppler, rotación de polarización y efecto Faraday.** `static_loss_db` es un
  escalar único para todo lo constante que ningún módulo modela; el valor de
  referencia que se le mete son los 0.3 dB de decoherencia de polarización que
  Ntanos et al. §4.1 declaran. Llamarlo pérdida estática y no modelo de
  polarización es justo el punto: es un hueco con cita, no un tratamiento físico.
- **Cualquier cantidad de protocolo.** Rendimiento, QBER, sifting, decoy y tasa
  de clave consumen una transmitancia y una tasa de ruido; no pertenecen al
  canal. Aquí termina `quoss.channel`.

### Un defecto de los módulos hermanos que apareció al ensamblarlos

Un eje temporal **vacío** —un pase que todavía no ha empezado, que es lo que
devuelve una segmentación antes de la primera muestra visible— hacía reventar a
`beam.py`, `turbulence.py`, `pointing.py` y `background.py` con
`ValueError: zero-size array to reduction operation minimum which has no
identity`. Los cuatro calculan el peor caso del array (`np.max`/`np.min`) para
decidir si registran un aviso, sin comprobar que hay array. No es un error de
física y no lo cazaba ningún test, porque cada módulo se probaba con muestras
reales; lo cazó `link_budget.py`, que los llama a los cuatro seguidos.

Lo interesante es que **`detector.py` ya tenía la guarda** (`if product.size else
0.0` en `observed_count_rate_cps`, §21): el patrón ya se había encontrado una vez
y se había arreglado solo donde apareció. Ahora está en los cinco, y el test de
regresión es `TestScalingLaws::test_an_empty_pass_returns_empty_and_records_nothing`,
que pide el presupuesto entero sobre un pase vacío y comprueba que sale vacío y
que el log no registra nada.

**Estado de la etapa 2.2: cerrada.** Los siete módulos escritos —`atmosphere.py`,
`turbulence.py`, `beam.py`, `pointing.py`, `background.py`, `detector.py`,
`link_budget.py`— más el compartido `_validation.py`, y `channel/` entero al
**100 %** de cobertura de líneas y ramas. Catorce huecos declarados en el ADR
0009, ninguno rellenado con la cita más plausible. Lo siguiente es la etapa 2.3,
`qkd/`, que es el primer consumidor de lo que este módulo produce.

---

## 23. `qkd/base.py` — la frontera: qué entra a un protocolo y qué sale

### Qué hace este módulo, para quien llegue nuevo

`channel/` termina con dos números en cada instante de un pase: **qué fracción**
de los fotones que salieron del satélite llega a un detector, y **cuántas cuentas
por puerta** llegan que no eran señal. Un protocolo de QKD convierte ese par en
otros dos: una tasa de clave secreta y una tasa de error. Este módulo es la
**costura** entre las dos mitades.

No hay física dentro. Lo que hay es la forma de la conversación —`LinkConditions`
(lo que entra), `KeyRate` (lo que sale), `QkdProtocol` (la interfaz) y
`ProtocolRegistry` (el nombre que escribe un escenario → la clase que lo
implementa)— más la única función que calcula algo, `binary_entropy`. Toda
fórmula que diga algo sobre BB84 vive en `bb84.py`.

**Vocabulario, sin dar nada por sabido.** Una **puerta** (*gate*) es la ventana
corta en la que el receptor acepta que un clic vino del pulso que Alice envió;
hay **una puerta por pulso**. La **ganancia** `Q` es la probabilidad de que un
pulso produzca un clic, venga de donde venga: es por *pulso*, no por segundo. El
**rendimiento** `Y_n` es lo mismo condicionado a lo que Alice envió, y `Y_0` —el
rendimiento cuando no envió nada— es el ruido. El **sifting** es quedarse solo
con los pulsos en los que Alice y Bob eligieron por azar la misma base. El
**QBER** es la fracción de bits cribados en los que discrepan; es una *fracción*,
no una tasa por segundo: el 11 % es `0.11`.

### Las tres trampas que dan forma a la costura

**1. Una media no es una probabilidad.** `NoiseBudget` reporta cuentas por puerta
como **media** —es lo que permite sumar fondo, cuentas oscuras y afterpulsing—, y
un protocolo necesita `Y_0`, que es una **probabilidad**. La conversión es
`1 - exp(-µ)`, hecha una vez. Leer la media como probabilidad es el error que
`background.py` tasa en 253 % para la luz solar brillante de la UIT, donde la
«probabilidad» sale **3.42**. Medido aquí en el caso ordinario en vez del
patológico, con los 6 W/(m²·µm·sr) de día claro que Ntanos et al. citan a
1550 nm: en su telescopio de 2.3 m la media vale 7.0712e-2 y la `Y_0` verdadera
6.8270e-2, así que la lectura lineal **sobreestima un 3.58 %**; en el de 0.75 m
del enlace de referencia, un **0.38 %**. Pequeño, silencioso, y en la dirección
que favorece al enlace. `LinkConditions.background_yield` es el único camino
entre las dos, y **es** `click_probability` con señal cero y eficiencia uno, no
una segunda copia de esa exponencial: una sola ley de clic de Poisson en el
proyecto.

**2. La transmitancia ya lleva el receptor dentro.**
`LossBudget.transmittance` es extremo a extremo: óptica, filtro y eficiencia
cuántica están dentro. Multiplicarla otra vez por una eficiencia es el doble
conteo de **6.36 dB** que da forma a `link_budget.py` —factor 4.3 en tasa de
clave— así que `LinkConditions` tiene **un** campo de transmitancia y **ningún**
campo de eficiencia: no hay par que multiplicar. Asertado por ausencia en
`test_the_link_conditions_offer_no_second_efficiency_to_multiply_by`.

**3. Un número por pulso no es un número por segundo.** Todo lo que calcula un
protocolo es por pulso; todo lo que dibuja un paper es por segundo. `KeyRate`
guarda **solo** la forma por pulso y *deriva* la otra, así que las dos no pueden
discrepar — la misma razón por la que `LossBudget` es inmutable.

### La interfaz comprueba a sus implementaciones

`QkdProtocol.key_rate` es concreto y llama a `_key_rate`, que es el abstracto.
Esa indirección existe porque hay tres cosas que una implementación puede
equivocar sin que nada parezca raro, y las tres se comprueban al volver:

| Comprobación | Qué falla si no está |
|---|---|
| la **forma** coincide con la de las condiciones | dos arrays combinados en producto exterior dan un resultado `(n, n)` cuya diagonal es correcta y cuya gráfica no significa nada |
| la **tasa de pulsos** se copió, no se recalculó | `secure_bit_s` se deriva de ella, así que una tasa venida de otro sitio escala todas las figuras |
| el **nombre** es el de este protocolo | un resultado se compara con otro por esa cadena |

Los tres levantan `ConfigurationError` y no `ScenarioError`, porque el defecto
está en la clase del protocolo, no en el escenario del usuario. Cada uno tiene
detrás un test con una implementación rota a propósito: una comprobación que
nadie ha visto fallar es una comprobación que nadie sabe si funciona.

La misma idea en `KeyRate`, que valida la cadena `gain >= sifted >= secure >= 0`.
No es cosmética: cribar descarta clics y no crea ninguno, y la amplificación de
privacidad no puede quitar más que toda la clave cribada, así que una violación
es un argumento en la ranura equivocada. La holgura que se permite es
**relativa, 1e-12**, y está probada por los dos lados —`1e-13` pasa, `1e-6` no—
porque las tres tasas se calculan una de otra y una igualdad puede perder el
último bit, pero una parte en un millón no sale de ahí.

### Dos decisiones de reparto que `bb84.py` va a heredar

- **El desalineamiento (`e_mis`) es del enlace, no del protocolo.** Es la
  probabilidad de que un fotón de señal *que sí se detectó* caiga en el resultado
  equivocado porque las referencias de polarización de emisor y receptor no
  coinciden. Es calidad de hardware medida, no una elección del experimentador,
  y es además el único error que **no** se lava cuando el enlace mejora: el fondo
  se diluye, el desalineamiento no. Por eso va en `LinkConditions`, y en el
  objeto del protocolo quedan solo las elecciones (intensidades, sesgo de bases,
  longitud de bloque, parámetro de seguridad). Va **sin defecto**, por la misma
  razón que `zenith_transmittance` en `link_budget.py`: un `0.0` por omisión es
  una afirmación de óptica perfecta hecha por quien no se enteró de que la hacía.
- **La puerta se pide aunque no entre en ninguna fórmula.** El ruido llega ya
  integrado sobre ella, así que `gate_duration_s` no multiplica nada aquí; se
  exige porque es lo único que hace que «por puerta» signifique algo, y porque
  una puerta **más ancha que el periodo de pulso** es un receptor cuyas puertas
  se solapan: cada cuenta se atribuiría a dos pulsos. El caso límite —puerta
  igual al periodo, receptor continuo— es legal y tiene su test.

Ninguna de las dos abre un ADR todavía. El sitio natural es el ADR que abrirá
`bb84.py` con las decisiones de decoy y finite-key, y un ADR de una decisión que
aún no tiene un consumidor es un documento que se escribe dos veces.

### Lo que el módulo deja fuera, dicho en voz alta

- **Cualquier protocolo que no sea BB84.** El registro estará vacío hasta que
  `bb84.py` se importe, y nunca tendrá un nombre para E91, CV-QKD, MDI-QKD ni
  TF-QKD mientras no estén implementados. Es la regla del
  [ADR 0005](../docs/adr/0005-propagation.md) para `PropagationMethod`: un nombre
  ausente obliga a preguntar en el punto de llamada, uno presente y sin
  implementar invita a un escenario a seleccionarlo. El control negativo corre
  sobre el registro real y sobre ocho deletreos (`e91`, `cv-qkd`, `mdi`, …), así
  que sigue valiendo por muchos módulos de protocolo que se importen después.
- **La entrada de finite-key por bloques.** `key_rate` mapea instantes a
  instantes. Una cota finite-key habla de un **bloque** de detecciones, y un
  bloque es una integral sobre el pase, que necesita el eje temporal que este
  módulo no lleva. Va en `finite_key.py`, y toma cuentas acumuladas en vez de una
  tasa. Hasta que exista, toda tasa que devuelva esta interfaz es
  `KeyRegime.ASYMPTOTIC` y **lo dice en su propio campo**, porque la asintótica
  es una cota superior y no una entrega.
- **El eje temporal.** `LinkConditions` lleva arrays y no un `TimeGrid`, igual
  que las funciones de `channel/` toman un array de elevaciones y no una rejilla.
  Así un barrido de cien transmitancias —que no es una serie temporal— no tiene
  que inventarse un eje para poder pasar. Integrar la tasa sobre el pase es
  `system/key_volume.py`, una etapa más tarde.
- **La maquinaria de decoy.** Acotar `Y_1` y `e_1` desde las ganancias
  observadas de varias intensidades es contenido de BB84 con pulsos coherentes
  débiles, no de la frontera. Un test asierta que ninguna firma pública de este
  módulo acepta una intensidad, un nivel decoy, una longitud de bloque ni un
  parámetro de seguridad: es el sitio por donde crecería una segunda copia del
  modelo.
- **La saturación por tiempo muerto.** Quien haga correr una fuente lo bastante
  rápido como para saturar sus propios detectores no recibe aviso aquí; el número
  que lo decide es `detector.saturation_count_rate_cps` y pide un tiempo muerto
  que este módulo no tiene por qué llevar.

### Por qué `xlogy` y no `x * log(x)`

`h(x) = -x log2 x - (1-x) log2(1-x)` es el precio de las dos cosas que Alice y
Bob tienen que pagar: corregir los errores cuesta al menos `h(E)` bits por bit
cribado, y borrar lo que la espía pueda saber cuesta otro `h(e_1)`. En `x = 0` el
producto `x log x` es `0 · (-inf)`: numpy devuelve `nan` **y avisa**, y esta suite
corre con `filterwarnings = ["error"]`, así que el aviso no es algo que se pueda
decidir ignorar después. Envolverlo en `np.where` no sirve —las dos ramas se
evalúan antes de elegir—, y un error nulo no es un caso raro: es lo que tiene un
enlace simulado sin fondo ni desalineamiento. `scipy.special.xlogy` define
`xlogy(0, 0) = 0`, que es el límite, y lo calcula sin llegar a formar el
producto. Además se le suma `0.0` a la salida para que el cero sea `+0.0`: `-0.0`
compara igual que cero y no rompe nada, pero se imprime como una entropía
negativa en una tabla de resultados.

Verificación: **V1**. Valores a mano (`h(0) = h(1) = 0`, `h(½) = 1`), la
definición reevaluada por un camino independiente (`math.log2` de la biblioteca
estándar en vez de `xlogy`), simetría alrededor de ½, y el umbral del 11 % de
BB84 **resuelto con un buscador de raíces** en vez de transcrito: donde
`h(E) = ½` sale `E = 0.110027864…`.

### Estado

`src/quoss/qkd/base.py`, 200 sentencias, **100 % de cobertura de líneas y de
ramas**; `tests/qkd/test_base.py`, 102 tests. `ruff`, `ruff format` y `mypy`
(estricto para `quoss.qkd.*`) limpios, y la suite entera en verde. No hay ningún
número publicado reproducido aquí porque no hay física que reproducir: los dos
números medidos (3.58 % y 0.38 %) salen de correr el propio `downlink_noise_budget`
dentro del test, no de una medición hecha a mano y guardada en prosa.

Lo siguiente de la etapa 2.3 es `qkd/bb84.py`: BB84 con pulsos coherentes débiles
y estados decoy, que es lo primero que implementa esta interfaz.

---

## 24. `qkd/bb84.py` — BB84 con pulsos coherentes débiles y decoy vacío+débil

### Qué hace este módulo, para quien llegue nuevo

Es la primera implementación de `QkdProtocol`, y por ahora la única. Entra un
`LinkConditions` —transmitancia, ruido y desalineamiento en cada instante— y sale
un `KeyRate`: tasa de clave secreta por pulso, QBER, y la etiqueta que dice de
qué afirmación de seguridad se trata. Todo lo que devuelve es **asintótico**, y lo
dice en su propio campo.

**Por qué hace falta el decoy, dicho desde cero.** Una fuente QKD real no emite
un fotón: emite un pulso láser atenuado cuyo número de fotones es Poisson. Con
µ = 0.56, el 57 % de los pulsos van vacíos, el 32 % llevan exactamente uno, y el
11 % llevan dos o más. Esos últimos son el problema: si un pulso lleva dos
fotones, la espía se queda uno y reenvía el otro, tiene una copia perfecta del bit
y **no ha perturbado nada** —el QBER no la ve—. Y como una bajada satelital pierde
28 dB, Alice y Bob esperan que casi todo se pierda, así que a la espía le basta
con bloquear todos los pulsos de un fotón, reenviar solo los multifotónicos por un
canal sin pérdidas suyo, y reproducir exactamente la ganancia que Bob espera
sabiendo la clave entera. Es el ataque **PNS**.

La defensa (GLLP) es suponer lo peor: todo pulso multifotónico está *marcado*, la
espía lo sabe gratis, y **solo los clics que vinieron de pulsos de un fotón**
producen secreto. Eso deja la pregunta que GLLP no resuelve: el detector de Bob no
dice de qué pulso vino cada clic. Los estados **decoy** la resuelven —Alice varía
la intensidad al azar entre µ, ν y vacío y lo anuncia después; la espía no puede
distinguirlas en vuelo, así que lo que le haga al canal se lo hace a las tres, y
tres ganancias medidas acotan las mismas incógnitas.

### Las cuatro decisiones, cada una con el número que la sostiene

**1. El rendimiento exacto, no la aproximación publicada.** Ma et al. escriben
`Y_n = Y_0 + η_n − Y_0 η_n` y en la línea siguiente `≈ Y_0 + η_n`. Sumada sobre la
Poisson, la aproximación da su Ec. (10) —y la (A4) de Ntanos et al.—,
`Q = Y_0 + 1 − e^(−ηµ)`. Este módulo usa la **primera** línea, cuya suma es
`Q = 1 − (1 − Y_0) e^(−ηµ)`, que **es** `click_probability`: una sola ley de clic
Poisson en el proyecto, no una segunda copia.

La diferencia son las puertas donde disparan el fondo **y** la señal, que la
aproximación cuenta dos veces. Medido en el enlace de referencia (0.75 m, cenit,
µ = 0.56): **0.0000787 %** con el ruido nocturno, **0.070965 %** con el día claro
de Ntanos et al. en ese mismo telescopio, y **0.077502 %** en el de 2.3 m. Pequeño — y
entonces deja de serlo de la única forma que importa: por encima de **7.152
cuentas por puerta la forma publicada devuelve una ganancia mayor que uno**,
1.0007 a diez cuentas. Es la misma confusión entre media y probabilidad que §20
encontró en la Ec. (20) de Ntanos et al., y `KeyRate` rechaza una ganancia por
encima de uno, así que aquí la aproximación no engañaría: reventaría.

**2. El QBER como mezcla, no como cociente.** Se escribe
`E = e_0 + (e_mis − e_0)(Q − Y_0)/Q`: la media ponderada entre la moneda al aire
del fondo (`e_0 = ½`) y el error de la óptica, con el peso de cuántos clics pone
cada uno. Algebraicamente es la Ec. (11) de Ma et al.; la razón de deletrearlo así
es que `E ≤ ½` se cumple **en coma flotante** y no solo en el álgebra. Mantener su
numerador literal junto a la ganancia exacta **no** tiene esa propiedad: devuelve
`E > ½` por encima de **3.912 cuentas por puerta**, y el caso de sol brillante de
la ITU que este proyecto ya modela está en 3.42 — un 12.6 % por debajo, no a
salvo. Un QBER por encima de un medio no es una clave peor: es un convenio de bit
invertido, y `KeyRate` levanta `DomainError`.

**3. Donde la cota decoy no certifica nada, lo dice.** La cota inferior de `Y_1`
puede salir **negativa**, que no es un rendimiento pequeño sino un conjunto de
restricciones vacío. Se recorta a cero, pero entonces `e_1` es `0/0`, y devolver
`e_1 = 0` ahí dibujaría un canal de un fotón **perfecto** justo donde el análisis
falló. Se devuelve `e_1 = ½` —el valor que no informa, `h(½) = 1`, clave cero—, se
marca la muestra en `certified` y se registra
`bb84.single-photon-yield-uncertified`.

**Y aquí hubo que corregir la intuición, que es la parte que merece leerse.** La
primera versión de este docstring decía que la cota falla «a baja elevación», que
es la respuesta natural y es **falsa**. Barrida de η = 1 a 1e-08 con el ruido
nocturno y las intensidades de Ntanos et al., la cota sigue positiva todo el
recorrido y converge a `Y_0` —salvo su propia holgura de primer orden en ν, un
**1.221 %** con esas intensidades—: un enlace sin señal todavía certifica que un
fotón habría hecho clic tan a menudo como el fondo. Lo que sí la rompe es la
**elección de intensidad**: con ν = 0.1 se vuelve no positiva por encima de
**µ = 3.72** a η = 1e-03. El test que lo mide existe precisamente porque la frase
equivocada ya estaba escrita, y una frase de «cuándo falla esto» equivocada es
peor que ninguna.

**4. La eficiencia de protocolo cuenta los pulsos gastados en decoys.** Ma et al.
dan `q = ½`; la Ec. (A1) de Ntanos et al. la extiende a
`q = ½ · N_s/(N_s + N_1 + N_2)`. Se usa la segunda, así que toda tasa es **por
pulso emitido**, decoys incluidos, que es el único denominador bajo el cual una
frecuencia de fuente en hercios significa algo.

### Una inconsistencia en la fuente, escrita en vez de arreglada a escondidas

Ntanos et al. §4.1 dicen «signal:decoy:vacuum ratio = 4:1:16» y «about q = 2/5» en
la **misma frase**, y las dos no concuerdan. Metido en su propia Ec. (A1), el
orden impreso da `q = ½·(4/21) = 0.0952`, un factor **4.2** por debajo de 2/5; el
orden invertido, 16:1:4, da `0.3810`, que es lo que significa «about 2/5». Así que
`NTANOS_STATE_COUNTS = (16, 1, 4)`, con la aritmética en el docstring de la
constante **y en un test que corre**, para que la afirmación no pueda volverse
falsa en silencio. Regla del [ADR 0009](../docs/adr/0009-citation-policy.md).

### Verificación

- **V1 — la ganancia contra la serie que dice ser.** El cierre analítico se
  compara contra la suma explícita `Σ_n P(n|µ) Y_n` con `Y_n = 1 − (1−Y_0)(1−η)^n`,
  término a término hasta n = 200, sobre 40 combinaciones de pérdida e intensidad.
  La serie se evalúa con `log1p`/`expm1` porque escrita literalmente es una resta
  de dos números que coinciden en dieciséis dígitos cuando `Y_0` y `η` rondan
  1e-07 — que es el enlace de referencia, así que la forma ingenua habría hecho
  del **test** lo menos preciso de la comparación.
- **V1 — la cota es una cota.** `Y_1` por debajo y `e_1` por encima del valor
  verdadero, en cinco décadas de pérdida. Es la comprobación sin síntoma: si se
  cruza, la tasa sigue siendo un número plausible y la afirmación de seguridad es
  nula, porque aguas abajo solo se ve la cota.
- **V3 — la cota contra el programa lineal del que es forma cerrada.** La Ec. (34)
  de Ma et al. es la solución analítica de «minimizar `Y_1` sobre todas las
  sucesiones de rendimientos en [0,1] compatibles con las dos ganancias medidas y
  con `Y_0`». Ese programa se le entrega a `scipy.optimize.linprog`, que no
  comparte una línea de razonamiento con su derivación: **coinciden a 1e-09
  relativo** en cuatro pérdidas. Es la verificación más fuerte disponible aquí, y
  dice que la fórmula es el óptimo del programa, no una relajación de él.
- **V2 — la intensidad óptima.** La Ec. (12) de Ma et al. da el óptimo analítico
  de µ en el límite dominado por pérdidas: resuelta desde la ecuación publicada da
  **µ = 0.7687** para `e_mis = 1 %` y `f = 1.22`. Maximizar numéricamente la tasa
  **completa de este módulo** lo reproduce con un error de **0.09 %** a η = 1e-02,
  **0.10 %** a η = 1.3993e-03 y **0.98 %** a η = 1e-04. La tolerancia es
  **derivada, no elegida**: la Ec. (12) desprecia el fondo (error de orden
  `Y_0/(ηµ)`) y un ν no nulo (orden `ν/µ`), así que se exige que la diferencia no
  pase del tamaño de lo que la ecuación tira. Por debajo de η ≈ 1e-05 el primer
  término deja de ser pequeño para este receptor y la comparación deja de serlo —
  propiedad de la Ec. (12), no de este módulo, y por eso el barrido acaba donde
  acaba.
- **V2 — el estado de vacío.** `Q_vacuum = Y_0` y `E_vacuum = ½`, Ec. (33) de Ma
  et al., **exactamente** y sin una rama por `intensity == 0`: la expresión
  general tiene que darlo.
- **V4 — el punto de referencia.** 1.180893e-04 bit por pulso a cenit, 11 809
  bit/s a 100 MHz, QBER 1.0492 %. Etiquetado como lo que es: una foto de la salida
  del propio módulo. **No** es trazable a un número publicado, y el test lo dice:
  Ntanos et al. reportan un máximo de 3.9e-04 bit/pulso sobre todo su estudio, para
  un telescopio y una elevación que no fijan, y con un presupuesto que arrastra los
  0.906 dB de residuo de §22. Lo único derivable de esa comparación es una
  desigualdad de un lado —a cenit y con su telescopio mayor tiene que salir **por
  encima**— y es lo único que se asierta; una tolerancia de dos lados aquí sería un
  número elegido para pasar.

### Lo que el módulo deja fuera, dicho en voz alta

- **La cota finite-key.** Sigue en `finite_key.py`. El indicador más nítido de que
  hace falta está dentro de este módulo: en el límite asintótico las fracciones de
  decoy y vacío son **coste puro** —la cota que compran ya es exacta por pocos que
  se envíen—, así que la tasa es estrictamente proporcional a la fracción de
  señal, y hay un test que lo asierta. Y el ν óptimo es «tan débil como dejen las
  estadísticas», que es justo lo que un módulo asintótico no puede ver.
- **Variantes de uno y de tres o más decoys.** La cota implementada es la de
  vacío+débil y solo esa. Un protocolo de un decoy tiene una cota **distinta**, no
  esta con una probabilidad a cero, y por eso se exigen las tres probabilidades
  estrictamente positivas.
- **La optimización de µ y ν.** Son argumentos **sin defecto**. El 0.56 y el 0.11
  salieron de optimizar contra *su* enlace con *su* ruido; un defecto llevaría esa
  optimización, en silencio, a un enlace para el que no se hizo.
  `Bb84DecoyProtocol.ntanos_2021()` existe para que pedir su configuración se
  parezca a pedirla.
- **BB84 asimétrico (eficiente).** Sesgar la base empuja `q` hacia 1 haciendo rara
  una de las bases, y la base rara es entonces de donde sale la estimación de
  parámetros — que es una afirmación sobre una muestra finita. Tasarlo
  asintóticamente sería cobrar la ganancia sin el coste.
- **Los clics dobles.** `channel/detector.py` ya dice por qué se queda corto; la
  diferencia con el tratamiento que asigna un bit al azar es `O(Y_0 η µ)`, 6e-12 en
  el punto nocturno de referencia.

### Estado

`src/quoss/qkd/bb84.py`, 184 sentencias, **100 % de cobertura de líneas y de
ramas**; `tests/qkd/test_bb84.py`, 552 tests. `ruff`, `ruff format` y `mypy`
(estricto para `quoss.qkd.*`) limpios, y la suite entera —1888 tests— en verde.

### Lo que se corrigió al revisar la etapa antes de guardarla

Tres cifras de tests de esta entrada y de la §23 estaban **contadas a mano y
mal**: «105» y «555» son en realidad **102** y **552** (`uv run pytest
tests/qkd/test_base.py` y `tests/qkd/test_bb84.py`), y la suite entera son
**1888**, no 1887. Corregidas aquí y en las dos entradas de la etapa 2.3 del
[`ROADMAP.md`](ROADMAP.md). Es la C1 de la auditoría del 2026-08-04 en pequeño y
sin consecuencias físicas —un número guardado solo en prosa— y es la razón de que
el modo de guardar cifras sea correr el comando, no recordarlo. Lo que sí se
reprodujo al comprobarlo: `--cov=quoss.qkd --cov-branch` da 386 sentencias y 108
ramas con **cero sin cubrir**, o sea que el «100 % de líneas y ramas» de las dos
entradas es exacto.

Y una afirmación del código que era falsa: `src/quoss/qkd/__init__.py` decía que
la cota finite-key «is on by default and the asymptotic rate is an explicit flag,
not the other way round», y listaba `finite_key` entre sus módulos como si se
pudiera importar. Ese fichero no existe, y `base.py` dice lo contrario con todas
las letras («Until it exists, every rate this interface returns is
`KeyRegime.ASYMPTOTIC`»). El docstring del paquete habla ahora en futuro y marca
el módulo como no escrito. Que el defecto se anuncie antes de existir es
exactamente la sobreestimación silenciosa que `KeyRegime` está para hacer
visible: quien lea solo el paquete creería que la tasa que recibe ya lleva
descontado el coste del bloque finito, y no lo lleva.

Lo siguiente de la etapa 2.3 es `qkd/finite_key.py`, y con él el ADR que este
módulo todavía no abre: las decisiones de decoy de arriba y las de finite-key
pertenecen al mismo documento, y un ADR de una decisión sin consumidor se escribe
dos veces.

---

## 25. `qkd/finite_key.py` — de una tasa a una longitud, y por qué no es lo mismo

### Qué hace este módulo, para quien llegue nuevo

`bb84.py` contesta «qué fracción de los pulsos se convierte en clave» suponiendo
que Alice y Bob tuvieran tiempo infinito. Este contesta la pregunta que plantea
un pase de verdad: *tuvieron once minutos y 6.6e10 pulsos — cuántos bits de clave
pueden reclamar, y con qué probabilidad la reclamación es falsa*.

**Por qué «finito» cambia algo, y no un poco.** Todos los números de la tasa
asintótica son probabilidades, y Alice y Bob nunca observan una probabilidad:
observan un recuento. 412 detecciones de 3.7e8 pulsos a la intensidad decoy. Un
recuento dividido por los intentos es una **estimación**, y una estimación puede
tener mala suerte. La cota decoy se construye restando una ganancia medida de
otra, así que una fluctuación del signo equivocado en cualquiera de las dos hace
que el rendimiento de un fotón certificado salga **demasiado alto** — y un
rendimiento certificado de más es clave que Eve conoce en parte. El análisis
finite-key sustituye cada recuento por el peor valor compatible con él a una
confianza declarada, y pone precio a la diferencia.

**Qué quiere decir «componible», que es la palabra que carga el peso.** Una clave
no es «segura» o «insegura»: es `epsilon`-segura, o sea que se separa de una
clave ideal —uniforme y desconocida para Eve— como mucho `epsilon` en una
distancia que se **compone bien**. Eso último es lo que importa: garantiza que
usar la clave dentro de otro protocolo —cifrar con ella, autenticar con ella—
degrada la seguridad de ese protocolo como mucho otro `epsilon`. Una cota no
componible puede ser perfectamente cierta y no decir nada sobre el sistema donde
la clave se usa.

**Y qué es el error de fase, que no es el QBER.** La amplificación de privacidad
cobra por lo que Eve sabe, y lo que Eve sabe está acotado por la tasa de error
que Alice y Bob **habrían visto** si hubieran medido en la base conjugada. No la
midieron: esos bits fueron clave. Así que hay que inferirla desde la base que sí
midieron, y la inferencia es un argumento de muestreo con su propia probabilidad
de fallo — el término `gamma`. Son dos tasas de error distintas en dos términos
distintos de la misma ecuación, y en el bloque de referencia valen **1.06 %** y
**8.85 %**: confundirlas infla el término de un fotón por **1.609**, sin que nada
aguas abajo pueda notarlo.

### La decisión de esta entrada: Lim et al. 2014, no Tomamichel et al. 2012

El roadmap escribió «finite-key componible (Tomamichel)» antes de que existiera
`bb84.py`. Lo que hay hoy es un protocolo de **pulsos coherentes débiles con
decoy**, y eso manda: Tomamichel, Lim, Gisin y Renner (*Nature Communications*
3:634, 2012) analizan BB84 con **fuente de un fotón**, y aplicarlo aquí exigiría
una fuente que este proyecto no modela o un argumento de *tagging* encima que
nadie ha publicado en esa combinación. Lim, Curty, Walenta, Xu y Zbinden (*PRA*
89, 022307, 2014) analizan exactamente el protocolo que hay, en cinco ecuaciones,
y su análisis de secreto **está construido sobre** la relación de incertidumbre
entrópica de Tomamichel y Renner. Elegir Lim no es apartarse de Tomamichel: es
usar el resultado que aplica su técnica a nuestro protocolo.

### Por qué no es «la asintótica por un factor de corrección»

Tres razones, cada una medida:

1. **Hay un coste fijo por bloque.** La Ec. (1) resta
   `6 log2(21/eps_sec) + log2(2/eps_cor)` bits **una vez**: **260** con
   `eps_sec = eps_cor = 1e-10` (225.7 + 34.2). Despreciable frente a un pase,
   decisivo frente a una demostración de unos cientos de bits, y sin traducción
   posible a una tasa.
2. **La desviación estadística es una sola para las tres intensidades.** Hoeffding
   acota el **reparto del bloque entero** entre ellas, así que la misma `delta`
   absoluta le toca a la intensidad rara y a la común — y tras el `1/p_k` que
   convierte cuentas en cantidad por pulso, la relativa de la rara es 21 veces
   mayor. En el bloque de referencia eso se ve crudo: el estado decoy registró
   **230** errores en la base de comprobación y la desviación compartida es
   **458**, o sea el doble que lo que mide. La cota de errores de un fotón sale
   entonces en **39 630** donde la base registró **16 088** errores de todo tipo.
   Una cota superior por encima del total sigue siendo una cota superior; lo que
   dice es que esa configuración no certifica casi nada sobre de dónde vinieron
   los errores.
3. **El protocolo no es el mismo.** Base sesgada, clave de las **tres**
   intensidades, error estimado en la **otra** base, y `mu_3 >= 0` en vez de
   vacío exacto. Comparar término a término es comparar dos protocolos.

### El crédito de vacío: ruido que hace clave, y cuánto vale de verdad

La Ec. (1) suma `s_{X,0}` —las detecciones en puertas donde Alice no envió nada—
**entera**, sin cobrarle amplificación de privacidad. Es correcto: un clic en una
puerta vacía lo decidió el detector, no el canal, así que Eve no sabe nada del bit
que Bob apuntó. Suena a truco, así que se midió, con 1e12 pulsos:

| Ruido (cuentas/puerta) | `s_0` | Clave | Aporte de `s_0` |
|---|---|---|---|
| 7.9e-07 (noche) | **0** | 5.47e+07 bits | 0 % |
| 1e-05 | 1.51e+06 | 4.58e+07 bits | **3.3 %** |
| 1e-04 | 1.65e+07 | **0** | — |

De noche no se certifica ninguno: hay **37 522** detecciones de vacío y la
desviación es **44 399**, así que están dentro del ruido del reparto. Y de 1e-04
en adelante el término crece pero la clave ya es cero, porque la corrección de
errores se cobra sobre **todo** el bloque y el QBER que producen esas mismas
cuentas oscuras se la comió antes. El crédito es real, es pequeño y **nunca
rescata** un enlace ruidoso.

### El hallazgo que solo este módulo puede ver

`Bb84DecoyProtocol.protocol_efficiency` dice que los pulsos decoy son coste puro y
que su fracción óptima es cero. Es cierto —y es cierto **solo asintóticamente**.
Barriendo la fracción decoy con la de vacío fija en 5 %:

| Fracción decoy | Clave/pulso a 1e20 | Clave/pulso a 1e10 |
|---|---|---|
| 0.05 | **7.11e-05** | 0 |
| 0.10 | 6.85e-05 | 6.26e-06 |
| 0.50 | 4.77e-05 | **2.12e-05** |
| 0.90 | 2.70e-05 | 1.69e-05 |

Asintóticamente cae de forma monótona; con un bloque de pase tiene **máximo
interior cerca del 50 %**, y gastar medio pase en decoys vale un factor **3.4**
sobre gastar una décima. Ese óptimo es invisible desde `bb84.py`, porque la
cantidad que `bb84.py` optimiza no depende de la fracción decoy en absoluto.

Un segundo efecto de la misma familia, y también contraintuitivo: apretar
`eps_sec` cinco décadas engorda `delta` solo un **20 %** —lleva
`sqrt(ln(21/eps_sec))`— pero cuesta el **72 %** de la clave del bloque de
referencia, porque un 20 % más de desviación mueve la tasa de error de fase de
5.4 % a 12.1 %, que es media curva de `h`. Barato en la desviación, caro en la
clave.

### La verificación: dos papeles, dos transcripciones, un número

La comprobación más fuerte de la etapa no compara contra un valor publicado sino
contra **otra fuente implementada aparte**. Con `mu_3 = 0` y un bloque tan grande
que la desviación es despreciable, la Ec. (3) de Lim et al. **es** la Ec. (34) de
Ma et al. que implementa `bb84.py`, escrita en cuentas en vez de en
probabilidades.

Y no solo coinciden: **coinciden de la manera correcta**. El residuo relativo es
**4.33e-04** con 1e16 pulsos, **4.33e-06** con 1e20 y **4.33e-08** con 1e24 — tres
puntos sobre una recta de pendiente −1/2, que es exactamente como escala `delta`.
Una coincidencia en un punto pueden ser dos errores que se cancelan; una que
converge con la ley correcta, no. Lo mismo con la Ec. (4) contra la Ec. (37).

**El V2, y la ambigüedad que resolvió.** Su §Evaluation publica que a 100 km la
tasa con bloque 1e9 es «about 1.75» veces la de 1e7. Pero su tasa de error
impresa lleva `eta_ch` —solo la fibra— en el término de desalineamiento, mientras
la tasa de detección de al lado lleva `eta_sys = eta_ch·eta_Bob`, diez veces
menor: ese término aporta entonces **3.9 puntos** de QBER a pérdida cero donde
la lectura consistente aporta **0.48**, un factor **8.07** que es justo el
`1/eta_Bob` que sobra. Cruzando esa
lectura con la de si `e_k` cuenta errores por puerta o por detección salen cuatro
modelos, con cocientes **1.79**, 2.73, 1.46 y 1.47. **Solo el físicamente
consistente cae sobre su número**, así que es el que se implementa — la
ambigüedad se resolvió midiendo, no eligiendo.

**Lo que no se reproduce, escrito en vez de ajustado:** dicen que un bloque de
1e4 llega a 135 km. Con esa lectura, un bloque de 1e4 no certifica clave **a
ninguna distancia**, ni a pérdida cero. El desajuste es de exactamente una
década: nuestra curva de 1e5 es su curva de 1e4 —positiva a 135 km, muerta antes
de 150—. Hueco 16 del [ADR 0009](../docs/adr/0009-citation-policy.md), y un test
que **asierta el desacuerdo**, para que quitarlo obligue a reescribir esto.

### Dos detalles que un lector cuidadoso pararía a mirar

**Recortar `s_0` a cero antes de usarlo en la Ec. (3) parece inseguro y no lo
es.** Esa ecuación lleva `+ (mu_2²-mu_3²)/mu_1² · s_0/tau_0`, así que un `s_0`
mayor da un `s_1` mayor, y mayor es la dirección insegura. Pero la Ec. (3) está
derivada con el número **verdadero** de eventos de vacío y es monótona creciente
en él: sustituir cualquier cota inferior válida del verdadero `s_0` da una cota
inferior válida de `s_1`. Cero es una cota inferior válida de un recuento, y es
**más ajustada** que un número negativo. Recortar mantiene la garantía y mejora el
resultado.

**El único sitio donde la fuente mezcla dos logaritmos.** El término de muestreo
escribe `cd log 2` en el denominador y `log2(...)` en el numerador de la misma
expresión. El primero es natural, el segundo base dos. Leer el primero como base
dos lo hace `1` en vez de `0.693` y escala `gamma` por `sqrt(ln 2) = 0.8326`: un
**17 % de subestimación** del castigo, en la dirección que favorece a la clave y
sin síntoma en ninguna otra parte. Hay un control negativo que lo mide.

### Lo que el módulo deja fuera, dicho en voz alta

- **El defecto activo que el roadmap pedía.** Quien posee un pase —y por tanto un
  bloque— es `system/key_volume.py`. Hasta que exista, lo que sale de `qkd/` por
  la interfaz de protocolo es asintótico y lo dice en su campo.
- **La optimización de parámetros.** Cinco, y el óptimo se mueve con el bloque.
  Es `engine/sweep.py`.
- **El sorteo de las cuentas.** `expected_block_counts` devuelve **esperanzas**:
  la cota tasa la incertidumbre de estimación que queda aunque las cuentas caigan
  justo en su media. Cuánto dispersa entre pases es otra pregunta, y es
  `system/monte_carlo.py`.
- **Variantes de uno o de más de dos decoys**, y cualquier protocolo que no sea
  BB84.

### El ADR que la etapa tenía aplazado

La §24 dejó dicho que las decisiones de decoy y las de finite-key pertenecen al
mismo documento y que escribirlo antes de tener consumidor era escribirlo dos
veces. Ya está: [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md), que cubre
los tres módulos de la etapa 2.3.

### Estado

`src/quoss/qkd/finite_key.py`, 396 sentencias, **100 % de cobertura de líneas y
de ramas**; `tests/qkd/test_finite_key.py`, 158 tests, de los cuales tres —la
reproducción de su Fig. 1, que optimiza cinco parámetros por punto— van marcados
`slow` y tardan 7 s. `ruff`, `ruff format` y `mypy` (estricto para `quoss.qkd.*`)
limpios, y la suite entera —2058 tests— en verde.

Lo siguiente de la etapa 2.3 son `qkd/entanglement.py`, `qkd/cv.py` y
`qkd/mdi_tf.py`; ninguno de los tres tiene hoy un nombre en el registro de
protocolos, y no lo tendrá hasta que exista su implementación.

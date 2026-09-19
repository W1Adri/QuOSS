# Archivo de `LAST_CHANGES.md` — §40

> **Qué es esto.** Una entrada de la bitácora del proyecto, **íntegra y sin
> editar**, sacada del camino de lectura obligatorio y no borrada. La razón
> general es la misma que la de [`LAST_CHANGES-01-12.md`](LAST_CHANGES-01-12.md)
> y sus cuatro hermanos: `notes/LAST_CHANGES.md` guarda las cinco últimas
> entradas completas y el resto vive aquí, con una línea por entrada en el
> índice del fichero vivo.
>
> **Por qué esta y por qué ahora.** Por la cota estructural de
> `tests/unit/test_notes.py` —cinco entradas vivas como mucho— al entrar §45, y
> **solo después de comprobar que todo lo que carga peso en ella vive ya en otro
> sitio**, que es la regla de §41 y no una formalidad. Comprobado, uno a uno:
>
> - La unión discriminada sobre el tag `link`, el bloque declarado y la forma
>   del resultado horizontal: en el
>   [ADR 0024](../../docs/adr/0024-the-horizontal-scenario.md), y asertados en
>   `tests/scenario/test_models.py` y `tests/engine/test_horizontal.py`.
> - Los dos terminales y el sentido único de GE-1: en el
>   [ADR 0025](../../docs/adr/0025-two-terminals-one-way.md).
> - Los **253 935 bit/s certificados a 1 km en una sesión de 60 s** y el cero de
>   los 5 km contra los 4.4 kbit/s que reclama el cálculo asintótico: en
>   `tests/engine/test_horizontal.py` y en el escenario commiteado
>   `scenarios/ge1_1km.yaml`, que es de donde salen.
> - Los huecos 20 y 21, los dos subidos de categoría con su medida: en el
>   [ADR 0009](../../docs/adr/0009-citation-policy.md).
> - El defecto del régimen mudado a las firmas: en el anexo del
>   [ADR 0022](../../docs/adr/0022-the-strong-regime.md), que §39 ya dejó
>   comprobado.
>
> No se ha borrado nada. Lo que sigue es el texto tal cual estaba, enlaces
> relativos incluidos: son los del fichero vivo y desde aquí apuntan un nivel
> de más, igual que en los cuatro hermanos.

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

# LAST_CHANGES §44 — archivada

> Entrada íntegra y sin editar, archivada el 2026-09-19 por la regla de las
> cinco entradas vivas (`notes/LAST_CHANGES.md`, cabecera; §41 tiene la medida).
> Todo lo que cargaba peso en ella vive hoy en el
> [ADR 0018](../../docs/adr/0018-validation-is-a-table-not-a-badge.md), en
> `docs/validation.md` y en `tests/validation/`.

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

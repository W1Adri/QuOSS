# Archivo de `LAST_CHANGES.md` — §39

> **Qué es esto.** Una entrada de la bitácora del proyecto, **íntegra y sin
> editar**, sacada del camino de lectura obligatorio y no borrada. La razón
> general es la misma que la de [`LAST_CHANGES-01-12.md`](LAST_CHANGES-01-12.md)
> y sus tres hermanos: `notes/LAST_CHANGES.md` guarda las cinco últimas entradas
> completas y el resto vive aquí, con una línea por entrada en el índice del
> fichero vivo.
>
> **Por qué esta y por qué ahora.** Por la cota estructural de
> `tests/unit/test_notes.py` —cinco entradas vivas como mucho— al entrar §44, y
> **solo después de comprobar que todo lo que carga peso en ella vive ya en otro
> sitio**, que es la regla de §41 y no una formalidad. Comprobado, uno a uno:
>
> - El campo `ChannelSpec.scintillation_regime` y la defensa de su valor por
>   defecto: en su propio docstring y en el **anexo del 2026-09-15** del
>   [ADR 0022](../../docs/adr/0022-the-strong-regime.md).
> - La tabla del día de referencia en los dos regímenes (+3.66 %) y el barrido de
>   máscara con sus dos óptimos: en el mismo anexo, y asertados en
>   `tests/e2e/test_reference_scenarios.py`.
> - Los **457 bits que cambian de signo** y el cruce de 27.02°: en el anexo, y en
>   `TestTheFourHundredAndFiftySevenBits` y su gemelo saturado.
> - La corrección del «3.4 %» a un rango de **−3.4 % a −21.1 %** celda a celda:
>   en la tabla del anexo, y en
>   `tests/channel/test_turbulence.py::test_what_the_default_would_cost_across_the_whole_published_table`.
> - El precio del flip (30 aserciones rojas contra 84, y seis anclajes V2): en la
>   sección «El precio del flip» del anexo.
>
> No se ha borrado nada. Lo que sigue es el texto tal cual estaba.

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

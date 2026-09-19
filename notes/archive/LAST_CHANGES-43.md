# Archivo de `LAST_CHANGES.md` — §43

> **Qué es esto.** Una entrada de la bitácora del proyecto, **íntegra y sin
> editar**, sacada del camino de lectura obligatorio y no borrada. La regla es
> la suya propia: `notes/LAST_CHANGES.md` guarda las cinco últimas entradas
> completas y el resto vive aquí, con una línea por entrada en el índice del
> fichero vivo.
>
> **Por qué esta y por qué ahora.** Por su propia cota estructural al entrar
> §48, y **solo después de comprobar que todo lo que carga peso en ella vive ya
> en otro sitio**. Comprobado, uno a uno:
>
> - La CLI, su única regla («no calcula nada»), las dos formas de directorio de
>   un export y `expected_degradations` fuera del hash: en el
>   [ADR 0028](../../docs/adr/0028-the-cli-computes-nothing.md) y en los
>   docstrings de `src/quoss/cli/`, que es donde se asertan.
> - Que los avisos se imprimen enteros y nunca contados: en el docstring de
>   `src/quoss/cli/report.py`, con el caso concreto que lo exige.
> - El entry point y por qué su test es un subproceso: en `tests/cli/test_main.py`.
> - Las catorce citas a la guía: cerradas, y el test que impide que vuelvan a
>   romperse es `tests/unit/test_notes.py::test_every_guide_section_cited_from_the_code_exists`.
> - La errata de Vallado y la capa que la vuelve inutilizable: en el
>   [ADR 0003](../../docs/adr/0003-orbital-elements.md), con el test que la cita.
> - La reclasificación de la etapa 2.4 y la distinción vectorizar/paralelizar:
>   en el [ADR 0026](../../docs/adr/0026-the-language-ladder.md) y en
>   `notes/ROADMAP.md`.
> - Las dos inconsistencias que esta entrada cerró, #15 y #17, están en
>   `notes/INCONSISTENCIAS.md` con su justificación.
>
> Nada de lo de abajo se ha editado al moverlo.

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

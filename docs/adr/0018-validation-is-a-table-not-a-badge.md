# ADR 0018 — «Validado» es una tabla que se recalcula, no una insignia que se escribe

- **Estado:** aceptada
- **Fecha:** 2026-09-19
- **Etapa:** 8 (`validation/`)
- **Afecta a:** `validation/base.py` (`ValidationStatus`, `Comparison`,
  `AccountedTerm`, `classify`, `ValidationCase`, `run_all`, `render_markdown`,
  `EXPECTED_DISAGREEMENTS`, `PENDING_DISAGREEMENTS`), `validation/channel.py`,
  `validation/satquma.py`, `validation/micius.py`, `validation/__main__.py`,
  `cli/validate.py`, `tests/validation/`, y `docs/validation.md` cuando exista
  (ver el punto 5: decidido, no implementado).
- **Número reservado desde el 2026-09-14.** `src/quoss/validation/__init__.py`
  citaba este fichero por su nombre exacto antes de que existiera, y el roadmap
  lo reservaba para esta etapa.
- **Extiende** al [ADR 0009](0009-citation-policy.md) (una cita es una fuente
  que se ha abierto; un hueco declarado es mejor que un número plausible) y a
  `tests/golden/README.md`, que es el dueño de los cuatro niveles V1–V4.

---

## Contexto

### Qué significa «validado», y por qué la palabra es el problema

En un simulador de física, «validado» debería querer decir: *alguien comparó lo
que este código calcula con un número que otra persona publicó, y coincidieron*.
En la práctica la palabra se usa para otras tres cosas que no son esa:

- «pasa sus tests» — que es **V1**, invariantes: demuestra que el módulo no se
  contradice a sí mismo, y nada sobre si acierta;
- «reproduce un snapshot de sí mismo» — que es **V4**, regresión: demuestra que
  un refactor no movió un número, y nada sobre si el número era correcto;
- «alguien lo revisó una vez» — que no es ningún nivel, porque no se recalcula.

Solo dos niveles son validación: **V2**, un valor impreso en una fuente que
alguien abrió, y **V3**, una implementación independiente de la misma física.
Los cuatro están definidos en `tests/golden/README.md`, que es su dueño.

### El modo de fallo concreto: la insignia que sobrevive al acuerdo que describía

Lo que este ADR existe para impedir tiene una forma muy precisa. Alguien compara
un número, coincide, y **escribe** «validado» en un README, en una tabla, o en
un campo `status="reproduced"` de un fichero de casos. Seis meses después la
física cambia —una corrección, un modelo mejor, una constante actualizada—, el
número deja de coincidir, **y la palabra sigue ahí**. No hay nada que la mueva:
no es una aserción, no la recalcula nadie, y el fichero que la contiene se lee
como documentación.

Ese es el mismo patrón que el proyecto persigue en todas partes: una afirmación
defendida por evidencia que **ya no se comprueba**. Y aquí cuesta más que en
otros sitios, porque «validado contra la literatura» es precisamente la
afirmación con la que un lector externo decide creerse el resto.

### Qué había antes de este fichero

El paquete `quoss.validation` existía desde la etapa 8 parcial —`base.py`,
`channel.py`, `satquma.py`, `micius.py`, 22 casos de tres fuentes— con la regla
ya implementada y **sin dueño de la justificación**: `validation/__init__.py`
citaba `docs/adr/0018-validation-is-a-table-not-a-badge.md` por nombre y el
fichero no existía ([inconsistencia #11](../../notes/INCONSISTENCIAS.md),
anotada el 2026-09-14 y cerrada de verdad aquí).

---

## Decisión

### 1. El estado se **deriva**, y `classify` es el único sitio donde se decide

Un `ValidationCase` no se puede construir con un estado que sus propios números
no producen: el estado es el valor de retorno de `classify(published=…,
computed=…, tolerance=…)`, y el constructor lo comprueba. Escribir
`status=REPRODUCED` en un caso cuyo residuo excede su tolerancia es un error en
tiempo de construcción, no una nota que alguien tenga que revisar.

**Por qué esto es lo que rompe la insignia.** Una insignia es una palabra que
sobrevive a los números; un estado derivado **no puede**: si la física cambia y
el número deja de coincidir, el estado cambia solo, la tabla se regenera
distinta, y el diff lo enseña. La palabra deja de ser un artefacto editorial y
pasa a ser una función de los datos.

### 2. Cuatro estados, y los dos del medio son los que hacen falta

| Estado | Qué significa |
|---|---|
| `reproduced` | Dentro de la tolerancia declarada. |
| `compatible` | Fuera de ella, y el residuo cae dentro de un término **acotado y declarado** que la fuente omite. |
| `not_reproduced` | Fuera, y nada declarado lo explica. Se publica. |
| `gap` | La fuente no da nada computable. Se publica también. |

`reproduced` y `not_reproduced` son obvios. Los otros dos son la decisión:

- **`compatible` existe porque la alternativa es ensanchar una tolerancia.**
  Ntanos et al. imprimen un presupuesto de 20 dB; este proyecto calcula 19.094,
  con la precisión impresa de 0.5 dB. Quedan 0.906 dB fuera. La tentación es
  poner la tolerancia en 1 dB y llamarlo reproducido — y esa tolerancia, elegida
  para que pase el resultado de hoy, ya no puede fallar nunca, que es la regla
  de tolerancias derivadas de `CLAUDE.md`. Lo que se hace en su lugar es
  declarar el término que falta con su **intervalo y su base**: una extinción
  atmosférica no modelada solo puede **añadir** pérdida, así que su residuo
  admisible es `[0, +inf)`. El 0.906 cae dentro, el estado es `compatible`, y la
  afirmación que se publica —«coincide una vez se tiene en cuenta un término
  acotado que la fuente no da»— es más débil y **es la verdadera**.
  `AccountedTerm` solo se consulta cuando la comparación directa falla, así que
  no puede convertir un acuerdo en otra cosa.
- **`gap` existe porque un hueco declarado vale más que un V2 inventado.** Es la
  misma regla del ADR 0009 aplicada a la tabla: una fila que dice «la fuente no
  publica nada computable aquí» es información; rellenarla con la cita más
  plausible es fabricarla.

Y `Comparison` —`EQUAL`, `AT_MOST`, `AT_LEAST`— existe por lo mismo un nivel más
abajo: leer una cota como si fuera un punto **inventa precisión que la fuente no
reclama**. «10 kcps **como mucho**» no es «10 kcps».

### 3. Un desacuerdo se **publica**; lo que se aserta es que no aparezca uno nuevo

La tabla que `render_markdown` produce —y que `quoss validate` imprime— lleva
sus filas `not reproduced` con el desacuerdo escrito al lado. Hoy hay una: la
pérdida por difracción de Micius a 1200 km, 22 dB, que no es la de la apertura
de 300 mm que el mismo artículo imprime —la divergencia de ~10 µrad que publica
es 2.8 veces su propio límite de difracción—.

La puerta que sí falla es `tests/validation/test_base.py`, contra
`EXPECTED_DISAGREEMENTS`, y **falla en las dos direcciones**:

- un desacuerdo nuevo que no esté en la lista pone CI en rojo;
- y un desacuerdo listado que **empieza a coincidir** también. Es buena noticia,
  y es una noticia que hay que leer: la nota del caso y el párrafo de ADR que la
  explica describen un desacuerdo que ya no existe, y quedarse callado los
  dejaría mintiendo.

`PENDING_DISAGREEMENTS` guarda aparte los desacuerdos de casos **que todavía no
existen** —los seis de `ntanos2021` y el de Lim et al.—, porque
`EXPECTED_DISAGREEMENTS` no admite una clave que ningún módulo produce: una
entrada inalcanzable es una afirmación que nadie puede comprobar, que es
justamente lo que este ADR persigue.

### 4. Un desacuerdo **no** es un fallo del comando: `quoss validate` sale 0

`python -m quoss.validation` y `quoss validate` devuelven cero aunque la tabla
contenga filas `not reproduced`. Lo único que falla es **no poder calcular la
tabla**: una función de física que rechaza sus entradas, un caso cuyo estado
declarado no produce, dos casos con el mismo identificador.

**Por qué, que es lo menos evidente de este ADR.** Un comando que fallara con un
desacuerdo publicado enseñaría a su usuario a dejar de ejecutarlo —y un comando
que nadie ejecuta no valida nada—; además pondría al autor de una fila nueva en
la posición de elegir entre publicar el desacuerdo y tener CI en verde, que es
exactamente el incentivo que produce insignias. Separando las dos cosas, una
persona puede regenerar el documento en una rama donde algo discrepa, **verlo en
el diff** y decidir, mientras CI sigue negándose a dejarlo pasar sin explicación.

### 5. La tabla se genera, se **commitea**, y un test compara las dos — **decidido, no implementado**

`docs/validation.md` será un fichero generado y versionado, con el comando que lo
reescribe citado dentro (`REGENERATE_COMMAND`, que ya existe y ya se aserta en
`tests/validation/test_main.py`), y un test que falle cuando el fichero difiera
del texto que el código produce.

**Estado al 2026-09-19: el fichero no existe todavía**, y esto es una decisión
tomada y no una descripción del árbol. Es la etapa 8 del roadmap, junto con
`ntanos2021.py`. Se escribe aquí porque la decisión se toma ahora —el renderizado
ya está implementado y la política de salida depende de ella— y porque decir
«decidido y pendiente» es lo honesto: lo que este ADR no puede hacer es describir
en presente algo que no se cumple.

**Por qué committear algo generado.** Porque el lector al que esta tabla va
dirigida —un revisor, alguien decidiendo si creerse una cifra— llega por el
repositorio y no ejecuta nada. Y porque un fichero versionado hace que **un
cambio de estado aparezca en un diff**, que es la única forma de que a alguien
le salte a la vista que una fila pasó de `reproduced` a `not_reproduced`. El
riesgo de un generado commiteado es que envejezca; lo cubrirá el test.

---

## Alternativas descartadas

**Una insignia en el README («validated against the literature»).** Es
literalmente el patrón que este ADR nombra: una palabra que no se recalcula y
que sobrevive al acuerdo que describía. Además es **agregada**: colapsa 22 casos
de tres fuentes, con estados distintos, en un único verde que oculta la fila que
más importa.

**Un porcentaje («85 % reproducido»).** Peor que la insignia, porque parece una
medida. Un porcentaje trata todos los casos como equivalentes, y no lo son: la
fila que falta —Ntanos et al. 2021, la fuente del enlace de referencia entero—
pesa más que las quince que sí están. Un número agregado la esconde; una tabla
con un hueco declarado la enseña.

**Estados escritos a mano, revisados en la PR.** Es lo que hace casi todo el
mundo y falla por omisión, no por malicia: la revisión ocurre el día que se
escribe el caso y no el día que la física cambia.

**Hacer fallar el comando con cualquier desacuerdo.** Ver el punto 4: convierte
publicar un desacuerdo en un coste, y lo que se optimiza entonces es la tabla.

**Congelar la salida de este proyecto como referencia.** Eso es V4 y no es
validación; `tests/golden/README.md` lo dice y SimulCTTC es el ejemplo de lo que
pasa cuando se hace (cuatro defectos que congelar su salida habría canonizado).

---

## Consecuencias

- **Lo que se puede afirmar hoy es lo que la tabla dice, y no más.** 22 casos,
  tres fuentes: 14 reproducidos, 1 compatible, 1 no reproducido, 6 huecos. La
  fuente del enlace de referencia de este proyecto —Ntanos et al. 2021— **no
  está todavía en la tabla**, y cualquier cosa reportada como validada contra
  ella traza a las aserciones de `tests/channel/` y `tests/qkd/`, no a una fila
  de aquí. Es la etapa 8.1 del roadmap.
- **Añadir un caso cuesta escribir su tolerancia con su base**, porque el
  constructor la exige. Es el coste que hace que la tabla signifique algo.
- **`quoss validate` es la forma instalada del mismo comando**, con la misma
  política de salida; el módulo `__main__` sigue existiendo porque
  `REGENERATE_COMMAND` lo cita dentro del documento generado, y un documento que
  nombra un comando que nadie puede ejecutar es peor que no nombrar ninguno.
- **Lo que falta para cerrar la etapa 8** son dos cosas y están en el roadmap:
  `ntanos2021.py` con sus filas, y el test que compara `docs/validation.md`
  commiteado con el generado.

---

## Referencias

- `tests/golden/README.md` — los cuatro niveles V1–V4, y por qué V4 no es
  validación. Es el dueño de esa definición; este ADR la usa.
- [ADR 0009](0009-citation-policy.md) — una cita es una fuente abierta, y los
  huecos se declaran. `gap` es esa regla dentro de la tabla.
- `src/quoss/validation/base.py` — `classify`, la regla; `ValidationCase`, la
  comprobación; las dos listas de desacuerdos.
- `src/quoss/validation/__main__.py`, `src/quoss/cli/validate.py` — la política
  de salida del punto 4, en los dos sitios desde donde se invoca.
- `notes/ROADMAP.md`, etapa 8 — qué falta.

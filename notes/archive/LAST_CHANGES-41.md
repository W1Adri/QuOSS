# Archivo de `LAST_CHANGES.md` — §41

> **Qué es esto.** Una entrada de la bitácora del proyecto, **íntegra y sin
> editar**, sacada del camino de lectura obligatorio y no borrada. La regla es
> la suya propia: `notes/LAST_CHANGES.md` guarda las cinco últimas entradas
> completas y el resto vive aquí, con una línea por entrada en el índice del
> fichero vivo.
>
> **Por qué esta y por qué ahora.** Por su propia cota estructural al entrar
> §46, y **solo después de comprobar que todo lo que carga peso en ella vive ya
> en otro sitio**. Comprobado, uno a uno:
>
> - La regla de las cinco entradas, la cota del encabezado y la de una entrada
>   suelta, con la derivación de cada número: en el docstring de
>   `tests/unit/test_notes.py` y en sus constantes, que es donde se asertan.
> - Que 240 de los 241 números que el ROADMAP citaba vivían ya en un ADR, un
>   test o un docstring: en la cabecera de `notes/ROADMAP.md`.
> - La escalera de lenguajes y los cuatro niveles de distribución, que esta
>   entrada sacó de la guía: en los
>   [ADR 0026](../../docs/adr/0026-the-language-ladder.md) y
>   [0027](../../docs/adr/0027-four-levels-of-distribution.md).
> - Las catorce citas a apartados de la guía y el test que las resuelve: en
>   `tests/unit/test_notes.py::test_every_guide_section_cited_from_the_code_exists`,
>   que desde §46 tiene dos hermanos, uno para ficheros y otro para nodos.
>
> No se ha borrado nada. Lo que sigue es el texto tal cual estaba, enlaces
> relativos incluidos.

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

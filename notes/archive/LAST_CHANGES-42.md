# Archivo de `LAST_CHANGES.md` — §42

> **Qué es esto.** Una entrada de la bitácora del proyecto, **íntegra y sin
> editar**, sacada del camino de lectura obligatorio y no borrada. La regla es
> la suya propia: `notes/LAST_CHANGES.md` guarda las cinco últimas entradas
> completas y el resto vive aquí, con una línea por entrada en el índice del
> fichero vivo.
>
> **Por qué esta y por qué ahora.** Por su propia cota estructural al entrar
> §47, y **solo después de comprobar que todo lo que carga peso en ella vive ya
> en otro sitio**. Comprobado, uno a uno:
>
> - La escalera de lenguajes, las tres condiciones de entrada de la etapa 2.4 y
>   el perfil que dice que hoy no toca —incluido el hallazgo de que los 55.6 s
>   de sesenta satélites miden el bucle en serie de `propagator.py:535` y no la
>   aritmética—: en el
>   [ADR 0026](../../docs/adr/0026-the-language-ladder.md), y el trabajo que
>   sale de él está en `notes/ROADMAP.md` como etapa 11.
> - Los cuatro niveles de distribución y la asimetría que descarta el binario
>   descargable: en el
>   [ADR 0027](../../docs/adr/0027-four-levels-of-distribution.md). La cifra de
>   `pyarrow` que esta entrada corrigió vive hoy medida y defendida en
>   `pyproject.toml`, y §44 la volvió a medir.
> - La cota estructural que sustituyó al objetivo de 900 líneas, con la
>   derivación de cada número: en el docstring y las constantes de
>   `tests/unit/test_notes.py`, que es donde se aserta.
> - Las dos inconsistencias que esta entrada dejó abiertas, #17 y #18, están
>   **cerradas**: la primera en §46 y la segunda en §45, con su justificación
>   en `notes/INCONSISTENCIAS.md`.
>
> Nada de lo de abajo se ha editado al moverlo.

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

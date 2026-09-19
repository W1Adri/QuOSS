# ADR 0028 — La CLI no calcula nada, y un resultado horizontal tiene su propia forma de directorio

- **Estado:** aceptada
- **Fecha:** 2026-09-19
- **Etapa:** 7 (`cli/`) + 6 (`io/export.py`)
- **Afecta a:** `cli/main.py`, `cli/run.py`, `cli/sweep.py`, `cli/validate.py`,
  `cli/report.py` (nuevos), `io/export.py` (`ScalarBlockResult`, `AnyExportable`,
  `SHAPES`, `ExportManifest.shape`), `scenario/result.py`
  (`HorizontalResult.to_manifest_and_blocks`), `scenario/models.py`
  (`expected_degradations`, `HASH_EXCLUDED_FIELDS`), `pyproject.toml`
  (`[project.scripts]`), `scenarios/sweeps/ge1_distance.yaml` (nuevo).
- **Extiende** al [ADR 0027](0027-four-levels-of-distribution.md) (esto es el
  nivel 0, el que va primero y del que los otros tres son clientes), al
  [ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md) (la misma
  afirmación, una capa más arriba), al
  [ADR 0024](0024-the-horizontal-scenario.md) (los dos resultados, y el
  argumento de los arrays de longitud cero que aquí se aplica a los ficheros) y
  al [ADR 0015](0015-external-data-isolation-and-snapshots.md) (el export y su
  manifiesto).

---

## Contexto

### Qué se está decidiendo

Dos cosas que son la misma historia, y por eso están en un ADR y no en dos: **la
CLI**, que es lo único de este proyecto que una persona ejecuta directamente, y
**qué escribe un export cuando el resultado es horizontal**, que es el hueco que
la CLI destapa en cuanto alguien escribe `quoss run scenarios/ge1_1km.yaml`.

### El estado de partida, con sus dos defectos

**`[project.scripts]` prometía un comando roto desde la etapa 0.** El
`pyproject.toml` declara `quoss = "quoss.cli.main:main"` desde el primer commit
del proyecto, y `quoss/cli/` estaba vacío. El instalador escribe el script de
consola igualmente —no comprueba que el objetivo exista—, así que **cualquier
instalación dejaba un `quoss` que moría con `ModuleNotFoundError: No module
named 'quoss.cli.main'`**. Medido antes de esta PR, sobre el `.venv` de
desarrollo: `.venv/bin/quoss` existe, tiene 343 bytes, y su primera línea
efectiva es el `import` que falla.

**`io/export.py` no sabía escribir un `HorizontalResult`.** Desde el ADR 0024
hay dos resultados; `export_result` estaba tipado sobre un protocolo
`ExportableResult` que pide `to_manifest_and_arrays`, y el horizontal no lo
tiene. Medido: `export_result(run(load_scenario("scenarios/ge1_1km.yaml")), …)`
levantaba `AttributeError: 'HorizontalResult' object has no attribute
'to_manifest_and_arrays'`. Era la [inconsistencia #15](../../notes/INCONSISTENCIAS.md),
dejada explícitamente para esta etapa porque **decidir qué escribe es una
decisión de la etapa 7**, no un cableado de la 5.

---

## Decisión

## Parte A — El export escribe dos formas de directorio, y las nombra

### A.1 Dos formas, `downlink` y `horizontal`, declaradas en `manifest.json`

| | `downlink` | `horizontal` |
|---|---|---|
| tablas | `passes.csv`, `daily.csv`, `series_<estación>.csv` | `budget.csv`, `session.csv` |
| arrays | `arrays.npz` | **ninguno** |
| envoltorio | `manifest.json`, `README.txt`, `result.json` | igual |

`manifest.json` lleva `export.shape` con una de las dos cadenas, y `README.txt`
lo dice en su primera línea.

**Por qué un nombre y no «se deduce de qué ficheros hay».** Porque la deducción
va por la **ausencia**, y una ausencia no dice por qué. Un consumidor que abre
un directorio sin `passes.csv` tiene al menos tres lecturas igual de plausibles:
«el export falló a medias», «no se pidió el formato CSV» y «este enlace no tiene
pases». Las tres producen código distinto y solo una es cierta, y equivocarse no
levanta ningún error: se lee como «cero pases».

Es **exactamente** el argumento del ADR 0024 una capa más abajo. Allí se
rechazaron los arrays de longitud cero porque `daily.finite_bits.sum()` sobre un
eje vacío es `0.0`, y **un enlace que certificó 15.2 Mbit se reportaría como
cero bits al día** sin error en ninguna parte. Aquí el objeto es un fichero en
vez de un array, y el fallo es el mismo: «no aplica» y «salió cero» no se pueden
distinguir. La forma con nombre los distingue **antes de abrir un fichero**.

### A.2 Las dos formas no comparten ningún nombre de fichero de datos

Solo coinciden en el envoltorio (`manifest.json`, `README.txt`, `result.json`).
Nada de `passes.csv` con columnas vacías, nada de `budget.csv` en un directorio
de bajada. Hay test de la disyunción, porque es la propiedad que hace que la
ausencia de `passes.csv` sea inequívoca en lugar de una lectura que el consumidor
tiene que adivinar.

### A.3 El despacho es por **qué método ofrece el resultado**, y los dos protocolos son disjuntos

```python
class ExportableResult(Protocol):      # la forma downlink
    def to_manifest_and_arrays(self) -> tuple[dict, dict[str, np.ndarray]]: ...

class ScalarBlockResult(Protocol):     # la forma horizontal
    def to_manifest_and_blocks(self) -> tuple[dict, dict[str, dict]]: ...
```

Tres cosas, y cada una tiene su razón:

1. **No es un `import` de `HorizontalResult` en `io/export.py`.** El paquete
   `io/` no importa nada de `scenario/` hoy —se comprueba: sus seis módulos
   importan de `core`, de `orbits` y de sí mismos— y el protocolo existe
   precisamente para que el exportador no dependa de las clases de resultado ni
   de Pydantic. Un `isinstance` sobre el tipo real lo acoplaría.
2. **No es «`to_manifest_and_arrays` devolviendo un dict de arrays vacío».** Es
   la opción más corta y es la que hay que rechazar: un `HorizontalResult` que
   satisficiera `ExportableResult` **exportaría por el camino de bajada**, no
   encontraría `passes` ni `daily` en su manifiesto, registraría dos `INFO` de
   «tabla ausente» y escribiría un `arrays.npz` sin nada dentro. El resultado es
   un directorio que se parece al de bajada de un enlace que no certificó nada
   — precisamente lo que A.1 existe para impedir.
3. **Los dos protocolos no comparten ni un método**, y hay un test que lo
   aserta como propiedad. Mientras sean disjuntos, el `isinstance` estrecha y
   **el type checker rechaza el camino equivocado antes de que se pueda tomar**;
   el día que uno gane un método que el otro también tiene, deja de estrechar.
   Por eso la disyunción es una aserción y no una costumbre.

### A.4 Un bloque es **una fila**, no una columna de términos

`budget.csv` tiene trece columnas y una fila; `session.csv`, doce y una fila. La
alternativa —formato largo, `término,valor`— es más legible para un único
resultado y peor para todo lo demás: con una fila por ejecución, **N exports se
concatenan en una tabla de N filas**, que es lo que un barrido sobre distancia
es en disco. `session.csv` lleva además las tres columnas derivadas que un
lector compara entre sesiones de distinta longitud: `finite_bit_s`,
`asymptotic_bit_s` y `has_key`.

Un bloque que no sea plano —un mapa anidado, una lista— es `DomainError`, no un
JSON metido en una celda: una celda con JSON dentro se lee como dato y no lo es.

### A.5 Pedir `npz` sobre la forma horizontal no escribe un archivo vacío, y lo dice

Se registra un `INFO` `io.export-no-arrays` explicando que este resultado no
tiene arrays y que el contenido entero está en `result.json`. No se escribe
`arrays.npz`.

**Por qué no escribirlo vacío**, aunque el módulo diga en otro sitio que un
formato pedido no se salta en silencio: un `.npz` con cero entradas es
indistinguible de un export cuyos arrays salieron vacíos. Es la versión
«fichero» del array de longitud cero. Y **por qué no fallar**: el enlace se
calculó bien y su resultado está completo en el directorio; abortar un export
correcto porque uno de los tres formatos no aplica convertiría
`--format json csv npz` —el valor por defecto— en un error para media de los
escenarios del repositorio.

---

## Parte B — La CLI

### B.1 La CLI **no calcula nada**, y se aserta como lo aserta el ADR 0016

La regla: `cli/` traduce argumentos a una llamada y un resultado a ficheros.
No decide qué geometría corre (lo decide el campo `link` del fichero, y
`engine.pipeline.run` despacha sobre él), no decide qué ficheros escribe el
export (lo decide la forma del resultado, A.3), no evalúa una métrica (lo hace
`engine.sweep.metric_value`) y no renderiza la tabla de validación (lo hace
`validation.base.render_markdown`).

**La aserción es la del ADR 0016 una capa más arriba.** Aquel dice que el motor
no calcula nada que no calcularía una persona llamando a las funciones a mano, y
lo prueba por igualdad exacta etapa por etapa. Este dice que **lo que `quoss
run` escribe reconstruye un resultado igual, término a término, a
`run()` llamado a mano sobre el mismo fichero**, para las dos geometrías
(`tests/cli/test_run.py`). Se excluyen dos campos y se nombran:
`provenance.created_utc` y `timings`, que son lecturas de reloj de pared y
difieren entre dos ejecuciones de cualquier cosa. Todo lo demás —cada número,
cada aviso, el hash y el escenario entero— entra en la comparación.

Y se comprueba además que **reconstruye la clase correcta**: la igualdad de
`to_dict()` pasaría para dos contenedores distintos con los mismos números, y el
punto entero de los dos contenedores del ADR 0024 es que una ejecución
horizontal no vuelva como una de bajada con agujeros.

### B.2 Los `warnings[]` se imprimen **enteros**

Cada entrada, con sus cinco campos: `severity`, `code`, `where`, `message` y
`details`. Sin resumir, sin truncar y sin sustituirlos por un recuento.

**Por qué, con el caso que lo produce.** Cada campo es el único que contesta
alguna pregunta que el lector va a tener: el `code` es lo que un script busca,
el `where` es qué función lo hizo, el `message` es qué se sustituyó por qué, y
los `details` llevan los números que lo provocaron. «3 avisos (1 degradado)» no
contesta ninguna. Y el caso concreto es el horizontal: ahí viven
`horizontal.block-is-the-declared-session` —«el bloque finite-key es la sesión
que declaraste, y nada en la geometría la fija»— y
`horizontal.session-without-key`, que **lleva la cifra asintótica al lado del
cero certificado**. Esas dos entradas son la diferencia entre «el enlace no
cierra» y «el asintótico decía 4.4 kbit/s», y un lector que ve «2 avisos» tiene
el recuento y no el hallazgo.

Contar **además** no está prohibido: el `[2/5]` delante de cada entrada es
navegación. Lo que está prohibido es contar **en vez de**.

Los avisos van a **`stderr`**, para que un `quoss run` con la salida estándar
redirigida siga enseñándolos. Y se imprime el **log completo**, no
`result.warnings`: los dos difieren exactamente en lo que registró el *export*,
que el resultado no puede llevar porque ya estaba construido —`io.export-no-arrays`
es una de ellas, y es justo la línea que explica por qué no hay `arrays.npz`—.

### B.3 Salida distinta de cero ante un `DEGRADED` que el escenario **no declara**

`DEGRADED` significa que un modelo fue **sustituido**, así que los números ya no
son los del modelo que se pidió. Una canalización que escribe una figura con eso
sin enterarse ha publicado algo que no calculó. Pero una sustitución puede estar
perfectamente entendida y aceptada, y fallar sobre ella haría inútil el código
de salida: la única manera de mantener verde un script sería dejar de mirarlo.

Así que el escenario declara cuáles espera, en `expected_degradations`, y el
estado de salida es sobre la **diferencia**: un código que el autor ha mirado y
listado se acepta; uno que aparece sin estar listado es fallo.

**El campo está fuera del hash** (`HASH_EXCLUDED_FIELDS`). Es una afirmación
sobre *qué tolera el lector*, no sobre lo que el código calcula: el mismo
escenario produce exactamente los mismos números esté o no listado un código.
Dos ficheros que difieren solo ahí tienen que compartir entrada de caché —hay
test de que el digest no se mueve—, porque **aceptar un aviso no puede
reejecutar un día de Monte Carlo**. El digest fijado de
`reference_castelldefels` sigue siendo `17f44003…`, que es la comprobación de
que no se cambió el contrato al añadir el campo.

Los cuatro estados de salida:

| | |
|---|---|
| `0` | Terminó y no registró ningún `DEGRADED` no declarado. |
| `1` | Terminó y registró alguno. **Los ficheros se escriben igual**: la ejecución no está mal, está *no es lo que se pidió*, y quien tenga que inspeccionar la sustitución necesita los números que produjo. |
| `2` | Uso: una opción mala o un argumento que falta. Es el estado propio de `argparse`, conservado en vez de remapeado, que es la convención del shell. |
| `3` | No se pudo hacer la ejecución: un `QuossError` —escenario inválido, función de física rechazando sus entradas, fichero que no está—. |

### B.4 El `spec` de `quoss sweep` es un **fichero**, no una cadena en línea

`quoss sweep escenario.yaml spec.yaml`, con el spec en YAML o JSON por sufijo
(la misma regla que `scenario/io.format_for_path` aplica al escenario):
`parameters` (rutas con puntos a listas de valores), opcionalmente `mode`
(`grid` o `zip`) y `metrics`.

**Por qué no `"path.path_length_m=200,1000,5000"`.** Por la misma razón por la
que el escenario es un fichero y no un request (ADR 0014, principio 1): **una
figura tiene que ser reproducible desde algo que esté commiteado**. Una cadena
en línea vive en un historial de shell, que no está versionado, no se hashea y
no es lo que se le puede pasar a un revisor. Escribir el fichero cuesta tres
líneas. Además evita que este módulo se convierta en el parser de un segundo
lenguajito cuyas reglas de escapado no escribió nadie.

`scenarios/sweeps/ge1_distance.yaml` es el primero, y reproduce el hallazgo de
`LAST_CHANGES.md` §40 por el camino de la CLI: 23 696 707 bits certificados a
200 m, 15 236 099 a 1 km, 2 098 831 a 2410 m y **exactamente cero** a 5 km
mientras el asintótico sigue reclamando 267 678 (4.46 kbit/s) — que es por lo
que el spec pide las dos métricas.

Una clave desconocida en el spec es un error que **nombra las tres que existen**.
Un `parameter:` en vez de `parameters:` saldría si no como «un barrido necesita
al menos un parámetro», dejando al lector mirando un fichero que visiblemente
tiene parámetros dentro.

### B.5 `quoss validate` sale 0 con un desacuerdo publicado

La misma política de `python -m quoss.validation`, con su justificación en el
[ADR 0018](0018-validation-is-a-table-not-a-badge.md): un desacuerdo publicado
es una tabla *correcta*, y un comando que fallara sobre él enseñaría a su
usuario a no ejecutarlo. Lo que falla es no poder calcular la tabla, y eso llega
como excepción y sale `3`.

### B.6 `argparse`, no un framework de CLI

Tres subcomandos y una docena de opciones no lo necesitan, y un framework es una
dependencia que cargaría **todo el que instale el núcleo de física**. La lista
de dependencias del núcleo son cinco paquetes a propósito, por el mismo
argumento que el ADR 0027 hace sobre los niveles de distribución: lo que la
gente instala para calcular física no debería crecer por la comodidad del shell
que tiene delante.

### B.7 Un `QuossError` se imprime como mensaje, no como traceback

Un `QuossError` es este proyecto diciendo «tus entradas están mal y este es el
campo»: los mensajes están escritos para leerse, nombran la ruta del valor
ofensor y están asertados en la suite. Poner cuarenta líneas de traceback encima
entierra la frase que importa bajo la maquinaria que la produjo. Cualquier otra
excepción —un `OSError`, un fallo de este proyecto— conserva su traceback,
porque ahí la maquinaria **es** la información.

---

## Alternativas descartadas

**Una opción `--horizontal` en `quoss run`.** Sería un segundo sitio donde se
declara la geometría, y el día que los dos no coincidan gana la opción y el
fichero se lee como algo que no es. El campo `link` ya lo dice en su primera
línea, y el ADR 0024 lo hizo obligatorio precisamente para eso.

**Una forma de directorio con las tablas inaplicables omitidas y sin nombrar la
forma.** Es A.1: la ausencia no dice por qué.

**Una forma de directorio con `passes.csv` de cero filas.** Peor: un consumidor
lo lee, obtiene una tabla vacía, y suma cero.

**Un `--strict` que falle con cualquier `DEGRADED`.** Sin el campo en el
escenario, la única forma de tener un script verde con una sustitución conocida
y aceptada es no usar la opción — y entonces ninguna sustitución se detecta. La
declaración por escenario es lo que permite que el estado de salida signifique
algo en las dos direcciones.

**Meter `expected_degradations` en el hash.** Rompería el digest fijado, exigiría
un `SCHEMA_VERSION` nuevo, y haría que aceptar un aviso invalidara la caché de
una ejecución cuyos números son idénticos.

**Un resumen de avisos con `--verbose` para verlos enteros.** El caso por
defecto es el que se lee, y por defecto estaría el resumen.

---

## Consecuencias

- **El comando instalado funciona, y eso se prueba como subproceso.**
  `tests/cli/test_main.py` ejecuta `.venv/bin/quoss`, no importa el módulo: un
  import no ve una cadena de entry point equivocada, ni un script de consola que
  el instalador nunca escribió. Hay una segunda guarda por el otro lado, que lee
  `[project.scripts]` del `pyproject.toml` y comprueba que el módulo y el
  atributo existen; las dos fallan con mensajes distintos.
- **La inconsistencia #15 se cierra**, y no con un arreglo mínimo: el resultado
  horizontal tiene forma de archivo propia, con su manifiesto, sus hashes por
  fichero y un test de que el directorio reconstruye el resultado real.
- **`HorizontalResult` sigue sin tener `to_manifest_and_arrays`**, y es
  deliberado. Su docstring ya decía que no tener contrapartida de arrays no es
  una omisión; ahora además es lo que mantiene los dos protocolos disjuntos.
- **Los escenarios ganan un campo opcional** con valor por defecto vacío, así
  que ningún fichero existente cambia y ningún digest se mueve.
- **El roadmap cambia de estado**: la etapa 7 pasa a completa salvo el `viz/`
  que ya estaba, y el defecto del `[project.scripts]` deja de estar abierto.

---

## Referencias

- [ADR 0027](0027-four-levels-of-distribution.md) — el nivel 0 y por qué va
  primero.
- [ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md) — la afirmación
  que este ADR repite una capa más arriba, y la forma de asertarla.
- [ADR 0024](0024-the-horizontal-scenario.md) — los dos resultados, y el
  argumento de los arrays de longitud cero del que sale A.1.
- [ADR 0011](0011-the-block-is-the-pass.md) — el acantilado que produce la
  sesión sin clave que `quoss run` tiene que enseñar entera.
- [ADR 0014](0014-scenario-contract-and-provenance.md) — el escenario es un
  dato; B.4 lo aplica al spec de un barrido.
- [ADR 0018](0018-validation-is-a-table-not-a-badge.md) — la política de salida
  de `quoss validate`.
- `src/quoss/cli/report.py` — las dos decisiones de B.2 y B.3, donde se aplican.
- `notes/INCONSISTENCIAS.md` #15 — lo que esto cierra.

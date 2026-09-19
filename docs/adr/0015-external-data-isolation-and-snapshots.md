# ADR 0015 — El mundo exterior entra por inyección, y lo que entró se puede reproducir sin red

- **Estado:** aceptada
- **Fecha:** 2026-09-13
- **Etapa:** 6 (`io/cache.py`, `io/celestrak.py`, `io/openmeteo.py`, `io/snapshots.py`, `io/export.py`, `io/stations.py`, `quoss/data/ogs.yaml`, `quoss/data/snapshots/`)
- **Afecta a:** todo resultado que use un TLE o una serie de nubes reales, a
  la procedencia (`Provenance.data_versions`) que `scenario/result.py` guarda,
  a la demo offline de `notes/archive/GUIA_REIMPLEMENTACION-v3.md` §5, y a
  `engine/` y
  `cli/`, que son quienes llaman a este paquete.
- **Extiende** al [ADR 0009](0009-citation-policy.md): una coordenada de
  estación o un TLE son también «números que se citan», y la regla de que una
  cita es una fuente que se ha abierto se aplica igual. Y al
  [ADR 0007](0007-tle-and-sgp4-propagation.md): la época del TLE, que allí es
  el ancla del propagador, aquí es la *versión* del dato.

---

## Contexto

### Qué se estaba decidiendo, en una frase

Dos de las entradas de un escenario viven en el servidor de otro: el TLE de
un satélite (CelesTrak) y la cobertura de nubes sobre una estación
(Open-Meteo, que sirve el reanálisis ERA5 de ECMWF). Había que decidir **cómo
entran** esos datos en un simulador cuya suite corre sin red y cuya demo no
puede depender del wifi de un congreso, y **qué queda escrito** cuando entran,
para que un resultado pueda decir *qué* TLE y *qué* serie de nubes usó.

### Por qué esto es una etapa tardía y no una utilidad de la etapa 0

Porque una función de física que pueda «ir a buscar» un dato es una función
que puede fallar por una razón que no es física, y una que puede devolver un
número distinto hoy y mañana con los mismos argumentos. `core`, `orbits`,
`channel`, `qkd`, `system` y `engine` se escribieron y verificaron enteros con
datos sintéticos o con ficheros de `data/`, y ninguno importa `quoss.io`. Esa
frase es comprobable con un `grep` y la cumplen los siete módulos de arriba.
La flecha va en un solo sentido: `io` importa `core`, `orbits` y `scenario`;
lo que `io` produce llega a la física **por inyección** —un `TleRecord` que
alguien mete en un escenario, una `CloudCoverSeries` que alguien pasa a
`system/pcflos.py`—, nunca porque la física lo pida.

### El modo de fallo que se estaba cerrando

No es «se cae la red». Es el contrario: **la red funciona, devuelve algo
plausible, y el resultado no dice de cuándo es.** Un TLE de la ISS se reajusta
varias veces al día; una figura calculada con el de hace tres semanas es una
figura con kilómetros de error ([ADR 0007](0007-tle-and-sgp4-propagation.md))
que no se distingue a simple vista de una correcta. Y la comodidad obvia de
cualquier caché —«si no puedo bajarlo, uso lo que tengo en disco»— es
exactamente la forma en que ese error entra sin que nadie lo vea.

---

## Decisión

### 1. Ningún test abre un socket, y hay un test que lo demuestra rompiéndolo

Toda función que podría hacer una petición recibe un `fetch: Callable[[str],
bytes]` inyectado; la implementación real (`urllib_fetch`, la única función
del paquete que puede abrir un socket) es solo el valor por defecto. Los tests
pasan una falsa.

Y no se deja en «los tests no usan la red»:
`tests/io/test_cache.py::TestTheSuiteIsOffline` sustituye `socket.socket` y
`socket.create_connection` por una función que lanza `OSError`, comprueba que
`urllib_fetch` contra CelesTrak **falla** con `DataError`, y a continuación
ejecuta con `fetch` falsos todos los caminos del paquete —`fetch_tle`,
`fetch_cloud_cover`, los dos adaptadores de snapshot, el catálogo de
estaciones y un export completo— y ve que todos terminan. Si alguien mete una
petición real en cualquiera de ellos, ese test falla el mismo día, en CI, no el
día en que no hay wifi.

### 2. La caché HTTP es content-addressed por URL, con TTL obligatorio y sin fallback silencioso

`HttpCache(directory, *, ttl_s, fetch=None, now=None)`:

- **Clave = SHA-256 de la URL.** «Content-addressed» quiere decir que el
  nombre del fichero es función de lo que guarda, así que dos llamadas a la
  misma URL caen en el mismo fichero sin registro que mantener, y una URL con
  `?`, `&` o `/` no hay que escaparla. SHA-256 y no algo más corto porque el
  coste es nulo y una colisión sería sustituir un dataset por otro sin ruido.
- **`ttl_s` no tiene defecto.** Un TLE envejece en un día; una serie ERA5 de
  2025 no cambia en un año. Ningún valor sirve para los dos, así que no se
  adivina.
- **El reloj se inyecta.** `now()` devuelve segundos Unix; el test del TTL
  mueve el reloj en vez de dormir. Medido en `TestTtl`: con `ttl_s=3600`, a
  3599 s la segunda lectura es un acierto y `fetch` se llamó una vez; a 3600 s
  es un fallo y se llamó dos.
- **Una entrada caducada nunca se sirve sin pedirlo.** Si `fetch` falla, el
  defecto es `DataError` con la URL y el estado HTTP. Solo con
  `allow_stale=True` se sirve la copia caducada, y entonces queda un `WARNING`
  `io.cache-stale-fallback` en el `DegradationLog` —que es argumento
  obligatorio de `get`— con la edad de la entrada y el error que obligó.
- **El hash del payload se comprueba en cada lectura.** Una entrada editada o
  truncada se descarta y se vuelve a bajar, con `WARNING`
  `io.cache-corrupt-entry`; la URL es la fuente de verdad, no la copia.

### 3. La versión de un TLE es su época, y la de una serie de nubes es su ventana más la fecha de descarga

`Provenance.data_versions["tle"]` recibe `"<catálogo>@<época JD>"`, p. ej.
`"25544@2461296.67555434"`. Ni «el TLE de la ISS» (se reajusta varias veces al
día) ni la hora de descarga (dos descargas con una hora de diferencia suelen
devolver el mismo conjunto) identifican un conjunto de elementos; la época,
impresa en las columnas 19-32 de la línea 1 con resolución de `1e-8` día, sí.

Para Open-Meteo no hay tal cosa: la respuesta no lleva versión ni nombre del
modelo (la documentación describe un «best match» entre ERA5, ERA5-Land, IFS y
CERRA por región y fecha). La versión es entonces
`"open-meteo-archive:<primer día>:<último día>:fetched=<fecha>"`, y
`CloudCoverSeries.model` lleva la etiqueta del endpoint,
`open-meteo-archive:best_match`, en vez de un nombre de reanálisis que el
código no puede verificar.

### 4. Lo que se descarga se valida antes de existir

`fetch_tle` pasa el texto por `orbits.tle.parse_tle` —longitud, prefijo,
checksum, error de inicialización de SGP4— antes de devolver un `TleRecord`; un
cuerpo `No GP data found`, una página de error de un proxy o una respuesta con
dos objetos mueren aquí como `DataError` con la URL, no más tarde como un fallo
de SGP4 en alguna muestra.

`fetch_cloud_cover` exige `utc_offset_seconds == 0`, unidad `%`, listas de
igual longitud, marcas de tiempo `YYYY-MM-DDTHH:MM`, valores en `[0, 100]` y
estrictamente crecientes. **Una hora ausente (`null`) es `DataError`, no
interpolación.** La cobertura de nubes no es suave —la serie de referencia va
0 → 39 → 82 → 14 % en tres horas consecutivas— y una interpolación no tendría
cota de error; sin cota no hay `DEGRADED` posible, así que se rechaza y el
mensaje nombra las horas que faltan.

Y se registra lo que el usuario no pidió pero recibió: la celda del reanálisis
no es el telescopio. Para Castelldefels (41.2750 N, 1.9875 E) Open-Meteo
sirvió la celda de 41.3005 N, 2.0660 E, a **7.2 km** (INFO
`io.openmeteo-grid-offset`, medido en
`tests/io/test_openmeteo.py::TestGridOffset`).

### 5. Un snapshot es una respuesta real con su manifiesto, o dice «synthetic» en el nombre

`quoss/data/snapshots/<kind>/<name>.json` guarda `{"manifest": {kind, name,
source_url, fetched_utc, sha256, data_version, note}, "payload": <respuesta
verbatim>}`. Tres reglas:

- **`sha256` es el del JSON canónico del payload** (claves ordenadas, sin
  espacios, UTF-8), y `load_snapshot` lo recalcula y lanza `DataError` si no
  coincide. Lo que cierra no es una manipulación: es la edición a mano de un
  número «para que la demo salga», que con el hash es un error ruidoso hasta
  que alguien regenera el manifiesto por `save_snapshot` y tiene que escribir
  en `note` por qué.
- **Un manifiesto nunca afirma una descarga que no ocurrió.** Un payload
  sintético tiene que llamarse `synthetic_*` y decir «synthetic» en la nota;
  `save_snapshot` rechaza las dos combinaciones cruzadas.
- **Usar un snapshot deja rastro:** INFO `io.snapshot-used` con `fetched_utc`,
  `data_version` y si es sintético.

Los dos snapshots que se entregan son **descargas reales**, hechas con `curl`
el 2026-09-13 a las 16:16:24 UTC (HTTP 200 las dos):

| Snapshot | Fuente | Contenido | `data_version` |
|---|---|---|---|
| `tle/iss_zarya` | CelesTrak `gp.php?CATNR=25544&FORMAT=TLE` | ISS (ZARYA), cuerpo verbatim con CRLF y nombre rellenado a 24 caracteres; época 2026-09-13 04:12:48 UTC | `25544@2461296.67555434` |
| `cloud_cover/castelldefels_2025-01-01_02` | Open-Meteo archive, 41.2750 N 1.9875 E, 2025-01-01..02 | 48 valores horarios en %, sin huecos, de 0 a 100 | `open-meteo-archive:2025-01-01:2025-01-02:fetched=2026-09-13` |

No hay ninguno sintético. Las notas de cada manifiesto llevan además el
SHA-256 del cuerpo HTTP crudo, para quien quiera comparar con una descarga
propia.

### 6. El export escribe un directorio que se describe a sí mismo

`export_result(result, directory, *, formats=("json","csv","npz"), degradations)`
escribe `manifest.json` (procedencia, avisos, tiempos y todos los escalares
del resultado, con cada array sustituido por `{"$array": "<clave>"}`) más la
lista de todos los ficheros escritos con su SHA-256; `arrays.npz` con las
arrays tal cual; `passes.csv`, `daily.csv` y un `series_<estación>.csv` por
estación; `result.json` como forma de un solo fichero; y con `"parquet"`, las
mismas tablas por `pyarrow`, que es el extra opcional `quoss[export]` —si
falta, `ConfigurationError("install quoss[export]")`, nunca saltarse el
formato en silencio. Los flotantes van a CSV por `repr`, que es la promesa de
ida y vuelta `float(repr(x)) == x`; NaN (las series fuera de un pase) va como
celda vacía. `manifest.json` + `arrays.npz` es exactamente lo que
`SimulationResult.from_manifest_and_arrays` recibe: el test
`test_npz_and_manifest_rebuild_the_result` reconstruye el resultado y compara
`to_dict()` completo.

### 7. Una estación del catálogo es una coordenada con su fuente, y una apertura que no está en la fuente es `null`

`quoss/data/ogs.yaml` lleva cuatro estaciones. Cada una tiene `source` (con la fecha
en que se abrió la página) y `coordinates_precision` (cuántos decimales imprimió
la fuente y qué valen en el suelo); el cargador exige que ambos sean cadenas
no vacías, que no haya nombres duplicados ni claves desconocidas, y que los
rangos sean físicos. Matera (MLRO) y Graz (Lustbühel) vienen de las páginas
del ILRS, que dan coordenadas pero **no** la apertura del telescopio, así que
`receive_aperture_m` es `null` y `to_station_spec_kwargs()` lanza `DataError`
hasta que quien monte el escenario pase la suya. Rellenar «el 1.5 m que todo
el mundo sabe» sería el número inventado etiquetado como publicado que el
proyecto prohíbe.

---

## Alternativas descartadas

- **`requests` u `httpx` como dependencia.** `urllib.request` de la biblioteca
  estándar hace las dos peticiones que este proyecto necesita; una dependencia
  nueva por dos GET no se justifica, y la función que la envuelve son quince
  líneas cuyo trabajo es convertir tres excepciones de `urllib` en un
  `DataError` con URL y estado.
- **Fallback a la entrada caducada por defecto.** Es la comodidad estándar de
  toda caché y es la que produce resultados sobre datos de hace semanas sin que
  nadie lo sepa. Se deja como opción explícita con aviso.
- **Interpolar horas ausentes en la serie de nubes con `DEGRADED`.** Solo se
  registra una sustitución cuando se puede acotar su coste; la cobertura
  horaria no tiene continuidad que permita acotarlo.
- **Snapshots sintéticos «para tener algo».** Se pudo descargar en vivo, así
  que no hacía falta; y de haber hecho falta, el nombre `synthetic_*` y la nota
  habrían sido obligatorios.
- **Guardar el catálogo de estaciones como `StationSpec` de Pydantic.** El
  catálogo son hechos sobre un lugar; `StationSpec` añade opciones de modelado
  y depende de un esquema que se estaba escribiendo a la vez. Un dataclass
  pequeño y un método puente evitan acoplar los dos.

## Consecuencias

### Lo que ahora se puede afirmar

- Que la suite de `io/` no toca la red, porque hay un test que rompe el socket.
- Que un resultado sobre un TLE real dice qué conjunto de elementos usó
  (`25544@<época>`), y uno sobre nubes reales dice qué ventana y de cuándo es
  la descarga.
- Que la demo corre sin wifi sobre respuestas reales de un día conocido, y que
  un número editado a mano en esas respuestas hace fallar la carga.

### Lo que esto cuesta

- `DEFAULT_SNAPSHOT_ROOT` y `DEFAULT_CATALOGUE_PATH` se resuelven relativos al
  fichero fuente. **Hasta el 2026-09-19 eso era `<repo>/data/...`**, tres
  directorios por encima del módulo, y el coste estaba escrito aquí como
  aplazado: funcionaba en un checkout y con `uv run`, y **no** con el paquete
  instalado, donde `data/` ni siquiera viajaba en el wheel. Cerrado: los datos
  son hoy datos de paquete en `src/quoss/data/`, el ancla es
  `quoss.data.DATA_ROOT` —un directorio por encima, dentro de lo que se copia—
  y el wheel los lleva. La medida y el test que lo comprueba **desde una
  instalación fuera del checkout** están en `LAST_CHANGES.md` §45 y en
  `tests/packaging/test_wheel.py`. Toda función sigue aceptando `root`/`path`
  explícitos, que es lo que usa quien guarda los snapshots en otro sitio.
  Lo que **no** cubre el arreglo, dicho en `quoss/data/__init__.py`: un paquete
  zipimportado no tiene directorio que abrir, y ninguno de los cuatro niveles
  del [ADR 0027](0027-four-levels-of-distribution.md) lo distribuye así.
- La celda de 25 km del reanálisis no es la línea de visión de un pase de
  cinco minutos. Este paquete registra la distancia; qué hacer con ella es de
  `system/pcflos.py`.
- El endpoint y los nombres de campo de Open-Meteo se verificaron contra la
  documentación y contra la respuesta real el 2026-09-13; que un `null`
  represente una hora ausente es la convención general del API y no está
  escrito explícitamente en la documentación. Se rechaza en cualquier caso.

### Lo que queda explícitamente fuera

- Un cliente para ERA5 directo (CDS API) o para otra fuente de nubes.
- Space-Track como fuente de TLE (requiere cuenta).
- NetCDF/xarray como formato de export: `npz` + manifiesto cubre la
  reproducibilidad y `parquet` la analítica; NetCDF añadiría una dependencia
  sin un consumidor hoy.

## Verificación

`tests/io/`: 197 elementos recogidos (186 tests con parametrizaciones, 11
doctests), cobertura de líneas y ramas del 100 % en los siete módulos
(`--cov=quoss.io --cov-branch`). Property-based con `hypothesis` en la clave de
caché (SHA-256 de la URL, inyectiva sobre cadenas) y en la ida y vuelta de CSV
(50 tablas de hasta 40 filas, igualdad exacta) y npz. El export se prueba
contra el `SimulationResult` real de `scenario/result.py`, reconstruyéndolo
desde `manifest.json` + `arrays.npz` y desde `result.json`.

# ADR 0027 — Los cuatro niveles de distribución, y por qué la web es un cliente y no el simulador

- **Estado:** aceptada
- **Fecha:** 2026-09-19
- **Etapa:** gobierna la **7** (`cli/`), la **9** (`api/`), la **10** (`web/`) y
  la **11** (`deploy/`). De las cuatro, solo `viz/` de la 7 está escrita.
- **Afecta a:** `[project.scripts]` de `pyproject.toml:40`, los extras `viz`,
  `export`, `accel` y `web` (`pyproject.toml:42-62`), `cli/main.py`,
  `cli/serve.py`, `api/app.py`, `web/`, `deploy/Dockerfile` y `deploy/compose.yaml`
  — de los cuales **ninguno existe todavía**.
- **Procedencia:** decidido el 2026-07-31 en la *Guía de reimplementación v3* §3,
  vigente desde entonces sin ADR. Igual que el [ADR 0026](0026-the-language-ladder.md),
  esto lo cierra. Texto original en
  [`notes/archive/GUIA_REIMPLEMENTACION-v3.md`](../../notes/archive/GUIA_REIMPLEMENTACION-v3.md).

---

## Contexto

### Qué se está decidiendo, y qué no

**Distribución** aquí significa: en qué forma le llega este simulador a alguien
que no es quien lo escribe. No es cómo se programa —eso es el
[ADR 0026](0026-the-language-ladder.md)— ni qué calcula. Es la respuesta a
«tengo el paper delante, ¿cómo reproduzco la figura 4?».

La pregunta parece de logística y no lo es, porque **la forma de entrega decide
la arquitectura**. Un simulador que solo se puede ejecutar desde un navegador
tiene la física dentro del servidor web, y eso no es una consecuencia
desafortunada: es lo único que puede pasar, porque nadie escribe una capa que no
tiene cliente.

### El caso concreto, que es de este proyecto

**SimulCTTC —el simulador anterior, del que QuOSS es la reescritura— entregaba
por un solo sitio: una web.** El diagnóstico completo está en
[`notes/GUIA_REIMPLEMENTACION.md`](../../notes/GUIA_REIMPLEMENTACION.md) §1, y
la parte que sostiene este ADR es esta: había **~486 líneas de pipeline dentro
de un handler HTTP**, y el escenario existía **solo como cuerpo de un request**.

Las consecuencias no son estéticas y se pueden enumerar:

- **No había CLI.** Correr un barrido de cien escenarios significaba cien clics,
  o escribir un cliente HTTP para tu propio simulador.
- **No había escenario como fichero.** Lo que se simuló no se podía adjuntar a un
  paper, ni versionar en git, ni volver a correr un año después; existía como un
  JSON que ya se había ido.
- **No había test de extremo a extremo limpio**, porque para ejercitar la física
  había que levantar un servidor.
- **La física era inalcanzable sin red.** Un test no puede depender de un socket.

Nada de eso se arregla poniendo una CLI encima al final. Se arregla decidiendo
**antes** que la web es un cliente, y construyendo los niveles en orden.

### Qué son los términos, para quien llegue nuevo

- Un **wheel** es el formato de paquete instalable de Python: un `.zip` con el
  código y un manifiesto. `pip install quoss` o `uv add quoss` descargan uno.
- **`uvx`** (de `uv`) ejecuta un comando de un paquete **sin instalarlo** en el
  entorno de nadie: descarga el wheel a una caché temporal, lo corre y se va.
- Una **imagen Docker** es un sistema de ficheros congelado con todo dentro —
  intérprete, dependencias, código—, de forma que `docker run` produzca el mismo
  resultado en cualquier máquina que la sepa correr.
- **Offline** aquí significa literalmente sin red: el contenedor tiene que poder
  correr el escenario de referencia con la tarjeta de red apagada. Es una
  propiedad que el proyecto ya aserta para la suite, en
  `tests/io/test_cache.py::TestTheSuiteIsOffline`, que rompe `socket.socket`.

---

## Decisión

**Cuatro niveles, el mismo motor en los cuatro, y la web como cliente.**

| Nivel | Qué es | Para quién | Etapa |
|---|---|---|---|
| **0** | `uv run quoss run scenario.yaml --out out/` | El día a día. Reproducible, scriptable, sin servidor. **Aquí salen las figuras del paper** | 7 |
| **1** | `quoss serve` → UI en `localhost` | Exploración interactiva, cero infraestructura | 9 + 10 |
| **2** | Imagen Docker publicada | Cualquiera: `docker run …`. **Funciona offline** | 11 |
| **3** | Servicio cloud público | Opcional, y con condiciones: cola de jobs, límites de escenario, rate limiting | 11 |

**La decisión no es la tabla: es el orden, y que el nivel 0 sea el primero.**
Cada nivel es un cliente del anterior. La CLI llama al motor; `serve` levanta una
API que llama al motor; el contenedor empaqueta lo mismo; el servicio público es
el contenedor con una cola delante. **En ningún nivel hay física que los otros no
tengan**, y eso es lo que hace que la frase «el frontend no calcula física» sea
verificable en vez de una intención: si calculara algo, el nivel 0 daría otro
número.

**El nivel 3 es opcional y lo seguirá siendo.** Un servicio público es una
obligación de operación —disponibilidad, abuso, coste— que un proyecto de
investigación no tiene por qué contraer. El nivel 2 ya da reproducibilidad por
terceros, que es lo que un revisor necesita.

### La consecuencia que hay que aceptar por escrito

**El paper se escribe con el nivel 0 y solo con el nivel 0.** Ninguna cifra
publicable sale de una sesión interactiva, porque una sesión interactiva no deja
un fichero que alguien pueda volver a correr. Eso ya está construido: el
escenario es un YAML versionado, el resultado lleva su `Provenance` con hash de
escenario y commit ([ADR 0014](0014-scenario-contract-and-provenance.md)), y
`viz/figures.py` genera cada figura desde un escenario y no desde una variable.

---

## Lo que esto mide

Medido en este árbol el 2026-09-19, y las cifras son el argumento de las
alternativas descartadas de abajo.

### Lo que pesa el paquete, y lo que pesa lo que arrastra

| Artefacto | Tamaño |
|---|---|
| `quoss-0.1.0-py3-none-any.whl` (`uv build`) | **644 KB**, 85 ficheros al medir (2026-09-19); **648 KB y 90** con `cli/` dentro, y **671 KB y 95** desde que lleva `quoss/data/` (los tres ficheros de datos, su `__init__.py` y la entrada de directorio) |
| `quoss-0.1.0.tar.gz` (sdist) | 1.66 MB |
| `numpy` instalado | 33 MB |
| `scipy` instalado | 91 MB |
| `matplotlib` (extra `viz`) | 30 MB |
| `pyarrow` (extra `export`) | **152 MB** |
| `numba` + `llvmlite` (extra `accel`) | 17 + 172 = **189 MB** |
| `.venv` completo de desarrollo | **742 MB** |

**Lo que estas cifras deciden.** El código de QuOSS es el 0.09 % de su propio
entorno: cualquier forma de entrega que empaquete el stack numérico entero
mueve 124 MB como mínimo —numpy más scipy— para acompañar a 644 KB de física.
Esa asimetría es la razón de las tres alternativas descartadas, y es también la
razón de que `pyarrow` y `numba` sean **extras** y no dependencias: el comentario
del extra `export` en `pyproject.toml` («pyarrow, que son 40 MB y no es una
dependencia de física») tenía la idea correcta y la cifra corta por un factor de
casi cuatro. Hoy dice 152 MiB, con la orden que lo mide al lado. *(Citado por el
extra y no por `pyproject.toml:48`, que es donde estaba el 2026-09-19: un número
de línea es una cita que envejece sin que nada lo note, y en este fichero ya se
había movido.)*

### Dos defectos del nivel 0 que esta medición destapó; los dos están cerrados

1. **~~`[project.scripts]` apunta a `quoss.cli.main:main` desde la etapa 0 y ese
   módulo no existe.~~ Cerrado el 2026-09-19** por el
   [ADR 0028](0028-the-cli-computes-nothing.md), que escribe `cli/`. Medido
   después: instalado el wheel en un `.venv` limpio **fuera del checkout**, el
   comando `quoss` responde a `--version` y corre `quoss run` sobre los tres
   escenarios probados —horizontal, bajada y TLE—, saliendo 0 y escribiendo su
   directorio. El test que lo guarda ejecuta el script de consola **como
   subproceso**, porque un `import` no ve una cadena de entry point equivocada.
2. **~~El wheel no lleva `data/`.~~ Cerrado el 2026-09-19**, el mismo día que
   se midió. Las 90 entradas del wheel eran `quoss/**/*.py` y el `dist-info`:
   `data/ogs.yaml` y `data/snapshots/` no viajaban, y se resolvían relativos al
   fichero fuente, tres directorios por encima del módulo. Con el defecto 1
   cerrado esto **ya era alcanzable**, y se midió: desde la instalación,
   `load_station_catalogue()` resolvía su ruta por defecto a
   `<venv>/lib/python3.13/data/ogs.yaml` —un nivel por encima de
   `site-packages`— y levantaba `DataError: Station catalogue not found at …`.

   **Cómo se cerró.** Los datos pasan a ser **datos de paquete**:
   `src/quoss/data/`, con `quoss.data.DATA_ROOT` como única ancla —un
   directorio por encima de sí misma, o sea *dentro* de lo que se copia— y las
   dos rutas por defecto derivadas de ella. El wheel pasa de **90 a 95
   entradas** y de 648 a **671 KB**.

   **Y se aserta desde donde el defecto existe**, que es lo que costaba:
   `tests/packaging/test_wheel.py` construye el wheel, lo instala en un venv
   limpio **fuera del checkout** —comprobado, no supuesto: la ruta del venv se
   aserta ajena al árbol— y desde ahí carga el catálogo, los dos snapshots
   (con su SHA-256) y corre los tres escenarios. **16 s en total** con la caché
   de `uv` caliente, de los cuales 15 son física; por eso corre en todos los
   jobs y no en uno aparte.

   La comprobación que le da valor es la negativa: devuelto el defecto a mano
   con un `exclude` en `[tool.hatch.build.targets.wheel]`, **fallan cinco de
   los ocho tests** y los tres que pasan son los tres escenarios — porque los
   escenarios commiteados llevan su estación y su TLE en línea y nunca abren
   `quoss/data/`. Es exactamente lo que #18 reportaba: el comando salía 0
   mientras el catálogo no se podía cargar.

   Lo que **no** cubre: un paquete zipimportado, donde `__file__` nombra una
   entrada de un archivo y no hay directorio que abrir. Ninguno de los cuatro
   niveles de arriba distribuye así, y está escrito en
   `quoss/data/__init__.py` en vez de descubrirse.

---

## Decisiones aplazadas, con lo que haría falta para cerrarlas

| Aplazada | Qué falta para cerrarla |
|---|---|
| **Si el nivel 3 se construye alguna vez.** Decidido que es opcional; no decidido que se haga | Que exista una demanda concreta. Construirlo «por si acaso» es exactamente lo que acopló SimulCTTC |
| **Qué límites lleva el nivel 3** (tamaño máximo de escenario, cuota de jobs, rate limit) | Un perfil de coste real del motor, que hoy no existe porque no hay servicio |
| **Si la imagen del nivel 2 lleva los extras `viz` y `export`.** `viz` son 30 MB y `export` 152 | Una decisión de la etapa 11, medida sobre la imagen construida y no sobre el `.venv` de desarrollo, que no es lo mismo |
| **Qué versión de escenario acepta una imagen publicada.** Un YAML de hoy contra una imagen de dentro de un año | El primer cambio incompatible del esquema. `scenario/hash.py` ya clava un digest como guardia del contrato, que es la mitad del problema |

---

## Alternativas descartadas

**Binario descargable (PyInstaller, Nuitka): no.** Un empaquetador de estos mete
el intérprete y todas las dependencias en un ejecutable. Con las cifras de
arriba eso son **124 MB de numpy y scipy como suelo**, antes de matplotlib; el
artefacto es **uno por sistema operativo**, hay que notarizarlo en macOS y
firmarlo en Windows para que no lo bloqueen, y —lo que de verdad lo descarta—
**no es scriptable**: un investigador no puede meter un ejecutable de doble clic
en un bucle de barrido. Un wheel más `uvx quoss run …` da el mismo «descarga y
ejecuta» sin perder ninguna de esas cosas.

*(Los 124 MB están medidos aquí; lo que pesaría el binario concreto, no: eso
depende del empaquetador y de cuánto pode. Queda como orden de magnitud
declarado, no como cifra del proyecto.)*

**WASM / Pyodide: descartado, y revisable.** WebAssembly permitiría correr
Python en el navegador sin servidor, que suena ideal para el nivel 1. El stack
numérico compilado a WASM es hoy notablemente más lento y más pesado de
descargar que el nativo, y el nivel 1 ya resuelve el problema sin servidor
remoto: `quoss serve` es `localhost`. **Revisable** porque es la única de las
tres descartadas cuya razón puede caducar sola, si el stack numérico en WASM
mejora.

**Frontend en JavaScript plano: no. TypeScript, con Vite y Svelte, y las
dependencias vendorizadas** —copiadas al repositorio, no traídas de un CDN al
cargar la página. Las dos razones son del caso de este proyecto: el frontend de
SimulCTTC eran ~16 000 líneas de JavaScript sin tipos, y un CDN es una
dependencia de red en el arranque, lo que rompería la promesa de **offline** del
nivel 2 en el sitio más visible posible.

**Las figuras del paper desde el navegador: no.** Salen de Python
(`viz/figures.py`), cada una desde un escenario versionado. Una figura generada
en el navegador no tiene procedencia: no hay hash de escenario ni commit al que
atarla.

**Poner la física detrás de la API «porque de todas formas va a haber API»: no**,
y es la alternativa contra la que existe este ADR entero. Es exactamente lo que
hizo SimulCTTC, y las cuatro consecuencias están enumeradas arriba con nombre.

---

## Consecuencias

### Lo que cierra

- Las etapas 7, 9, 10 y 11 tienen un dueño escrito para la pregunta «¿por qué
  en este orden?», que hasta hoy vivía en un fichero de notas.
- La regla «el frontend no calcula física» pasa de intención a propiedad
  comprobable: el nivel 0 es el oráculo de los otros tres.
- Los dos defectos del nivel 0 —el `[project.scripts]` roto y el `data/` que no
  viaja en el wheel— quedan medidos y localizados, en vez de descubrirse el día
  de la primera instalación.

### Lo que no cierra

- **Nada de esto está asertado hoy**, porque ninguno de los ficheros existe. Lo
  que sí queda asertable, y es lo que hay que exigir en su etapa: un test que
  instale el wheel y corra `quoss run` **desde la instalación y no desde el
  árbol** (nivel 0), y otro que construya la imagen y la corra con la red
  cortada (nivel 2). Un nivel sin test es una promesa.
- **El extra `web` ya está declarado** (`fastapi`, `uvicorn`,
  `pydantic-settings`) para una etapa 9 que no existe. No es un defecto —declara
  la intención en el sitio correcto— pero sí es una fila que alguien tiene que
  comprobar el día que se escriba, porque lleva ahí desde la etapa 0.

---

## Referencias

- `notes/archive/GUIA_REIMPLEMENTACION-v3.md` §3 — el texto original de los
  cuatro niveles, 2026-07-31.
- `notes/GUIA_REIMPLEMENTACION.md` §1 — el diagnóstico de SimulCTTC, que es lo
  que sostiene «la web es un cliente»: las ~486 líneas de pipeline dentro del
  handler HTTP y el escenario que solo existía como request.
- [ADR 0014](0014-scenario-contract-and-provenance.md) — el escenario como dato
  versionable, que es la pieza sin la cual el nivel 0 no sería reproducible.
- [ADR 0015](0015-external-data-isolation-and-snapshots.md) — el aislamiento de
  la red, que es lo que hace posible la promesa *offline* del nivel 2.
- [ADR 0026](0026-the-language-ladder.md) — la otra mitad: en qué lenguaje se
  escribe lo que aquí se entrega.

# QuOSS — Quantum Optical Satellite Simulator

**QuOSS contesta una pregunta: cuántos bits de clave secreta certifica un enlace
óptico cuántico, y qué habría que cambiar para que certifique más.**

«Enlace óptico cuántico» aquí es un láser atenuado hasta el nivel de fotón único
que lleva estados cuánticos de un extremo a otro —de un satélite a un telescopio
en tierra, o entre dos terminales fijos sobre el suelo— y del que se destila una
clave criptográfica mediante **QKD** (*quantum key distribution*): un protocolo
cuyo argumento de seguridad no depende de que nadie sepa factorizar, sino de que
medir un estado cuántico lo perturba y esa perturbación se puede acotar.

«Certifica» es la palabra que carga el peso. La literatura suele publicar la
**tasa asintótica**: la clave que saldría si la medida durara infinito. Un pase
de satélite dura diez minutos, y la cota de seguridad que aguanta un bloque
finito de datos —la de **Lim et al. 2014**— devuelve bastante menos, a veces
cero. QuOSS calcula las dos y reporta la finita.

**La cifra que resume el proyecto.** Un día del enlace de referencia
(Castelldefels, telescopio de 0.75 m, satélite heliosíncrono a 700 km, noche
clara, máscara de elevación de 10°) tiene cuatro pases. La tasa asintótica
reclama **3.78 Mbit**; la cota finita certifica **0.43 Mbit**, el 11.5 %. Y
**dos de los cuatro pases certifican cero**, donde la asintótica les atribuye
320 y 199 kbit. Por eso `pass_key_volume` devuelve `FINITE` y el número
asintótico solo se alcanza llamando a una función que se llama `asymptotic_…`.

---

## Las respuestas, antes que el proceso

Si has llegado aquí para leer un resultado y no para leer código, estos cuatro
documentos son el resultado. Están **commiteados y generados**: ninguna cifra
dentro está transcrita a mano, y un test vuelve a renderizarlos y falla si
difieren de lo que el código produce hoy.

| Documento | Qué decide |
|---|---|
| [**GE-1**](docs/experiments/GE-1.md) | Dos terminales en tierra a un kilómetro. Qué cuesta la arquitectura, término a término, y qué compra una lente más grande |
| [**GE-0b**](docs/experiments/GE-0b.md) | El mismo enlace sobre un banco óptico, que es el paso previo a montarlo |
| [**Enlace de referencia**](docs/experiments/reference-link.md) | El día de satélite sobre el que se mide todo lo demás |
| [**`docs/validation.md`**](docs/validation.md) | **35 casos de ocho fuentes**: contra qué literatura se comparó cada número, con qué tolerancia, y qué salió |

**Lo honesto de esa tabla son sus ocho filas que no reproducen.** «Validado» en
este proyecto no significa «coincide»: significa «se comparó contra un valor
publicado, con una tolerancia derivada de cómo está impreso ese valor, y el
resultado está escrito» — incluido cuando el resultado es que no cuadra
([ADR 0018](docs/adr/0018-validation-is-a-table-not-a-badge.md)). El desglose
son **17 reproducidos**, **3 compatibles**, **8 no reproducidos** y **7 huecos
de fuente** (la fuente no imprime nada computable).

---

## Instalar y correr un escenario

Requiere [`uv`](https://docs.astral.sh/uv/), que además gestiona la versión de
Python. Cinco líneas, ejecutadas en un entorno limpio y no escritas de memoria:

```bash
git clone https://github.com/W1Adri/QuOSS.git && cd QuOSS
uv sync --extra viz --extra export
uv run quoss --version
uv run quoss run scenarios/reference_castelldefels.yaml --out out/reference
uv run quoss dossier scenarios/ge1_1km.yaml --out out/GE-1.md
```

La tercera línea imprime la versión, el commit y la pila numérica. La cuarta
deja en `out/reference/` un directorio que se describe a sí mismo —un
`manifest.json` con SHA-256 por fichero, los CSV, los arrays y un `README.txt`—
y la quinta escribe el expediente de GE-1 desde cero, en 1.2 s.

**Cuánto tarda la cuarta, desglosado, porque el total engaña:** unos **4.8 s**
de reloj, de los cuales **la física son 0.117 s**. El resto es 0.6 s de
arrancar el intérprete e importar numpy y scipy, y **3.9 s de escribir el
directorio** —CSV, `.npz` y un SHA-256 por fichero—. Si lo que interesa es el
coste del modelo, la cifra es la de en medio, y se obtiene llamando a `run()`
desde Python sin exportar nada.

**`pip install quoss` instala el motor y la CLI, no los escenarios.** Un
escenario es una *entrada* —un fichero YAML versionado cuyo hash entra en la
procedencia del resultado—, así que vive en el repositorio y no en el wheel:
distribuir uno dentro del paquete sería distribuir una entrada sin su historia.
Quien instale desde PyPI y quiera el enlace de referencia sin clonar lo tiene en
Python, en `quoss.scenario.defaults.reference_castelldefels()`.

### Desde Python, de fichero a resultado

```python
from quoss.engine.pipeline import run
from quoss.scenario.io import load_scenario

result = run(load_scenario("scenarios/reference_castelldefels.yaml"))

result.passes.n_passes                      # 4
result.daily.finite_bits.tolist()           # [433442.0]
result.daily.asymptotic_bits.tolist()       # [3779461.558061474]
[w["code"] for w in result.warnings]        # lo que el modelo no pudo afirmar
result.provenance.scenario_hash             # qué entradas produjeron esto
```

Y un enlace de tierra, que desde el
[ADR 0024](docs/adr/0024-the-horizontal-scenario.md) es el otro miembro de una
unión discriminada por el campo `link` y no un caso especial del anterior:

```python
result = run(load_scenario("scenarios/ge1_1km.yaml"))

type(result).__name__                       # 'HorizontalResult' — sin pases ni días
result.budget.total_db                      # 11.637
result.session.finite_bits                  # 15236099.0 en 60 s de sesión
result.session.finite_bit_s                 # 253934.98
```

### Los cuatro subcomandos

```bash
uv run quoss run     scenarios/ge1_1km.yaml --out out/ge1
uv run quoss sweep   scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml
uv run quoss validate
uv run quoss dossier scenarios/ge1_1km.yaml --out docs/experiments/GE-1.md
uv run python -m quoss.dossier          # los tres expedientes a la vez
```

`quoss run` despacha sobre el tag `link` del fichero sin que haya que decírselo,
y **no calcula nada**: lo que escribe reconstruye un resultado igual, término a
término, a `run()` llamado a mano sobre el mismo fichero. Los `warnings[]` se
imprimen **enteros** en `stderr`, nunca resumidos ni contados, y la salida es
distinta de cero cuando aparece un `DEGRADED` que el escenario no declaró en
`expected_degradations` ([ADR 0028](docs/adr/0028-the-cli-computes-nothing.md)).

---

## Lo que el modelo **no** afirma

Un simulador que solo publica lo que sabe hacer es un folleto. Esto es lo que
hay que saber antes de usar una cifra de arriba en un documento de misión:

- **Las cifras de arriba son para una atmósfera que no absorbe ni dispersa.** El
  escenario de referencia declara `zenith_transmittance: 1.0` —«sin extinción
  modelada»—, así que son una **cota superior** sobre la atmósfera y una
  afirmación exacta sobre todo lo demás. Desde el
  [ADR 0023](docs/adr/0023-traceable-extinction.md) la cota tiene tamaño:
  **23 km de visibilidad, la línea más limpia del código meteorológico de la
  UIT, son 0.230 dB cenitales y el 22.7 % de esos 433 442 bits**; 10 km son el
  47.7 %; con 2 km de bruma el día **no certifica nada**.
- **Hay veintitrés huecos de cita declarados** y ninguno rellenado con la
  fuente más plausible ([ADR 0009](docs/adr/0009-citation-policy.md)). Un hueco
  declarado es preferible a un valor publicado falso.
- **SimulCTTC no es un oráculo.** El código anterior de la casa nunca fue
  validado, y leerlo destapó cuatro defectos que congelar su salida habría
  canonizado. Se usa como diff informativo, nunca como `assert`.
- **Un *snapshot* de la propia salida no es validación.** Los cuatro niveles
  —invariantes, valor publicado, implementación independiente, regresión
  propia— están en [`tests/golden/README.md`](tests/golden/README.md), y lo que
  este proyecto reporta como validado traza a los dos de en medio.
- **Prohibido degradar en silencio.** Una entrada mala levanta `DomainError`; un
  modelo que no se puede evaluar sale en `warnings[]` del resultado, nunca en un
  `except: pass`.

---

## Citar QuOSS

El repositorio lleva [`CITATION.cff`](CITATION.cff), que GitHub y Zenodo leen
directamente, y cada versión lleva su tag. El procedimiento para la siguiente
versión —incluido cómo se dispara el DOI de Zenodo desde el tag— está en
[`CHANGELOG.md`](CHANGELOG.md), y el porqué de que se cite la herramienta y no
solo el artículo, en el
[ADR 0030](docs/adr/0030-a-release-is-something-you-can-cite.md).

Todo resultado lleva además su propia procedencia: `result.provenance` guarda el
hash del escenario, la versión del código, el commit, el intérprete, numpy,
scipy y la semilla. `quoss --version` imprime lo mismo para la herramienta.

---

## Estado del proyecto

Las etapas **0 a 8 están cerradas**, y con la 8 se alcanza el **Hito B**:
resultados validados contra literatura y reproducibles por terceros. Lo que
queda —`api/`, `web/`, `deploy/`— es **distribución, no ciencia**, y el
[ROADMAP](notes/ROADMAP.md) lo lista como disparadores y no como plan: dice qué
tendría que pasar para abrir cada etapa, no cuándo se abrirá.

```
src/quoss/     core ✅  orbits ✅  channel ✅  qkd ✅  system ✅
               scenario ✅  engine ✅  io ✅  viz ✅  cli ✅  validation ✅
               dossier ✅
scenarios/     ✅ siete escenarios versionados (.yaml) — cinco escenarios de
                  bajada y dos escenarios de tierra — más sweeps/
src/quoss/data ✅ catálogo de estaciones + snapshots offline con manifiesto
tests/         ✅ unit · orbits · channel · qkd · system · scenario · engine
                  · io · viz · cli · validation · dossier · packaging · e2e
                  · golden
docs/          ✅ 30 ADRs + validation.md + experiments/ (los tres expedientes)
```

Regla de dependencia: `core ← orbits/channel/qkd ← system ← engine ← {cli, viz}`.
Las flechas nunca van al revés.

**Lo que no está en ese árbol tampoco está en el repositorio.** Desde el
2026-09-19 no queda ni un directorio vacío: los cuatro de la raíz
(`benchmarks/`, `deploy/`, `web/`, `validation/`) se borraron en la PR anterior,
y los cuatro que quedaban dentro de `src/quoss/` y `tests/` —`api/`, `kernels/`,
`tests/api/`, `tests/physics/`— en esta. Un directorio vacío **promete**, y dos
de ellos viajaban dentro del wheel. Dónde va cada uno cuando toque lo dicen el
[ROADMAP](notes/ROADMAP.md) y los ADR
[0026](docs/adr/0026-the-language-ladder.md) y
[0027](docs/adr/0027-four-levels-of-distribution.md), que son sitios que no
prometen nada por existir.

### Verificación

| | |
|---|---|
| Suite, entorno del lock | **3 993 tests**, al 2026-09-19 |
| Cobertura | **100 % de líneas y ramas** en todo `src/quoss` |
| Matriz de CI | Python 3.11 / 3.12 / 3.13, macOS arm64, numpy 2.0, y los suelos declarados |

Los **suelos de versión están probados**: el job `minimums` de CI construye el
entorno más bajo que `pyproject.toml` declara —numpy 2.0.2, scipy 1.13.0,
pydantic 2.7.0, sgp4 2.23, pyyaml 6.0, matplotlib 3.11.0, pyarrow 16.0.0, sobre
Python 3.11— y corre la suite entera ahí. Los extras `accel` y `web` **no
declaran suelo**, porque nada los importa todavía y un `>=` que ningún entorno
construye no es un suelo: es una esperanza publicada en los metadatos del wheel.

**Un defecto conocido de la suite**, que no es del paquete:
`tests/viz/test_plots.py` importa matplotlib arriba del fichero, así que sin el
extra `viz` la recogida de `tests/viz/` **falla** en vez de saltarse. El paquete
sí degrada bien —`quoss.viz` levanta `ConfigurationError` diciendo qué
instalar—; es el test el que no. Por eso la línea de instalación de arriba lleva
`--extra viz --extra export`, que es exactamente lo que sincroniza CI.

### Comandos de desarrollo

```bash
uv run pytest           # suite
uv run ruff check .     # lint
uv run ruff format .    # formato
uv run mypy             # tipos (estricto en core/, física y cli/)
```

### Dónde está escrito el porqué

| Fichero | Qué guarda |
|---|---|
| [`docs/adr/`](docs/adr/) | Una decisión no obvia por fichero, numerada y nunca renumerada |
| [`notes/ROADMAP.md`](notes/ROADMAP.md) | Qué existe y qué falta. **Estado, no justificación** |
| [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md) | Las cinco últimas entradas de la bitácora; las anteriores en [`notes/archive/`](notes/archive/) |
| [`notes/INCONSISTENCIAS.md`](notes/INCONSISTENCIAS.md) | Lo que el código o los documentos afirman y hoy no se cumple |
| [`CHANGELOG.md`](CHANGELOG.md) | Qué contiene cada versión y qué **no** afirma |

## Licencia

MIT — ver [`LICENSE`](LICENSE). © 2026 Adrià Sancho.
Proyecto personal; sin afiliación institucional.

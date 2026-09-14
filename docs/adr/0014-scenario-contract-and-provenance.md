# ADR 0014 — El escenario como dato: unidades en la frontera, dos campos sin defecto, un hash sin etiquetas y un resultado con dos formas

- **Estado:** aceptada
- **Fecha:** 2026-09-13
- **Etapa:** 4 (`scenario/`)
- **Afecta a:** todo lo que hay por encima de la física: `engine/`, `io/`, `cli/`,
  `viz/`, `validation/`. Es el contrato que todos leen.
- **Extiende** al [ADR 0001](0001-unit-conventions.md) (aquí *está* la frontera de
  unidades que ese ADR prometía), al [ADR 0009](0009-citation-policy.md) (el hueco 14
  pasa de ser un argumento sin defecto a un campo sin defecto) y al
  [ADR 0011](0011-the-block-is-the-pass.md) (la máscara sin defecto, por la misma razón).

---

## Contexto

### Qué es un escenario, para quien llegue nuevo

Un **escenario** es la descripción completa de una ejecución: qué satélite, qué
estaciones, qué telescopio y qué detector, qué protocolo con qué intensidades,
qué día y con qué paso. Todo lo que el simulador necesita y **nada más**: dos
personas con el mismo fichero y la misma semilla obtienen los mismos números. Se
escribe en YAML o JSON, y `scenario/models.py` es el contrato que ese fichero
tiene que cumplir. `notes/ROADMAP.md` lo llama «el archivo más importante del
proyecto» porque decide **qué puede decir un usuario**: un parámetro que la física
acepta y el esquema no expresa es un parámetro que todo el mundo recibe en su
defecto sin saberlo, y uno que el esquema acepta sin validar es un número plausible
y equivocado esperando su momento.

### Por qué un dato y no una petición

SimulCTTC tomaba las entradas como argumentos de un handler HTTP: una petición,
montada al vuelo, con defectos donde el llamante callaba. `notes/ROADMAP.md`
registra lo que costó: una época que «caía silenciosamente al reloj de pared», de
modo que la misma petición dos días distintos describía dos cielos distintos. Y una
petición no se puede hashear, versionar ni diferenciar, así que nada ataba una
figura a las entradas que la produjeron. Un escenario es lo contrario: un valor
completo, congelado y hasheable. Es **dato**.

### Lo que ya estaba decidido y esta etapa solo tenía que respetar

- El ADR 0001 fija radianes, metros y transmitancia lineal dentro de la física, y
  grados/nm/dB **solo en la frontera con el usuario**, que se convierte «en
  `scenario/io.py`». El guardia `tests/unit/test_conventions.py` lo comprueba sobre
  el AST.
- El ADR 0009 (hueco 14) fija que `zenith_transmittance` es un argumento
  obligatorio y sin defecto de `atmospheric_transmittance`, con un test que lo
  aserta.
- El ADR 0011 §5 mide que la máscara de elevación tiene óptimo interior cerca de
  8° y que un defecto habría escondido un efecto del 6 % de la clave del día.

---

## Decisión

### 1. Las unidades del usuario van en el nombre del campo; la conversión vive aquí y se hace una vez

Cada campo del esquema lleva sufijo de unidad de usuario —`latitude_deg`,
`wavelength_nm`, `pointing_jitter_urad`, `gate_ns`, `timing_jitter_fwhm_ps`— y
cada modelo ofrece la versión en unidad de física como propiedad o método con el
nombre que la física usa —`latitude_rad`, `wavelength_m`, `pointing_jitter_rad`,
`gate_s`, `chain_efficiency`, `to_elements()`, `to_protocol()`, `to_security()`,
`grid()`—. El motor llama a eso y **nunca convierte por su cuenta**, así que hay
un único sitio donde un grado se vuelve radián y el guardia de convenciones puede
comprobar que no hay otro. Las conversiones pasan por `core/units.py`
(`deg_to_rad`, `nm_to_m`, `m_to_km`); las tres que ese módulo no tiene (µrad, ns,
ps) son constantes con nombre en `models.py`.

**Por qué propiedades y no `computed_field` de Pydantic.** Un `computed_field`
entra en `model_dump`, así que un fichero escrito por `dump_scenario` llevaría
`latitude_rad` al lado de `latitude_deg`, y al leerlo bajo `extra="forbid"`
fallaría **sobre su propia salida**. La ida y vuelta manda.

**Por qué `extra="forbid"`.** Una clave mal escrita (`wavelenght_nm`) que se
ignora en silencio deja el campo en su defecto: es exactamente el «número
plausible y equivocado» que el README prohíbe. Con `forbid` es un error con la
ruta del campo.

**Por qué `allow_inf_nan=False`.** Un NaN pasa todas las cotas `gt`/`lt` (toda
comparación con NaN es falsa) y envenena cada array aguas abajo. Ningún campo del
esquema tiene sentido en infinito.

### 2. Dos campos no tienen defecto, y un test lo mantiene así

| Campo | Por qué | Test |
|---|---|---|
| `channel.zenith_transmittance` | ADR 0009 hueco 14: la ley de escala está publicada, el número que escala no, en ninguna fuente que se pueda abrir. Un defecto sería un número inventado etiquetado «publicado» por su posición. Quien no tiene extinción escribe `1.0` y con eso lo declara | `test_models.py::TestTheTwoFieldsWithoutADefault::test_zenith_transmittance_is_required` |
| `passes.minimum_elevation_deg` | ADR 0011 §5: óptimo interior cerca de 8°; bajar de 8° a 2° compra un 71 % más de segundos y destruye el 6.0 % de la clave. Una cantidad con óptimo es variable de diseño | `…::test_minimum_elevation_is_required` |

Todo lo demás con valor publicado defendible lo lleva como defecto, con la fuente
en la descripción del campo.

### 3. Lo que valida aquí, convierte allí: las reglas del esquema son las de los contenedores de física

Un escenario que pasa la validación **no puede** fallar al construir sus objetos
de física. Para eso cada regla de un contenedor tiene su espejo:

- `duration_s` múltiplo entero de `step_s` con la misma holgura relativa `1e-9`
  que `TimeGrid.uniform` (medido con Hypothesis, 60 ejemplos: `k` pasos dan
  `k + 1` muestras, `test_models.py::TestAValidScenarioAlwaysConverts`).
- `0 < decoy < signal`, tres probabilidades en `(0, 1)` que suman 1 con la misma
  holgura `1e-9` de `Bb84DecoyProtocol`, eficiencia ≥ 1, `misalignment ≤ 0.5`.
- `eps` en `(0, 1)` como `SecurityParameters`.
- Puerta ≤ periodo de pulso, la regla de `LinkConditions`, comprobada a nivel de
  escenario porque cruza dos submodelos.
- Periapsis por encima del radio ecuatorial; una órbita heliosíncrona imposible
  (20 000 km) se rechaza llamando a la misma función que luego calcularía la
  inclinación.
- Un TLE se parsea con `parse_tle` **al validar**, así que un checksum corrupto es
  un `ScenarioError` con ruta de campo y no un `DomainError` diez minutos después.
- Un `condition` de la tabla ITU solo con longitud de onda dentro de 530–1500 nm
  (1550 nm cae fuera; la física levantaría `DomainError`, el esquema lo dice antes).
- `protocol.name` contra `PROTOCOLS.names()`: `"e91"` se rechaza con la lista de
  lo que existe.

### 4. Una época ingenua se rechaza: es el defecto de SimulCTTC con otro traje

`time.epoch_utc` tiene que llevar zona horaria y ser UTC. Una `datetime` sin
`tzinfo` la leería Python en la zona de la máquina — «la época cayó al reloj de
pared» con distinta cara —, y el cielo sobre una estación es función del instante
verdadero. El mensaje de error cita el defecto por su nombre.

### 5. El hash excluye las etiquetas, los flotantes van por `repr`, y un valor está clavado

`scenario_hash` es SHA-256 del JSON canónico: claves ordenadas, sin espacios,
ASCII, enums por valor, la época ISO-8601 con `Z`, y **sin `name` ni
`description`**. Dos escenarios con la misma física y distinto nombre comparten
entrada de caché; si no, renombrar un fichero repetiría un día de Monte Carlo.
Todo lo demás entra, opciones incluidas: 200 realizaciones es otro cálculo que
2000, y `schema_version` entra porque los mismos números bajo otro esquema
significan otra cosa.

**Flotantes por `repr`:** `0.1 + 0.2` es `0.30000000000000004` y `0.3` es `0.3`;
son dobles distintos, escenarios distintos, hashes distintos. Redondear antes de
hashear haría que dos ejecuciones con números distintos compartieran caché, que es
errar en la dirección peligrosa. En cambio `1` y `1.0` hashean **igual**, porque el
esquema convierte el entero a `1.0` antes de volcar nada: la ortografía del autor
no es física. Las dos cosas son tests (`test_hash.py::TestFloatsHashByRepr`).

**El valor clavado:** `test_hash.py` fija el digest de `reference_castelldefels()`
en `feafee61…4227`. Es un guardia de estilo V4 —una instantánea de nuestra propia
salida, que no prueba nada de física— y es la herramienta correcta **aquí** porque
lo que guarda es un contrato de serialización: un campo renombrado, un enum por
nombre o una fecha en otro formato dejarían inalcanzable cada resultado cacheado y
desacoplada cada procedencia de su escenario sin que ningún test de física lo
notara. Ese test lo nota, y su fallo es una instrucción: subir `SCHEMA_VERSION`.

### 6. El resultado tiene dos formas, y las dos van y vuelven

`SimulationResult` es un dataclass congelado sobre arrays (no Pydantic: 86 401
elevaciones por estación no pasan por listas de Python en cada validación). Se
escribe de dos maneras:

- `to_dict()` / `from_dict()`: un dict serializable en JSON, arrays como listas,
  **NaN como `null`** (el valor de una serie fuera de pase, donde el canal no se
  evaluó). Es JSON estricto (`allow_nan=False` pasa) y no el token `NaN` no
  estándar de Python.
- `to_manifest_and_arrays()` / `from_manifest_and_arrays()`: el mismo árbol con
  cada array extraído a un `{"clave.con.puntos": np.ndarray}` plano y un marcador
  `{"$array": clave}` en su sitio. El manifiesto es JSON pequeño; los arrays van a
  un `.npz` con su dtype y sus NaN intactos. Es la forma de la caché
  (`engine/cache.py`) y de `io/export.py`.

Medido: las dos formas devuelven un resultado igual campo a campo, dtype a dtype,
para un resultado sin etapas opcionales y para uno con Monte Carlo, multiestación y
relé; una tabla de pases **vacía** conserva `int64` y `bool` al volver
(`np.asarray([])` daría `float64`), y el `.npz` real pasa por `np.savez`/`np.load`
(`test_result.py::TestRoundTrip`).

`Provenance.collect` rellena hash, nombre, `quoss.__version__`, commit de git (o
`None` sin excepción: sin `git`, fuera de un repositorio o con timeout), versiones
de Python/NumPy/SciPy, versiones de datos, semilla y hora UTC. La procedencia no
puede ser la razón de que una ejecución falle.

### 7. Los defectos guardan literales en la unidad del usuario, y un test los ata a las constantes SI

`defaults.py` escribe `dead_time_ns=30.0`, no `NTANOS_SNSPD_DEAD_TIME_S * 1e9`,
porque eso es `29.999999999999996` en binario: un fichero que dijera eso en vez de
30 no lo escribiría nadie, y su hash difiere del YAML escrito a mano. Lo mismo con
`20.0` grados de máscara (`rad_to_deg` de la constante da `20.000000000000007`).
`test_defaults.py::TestTheDefaultsAreTheNtanosConstants` convierte cada literal de
vuelta y lo compara con su constante a `2^-50` relativo — una multiplicación por
una potencia de diez es a lo sumo un redondeo de `2^-53` por lado.

### 8. La estación lleva el viento r.m.s., no el viento en superficie

El brief pedía `ground_wind_speed_m_s = 2.3` con conversión Bufton. Medido al
implementarlo: la Ec. (5) de ITU-R P.1621-2 convierte 2.3 m/s en **21.018** m/s,
no en los 21.0 del modelo HV 5/7 que la física usa por defecto y que el enlace de
referencia usa; el 0.085 % de diferencia movió el presupuesto de pérdidas de
referencia **6.8e-5 relativo (0.0028 dB a 10°)** y bastó para que el escenario de
referencia dejara de reproducir el enlace de referencia con exactitud. Así que
`StationSpec.rms_wind_speed_m_s = 21.0` es el parámetro que la física toma, con
un test que lo ata a la firma de `log_irradiance_variance`; quien tenga viento en
superficie lo convierte con `bufton_rms_wind_speed_m_s` y escribe el resultado.
(`test_models.py::TestUnitsConvertOnceAtTheBoundary::test_the_wind_default_is_the_hv57_value_not_the_bufton_conversion`).

### 9. Los escenarios de Ntanos et al. 2021 dicen qué es del paper y qué es elección

Se releyó el PDF al escribir `defaults.py`. Del paper: altitud 600 km e
inclinación **97.4°** (§4.3, tal como está impresa; la condición heliosíncrona a
600 km da 97.79°, medido con 0.39° de diferencia), coordenadas y altura de las
tres estaciones (§2), transmisor, receptor, protocolo y suelo de 20° (§4.1),
radiancia de la noche de estudio (§4.2.2). Elección de QuOSS, dicha en el
docstring y en los comentarios del YAML: RAAN, argumento del periapsis, anomalía,
forma circular, época y ventana de un día — el paper propaga diez satélites con
STK y no imprime elementos.

Y lo que había que decir en voz alta: el §2 imprime «Skinakas (longitude:
35.2118°, latitude: 24.8981°)», con las etiquetas **intercambiadas** — Skinakas
está en Creta, a 35.2 N 24.9 E; 35° de longitud este cae en Anatolia. Los números
se usan como están impresos bajo las etiquetas corregidas, y un test aserta que
cada «longitud» impresa cae en la banda de latitudes de Grecia y no en la de
longitudes (`test_defaults.py::TestNtanos2021::test_the_printed_coordinate_labels_are_swapped`).

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **`computed_field` para las conversiones** | Entra en `model_dump`; el fichero volcado no se puede volver a leer bajo `extra="forbid"` |
| **Un defecto para `zenith_transmittance` (p. ej. 0.812, el residuo del hueco 14)** | Un residuo que cae en un rango creíble no es prueba de ser lo que parece; sería inventar un V2 por posición |
| **Un defecto para la máscara (20°, Ntanos)** | Óptimo interior a 8° y un 6 % del día en juego (ADR 0011 §5) |
| **Aceptar `datetime` ingenuas como UTC** | Es el defecto del reloj de pared con la mitad del síntoma escondida: funciona en la máquina del autor |
| **Hashear el nombre** | Renombrar un fichero repetiría la simulación; dos figuras con el mismo dato tendrían dos procedencias |
| **Redondear flotantes antes de hashear** | Dos ejecuciones con números distintos compartirían caché |
| **Sin digest clavado** | Un cambio de forma canónica dejaría toda la caché inalcanzable sin ningún test rojo |
| **Pydantic para el resultado** | Arrays de 86 401 muestras por listas de Python en cada validación, o tipos a medida para evitarlo |
| **Solo `to_dict` con listas** | ~20 MB de JSON por estación y día donde el `.npz` son ~4 MB; y el JSON de Python escribiría `NaN`, que no es JSON |
| **`ground_wind_speed_m_s` con conversión Bufton** | 21.018 ≠ 21.0: el escenario de referencia dejaba de reproducir el enlace de referencia (6.8e-5 relativo) |
| **Derivar los literales de usuario de las constantes SI en tiempo de ejecución** | `30e-9 * 1e9 = 29.999999999999996`; el fichero y el hash dejarían de ser lo que una persona escribe |
| **Importar `system/multi_ogs.py` y `relay.py` para los contenedores de resultado** | Se escriben en la misma etapa; los contenedores se definen aquí como arrays con las formas del contrato y el motor los rellena |

---

## Consecuencias

**Lo que ahora se puede afirmar.** Que cualquier fichero que carga se ejecuta sin
un `DomainError` de conversión; que un resultado lleva la identidad exacta de sus
entradas; que el motor no contiene ninguna conversión de unidades; que los cinco
YAML versionados son iguales a sus constructores y ejecutables sin red.

**Lo que cuesta.** Un `ScenarioError` por cada regla espejo cuando la física cambie
una cota: hay que cambiarla en dos sitios. El precio es bajo porque cada espejo
lleva el nombre de la función cuya regla copia. Y `SCHEMA_VERSION` es una
responsabilidad: cambiar un campo de significado obliga a subirlo y a decirlo.

**Lo que queda fuera.** La radiancia dependiente de la elevación, la fase lunar y
la extinción publicada siguen siendo huecos del ADR 0009; el esquema los expresa
como números que el usuario declara. `TleOrbit` fija el propagador SGP4 pero el
desplazamiento entre la época del TLE y la ventana lo calcula el motor (el módulo
de TLE no acepta otra época, por diseño). El único límite de ida y vuelta conocido
está declarado como test: YAML 1.1 trata U+0085 como salto de línea y PyYAML lo
pliega a un espacio en una **etiqueta** — fuera del hash, y ningún campo de física
lleva texto.

---

## Verificación

`tests/scenario/`, 202 tests, **100 % de cobertura de líneas y de ramas** de los
seis módulos (`models.py` 349 sentencias, `result.py` 372, `io.py` 69,
`defaults.py` 46, `hash.py` 12). Las medidas citadas arriba viven en:

- `test_models.py::TestTheTwoFieldsWithoutADefault`, `::TestAValidScenarioAlwaysConverts`
  (Hypothesis), `::TestUnitsConvertOnceAtTheBoundary::test_the_wind_default_is_the_hv57_value_not_the_bufton_conversion`.
- `test_defaults.py::TestReferenceCastelldefels::test_the_budgets_evaluate_identically_from_either_source`
  (los dos presupuestos a `1e-12` relativo desde el escenario y desde las
  constantes), `::TestNtanos2021`.
- `test_hash.py::TestFloatsHashByRepr`, `::TestThePinnedReferenceDigest`.
- `test_io.py::TestRoundTrip::test_generated_scenarios` (Hypothesis, 40 ejemplos,
  YAML y JSON), `::TestTheMessageListsEveryFailingField`.
- `test_result.py::TestRoundTrip`, `::TestProvenance`.
- `test_scenario_files.py`: los cinco YAML cargan, van y vuelven, y los cuatro con
  constructor son iguales a él; el TLE pasa el checksum de `parse_tle`.

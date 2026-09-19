# QuOSS — Inconsistencias abiertas

> Lo que **está mal hoy** y no se ha arreglado todavía. No es el sitio de lo que
> falta implementar (eso es [`ROADMAP.md`](ROADMAP.md)) ni de lo que se decidió
> (eso son los ADR y [`LAST_CHANGES.md`](LAST_CHANGES.md)): aquí solo entra lo que
> el código o los documentos afirman y no se cumple.
>
> Regla del fichero: una entrada se **borra** cuando se arregla, y su
> justificación se muda a `LAST_CHANGES.md`. Un fichero de deuda que solo crece
> es una lista que nadie lee.

---

## Estado: **cuatro abiertas**

| # | Qué es | Medida, y por qué sigue abierta |
|---|---|---|
| 15 | **`io/export.py` no sabe escribir un `HorizontalResult`, y el README dice que escribe «el resultado».** Desde el [ADR 0024](../docs/adr/0024-the-horizontal-scenario.md) hay dos resultados, y `export_result` está tipado sobre `ExportableResult`, un protocolo que pide `to_manifest_and_arrays`. Un resultado horizontal no lo tiene | **Medido:** `export_result(run(load_scenario("scenarios/ge1_1km.yaml")), …)` levanta `AttributeError: 'HorizontalResult' object has no attribute 'to_manifest_and_arrays'`. No es un fallo silencioso —revienta en la primera línea y con el nombre del método— pero es un `AttributeError` donde debería haber un `ConfigurationError` o, mejor, un exportador. **Sigue abierta porque cerrarla es la etapa 7**, donde `quoss run scenarios/ge1_1km.yaml --out out/` la necesita: exportar un resultado sin arrays no es «lo mismo con menos ficheros» (no hay `arrays.npz`, no hay `passes.csv`, no hay `daily.csv`), y decidir qué escribe es una decisión de esa etapa, no de esta. Mientras tanto un resultado horizontal se serializa con `to_dict()`, que es completo: no tiene arrays, así que el JSON **es** su formato de archivo |
| 16 | **Una sesión afirmó «verificado en `main` y en las trece ramas» contra un `main` de hacía 29 commits.** El 2026-09-19, al arrancar la etapa 7, esta sesión concluyó que `HorizontalResult`, el tag `link`, `scenarios/ge1_1km.yaml`, los ADRs 0024 y 0025 y el §40 de `LAST_CHANGES.md` **no existían**, y lo dijo con una tabla de siete filas de evidencia. Las siete filas eran ciertas sobre el árbol que tenía delante y falsas sobre el proyecto: los siete artefactos llevaban mergeados en `origin/main` desde `2596618` (PR #16) | **Medido:** `git log --oneline -3` antes de `git fetch` daba `fd3b3fd`; después daba `2596618`, con `cb3c0c1 Make the horizontal path a scenario` en medio. **29 commits de diferencia**, y `git fetch --prune` borró además once refs remotos que ya no existían. El `grep` que devolvió «cero ocurrencias de `HorizontalResult`» es el mismo `grep` que ahora devuelve 94. **Por qué entra en este fichero:** es el modo de fallo que el proyecto persigue en los números —un resultado plausible, defendido con evidencia, y equivocado— aplicado por una vez a la verificación en lugar de a la física, y el coste de una verificación equivocada es mayor que el de un número equivocado porque la verificación es lo que se supone que caza a los números. **Sigue abierta porque no se puede asertar:** la suite corre sobre el árbol que tiene, así que no hay test que distinga un árbol fresco de uno rancio. La única defensa es la norma, y una norma que solo se recuerda es lo que la N.4 de esta misma ronda declara insuficiente. Escrita en `CLAUDE.md`: **`git fetch origin --prune` antes de afirmar que algo no existe** |
| 17 | **Once de las catorce citas a `notes/GUIA_REIMPLEMENTACION.md` apuntan a un apartado que ese fichero no tiene, y una apunta al equivocado.** El recorte del 2026-09-19 (§41) renumeró el documento —el v3 tenía §0–§5, el recortado §1–§3— sin tocar a quien lo citaba | **Medido:** 14 citas con número de apartado en `src/`, `docs/` y `tests/`. Cinco a **§5**, tres a **§2.2**, dos a **§0**, una a **§4**: **once que no resuelven**, porque esos apartados solo existen hoy en `archive/GUIA_REIMPLEMENTACION-v3.md`. Y las tres a §1 son peores que no resolver: `src/quoss/viz/__init__.py:6` cita «§1» para *una fórmula, un sitio*, y el §1 de hoy es **«qué era SimulCTTC»** — una cita que **resuelve en silencio al apartado equivocado**, que es la misma familia que un número plausible y falso. **Sigue abierta** porque arreglarla es tocar once docstrings de `.py` y la PR que lo destapó no toca `.py`. El arreglo es mecánico: cada cita pasa a `archive/GUIA_REIMPLEMENTACION-v3.md §N`, o al ADR que hoy posea esa decisión (0026 para §4, 0027 para §3) |
| 18 | **El wheel no lleva `data/`, y `data/` se resuelve relativo al checkout.** `[project.scripts]` promete un `quoss` instalable desde la etapa 0; una instalación no encontraría las estaciones ni los snapshots | **Medido:** `uv build` produce `quoss-0.1.0-py3-none-any.whl` de **644 KB y 85 ficheros**, y los 85 son `quoss/**/*.py`: ni `data/ogs.yaml` ni `data/snapshots/`. Hoy no se nota porque nadie ejecuta desde una instalación —el `quoss` del `[project.scripts]` apunta a `quoss.cli.main:main`, que **tampoco existe**, así que el comando instalado revienta antes de llegar a los datos. **Sigue abierta** porque cerrarla es declarar datos de paquete y escribir el test que lo compruebe **desde una instalación y no desde el árbol**, que es empaquetado, no notas. Escrita también en el [ADR 0027](../docs/adr/0027-four-levels-of-distribution.md), «Lo que esto mide» |

> Cinco entradas nuevas (7-11) se abrieron y cerraron el **2026-09-14**, al escribir
> el puente de extremo a extremo que el motor decía tener. Se listan abajo en vez de
> borrarse porque las cinco eran **afirmaciones escritas que no se cumplían**, que es
> exactamente lo que este fichero registra, y porque cuatro de ellas llevaban meses
> en el árbol sin que la suite pudiera verlas.

La auditoría del **2026-08-04** dejó seis inconsistencias más una consideración
(C1, «219 km es un número sin test»). **Las siete están cerradas** el mismo día;
la justificación de cada arreglo está en
[`LAST_CHANGES.md`](LAST_CHANGES.md) §14, y el resumen es:

| # | Qué era | Cómo se cerró |
|---|---|---|
| 1 | `Frame` aceptaba una cadena y la guardaba cruda | `frames.resolve_frame`, llamado por `ClassicalElements` y `Trajectory` antes de juzgar el marco. Los dos mensajes siguen siendo dos |
| 2 | «Immutable» era falso en los tres contenedores | `core.types.frozen_copy` / `frozen_view`; copia en `TimeGrid` y `ClassicalElements`, congelado sin copia en `Trajectory` |
| 3 | `relabelled_as` compartía buffer con el original | consecuencia de la 2, cerrada con ella y con un test de `shares_memory` |
| 4 | `MEAN_BROUWER` afirmaba fijar unas constantes que no fija | el docstring y el ADR 0006 dicen ahora que la etiqueta nombra la **teoría**, y que la coherencia con las constantes no se comprueba porque no se puede |
| 5 | El ADR 0004 quedó fuera y contradecía al 0006 | dos filas nuevas en su tabla, el punto de contexto 4 actualizado, y el bullet del acoplamiento con `tle.py` corregido |
| 6 | Dos huecos de documentación menores | el `Raises` de `propagate` nombra los elementos medios; el ejemplo de `CLAUDE.md` dice que hoy eso levanta `DomainError` |
| C1 | 219 km citados en 15 sitios sin un test que los reproduzca | `TestWhatNotHavingBrouwerLyddaneCosts`, 8 tests. **Los números eran falsos**: la cifra real es 5.9 veces mayor, y además no existe una cifra única |

Verificación tras los arreglos: `ruff`, `ruff format`, `mypy`, **625 tests**
(eran 586), 99 % de cobertura global y 100 % en los cuatro módulos de `orbits/` y
en `_validation.py` — los mismos porcentajes que antes.

---

## Las que se cerraron el 2026-09-14

| # | Qué era | Cómo se cerró |
|---|---|---|
| 7 | `src/quoss/engine/__init__.py` y `engine/pipeline.py` afirmaban que `tests/e2e/test_reference_scenarios.py` probaba **bit a bit** que el motor no añade ni pierde nada. **El fichero no existía** | Escrito: 30 tests, igualdad **exacta** de coma flotante, etapa por etapa, con las tres opcionales dentro. `LAST_CHANGES.md` §32 y el [ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md) |
| 8 | La cabecera de `scenarios/reference_castelldefels.yaml` decía que el fichero «convierte en **exactamente** las entradas de física de `tests/system/reference.py`», y no es verdad: difieren en `station_height_m`, que son **457 bits** | Las dos cabeceras dicen ahora en qué difieren y cuánto vale; `tests/system/reference.py` lo dice en `STATION_ALTITUDE_KM` |
| 9 | El docstring de `reference_castelldefels()` decía que `TestReferenceCastelldefels` «aserta que la conversión reproduce **todas** las entradas de física» — cuando ese test ya pasaba `station_height_m=30.0` a mano por el lado cableado | Corregido, y el `30.0` del test lleva el comentario que explica por qué está escrito a mano |
| 10 | `channel/atmosphere.py` documentaba `station_height_m` como «height above ground level» en 16 sitios, mientras `scenario/models.py` le metía la altura sobre el elipsoide. Bajo la lectura literal, una estación de montaña recibe la capa límite entera: el **35.7 %** de la clave de Calar Alto, al revés | Resuelto **con la fuente abierta**, no eligiendo: la frase que sigue a la Ec. (13) de la ITU-R P.1621-2 da el rango de validez como «earth station altitude between 0 km and 5 km **above sea level**». Un rango de 0-5 km es de sitios, no de mástiles. Los 15 parámetros dicen «above mean sea level» y el módulo lleva la cita |
| 11 | `viz/plots.py` citaba `docs/adr/0017-…` y `validation/__init__.py` citaba `docs/adr/0018-…`; ninguno de los dos existe | Las dos citas dicen ahora que el fichero está pendiente, y `notes/ROADMAP.md` **reserva** el 0017 a la etapa 7 y el 0018 a la 8. El 0016 estaba libre y lo ocupa la decisión de la etapa 5 |

---

## Las que se cerraron el 2026-09-15

| # | Qué era | Cómo se cerró |
|---|---|---|
| 12 | El docstring de `tests/e2e/test_reference_scenarios.py` justificaba la igualdad exacta de **todas** sus aserciones con «la misma función con los mismos argumentos devuelve los mismos doubles». Es verdad para ruta contra ruta en un proceso; no lo es para dos literales escritos a mano en una máquina, que fallaron por **9 ULP** en otra | Dos clases de aserción separadas. Los literales van contra una cota derivada (8.15e-13 relativo) y los enteros se quedan exactos con una prueba de margen. CI corre en macOS arm64 y numpy 2.0. `LAST_CHANGES.md` §35 |
| 13 | `combined_fade_db` decía ser «exact» y convergida «below a part in 1e20 of a decibel». Con `γ` grande —apuntado despreciable, el caso de un enlace horizontal— devolvía **1.602 dB** donde la respuesta es **0.101**, y **124.9** donde es **8.23**, por cancelación catastrófica en el exponente de `_emg_cdf` | La identidad `erfcx`, exacta y sin cancelación, y `γ = ∞` como límite. `TestTheJointFadeWhenPointingIsNegligible`. §35 |
| 14 | `equivalent_beam_radius_m` dividía por `exp(-v²)` subdesbordado cuando la lente es más de ~21 radios de haz —un banco normal—: `RuntimeWarning`, o `γ = 7.9e137` sin más queja que el aviso de rango | Radio equivalente `+inf` pasado `v² = 700`, que es el límite de la propia ley, con el aviso diciéndolo. `TestALensFarWiderThanTheBeam`. §35 |

---

## Consideraciones que **no** son defectos, pero conviene tener conscientes

- **Hay dos enlaces de referencia y seguirá habiéndolos.** El de la etapa 3
  (`tests/system/reference.py`) integra la turbulencia desde el nivel del mar; el
  del escenario, desde los 30 m de la estación. Difieren en el **0.106 %** del día
  y las dos cifras están reproducidas a la última cifra por
  `tests/e2e/test_reference_scenarios.py`. **No se unifican hoy** porque re-medir
  la etapa 3 movería unas cincuenta citas en docstrings, ADRs y notas por un 0.1 %
  sin cambiar ninguna conclusión cualitativa — y este proyecto ya sabe lo que
  cuesta una cifra citada en quince sitios (§14.1). Se unificará el día que haya
  otra razón para tocar esas cifras. Lo que **sí** está garantizado es que ninguno
  de los dos sitios afirma ser el otro.
- **La Ec. (11) de Ntanos et al. —el perfil HV modificado con la altitud de la
  estación— no está implementada.** Lo que hay es la Ec. (6) de la ITU-R P.1621-2
  con el integral truncado por abajo en `station_height_m`. Son dos modelos del
  mismo efecto, y el roadmap listaba el primero como fuente de la etapa 2.2. No es
  una inconsistencia porque ningún docstring afirma implementarlo; es un hueco de
  modelo, y se vio al medir lo que vale la altura.
- **Los escenarios de Ntanos et al. no están en el puente bit a bit.**
  `tests/e2e/oracle.py` cablea la apertura de 0.75 m, así que las estaciones de
  1.3 m y 2.3 m necesitarían un segundo parámetro en el oráculo. Cargan y corren
  (`tests/scenario/test_scenario_files.py`); lo que falta es la comparación exacta.
- **`secular_rates_j2` ya no es alcanzable desde ningún flujo real.** Con el gate
  puesto, todos sus llamantes son tests o código que etiqueta a mano. Es lo
  esperado y es correcto; y cuando llegue `constellations.py`, el diseño SSO
  tendrá que declarar `MEAN_BROUWER` — que también es correcto, porque las
  fórmulas de sincronismo solar son de elementos medios. Solo hay que no
  descubrirlo como sorpresa.
- **Con `j2 = 0` la distinción medio/osculador no existe** (el campo es de dos
  cuerpos y las dos elipses coinciden), y el gate sigue aplicando. Meter una
  excepción en la guarda sería peor que la arruga: una guarda con un caso
  especial es una guarda que hay que leer dos veces. El test
  `test_with_j2_off_both_paths_are_the_same_two_body_problem` usa exactamente ese
  caso como control del instrumento, y necesita `relabelled_as` para llegar a él.
- **`TimeSeries` no copia ni congela sus `values`, y eso es deliberado.** Es el
  cuarto contenedor y el único que no afirma inmutabilidad, así que no había
  inconsistencia que cerrar; y sus valores pueden ser una pila Monte Carlo `(n, m)`
  donde copiar sí costaría. Si algún día su docstring promete lo que prometen los
  otros tres, `frozen_view` es lo que tiene que llamar.
- **El predictor `3π·δa` usa el promedio temporal del semieje osculador como
  sustituto del semieje medio de Brouwer**, que no es lo mismo: difieren en O(J2)
  relativo. Por eso la tolerancia del test es del 5 % y no del 0.1 %. Cuando entre
  Brouwer-Lyddane, ese test puede apretarse y pasa a ser V3 de verdad.
- **El árbol no está probado en Python 3.11 ni 3.12.** El desarrollo va sobre
  3.13 y la matriz de CI cubre las tres. `ruff` con `target-version = "py311"`
  cubre la sintaxis, no el comportamiento.
- **Tres statements de `core/types.py` siguen sin cubrir** (`is_uniform` con menos
  de tres muestras, y `__repr__` de `TimeGrid`). Preexistentes, verificado
  comparando la cobertura antes y después de estos arreglos: 97 % en ese fichero
  en los dos casos.

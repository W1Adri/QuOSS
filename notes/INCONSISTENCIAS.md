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

## Estado: **ninguna abierta**

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

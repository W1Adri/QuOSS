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

## Consideraciones que **no** son defectos, pero conviene tener conscientes

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

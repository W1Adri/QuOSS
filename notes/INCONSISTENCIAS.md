# QuOSS — Inconsistencias abiertas

> Lo que **está mal hoy** y no se ha arreglado todavía. No es el sitio de lo que
> falta implementar (eso es [`ROADMAP.md`](ROADMAP.md)) ni de lo que se decidió
> (eso son los ADR y [`LAST_CHANGES.md`](LAST_CHANGES.md)): aquí solo entra lo que
> el código o los documentos afirman y no se cumple.
>
> Auditoría del **2026-08-04**, sobre el estado tras la bandera osculador/medio
> ([ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md)). Suite verde en
> ese momento: `ruff`, `ruff format`, `mypy`, **586 tests**, 99 % de cobertura
> global y 100 % en los cuatro módulos de `orbits/`. Es decir: **nada de lo de
> abajo lo detecta la suite**, y por eso está escrito.
>
> Regla del fichero: una entrada se **borra** cuando se arregla, y su
> justificación se muda a `LAST_CHANGES.md`. Un fichero de deuda que solo crece
> es una lista que nadie lee.

| # | Qué | Severidad | Origen |
|---|---|---|---|
| 1 | `Frame` acepta una cadena y la guarda cruda | media (latente) | preexistente |
| 2 | «Immutable» es falso en los tres contenedores | media | preexistente |
| 3 | `relabelled_as` comparte buffer con el original | baja | consecuencia de 2 |
| 4 | `MEAN_BROUWER` afirma fijar constantes que no fija | baja | ADR 0006 |
| 5 | El ADR 0004 quedó fuera y contradice al 0006 | baja (documental) | ADR 0006 |
| 6 | Dos huecos de documentación menores | trivial | ADR 0006 |
| C1 | 219 km citados en 15 sitios, sin un test que los reproduzca | **alta por norma** | preexistente, ahora en un mensaje de error |

---

## 1. `Frame` acepta una cadena y la guarda cruda

**Qué pasa.** `ClassicalElements.__init__` valida el marco con
`if frame not in (Frame.TEME, Frame.GCRF)`. `Frame` es un `StrEnum`, así que
`"teme" == Frame.TEME` es `True` y la comprobación pasa — pero lo que se
almacena es el `str`, no el miembro.

```python
coe = ClassicalElements(..., frame="teme")
coe.frame                    # 'teme'  (str)
coe.frame is Frame.TEME      # False
propagate(coe, grid, method=...).frame is Frame.TEME   # False
```

**Por qué importa.** El `repr` se ve idéntico (`frame=teme`), ningún test lo
toca porque todos pasan miembros, y el `str` viaja intacto hasta el
`Trajectory`. El día que `geometry.py` escriba `if traj.frame is Frame.TEME:`
—la forma idiomática, y la que ya usan los tests de `frames.py`— tomará la rama
equivocada **sin error**. Es el modo de fallo que el [ADR 0002](../docs/adr/0002-frames-and-time-scales.md)
dice que el enum existe para cerrar: «un tag para que una posición TEME no pueda
consumirse en silencio como GCRF».

Hay además una asimetría nueva dentro de la misma clase: `element_type` **sí**
resuelve la cadena a miembro (`_validated_element_type`), `frame` no. Dos tags,
dos disciplinas.

**Arreglo.** Un `_validated_frame` espejo del de `element_type`: resuelve
`Frame(value)`, levanta `DomainError` con los válidos si no, y **después**
rechaza los que rotan. ~15 líneas y dos tests (que la cadena se resuelve a
miembro; que `traj.frame is Frame.TEME` tras construir con `"teme"`).

**Ojo al arreglarlo:** el mensaje de rechazo de ITRF/ENU tiene que seguir siendo
el que es —«unos elementos en un marco que rota no son unos elementos»— y no
degradarse a «no es un marco válido», que dice menos. Son dos fallos distintos y
merecen dos mensajes.

---

## 2. «Immutable» es falso en los tres contenedores

**Qué pasa.** `ClassicalElements`, `TimeGrid` y `Trajectory` documentan
«Immutable and validated at construction, so a function receiving one may assume
… without re-checking». Lo inmutable es el *binding* del atributo, no el
contenido de los arrays:

```python
g = TimeGrid(epoch_jd=2460676.5, t_s=np.array([0.0, 60.0]))
g.t_s[0] = 99.0          # [99., 60.] — y g.n sigue diciendo 2
traj.r_km[0, 0, 0] = 0.0 # el dataclass es frozen; el array no
coe.semi_latus_rectum_km[0] = 1.0
```

**Por qué importa, y el caso peor.** `TimeGrid(t_s=[99, 60])` se **rechaza** en
construcción por no ser estrictamente creciente. Se puede llegar a ese estado
mutando después, y entonces `duration_s` e `is_uniform` devuelven números sin
sentido sin que nada falle — con el agravante de que el docstring da permiso
explícito a los consumidores para no re-comprobar. Es una invariante que el
proyecto declara y no sostiene.

**Segundo filo: aliasing.** `as_1d` devuelve el *mismo objeto* si ya es `float64`
1-D, así que `ClassicalElements` aliasea el array del llamante. Si el llamante lo
modifica más tarde, los elementos cambian por debajo.

**Arreglo.** Copiar-y-congelar al almacenar:

```python
arr = np.array(arr, dtype=np.float64)   # rompe el aliasing
arr.flags.writeable = False             # rompe la mutación
```

Coste a medir antes de aplicarlo a ciegas: en `Trajectory` los arrays los crea el
propio módulo, así que ahí basta con **congelar sin copiar** (una copia de
`(S, n, 3)` para un millón de muestras son ~24 MB por array y no hace falta).
En `ClassicalElements` y `TimeGrid` la copia sí es necesaria, y es de tamaño
`n` — irrelevante.

**Ojo:** hay que comprobar que ningún consumidor escribe en esos arrays. Hoy no
lo hace ninguno (todo devuelve arrays nuevos), pero `np.broadcast_to` ya produce
vistas de solo lectura, así que el patrón ya está a medias en el código y
conviene que quede uniforme y no a medias.

---

## 3. `relabelled_as` comparte buffer con el original

Consecuencia directa de la 2:

```python
b = a.relabelled_as(ElementType.MEAN_BROUWER)
np.shares_memory(a.semi_latus_rectum_km, b.semi_latus_rectum_km)   # True
a.semi_latus_rectum_km[0] = 1.0   # y b también cambia
```

`raan`, `argp` y `nu` **no** comparten, porque `_wrap_two_pi` crea arrays nuevos:
así que el objeto reetiquetado está medio aliaseado y medio no, lo cual es peor
que cualquiera de las dos cosas de forma consistente.

Hoy es inocuo —nadie muta nada— y el test
`test_relabelling_moves_the_label_and_nothing_else` seguiría pasando aunque esto
fuera un problema, porque compara valores, no identidad de memoria. Se cierra
solo al arreglar la 2.

---

## 4. `MEAN_BROUWER` afirma fijar unas constantes que no fija

**Qué pasa.** El docstring de `ElementType.MEAN_BROUWER` dice «Brouwer-Lyddane
mean elements **referred to the EGM96 constants**», y el ADR 0006 repite el par
«Brouwer-Lyddane/EGM96 frente a Brouwer-Kozai/WGS-72». Pero existe, y pasa, este
test:

```python
# tests/orbits/test_perturbations.py::test_wgs72_gives_a_slightly_different_answer_than_egm96
secular_rates_j2(_mean_elements(), mu_km3_s2=WGS72..., r_equatorial_km=WGS72..., j2=WGS72_J2)
```

es decir, elementos etiquetados «referidos a EGM96» evaluados con constantes
WGS-72. O el test es ilegal, o el docstring afirma de más.

**Cuál de los dos.** El docstring. Por la regla del
[ADR 0004](../docs/adr/0004-zonal-perturbations.md), las constantes viajan con el
**modelo** (`ZonalGravity`, o los argumentos de la función), no con los
elementos; y ese test es legítimo, porque mide justo la diferencia entre dos
juegos de constantes sobre la misma órbita.

**El matiz que no hay que perder al corregirlo.** Unos elementos medios *sí*
dependen de con qué constantes se promediaron —el semieje medio de Brouwer
depende del J2 y del radio usados—, así que la etiqueta no es del todo ajena a
ellas. La afirmación honesta es: **la etiqueta nombra la teoría** (Brouwer-Lyddane
frente a Brouwer+Kozai, que cambian el significado del semieje medio), las
constantes son responsabilidad del llamante, y **la coherencia entre las dos no
se comprueba porque no se puede**. Eso sigue justificando la subdecisión 2
—`MEAN` a secas seguiría siendo falso— pero por la teoría, no por las
constantes.

**Arreglo.** Dos frases en el docstring de `ElementType` y una en el ADR 0006.

---

## 5. El ADR 0004 quedó fuera, y ahora dos ADRs se contradicen

Al implementar la bandera se actualizaron los ADR 0003 y 0005, pero **el ADR que
documenta `secular_rates_j2` es el 0004** y sigue sin decir que su firma ahora
rechaza osculadores: su tabla de decisiones está intacta y su punto de contexto 4
(«Una tasa secular es una afirmación sobre elementos medios. `rv_to_coe` devuelve
osculadores. La diferencia es O(J2)») se lee como si eso siguiera siendo un coste
tolerado.

Y hay una contradicción explícita: el «Lo que no cierra» del ADR 0004 afirma que
Brouwer-Lyddane es «la misma que `tle.py` necesitará para no confundir los
elementos medios de un TLE con los osculadores de `kepler.py`». `LAST_CHANGES.md`
§13 corrigió eso por escrito («está sobredimensionado»: SGP4 devuelve estado, así
que el camino TLE → posición no pasa por ninguna pieza nuestra de BL) y el ADR
0006 repite la versión corregida. Dos documentos vivos del repo dicen cosas
distintas sobre la misma pieza.

**Arreglo.** Una fila en la tabla del ADR 0004 (`Tipo de elemento | exige
MEAN_BROUWER, ver ADR 0006`), y corregir ese bullet apuntando al análisis del
acoplamiento.

---

## 6. Dos huecos de documentación menores

- El `Raises` de `propagate` no menciona los elementos medios. El párrafo de
  `elements` sí lo explica, pero quien lee la lista de excepciones no se entera.
- `CLAUDE.md` usa como ejemplo de «explicación mala»: «`secular_rates_j2` espera
  elementos medios. Pasarle osculadores introduce un error O(J2)». Como ejemplo
  de **estilo** sigue valiendo —es lo que la norma 1 quiere ilustrar— pero
  describe algo que ya no puede ocurrir, y la versión «Bien» de al lado tampoco
  dice que hoy eso levanta `DomainError`.

---

## C1. Consideración: 219 km es un número sin test

**Qué pasa.** Las cifras **14.6 km por vuelta** y **219 km al día** aparecen en
15 sitios: el docstring de módulo de `kepler.py`, el de `propagator.py`, el ADR
0005, el ADR 0006, la bitácora — y, lo que las vuelve críticas, **el texto de un
`DomainError` que un usuario va a leer** (`coe_to_rv`). Ningún test las
reproduce: salieron de una medición ad-hoc hecha al escribir `propagator.py` y
registrada solo en prosa.

**Por qué importa.** Choca con la norma 1 de `CLAUDE.md` («un ejemplo con
números, preferiblemente medido en este repo, no citado de memoria») y con la
razón de ser del protocolo V1–V4: es una afirmación cuantitativa **sin oráculo**.
Si mañana cambia una constante, un default del integrador o el preset de
gravedad, el mensaje de error seguirá diciendo 219 km y nadie se enterará. Es
además el único número del proyecto que se le muestra al usuario en una
excepción.

**Se puede cerrar con lo que ya existe** — no hace falta Brouwer-Lyddane. El
propagador analítico que la medición usó son cuatro líneas dentro del test:

1. `secular_rates_j2` sobre los elementos etiquetados `MEAN_BROUWER`;
2. `advance_mean_anomaly` con `dM/dt`, y `Ω`, `ω` avanzados con sus tasas;
3. reconstruir `ClassicalElements` y `relabelled_as(OSCULATING)` para poder
   llamar a `coe_to_rv`;
4. comparar contra `propagate_zonal` con **J2 solo en los dos lados**, para que
   la diferencia sea el desajuste y no física distinta.

Con el control del instrumento que ya está medido: con `j2 = 0` en los dos lados
el residuo cae a **0.09 mm** sobre 15 vueltas, lo que demuestra que los 219 km
son física y no error de la comparación. Y con la descomposición
radial / along-track / cross-track, que es donde está el argumento de verdad: el
radial y el cross-track se quedan quietos (~10 km y ~1–4 km, oscilan) y el
along-track **crece linealmente**, que es lo que convierte 219 km en ≈30 s de
reloj orbital al día.

Es, además, el uso más elocuente posible de la bandera: **las dos direcciones de
`relabelled_as` en el mismo test, para medir exactamente lo que cuesta no tener
la conversión.** Coste estimado: ~40 líneas y un par de segundos de suite (marcar
`slow` el caso de un día).

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
  especial es una guarda que hay que leer dos veces.
- **El árbol no está probado en Python 3.11 ni 3.12.** El desarrollo va sobre
  3.13 y la matriz de CI cubre las tres. `ruff` con `target-version = "py311"`
  cubre la sintaxis, no el comportamiento.

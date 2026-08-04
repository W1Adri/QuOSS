# ADR 0006 — La bandera osculador/medio dentro de `ClassicalElements`

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Etapa:** 2.1 (`orbits/kepler.py`, `orbits/perturbations.py`, `orbits/propagator.py`)
- **Afecta a:** `tle.py`, `constellations.py`, `geometry.py`, el modo analítico de
  `propagator.py` cuando entre, y el esquema de escenario de la etapa 4.
- **Extiende** al [ADR 0003](0003-orbital-elements.md), que fijó qué son los seis
  elementos pero no *de qué órbita* son.

---

## Contexto

### Qué son un elemento osculador y uno medio, desde cero

Un satélite real no recorre una elipse. La Tierra está achatada —el ecuador
sobresale unos 21 km respecto a los polos— y ese exceso de masa tira del satélite
fuera de la elipse en todo momento. Así que la frase «la órbita del satélite» no
tiene un único significado. Hay dos, y son dos elipses distintas:

- **Elementos osculadores** (del latín *osculari*, besar): la elipse que el
  satélite seguiría *a partir de este instante* si la Tierra se convirtiera de
  golpe en una esfera perfecta. Es tangente —«besa»— a la trayectoria real en ese
  punto, y cambia continuamente. Es lo que devuelve `rv_to_coe`, porque un vector
  de estado (posición + velocidad en un instante) no puede determinar otra cosa.
- **Elementos medios**: la misma órbita con el bamboleo rápido ya restado. Es una
  elipse que no existe en ningún instante concreto —ningún vector de estado la
  toca— pero que resume el promedio. Es de lo que habla una **tasa secular**
  («secular» aquí no tiene nada que ver con religión: en mecánica celeste
  significa *que crece sin parar*, frente a lo que oscila y se cancela).

La diferencia entre las dos es del orden de J2 ≈ 1.08e-3, es decir **una parte en
mil**. Sobre 7000 km eso son ~7 km, y no es una constante: la parte que importa
crece.

### Por qué eso es un problema y no un detalle

Medido en este repo, contra `propagate_zonal` con J2 solo en los dos lados (así
que la diferencia es *solo* el desajuste, no física distinta):

| Órbita | 1 vuelta | 15 vueltas (~1 día) | radial | cross-track |
|---|---|---|---|---|
| SSO 700 km, i = 98.2° | 14.6 km | **219 km** | 11.7 km | 1.0 km |
| ISS-like, i = 51.6° | 9.9 km | **144 km** | 5.3 km | 4.0 km |
| LEO polar, i = 90° | 14.9 km | **224 km** | 12.3 km | 0.0 km |

Control del instrumento: con `j2 = 0` en los dos lados el residuo cae a **0.09 mm**
sobre 15 vueltas, así que los 219 km son física y no un fallo de la comparación.

**Lo que hay que leer en la tabla no es el tamaño, es que crece.** El error radial
y el cross-track se quedan quietos: son el bamboleo de período corto, que oscila y
no acumula. El along-track crece linealmente, ~14.6 km por vuelta, porque un error
O(J2) en el semieje `a` es un error O(J2) en el movimiento medio (`n ∝ a^{-3/2}`),
y una velocidad angular equivocada integra. En unidades útiles: **≈2 s de error de
reloj orbital por vuelta, ≈30 s al día**. Un pase dura ~10 minutos, así que a la
semana las ventanas de visibilidad están corridas varios minutos.

Y el modo de fallo es el característico del proyecto: **no da un error, da un
número plausible**. Los arrays tienen la forma correcta, las magnitudes son
razonables y ninguna aserción de tipo o de forma se entera.

### Por qué ahora

La decisión de fondo —bandera dentro de `ClassicalElements`, como el `Frame` del
ADR 0003— estaba tomada y anotada en `notes/LAST_CHANGES.md` §12, con **tres
subdecisiones abiertas** que había que resolver *antes* de escribir la bandera.
Este ADR las resuelve y la implementa. Lo que no entra sigue sin entrar: la
transformación de Brouwer-Lyddane no existe, y este ADR no la finge.

## Decisión

**`ClassicalElements` lleva un `ElementType` con dos miembros, `OSCULATING` y
`MEAN_BROUWER`. `rv_to_coe` marca osculador; `coe_to_rv` exige osculador y
`secular_rates_j2` exige medio, los dos con `DomainError`. No hay conversión
entre los dos tipos, y la única forma de cambiar la etiqueta es
`relabelled_as`, que no convierte nada y lo dice.**

| Cuestión | Elección |
| -------- | -------- |
| Dónde vive la etiqueta | dentro de `ClassicalElements`, como `Frame` |
| Valor por defecto | `OSCULATING` — lo único que el proyecto sabe producir |
| Miembros del enum | exactamente dos: `OSCULATING`, `MEAN_BROUWER` |
| `coe_to_rv` con medios | `DomainError` (subdecisión 1) |
| `secular_rates_j2` con osculadores | `DomainError` |
| Conversión medio↔osculador | **no existe**; entra con Brouwer-Lyddane |
| Reetiquetar sin convertir | `ClassicalElements.relabelled_as` (subdecisión 3) |
| `assume_mean=True` en la física | rechazado |

## Justificación

### Por qué una bandera y no documentación

Es la misma jugada que el `Frame` del ADR 0003, un nivel más adentro: unos
elementos referidos a un marco que rota no son unos elementos, y unos elementos
medios usados como osculadores no son la órbita que dicen ser. Hasta hoy el aviso
estaba escrito en tres documentos y en dos docstrings. Un aviso escrito solo
protege al lector que ya sabía que tenía que buscarlo — y aquí el resultado
equivocado no se distingue del correcto mirando la salida.

### Subdecisión 1 — `coe_to_rv` rechaza los elementos medios

La guarda intuitiva es la otra: `secular_rates_j2` es la función cuya teoría
necesita elementos medios, así que parece el sitio natural del control. Pero
**los kilómetros se pierden en el otro lado**:

- Alimentar la teoría secular con osculadores cuesta O(J2) *relativo sobre la
  tasa*: el residuo es del tamaño del término que la teoría de primer orden ya
  descarta. Es un error, y ahora se rechaza, pero es del tamaño de la propia
  incertidumbre del modelo.
- Convertir un juego medio a estado como si fuera osculador es la tabla de arriba:
  219 km al día, y creciendo.

Si la bandera se comprobara en un solo sentido, el agujero grande quedaría
abierto. Así que se cierran los dos, y el que se documenta más largo es este.

Coste para los llamantes actuales: **ninguno**. Quien hace `rv_to_coe → coe_to_rv`
sigue teniendo osculadores en las dos puntas. Quien algún día propague
analíticamente gana un paso explícito, que es justo el paso que hoy se olvidaría
en silencio.

Consecuencia en `propagator.py`, que no es evidente: `TWO_BODY` no le pasa a
`coe_to_rv` los elementos del llamante, sino una pila aplanada de `S · n` juegos
construida dentro. Esa pila **reenvía la etiqueta** en vez de dejarla caer al
defecto; si no lo hiciera, el modo de dos cuerpos blanquearía elementos medios
pasándolos por delante de la única guarda que hay, y ninguna aserción de forma se
enteraría. Hay un test parametrizado sobre `PropagationMethod` que lo fija.

### Subdecisión 2 — dos miembros, y por qué el segundo se llama `MEAN_BROUWER`

«Medio» no es una cosa: es una por teoría. Los elementos medios de un TLE son de
Brouwer con la modificación de Kozai y referidos a las constantes de WGS-72; los
que necesita `secular_rates_j2` son de Brouwer-Lyddane con EGM96. **No son
intercambiables**, y una bandera de dos valores cuyo segundo valor se llamara
`MEAN` los haría parecerlo — exactamente el error que la bandera existe para
prevenir.

El miedo legítimo a quedarse en dos valores era: «añadir un tercero después toca a
todos los llamantes». Ese miedo **desaparece al nombrar el miembro por su
teoría**. Ningún llamante puede escribir `MEAN`, así que el día que algo produzca
elementos medios de SGP4 se añade `MEAN_KOZAI_SGP4` y no hay un solo sitio que
tenga que decidir cuál de los dos quería decir.

Y no se añade hoy porque el [ADR 0005](0005-propagation.md) ya decidió que
`tle.py` **no construye un `ClassicalElements`**: un TLE se propaga con SGP4, que
devuelve estado en TEME, y los elementos de ese estado son osculadores. Un miembro
que ningún código puede producir es una etiqueta que solo invita a ponerla a mano
— la misma regla con la que el ADR 0005 envió `PropagationMethod` con dos miembros
en vez de tres. Un nombre ausente obliga a preguntar; uno presente y sin dueño, no.

Hay un test que fija el conjunto exacto de miembros y que además aserta que **no
existe** un `MEAN` a secas, para que la ausencia sea una decisión y no un olvido.

### Subdecisión 3 — `relabelled_as`, y por qué no `assume_mean=True`

`TestSecularRatesAgainstIntegration` alimenta osculadores a `secular_rates_j2`
**queriendo**. No es descuido: es el experimento. Un juego de seis números tiene
que hacer dos papeles ahí — condición inicial de la integración (osculador, porque
un estado no puede ser otra cosa) y argumento de la teoría (medio) — y de esa
tensión sale la medición que sostiene el módulo entero: el residuo del primer
orden es **exactamente proporcional a J2** (el cociente residuo/J2 se mantiene
constante a cuatro cifras al escalar J2 por 1, ½, ¼ y ⅛). Eso es lo que separa
«la teoría está truncada» de «un coeficiente está mal escrito», y una cota sola no
lo separa.

Con la bandera, esos tests necesitan una vía explícita. Las dos candidatas:

|  | `assume_mean=True` en `secular_rates_j2` | **`relabelled_as` en el contenedor (elegida)** |
| --- | --- | --- |
| Dónde vive | en la API de física | en el objeto de datos |
| Quién puede alcanzarlo | cualquiera, incluido un YAML de escenario | quien tiene los elementos en la mano y escribe la palabra |
| Tiene valor por defecto | sí, forzosamente | no aplica |
| Qué dice el nombre | «supón» — invita a suponer | «reetiquetado» — admite que no convierte |
| Qué es en realidad | la degradación silenciosa que el README prohíbe, con otro nombre | una mentira visible en el punto de llamada |

`relabelled_as` devuelve un objeto nuevo con **los mismos números bit a bit** y
otra etiqueta, y hay un test que lo aserta campo por campo. Si algún día creciera
una conversión de verdad detrás de ese nombre, ese test falla — y debe fallar: una
conversión escondida tras la palabra «reetiquetar» sería peor que la confusión
original.

Los tests que solo preguntan por lo que la fórmula cerrada calcula —un signo, un
límite, una simetría, el caso crítico— **no** reetiquetan: construyen elementos
medios directamente (`element_type=MEAN_BROUWER`), porque eso es lo que dicen ser
y nada allí los convierte en un estado. La distinción entre las dos ayudas de test
(`_mean_elements` frente a `.relabelled_as(...)`) es la que separa «estos son
medios» de «estos no lo son y lo sé».

### Por qué el defecto es `OSCULATING`

Porque es lo único que el proyecto sabe producir hoy, y porque es la etiqueta que
las dos funciones existentes aceptan y que la tercera rechaza — es decir, el
defecto no puede colar nada por ninguna de las dos guardas. Un defecto `MEAN`
habría hecho que todo escenario escrito a mano fuera rechazado por `coe_to_rv`, y
un defecto obligatorio (sin default) habría cambiado cada línea de construcción
del proyecto para proteger un caso que aún no puede darse.

## Consecuencias

### Lo que esto cierra

- El desajuste medio↔osculador deja de ser un aviso en prosa y pasa a ser una
  excepción, en las **dos** direcciones.
- El modo analítico de `propagator.py` tiene ya el tipo que va a exigir: cuando
  entre `J2_SECULAR_ANALYTIC`, la bandera es lo que impide alimentarlo mal.
- `tle.py` hereda la disciplina con un mecanismo detrás: no construir un
  `ClassicalElements` con elementos medios de un TLE ya no es solo una nota.

### Lo que no cierra

- **La transformación de Brouwer-Lyddane.** Sigue sin existir, y con ella siguen
  bloqueados el modo analítico de J2 y los términos seculares de segundo orden del
  [ADR 0004](0004-zonal-perturbations.md). Pendiente de elegir alcance (solo
  período corto, o corto + largo) y oráculo de validación. Hoy la bandera es una
  **puerta cerrada, no un paso**: marca dónde haría falta la conversión.
- **`MEAN_KOZAI_SGP4`.** Entra el día que algo lo produzca, y con las constantes
  WGS-72 que le corresponden.
- **El esquema de escenario (etapa 4).** El campo aceptará la cadena
  (`ElementType` es `StrEnum` y se resuelve desde texto), pero cómo se escribe en
  el YAML y qué valida Pydantic es decisión de esa etapa.

## Alternativas descartadas

**Dejarlo documentado, como estaba.** Es lo que había: dos docstrings y tres notas
avisando. Falla porque el error no se ve en la salida, así que el aviso solo sirve
al lector que ya sospechaba.

**Un tipo distinto para cada clase de elementos** (`MeanElements` aparte de
`ClassicalElements`). Es la versión más fuerte y la que un lenguaje con tipos
suma-verdaderos haría. Se descarta por duplicación: las seis propiedades, la
validación, el pliegue de ángulos degenerados y la vectorización son idénticos, y
lo único que cambia es qué función te acepta. Una etiqueta dentro cuesta un campo;
un segundo tipo cuesta una segunda clase que mantener sincronizada, y el ADR 0003
ya rechazó mantener dos representaciones por el mismo motivo (elementos
equinocciales).

**Un `MEAN` genérico ahora y refinarlo luego.** Ver subdecisión 2: sería afirmar
que los medios de un TLE y los de Brouwer-Lyddane son la misma cosa.

**`assume_mean=True`.** Ver subdecisión 3.

**Guardar solo en `secular_rates_j2`.** Ver subdecisión 1: deja abierto el agujero
de 219 km/día.

## Referencias

- `notes/LAST_CHANGES.md` — el planteamiento previo y las tres subdecisiones
- [ADR 0003](0003-orbital-elements.md) — los seis elementos, y el `Frame` que
  viaja dentro; esta bandera es el mismo mecanismo
- [ADR 0004](0004-zonal-perturbations.md) — la teoría secular de primer orden y
  por qué su segundo orden depende de Brouwer-Lyddane
- [ADR 0005](0005-propagation.md) — el enum incompleto, y por qué `tle.py` no
  construye elementos
- Brouwer, «Solution of the problem of artificial satellite theory without drag»,
  *Astronomical Journal* 64, 378-397, 1959
- Lyddane, «Small eccentricities or inclinations in the Brouwer theory of the
  artificial satellite», *Astronomical Journal* 68, 555-558, 1963
- Kozai, «The motion of a close earth satellite», *Astronomical Journal* 64,
  367-377, 1959

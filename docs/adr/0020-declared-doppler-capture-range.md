# ADR 0020 — Un rango de captura declarado y opcional, y qué dice el resultado cuando no lo hay

- **Estado:** aceptada
- **Fecha:** 2026-09-15
- **Etapa:** 4 (`scenario/`) y 5 (`engine/`).
- **Afecta a:** `scenario/models.py` (`ReceiverSpec`), `engine/pipeline.py`
  (etapa de adquisición).
- **Extiende** al [ADR 0014](0014-scenario-contract-and-provenance.md): añade un campo
  al contrato de escenario, y por tanto es una decisión y no un detalle.
- **Cierra** el primer punto de «Lo que no cierra» del
  [ADR 0019](0019-acquisition-in-the-result.md).

---

## Contexto

El [ADR 0019](0019-acquisition-in-the-result.md) puso en el resultado lo que cada
pase **exige** de un transceptor: la excursión Doppler, el pico de un lado y la
velocidad de seguimiento. Y dejó escrito, en sus propias limitaciones, que nada
decía si algo podía **suministrarlo**, porque el escenario no tenía dónde
declarar la ventana de aceptación de un receptor.

Mientras eso fue así, la comparación la hacía el lector de memoria, con la hoja
de características del transceptor en la cabeza. Que es lo mismo que no hacerla:
el modo de fallo del proyecto no es un error, es un número plausible que nadie
contrasta.

### Qué es un rango de captura, para quien llegue nuevo

Un receptor coherente no encuentra una portadora en cualquier sitio. Tiene una
**ventana de aceptación**: un intervalo de frecuencias dentro del cual puede
buscarla y engancharla. Fuera de ese intervalo la señal está ahí, con toda su
potencia, y el receptor no la ve.

Un pase LEO mueve la portadora **8.37 GHz** de punta a punta (ADR 0019 §1). Si la
ventana es más estrecha que ese recorrido, hay segundos del pase durante los
cuales no hay enlace — y son, por la geometría, los segundos del horizonte, que
es donde la señal además es más débil. Ese es el fallo de final de pase de TBIRD.

---

## Decisión

**Un campo opcional `receiver.doppler_capture_range_hz`, nulo por defecto, en la
convención de anchura total; con `null` el resultado emite un INFO diciendo que
no se ha contrastado nada, y con valor un WARNING por pase que no cabe, llevando
dentro las dos cifras y cuántos segundos del pase quedan fuera.**

### 1. Opcional y nulo por defecto, porque hoy no se sabe

Para CLAU no hay transceptor elegido. Poner un valor por defecto sería declarar
una especificación que nadie ha seleccionado, que es exactamente la regla de «no
inventar números» del README. `null` es la verdad.

### 2. `null` **no** es silencio: es un INFO

Y aquí está el compromiso que hace que el campo valga algo. Una ejecución que no
ha contrastado nada **no puede leerse igual** que una que contrastó y pasó. Si
`null` no dijera nada, las dos producirían el mismo resultado limpio, y la
diferencia entre «cumple» y «nadie lo ha mirado» se perdería.

Es un INFO y no un WARNING porque **ninguna cifra está degradada**: todo lo
calculado es correcto. Lo que falta es una entrada, y una entrada que falta sin
cambiar ningún número es justo para lo que existe INFO
([`core/errors.py`](../../src/quoss/core/errors.py)). El registro lleva dentro la
mayor excursión del día, para que quien lo lea tenga a mano el número con el que
haría la comparación a mano.

### 3. Con valor, un WARNING que dice **cuántos segundos**, no solo que se excede

«Se excede» y «se excede durante 127 s de un pase de 562 s» piden ingeniería
distinta, y desde la primera no se distingue un transceptor equivocado de uno que
recorta un par de muestras en el horizonte. El registro lleva la excursión del
pase, la ventana declarada, la semi-ventana, el pico de un lado, los segundos
fuera y la duración del pase.

Medido en el día de referencia contra una ventana de 8 GHz (±4 GHz): el pase 0
barre 8.3697 GHz y está fuera **127.2 s de 562.2**; el pase 2 barre 8.5376 GHz y
está fuera **173.4 s de 558.4**. Los dos pases bajos caben y no se mencionan.

### 4. La convención es **anchura total**, y la otra lectura existe por su nombre

El campo es la anchura completa de la ventana, emparejada con
`doppler_excursion_hz` y **no** con `peak_one_sided_doppler_hz`. Un transceptor
anunciado como «±5 GHz» es `1e10` aquí.

Por qué anchura total y no ±: es la magnitud con la que se compara, y el
[ADR 0019 §1.a](0019-acquisition-in-the-result.md) acaba de establecer que el
error caro de este dominio es leer un pico como si fuera una anchura. Repetir la
ambigüedad en el campo de entrada, justo después de quitarla de las columnas de
salida, sería reabrirla por el otro lado.

Y para que ninguna de las dos lecturas sea «la que hay que acordarse de
convertir», `ReceiverSpec.doppler_capture_half_range_hz` devuelve la mitad, con
nombre propio.

### 5. Qué significa «fuera», que es una elección y se dice

La ventana se toma **centrada en la portadora nominal**, así que la señal está
dentro mientras `|Δf| ≤ rango/2`. Es la lectura conservadora y la correcta para
la *adquisición*: un receptor que todavía no ha encontrado la portadora no tiene
nada mejor sobre lo que centrarse que lo que el transmisor nominalmente emite.

Un receptor que **pre-compensa** desde una efeméride recentra su ventana instante
a instante, y para ése la comparación que manda es la excursión entera contra la
ventana. Las dos cifras van dentro del aviso, así que las dos lecturas están
disponibles; lo que no está disponible es no leer ninguna.

Que no son la misma comprobación se mide, y el caso está en la suite: contra una
ventana de **4.42 GHz**, el pase 3 del día de referencia tiene una excursión de
**4.3992 GHz** — *cabe*, con 21 MHz de sobra para un receptor que recentra — y
sin embargo un receptor que busca alrededor de la nominal pierde la señal
**1.7 s de un pase de 302.7 s**, porque su semi-ventana llega a ±2.21 GHz y el
pase pica a 2.2256 GHz.

---

## Consecuencias

- Un escenario puede ahora declarar un transceptor y obtener un veredicto por
  pase, y `engine/sweep.py` puede barrer sobre la ventana igual que sobre
  cualquier otro campo: «qué rango de captura hace falta» es un barrido.
- El campo es opcional, así que **ningún escenario existente cambia de
  resultado**; los que no lo declaren ganan un INFO que antes no tenían.
- `scenarios/*.yaml` no lo declaran, deliberadamente: el enlace de referencia
  reproduce a Ntanos et al. 2021, que no especifica un transceptor.

### Lo que no cierra

- **La ventana se compara instante a instante, no se modela un lazo.** Que un
  receptor esté dentro de la ventana no garantiza que enganche: eso depende de la
  velocidad de seguimiento, que es la otra columna, y del tiempo de adquisición,
  que no está modelado. El aviso dice «la señal estuvo fuera», no «el enlace se
  cayó».
- **No hay un campo de velocidad de seguimiento máxima.** Sería el par natural de
  éste y cerraría el segundo requisito del ADR 0019 §1; no se añade hoy porque el
  criterio de «dentro» para una tasa necesita decidir qué se hace con un
  transitorio, y eso es otra decisión.
- **Una sola ventana para todo el receptor.** Un sistema con bajada clásica en
  otra portadora tendría dos, y eso espera al segundo portador del ADR 0019 §2.

---

## Alternativas descartadas

- **Un valor por defecto plausible** (p. ej. ±5 GHz). Convierte una especificación
  inventada en el criterio contra el que se juzgan todos los pases, y nada en el
  resultado diría que salió de la nada.
- **Que `null` sea silencio.** Hace indistinguibles «cumple» y «nadie lo ha
  mirado», que es la degradación silenciosa que el README prohíbe.
- **Un `DomainError` cuando un pase no cabe.** Un transceptor insuficiente no
  hace incalculable el enlace: hace que el enlace tenga huecos, que es un
  resultado válido y es justo el que se quiere poder leer. `warnings[]`, no
  excepción.
- **Reportar solo un booleano «cabe / no cabe».** Tira los segundos, que son lo
  que distingue un problema de diseño de un recorte en el horizonte.

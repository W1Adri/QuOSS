# ADR 0019 — Doppler y point-ahead en el resultado: dos requisitos, no uno, y una portadora que no se configura

- **Estado:** aceptada
- **Fecha:** 2026-09-14
- **Etapa:** 3 (`system/`) y 5 (`engine/`), por el esquema de resultado que comparten.
- **Afecta a:** `orbits/geometry.py`, `system/passes.py`, `scenario/result.py`,
  `engine/pipeline.py`, y todo lo que lea `SeriesResults` o `PassResults`
  (`io/export.py`, `viz/`).
- **Extiende** al [ADR 0014](0014-scenario-contract-and-provenance.md): un campo del
  escenario significa una cosa, y lo que el resultado deriva de él lo deriva a la vista.

---

## Contexto

### Qué son estas dos magnitudes, para quien llegue nuevo

**Doppler.** Un satélite en LEO se acerca y se aleja a varios km/s, y eso
desplaza la frecuencia de la portadora que recibe la estación: acercándose la
sube (azul), alejándose la baja (rojo). A 1550 nm —una portadora de
1.934e14 Hz— una velocidad radial de 1 km/s desplaza **645 MHz**, y un pase
real llega a **±4.3 GHz**.

Un receptor coherente tiene **dos** números frente a eso, y confundirlos es
justo lo que este ADR existe para impedir:

- el **rango de captura**: cuán ancha es la ventana dentro de la cual puede
  encontrar la portadora;
- la **velocidad de seguimiento**: cuán rápido puede barrer el lazo una vez
  enganchado.

Un pase puede caber holgadamente en el primero y dejar atrás el segundo. Cuando
eso pasa, el síntoma es un enganche que aguanta todo el pase y se cae cerca del
horizonte — que es la forma del problema que tuvo TBIRD en órbita, y es la razón
por la que CLAU se está diseñando mirando esto.

**Point-ahead.** La luz tarda en ir y volver, y en ese tiempo el satélite se ha
movido. Un terminal monostático —que transmite y recibe por la misma apertura—
no puede apuntar a donde *ve* el otro extremo: tiene que apuntar a donde **estará**
cuando la luz llegue. Ese adelanto es el ángulo de point-ahead, y en LEO vale
unas decenas de microradianes, del orden del propio ancho del haz.

### El problema concreto

`orbits/geometry.py` ya calculaba las dos cosas —`LookAngles.range_rate_km_s` y
`LookAngles.point_ahead_angle_rad`— y `system/passes.py` ya troceaba la
geometría por pase. **Ninguna de las dos salía del motor.** `SeriesResults` no
las llevaba y `PassResults` tampoco, así que un diseñador que quisiera saber qué
le pide un pase a su transceptor tenía que reconstruir la cadena a mano fuera
del simulador — que es exactamente el trabajo que este simulador existe para no
repetir.

---

## Decisión

**Cuatro series nuevas en `SeriesResults` (velocidad radial, desplazamiento
Doppler, su derivada, y ángulo de point-ahead), y cuatro columnas nuevas por pase
en `PassResults` (máximo de |Doppler|, máximo de |dDoppler/dt|, y el máximo y el
mínimo del point-ahead). La portadora se **deriva** de la longitud de onda del
transmisor del escenario y no es un campo propio.**

### 1. El rango de captura y la velocidad de seguimiento son **dos** columnas

Es la decisión principal y la razón de que haya una derivada en el resultado. La
tentación es reportar solo el pico de |Doppler|, porque es el número grande y
llamativo; pero es solo la mitad de la especificación, y no es la mitad que falla
tarde. Medido en el día de referencia (Castelldefels, 0.75 m, SSO a 700 km,
máscara de 10°, 1550 nm), por pase:

| Pase | Pico de un lado: máx \|Δf\| | Excursión total: máx Δf − mín Δf | Seguimiento: máx \|dΔf/dt\| |
|---|---|---|---|
| 1 | 4.19 GHz | **8.37 GHz** | 37.9 MHz/s |
| 2 | 2.85 GHz | **5.66 GHz** | 19.2 MHz/s |
| 3 | **4.27 GHz** | **8.54 GHz** | **41.5 MHz/s** |
| 4 | 2.23 GHz | **4.40 GHz** | 16.8 MHz/s |

#### 1.a. Por qué la columna de la excursión existe, y por qué la primera no es el rango de captura

Esta tabla tenía **dos** columnas y la primera se llamaba «Captura». Estaba mal,
por un factor **2**, en el único parámetro que este ADR nombra como causa del
fallo de TBIRD.

El pico de un lado es `f0·|ṙ|max/c`: **cuán lejos de la portadora nominal llega
la señal**. Pero la señal no se queda ahí. A lo largo del pase **recorre** de
+4.18 a −4.19 GHz, pasando por cero en la culminación, y un receptor tiene que
poder encontrarla en cualquier punto de ese recorrido. Lo que dimensiona una
ventana de captura o de búsqueda es por tanto la **excursión total**,
`máx Δf − mín Δf` = **8.37 GHz**. Quien compre un transceptor contra «4.19 GHz»
se queda con la mitad de la ventana que el pase necesita.

La respuesta del repo a esta familia de error ya estaba escrita en otros sitios
—`field_of_view_urad` (ángulo completo, no semiángulo), las dos transmitancias
con nombre distinto de `link_budget.py`— y es ponerlo **en el nombre**. Así que
existen las dos columnas, `peak_one_sided_doppler_hz` y `doppler_excursion_hz`,
y ninguna de las dos es «la que hay que acordarse de multiplicar por dos».

**Y no es literalmente un factor dos, lo que importa.** La excursión se **mide**
como `máx − mín`, no se define como el doble del pico. En un pase real los dos
extremos no son iguales —el pase no es simétrico respecto a la culminación y las
muestras son una rejilla—, así que la razón va de **1.977 a 1.999** en el día de
referencia, nunca 2.000. Derivar una columna de la otra cablearía una simetría
que la geometría no tiene, y escondería cualquier error futuro que la rompiera.
La desigualdad `máx − mín ≤ 2·máx(|máx|,|mín|)` sí es aritmética y vale siempre:
es lo que aserta
`tests/engine/test_pipeline.py::TestTheTwoDopplerConventions`.

**Y lo que este día concreto *no* demuestra, dicho para no leerlo de más:** aquí
las dos columnas ordenan los cuatro pases igual (3 > 1 > 2 > 4), porque las dos
las gobierna lo mismo — cuánto se acerca el pase: las culminaciones son 58.8°,
52.9°, 17.7° y 14.2°, y un pase bajo nunca llega a una geometría empinada, así
que ni acelera mucho ni alcanza una velocidad radial grande. Que coincidan es un
hecho sobre **estos cuatro pases**, no una ley, y no hace de una columna la otra:
siguen siendo dos especificaciones distintas del receptor, y son 8.54 GHz de
ventana y 41.5 MHz/s de barrido, números que no se convierten el uno en el otro
sin la geometría. Que no son restatements uno del otro se aserta por la vía
débil y honesta: el cociente excursión/barrido —el tiempo que la señal tarda en
cruzar su propia ventana— **no es constante** entre los cuatro pases, así que
ninguna columna se calcula desde la otra.

**Y el extremo está en los bordes, no en la culminación.** En la culminación el
satélite se mueve **atravesando** la línea de visión, así que la velocidad radial
—y con ella el desplazamiento— pasa por cero. Los extremos caen en el horizonte,
donde la elevación es mínima y el enlace es peor: el receptor tiene que trabajar
más justo donde menos señal tiene. Está asertado en
`tests/engine/test_pipeline.py::TestTheAcquisitionStage`.

### 2. La portadora se deriva, no se configura

`f0 = c / λ` del `transmitter.wavelength_nm` del propio escenario. **No hay un
campo `carrier_frequency_hz`.**

Por qué: un campo aparte permite que una ejecución lleve el Doppler de una
portadora que el escenario no transmite, y nada lo detectaría — las dos cifras
son plausibles y difieren en un factor que nadie mira. Derivarla hace que la
única forma de cambiar el Doppler sea cambiar lo que el sistema emite.

**Lo que esto deja fuera, dicho ahora para que no sorprenda en la etapa 2.2:** un
sistema con una bajada clásica a otra longitud de onda tiene una **segunda**
portadora, y esta serie no es esa. Cuando entre el canal clásico de CLAU hará
falta un segundo campo y una segunda serie; inventarlo hoy sería declarar un
valor que nadie ha elegido.

### 3. Se llevan a la vez la velocidad radial y el Doppler, y la redundancia es deliberada

`doppler_shift_hz` es `range_rate_km_s` por una constante, así que una de las dos
sobra. Se llevan las dos porque responden a personas distintas: la velocidad
radial es la **geometría** y no carga ninguna suposición; el Doppler es esa
geometría **comprometida con una portadora**, y es el número en el que está
escrito el rango de captura de un transceptor.

Llevar solo la primera obligaría a cada lector a multiplicar, cada uno con su
velocidad de la luz y su lectura del signo. Llevar solo la segunda enterraría la
suposición de la portadora dentro de una columna que nadie puede deshacer.

### 4. La derivada es numérica, y lo que eso cuesta está medido

`np.gradient` sobre el eje temporal, diferencias centradas de segundo orden, con
los instantes de muestreo pasados explícitamente para que una rejilla no uniforme
se trate como tal. **No analítica:** la aceleración radial exacta necesita la
aceleración relativa de satélite y estación, es decir el modelo de fuerzas, y un
`LookAngles` lleva posiciones y velocidades.

Lo que la aproximación cuesta, medido en vez de supuesto: el mayor
|dΔf/dt| por pase del día de referencia es **41.547201 MHz/s** en rejilla de 1 s
y **41.549130 MHz/s** en rejilla de 0.1 s — **46 partes por millón**, cien veces
más fino de lo que se escribe cualquier especificación de transceptor.

**Y se diferencia la rejilla entera, no cada pase.** Una derivada tomada dentro
de un pase vería el borde del pase como un extremo y devolvería una diferencia
lateral justo en el horizonte, que es el instante que toda esta magnitud existe
para describir.

### 5. Las series geométricas están definidas **en todas partes**, y el canal no

`SeriesResults` ya ponía `NaN` fuera de un pase para la transmitancia, el
presupuesto y la tasa, porque el canal ahí no se evalúa. Las cuatro series nuevas
son finitas en toda la rejilla, y la asimetría es una afirmación: **un satélite
tiene posición y velocidad aunque el enlace no valga la pena puntuarlo**, y una
pregunta de adquisición se hace precisamente sobre el trozo de cielo que la etapa
de clave se niega a puntuar.

### 6. Los extremos por pase son **cotas**, y se dice cuánto

`PassSamples.segment_max` y `segment_min` reducen sobre las muestras de la
rejilla que están **dentro** del pase, y un pase empieza y acaba *entre* muestras
(`PassTable.start_s` es un cruce refinado). Las magnitudes que pican en el
horizonte —las cuatro— vuelven por tanto como cota inferior (las tres máximas) o
superior (la mínima) del extremo real del pase continuo.

Es la misma honestidad que `sampled_culmination_elevation_rad`, y del mismo
tamaño: el mayor |Doppler| por pase es 4.272427 GHz en rejilla de 1 s y
4.273114 GHz en la de 0.1 s, **160 partes por millón**. Quien dimensione un rango
de captura con esto debe tomar la cota por lo que es; quien use una rejilla de
30 s debería refinarla antes.

### 7. `segment_max` y `segment_min` son reducciones con nombre, no un truco

`segment_sum` convertía una magnitud por instante en una por pase, y es la
reducción de un **rendimiento**: la clave de un pase es la integral de su tasa.
Un **requisito** no se integra, se maximiza. Por eso hay dos métodos nuevos al
lado y no una expresión en el motor.

Son **con signo**: el máximo de una serie con signo no es el máximo de su módulo
—el Doppler va de un azul grande a un rojo grande— así que el llamante escribe
`np.abs(...)` y las dos preguntas siguen siendo dos. Y `segment_min` existe en
vez de `-segment_max(-x)` porque ese idioma necesita un comentario cada vez que
se escribe y se equivoca de signo a la tercera.

Un pase sin muestras devuelve `-inf` / `+inf`, no cero: sin muestra no hay
máximo, y un cero sería un valor que nadie midió.

### 8. Se reportan el máximo **y el mínimo** del point-ahead

Porque lo que dimensiona un espejo de apuntado fino es el **recorrido**, no el
pico. En el mejor pase del día de referencia el adelanto va de **24.685920 a
50.652309 µrad**: un factor dos dentro de un solo pase. Un terminal que
mantuviera un adelanto fijo se equivocaría en 26 µrad en un extremo del pase, que
a esas divergencias es apuntar fuera del haz.

---

## Consecuencias

### Lo que esto abre

- El criterio de aceptación 2 del enlace de CLAU —«leer del resultado, por pase,
  el máximo de |Doppler| y su derivada, y el ángulo de point-ahead»— se cumple
  desde un escenario versionado, y sale también por `io/export.py` sin tocarlo:
  las tablas se construyen del manifiesto, así que las columnas nuevas viajan
  solas a CSV, Parquet, `npz` y JSON.
- El barrido de `engine/sweep.py` puede reducir sobre las columnas nuevas igual
  que sobre la clave, así que «qué rango de captura hace falta para una máscara
  de X grados» es un barrido, no un script.

### Lo que no cierra

- ~~**No hay un campo de rango de captura en el escenario y por tanto no hay
  aviso.**~~ **Cerrado** por el [ADR 0020](0020-declared-doppler-capture-range.md):
  `receiver.doppler_capture_range_hz` es opcional y nulo por defecto, `null`
  emite un INFO diciendo que no se ha contrastado nada, y un valor declarado
  levanta un `WARNING` por pase que no cabe con los segundos que quedan fuera.
- **Un segundo portador para la bajada clásica** (punto 2), que es de la
  etapa 2.2 de CLAU.
- **El point-ahead no lleva su propio presupuesto de error.** El ángulo es
  `2 v_perp / c` y lo que un terminal real consigue depende de la calibración del
  sensor de faro; aquí está el ángulo que la geometría pide, no el que un
  actuador entrega.

---

## Alternativas descartadas

- **Reportar solo el pico de |Doppler|.** Es la mitad de la especificación, y la
  mitad que no explica un enganche que se cae al final del pase.
- **Un campo `carrier_frequency_hz` en el escenario.** Permite una ejecución que
  reporta el Doppler de una portadora que no se transmite, sin que nada lo vea.
- **Derivar la aceleración radial analíticamente.** Necesita el modelo de
  fuerzas dentro de `geometry.py`, que es una dependencia al revés de la regla
  del README; y la diferencia numérica cuesta 46 ppm en la rejilla de trabajo.
- **Calcular los extremos sobre los bordes refinados del pase** en vez de sobre
  las muestras. Sería exacto y necesitaría evaluar la geometría fuera de la
  rejilla, lo que convierte una reducción en una interpolación con su propio
  error. La cota, dicha como cota y medida, es más barata y más honesta.

---

## Verificación

- `tests/orbits/test_geometry.py::TestDopplerRate` — V1 contra la derivada exacta
  de un rango cuadrático (donde la diferencia centrada es exacta, lo que separa
  la fórmula de la discretización), el signo contra la imagen física, la
  integral de la derivada contra el salto del desplazamiento, la rejilla no
  uniforme, y las seis entradas que se rechazan.
- `tests/system/test_passes.py::TestTheSegmentExtrema` — el máximo por pase contra
  la culminación refinada (la cota), la reducción con signo, la identidad
  `min = -max(-x)`, y el pase vacío.
- `tests/engine/test_pipeline.py::TestTheAcquisitionStage` — la portadora que se
  deriva (media longitud de onda dobla el Doppler y no toca la geometría), las
  series definidas donde el canal no lo está, la estación sin pases, el extremo
  en los bordes y no en la culminación, y la cota apretándose al refinar.
- `tests/e2e/test_reference_scenarios.py` — las cuatro series y las cuatro
  columnas contra la cadena cableada a mano, por **igualdad exacta**
  ([ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md)).

Cobertura con ramas de todo lo tocado —`orbits/geometry.py`, `system/passes.py`,
`scenario/result.py`, `engine/pipeline.py`, `io/export.py`— al **100 %**.

## Referencias

- [ADR 0014](0014-scenario-contract-and-provenance.md) — el escenario como dato.
- [ADR 0016](0016-the-engine-adds-nothing-and-one-altitude.md) — el puente de
  igualdad exacta que cubre las columnas nuevas.
- El módulo `quoss.orbits.geometry` documenta la derivación del factor 2 del
  point-ahead y su referencia (Degnan, *Contributions of Space Geodesy to
  Geodynamics*, Geodynamics Series vol. 25, 1993).

# ADR 0013 — Las nubes deciden si el pase existe, un terminal decide a quién sirve, y el almacén de a bordo hace que el orden importe solo para la latencia

- **Estado:** aceptada
- **Fecha:** 2026-09-13
- **Etapa:** 3 (`system/pcflos.py`, `system/multi_ogs.py`, `system/relay.py`)
- **Afecta a:** todo número que este proyecto publique como «clave por día con
  N estaciones», «disponibilidad» o «clave extremo a extremo», y por tanto a
  `scenario/` (`MultiStationSpec`, `RelaySpec`, `StationSpec.cloud_fraction`),
  a `engine/` y a `io/openmeteo.py`.
- **Extiende** al [ADR 0011](0011-the-block-is-the-pass.md): la cota finita
  certifica los bits de un pase; aquí se decide qué hace una probabilidad de
  cielo despejado con esos bits (nada: decide si el pase ocurre), y qué hacen
  varios pases de varias estaciones con un solo terminal y un solo almacén.
- **Extiende** al [ADR 0009](0009-citation-policy.md) con cinco huecos nuevos,
  declarados abajo, el primero de ellos con la firma.

---

## Contexto

### Tres preguntas que una estación sola no puede contestar

Hasta `key_volume.py` todo el paquete `system/` es la vista de una estación.
Una misión tiene varias, y un cielo, y con eso aparecen tres preguntas:

1. **¿Con qué probabilidad existió el pase?** Una nube no atenúa: corta. Un
   cirro cuesta decenas de decibelios y un cúmulo lo cuesta todo, así que el
   modelo honesto es binario y la cantidad es una probabilidad, pCFLOS.
2. **¿Cuánta clave dan varias estaciones?** Depende de si el satélite tiene un
   terminal para todas o guarda una clave por estación. Son dos aritméticas.
3. **¿Cómo comparten clave dos estaciones que nunca ven el satélite a la vez?**
   A través del satélite, que la guarda y la empareja. Es una simulación sobre
   el tiempo con un almacén.

### El error que había que impedir antes de escribir la primera línea

`key_volume.py` y el ADR 0011 lo dejaron escrito: multiplicar un volumen de
clave por una probabilidad de cielo despejado convierte «funciona el 70 % de
las noches» en «entrega el 70 % de la clave cada noche», que son sistemas
distintos — el primero guarda clave contra las rachas secas, el segundo no lo
necesita. Y el modo de fallo es el de siempre: el número que sale es plausible.

### Y la fuente que no se pudo abrir

La dependencia de pCFLOS con la elevación —que existe, porque una línea a 10°
recorre 5.8 veces más capa de nubes que una vertical— tiene una medida clásica,
Lund & Shanklin (*J. Appl. Meteorol.* 11:773, 1972, y 12:28, 1973). La
editorial devuelve 403 y Semantic Scholar 429. Por el ADR 0009, no se transcribe
de memoria ningún número con un número de tabla al lado.

---

## Decisión

### 1. La probabilidad de cielo despejado multiplica una **esperanza**, nunca una clave

Toda cifra etiquetada `expected` en `multi_ogs.py` es `bits × disponibilidad`:
la clave esperada sobre el tiempo de un pase que certifica `bits` cuando
ocurre. Es un número de planificación para una temporada. La cota finita
certifica los bits; la nube decide si el pase ocurre. `MultiStationKeyVolume`
lleva **las dos columnas** —`station_bits` y `station_expected_bits`— y un
`INFO` que lo dice en cada llamada con disponibilidad. No hay ninguna función
que devuelva solo la esperada.

### 2. Sin elevación en ninguna firma, y con aviso en cada llamada

`cloud_free_probability(cloud_fraction, *, degradations)` devuelve `1 − f`, que
para una línea vertical es una definición: la fracción de cobertura *es* la
fracción del área que una vertical atraviesa con nube. **No acepta una
elevación**, y `tests/system/test_pcflos.py::test_no_function_here_takes_an_elevation`
lo aserta por ausencia sobre todo `__all__`, el mismo control negativo de
`channel/background.py`. Cada llamada registra un `WARNING`
(`pcflos.no-elevation-dependence`) con el sentido del error: para una capa, una
línea oblicua solo puede encontrar *más* nube, así que `1 − f` es **cota
superior** a cualquier elevación y exacta solo en el cénit.

**Por qué no un modelo geométrico.** Necesitaría la altura de la base y el
tamaño de celda, que no están en ningún archivo de cobertura, y el resultado es
sensible a ambos: el mismo `f = 0.5` puede ser una sábana continua (una línea
oblicua la cruza con probabilidad 0.5, como una vertical) o un campo de cúmulos
pequeños (una línea a 10° apenas puede evitarlos). Un par adivinado daría una
curva plausible con un error que nadie podría acotar, y el número saldría con
la elevación pegada, como si se hubiera medido.

### 3. Tres lecturas de una serie horaria, la media por defecto, y la diferencia medida

ERA5 es horario; un pase dura diez minutos. `pass_availability` interpola
**linealmente** —la única regla que no añade estructura que los datos no
tienen— y lo registra como `INFO` en cada llamada. Luego tiene que decir qué
valor «es» el pase, y ofrece tres (`AvailabilityRule`): la **media ponderada
por permanencia** (fracción esperada de instantes despejados), la
**culminación**, y el **mínimo** (lo que necesita un pase si un minuto tapado
aborta el bloque). Ninguna es «la» disponibilidad: la de verdad necesita la
correlación espacio-temporal de la nube a diez minutos, que un archivo horario
no contiene.

Lo que sí garantiza la resolución horaria es que no pueden diferir mucho, y se
**mide** en vez de afirmarse
(`TestTheThreeReadingsOfAnHourlySeries::test_the_spread_between_readings_is_small_at_hourly_resolution`):
con un frente sintético de 0.05 a 0.95 en tres horas, colocado sobre los pases
del día de referencia, la mayor diferencia entre dos lecturas es **0.023**,
contra un techo *derivado* de 0.047 (0.3 por hora por 562 s). La media es el
defecto porque es la única que es una esperanza de algo; las otras dos viajan en
el registro.

### 4. Dos estaciones: exacto. Tres o más: cotas, y el hueco con nombre

Con `ρ_ij = exp(−d_ij/L)`, dos Bernoulli con marginales y correlación dados
tienen **una** ley conjunta, y `joint_cloud_free_probability` la devuelve
exacta (`P(ambas nubladas) = q₁q₂ + ρ√(p₁q₁p₂q₂)`). No toda `ρ` es compatible
con todo par de marginales: la cota de Fréchet `√(min(p₁q₂,p₂q₁)/max(·))` vale
1 con marginales iguales y 0.2182 con 0.9 y 0.3. **Por encima se lanza
`DomainError`, no se recorta**, porque una correlación recortada es un modelo
sustituido sin registro.

Con `N ≥ 3`, `2^N − 1` probabilidades libres contra `N(N−1)/2` correlaciones:
no hay valor exacto que calcular. Se devuelven las dos cotas —independencia por
arriba, `max_i p_i` por abajo— con `exact = None` y un `WARNING`. Una cópula
gaussiana rellenaría el hueco con una elección concreta; no se hace porque nada
verificado dice que sea la correcta. `L` **no tiene defecto**.

### 5. Un planificador exacto, porque el greedy no lo es y el exacto no cuesta más

`BEST_AVAILABLE` modela un terminal a bordo: los pases solapados chocan.
Elegir el subconjunto disjunto de mayor peso es *weighted interval scheduling*,
con solución exacta en `O(n log n)`: ordenar por fin, bisección al último
compatible, `M_j = max(M_{j−1}, w_j + M_{p(j)})`, retroceso. El greedy por
clave pierde cuando un pase rico está entre dos algo más pobres que no chocan
entre sí (6 contra 8). El brief pedía greedy «documentado y medido contra el
óptimo»; se implementó el óptimo y se dejó el greedy al lado **con nombre**,
para que la comparación sea entre dos funciones y no una afirmación sobre una.

Dos detalles que el test encontró y la derivación no:

- **Compleción.** El programa dinámico deja fuera un intervalo que no aporta
  nada, así que reportaría un pase muerto como «descartado» aunque no choque
  con nadie. Un segundo paso añade, en orden de fin, todo intervalo no
  seleccionado compatible con todo lo seleccionado —solo puede ser de peso
  cero— y después «no seleccionado» significa **choca con uno seleccionado** y
  nada más. El total no cambia; la fuerza bruta lo comprueba.
- **El terminal de tierra.** Dos satélites sobre una estación a la vez es el
  conflicto espejo, y no se modela: alcance de un satélite (2026-09-10). Se
  rechaza con `DomainError` en vez de planificarse mal.

`minimum_gap_s` (giro y asentamiento) tiene defecto `0.0`: no hay fuente, y
cero es el único valor que no es una invención.

### 6. El relé: el orden decide la latencia, no la cantidad

Con almacén ilimitado, los dos saldos nunca son positivos a la vez, así que al
cerrar la ventana uno es cero y **el total entregado es `min(ΣK_A, ΣK_B)` sea
cual sea el orden**. Lo que el orden decide es **cuándo** (latencia, día UTC)
y **cuánto queda varado**. La identidad se aserta con Hypothesis para que el
total no se lea como mérito de la planificación. La clave de un pase existe
cuando el pase **termina** (el bloque es el pase), el almacén es FIFO, y la
latencia se define dos veces: edad del bit más antiguo y media ponderada.

La seguridad se compone por **cota de la unión** sobre los bloques consumidos
de ambos lados: la clave extremo a extremo falla si cualquiera de las dos
falló, y la composabilidad es exactamente lo que autoriza sumar. Cuatro bloques
a `1e-10` dan `4e-10`; si la suma llega a uno se rechaza.

**ISL fuera de alcance, sin stub.** Un segundo satélite en cualquiera de los
volúmenes es `DomainError` nombrando la decisión. Un relé por dos satélites es
otro almacén con otra afirmación de seguridad.

### 7. Las coordenadas de las estaciones de medida, con su procedencia

- Castelldefels: las constantes de `tests/system/reference.py`.
- Calar Alto: 37°13'25"N 2°32'46"W, 2168 m — infobox de Wikipedia (2026-09-13);
  la web del observatorio confirma la altitud y no imprime coordenadas.
  **Aproximadas al segundo de arco del infobox**; unos cientos de metros no
  mueven un pase.
- OGS de ESA, Tenerife: 28.298 N, 16.511833 W, 2400 m — página institucional
  del IAC (2026-09-13).

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Multiplicar `key_bits` por la disponibilidad y devolver un solo número** | Convierte «el 70 % de las noches» en «el 70 % de la clave cada noche». Las dos columnas viajan juntas y ninguna función devuelve solo la esperada |
| **Transcribir la curva de Lund & Shanklin de memoria** | Ninguno de los dos papers se pudo abrir. Un número con número de tabla que nadie ha comprobado es el fallo que el ADR 0009 existe para impedir |
| **Un modelo geométrico de nube con base y celda adivinadas** | Sensible a las dos, ninguna está en un archivo de cobertura, y la curva saldría con la elevación pegada como si fuera medida |
| **Devolver el mínimo sobre la ventana como disponibilidad** | Es la lectura pesimista de una cantidad que ninguna de las tres lecturas mide; difiere de la media 0.023 y viaja en el registro |
| **Recortar `ρ` a la cota de Fréchet** | Sustituye un modelo sin registro. El `DomainError` dice qué par y por cuánto |
| **Una cópula gaussiana para N > 2** | Rellenaría el hueco con una elección sin fuente; se devuelven las cotas |
| **Un defecto para `L`** | Es todo el contenido del modelo de correlación y nadie lo publica |
| **Greedy por clave** | No es exacto (6 contra 8 en la instancia del test) y el exacto cuesta lo mismo |
| **Planificar también el terminal de tierra** | Deja de ser interval scheduling; alcance de un satélite. Se rechaza en vez de planificar mal |
| **Un stub o bandera para ISL** | Otro almacén, otra seguridad. `DomainError` con la decisión |
| **Componer la seguridad del relé como el máximo de los dos lados** | La clave falla si *cualquiera* falla: cota de la unión, suma |

---

## Consecuencias

### Lo que ahora se puede afirmar

- Una disponibilidad por pase desde una serie horaria, con la regla y la
  interpolación en el registro y el coste de la elección medido.
- Cuánto compra la diversidad de emplazamiento **con un terminal** (2.30 veces
  la estación sola en el día de referencia) y cuánto cuesta el terminal único
  frente a la suma (5.4 %).
- Clave extremo a extremo por nodo de confianza con latencia definida, residuo
  a bordo y `eps` compuesto — y la advertencia de que el total no depende del
  orden.

### Lo que esto cuesta

- **Dos columnas donde uno querría una.** Certificada y esperada. Es
  deliberado.
- **Un objeto de resultado para la probabilidad conjunta** en vez de un array,
  porque para N > 2 son dos cotas y no un número.
- **Dos bucles de Python sobre pases** (el planificador y el almacén). Son
  cientos de pasos una vez; el eje temporal sigue vectorizado.

### Lo que queda explícitamente fuera

1. La dependencia angular de pCFLOS (hueco con la firma).
2. La ley conjunta de N > 2 estaciones.
3. `L`, la longitud de decorrelación.
4. El hueco de reorientación del terminal.
5. El terminal de tierra con varios satélites, y los ISL.
6. Un almacén de a bordo acotado; los residuos dicen cuánto tendría que guardar.

---

## Verificación

- `tests/system/test_pcflos.py` (53 tests): `1 − f` con Hypothesis; el control
  negativo de la elevación; las tres lecturas y su diferencia de 0.023 contra
  el techo derivado de 0.047; la media contra un bucle por pase y el mínimo
  contra muestreo denso y contra un nudo escondido dentro de un pase (V3);
  cobertura de serie rechazada, épocas reconciliadas; la ley de dos Bernoulli
  transcrita aparte, las cotas con Hypothesis, la cota de Fréchet a ambos
  lados; N > 2 con el hueco en el registro; la separación contra la haversine
  con la cota **derivada** `1 − a(1−e²)/R` (V3).
- `tests/system/test_multi_ogs.py` (55 tests): el programa dinámico contra
  fuerza bruta sobre todos los subconjuntos (Hypothesis, 300 instancias, con y
  sin hueco), maximalidad, greedy nunca por encima y perdiendo en la instancia
  4+4 contra 6; el día de referencia con tres estaciones (1 052 607 contra
  995 682, 4 de 10, 56 925 bits, 2.30×) y que el greedy coincide ahí; la
  planificación pesa esperados; el hueco solo quita; el terminal de tierra
  rechazado; cada `DomainError`.
- `tests/system/test_relay.py` (39 tests): la identidad `min(ΣA, ΣB)` con
  Hypothesis; el almacén contra una segunda implementación en Python plano
  (V3); el día de referencia contra Tenerife (tres entregas, 1.6 a 9.4 h,
  129 712 varados, `4e-10`) y contra Calar Alto (59 s y 39 822 s); la
  composición sobre bloques consumidos y los dos rechazos distintos; un segundo
  satélite rechazado y ningún «ISL» en la superficie.
- **100 % de cobertura de líneas y ramas** en los tres módulos (657 sentencias,
  244 ramas); 10 doctests.

## Referencias

- I. A. Lund y M. D. Shanklin, «Photogrammetrically determined cloud-free
  lines-of-sight through the atmosphere», *J. Appl. Meteorol.* **11**(5):773,
  1972; «Universal methods for estimating probabilities of cloud-free
  lines-of-sight through the atmosphere», *J. Appl. Meteorol.* **12**(1):28,
  1973. **Citados como la fuente que cerraría el hueco, no como fuente de
  ningún número: no se pudieron abrir.**
- [ADR 0011](0011-the-block-is-the-pass.md) (el bloque es el pase; la clave de
  un pase existe cuando termina), [ADR 0009](0009-citation-policy.md) (los
  huecos se declaran), [ADR 0001](0001-unit-conventions.md).
- `notes/LAST_CHANGES.md`, decisión de 2026-09-10: un satélite, sin ISL.

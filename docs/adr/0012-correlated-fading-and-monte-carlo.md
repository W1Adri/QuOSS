# ADR 0012 — El desvanecimiento es un proceso en el tiempo, y la clave de un pase es una distribución

- **Estado:** aceptada
- **Fecha:** 2026-09-13
- **Etapa:** 3 (`system/correlated_fading.py`, `system/monte_carlo.py`)
- **Afecta a:** toda cifra que este proyecto reporte como «clave por pase» o
  «clave por día» con una barra de error, al entregable DB3, a `scenario/`
  (`MonteCarloSpec`) y a `engine/`.
- **Cierra** las dos reservas que el [ADR 0011](0011-the-block-is-the-pass.md)
  dejó explícitamente fuera: «la dispersión entre pases» y «el fading
  correlacionado en el tiempo», y con ellas la frase de `channel/link_budget.py`
  —«hasta que exista `system/correlated_fading.py`, ninguna afirmación de ese
  módulo sobre clave *por pase* se sigue de una sobre clave *por puerta*»—, que
  ahora tiene el módulo al que apuntaba.
- **Extiende** al [ADR 0009](0009-citation-policy.md): los tiempos de
  correlación son un hueco declarado y por eso son un parámetro, no un modelo.

---

## Contexto

### Qué es un desvanecimiento, y qué sabía el proyecto de él hasta ahora

La potencia que un telescopio de tierra recoge de un satélite no es estable.
Dos cosas la sacuden. El aire que el haz atraviesa está lleno de lentes en
movimiento y la irradiancia parpadea —eso es la **centelleo**, el titilar de
una estrella—, y el terminal del satélite nunca apunta exactamente al
telescopio, así que el telescopio está ahora más cerca del centro del haz y
ahora más cerca de su borde —eso es el **jitter de apuntado**—. Un
**desvanecimiento** («fade») es un tramo de tiempo en el que cualquiera de las
dos ha empujado la potencia recogida por debajo de aquello para lo que el enlace
se diseñó.

`channel/link_budget.py` trata los dos como **distribuciones marginales**: se
pregunta qué fracción del tiempo está el enlace peor que un nivel, y contesta
con un número por muestra, el nivel que se supera el 99 % del tiempo. Eso es la
pregunta correcta para un presupuesto estático y la pregunta equivocada para un
bloque de cuentas, porque no dice nada de **cuánto dura** un desvanecimiento una
vez que empieza. Un enlace desvanecido el 1 % del tiempo en mil parpadeos
independientes de un microsegundo y un enlace desvanecido el 1 % del tiempo en
un único apagón de diez segundos tienen la misma marginal y consecuencias
completamente distintas.

### Qué número reporta hoy el proyecto, y qué número es

`pass_key_volume` alimenta `expected_block_counts` con
`LinkConditions.transmittance`, que es `LossBudget.transmittance` y **lleva
dentro el margen de desvanecimiento** `fade_db`: la pérdida que apuntado y
centelleo juntos solo superan el 1 % del tiempo. Así que la cifra que el
proyecto reporta hoy —**432 985 bits/día** en el día de referencia— es la clave
de un pase en el que el enlace está en su cuantil del 1 % **durante todo el
pase**, como si la peor centésima de segundo fuera cada segundo. No es la media
de la clave sobre la distribución del desvanecimiento ni ningún cuantil de la
distribución de claves por pase. Es una cifra de diseño.

Medido en `tests/system/test_monte_carlo.py::TestWhatTheDesignNumberUnderReports`:
el mismo cálculo determinista a la transmitancia **media** —el margen devuelto,
el factor de apuntado en su media `γ²/(γ²+1)`— da **758 707 bits**, ×1.752, así
que la cifra de diseño **infrarreporta el día típico un 43 %**. Y los dos pases
muertos siguen muertos: los pases 2 y 4 no certifican nada tampoco a la
transmitancia media, así que el hallazgo del ADR 0011 no era un artefacto del
margen.

---

## Decisión

### 1. Los dos desvanecimientos son procesos gaussianos en la variable donde son gaussianos, con memoria exponencial

**Centelleo.** `scintillation_fade_db` lee la Ec. (18) de Ntanos et al. como una
distribución: el desvanecimiento en dB es gaussiano con media `4.343 σ²/2` y
desviación `4.343 σ`. Deshacer los decibelios es decir que la log-irradiancia
`χ = ln(I/⟨I⟩)` es `N(−σ²/2, σ²)`, y la media `−σ²/2` es lo que hace
`E[exp χ] = 1`. Ese convenio se mantiene exactamente, comprobado en
`TestAgainstTheChannelsClosedForms`: con un millón de muestras, el factor
promedia a 1 dentro de cuatro errores estándar, y el cuantil del 1 % del
desvanecimiento en dB reproduce el de `link_budget.py`.

**Apuntado.** `pointing.py` deriva su ley de dos componentes gaussianas
independientes de jitter, una por eje. Con `γ = w_zeq/(2σ_s)` el factor relativo
es `F_p = exp(−(x₁² + x₂²)/(2γ²))` con `x₁, x₂ ~ N(0,1)`, y de ahí salen
exactamente las dos cosas que `pointing.py` publica y que aquí son el oráculo
V3: `P(F_p < x) = x^(γ²)` y `E[F_p] = γ²/(γ²+1)`. Nótese lo segundo: **el
factor de apuntado no promedia a uno**; un terminal que tiembla pierde potencia
en media, y `FadeRealisations.mean_pointing_factor` lo lleva para que el
llamante sepa alrededor de qué fluctúa el conjunto.

**Tiempo.** Cada motor gaussiano —uno para el centelleo, dos para el apuntado—
es un **proceso de Ornstein-Uhlenbeck**: el proceso gaussiano estacionario con
memoria más simple, cuya correlación decae como `exp(−|Δt|/τ)`. El único
parámetro `τ` es el **tiempo de correlación**: cuánto tarda el proceso en
olvidar dónde estaba, a un factor `1/e`. Muestreado en una rejilla es una
recursión AR(1), y la discretización es **exacta**, no de Euler:
`φ_i = exp(−Δt_i/τ)`, `x_i = φ_i x_{i−1} + sqrt(1−φ_i²) ε_i`, válida en
rejillas no uniformes y comprobada contra `exp(−k Δt/τ)` a los retardos 1, 2 y
5 dentro del error estándar de su propio estimador
(`TestTheProcess::test_the_autocorrelation_is_the_exponential_of_the_lag`).

### 2. El tiempo de correlación es un parámetro, no un modelo

Porque ninguna fuente abierta para este proyecto lo publica con la precisión
que un modelo afirmaría. Lo que hay es un orden de magnitud por la hipótesis de
turbulencia congelada de Taylor —el patrón se arrastra rígido a través de la
línea de visión, así que una anchura de correlación `ℓ` en el espacio se
convierte en `τ = ℓ/v`—, y para un enlace descendente LEO la velocidad `v` **no
es el viento**: es el barrido de la línea de visión a través de la capa
turbulenta. Medido en el pase 3 del día de referencia
(`TestChoosingACorrelationTime`): a la altura de escala de la turbulencia de la
UIT, 7 700 m, la línea de visión barre a **62–85 m/s** contra los 2.3 m/s de
viento a ras de suelo de la P.1621. Con una anchura de Fresnel `sqrt(λh)` =
0.109 m, `τ` cae en **1.3–1.8 ms**; con solo el viento diría 47 ms, treinta
veces más. La anchura `ℓ` es un hueco declarado, no un número adivinado.

Así que `FadingParameters` toma los dos tiempos como argumentos obligatorios,
`taylor_correlation_time_s` y `slew_transverse_speed_m_s` dan la derivación para
quien quiera elegirlos desde una geometría, y ninguno tiene defecto.

### 3. Lo que se alimenta al modelo de cuentas es el factor **promediado sobre la permanencia**, y el promedio se muestrea exacto

Un tiempo de correlación de milisegundos y una rejilla de 1 s significan mil
desvanecimientos independientes dentro de cada muestra. Los pulsos de esa
muestra ven el **promedio** del desvanecimiento sobre su permanencia, no un
valor instantáneo, y el modelo de cuentas es lineal en la transmitancia hasta
`ημ`, que en el enlace de referencia es menor que `5e-4`
(`TestReproducesTheDeterministicVolume::test_the_click_probability_bounds_the_poisson_approximation`).
Alimentarlo con un sorteo de varianza completa por muestra sobreestimaría la
fluctuación de cada muestra en `1/w`, con
`w(T/τ) = 2(τ/T)²(T/τ − 1 + e^{−T/τ})` la reducción exacta de varianza de un
promedio de Ornstein-Uhlenbeck sobre una ventana `T`: 500 en varianza para 1 s
y 1 ms. Medido sobre el pase 1 del día de referencia
(`TestWhatCorrelationChangesOnTheGrid`): un sorteo instantáneo por muestra
sobreestima la desviación del recuento agrupado del pase en un factor que cae
entre `sqrt(1/w)` de los dos componentes —10 para el apuntado a 10 ms, 22 para
el centelleo a 1 ms—, y la fluctuación real del recuento agrupado es menor que
el 0.2 %.

**Cómo se aplica.** No se sub-muestrea (a 1 ms por debajo de 1 s serían 4 000
sub-pasos por muestra, 7·10⁹ sorteos para un día a mil realizaciones). En su
lugar `sample_fade_factors` muestrea la **integral** del motor gaussiano sobre
cada ventana exactamente, junto con su valor final —el par es conjuntamente
gaussiano con covarianzas en forma cerrada—, de modo que ventanas consecutivas
conservan la correlación que de verdad tienen y no la de sus extremos. La no
linealidad de los dos factores se evalúa sobre la media estandarizada y se
encoge hacia la media marginal por `sqrt(w)`, a `τ` para el centelleo y a
`τ/2` para el apuntado, porque el factor de apuntado depende del **cuadrado** de
sus motores y `E[x_t² x_s²] − 1 = 2 exp(−2|t−s|/τ)`. La construcción tiene la
media exacta a todo `T/τ`, es exacta en los dos límites, y reproduce la varianza
y la covarianza entre ventanas del promedio verdadero a primer orden en `σ²` y
`1/γ²`. Contra un promedio de fuerza bruta sobre una rejilla fina
(`TestTheDwellAverage::test_the_construction_matches_a_brute_force_average_of_the_factors`,
20 000 trayectorias, 200 sub-pasos por ventana, `T/τ` = 0.1, 1 y 10, `σ²` y `γ`
de referencia): varianza por ventana dentro del 1.5 % en los tres componentes;
varianza a nivel de pase del producto dentro del 1.5 %; la única debilidad
conocida es la covarianza entre ventanas de la parte de apuntado a `T = τ`, un
5 % por debajo, y está acotada en el test y dicha en el docstring.

### 4. El hallazgo, dicho sin adorno: en la rejilla del proyecto la correlación casi no mueve la clave, y lo que la mueve es contar

Barrido de `τ` sobre el enlace de referencia con los dos tiempos iguales y las
cuentas en su esperanza (`TestWhatCorrelationChanges`, 400 realizaciones):

| `τ` | Pase 1, P5–P95 (%) | Pase 3, P5–P95 (%) | Día, P5–P95 (%) |
|---|---|---|---|
| 1 ms | 0.11 | 0.09 | 0.07 |
| 10 ms | 0.33 | 0.27 | 0.22 |
| 100 ms | 1.04 | 0.89 | 0.68 |
| 1 s | 3.6 | 3.0 | 2.2 |
| 10 s | 10.9 | 9.9 | 7.4 |
| 100 s | 30.4 | 28.8 | 20.0 |

Cada década de `τ` ensancha la banda en `sqrt(10)`, porque la reducción es
`2τ/T` y un pase contiene `duración/(2τ)` tramos independientes. La banda cruza
el 1 % de la mediana **entre 10 y 100 ms**, dos órdenes de magnitud por encima
de la estimación física, y la mediana no se mueve con `τ`.

**Y a la `τ` física el desvanecimiento no es lo que fija la dispersión.** Con
las cuentas del bloque sorteadas de Poisson y sin desvanecimiento (`τ → 0`), la
banda P5–P95 del pase 1 es el **9.0 %** de la mediana; con el desvanecimiento a
los tiempos físicos encima, el 9.4 %. Noventa veces la contribución del
desvanecimiento, y no viene de los millones de detecciones del bloque —cuya
dispersión de Poisson propia es el 0.03 %— sino de las cuentas pequeñas de
señuelo y de vacío desde las que la cota infiere el rendimiento de un fotón, y
cuya dispersión amplifica: los eventos certificados de un fotón dispersan más
de cinco veces lo que el tamaño del bloque
(`test_counting_noise_dwarfs_fading_at_the_physical_tau`). Es el número contra
el que un estudio sobre «el efecto del desvanecimiento en la clave» tendría que
compararse antes que nada.

Lo que el desvanecimiento correlacionado **sí** cambia: (a) los cuantiles bajos,
en exactamente la varianza que la correlación añade en cuanto `τ` es comparable
a la permanencia, y (b) la **estadística de duración de los desvanecimientos**,
que gobierna sincronización y errores a ráfagas y que un modelo i.i.d. calcula
mal por la razón que sigue.

### 5. La duración de un desvanecimiento se cuenta por paso de rejilla, porque en tiempo continuo diverge

Para un proceso gaussiano diferenciable la fórmula de Rice da la tasa de
cruces de un nivel. Una trayectoria de Ornstein-Uhlenbeck **no es
diferenciable** —sus incrementos en `Δt` son de tamaño `sqrt(Δt)`—, así que la
tasa de cruces en tiempo continuo es infinita: refinar la rejilla hace crecer el
recuento sin límite. La cantidad que existe es el número esperado de cruces
hacia abajo *por paso*, que para un motor gaussiano al nivel `c` es la
probabilidad binormal exacta `P(x_{i−1} ≥ c, x_i < c) = Φ(c) − Φ₂(c, c; φ)`.
`fade_duration_statistics` lo reporta con su paso al lado, y
`TestFadeDurations` lo comprueba contra la binormal de SciPy (implementación
independiente) dentro de cuatro errores estándar.

Medido con el factor de apuntado bajo 0.85 y `τ_p = 0.2 s`
(`test_an_iid_model_gets_fade_durations_wrong_by_the_step_to_tau_ratio`): la
duración media del desvanecimiento correlacionado es **47, 22 y 14 ms** a pasos
de 20, 5 y 2 ms —2.3, 4.5 y 7.0 pasos— contra los 1.04 pasos del modelo i.i.d.
a cualquier paso; los desvanecimientos por segundo crecen como `Δt^{−1/2}`
(0.90, 1.90, 2.97), que es la divergencia de Rice vista en una rejilla, mientras
la fracción de tiempo desvanecido se queda en el 4.2 % marginal. Las dos cosas
están afirmadas en el test, incluida la divergencia, porque un módulo que
reportara «la duración del fade» sin su paso reportaría un número que nada
puede comparar.

### 6. El conjunto es una función de la semilla y de la tabla de pases, y de nada más

`monte_carlo_pass_key_volume` engendra un hijo de `RandomSource` **por pase**
(`spawn(P)`); el hijo sortea los desvanecimientos de ese pase para todas las
realizaciones en una llamada y, si se pide, sus cuentas de Poisson. La
evaluación de las cuentas entre ambos va por trozos de realizaciones y no
consume aleatoriedad, así que el tamaño del trozo no cambia ni un bit
(`TestReproducibility::test_the_chunk_size_does_not_change_a_bit`, trozos de
1 000 y 10⁸ elementos, igualdad exacta). El proceso se reinicia en cada pase:
la separación es de horas, `exp(−gap/τ)` está por debajo de `1e-15` para toda
`τ` menor que un treintaicincoavo de la separación, y cuando no lo está
(`τ = 1000 s` contra los 5 363 s de separación mínima del día de referencia,
`4.6e-3` de correlación descartada) el registro lo dice.

### 7. Las cuentas del bloque se sortean de Poisson, con los errores dentro de las detecciones por construcción

Con `sample_counts=True` (el defecto) cada recuento agrupado se sortea de una
Poisson con la esperanza como media, y cada recuento de errores de una binomial
sobre las detecciones sorteadas a la tasa esperada: el adelgazamiento de un
proceso de Poisson, que es exacto para un proceso de tasa constante a trozos —lo
que es un bloque de puertas con una transmitancia por muestra una vez fijada la
realización del desvanecimiento— y difiere de la verdad Bernoulli-por-puerta en
un factor `1 − Q` en la varianza, con `Q < 1e-3` en el enlace de referencia. El
presupuesto de pulsos no se sortea: el reloj de la fuente no es aleatorio.

### 8. Cuantiles de sumas, no sumas de cuantiles; y el `eps` compuesto viaja con el día

`monte_carlo_daily_key_volume` suma los pases de cada realización y toma los
cuantiles de esa suma. Sumar los P5 por pase supondría que todos los pases
tienen su mala noche la misma noche: en el día de referencia el P5 de la suma es
735 329 bits y la suma de los P5 724 553
(`TestComposingADay::test_the_p5_of_the_sum_exceeds_the_sum_of_the_p5s`). La
composición del `eps` sigue al ADR 0011 sin cambios: `4e-10` para cuatro
bloques.

### 9. El número de realizaciones sale de un criterio

El P5 es un estadístico de orden y su error estándar es
`sqrt(p(1−p)/R)/f(q_p)`; bajo una aproximación normal
`realisations_for_quantile` lo invierte:
`R = p(1−p)(dispersión/precisión)²/φ(z_p)²`. A 1 000 realizaciones el error
estándar *bootstrap* del P5 es el **0.22 % y el 0.16 %** de la mediana en los
dos pases vivos, la dispersión relativa es del 2.9 % y del 2.5 %, y la fórmula
dice que 37 realizaciones bastaban para un 1 % —de acuerdo con el bootstrap
dentro del 25 %, que es lo que vale la aproximación normal cerca del
acantilado, no en él (`TestTheRealisationCount`).

### 10. Una realización, bit a bit, es `pass_key_volume`

El agrupamiento por pase usa la misma suma ordenada por índice que
`key_volume.py` (`np.bincount`, no `ndarray.sum`, que es por pares), así que
una realización cuya transmitancia se reconstruye desde el mismo hijo de la
semilla y se pasa por `pass_key_volume` da **la misma clave hasta el último
bit**, y un factor exactamente 1 (`σ² = 0`, `γ = 1e8`, `τ → 0`) reproduce el
volumen a la transmitancia media exactamente
(`TestReproducesTheDeterministicVolume`). Es lo que hace que el conjunto sea
`pass_key_volume` aplicado a cada realización y no una segunda implementación
que pudiera diferir por otra cosa.

---

## Consecuencias

### Lo que ahora se puede afirmar

- **Clave por pase y por día como distribución** —P5/P50/P95, media,
  probabilidad de que un pase no dé nada— con el régimen finito, el `eps`
  compuesto y la semilla en el resultado. En el día de referencia, a 1 000
  realizaciones y `τ` = 2 ms / 20 ms, con las cuentas sorteadas: pase 1
  **329 229 / 345 658 / 361 865** bits, pase 3 **395 324 / 412 512 / 429 023**,
  día **735 329 / 758 314 / 782 391**; los pases 2 y 4 a cero en las mil
  realizaciones.
- **Que la cifra de diseño de hoy infrarreporta la mediana un 43 %**, y por qué:
  mantiene el cuantil del 1 % del desvanecimiento durante todo el pase.
- **Que los dos pases muertos lo están por otro mecanismo a la transmitancia
  media**: no por `φ = 0.5` sino porque la corrección de errores adelanta al
  término de un fotón por 2.2 y 8.7 veces (`φ` = 0.197 y 0.315); la mejor de
  mil realizaciones llega al 58 % y al 20 % de su propia fuga.
- **Que a la `τ` física la dispersión la fija contar, no el desvanecimiento**,
  por un factor de noventa, y dónde deja de ser así.
- **Estadística de duración de desvanecimientos** con su paso y su
  divergencia declarados.

### Lo que esto cuesta

- **Un `τ` que el usuario tiene que elegir.** Sin defecto, con dos ayudantes
  cinemáticos y una anchura de correlación declarada hueco.
- **Un segundo objeto de resultado para el día**, con las mismas columnas que
  `DailyKeyVolume` más los cuantiles. `engine/` lo rellena cuando `MonteCarloSpec`
  está presente.
- **0.86 s** por día a mil realizaciones (`TestRuntime`, 1.8 millones de
  evaluaciones del enlace y 4 000 bloques), vectorizado por trozos y sin
  paralelismo.

### Lo que queda explícitamente fuera

- **Un espectro de centelleo medido.** Un proceso de Ornstein-Uhlenbeck tiene
  espectro lorentziano; un espectro con cola `−8/3` es un proceso de dos
  parámetros, y una fuente para ellos en un enlace LEO es un hueco.
- **Turbulencia no gaussiana.** El log-normal es el modelo de fluctuación débil
  al que el canal ya se compromete; la advertencia de `turbulence.py` a `σ² > 1`
  aplica sin cambios.
- **Nubes**, `system/pcflos.py`; **varias estaciones y relés**,
  `system/multi_ogs.py` y `system/relay.py`.
- **La correlación entre pases.** Se reinicia el proceso; el registro avisa
  cuando la `τ` no es corta contra la separación.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Un sorteo i.i.d. por muestra de la rejilla** | Sobreestima la fluctuación del recuento agrupado en `sqrt(1/w)`, entre 10 y 22 veces en el pase 1 a los tiempos físicos, y reporta una banda que no existe. `sample_fade_factors` avisa cuando se le piden factores instantáneos en una rejilla más gruesa que catorce tiempos de correlación |
| **Sub-muestrear cada permanencia a `τ/4`** | 7·10⁹ sorteos para un día a mil realizaciones. La integral del proceso sobre la ventana tiene forma cerrada conjunta con su extremo, y es exacta |
| **Encoger en el dominio gaussiano (`exp(σ sqrt(w) x − σ²w/2)`)** | Preserva la media para el centelleo pero no para el apuntado, cuya media la fija la *dispersión* del desplazamiento y no puede reducirse sin moverla. Una regla única —encoger el factor hacia su media marginal— tiene la media exacta en los dos componentes y la varianza a primer orden en ambos |
| **Encoger los extremos del proceso en vez de su integral** | Correlación entre ventanas consecutivas hasta un 20 % baja a `T ≈ τ` a nivel de pase; con la integral muestreada exactamente el residuo del producto queda bajo el 1.5 % |
| **Tiempos de correlación por defecto (2 ms, 20 ms)** | Son estimaciones de orden de magnitud por la hipótesis de Taylor con una anchura no publicada. Un defecto los vestiría de valor publicado, contra el ADR 0009 |
| **Una tasa de cruces en tiempo continuo (Rice)** | Diverge para un proceso de Ornstein-Uhlenbeck; medido, el recuento por segundo crece como `Δt^{−1/2}`. Se reporta el recuento por paso con su paso, comprobado contra la binormal exacta |
| **Sortear detecciones y errores de Poisson independientes** | Permitiría más errores que detecciones. Poisson sobre las detecciones y binomial sobre los errores es el adelgazamiento exacto |
| **Engendrar un hijo del generador por trozo de realizaciones** | Cambiar el tamaño del trozo cambiaría el conjunto. Un hijo por pase, con los sorteos antes de la evaluación por trozos, hace el resultado función de la semilla y de la tabla de pases |
| **Sumar los P5 por pase para el día** | Es una cota inferior suelta: supone que todos los pases tienen su mala noche la misma noche. Medido, 724 553 contra 735 329 |
| **`ndarray.sum` para agrupar el bloque** | Suma por pares; `key_volume.py` suma por índice con `bincount`. Con la misma suma una realización reproduce `pass_key_volume` bit a bit, y el test afirma igualdad, no cercanía |

---

## Verificación

- `tests/system/test_correlated_fading.py` y `tests/system/test_monte_carlo.py`:
  83 tests más 15 doctests, **100 % de cobertura de líneas y de ramas** en los
  dos módulos. Ninguno supera los 3 s; el conjunto corre en 24 s.
- **V1**: coeficientes AR(1) en `[0, 1]` con cero delante (hypothesis, 200
  casos), reducción de varianza en `(0, 1]` y monótona (hypothesis, 300 casos),
  cuantiles ordenados y probabilidades acotadas por construcción, factores no
  negativos y apuntado en `[0, 1]`, reproducción bit a bit de
  `pass_key_volume`.
- **V3**: `pointing.py` (media, cuantil del 1 %, ley de outage a tres niveles)
  y `link_budget.py` (cuantil del 1 % del centelleo en dB) con un millón de
  sorteos y tolerancias derivadas del error estándar de cada estimador;
  autocorrelación `exp(−kΔt/τ)` dentro del error de su estimador; la reducción
  de varianza y la construcción promediada contra fuerza bruta en rejilla fina;
  cruces por paso contra la binormal de SciPy.
- Las cifras de esta página están todas en un test que corre, con el nombre del
  test al lado.

## Referencias

- A. Ntanos et al., «LEO Satellites Constellation-to-Ground QKD Links: Greek
  Quantum Communication Infrastructure Paradigm», *Photonics* **8**(12):544
  (2021), Ec. (18): la normalización log-normal del centelleo que se conserva.
- A. A. Farid y S. Hranilovic, «Outage Capacity Optimization for Free-Space
  Optical Links With Pointing Errors», *J. Lightwave Technol.* **25**(7):1702
  (2007), Ecs. (9)–(11): el jitter gaussiano de dos ejes del que sale el factor
  de apuntado. Las dos abiertas, según el ADR 0009.
- G. I. Taylor (1938), la hipótesis de turbulencia congelada: **no abierta**
  para este proyecto; solo se usa la afirmación cinemática `τ = ℓ/v`, derivada
  en `taylor_correlation_time_s` en vez de citada.
- [ADR 0011](0011-the-block-is-the-pass.md) (el bloque es el pase; las dos
  reservas que este ADR cierra), [ADR 0009](0009-citation-policy.md) (por qué
  `τ` es un parámetro), [ADR 0010](0010-decoy-and-finite-key.md) (la cota que
  cada realización evalúa).

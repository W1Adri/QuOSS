# ADR 0011 — El bloque es el pase: la cota finita pasa a ser el defecto, y la máscara de elevación resulta ser una variable de diseño

- **Estado:** aceptada
- **Fecha:** 2026-09-13
- **Etapa:** 3 (`system/passes.py`, `system/key_volume.py`)
- **Afecta a:** todo número que este proyecto vaya a publicar como «clave por
  pase» o «clave por día», y por tanto a `engine/`, `viz/` y al entregable DB3.
- **Cierra** la decisión que el [ADR 0010](0010-decoy-and-finite-key.md) dejó
  explícitamente aplazada («quien posee un pase —y por tanto un bloque— es
  `system/key_volume.py`») y la frase equivalente del docstring de
  `quoss/qkd/__init__.py`.
- **Extiende** al [ADR 0009](0009-citation-policy.md): la transmitancia cenital
  sigue siendo un hueco declarado, así que las cifras de abajo son una cota
  superior sobre la atmósfera y una afirmación exacta sobre todo lo demás.

---

## Contexto

### Qué se estaba decidiendo, en una frase

Un pase LEO dura unos minutos. El [ADR 0010](0010-decoy-and-finite-key.md) dejó
implementada la cota finite-key de Lim et al. 2014, que convierte **un bloque de
cuentas acumuladas** en **un número de bits**. Lo que faltaba era decir qué es el
bloque, y eso no es una pregunta de criptografía: es una pregunta sobre el eje
temporal. Esta etapa la contesta, y al contestarla tiene que fijar tres cosas que
no son obvias: **qué cuenta como pase**, **cómo se integra sobre él**, y **qué
afirmación de seguridad sobrevive a sumar varios**.

### Por qué no era una multiplicación

Porque la cota finita **no es aditiva sobre sub-bloques**, y el error de suponer
que lo es no es pequeño: es total. Medido en
`tests/system/test_key_volume.py::TestTheBlockIsThePass`, con el día de
referencia (estación de Castelldefels, telescopio de 0.75 m, satélite SSO a 700
km, noche clara sin luna, reparto 16:1:4 de Ntanos et al., `eps = 1e-10`, máscara
de 10°, rejilla de 1 s):

| Qué se toma como bloque | Clave del día |
|---|---|
| **Una muestra de la rejilla** (1800 bloques) | **0 bits**, y cero de 1800 muestras certifica un solo bit |
| **Un pase** (4 bloques) | **432 985 bits** |

Cada muestra tiene una mediana de **1615** detecciones en la base de clave —469 en
la peor, 8917 en la mejor—, contra un peaje
fijo de 260 bits (`SecurityParameters.penalty_bits`) y una inferencia de error de
fase que no tiene con qué trabajar. Tratar la cota finita como una corrección por
instante —que es lo que haría un `regime=FINITE` en `QkdProtocol`— pierde el día
entero.

---

## Decisión

### 1. El bloque es el pase. No la muestra, y no el día

**Un pase, un bloque, una longitud de clave.** Las cuentas de las muestras de un
pase se suman (una suma de segmentos, porque una cuenta es una cuenta) y la Ec.
(1) de Lim et al. se evalúa una vez por pase.

- **Contra la muestra:** medido arriba, cero bits.
- **Contra el día:** agrupar los cuatro pases en un bloque es la tentación
  opuesta —un bloque mayor paga el peaje fijo una vez y tiene estadística más
  apretada— y es igual de incorrecta. Entre dos pases el satélite está bajo el
  horizonte y **no se envía ningún pulso**: no es un bloque, son dos ejecuciones
  del protocolo separadas por horas. Y en concreto mezclaría las tasas de error:
  los dos pases bajos aportan 787 000 detecciones al 1.8–1.9 % de QBER a un
  bloque cuyos pases buenos están al 1.24–1.26 %, y la corrección de errores se cobra
  sobre todas. `key_volume.py` no ofrece esa función, y `daily_key_volume` suma
  **longitudes**, que es la operación que la componibilidad sí autoriza.

### 2. La cota finita es el defecto, y lo es **estructuralmente**

`pass_key_volume` —el nombre sin adjetivos, el que se escribe por inercia—
devuelve `KeyRegime.FINITE`. El número asintótico solo se alcanza llamando a
`asymptotic_pass_key_volume`, y **no existe ningún argumento `regime=`**.

**Por qué no un argumento con defecto.** Un defecto es un valor que alguien pasa
distinto por descuido, y el descuido aquí no tiene síntoma: las dos llamadas
devuelven un número de bits positivo y plausible. Lo que mide la diferencia, en
el día de referencia:

| Pase | Asintótico | Finito | Culminación |
|---|---|---|---|
| 1 | 1 548 341 bits | **190 581** bits | 52.9° |
| 2 | 319 898 bits | **0** bits | 17.6° |
| 3 | 1 709 160 bits | **242 404** bits | 58.8° |
| 4 | 199 281 bits | **0** bits | 14.2° |
| Día | 3 776 681 bits | **432 985** bits | — |

El cociente del día es **11.5 %**, y no es lo importante. Lo importante es la
columna por pase: **dos de los cuatro pases no certifican nada**, así que el
error de reportar la cifra asintótica no es «unas ocho veces optimista», es
**ilimitado** justo en los pases bajos que un planificador estaría decidiendo si
vale la pena agendar.

**Y muere de golpe, no poco a poco**, que es la parte contraintuitiva. El pase 4
recoge 309 867 detecciones en la base de clave —no es un número pequeño—. Lo que
lo mata es la **tasa de error de fase**: la inferencia desde la base medida hacia
la conjugada devuelve `phi = 0.5`, el máximo posible, donde `1 − h(phi) = 0` y el
término de un fotón se anula entero, mientras la corrección de errores sigue
cobrándose sobre los 309 867 bits. No hay un régimen de «poca clave»; hay un
acantilado, y `FiniteKeyResult.phase_error_rate` es el campo que dice cuál.

### 3. Las dos regímenes comparten **una** cuadratura y **un** objeto de configuración

Una comparación entre dos números no vale nada si difieren en algo más que en lo
que se compara. Dos precauciones hacen que la tabla de arriba mida la cota y nada
más.

- **Un vector de pesos.** Los dos caminos integran sobre los tiempos de
  permanencia de `PassTable.samples()`. El asintótico multiplica la tasa por
  segundo por ellos; el finito multiplica la tasa de pulsos por ellos para
  repartir el presupuesto de pulsos del bloque. Ninguno tiene regla de cuadratura
  propia, así que ninguno puede ir por delante por una razón que no sea la cota.
- **Un objeto de configuración.** Los dos toman el mismo `Bb84DecoyProtocol`, y
  `decoy_settings_from_protocol` deriva de él el `DecoySettings` que el camino
  finito necesita. La alternativa —dos objetos— permitiría que los dos caminos
  describieran experimentos distintos, y el fallo no tiene síntoma: la
  comparación sigue dando un cociente, y el cociente está mal por aquello en lo
  que las dos configuraciones discrepaban. `tests/system/test_key_volume.py::
  TestOneQuadratureAndOneConfiguration::test_changing_the_intensity_moves_both_regimes`
  comprueba que el puente es portante y no decorativo.

La única pieza que el protocolo asintótico no lleva es la tercera intensidad,
porque su estado de vacío es un pulso exactamente vacío; `mu_3 = 0` se suministra
aquí y se documenta en `_VACUUM_INTENSITY`. La cota de Lim et al. admite
`mu_3 >= 0`, que es estrictamente más general; una ejecución con tercera
intensidad no nula construye su `DecoySettings` directamente y no tiene
contraparte asintótica en este paquete con la que compararse.

### 4. La regla de cuadratura es la del punto medio, recortada a los cruces
refinados

Un pase empieza cuando la elevación cruza la máscara, y ese instante cae **entre
dos muestras**. Tomar la primera muestra por encima de la máscara como inicio
tira la fracción de paso anterior, en los dos extremos: en el día de referencia,
1796.00 s en vez de 1799.79 s, **3.79 s o el 0.21 % simplemente ausentes**.
`find_passes` refina los dos cruces por interpolación lineal en elevación —que es
la forma correcta de aproximación aquí, porque la elevación frente al tiempo es
lo más lineal que será justo en el horizonte, donde cambia más rápido— y
`PassTable.samples()` devuelve un **tiempo de permanencia por muestra** bajo la
regla del punto medio recortada a `[start_s, end_s]`.

**Por qué el punto medio y no el trapecio.** Las dos son de segundo orden, así
que la precisión no decide. Deciden otras dos cosas:

1. **El trapecio no puede representar los cruces refinados.** Sus pesos se
   construyen desde las muestras, así que integra sobre `[t_first, t_last]` y no
   hay forma de decirle que el pase empezó 0.4 s antes.
2. **Estos pesos se multiplican por una tasa de pulsos para dar un recuento de
   pulsos.** Un peso es entonces «cuántos pulsos se emitieron mientras el enlace
   lo describía mejor esta muestra», una cantidad física que tiene que ser
   positiva y sumar exactamente los pulsos que el pase emitió. El punto medio lo
   da por construcción; los pesos de borde del trapecio son medios pasos
   independientemente de dónde acabe el pase.

Lo que cuesta el recorte, medido: los 3.79 s recuperados son el 0.21 % del tiempo
y solo el **0.032 %** de los bits, porque son los segundos de menor elevación del
pase. Vale la pena decir la cifra pequeña además de la grande: el refinamiento se
hace porque es exacto y gratis, no porque cambie el resultado.

### 5. La máscara de elevación es una **variable de diseño con óptimo interior**,
y por eso no tiene defecto

`find_passes` exige `minimum_elevation_rad` sin defecto. La razón no es
bibliográfica: barriendo la máscara sobre el día de referencia,

| Máscara | Pases | Día finito | Día asintótico |
|---|---|---|---|
| 2° | 6 | 408 946 | 3 876 492 |
| 5° | 5 | 426 988 | 3 876 492 |
| 7° | 4 | 433 771 | 3 862 432 |
| **8°** | 4 | **434 938** | 3 844 682 |
| 10° | 4 | 432 985 | 3 776 681 |
| 20° | 2 | 360 978 | 2 949 471 |

**La columna asintótica es monótona y la finita no.** La clave asintótica por
pulso está recortada a cero muestra a muestra, así que añadir una muestra mala a
un pase nunca puede restar clave — por debajo de 5° las muestras extra aportan
**exactamente cero** y la columna deja de moverse. Una cota a nivel de bloque no
tiene esa protección: las muestras de baja elevación de los bordes de un pase
meten sus errores en el bloque agrupado, donde la corrección de errores se cobra
sobre **todas** las detecciones, aportando casi ningún evento certificado de un
fotón. Bajar la máscara de 8° a 2° compra un **71 % más** de segundos útiles y
**destruye el 6.0 %** de la clave del día, y el cálculo asintótico no puede verlo
ocurrir.

El mecanismo, medido sobre un solo pase al pasar de 10° a 5°: sus eventos
certificados de un fotón suben un **2.6 %** (718 970 → 737 975) y su fuga de
corrección de errores sube un **5.5 %** (246 574 → 260 144). La segunda adelanta
a la primera. Es la misma familia de hallazgo que el óptimo de la fracción decoy
del [ADR 0010](0010-decoy-and-finite-key.md): una cantidad a la que la fórmula
asintótica es indiferente tiene un óptimo real en cuanto el bloque es finito.

Una máscara constante en el código habría escondido un efecto del 6 %.

### 6. Sumar un día compone las probabilidades de fallo, y eso se reporta

Cada pase es un bloque independiente, `eps_sec`-secreto y `eps_cor`-correcto **por
su cuenta**. Concatenar `n` claves así da una clave cuya probabilidad de fallo
está acotada por la unión: **`n · eps`, no `eps`**. `composed_security` lo calcula
y `DailyKeyVolume.security` lo lleva, de modo que la clave de un día no viaja
nunca sin el `eps` bajo el que de verdad es segura.

Con cuatro pases a `1e-10` eso es un inofensivo `4e-10`. Es inofensivo y es **un
número distinto del que se imprime al lado**, y crece con exactamente la cantidad
que una misión intenta maximizar: cien pases de una constelación son `1e-8`, un
año de cuatro pases diarios es `1.5e-7`.

Y la otra dirección también se tasa: para que el **día** sea `eps`-seguro en vez
de cada pase, cada bloque tiene que correr a `eps / n`. Medido en el día de
referencia a `eps = 1e-10` y cuatro pases: 404 780 bits en vez de 432 985, o sea
que un día honestamente `1e-10`-seguro cuesta el **6.5 %** de la clave. Barato, no
nulo, y nada que nadie fuera a encontrar leyendo una gráfica de tasa.

`composed_security` **se niega** a devolver una composición vacua: `n · eps >= 1`
no es una probabilidad de fallo, es la ausencia de afirmación, y devolverla como
número sería exactamente el `except: pass` que el README prohíbe.

### 7. Una rejilla gruesa **infla** la clave, así que el guardia cuenta muestras

Integrando el día de referencia con rejillas progresivamente más gruesas, contra
las 432 985 bits de la de 1 s:

| Paso | Muestras en el pase más corto | Sesgo |
|---|---|---|
| 1 s | 303 | 0.0000 % |
| 10 s | 30 | +0.026 % |
| 25 s | 12 | +0.120 % |
| 45 s | 7 | **+1.319 %** |
| 60 s | 5 | **+2.018 %** |
| 120 s | 2 | **+8.586 %** |

Dos cosas de esa tabla. **El signo es positivo**: quien engrosa la rejilla para
ahorrar tiempo recibe una clave *mayor*, que es el modo de fallo
«plausible-y-equivocado» que este proyecto existe para rechazar. Y el sesgo **no
es monótono** en el paso: depende de dónde caigan las muestras respecto a la
culminación, así que 48 s aterriza en +0.003 % por accidente entre vecinos a
+1.3 % y +2.0 %.

Por eso `MINIMUM_SAMPLES_PER_PASS = 12` guarda el **recuento de muestras** y no
una estimación de error: una estimación de error calculada desde una sola
ejecución gruesa puede ser pequeña por coincidencia, y «este pase tiene cuatro
muestras» no puede.

### 8. Un pase cortado por el borde de la rejilla se marca, no se reporta como
pase corto

Si el satélite ya está por encima de la máscara en la primera muestra, o sigue
por encima en la última, lo que la rejilla contiene es un **fragmento**: su
duración, su culminación y todo bit integrado sobre él son cotas inferiores, y
nada en los números lo dice. `PassTable.truncated_start` y `truncated_end` lo
dicen, y `find_passes` registra un `warning` con cuántos encontró. Medido: el
fragmento del pase 1 de la ventana de prueba es menos del 80 % del pase real.

### 9. La culminación se refina con una parábola de tres puntos, escrita para
espaciado desigual

La elevación máxima de un pase fija su rango mínimo y por tanto su mejor
transmitancia, así que es el número que un planificador lee primero, y leerlo de
las muestras lo sesga **a la baja** como el cuadrado del paso. Medido: en una
rejilla de 10 s el máximo discreto del mejor pase queda **0.029°** por debajo de
la verdad, y en una de 30 s **0.51°**. El vértice de la parábola que pasa por la
muestra máxima y sus dos vecinas los reduce a **0.0006°** y **0.081°**.

Está escrito en forma de Newton, válida para espaciado **desigual**, porque
`TimeGrid` admite rejillas no uniformes y la fórmula de paso constante sería ahí
incorrecta de una forma que parece un pequeño error de modelado en vez de un bug.

El ajuste se acepta solo si `b_2 < 0`, si el máximo del pase lo alcanza **una
sola** muestra, y si el vértice cae dentro del corchete de tres puntos y de la
ventana refinada. La condición del empate no es relleno defensivo: por
`(20, 30, 30)` el vértice vale **31.25**, una elevación que ninguna muestra vio.
Un máximo alcanzado en más de una muestra es una meseta a la resolución de la
rejilla, y entonces la muestra se queda — que es honesto y además el sentido
conservador.

### 10. `system/` no calcula el canal

`pass_key_volume` recibe un `LinkConditions` ya evaluado en los instantes que
`PassTable.samples()` lista, en ese orden. No toma ni una sola perilla óptica.

**Por qué.** Lo contrario pondría doce argumentos de presupuesto óptico en esta
firma y haría que `quoss.system` dependiera de cada perilla de `quoss.channel`,
rompiendo el `core ← física ← system` de la
[regla de oro del orden](../../notes/ROADMAP.md). El contrato se comprueba por
longitud, y el docstring dice explícitamente que el **orden** es parte del
contrato y no una convención: una longitud correcta en otro orden atribuiría cada
transmitancia al instante equivocado y nada aguas abajo podría notarlo.

`passes.py` va más lejos y no importa nada de `channel` ni de `qkd` en absoluto,
comprobado sobre el AST en
`tests/system/test_passes.py::TestTheModuleSurface::test_it_imports_nothing_from_channel_or_qkd`.

---

## Consecuencias

### Lo que ahora se puede afirmar

- **Clave por pase y clave por día con la cota finite-key aplicada al bloque
  correcto**, que es la respuesta que DB3 pide, con el régimen en un campo del
  resultado y la probabilidad de fallo compuesta del día en otro.
- **Qué pases no dan clave**, que es la salida más informativa del módulo y la
  que ningún cálculo asintótico produce.
- **Que la máscara de elevación tiene un óptimo**, con su mecanismo medido.

### Lo que esto cuesta

- **Un `PassSamples` plano en vez de un contenedor por pase.** Los pases tienen
  longitudes distintas, así que la forma `(n_pases, n_muestras)` no existe. El
  precio es que el llamante indexa con dos arrays en vez de con un bucle; la
  ganancia es que un día entero de canal y protocolo se evalúa en **una** llamada
  vectorizada y se colapsa con una suma de segmentos, sin ningún bucle sobre
  pases.
- **El llamante evalúa el canal.** Ver la decisión 10: es deliberado, y el
  contrato está comprobado por forma.

### Lo que queda explícitamente fuera

- **La dispersión entre pases.** Todas las cuentas vienen de
  `expected_block_counts`, que devuelve **esperanzas**: la cota tasa la
  incertidumbre de estimación que queda aunque las cuentas caigan justo en su
  media. Cuánto se mueve la respuesta cuando no lo hacen es
  `system/monte_carlo.py`, y hasta que exista estas cifras son la clave que
  certifica un pase **típico**, sin P5/P95.
- **El fading correlacionado en el tiempo.** `channel/link_budget.py` dice con
  todas las letras que hasta que exista `system/correlated_fading.py` «ninguna
  afirmación de ese módulo sobre clave *por pase* se sigue de una sobre clave
  *por puerta*». Este módulo hace exactamente esa afirmación, así que la reserva
  **se traslada aquí y se repite en su docstring** en vez de desaparecer: estas
  cifras suponen que la estadística de desvanecimiento de un pase es la marginal.
- **Las nubes.** `system/pcflos.py`. Multiplicar un volumen de clave por una
  probabilidad de cielo claro convertiría «funciona el 70 % de las noches» en
  «entrega el 70 % de la clave cada noche», que son sistemas distintos.
- **La optimización de parámetros.** Intensidades, reparto decoy, sesgo de base y
  máscara tienen óptimos que se mueven con el bloque, y dos de ellos están
  medidos arriba. Barrer ese espacio es `engine/sweep.py`.
- **Varias estaciones y relés.** `system/multi_ogs.py`, `system/relay.py`.
- **Refinar la rejilla alrededor de un pase.** `notes/LAST_CHANGES.md` dejó la
  pregunta abierta. La respuesta de esta etapa: se refinan los **bordes** y la
  **culminación** desde las muestras que existen, y nunca se fabrica un vector de
  estado. Quien necesite resolución fina dentro del pase pide una rejilla más
  fina —que `TimeGrid` admite no uniforme—, que es una segunda propagación y no
  un caso especial aquí.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Un argumento `regime=KeyRegime.FINITE` en una sola función** | Un defecto es un valor que alguien pasa distinto por descuido, y aquí el descuido no tiene síntoma: las dos ramas devuelven bits positivos y plausibles, con un factor 8.7 y dos pases de diferencia. Dos nombres hacen que elegir sea una edición visible |
| **Un bloque por muestra, tratando la cota finita como corrección por instante** | Medido: **0 bits** del día entero, cero de 1800 muestras. La cota no es aditiva sobre sub-bloques |
| **Un bloque por día** | Entre pases no se envía ningún pulso, así que no es un bloque sino varias ejecuciones; y mezclaría el QBER del 1.8–1.9 % de los pases muertos con el 1.24–1.26 % de los buenos en una corrección de errores que se cobra sobre todo |
| **Pesos trapezoidales sobre las muestras crudas** | No puede representar los cruces refinados (tira 3.79 s, el 0.21 % del día) y sus pesos de borde no suman los pulsos que el pase emitió, que es lo que el presupuesto de pulsos del bloque necesita |
| **Una máscara de elevación por defecto (20°, la de Ntanos et al.)** | Tiene óptimo interior cerca de 8° y la diferencia vale el 6 % del día. Un defecto habría escondido un efecto medible |
| **Calcular el presupuesto de enlace dentro de `key_volume.py`** | Doce argumentos ópticos en esta firma y `quoss.system` dependiendo de cada perilla de `quoss.channel`, contra el orden de dependencias de la guía |
| **Reportar `eps` por día igual al `eps` por bloque** | Es lo que hace casi toda la literatura y es falso por un factor `n`. Pequeño hoy, y creciente con exactamente lo que una misión maximiza |
| **Un `eps` compuesto por fila en `DailyKeyVolume`** | Un lector que sumara la columna lo compondría una segunda vez a mano, y mal. Una sola afirmación, la más débil de la tabla, es la única verdadera de todas las filas |
| **Estimar el error de cuadratura en vez de contar muestras** | El sesgo no es monótono en el paso: 48 s da +0.003 % por accidente entre vecinos a +1.3 % y +2.0 %. Una estimación desde una sola ejecución gruesa puede ser pequeña por coincidencia |
| **Interpolar la trayectoria para refinar dentro del pase** | `Trajectory` no interpola por diseño, y fabricar estados intermedios inventaría geometría. Los bordes y la culminación se refinan **en elevación**, que es el dato que sí está |
| **Filtrar pases por umbral de clave dentro de `passes.py`** | Los pases sin clave son la salida más interesante de `key_volume.py`; esconderlos en la segmentación los haría invisibles |

---

## Referencias

- C. C. W. Lim, M. Curty, N. Walenta, F. Xu, H. Zbinden, «Concise security bounds
  for practical decoy-state quantum key distribution», *Phys. Rev. A* **89**,
  022307 (2014). Ec. (1) es la cota de bloque sobre la que descansa todo número
  de esta etapa; `quoss.qkd.finite_key` la implementa y esta etapa decide qué es
  el bloque.
- A. Ntanos et al., «LEO Satellites Constellation-to-Ground QKD Links: Greek
  Quantum Communication Infrastructure Paradigm», *Photonics* **8**(12):544
  (2021), §4.1: los parámetros del enlace de referencia y el suelo de elevación
  de 20° que esta etapa mide como no óptimo para la cota finita.
- [ADR 0010](0010-decoy-and-finite-key.md) (las dos afirmaciones de clave y la
  decisión aplazada que este ADR cierra),
  [ADR 0009](0009-citation-policy.md) (política de citas; la transmitancia
  cenital sigue siendo un hueco declarado),
  [ADR 0001](0001-unit-conventions.md) (por qué las conversiones de ángulo de
  estos módulos pasan por `core/units.py`).

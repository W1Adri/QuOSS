# Archivo de `LAST_CHANGES.md` — §25 a §36

> **Qué es esto.** Entradas de la bitácora del proyecto, **íntegras y sin
> editar**, sacadas del camino de lectura obligatorio y no borradas. Están aquí
> porque `notes/LAST_CHANGES.md` llegó a 6 834 líneas y CLAUDE.md manda leerlo al
> empezar cada sesión: una bitácora que no cabe en la sesión que la tiene que
> leer deja de ser una bitácora y pasa a ser un archivo, y el efecto medido es
> que las sesiones leen las primeras pantallas y se saltan las entradas que
> describen el árbol de hoy.
>
> **La regla por la que una entrada llega aquí**, y no es «lo viejo fuera»: una
> entrada se archiva cuando **todo lo que carga peso en ella vive ya en otro
> sitio que se lee de verdad** — un ADR, un test, o un docstring. Si no, se
> migra primero y se archiva después. La comprobación que lo respalda está en
> `LAST_CHANGES.md` §41: de los **823 números distintos** de §1 a §35, **765 ya
> vivían** en `docs/adr/`, `src/` o `tests/`, y los 58 restantes se clasificaron
> uno a uno.
>
> **Lo que sigue valiendo de leer esto:** la prosa de *por qué* se decidió algo,
> y sobre todo las entradas que cuentan un error y su corrección. Un ADR dice lo
> que se decidió; estas entradas dicen qué se creía antes y qué lo cambió.
>
> Índice de una línea por entrada, con su cifra: [`../LAST_CHANGES.md`](../LAST_CHANGES.md).

---

**Cierre de 2.3, la etapa 3 (`system/`) entera, y las etapas 4, 5 y 6 (`scenario/`, `engine/`, `io/`), más tres entradas de corrección. 2026-09-12 a 2026-09-15.**

---

## 25. `qkd/finite_key.py` — de una tasa a una longitud, y por qué no es lo mismo

### Qué hace este módulo, para quien llegue nuevo

`bb84.py` contesta «qué fracción de los pulsos se convierte en clave» suponiendo
que Alice y Bob tuvieran tiempo infinito. Este contesta la pregunta que plantea
un pase de verdad: *tuvieron once minutos y 6.6e10 pulsos — cuántos bits de clave
pueden reclamar, y con qué probabilidad la reclamación es falsa*.

**Por qué «finito» cambia algo, y no un poco.** Todos los números de la tasa
asintótica son probabilidades, y Alice y Bob nunca observan una probabilidad:
observan un recuento. 412 detecciones de 3.7e8 pulsos a la intensidad decoy. Un
recuento dividido por los intentos es una **estimación**, y una estimación puede
tener mala suerte. La cota decoy se construye restando una ganancia medida de
otra, así que una fluctuación del signo equivocado en cualquiera de las dos hace
que el rendimiento de un fotón certificado salga **demasiado alto** — y un
rendimiento certificado de más es clave que Eve conoce en parte. El análisis
finite-key sustituye cada recuento por el peor valor compatible con él a una
confianza declarada, y pone precio a la diferencia.

**Qué quiere decir «componible», que es la palabra que carga el peso.** Una clave
no es «segura» o «insegura»: es `epsilon`-segura, o sea que se separa de una
clave ideal —uniforme y desconocida para Eve— como mucho `epsilon` en una
distancia que se **compone bien**. Eso último es lo que importa: garantiza que
usar la clave dentro de otro protocolo —cifrar con ella, autenticar con ella—
degrada la seguridad de ese protocolo como mucho otro `epsilon`. Una cota no
componible puede ser perfectamente cierta y no decir nada sobre el sistema donde
la clave se usa.

**Y qué es el error de fase, que no es el QBER.** La amplificación de privacidad
cobra por lo que Eve sabe, y lo que Eve sabe está acotado por la tasa de error
que Alice y Bob **habrían visto** si hubieran medido en la base conjugada. No la
midieron: esos bits fueron clave. Así que hay que inferirla desde la base que sí
midieron, y la inferencia es un argumento de muestreo con su propia probabilidad
de fallo — el término `gamma`. Son dos tasas de error distintas en dos términos
distintos de la misma ecuación, y en el bloque de referencia valen **1.06 %** y
**8.85 %**: confundirlas infla el término de un fotón por **1.609**, sin que nada
aguas abajo pueda notarlo.

### La decisión de esta entrada: Lim et al. 2014, no Tomamichel et al. 2012

El roadmap escribió «finite-key componible (Tomamichel)» antes de que existiera
`bb84.py`. Lo que hay hoy es un protocolo de **pulsos coherentes débiles con
decoy**, y eso manda: Tomamichel, Lim, Gisin y Renner (*Nature Communications*
3:634, 2012) analizan BB84 con **fuente de un fotón**, y aplicarlo aquí exigiría
una fuente que este proyecto no modela o un argumento de *tagging* encima que
nadie ha publicado en esa combinación. Lim, Curty, Walenta, Xu y Zbinden (*PRA*
89, 022307, 2014) analizan exactamente el protocolo que hay, en cinco ecuaciones,
y su análisis de secreto **está construido sobre** la relación de incertidumbre
entrópica de Tomamichel y Renner. Elegir Lim no es apartarse de Tomamichel: es
usar el resultado que aplica su técnica a nuestro protocolo.

### Por qué no es «la asintótica por un factor de corrección»

Tres razones, cada una medida:

1. **Hay un coste fijo por bloque.** La Ec. (1) resta
   `6 log2(21/eps_sec) + log2(2/eps_cor)` bits **una vez**: **260** con
   `eps_sec = eps_cor = 1e-10` (225.7 + 34.2). Despreciable frente a un pase,
   decisivo frente a una demostración de unos cientos de bits, y sin traducción
   posible a una tasa.
2. **La desviación estadística es una sola para las tres intensidades.** Hoeffding
   acota el **reparto del bloque entero** entre ellas, así que la misma `delta`
   absoluta le toca a la intensidad rara y a la común — y tras el `1/p_k` que
   convierte cuentas en cantidad por pulso, la relativa de la rara es 21 veces
   mayor. En el bloque de referencia eso se ve crudo: el estado decoy registró
   **230** errores en la base de comprobación y la desviación compartida es
   **458**, o sea el doble que lo que mide. La cota de errores de un fotón sale
   entonces en **39 630** donde la base registró **16 088** errores de todo tipo.
   Una cota superior por encima del total sigue siendo una cota superior; lo que
   dice es que esa configuración no certifica casi nada sobre de dónde vinieron
   los errores.
3. **El protocolo no es el mismo.** Base sesgada, clave de las **tres**
   intensidades, error estimado en la **otra** base, y `mu_3 >= 0` en vez de
   vacío exacto. Comparar término a término es comparar dos protocolos.

### El crédito de vacío: ruido que hace clave, y cuánto vale de verdad

La Ec. (1) suma `s_{X,0}` —las detecciones en puertas donde Alice no envió nada—
**entera**, sin cobrarle amplificación de privacidad. Es correcto: un clic en una
puerta vacía lo decidió el detector, no el canal, así que Eve no sabe nada del bit
que Bob apuntó. Suena a truco, así que se midió, con 1e12 pulsos:

| Ruido (cuentas/puerta) | `s_0` | Clave | Aporte de `s_0` |
|---|---|---|---|
| 7.9e-07 (noche) | **0** | 5.47e+07 bits | 0 % |
| 1e-05 | 1.51e+06 | 4.58e+07 bits | **3.3 %** |
| 1e-04 | 1.65e+07 | **0** | — |

De noche no se certifica ninguno: hay **37 522** detecciones de vacío y la
desviación es **44 399**, así que están dentro del ruido del reparto. Y de 1e-04
en adelante el término crece pero la clave ya es cero, porque la corrección de
errores se cobra sobre **todo** el bloque y el QBER que producen esas mismas
cuentas oscuras se la comió antes. El crédito es real, es pequeño y **nunca
rescata** un enlace ruidoso.

### El hallazgo que solo este módulo puede ver

`Bb84DecoyProtocol.protocol_efficiency` dice que los pulsos decoy son coste puro y
que su fracción óptima es cero. Es cierto —y es cierto **solo asintóticamente**.
Barriendo la fracción decoy con la de vacío fija en 5 %:

| Fracción decoy | Clave/pulso a 1e20 | Clave/pulso a 1e10 |
|---|---|---|
| 0.05 | **7.11e-05** | 0 |
| 0.10 | 6.85e-05 | 6.26e-06 |
| 0.50 | 4.77e-05 | **2.12e-05** |
| 0.90 | 2.70e-05 | 1.69e-05 |

Asintóticamente cae de forma monótona; con un bloque de pase tiene **máximo
interior cerca del 50 %**, y gastar medio pase en decoys vale un factor **3.4**
sobre gastar una décima. Ese óptimo es invisible desde `bb84.py`, porque la
cantidad que `bb84.py` optimiza no depende de la fracción decoy en absoluto.

Un segundo efecto de la misma familia, y también contraintuitivo: apretar
`eps_sec` cinco décadas engorda `delta` solo un **20 %** —lleva
`sqrt(ln(21/eps_sec))`— pero cuesta el **72 %** de la clave del bloque de
referencia, porque un 20 % más de desviación mueve la tasa de error de fase de
5.4 % a 12.1 %, que es media curva de `h`. Barato en la desviación, caro en la
clave.

### La verificación: dos papeles, dos transcripciones, un número

La comprobación más fuerte de la etapa no compara contra un valor publicado sino
contra **otra fuente implementada aparte**. Con `mu_3 = 0` y un bloque tan grande
que la desviación es despreciable, la Ec. (3) de Lim et al. **es** la Ec. (34) de
Ma et al. que implementa `bb84.py`, escrita en cuentas en vez de en
probabilidades.

Y no solo coinciden: **coinciden de la manera correcta**. El residuo relativo es
**4.33e-04** con 1e16 pulsos, **4.33e-06** con 1e20 y **4.33e-08** con 1e24 — tres
puntos sobre una recta de pendiente −1/2, que es exactamente como escala `delta`.
Una coincidencia en un punto pueden ser dos errores que se cancelan; una que
converge con la ley correcta, no. Lo mismo con la Ec. (4) contra la Ec. (37).

**El V2, y la ambigüedad que resolvió.** Su §Evaluation publica que a 100 km la
tasa con bloque 1e9 es «about 1.75» veces la de 1e7. Pero su tasa de error
impresa lleva `eta_ch` —solo la fibra— en el término de desalineamiento, mientras
la tasa de detección de al lado lleva `eta_sys = eta_ch·eta_Bob`, diez veces
menor: ese término aporta entonces **3.9 puntos** de QBER a pérdida cero donde
la lectura consistente aporta **0.48**, un factor **8.07** que es justo el
`1/eta_Bob` que sobra. Cruzando esa
lectura con la de si `e_k` cuenta errores por puerta o por detección salen cuatro
modelos, con cocientes **1.79**, 2.73, 1.46 y 1.47. **Solo el físicamente
consistente cae sobre su número**, así que es el que se implementa — la
ambigüedad se resolvió midiendo, no eligiendo.

**Lo que no se reproduce, escrito en vez de ajustado:** dicen que un bloque de
1e4 llega a 135 km. Con esa lectura, un bloque de 1e4 no certifica clave **a
ninguna distancia**, ni a pérdida cero. El desajuste es de exactamente una
década: nuestra curva de 1e5 es su curva de 1e4 —positiva a 135 km, muerta antes
de 150—. Hueco 16 del [ADR 0009](../docs/adr/0009-citation-policy.md), y un test
que **asierta el desacuerdo**, para que quitarlo obligue a reescribir esto.

### Dos detalles que un lector cuidadoso pararía a mirar

**Recortar `s_0` a cero antes de usarlo en la Ec. (3) parece inseguro y no lo
es.** Esa ecuación lleva `+ (mu_2²-mu_3²)/mu_1² · s_0/tau_0`, así que un `s_0`
mayor da un `s_1` mayor, y mayor es la dirección insegura. Pero la Ec. (3) está
derivada con el número **verdadero** de eventos de vacío y es monótona creciente
en él: sustituir cualquier cota inferior válida del verdadero `s_0` da una cota
inferior válida de `s_1`. Cero es una cota inferior válida de un recuento, y es
**más ajustada** que un número negativo. Recortar mantiene la garantía y mejora el
resultado.

**El único sitio donde la fuente mezcla dos logaritmos.** El término de muestreo
escribe `cd log 2` en el denominador y `log2(...)` en el numerador de la misma
expresión. El primero es natural, el segundo base dos. Leer el primero como base
dos lo hace `1` en vez de `0.693` y escala `gamma` por `sqrt(ln 2) = 0.8326`: un
**17 % de subestimación** del castigo, en la dirección que favorece a la clave y
sin síntoma en ninguna otra parte. Hay un control negativo que lo mide.

### Lo que el módulo deja fuera, dicho en voz alta

- **El defecto activo que el roadmap pedía.** Quien posee un pase —y por tanto un
  bloque— es `system/key_volume.py`. Hasta que exista, lo que sale de `qkd/` por
  la interfaz de protocolo es asintótico y lo dice en su campo.
- **La optimización de parámetros.** Cinco, y el óptimo se mueve con el bloque.
  Es `engine/sweep.py`.
- **El sorteo de las cuentas.** `expected_block_counts` devuelve **esperanzas**:
  la cota tasa la incertidumbre de estimación que queda aunque las cuentas caigan
  justo en su media. Cuánto dispersa entre pases es otra pregunta, y es
  `system/monte_carlo.py`.
- **Variantes de uno o de más de dos decoys**, y cualquier protocolo que no sea
  BB84.

### El ADR que la etapa tenía aplazado

La §24 dejó dicho que las decisiones de decoy y las de finite-key pertenecen al
mismo documento y que escribirlo antes de tener consumidor era escribirlo dos
veces. Ya está: [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md), que cubre
los tres módulos de la etapa 2.3.

### Estado

`src/quoss/qkd/finite_key.py`, 396 sentencias, **100 % de cobertura de líneas y
de ramas**; `tests/qkd/test_finite_key.py`, 158 tests, de los cuales tres —la
reproducción de su Fig. 1, que optimiza cinco parámetros por punto— van marcados
`slow` y tardan 7 s. `ruff`, `ruff format` y `mypy` (estricto para `quoss.qkd.*`)
limpios, y la suite entera —2058 tests— en verde.

### La etapa 2.3 se cierra con tres módulos, no con seis

**Decisión del 2026-09-12:** `qkd/entanglement.py` (E91), `qkd/cv.py` (CV-QKD) y
`qkd/mdi_tf.py` (MDI-QKD y TF-QKD) **salen del roadmap**. El alcance del proyecto
es BB84 con pulsos coherentes débiles y decoy vacío+débil, y si alguno de los
otros hace falta más adelante, entra entonces.

**Por qué esto se puede decidir ahora y no cuesta nada.** El punto de extensión no
era nunca la lista de ficheros, era `QkdProtocol` + `ProtocolRegistry`, y eso es lo
que §23 dejó escrito y verificado —incluido el test que le pasa a la interfaz una
implementación rota a propósito para comprobar que caza el fallo—. Añadir un
protocolo es escribir una clase con su `_key_rate` y registrar un nombre; lo que
cruza la frontera es `LinkConditions` → `KeyRate`, y los cuatro protocolos
retirados consumen lo mismo (una transmitancia y un fondo) y producen lo mismo (una
tasa y un QBER), así que ninguno habría cambiado esos dos tipos. El coste de volver
es **un fichero**. Si fuera un refactor, retirarlos sería decidirlo a escondidas.

**Lo que no cambia, y ahora vale más:** los controles negativos sobre el registro
real. Que `PROTOCOLS.resolve("e91")` levante `ConfigurationError`, y que ninguno de
los ocho deletreos (`e91`, `entanglement`, `cv`, `cv-qkd`, `mdi`, `mdi-qkd`, `tf`,
`tf-qkd`) esté presente, **se queda tal cual** en `tests/qkd/test_base.py`. Antes
protegía contra que un escenario seleccionara algo todavía sin escribir; ahora
protege contra que seleccione algo que no va a existir, que es cuando fallar en voz
alta importa más. Igual se queda el test que exige que el docstring de `base.py`
nombre los cuatro: un alcance declarado por su nombre es lo que impide leer una
ausencia como un descuido.

**Lo siguiente del proyecto es por tanto la Etapa 3 — `system/`**, y arranca donde
los tres módulos de esta etapa dejaron su pendiente escrito: `system/passes.py`
(segmentar un pase) y `system/key_volume.py` (integrar la tasa sobre él), que es
quien posee un bloque y por tanto quien puede hacer de `finite_key.py` el defecto
activo.

---

## 26. `system/passes.py` — qué cuenta como pase, y las cuatro cosas que una implementación ingenua calcula mal

### Qué hace este módulo, para quien llegue nuevo

Un satélite en órbita baja no está aparcado sobre una ciudad: sale, cruza el
cielo en diez minutos o menos, y se pone. Un **pase** es una de esas travesías —
el tramo contiguo de tiempo en que una estación concreta puede usar un satélite
concreto. Es la unidad de trabajo: el telescopio gira hacia él, lo sigue, y para.
Todo lo que una misión reporta por noche lo reporta por pase.

**«Poder usar» no es «poder ver», y esa distinción es el primer trabajo del
módulo.** Un satélite a un grado sobre el horizonte es geométricamente visible y
prácticamente inútil: el haz cruza treinta veces más atmósfera que a cenit, el
telescopio mira por el aire más caliente, más turbulento y más contaminado de luz
que existe, y la distancia oblicua —y con ella la pérdida geométrica, que va con
el cuadrado del rango— está en su peor valor. Así que un pase se define contra
una **máscara de elevación**: un ángulo umbral por debajo del cual el enlace se
declara inservible.

`look_angles` ya dejó escrito en su docstring que el umbral es de este módulo, y
devuelve elevaciones negativas sin filtrar precisamente por eso.

### La decisión que parecía de trámite y no lo es: la máscara no tiene defecto

`find_passes` exige `minimum_elevation_rad`, sin defecto y por palabra clave. La
tentación era poner los 20° de Ntanos et al., que están ya en el paquete como
`NTANOS_MINIMUM_ELEVATION_RAD`.

La razón de no hacerlo la mide `key_volume.py` (§27) y se resume en una línea:
**la máscara tiene óptimo interior cerca de 8°, y la diferencia entre 2° y 8°
vale el 6.0 % de la clave del día.** Un defecto habría escondido un efecto
medible detrás de una cita. Una cantidad con óptimo no puede ser una constante.

### Las cuatro cosas que se calculan mal, cada una medida

Todas las cifras son del **día de referencia**: estación de Castelldefels
(41.2750 N, 1.9875 E, 30 m), satélite SSO a 700 km con el nodo a 30° este,
2025-01-01, rejilla de 1 s, máscara de 10°. Cuatro pases, de 562.2, 376.6, 558.4
y 302.7 s, con culminaciones a 52.9°, 17.6°, 58.8° y 14.2°.

**1. Los bordes no están en la rejilla.** Un pase empieza cuando la elevación
cruza la máscara, y ese instante cae **entre** dos muestras. Tomar la primera
muestra por encima de la máscara como inicio tira la fracción de paso anterior,
en los dos extremos: **1796.00 s en vez de 1799.79 s, o sea 3.79 s —el 0.21 %—
simplemente ausentes.** `find_passes` refina los dos cruces por interpolación
lineal en elevación.

Que la interpolación sea lineal no es pereza, y merece una frase: la elevación
frente al tiempo es lo más parecido a una recta justo en el horizonte, donde
cambia más rápido, y lo más curvada en la culminación, donde da la vuelta. Los
cruces están en el extremo del horizonte. La curvatura se trata aparte, donde
importa, que es el punto 3.

**2. El tiempo de permanencia de una muestra no es el paso de rejilla.** Las
muestras de un pase no valen todas los mismos segundos: la primera y la última
solo poseen la parte de su paso que cae dentro de la ventana refinada.
`PassTable.samples()` devuelve un **tiempo de permanencia por muestra** bajo la
regla del punto medio —cada muestra posee el intervalo entre su punto medio con
la anterior y su punto medio con la siguiente, recortado a `[start_s, end_s]`—
así que los tiempos de permanencia de un pase suman **exactamente** su duración
refinada, cosa que el trapecio sobre las muestras crudas no hace.

Esa exactitud es la que permite que `key_volume.py` use **un** vector de pesos
para la integral asintótica y para el presupuesto de pulsos del bloque finito, de
modo que comparar los dos regímenes mida la cota y no la cuadratura. Y hay una
segunda razón, más física: estos pesos se multiplican por una tasa de pulsos para
dar un **recuento de pulsos**, así que un peso es «cuántos pulsos se emitieron
mientras el enlace lo describía mejor esta muestra» — una cantidad que tiene que
ser positiva y sumar exactamente los pulsos que el pase emitió. El punto medio lo
da por construcción; los pesos de borde del trapecio son medios pasos
independientemente de dónde acabe el pase.

**Y lo que cuesta el recorte, dicho también en la dirección pequeña:** los
3.79 s recuperados son el 0.21 % del tiempo y solo el **0.032 %** de los bits,
porque son los segundos de menor elevación. El refinamiento se hace porque es
exacto y gratis, no porque cambie el resultado.

**3. La muestra más alta no es la culminación.** La elevación máxima de un pase
fija su rango mínimo y por tanto su mejor transmitancia, así que es el número que
un planificador lee primero, y leerlo de las muestras lo sesga **a la baja** como
el cuadrado del paso:

| Rejilla | Máximo discreto, error | Vértice parabólico, error |
|---|---|---|
| 10 s | **0.029°** | **0.0006°** |
| 30 s | **0.51°** | **0.081°** |

El vértice es el de la parábola por la muestra máxima y sus dos vecinas, escrito
en **forma de Newton** —válida para espaciado desigual— y no como la fórmula
`x_1 + h(y_0−y_2)/(2(y_0−2y_1+y_2))` de paso constante. `TimeGrid` admite
rejillas no uniformes, y ahí la fórmula de paso constante sería incorrecta de una
forma que parece un pequeño error de modelado y no un bug. Hay un test con una
parábola exacta sobre una rejilla deliberadamente irregular que la distingue.

**El detalle que encontró el test y no la derivación.** El ajuste se acepta solo
si `b_2 < 0`, si el vértice cae dentro del corchete de tres puntos **y de la
ventana refinada**, y si el máximo del pase lo alcanza **una sola** muestra. Esa
última condición no es relleno defensivo: por los puntos `(20, 30, 30)` el
vértice vale **31.25**, una elevación que ninguna muestra vio. Un máximo
alcanzado en más de una muestra es una meseta a la resolución de la rejilla, y
entonces la muestra se queda — que es honesto y además el sentido conservador. Lo
escribo porque la primera versión no lo tenía y el caso se descubrió escribiendo
el test de la meseta, no razonando.

**4. Un pase cortado por el borde de la rejilla no es un pase.** Si el satélite
ya está por encima de la máscara en la primera muestra, o sigue por encima en la
última, lo que la rejilla contiene es un **fragmento**: su duración, su
culminación y todo bit integrado sobre él son **cotas inferiores**, y nada en los
números lo dice. `truncated_start` y `truncated_end` lo dicen, y `find_passes`
registra un `warning` con cuántos encontró. Medido sobre una ventana de 600 s
abierta a mitad del primer pase: el fragmento es menos del 80 % del pase real.

### El guardia que cuenta muestras en vez de estimar un error

Una rejilla gruesa no difumina la clave integrada: **la infla**. Contra las
432 985 bits de la rejilla de 1 s (§27):

| Paso | Muestras en el pase más corto | Sesgo |
|---|---|---|
| 1 s | 303 | 0.0000 % |
| 10 s | 30 | +0.026 % |
| 25 s | 12 | +0.120 % |
| 45 s | 7 | **+1.319 %** |
| 60 s | 5 | **+2.018 %** |
| 120 s | 2 | **+8.586 %** |

Dos cosas. **El signo es positivo:** quien engrosa la rejilla para ahorrar tiempo
recibe una clave *mayor*, sin síntoma en ninguna parte. Y el sesgo **no es
monótono** en el paso —depende de dónde caigan las muestras respecto a la
culminación—, así que 48 s aterriza en **+0.003 % por accidente** entre vecinos a
+1.3 % y +2.0 %.

Por eso `MINIMUM_SAMPLES_PER_PASS = 12` guarda el **recuento de muestras**: una
estimación de error sacada de una sola ejecución gruesa puede ser pequeña por
coincidencia, y «este pase tiene cuatro muestras» no puede. El 12 es el punto más
grueso de la tabla donde el sesgo se queda por debajo del 0.15 %, y el test lo
**regenera** en vez de fiarse de los dígitos.

### La forma del contenedor, y por qué es plana

Los pases tienen longitudes distintas, así que el array natural
`(n_pases, n_muestras_del_pase)` **no existe**. `PassSamples` es por tanto plano:
cada par `(pase, muestra)` es una entrada, y las cuatro columnas comparten
longitud.

Esa forma es la que permite que `key_volume.py` evalúe el canal y el protocolo
**una sola vez** sobre todos los instantes dentro de pase de un día entero, en una
llamada vectorizada, y colapse el resultado por pase con una suma de segmentos
(`np.bincount`) — en vez de iterar sobre pases, que es lo que un contenedor
irregular obliga a hacer. No hay ningún bucle de Python sobre pases en toda la
etapa. La segmentación misma también es vectorizada sobre los dos ejes: rellenar
la máscara `(S, n)` con una columna falsa a cada lado convierte «aquí empieza un
tramo» en una diferencia local, y dos `np.nonzero` segmentan un día de sesenta
satélites a 1 s —5.2 millones de elevaciones, **240 pases en 0.07 s**— sin bucle.

Esa última cifra **se corre**, no se cita:
`TestTheConstellationCase::test_a_sixty_satellite_day_is_segmented_without_a_loop`
apila sesenta copias del satélite de referencia y exige que cada fila reproduzca
exactamente la tabla de un satélite. Sesenta copias no son una constelación
realista —todas las filas tienen los mismos pases— pero son justo la forma que
caza una segmentación que itera a escondidas, y la respuesta por fila se conoce de
antemano.

### Lo que este módulo deliberadamente no hace

- **No interpola la trayectoria.** `Trajectory` da las muestras que se le pidieron
  y nada entre ellas, y `notes/LAST_CHANGES.md` dejó abierto qué debía hacer
  `passes.py` con eso. La respuesta: se refinan los **bordes** y la
  **culminación** desde las muestras que existen, interpolando **en elevación**, y
  nunca se fabrica un vector de estado. Quien necesite resolución fina dentro del
  pase pide una rejilla más fina —que `TimeGrid` admite no uniforme—, que es una
  segunda propagación y no un caso especial aquí. **Fila cerrada** de la tabla de
  decisiones aplazadas.
- **No decide si un pase da clave.** Un pase con cero bits sigue siendo un pase, y
  cuáles son es la salida más interesante de §27. Meter un umbral de clave en la
  segmentación los haría invisibles.
- **No elige entre estaciones** (`multi_ogs.py`) **ni sabe de nubes**
  (`pcflos.py`).
- **No importa nada de `channel` ni de `qkd`**, comprobado sobre el AST y no sobre
  el texto, porque el docstring los nombra a propósito.

### Estado

`src/quoss/system/passes.py`, 284 sentencias, **100 % de cobertura de líneas y de
ramas**; `tests/system/test_passes.py`, 79 tests. Las conversiones de ángulo pasan
por `core/units.py`, que es lo que exige
`tests/unit/test_conventions.py` — la primera versión usaba `np.rad2deg` y el
guardia de convenciones la cazó, que es exactamente para lo que se escribió antes
de que existiera ningún módulo de física.

---

## 27. `system/key_volume.py` — el bloque es el pase, y con eso la cota finita pasa a ser el defecto

### Qué hace este módulo, para quien llegue nuevo

`qkd/` contesta «qué fracción de un pulso enviado **ahora mismo** se convierte en
clave». Una misión pregunta «cuántos bits sacamos esta noche». Convertir lo
primero en lo segundo parece multiplicar una tasa por una duración, y para la
tasa asintótica casi lo es. Para el número que un sistema real entrega, no, y la
diferencia es todo el contenido de este módulo.

La razón es que **una afirmación finite-key habla de un bloque, no de un
instante**. `qkd/finite_key.py` sabe poner precio a que Alice y Bob nunca observan
una probabilidad sino un recuento, y ese precio depende del tamaño del bloque — o
sea de una integral sobre un eje temporal. `qkd/` no tiene eje temporal, y por eso
toda `KeyRate` que sale de `qkd/base.py` va etiquetada `ASYMPTOTIC`, y por eso
`finite_key.py` podía calcular la cota pero **no** hacerla el defecto.

Este módulo tiene el eje temporal, así que puede. Y lo hace.

### La decisión central: la cota finita es el defecto, **estructuralmente**

`pass_key_volume` —el nombre sin adjetivos, el que se escribe por inercia—
devuelve `KeyRegime.FINITE`. El número asintótico solo se alcanza llamando a
`asymptotic_pass_key_volume`, y **no existe ningún argumento `regime=`**.

**Por qué no un argumento con defecto**, que era lo evidente: un defecto es un
valor que alguien pasa distinto por descuido, y aquí el descuido no tiene
síntoma. Las dos llamadas devuelven un número de bits positivo y plausible. Esto
es lo que hay entre ellas, en el día de referencia de §26 con el telescopio de
0.75 m, noche clara sin luna, reparto 16:1:4 de Ntanos et al. y
`eps_cor = eps_sec = 1e-10`:

| Pase | Asintótico | Finito | Culminación |
|---|---|---|---|
| 1 | 1 548 341 bits | **190 581** bits | 52.9° |
| 2 | 319 898 bits | **0** bits | 17.6° |
| 3 | 1 709 160 bits | **242 404** bits | 58.8° |
| 4 | 199 281 bits | **0** bits | 14.2° |
| **Día** | **3 776 681 bits** | **432 985 bits** | — |

El cociente del día es el **11.5 %**, y no es lo importante. Lo importante es la
columna por pase: **dos de los cuatro pases no certifican nada.** Así que el error
de reportar la cifra asintótica no es «unas ocho veces optimista», es
**ilimitado**, y lo es justo en los pases bajos que un planificador estaría
decidiendo si merece la pena agendar.

### Y muere de golpe, no poco a poco — la intuición que hubo que corregir

«Bloque pequeño, clave pequeña» es la intuición equivocada. El pase 4 recoge
**309 867** detecciones en la base de clave; no es un número pequeño. Lo que lo
mata es la **tasa de error de fase**: la cota tiene que inferir, desde la base que
Alice y Bob sí midieron, cuál habría sido el error en la base conjugada, y esa
inferencia es un argumento de muestreo cuya anchura crece al encogerse los
recuentos. Al tamaño de bloque del pase 4 la inferencia devuelve `phi = 0.5`, el
máximo posible, donde `1 − h(phi) = 0` y el término de un fotón se anula **entero**
— mientras la corrección de errores sigue cobrándose sobre los 309 867 bits.

No hay régimen de «poca clave»: hay un acantilado, y
`FiniteKeyResult.phase_error_rate` es el campo que dice cuál.

### Qué es un bloque: ni la muestra ni el día, y las dos alternativas medidas

Es la palanca más grande del módulo, y las dos tentaciones obvias fallan en
direcciones opuestas.

**Un bloque por muestra** —que es en lo que consistiría tratar la cota finita como
una corrección por instante— da **cero bits del día entero**: cero de 1800
muestras certifica un solo bit. Cada muestra tiene una mediana de 1615 detecciones en la
base de clave contra un peaje fijo de 260 bits y una inferencia de error de fase
que no tiene con qué trabajar. **La cota no es aditiva sobre sub-bloques**, y
suponer que lo es lo pierde todo.

**Un bloque por día** es la tentación opuesta: un bloque mayor paga el peaje una
vez y tiene estadística más apretada. También es incorrecto. Entre pases el
satélite está bajo el horizonte y **no se envía ningún pulso**, así que no es un
bloque sino varias ejecuciones del protocolo separadas por horas. Y en concreto
mezclaría las tasas de error: los dos pases muertos aportan 787 000 detecciones
al 1.8–1.9 % de QBER a un bloque cuyos pases buenos están al 1.24–1.26 %, y la
corrección de errores se cobra sobre todas. El módulo **no ofrece** esa función, y
`daily_key_volume` suma **longitudes**, que es la operación que la
componibilidad autoriza.

### El hallazgo que solo este módulo puede ver: la máscara tiene óptimo interior

§26 dejó dicho que la máscara es una variable de diseño. Aquí está por qué:

| Máscara | Pases | Día finito | Día asintótico |
|---|---|---|---|
| 2° | 6 | 408 946 | 3 876 492 |
| 5° | 5 | 426 988 | 3 876 492 |
| 7° | 4 | 433 771 | 3 862 432 |
| **8°** | 4 | **434 938** | 3 844 682 |
| 10° | 4 | 432 985 | 3 776 681 |
| 20° | 2 | 360 978 | 2 949 471 |

Dos cosas distintas, y las dos son el punto.

**La columna asintótica es monótona y la finita no.** La clave asintótica por
pulso está recortada a cero muestra a muestra, así que añadir una muestra mala a
un pase nunca puede restar clave: por debajo de 5° las muestras extra aportan
**exactamente cero** y la columna deja de moverse del todo. Una cota a nivel de
bloque no tiene esa protección — las muestras de baja elevación de los bordes
meten sus errores en el bloque agrupado, donde la corrección de errores se cobra
sobre **todas** las detecciones, aportando casi ningún evento certificado de un
fotón. Bajar la máscara de 8° a 2° compra un **71 % más** de segundos útiles y
**destruye el 6.0 %** de la clave del día, y el cálculo asintótico no puede verlo
ocurrir.

**El mecanismo, medido sobre un solo pase** al pasar de 10° a 5°: sus eventos
certificados de un fotón suben un **2.6 %** (718 970 → 737 975) y su fuga de
corrección de errores sube un **5.5 %** (246 574 → 260 144). La segunda adelanta a
la primera, y el pase pierde el 1.7 % de su clave ganando el 22 % de su duración.

Es la misma familia de hallazgo que el óptimo de la fracción decoy de §25: una
cantidad a la que la fórmula asintótica es indiferente tiene un óptimo real en
cuanto el bloque es finito.

### Una cuadratura y una configuración, porque si no la comparación no mide la cota

Una comparación entre dos números no vale nada si difieren en algo más que en lo
que se compara. Dos precauciones, las dos con test:

- **Un vector de pesos.** Los dos caminos integran sobre los tiempos de
  permanencia de `PassTable.samples()`. El asintótico multiplica la tasa por
  segundo por ellos; el finito multiplica la tasa de pulsos por ellos. Ninguno
  tiene regla de cuadratura propia, así que ninguno puede ir por delante por una
  razón que no sea la cota.
- **Un objeto de configuración.** Los dos toman el mismo `Bb84DecoyProtocol`, y
  `decoy_settings_from_protocol` deriva de él el `DecoySettings` que el camino
  finito necesita. La alternativa —dos objetos configurados aparte— permitiría que
  los dos caminos describieran experimentos distintos, y el fallo no tiene
  síntoma: la comparación sigue dando un cociente. Hay un test que cambia µ y
  exige que **se muevan las dos** columnas, para que el puente sea portante y no
  decorativo.

La única pieza que el protocolo asintótico no lleva es la tercera intensidad,
porque su estado de vacío es un pulso exactamente vacío; `mu_3 = 0` se suministra
aquí, con su defensa en `_VACUUM_INTENSITY`.

### La parte que una leyenda de figura casi siempre falla: componer un día

Cada pase es un bloque independiente, `eps_sec`-secreto y `eps_cor`-correcto **por
su cuenta**. Concatenar `n` claves así da una clave cuya probabilidad de fallo
está acotada por la unión de los `n` fallos: **`n · eps`, no `eps`**.
`composed_security` lo calcula y `DailyKeyVolume.security` lo lleva, de modo que
la clave de un día no viaja nunca sin el `eps` bajo el que de verdad es segura.

Con cuatro pases a `1e-10` eso es un inofensivo `4e-10`. Es inofensivo y es **un
número distinto del que se imprime al lado**, y crece con exactamente la cantidad
que una misión intenta maximizar: cien pases de una constelación son `1e-8`, un
año de cuatro pases diarios es `1.5e-7`.

**Y la otra dirección también está tasada.** Para que el **día** sea `eps`-seguro
en vez de cada pase, cada bloque tiene que correr a `eps / n`. Medido: **404 780
bits en vez de 432 985**, o sea que un día honestamente `1e-10`-seguro cuesta el
**6.5 %** de la clave. Barato, no nulo, y nada que nadie fuera a encontrar leyendo
una gráfica de tasa.

`composed_security` se **niega** a devolver una composición vacua: `n · eps >= 1`
no es una probabilidad de fallo, es la ausencia de afirmación, y devolverla como
número sería el `except: pass` que el README prohíbe.

### El contrato de entrada, y por qué el orden es parte de él

`pass_key_volume` recibe un `LinkConditions` ya evaluado en los instantes que
`PassTable.samples()` lista, **en ese orden**. No toma ni una perilla óptica: lo
contrario pondría doce argumentos de presupuesto en la firma y haría que
`quoss.system` dependiera de cada perilla de `quoss.channel`.

El contrato se comprueba por longitud, y el docstring dice explícitamente que el
**orden** también es parte del contrato y no una convención — porque una longitud
correcta en otro orden atribuiría cada transmitancia al instante equivocado y nada
aguas abajo podría notarlo. Es el tipo de fallo que esta norma existe para dejar
dicho en voz alta cuando no se puede comprobar.

### La reserva que se traslada en vez de desaparecer

`channel/link_budget.py` dice con todas las letras que hasta que exista
`system/correlated_fading.py` «ninguna afirmación de ese módulo sobre clave *por
pase* se sigue de una sobre clave *por puerta*». **Este módulo hace exactamente
esa afirmación.** Así que la reserva se repite en su docstring en vez de
desaparecer: un enlace real se desvanece a ráfagas de milisegundos, así que el
número de puertas **consecutivas** perdidas no es el que implica el muestreo
independiente, y qué le hace eso a un bloque es una pregunta abierta. Todas las
cifras de arriba suponen que la estadística de desvanecimiento de un pase es la
marginal.

Y por la misma regla: todas las cuentas vienen de `expected_block_counts`, que
devuelve **esperanzas**. Estas cifras son la clave que certifica un pase
**típico**, sin P5/P95 — la dispersión entre pases es `monte_carlo.py`.

### Lo que esto cierra

- **La decisión aplazada del [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md)**
  («quien posee un pase —y por tanto un bloque— es `system/key_volume.py`») y la
  frase equivalente del docstring de `quoss/qkd/__init__.py`, que decía en futuro
  algo que ahora es presente. Las dos están reescritas; lo que decía
  `KeyRegime.FINITE` —«lo que QuOSS reporta por defecto en cuanto exista
  `finite_key.py`»— también, porque `finite_key.py` ya existía cuando se escribió
  y el defecto no se fijaba allí.
- **El entregable DB3**: clave por pase y por día, con la cota finite-key aplicada
  al bloque correcto, el régimen en un campo del resultado y el `eps` compuesto
  del día en otro.

Todo lo demás de la etapa —la dispersión, el fading correlacionado, las nubes,
varias estaciones, los relés, la optimización de parámetros— sigue declarado
fuera, en el docstring y en el [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md).

### Estado

`src/quoss/system/key_volume.py`, 227 sentencias, **100 % de cobertura de líneas y
de ramas**; `tests/system/test_key_volume.py`, 80 tests. El ADR de la etapa es el
[0011](../docs/adr/0011-the-block-is-the-pass.md), y cubre los dos módulos.

---

## 28. `system/correlated_fading.py` y `system/monte_carlo.py` — el desvanecimiento como proceso, y la clave de un pase como distribución

### Qué hacen estos módulos, para quien llegue nuevo

§27 dejó dicho que `pass_key_volume` devuelve la clave de un pase **típico**,
sin P5/P95, y que todas sus cifras suponen que la estadística de desvanecimiento
de un pase es la marginal. Estos dos módulos cierran las dos reservas, y al
cerrarlas resulta que la cifra de §27 no es «típica» en el sentido que uno
esperaría.

Un **desvanecimiento** («fade») es un tramo de tiempo en el que el centelleo
—el titilar de la irradiancia al cruzar el aire turbulento— o el jitter de
apuntado —el terminal temblando alrededor del telescopio— han bajado la
potencia recogida por debajo del diseño. `channel/link_budget.py` los trata
como **marginales**: qué fracción del tiempo está el enlace peor que un nivel.
Eso no dice **cuánto dura** un desvanecimiento, y para un bloque de cuentas la
duración lo es todo: mil parpadeos de un microsegundo y un apagón de diez
segundos tienen la misma marginal y consecuencias opuestas.

`correlated_fading.py` convierte cada desvanecimiento en un **proceso en el
tiempo**: un motor gaussiano de Ornstein-Uhlenbeck —el proceso estacionario con
memoria más simple, correlación `exp(−|Δt|/τ)`— en la variable donde el
desvanecimiento es gaussiano (la log-irradiancia para el centelleo; las dos
componentes del jitter para el apuntado), pasado por las mismas leyes que
`turbulence.py` y `pointing.py` ya usan. `monte_carlo.py` multiplica cada
realización de ese factor en el enlace, pasa todas por el mismo modelo de
cuentas y la misma cota finita de §25 y §27, y devuelve **dónde están el P5, el
P50 y el P95** de la clave por pase y por día, y con qué frecuencia un pase no
da nada.

### Qué número reportaba el proyecto, y qué número era

`pass_key_volume` alimenta la cota con `LossBudget.transmittance`, que **lleva
dentro el margen de desvanecimiento** `fade_db`: la pérdida que apuntado y
centelleo solo superan el 1 % del tiempo. Así que los 432 985 bits/día de §27
son la clave de un pase en el que el enlace está en su cuantil del 1 %
**durante todo el pase**. Ni la media sobre el desvanecimiento ni ningún
cuantil de la distribución de claves: una cifra de diseño.

Medido (`TestWhatTheDesignNumberUnderReports`): el mismo cálculo determinista a
la transmitancia **media** —margen devuelto, apuntado en su media
`γ²/(γ²+1)`— da **758 707 bits**, ×1.752. La cifra de diseño **infrarreporta el
día típico un 43 %**. Y los pases 2 y 4 siguen muertos, así que el hallazgo del
ADR 0011 no era un artefacto del margen — pero **el mecanismo cambia**: a la
transmitancia de diseño mueren en el tope del error de fase (`φ` = 0.459 y
0.5); a la media `φ` es 0.197 y 0.315 y los mata que la corrección de errores
adelanta al término de un fotón por 2.2 y 8.7 veces. La mejor de mil
realizaciones llega al 58 % y al 20 % de su propia fuga.

### El conjunto de referencia

Día de referencia de §26, `τ` = 2 ms (centelleo) y 20 ms (apuntado), 1 000
realizaciones, cuentas sorteadas de Poisson, semilla 20260913
(`test_the_headline_quantiles`):

| | P5 | P50 | P95 |
|---|---|---|---|
| Pase 1 | 329 229 | 345 658 | 361 865 |
| Pase 3 | 395 324 | 412 512 | 429 023 |
| **Día** | **735 329** | **758 314** | **782 391** |

Los pases 2 y 4 dan cero en las mil realizaciones. El P5 de la suma (735 329)
está por encima de la suma de los P5 (724 553): los cuantiles del día son
cuantiles de la suma por realización, no sumas de cuantiles. El `eps` del día es
`4e-10`, como en §27.

**Cuántas realizaciones**, por un criterio y no por gusto: el error estándar
del P5 es `sqrt(p(1−p)/R)/f(q_p)`; a 1 000 realizaciones el *bootstrap* da el
**0.22 % y el 0.16 %** de la mediana en los pases vivos, y la fórmula normal
invertida (`realisations_for_quantile`) dice que 37 bastaban para un 1 %, de
acuerdo con el bootstrap dentro del 25 %. Tiempo: **0.86 s** por día a mil
realizaciones (`TestRuntime`).

### El tiempo de correlación es un parámetro, y por qué

Ninguna fuente abierta lo publica con precisión de modelo. La hipótesis de
Taylor da un orden de magnitud —`τ = ℓ/v`—, y para un enlace descendente LEO la
velocidad no es el viento sino el **barrido** de la línea de visión a través de
la capa turbulenta. Medido en el pase 3 (`TestChoosingACorrelationTime`): a la
altura de escala de la UIT, 7 700 m, la línea de visión barre a **62–85 m/s**
contra 2.3 m/s de viento; con una anchura de Fresnel de 0.109 m, `τ` cae en
**1.3–1.8 ms**; con el viento solo diría 47 ms. La anchura `ℓ` es un hueco
declarado, así que `FadingParameters` toma los dos tiempos sin defecto y
`taylor_correlation_time_s` / `slew_transverse_speed_m_s` /
`line_of_sight_angular_rate_rad_s` dan la derivación.

### La decisión técnica: promediar sobre la permanencia, muestreando la integral exacta

Milisegundos de `τ` y una rejilla de 1 s son mil desvanecimientos por muestra.
Los pulsos de la muestra ven el **promedio**, y el modelo de cuentas es lineal
en la transmitancia hasta `ημ < 5e-4`. Un sorteo instantáneo por muestra
sobreestimaría la fluctuación en `1/w`,
`w(T/τ) = 2(τ/T)²(T/τ − 1 + e^{−T/τ})`: 500 en varianza para 1 s y 1 ms.
Medido en el pase 1 (`TestWhatCorrelationChangesOnTheGrid`): el sorteo
instantáneo sobreestima la desviación del recuento agrupado entre 10 y 22
veces, y la fluctuación real del recuento es menor que el 0.2 %.

No se sub-muestrea (7·10⁹ sorteos por día): `sample_fade_factors` muestrea la
**integral** del motor sobre cada ventana exactamente, junto con su extremo (par
gaussiano con covarianzas cerradas), evalúa la no linealidad sobre la media
estandarizada y encoge hacia la media marginal por `sqrt(w)` —a `τ` para el
centelleo y a `τ/2` para el apuntado, cuyo factor va con el cuadrado de sus
motores—. Contra fuerza bruta en rejilla fina (`TestTheDwellAverage`, `T/τ` =
0.1, 1, 10): varianza por ventana dentro del 1.5 %, varianza a nivel de pase
del producto dentro del 1.5 %, y la covarianza entre ventanas del apuntado un
5 % baja a `T = τ`, acotada y dicha.

### El hallazgo, sin adorno

Barrido de `τ` con las cuentas en su esperanza (`TestWhatCorrelationChanges`):

| `τ` | Pase 1, P5–P95 (%) | Pase 3 (%) | Día (%) |
|---|---|---|---|
| 1 ms | 0.11 | 0.09 | 0.07 |
| 10 ms | 0.33 | 0.27 | 0.22 |
| 100 ms | 1.04 | 0.89 | 0.68 |
| 1 s | 3.6 | 3.0 | 2.2 |
| 10 s | 10.9 | 9.9 | 7.4 |
| 100 s | 30.4 | 28.8 | 20.0 |

Cada década ensancha `sqrt(10)`; la banda cruza el 1 % **entre 10 y 100 ms**,
dos órdenes de magnitud por encima de la estimación física; la mediana no se
mueve. **Y a la `τ` física no es el desvanecimiento lo que fija la dispersión:
es contar.** Cuentas de Poisson sin desvanecimiento: **9.0 %** de banda en el
pase 1; con el desvanecimiento encima, 9.4 %. Noventa veces más, y no de los
millones de detecciones (0.03 % de dispersión) sino de las cuentas pequeñas de
señuelo y vacío desde las que la cota infiere el rendimiento de un fotón.

Lo que el desvanecimiento correlacionado **sí** cambia: los cuantiles bajos en
cuanto `τ` se acerca a la permanencia, y la **duración de los
desvanecimientos**. Para un proceso de Ornstein-Uhlenbeck la tasa de cruces en
tiempo continuo (Rice) **diverge** —la trayectoria no es diferenciable—, así que
`fade_duration_statistics` reporta cruces *por paso* con su paso, comprobados
contra la binormal exacta de SciPy (`TestFadeDurations`). Medido con el
apuntado bajo 0.85 y `τ_p` = 0.2 s: **47, 22 y 14 ms** de duración media a pasos
de 20, 5 y 2 ms (2.3, 4.5 y 7.0 pasos) contra 1.04 pasos i.i.d. a cualquier
paso; los desvanecimientos por segundo crecen como `Δt^{−1/2}` y la fracción
de tiempo se queda en el 4.2 % marginal. Las dos cosas afirmadas en el test.

### Reproducibilidad, cuentas y agrupamiento

- Un hijo de `RandomSource` **por pase**; los sorteos van antes de la
  evaluación por trozos, así que el tamaño del trozo no cambia un bit
  (`test_the_chunk_size_does_not_change_a_bit`). El proceso se reinicia en cada
  pase; a `τ` = 1000 s contra 5 363 s de separación el registro avisa
  (`monte_carlo.passes-not-independent`).
- Cuentas: Poisson sobre las detecciones agrupadas y binomial sobre los errores
  —el adelgazamiento exacto—, con `1 − Q` (`Q < 1e-3`) como diferencia con la
  verdad por puerta. Pulsos no sorteados.
- Agrupamiento con la misma suma ordenada por índice que `key_volume.py`, y por
  eso una realización pasada por `pass_key_volume` da **la misma clave bit a
  bit** (`TestReproducesTheDeterministicVolume`).
- Registro: `monte_carlo.ensemble-summary` (INFO, con diseño, media y mediana),
  `monte_carlo.transmittance-clipped` (WARNING), `monte_carlo.passes-not-independent`
  (WARNING), `monte_carlo.day-composes-blocks` (INFO),
  `correlated_fading.samples-independent` (WARNING cuando se piden factores
  instantáneos en una rejilla más gruesa que catorce `τ`).

### Lo que queda fuera

Espectro de centelleo medido (cola `−8/3`, dos parámetros, sin fuente),
turbulencia no gaussiana, correlación entre pases, nubes, varias estaciones,
relés. Todo declarado en los docstrings y en el
[ADR 0012](../docs/adr/0012-correlated-fading-and-monte-carlo.md).

### Estado

`src/quoss/system/correlated_fading.py` (270 sentencias) y
`src/quoss/system/monte_carlo.py` (356), **100 % de cobertura de líneas y de
ramas** en los dos; `tests/system/test_correlated_fading.py` y
`tests/system/test_monte_carlo.py`, 83 tests más 15 doctests, 24 s en total,
ninguno por encima de 3 s. `tests/system/reference_fading.py` da los tres
insumos de desvanecimiento en las muestras del enlace de referencia de
`reference.py`. `ruff`, `ruff format` y `mypy` limpios. El ADR de la etapa es el
[0012](../docs/adr/0012-correlated-fading-and-monte-carlo.md).

---

## 29. `system/pcflos.py`, `system/multi_ogs.py`, `system/relay.py` — las nubes deciden si el pase existe, un terminal decide a quién sirve, y el satélite guarda la clave hasta que hay con quién emparejarla

### Qué hacen estos tres módulos, para quien llegue nuevo

Hasta la §27 todo el paquete `system/` es la vista de **una** estación: unos
ángulos de mira, una tabla de pases, un volumen de clave. Una misión tiene
varias estaciones y un cielo que a veces está nublado, y esas dos cosas
introducen tres preguntas nuevas que ningún módulo anterior podía contestar:

1. **¿Cuál es la probabilidad de que el pase haya existido?** Una nube no es
   una atenuación como la atmósfera de `channel/`: un cirro cuesta decenas de
   decibelios y un cúmulo lo cuesta todo. El modelo honesto es binario —o la
   línea de vista está libre y el pase existe, o no— y la cantidad que lo
   describe es la **probabilidad de línea de vista libre de nubes**, pCFLOS.
   Eso es `pcflos.py`.
2. **¿Cuánta clave dan varias estaciones juntas?** Hay dos respuestas y son
   sistemas distintos: si cada estación cosecha su propia clave con el satélite,
   la del día es la **suma**; si el satélite tiene **un** terminal óptico y dos
   estaciones lo quieren a la vez, solo un pase de los dos puede ocurrir y la
   respuesta es la mejor selección de pases **que no se solapan**. Eso es
   `multi_ogs.py`, y la segunda respuesta es un problema de planificación.
3. **¿Cómo llega la clave de A a B si A y B nunca ven el mismo satélite a la
   vez?** El satélite cosecha `K_A` sobre A, `K_B` sobre B, y anuncia por un
   canal público `K_A ⊕ K_B`; A y B acaban compartiendo `min(|K_A|, |K_B|)`
   bits. El satélite tiene las dos claves en claro, así que **hay que
   confiar en él** —de ahí «nodo de confianza»— y la clave espera a bordo
   hasta que hay con qué emparejarla. Eso es `relay.py`, y es una simulación
   sobre el tiempo, no una fórmula.

La regla que atraviesa los tres, heredada de la §27 y del ADR 0011: **la
probabilidad de cielo despejado multiplica una esperanza, nunca una clave**.
`bits × disponibilidad` es la clave *esperada* sobre el tiempo, un número de
planificación para una temporada; la cota finita certifica los bits del pase la
noche que el pase ocurre, y la nube solo decide si ocurre. `multi_ogs.py` lleva
las dos columnas —certificada y esperada— una al lado de la otra y no sustituye
una por la otra.

### `pcflos.py`: lo exacto, el hueco, y las tres lecturas de una serie horaria

**Lo exacto.** La entrada es una **fracción de cobertura** `f` —la fracción del
cielo, vista desde arriba, que tapa la nube; es lo que da un archivo
meteorológico (el `cloud_cover` de ERA5 vía Open-Meteo, en porcentaje, uno por
hora) y lo que da una climatología mensual—. Para una línea de vista
**vertical** la conversión no es un modelo sino una definición: la fracción de
cobertura es la fracción del área que una vertical atraviesa con nube, así que
`pCFLOS(cénit) = 1 − f`. `cloud_free_probability` devuelve eso y nada más, y
rechaza con `DomainError` un 50 que nunca se dividió por 100.

**El hueco, declarado y con la firma en vez de con un comentario.** Un satélite
no está en el cénit: a 10° la línea recorre `1/sin(10°) = 5.8` veces la
distancia vertical dentro de una capa de nubes, así que la probabilidad de
colarse entre las celdas es menor. La medida clásica es la de Lund & Shanklin
(*J. Appl. Meteorol.* 11:773, 1972, y 12:28, 1973), a partir de fotografías de
todo el cielo. **Ninguno de los dos papers se pudo abrir** —la editorial
devuelve 403 y Semantic Scholar 429— y por la política del ADR 0009 no se
transcribe de memoria ningún número con un número de tabla al lado.
Consecuencia estructural: **ninguna función del módulo acepta una elevación**,
y `test_no_function_here_takes_an_elevation` lo aserta por ausencia, el mismo
control negativo que tiene `channel/background.py` para la radiancia.
`cloud_free_probability` registra un `WARNING`
(`pcflos.no-elevation-dependence`) en cada llamada diciendo que devuelve el
valor cenital y en qué sentido se equivoca: para una capa, una línea oblicua
solo puede encontrar *más* nube, así que `1 − f` es **cota superior** a
cualquier elevación y exacta solo en el cénit. Lo que un modelo geométrico
necesitaría —altura de la base y tamaño de celda— no está en ningún archivo de
cobertura, y un par adivinado produciría una curva plausible con un error que
nadie podría acotar.

**Las tres lecturas.** Un archivo es horario y un pase dura diez minutos.
`pass_availability` interpola la serie **linealmente** sobre la rejilla del pase
—elección de modelado, registrada en cada llamada como `INFO`
(`pcflos.pass-availability-rule`) con el paso de la serie— y tiene que decir qué
valor del interpolante «es» el pase. Hay tres candidatos, todos disponibles vía
`AvailabilityRule`: la **media ponderada por permanencia** sobre la ventana
(la fracción esperada de instantes despejados), el valor en la **culminación**,
y el **mínimo** (lo que necesita un pase si un minuto tapado aborta el bloque).
Ninguno es «la» disponibilidad: la de verdad —que *todo* el pase esté
despejado— necesita la correlación espacio-temporal de la nube a diez minutos,
que un archivo horario no tiene. Lo que sí garantiza la resolución horaria es
que no pueden diferir mucho, y está **medido**
(`TestTheThreeReadingsOfAnHourlySeries::test_the_spread_between_readings_is_small_at_hourly_resolution`):
con un frente sintético que sube de 0.05 a 0.95 en tres horas y baja igual,
puesto de modo que los pases de la mañana caen en la subida y los de la tarde en
la bajada, la mayor diferencia entre dos lecturas cualesquiera sobre los cuatro
pases del día de referencia es **0.023** en probabilidad; el techo *derivado*
—0.3 por hora por los 562 s del pase más largo— es 0.047. La media y la
culminación coinciden a 1e-4 (el interpolante es casi lineal a lo largo de un
pase y la culminación está cerca de su centro); el mínimo queda por debajo la
pendiente por media ventana. La media es el defecto porque es la única de las
tres que es una esperanza de algo, y las otras dos viajan en el registro para
que quien quisiera el mínimo vea lo que le cuesta la elección. La cuadratura es
la del punto medio de `PassTable.samples()`, que para una función lineal es
**exacta** en toda celda que no contenga un nudo horario; la media vectorizada
se comprueba contra un bucle por pase (V3) y el mínimo contra un muestreo denso
a 0.1 s y contra un nudo colocado a propósito dentro de un pase, invisible desde
los extremos y la culminación.

**Lo que se niega a hacer:** extrapolar. Una serie que no cubre la ventana de
un pase es `DomainError`, porque `np.interp` extendería el valor del extremo sin
decir nada y eso es inventar tiempo. Las dos rejillas —la de la serie y la de
los pases— pueden tener épocas distintas y se reconcilian por fecha juliana;
hay un test que desplaza la serie seis horas y obtiene el mismo resultado.

**Diversidad de emplazamiento, con lo que se sabe y lo que no.** Dos estaciones
suficientemente separadas ven nubes distintas. Si fueran **independientes**,
`P = 1 − Π(1 − p_i)`, que es **cota superior** (la correlación solo hace más
probable «las dos tapadas»); con **correlación perfecta**, `max_i p_i`, **cota
inferior** para cualquier correlación no negativa (la unión contiene a cada
evento). Entre las dos, la parametrización habitual es `ρ_ij = exp(−d_ij/L)`.
Para **dos** estaciones eso basta: dos Bernoulli con marginales y correlación
dados tienen una sola ley conjunta, `P(ambas nubladas) = q₁q₂ + ρ√(p₁q₁p₂q₂)`,
y `joint_cloud_free_probability` devuelve uno menos eso, exacto — dos
estaciones con `p = 0.6` a 500 km con `L = 500 km` dan **0.7517**, entre el 0.60
correlado y el 0.84 independiente (doctest, y
`TestSiteDiversity::test_the_two_station_law_by_hand` con la fórmula transcrita
aparte). No toda `ρ` es compatible con todo par de marginales: la cota de
Fréchet es `√(min(p₁q₂, p₂q₁)/max(p₁q₂, p₂q₁))`, que vale 1 con marginales
iguales y **0.2182** con 0.9 y 0.3; por encima se lanza `DomainError`, no se
recorta, porque una correlación recortada es un modelo sustituido sin registro
(`test_the_feasibility_bound_is_the_frechet_one` comprueba que justo debajo
pasa y justo encima no). Para **tres o más** estaciones las correlaciones por
pares **no** determinan la ley conjunta (`2^N − 1` probabilidades libres frente
a `N(N−1)/2` correlaciones), así que se devuelven las dos cotas, `exact` es
`None` y hay un `WARNING` (`pcflos.joint-law-not-unique`); una cópula gaussiana
la rellenaría con una elección concreta y no se hace porque nada verificado
dice que sea la correcta. `L` **no tiene defecto**: es todo el contenido del
modelo de correlación y ninguna fuente verificada publica un valor.

**Distancia entre estaciones.** `station_separation_km` es la cuerda entre los
dos emplazamientos a través de `geodetic_to_itrf` —el mismo elipsoide donde
viven las estaciones del proyecto— convertida a arco sobre la esfera de radio
medio WGS-84 `(2a+b)/3 = 6371.0088 km`, derivado de las constantes y no
tecleado. Contra la haversine como cálculo independiente (V3): un grado sobre
el ecuador difiere en `f/3` (la cuerda usa `a`, la esfera `R`), y la cota
general **no es `f` sino `1 − a(1−e²)/R = 0.558 %`** —el radio de curvatura
meridiano en el ecuador es el más apretado del elipsoide—, alcanzada por un arco
meridiano infinitesimal y aproximada desde abajo por todo arco finito (0.5582 %
a 1°, 0.5538 % en el peor de 200 000 pares aleatorios entre 50 y 15 000 km).
Castelldefels–Calar Alto son **596.0 km** y Castelldefels–OGS de Tenerife
**2213.8 km**.

### `multi_ogs.py`: dos políticas, un planificador exacto, y lo que compró la diversidad

**Dos políticas, porque son dos sistemas.** `AggregationPolicy.SUM` suma
estaciones: vale cuando el satélite es un nodo de confianza que guarda cada
clave y las empareja después (es lo que consume `relay.py`). `BEST_AVAILABLE`
modela **un** terminal óptico a bordo: los pases cuyas ventanas se solapan
entran en conflicto, y se queda con el subconjunto sin solapes de mayor clave
esperada. Un módulo que ofreciera una sola habría tenido que elegir, y ninguna
es «la» respuesta.

**El planificador es exacto y no cuesta nada.** Elegir intervalos disjuntos de
peso total máximo es *weighted interval scheduling*, con solución exacta en
`O(n log n)`: ordenar por fin, buscar por bisección el último compatible de cada
uno, `M_j = max(M_{j−1}, w_j + M_{p(j)})`, y retroceder. Es el único bucle de
Python sobre pases de todo `system/`, y está bien que lo sea: son cientos de
pasos una vez, no el eje temporal. El **greedy por clave** —quedarse con el
pase más rico, descartar lo que lo solape, repetir— no es exacto: un pase rico
entre dos algo más pobres que no se solapan entre sí lo vence (4 + 4 = 8 contra
6, `test_the_instance_where_greedy_loses`). Los dos se comparan con nombre,
`schedule_passes` y `greedy_schedule_passes`, y el exacto se comprueba contra
una **fuerza bruta sobre todos los subconjuntos** de instancias aleatorias de
hasta nueve intervalos con Hypothesis, con y sin hueco de reorientación
(`TestTheSchedulerIsExact`, 300 ejemplos), además de la propiedad de
**maximalidad**: tras un paso de compleción, un intervalo no seleccionado lo es
**si y solo si** choca con uno seleccionado, que es lo que un recuento de
«pases descartados por conflicto» necesita significar (un pase muerto que no
choca con nada no se reporta como descartado).

**El hueco de reorientación.** `minimum_gap_s` es el tiempo de giro y
asentamiento entre dos pases consecutivos del mismo terminal, con defecto
`0.0`: es una propiedad del terminal para la que el proyecto no tiene fuente, y
cero es el único valor que no es una invención. Un hueco positivo solo puede
quitar pases (medido en `TestTheSlewGap`: 65 → 50 bits en un caso sintético
con dos pases a 100 s uno del otro y un hueco de 120 s).

**Lo que no modela, y lo rechaza en vez de planificar mal:** el conflicto del
terminal de **tierra** —dos satélites sobre una estación a la vez—, porque el
alcance del proyecto es un satélite (decisión de 2026-09-10). Esa entrada es
`DomainError` con la decisión en el mensaje; los pases de satélites distintos
se planifican por separado.

**Medido en el día de referencia** (`TestOnTheReferenceDay`): tres estaciones
con el receptor de referencia —Castelldefels; Calar Alto (37.2236 N, 2.5461 W,
2168 m; coordenadas del infobox de Wikipedia, altitud confirmada por caha.es,
que no imprime coordenadas); y la OGS de ESA en Tenerife (28.298 N, 16.5118 W,
2400 m; de la página institucional del IAC)—, máscara de 10°, rejilla de 1 s:

| Estación | Pases | Bits por pase (cota finita) |
|---|---|---|
| Castelldefels | 4 | 190 581, 0, 242 404, 0 |
| Calar Alto | 4 | 47 108, 0, 9 817, 0 |
| OGS Tenerife | 2 | 228 851, 333 846 |

Calar Alto está a 596 km y la misma órbita cruza las dos, así que **cada pase
suyo se solapa con uno de Castelldefels**; Tenerife solo se solapa con los dos
pases muertos de las otras dos. Resultado:

| Política | Bits | Pases conservados |
|---|---|---|
| SUM | **1 052 607** | 10 de 10 |
| BEST_AVAILABLE | **995 682** | 4 de 10 |

Con un terminal, la diversidad compró **2.30 veces** los 432 985 bits de
Castelldefels sola; los seis pases descartados —cuatro de ellos muertos, que
chocaban con uno vivo— valían **56 925 bits, el 5.4 %** de la suma. En este día
el greedy coincide con el exacto (los conflictos son por pares y el más rico
gana cada uno), y eso está **medido**, no supuesto
(`test_greedy_happens_to_agree_on_this_day`); la instancia donde difieren es la
de arriba. Y la planificación pesa **bits esperados**: con Castelldefels a
`0.1` de disponibilidad en su primer pase (19 058 esperados contra los 47 108 de
un Calar Alto despejado), el pase va a Calar Alto y la columna certificada dice
lo que ese pase certifica cuando ocurre
(`test_the_schedule_weighs_expected_bits_not_certified_ones`).

### `relay.py`: una identidad que hay que saber antes de leer cualquier número

`trusted_node_relay` recorre los pases de las dos estaciones en orden
cronológico de **fin** —la clave de un pase existe cuando el pase termina,
porque el bloque es el pase y no está completo antes de su última muestra—,
guarda cada clave viva en el almacén de su lado y, cuando el almacén contrario
no está vacío, empareja **primero-entra-primero-sale** y cada emparejamiento es
un evento de entrega.

**La identidad.** Con almacén ilimitado los dos saldos nunca son positivos a la
vez —cuando lo serían, hay emparejamiento—, así que al cerrar la ventana uno de
los dos es cero, y entonces **el total entregado es exactamente
`min(ΣK_A, ΣK_B)`, sea cual sea el orden de los pases**. El orden no cambia
*cuánto*; cambia **cuándo** (la latencia y en qué día UTC caen los bits) y
**cuánto queda varado** a bordo al cerrar la ventana. `TestTheStoreIdentity` lo
aserta con Hypothesis sobre 150 secuencias aleatorias, para que nadie lea el
total como si el orden se lo hubiera ganado. Entradas idénticas devuelven el
total con latencia cero.

**Latencia, definida.** Dos números por entrega, ambos desde el fin del pase
cuya clave se consume hasta el fin del que entrega: `latency_s` es la edad del
bit **más antiguo** entregado (una entrega puede consumir la cola de un pase
almacenado y la cabeza del siguiente; esta es la edad de la cola), y
`mean_latency_s` la media ponderada por bits. Un segundo almacén escrito en
Python plano sin arrays reproduce las tres columnas sobre secuencias aleatorias
(V3, `TestAgainstAHandSimulatedStore`).

**Composición de seguridad: una suma, y por qué una suma.** La clave extremo a
extremo es función de dos claves y falla si cualquiera de las dos no era lo
que su prueba prometía; la probabilidad de «cualquiera» está acotada por la
suma, la **cota de la unión** —el mismo argumento de `composed_security` para
concatenar los bloques de un día—. Se compone sobre los bloques **consumidos**
de cada lado: el día de referencia relevado consigo mismo consume cuatro y es
`4e-10`-seguro; relevado contra su propio primer pase consume uno de cada lado
y es `2·eps` (`test_only_consumed_blocks_count`). Si la suma llega a uno se
rechaza, y hay un test que separa el rechazo propio del relé (dos lados a 0.6,
que por separado son probabilidades y juntos 1.2) del de `composed_security`
sobre un solo lado.

**Medido en el día de referencia** (`TestOnTheReferenceDay`), Castelldefels →
OGS de Tenerife, mismo satélite:

| Evento | Entregado | Consume de | Latencia | Residuo |
|---|---|---|---|---|
| 1 | 190 581 | A pase 1 | 6 114 s | B: 38 270 |
| 2 | 38 270 | B pase 1 | 33 780 s | A: 204 134 |
| 3 | 204 134 | A pase 3 | 5 703 s | B: 129 712 |

Total **432 985 = min(432 985, 562 697)**. Quedan **129 712 bits** del último
pase de Tenerife varados a bordo a medianoche (`WARNING`
`relay.key-stranded-on-board`), y la latencia va de 1.6 a **9.4 horas** —el
segundo evento esperó el hueco diurno en que ninguna estación ve el satélite—.
Contra Calar Alto, cuyos pases terminan a menos de un minuto de los de
Castelldefels, el mismo relé entrega 56 925 bits y la definición de latencia
enseña los dientes: los primeros 47 108 llegan a **59 s**, pero los 9 817
restantes esperan **39 822 s**, porque el segundo pase vivo de Calar Alto
termina **72 s antes** que el segundo de Castelldefels y el almacén FIFO lo
empareja con lo que quedaba del *primero*, once horas viejo. La estación cercana
es rápida y pobre; la lejana, lenta y rica.

**Lo que queda fuera, sin stub:** los enlaces entre satélites. Un segundo
satélite en cualquiera de los dos volúmenes es `DomainError` nombrando la
decisión de 2026-09-10; no hay bandera ni marcador de posición, y hay un test
que aserta que la palabra «ISL» no aparece en ninguna firma ni en `__all__`.
Tampoco se acota el almacén de a bordo —los residuos dicen cuánto tendría que
guardar una memoria— ni se modela el canal clásico del anuncio.

### Lo que esto deja declarado como hueco

1. **La dependencia de pCFLOS con la elevación** (Lund & Shanklin 1972, 1973,
   no abiertos). Sin término angular; cota superior en cada llamada, con aviso.
2. **La ley conjunta de N > 2 estaciones** a partir de correlaciones por pares.
   Cotas, no valor.
3. **La longitud de decorrelación `L`**: sin fuente, sin defecto.
4. **El hueco de reorientación del terminal**: sin fuente, defecto cero.
5. **El conflicto del terminal de tierra** (dos satélites sobre una estación):
   fuera de alcance, rechazado.

### Estado

`src/quoss/system/pcflos.py` (177 sentencias, 56 ramas),
`src/quoss/system/multi_ogs.py` (284, 112) y `src/quoss/system/relay.py`
(196, 76): **100 % de cobertura de líneas y de ramas** en los tres.
`tests/system/test_pcflos.py` (53 tests), `test_multi_ogs.py` (55) y
`test_relay.py` (39), más 10 doctests; `tests/system/reference_stations.py`
es el ayudante que ve el satélite de referencia desde las tres estaciones,
propagando una vez y reutilizando `reference.conditions_at` para que el
receptor sea el mismo de la §27. El ADR de la etapa es el
[0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md).

---

## 30. `scenario/` — el escenario como dato: el contrato que todo lo demás lee

### Qué hace este paquete, para quien llegue nuevo

Todo lo que hay por debajo responde a una pregunta sobre física dado un número en
radianes o en metros. Nadie escribe así un experimento: se escribe «41.275 grados
norte, 1550 nm, 0.75 µrad de jitter, puerta de 1 ns, máscara de 10°». Un
**escenario** es esa descripción completa —satélite, estaciones, óptica,
detector, protocolo, día y paso— en un fichero YAML o JSON, y `scenario/` es lo
que lo convierte **una sola vez** en lo que la física acepta, lo identifica con
un hash, y define la forma del resultado que vuelve. `notes/ROADMAP.md` lo llama
el archivo más importante del proyecto porque decide qué puede decir un usuario;
la [ADR 0014](../docs/adr/0014-scenario-contract-and-provenance.md) recoge las
decisiones.

Es un **dato y no una petición**. SimulCTTC montaba las entradas al vuelo en un
handler HTTP y una época sin fijar «caía silenciosamente al reloj de pared»
(`notes/ROADMAP.md`). Aquí un escenario es un valor congelado, completo y
hasheable: dos personas con el mismo fichero y la misma semilla obtienen los
mismos números, y un resultado lleva dentro el hash de lo que lo produjo.

### Los seis módulos

- **`models.py`** — el esquema, Pydantic v2 con `extra="forbid"`, `frozen=True` y
  `allow_inf_nan=False`. Cada campo lleva la unidad del usuario en el nombre
  (`latitude_deg`, `wavelength_nm`, `pointing_jitter_urad`, `gate_ns`,
  `timing_jitter_fwhm_ps`) y cada modelo ofrece la conversión bajo el nombre de la
  física (`latitude_rad`, `wavelength_m`, `gate_s`, `chain_efficiency`,
  `to_elements()`, `to_protocol()`, `to_security()`, `grid()`, `to_satrec()`).
  Propiedades y no `computed_field`, porque un `computed_field` entra en
  `model_dump` y el fichero volcado no se podría volver a leer bajo `forbid`.
  Cada cota del esquema es el espejo de la del contenedor de física al que
  alimenta (holgura `1e-9` de `TimeGrid.uniform` y de `Bb84DecoyProtocol`,
  `(0, 1)` de `SecurityParameters`, puerta ≤ periodo de `LinkConditions`,
  checksum de `parse_tle`), así que **lo que valida, convierte**: medido con
  Hypothesis, 60 rejillas y 40 órbitas heliosíncronas construidas sin excepción.
- **`defaults.py`** — `reference_castelldefels()`, igual campo a campo al enlace
  de `tests/system/reference.py`, y `ntanos_2021(aperture_m)` para las tres
  estaciones griegas. Los literales van en unidad de usuario (`dead_time_ns=30.0`
  y no `30e-9 * 1e9 = 29.999999999999996`) y un test los ata a las constantes SI.
- **`io.py`** — `load/loads/dump/dumps_scenario`, solo `yaml.safe_load`/`safe_dump`;
  todo fallo es un `ScenarioError` que lista **cada** campo malo con su ruta con
  puntos (`stations.0.latitude_deg`).
- **`hash.py`** — `canonical_json` (claves ordenadas, sin espacios, flotantes por
  `repr`, enums por valor, época con `Z`, sin `name` ni `description`) y
  `scenario_hash` = SHA-256.
- **`result.py`** — `SimulationResult` y sus contenedores como dataclasses
  congelados sobre arrays de solo lectura, con dos serializaciones que van y
  vuelven: `to_dict` (listas, NaN como `null`, JSON estricto) y
  `to_manifest_and_arrays` (manifiesto JSON + `{"clave.con.puntos": ndarray}`
  para el `.npz` de la caché). `Provenance.collect` rellena hash, versión,
  commit de git (o `None` sin excepción), versiones de Python/NumPy/SciPy, semilla
  y hora.
- **`scenarios/*.yaml`** — cinco ficheros comentados línea a línea con la fuente
  de cada valor: el de referencia, los tres de Ntanos, y uno con TLE real de la
  ISS (CelesTrak, 2026-09-13, época 2026-09-13T04:12:47.9Z, pasa el checksum) con
  las tres etapas opcionales activadas para que el esquema completo tenga un
  ejemplo.

### Las decisiones con su número

**Dos campos sin defecto, y un test que lo mantiene.** `channel.zenith_transmittance`
(ADR 0009 hueco 14: la ley de escala está publicada y el número no) y
`passes.minimum_elevation_deg` (ADR 0011 §5: óptimo interior cerca de 8°, el 6.0 %
del día en juego entre 2° y 8°). `TestTheTwoFieldsWithoutADefault` aserta
`is_required()` de los dos y que su descripción cita el ADR.

**Una época ingenua se rechaza con el nombre del defecto.** `time.epoch_utc` tiene
que ser consciente de zona y UTC; una `datetime` sin `tzinfo` es «la época cayó al
reloj de pared» con otro traje, y el mensaje lo dice.

**El hash excluye las etiquetas y clava un valor.** Mismo dato con otro nombre,
mismo hash: renombrar un fichero no repite un día de Monte Carlo. `0.1 + 0.2` y
`0.3` son dobles distintos y hashean distinto (redondear erraría hacia el lado
peligroso); `1` y `1.0` en YAML hashean igual porque el esquema convierte antes de
volcar. El digest de referencia está clavado
(`feafee61257b303a9fdb838e66a981ea4c58c8fad94ec5dfeba7841d53a84227`) como guardia
V4 sobre el **contrato de serialización**, no sobre física: si cambia, toda la
caché queda inalcanzable, y el fallo del test es la instrucción de subir
`SCHEMA_VERSION`.

**La estación lleva el viento r.m.s., no el de superficie — una desviación del
brief, medida.** Bufton (ITU-R P.1621-2 Ec. (5)) convierte 2.3 m/s en **21.018**
m/s, no en los 21.0 del HV 5/7 que la física usa por defecto y el enlace de
referencia usa. El 0.085 % movió el presupuesto de pérdidas de referencia
**6.8e-5 relativo, 0.0028 dB a 10° y 2000 km**
(`TestUnitsConvertOnceAtTheBoundary::test_the_wind_default_is_the_hv57_value_not_the_bufton_conversion`),
suficiente para que el escenario de referencia no reprodujera el enlace de
referencia. `rms_wind_speed_m_s = 21.0`, atado por test a la firma de
`log_irradiance_variance`.

**El presupuesto evaluado desde el escenario y desde las constantes es el mismo a
`1e-12` relativo**, pérdidas y ruido, con cuatro elevaciones
(`TestReferenceCastelldefels::test_the_budgets_evaluate_identically_from_either_source`);
la tolerancia se deriva de que las entradas coinciden a `2^-50` y el presupuesto
tiene números de condición de orden diez.

**Ntanos et al. 2021, releído del PDF.** Del paper: 600 km e inclinación **97.4°**
tal como está impresa (§4.3) —la condición heliosíncrona a 600 km da 97.79°,
medido, 0.39° de diferencia, y se usa la impresa porque es el parámetro del paper—,
coordenadas y alturas de las estaciones (§2), receptor, transmisor, protocolo y
20° (§4.1). Elección de QuOSS, y dicha: RAAN, anomalía, forma circular, época,
ventana. Y el §2 imprime las coordenadas con las etiquetas de latitud y longitud
**intercambiadas** (Skinakas «longitude: 35.2118°» está en Creta, a 35.2 N); se
usan los números bajo las etiquetas corregidas y un test aserta que cada
«longitud» impresa cae en la banda de latitudes de Grecia.

**Un mensaje de error por escenario, no por campo.** Dos errores (un `"e91"` y
una transmitancia de 2.0) salen como `scenario has 2 invalid fields:` seguido de
`protocol.name: …` y `channel.zenith_transmittance: …`; un error de modelo se
reporta en el modelo que lo posee (`orbit.kepler: give exactly one of …`) y uno
de raíz como `<root>`.

**El resultado conserva dtypes al volver, incluso vacío.** Una tabla de pases sin
pases vuelve con `int64` y `bool` donde `np.asarray([])` daría `float64`; el
`.npz` real pasa por `np.savez`/`np.load`. NaN fuera de pase se escribe `null` y
`json.dumps(..., allow_nan=False)` pasa.

### Lo que queda fuera, dicho

- El motor calcula el desplazamiento entre la época de un TLE y la ventana;
  `TleOrbit.epoch_jd` lo da, y `propagate_tle` no acepta otra época por diseño.
- Los contenedores `MonteCarloResults`, `MultiStationResults` y `RelayResults` son
  arrays con las formas del contrato; `system/monte_carlo.py`, `multi_ogs.py` y
  `relay.py` se escriben en paralelo y no se importan.
- Un límite de ida y vuelta, declarado como test: YAML 1.1 trata U+0085 como
  salto de línea y PyYAML lo pliega a un espacio en una **etiqueta**. Fuera del
  hash; ningún campo de física lleva texto.

### Verificación

`tests/scenario/`, **202 tests**, **100 % de cobertura de líneas y de ramas** de
los seis módulos (`models.py` 349 sentencias, `result.py` 372, `io.py` 69,
`defaults.py` 46, `hash.py` 12, `__init__.py` 2). `ruff check`, `ruff format` y
`mypy` (estricto, con el plugin de Pydantic) limpios sobre `src/quoss/scenario` y
`tests/scenario`. Dos propiedades con Hypothesis (rejillas y órbitas; ida y vuelta
YAML/JSON de 40 escenarios). Ficheros: `src/quoss/scenario/{__init__,models,defaults,io,hash,result}.py`,
`scenarios/{reference_castelldefels,ntanos2021_075m,ntanos2021_130m,ntanos2021_230m,tle_example}.yaml`,
`tests/scenario/test_{models,defaults,io,hash,result,scenario_files}.py`,
`docs/adr/0014-scenario-contract-and-provenance.md`.

---

## 31. `io/` — el mundo exterior entra por inyección, y lo que entró se puede reproducir sin red

### Qué hace este paquete, para quien llegue nuevo

Todo lo que hay debajo de `io/` calcula con lo que tiene en memoria. Dos
entradas de un escenario, sin embargo, viven en el servidor de otro: el **TLE**
de un satélite (las dos líneas de 69 caracteres con las que se publican las
órbitas reales, ver §11 y el ADR 0007) y la **cobertura de nubes** sobre una
estación (la fracción del cielo tapada, 0 despejado y 1 cubierto, que
`system/pcflos.py` convierte en probabilidad de que un pase sea utilizable).
Este paquete es el único sitio del proyecto que puede abrir un socket, y está
construido para que nadie más lo necesite:

- `cache.py` — una caché HTTP en disco. Cada URL se guarda en
  `<sha256(url)>.bin` + `.json` (URL, hora de descarga, hash del cuerpo).
  «Content-addressed» quiere decir que el nombre del fichero sale de la URL, así
  que no hay registro que mantener. Tiene un **TTL** (tiempo de vida: una
  entrada más vieja se vuelve a bajar) obligatorio y sin defecto, porque un TLE
  caduca en un día y una serie ERA5 de 2025 no cambia en un año.
- `celestrak.py` — un TLE del API GP de CelesTrak, pasado por
  `orbits.tle.parse_tle` (longitud, prefijo, checksum, error de SGP4) antes de
  devolver nada.
- `openmeteo.py` — cobertura horaria de nubes del archivo histórico de
  Open-Meteo, que sirve el reanálisis **ERA5** de ECMWF: no una observación en
  la estación, sino un modelo meteorológico re-ejecutado sobre el pasado y
  ajustado a todas las observaciones, en una rejilla de ~25 km.
- `snapshots.py` — copias offline versionadas de lo anterior, con manifiesto y
  hash, para que la demo no dependa del wifi (§5 de la guía).
- `export.py` — un `SimulationResult` escrito a un directorio con
  `manifest.json`, CSV por pase/día/estación, `arrays.npz` y, opcionalmente,
  Parquet.
- `stations.py` + `data/ogs.yaml` — el catálogo de estaciones ópticas, cada
  una con la fuente de sus coordenadas.

### La decisión que organiza todo: ningún test abre un socket, y uno lo demuestra rompiéndolo

Toda función que podría hacer una petición recibe un `fetch` inyectado; la
real (`urllib_fetch`, sobre `urllib.request`, sin dependencia nueva) es solo el
defecto. `tests/io/test_cache.py::TestTheSuiteIsOffline` sustituye
`socket.socket` por una función que lanza `OSError`, ve que `urllib_fetch`
contra CelesTrak falla con `DataError`, y después ejecuta con `fetch` falsos
**todos** los caminos del paquete —`fetch_tle`, `fetch_cloud_cover`, los dos
adaptadores de snapshot, el catálogo y un export completo—. Si alguien mete
una petición real en cualquiera de ellos, ese test falla en CI el mismo día.

### Lo que se decidió, con su número

1. **El TTL se prueba moviendo el reloj, no durmiendo.** `HttpCache` recibe
   `now()`; medido en `TestTtl` con `ttl_s=3600`: a 3599 s es acierto (INFO
   `io.cache-hit`, `fetch` llamado una vez), a 3600 s es fallo (dos veces).
2. **Una entrada caducada no se sirve sin pedirlo.** Si `fetch` falla, el
   defecto es `DataError` con URL y estado HTTP. Solo con `allow_stale=True`
   se usa la copia, y queda un `WARNING` `io.cache-stale-fallback` con su edad.
   Es la comodidad estándar de toda caché, y es la que produce figuras sobre
   un TLE de hace tres semanas sin que nadie lo vea.
3. **La versión de un TLE es su época.** `TleRecord.data_version` es
   `"25544@2461296.67555434"`: ni «el TLE de la ISS» (se reajusta varias veces
   al día) ni la hora de descarga identifican un conjunto de elementos; la
   época, en las columnas 19-32 de la línea 1 con resolución de `1e-8` día, sí.
4. **Un `null` en la serie de nubes es `DataError`, no interpolación.** La
   serie de referencia va 0 → 39 → 82 → 14 % en tres horas consecutivas: no
   hay cota para una interpolación, y sin cota no hay `DEGRADED` posible.
5. **La celda no es el telescopio, y se registra.** Para Castelldefels
   (41.2750 N, 1.9875 E) Open-Meteo sirvió la celda de 41.3005 N, 2.0660 E, a
   **7.2 km** (INFO `io.openmeteo-grid-offset`, medido en
   `tests/io/test_openmeteo.py::TestGridOffset`). Qué hacer con esa distancia
   es de `pcflos.py`; aquí solo se deja escrito.
6. **El API no dice qué reanálisis sirvió la celda**, así que
   `CloudCoverSeries.model` lleva `open-meteo-archive:best_match` y la versión
   de datos es `open-meteo-archive:<inicio>:<fin>:fetched=<fecha>`. No se
   escribe «ERA5» donde el código no puede comprobarlo.
7. **Un snapshot con hash que se comprueba al cargar.** `sha256` del JSON
   canónico del payload; `load_snapshot` lo recalcula y lanza `DataError` si
   no coincide. Lo que cierra es la edición a mano de un número «para que la
   demo salga». Y un payload no descargado tiene que llamarse `synthetic_*` y
   decirlo en la nota: `save_snapshot` rechaza las dos combinaciones cruzadas.
8. **Los dos snapshots entregados son descargas reales**, con `curl` el
   2026-09-13 a las 16:16:24 UTC, HTTP 200: `tle/iss_zarya` (ISS, época
   2026-09-13 04:12:48 UTC, cuerpo verbatim con CRLF) y
   `cloud_cover/castelldefels_2025-01-01_02` (48 horas, sin huecos, de 0 a
   100 %). Ninguno es sintético. Usar uno deja INFO `io.snapshot-used`.
9. **El export escribe un directorio que se describe a sí mismo.**
   `manifest.json` lista cada fichero con su SHA-256; `manifest.json` +
   `arrays.npz` es exactamente lo que `SimulationResult.from_manifest_and_arrays`
   recibe, y el test lo reconstruye y compara `to_dict()` entero. Los
   flotantes van a CSV por `repr` (ida y vuelta exacta; medido sobre 50 tablas
   generadas por `hypothesis`), NaN como celda vacía. Sin `pyarrow`,
   `"parquet"` es `ConfigurationError("install quoss[export]")`, no un formato
   que se salta.
10. **Una apertura que no está en la fuente es `null`.** `data/ogs.yaml` lleva
    Castelldefels (de `tests/system/reference.py`), la OGS de ESA en Tenerife
    (página del IAC: 28.298 N, 16.5118 W, 2400 m, 1.0 m), Matera y Graz
    (páginas del ILRS, que dan coordenadas pero no la apertura). Para estas dos
    `to_station_spec_kwargs()` lanza `DataError` hasta que el escenario pase la
    suya. Las páginas de ESA para la OGS devolvieron 404; la del IAC no.

### Lo que queda fuera

- `DEFAULT_SNAPSHOT_ROOT` y `DEFAULT_CATALOGUE_PATH` se resuelven a
  `<repo>/data/...` relativo al fichero fuente: vale en un checkout, **no** en
  un wheel instalado. Todo acepta `root`/`path` explícitos; mover `data/` dentro
  del paquete es decisión de empaquetado pendiente.
- Que `null` sea una hora ausente en Open-Meteo es la convención general del
  API; la documentación no lo escribe. Se rechaza en cualquier caso.
- Space-Track, CDS directo, NetCDF: fuera, ver ADR 0015.

### Verificación

`tests/io/`: 197 elementos recogidos (186 tests con parametrizaciones + 11
doctests), **100 % de líneas y ramas** en los siete módulos
(`--cov=quoss.io --cov-branch`). `ruff check`, `ruff format --check` y `mypy`
limpios sobre `src/quoss/io` y `tests/io`. Property-based en la clave de caché
y en las idas y vueltas CSV/npz. El export se prueba contra el
`SimulationResult` real de `scenario/result.py` (dos pases, un día, una
estación, con y sin Monte Carlo), en los cuatro formatos, leyendo cada fichero.

### Ficheros

`src/quoss/io/{__init__,cache,celestrak,openmeteo,snapshots,export,stations}.py`,
`data/ogs.yaml`, `data/snapshots/tle/iss_zarya.json`,
`data/snapshots/cloud_cover/castelldefels_2025-01-01_02.json`,
`tests/io/test_{cache,celestrak,openmeteo,snapshots,export,stations}.py`,
`docs/adr/0015-external-data-isolation-and-snapshots.md`.

---

## 32. Dos tests que informaban de su entorno en vez de del código

> **Nota de orden:** esta entrada y la de `tests/e2e/` llevan las dos el número 32
> porque salen de dos ramas hermanas de la misma auditoría. Al integrar, la que
> entre segunda pasa a 33.

Dos arreglos pequeños y de la misma familia: un test falla —o no falla— por algo
que no es el código que prueba. Ninguno de los dos toca física.

### El primero: una figura asertada por las etiquetas que eligió matplotlib

`tests/viz/test_plots.py::TestSkyTrack::test_one_track_per_pass_at_the_zenith_angle`
comprobaba la escala radial del gráfico de traza celeste así:

```python
assert [(tick.get_loc(), tick.label1.get_text()) for tick in ax.yaxis.get_major_ticks()] == [
    (30.0, "60°"), (60.0, "30°"), (90.0, "0°"),
]
```

**Qué hace ese gráfico, para quien llegue nuevo.** Es un gráfico polar del cielo
visto desde la estación: el ángulo es el acimut (por dónde) y el **radio es el
ángulo cenital** (cuánto le falta al satélite para estar justo encima). Las
etiquetas de los anillos, en cambio, son la **elevación** — lo habitual en
astronomía—, así que radio y etiqueta corren al revés: un anillo a `r = 30°` del
centro está a `60°` sobre el horizonte. La relación es `etiqueta = 90 − r`.

**Por qué esa asserción estaba mal escrita.** El gráfico pide **cuatro** anillos
(0, 30, 60, 90); cuántos se dibujan lo decide matplotlib, no el código: su
`RadialLocator` polar descarta el tick que cae exactamente en el origen —aquí
`r = 0`, el cenit— y **si lo hace ha cambiado entre versiones**. Una lista fija
de etiquetas convierte una actualización de matplotlib en un fallo rojo con la
figura perfectamente correcta: el test informa de su dependencia y no del código.

**Lo que aserta ahora** es la propiedad que tiene que valer en cualquier versión
porque sin ella la figura se lee mal: cada anillo dibujado está en un radio del
conjunto pedido y lleva la etiqueta `90 − r`, y hay **al menos dos** anillos
(con uno solo no hay escala contra la que interpolar). Comprobado por mutación:
invertir la lista de etiquetas en `plots.py` —el error real que esto protege,
porque nadie lo ve a ojo en un polar— hace fallar el test.

El comentario de `plots.py` también afirmaba como hecho que el anillo `r = 0`
«nunca se dibuja». Es el comportamiento de **una** versión, no una propiedad, y
ahora lo dice así.

### El segundo: un `importorskip` colocado donde no se ejecuta

`quoss` instala sin `quoss[export]` a propósito: Parquet necesita `pyarrow`, que
son 40 MB y no es una dependencia de física. Sin ese extra,
`tests/io/test_export.py` daba **7 errores** — no saltados, errores.

`test_parquet_reads_back` **ya tenía** su `pytest.importorskip("pyarrow.parquet")`.
No servía de nada: el *fixture* de la clase ya había llamado a `export_result` con
`"parquet"` entre los formatos, que sin `pyarrow` levanta `ConfigurationError`, y
un fixture que falla es un **error** de todos los tests de la clase — incluidos
los seis que solo leen CSV, npz y JSON y no tienen nada que ver con Parquet.

**La lección, que generaliza:** una guarda de dependencia tiene que estar **aguas
arriba** de lo que la necesita, no al lado. Aquí eso significa partir el fixture:
`exported` exporta `CORE_FORMATS = ("json", "csv", "npz")`, cuyos escritores no
necesitan más que numpy y la biblioteca estándar; `exported_with_parquet` añade
Parquet y hace `importorskip` antes de exportar nada.

Medido: sin `pyarrow`, de **32 pasan y 7 errores** a **38 pasan y 2 saltados**.
Con `pyarrow`, `src/quoss/io/export.py` sigue al **100 %** de líneas y ramas —los
caminos de Parquet los cubren los dos tests que ahora dependen del fixture nuevo—
y hay un test más que antes, porque la lista de ficheros y sus SHA-256 se
comprueban dos veces: la de los formatos del núcleo y la de los ocho ficheros.

### Lo que esto **no** era

El diagnóstico de partida decía que `TestSkyTrack` **fallaba** en el árbol. En
`matplotlib 3.11.1` no falla: pasa. Lo que estaba mal no era el resultado sino la
forma de la asserción, y por eso se arregla igual — un test que hoy pasa por la
versión que hay instalada es el mismo defecto un día antes de manifestarse.

### Verificación

Suite completa: **3 230 tests** (uno más que los 3 229 de la línea base de esta
rama). `ruff check`, `ruff format --check` y `mypy` limpios. Cobertura con ramas:
`io/export.py` y los cuatro módulos de `viz/` al **100 %**. Sin `pyarrow` en el
entorno, `tests/io/test_export.py` da 38 pasan y 2 saltados y ningún error.

### Ficheros

`tests/e2e/test_reference_scenarios.py` (nuevo),
`docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md` (nuevo),
`src/quoss/channel/{atmosphere,turbulence,beam,link_budget}.py`,
`src/quoss/scenario/defaults.py`, `src/quoss/viz/plots.py`,
`src/quoss/validation/__init__.py`, `scenarios/reference_castelldefels.yaml`,
`tests/system/reference.py`, `tests/scenario/test_defaults.py`, `tests/viz/test_plots.py`,
`notes/ROADMAP.md`, `notes/INCONSISTENCIAS.md`.

---

## 33. El README decía «Etapa 3 en curso» con las etapas 0-6 en el árbol

Una entrada corta y sin física: el bloque de estado del README describía un
proyecto que ya no era este.

**Qué decía:** «Estado: **Etapa 3 — `system/`**, en curso», con `passes.py` y
`key_volume.py` como lo último y `monte_carlo.py` como lo siguiente.

**Qué hay:** las etapas **0 a 6 cerradas** —`core/`, `orbits/`, `channel/`,
`qkd/`, `system/` entero, `scenario/`, `engine/` e `io/`—, más `viz/` y
`validation/` a medias. `run(scenario) → result` funciona de punta a punta.

**Por qué es un defecto y no una nota desactualizada.** El bloque de estado es lo
primero que lee cualquiera que evalúe el proyecto, y **subestimarse tiene el mismo
coste que exagerar**: un lector que cree que falta desde la etapa 3 no busca el
motor, no encuentra `scenarios/`, y concluye que no puede correr nada. La regla
del proyecto —«prohibido degradar en silencio»— es sobre números, pero un estado
falso es la misma clase de afirmación sin comprobar.

### Lo que el bloque nuevo dice, y por qué en ese orden

1. **Una tabla de tres filas: cerrado, a medias, no existe.** Con los `.gitkeep`
   nombrados, porque un directorio vacío en el árbol parece código.
2. **«Lo que se puede afirmar hoy», separado de «lo que está implementado».** Son
   cosas distintas y el proyecto entero descansa en esa distinción: se puede
   afirmar la clave por pase con la cota finita aplicada al bloque correcto
   (ADR 0011) y que el motor no añade nada al orquestarla (ADR 0016); **no** se
   puede afirmar que los números estén validados contra literatura, porque eso es
   la etapa 8 y es justo la que está a medias.
3. **Las dos cifras del día de referencia, las dos, con su causa.** 433 442 por
   `run()` y 432 985 por el *fixture* de la etapa 3; ver §32.
4. **El hueco que hace de todo lo anterior una cota superior.** `zenith_transmittance`
   vale `1.0` en el escenario de referencia porque ninguna fuente abierta publica
   la extinción (hueco 14 del ADR 0009). Sale en el README y no solo en el ADR,
   porque es la advertencia que tiene que viajar **con** la cifra.
5. **Un ejemplo de uso que se ejecuta**, en vez del `quoss.__version__` que había.
   Los tres números que imprime están comprobados corriéndolo.

### El defecto que apareció al escribirlo

`tests/viz/test_plots.py` importa `matplotlib` en la cabecera del módulo, así que
**sin el extra `viz` la recogida de `tests/viz/` falla en vez de saltarse**. El
paquete sí degrada bien —`quoss.viz` levanta `ConfigurationError` diciendo qué
instalar—; es el test el que no. Es el mismo defecto que el de `pyarrow` en
`tests/io/test_export.py`, con la misma forma: **la guarda de dependencia tiene
que estar aguas arriba de lo que la necesita.** Queda escrito en el README como
pendiente en vez de arreglado aquí, porque esta entrada es de documentación.

### Ficheros

`README.md`.
## 34. Doppler y point-ahead salen al resultado — dos requisitos, no uno

> ADR de la entrada: [0019](../docs/adr/0019-acquisition-in-the-result.md).

### Qué son estas dos magnitudes, para quien llegue nuevo

**Doppler.** Un satélite en LEO se acerca y se aleja a varios km/s, y eso
desplaza la frecuencia de la portadora que llega a la estación: acercándose la
sube, alejándose la baja. A 1550 nm —una portadora de 1.934e14 Hz— cada km/s de
velocidad radial desplaza **645 MHz**, y un pase real llega a **±4.3 GHz**.

Un receptor coherente tiene **dos** números frente a eso, y la entrada entera
existe porque confundirlos es fácil:

- el **rango de captura**, cuánto se puede haber ido la portadora y aún así
  encontrarla;
- la **velocidad de seguimiento**, cuán rápido puede barrer el lazo una vez
  enganchado.

Un pase puede caber holgadamente en el primero y dejar atrás el segundo, y
entonces el síntoma es un enganche que aguanta todo el pase y se cae cerca del
horizonte. Es la forma del problema que tuvo TBIRD en órbita.

**Point-ahead.** La luz tarda en ir y volver y el satélite se mueve mientras
tanto, así que un terminal monostático no apunta a donde *ve* al otro extremo
sino a donde **estará**. En LEO ese adelanto son decenas de microradianes, del
orden del propio ancho del haz.

### El defecto: se calculaban y no salían

`orbits/geometry.py` ya devolvía `range_rate_km_s` y `point_ahead_angle_rad`, y
`system/passes.py` ya troceaba la geometría por pase. **Ninguna de las dos salía
del motor:** ni `SeriesResults` ni `PassResults` las llevaban. Quien quisiera
saber qué le pide un pase a su transceptor tenía que rehacer la cadena a mano
fuera del simulador.

### Lo que hay ahora

**Cuatro series** sobre la rejilla entera —velocidad radial, desplazamiento
Doppler, su derivada y el ángulo de point-ahead— y **cuatro columnas por pase**:
`peak_one_sided_doppler_hz`, `peak_doppler_slew_hz_s`, `max_point_ahead_angle_rad` y
`min_point_ahead_angle_rad`.

### Las cifras del día de referencia

Castelldefels, 0.75 m, SSO a 700 km, máscara de 10°, 1550 nm:

| Pase | Culminación | Captura: máx \|Δf\| | Seguimiento: máx \|dΔf/dt\| |
|---|---|---|---|
| 1 | 52.9° | 4.19 GHz | 37.9 MHz/s |
| 2 | 17.7° | 2.85 GHz | 19.2 MHz/s |
| 3 | **58.8°** | **4.27 GHz** | **41.5 MHz/s** |
| 4 | 14.2° | 2.23 GHz | 16.8 MHz/s |

Leído como requisito: un transceptor con menos de **±4.3 GHz** de captura no
engancha el mejor pase de este enlace en su horizonte, y uno cuyo lazo no barra
**42 MHz/s** no lo mantiene ahí.

Y el point-ahead va de **24.685920 a 50.652309 µrad** — un factor dos **dentro de
un solo pase**, que es por lo que se reporta el recorrido y no solo el pico: un
terminal con un adelanto fijo se equivocaría en 26 µrad en un extremo.

### Las decisiones, con su número

1. **Dos columnas y no una.** La tentación es reportar solo el pico de |Doppler|,
   que es el número grande; es la mitad de la especificación, y no la que falla
   tarde. **Y lo que este día no demuestra:** aquí las dos ordenan los pases igual
   (3 > 1 > 2 > 4), porque a las dos las gobierna cuánto se acerca el pase. Es un
   hecho sobre estos cuatro pases, no una ley.
2. **El extremo está en los bordes, no en la culminación**, y eso explica por qué
   un problema de Doppler es un problema de *final* de pase: en la culminación el
   satélite atraviesa la línea de visión y la velocidad radial pasa por cero
   (|Δf| baja a 0.010-0.032 GHz), mientras los extremos caen en el horizonte —
   donde el enlace es peor. El receptor trabaja más justo donde menos señal tiene.
3. **La portadora se deriva, no se configura.** `f0 = c / λ` del transmisor del
   escenario; **no hay** campo `carrier_frequency_hz`. Un campo aparte permitiría
   reportar el Doppler de una portadora que el escenario no emite, y nada lo
   vería. Consecuencia que conviene tener escrita antes de la etapa 2.2 de CLAU:
   una bajada clásica a otra longitud de onda es una **segunda** portadora y esta
   serie no es esa.
4. **Se llevan la velocidad radial *y* el Doppler, redundantes a propósito.** Uno
   es la geometría sin suposiciones; el otro es esa geometría comprometida con una
   portadora, y es el número en el que se escribe un rango de captura. Llevar solo
   el primero obliga a cada lector a multiplicar con su propia c y su propio
   signo; llevar solo el segundo entierra la portadora en una columna que nadie
   puede deshacer.
5. **La derivada es numérica y lo que cuesta está medido.** `np.gradient` con los
   instantes explícitos (rejilla no uniforme incluida). No analítica: la
   aceleración radial exacta necesita el modelo de fuerzas y un `LookAngles`
   lleva posiciones y velocidades. Coste: el mayor |dΔf/dt| por pase es
   **41.547201 MHz/s** a 1 s y **41.549130 MHz/s** a 0.1 s, **46 ppm**. Y se
   diferencia la **rejilla entera**, no cada pase: una derivada tomada dentro de
   un pase vería su borde como un extremo y daría una diferencia lateral justo en
   el horizonte, que es el instante del que trata.
6. **Las series geométricas están definidas en todas partes y el canal no.** El
   canal sigue siendo `NaN` fuera de un pase; estas cuatro son finitas en las
   86 401 muestras. La asimetría es una afirmación: un satélite tiene posición
   aunque el enlace no valga la pena puntuarlo, y una pregunta de adquisición se
   hace sobre el trozo de cielo que la etapa de clave se niega a puntuar.
7. **Los extremos por pase son cotas, y se dice cuánto.** `segment_max` reduce
   sobre las muestras **dentro** del pase, y un pase empieza entre muestras. El
   mayor |Doppler| por pase es 4.272427 GHz a 1 s y 4.273114 GHz a 0.1 s:
   **160 ppm** de cota. Misma honestidad que `sampled_culmination_elevation_rad`.
8. **`segment_max` y `segment_min` son reducciones con nombre.** `segment_sum`
   era la reducción de un **rendimiento** (la clave de un pase es la integral de
   su tasa); un **requisito** no se integra, se maximiza. Son **con signo** —el
   máximo de una serie con signo no es el de su módulo, y el Doppler va de un azul
   grande a un rojo grande— así que el llamante escribe `np.abs`. Y `segment_min`
   existe en vez de `-segment_max(-x)` porque ese idioma se equivoca de signo a la
   tercera llamada. Un pase sin muestras devuelve `±inf`, no cero.

### Lo que queda fuera

- **No hay campo de rango de captura en el escenario, y por tanto no hay aviso.**
  El resultado dice lo que el pase exige y el lector lo compara con su
  transceptor. Un `receiver.doppler_capture_range_hz` opcional que levante un
  `WARNING` al salirse encaja con «prohibido degradar en silencio» y es el paso
  siguiente natural; un campo del escenario es un compromiso del contrato
  (ADR 0014) y merece su propia decisión.
- **Segunda portadora para la bajada clásica** (decisión 3): etapa 2.2 de CLAU.
- **El point-ahead no lleva presupuesto de error propio.** Es el ángulo que la
  geometría pide, no el que un actuador entrega.

### Verificación

Suite **3 289 tests** (eran 3 262 al empezar la rama). `ruff check`,
`ruff format --check` y `mypy` limpios. Cobertura con ramas al **100 %** en todo
lo tocado: `orbits/geometry.py`, `system/passes.py`, `scenario/result.py`,
`engine/pipeline.py`, `io/export.py`. Las columnas nuevas viajan solas a CSV,
Parquet, `npz` y JSON porque `io/export.py` construye las tablas del manifiesto —
solo hubo que actualizar las cabeceras que los tests fijan.

Tests nuevos: `TestDopplerRate` (V1 contra la derivada exacta de un rango
cuadrático, que separa la fórmula de la discretización; el signo contra la imagen
física; la integral de la derivada contra el salto del desplazamiento; rejilla no
uniforme; seis entradas rechazadas), `TestTheSegmentExtrema`,
`TestTheAcquisitionStage`, y dos clases nuevas del puente e2e que comparan las
cuatro series y las cuatro columnas con la cadena a mano por **igualdad exacta**.

### Ficheros

`src/quoss/orbits/geometry.py`, `src/quoss/system/passes.py`,
`src/quoss/scenario/result.py`, `src/quoss/engine/pipeline.py`,
`docs/adr/0019-acquisition-in-the-result.md` (nuevo),
`tests/orbits/test_geometry.py`, `tests/system/test_passes.py`,
`tests/engine/test_pipeline.py`, `tests/e2e/{oracle,test_reference_scenarios}.py`,
`tests/io/test_export.py`, `tests/scenario/test_result.py`, `tests/viz/builders.py`.

---

## 35. Literales que solo valían en una máquina, y un desvanecimiento conjunto que mentía con apuntado despreciable

Tres arreglos de la ronda anterior y un defecto nuevo del camino compartido,
encontrado al construir el camino horizontal (§36).

### T1 — Dos tests fallaban en otra máquina, y no eran un fallo del motor

**Qué pasó.** En `72590a5` con numpy 2.4.4, la suite dio 2 fallos en
`tests/e2e/test_reference_scenarios.py`: `ENGINE_ASYMPTOTIC_DAY_BITS` y el
asintótico de la etapa 3, por **9 y 8 ULP** (1.1e-15 relativo). Un ULP, *unit in
the last place*, es la distancia entre un double y el siguiente: en 3.78 millones
son 4.7e-10.

**Por qué no era un fallo real.** El docstring del fichero defendía la igualdad
exacta con un argumento correcto —la misma función con los mismos argumentos
devuelve los mismos doubles— que solo cubre **ruta contra ruta en un proceso**.
Un literal escrito a mano es otra cosa: es un *golden* entre máquinas, y el
estándar IEEE 754 obliga a redondear correctamente `+ − × ÷ √` pero **no** `exp`,
`log`, `pow` ni `erf`. Dos bibliotecas conformes pueden devolver dobles vecinos.
La prueba de que era eso: en la otra máquina las aserciones ruta contra ruta
pasaban, y en esta no se reproduce el fallo ni con numpy 2.4.4, ni con 2.4.6, ni
apagando los núcleos SIMD de x86. Es la plataforma.

**Lo que asierta ahora.** Dos clases, separadas en el docstring:

- **Ruta contra ruta:** `==`, como estaba. Es lo que sostiene «el motor no añade
  nada».
- **Literal contra cálculo:** `assert_matches_literal`, con una cota **derivada**:

  `cota = 2 · u · ε · κ · (n + G) + (N − 1) · ε`

  con `u = 1` ULP por llamada elemental (lo que documentan las `libm`), `n = 140`
  sitios de llamada **contados del código fuente por el propio test**, `G = 740`
  la cancelación de `1 − exp(−x)` en el término geométrico en la muestra más
  baja, `κ = 1.064` la sensibilidad de la clave a la transmitancia **medida** por
  diferencia finita, y `N = 1 800` muestras sumadas en otro orden.

**Ejemplo con números.** Da **8.15e-13 relativo: 3.1e-6 bits, 6 618 ULP**. Los
9 ULP observados caben setecientas veces; un bit de error no cabe ni de lejos, y
el test lo comprueba en las dos direcciones.

**Los enteros se quedan exactos, demostrado.** La clave finita es `floor` de un
real, así que solo cambia si ese real está a menos del error de un entero.
`test_no_finite_literal_sits_near_a_floor_boundary` rehace el valor sin redondear
desde las columnas de la cota y mide: el pase más cercano está a **0.039 bits**
(190 807.961) contra **5.9e-7 bits** de error posible.

**Lo que la cota no modela:** la contracción FMA (un compilador que fusiona
`a·b + c`). Si una plataforma la excede, el mensaje dice por cuántos ULP.

### El barrido de la misma clase de defecto

Dos barridos. Uno busca literales de ≥ 12 cifras significativas en `tests/` y
`src/`: **78**. Otro busca, por AST, comparaciones `==` contra literales no
diádicos —que necesitan redondeo para ser un double— y, en los doctests, salidas
que son un float sin formatear: **118** líneas. Clasificados a mano:

| Dónde | Cuántos | Veredicto |
|---|---|---|
| `tests/e2e/test_reference_scenarios.py` | 2 | **Mismo defecto.** Arreglados arriba |
| `src/quoss/core/units.py`, doctests de `10 ** ±4.5` | 3 | **Mismo defecto.** El valor exacto está a 0.29 ULP del double de esta máquina: basta una `pow` a 0.71 ULP para imprimir otra cifra 17. Ahora con 12 cifras |
| `src/quoss/core/units.py`, doctests de `10 ** -3` | 2 | Mismo defecto, marginal (haría falta 0.90 ULP). Cambiados igual |
| Constantes contra el literal del que salen, parseo de JSON/TLE, entradas guardadas | ~100 | No es el defecto: no hay cálculo en medio |
| `deg_to_rad`, divisiones enteras (las `0.047619…` del digest), `exp(0)` | resto | No es el defecto: aritmética que IEEE redondea correctamente |

**El digest del escenario es portable:** sus floats largos son `1/21`, `16/21` y
`4/21`, divisiones que el estándar obliga a redondear igual en todas partes.

### Que no vuelva a pasar en silencio

Job nuevo de CI, `portability`: la suite en **macOS arm64** (otra `libm` y los
núcleos NEON de numpy) y en **numpy 2.0.2 con Python 3.11** (la numpy más antigua
que acepta la scipy del lock). La segunda se verificó aquí antes de añadirla:
**3 408 passed**. La primera no se puede verificar sin empujar la rama.

### El defecto nuevo: `combined_fade_db` con apuntado despreciable

**Qué es.** El margen de desvanecimiento conjunto es el cuantil de la suma de dos
desvanecimientos: uno exponencial (apuntado, tasa `a = γ²/4.343`) y uno gaussiano
(escintilación). Su función de distribución tiene un término cuyo exponente es la
diferencia de dos números de tamaño `(a·s)²/2`.

**Por qué fallaba.** En la bajada de referencia `γ ≈ 4.4` y no pasa nada. En un
enlace horizontal el haz es ancho frente a su jitter, `γ` va de decenas a miles,
y esa diferencia es cancelación catastrófica: los últimos bits del exponente son
ruido y `exp` del ruido es un número que parece bueno.

**Ejemplo con números** (antes → ahora → escintilación sola, que es la respuesta):

| `γ` | `σ²` | antes | ahora |
|---|---|---|---|
| 1e5 | 0.5 | `RuntimeWarning: overflow` | 8.2298 dB |
| 1e10 | 1e-4 | **1.602 dB** | 0.1012 dB |
| 1e30 | 0.5 | **124.9 dB** | 8.2298 dB |

**El arreglo es una identidad, no una aproximación:**
`exp(−a(l−m) + a²s²/2) · Φ(z − as) = ½ · erfcx((as − z)/√2) · exp(−z²/2)`, sin
cancelación en ningún sitio, usada donde `as ≥ z`; donde no, la forma original ya
es segura. En la bajada de referencia no cambia nada que un doctest vea (1.668 dB
sigue siendo 1.668). Y `γ = +∞` es ahora un valor legal: el límite «sin
desvanecimiento de apuntado».

**Y el que lo destapaba desde el otro lado:** `equivalent_beam_radius_m` dividía
por `exp(−v²)`, que se hace cero cuando la lente es más de ~21 radios de haz. Un
haz de 1 mm en una lente de 25 mm, un banco cualquiera. Ahora devuelve `+inf`
pasado `v² = 700`, que es el límite de la propia Ec. (9), y el aviso lo dice.

### T2 — La línea sin cubrir de la ronda anterior

`engine/pipeline.py:1015`: ventana de captura declarada y cero pases.
`TestTheDeclaredCaptureRange::test_with_no_pass_there_is_nothing_to_check_and_the_run_says_why`.
Una ejecución de 600 s que empieza sobre el ecuador no ve ningún pase: con
ventana declarada la etapa de adquisición no registra nada —no hay nada que
contrastar, y `passes.none-found` ya dice por qué—; sin ventana, el INFO sale
igual y lleva `largest_excursion_hz = None`, no `0.0`, porque cero se leería como
una excursión medida de cero hercios.

### T3 — Que un repinchado del digest se distinga de una deriva

`tests/scenario/test_hash.py` lleva ahora `DIGEST_HISTORY`: cada valor que ha
tenido el digest, con fecha, caso (1: cambia el significado y sube
`SCHEMA_VERSION`; 2: campo opcional nuevo, no sube), y los campos que lo movieron.
**Y un repinchado de caso 2 se demuestra, no se afirma:** el test borra de la
forma canónica de hoy los campos que nombra, del más nuevo al más viejo, y exige
que el SHA-256 vuelva a ser el anterior. Borrar
`receiver.doppler_capture_range_hz` da `feafee61…`, el digest del 2026-09-13, hasta
el último dígito. Una deriva que no nombra campo, o que nombra el equivocado, no
lo reproduce; hay un control negativo que lo comprueba.

### Verificación

Suite **3 478 passed** (eran 3 408 en `72590a5` en esta máquina, que tiene
`pyarrow`; en una sin él son 2 skipped), con cobertura de líneas y ramas al
**100 %** en todo `src/quoss` — incluida la línea 1015 de `engine/pipeline.py`.
`ruff check`, `ruff format --check` y `mypy` limpios. **La misma suite, con el
código de esta entrada, en Python 3.11 + numpy 2.0.2: 3 478 passed**, que es la
configuración del job nuevo de CI. El job de macOS arm64 no está verificado: no
se puede sin empujar la rama.

Ficheros: `.github/workflows/ci.yml`, `src/quoss/channel/{link_budget,pointing,__init__}.py`,
`src/quoss/core/units.py`, `src/quoss/channel/horizontal.py` (nuevo, §36),
`tests/e2e/test_reference_scenarios.py`, `tests/scenario/test_hash.py`,
`tests/engine/test_pipeline.py`, `tests/channel/{test_link_budget,test_pointing}.py`,
`tests/channel/test_horizontal.py` (nuevo, §36), `tests/golden/README.md`,
`docs/adr/0009-citation-policy.md`, `docs/adr/0021-horizontal-path.md` (nuevo),
`notes/INCONSISTENCIAS.md`.

---


---

## 36. Camino horizontal — presupuesto y QBER de un banco y de un enlace de unos kilómetros

Decisión en el [ADR 0021](../docs/adr/0021-horizontal-path.md).

### Qué es y por qué hacía falta

Un banco con emulador (GE-0b) y un enlace horizontal (GE-1) tienen `C_n^2`
**constante** a lo largo del camino y **no tienen elevación**. Todo el canal de
QuOSS eran integrales inclinadas sobre el perfil HV 5/7, así que no servía para
dimensionar lo primero que se va a montar. Y no vale el inclinado con un ángulo
pequeño: a 0.1° la fórmula integra 11 000 km de línea y da **2.1e4 veces** la
varianza de un kilómetro horizontal con el mismo aire de suelo.

### Lo que hay

`channel/horizontal.py`:

- `plane_wave_rytov_variance` — ITU-R P.1814 Ec. (8): `1.2285 C_n^2 k^(7/6) L^(11/6)`
  en Np².
- `horizontal_point_log_irradiance_variance` — plana o esférica (Kaushal &
  Kaddoum Ec. (9), `0.5 …`), con el aviso de régimen débil.
- `horizontal_aperture_averaging_factor` — Kaushal & Kaddoum (20)/(21).
- `horizontal_log_irradiance_variance` — lo anterior multiplicado.
- `horizontal_loss_budget` — el mismo `LossBudget` que la bajada, por la misma
  función de ensamblado.

**La receta de cuatro llamadas** para ir de «longitud, `C_n^2`, diámetros» a QBER
y clave es `tests/channel/test_horizontal.py::ge1_key`: `horizontal_loss_budget` →
`downlink_noise_budget` (que no tiene geometría dentro; en un banco, radiancia
cero) → `LinkConditions` → `Bb84DecoyProtocol.key_rate`.

### Cómo se comprueba

- **V2:** las seis celdas ópticas de la Tabla 4 de P.1814 (1 km; 0.98 y 1.55 µm;
  `C_n^2` = 1e-16, 1e-14, 1e-13) a sus dos decimales.
- **Entre fuentes:** P.1622 (4a) tumbada da 1.2289 contra 1.2285 (3.7e-4, cota
  4.4e-4); Kaushal & Kaddoum imprime 1.23 (1.3e-3, cota 4.1e-3); P.1622 (6)–(7)
  tumbadas dan un promediado a 0.67 % de Churnside (cota 4.5 %), y confirman la
  lectura en micrómetros de su 1.1e7.

### Régimen débil, y el cruce con 1.2

Por encima de una varianza de Rytov de 1, aviso con la asíntota de régimen fuerte
de Kaushal & Kaddoum (10)/(11) como **medida** del error. **La propia Tabla 4 de
P.1814 cae fuera:** su columna «High» es 1.99 Np² a 1550 nm y 3.39 a 980 nm, y
en la primera la teoría débil da **2.04 veces** lo que da la asíntota. Con
`C_n^2 = 1e-14`, el límite se cruza a **2.41 km**.

**Para 1.2:** los desvanecimientos se ensamblan en `link_budget._assembled_loss_budget`,
que llaman la bajada y el horizontal. Un modelo de saturación puesto ahí lo
heredan los dos; uno puesto en `turbulence.py`, solo la bajada, y habría que
decirlo.

### Lo que sale para GE-1 (V4, sobre supuestos declarados en el test)

Transmisor de 2.5 cm, 5 µrad de jitter, 0.2 dB/km, receptor Ntanos et al., noche,
BB84 decoy asintótico a la transmitancia del 1 % de outage:

- **A 1 km con turbulencia moderada, la apertura es la palanca:** de 2.5 a 10 cm,
  el término geométrico cae de 7.78 a 0.24 dB, la escintilación de 3.80 a
  1.12 dB, y la clave pasa de **56.8 a 636 kbit/s**.
- **El QBER no es lo que limita:** donde el enlace da más de 2 kbit/s, el QBER
  está por debajo del 1.2 % contra un suelo de 1 %.
- **A 5 km la elección de onda vale más que muchas decisiones de hardware:** 21.7
  contra 15.1 dB de escintilación con lente de 5 cm. Y ahí ya no hay teoría débil.
- **Un emulador de 2 m** necesita `C_n^2 = 8.9e-10` para igualar un kilómetro
  moderado: la varianza crece con la longitud a la 11/6.

### Lo que no hay (huecos 17–19 del ADR 0009)

Onda gaussiana; retrorreflector de doble paso; *beam wander* horizontal;
emuladores no Kolmogorov; escala interna y externa.

---


---

## Apéndice — la cabecera acumulativa, tal como estaba

> `LAST_CHANGES.md` llevaba una cabecera de **352 líneas** que crecía por
> apilamiento: cada entrada nueva empujaba a la anterior a un párrafo
> «Entrada anterior:…», y ninguno se retiraba nunca. Era el 5.2 % del
> fichero y lo primero que leía cualquiera, y su contenido es un resumen de
> §14 a §36 — es decir, la tercera copia de cosas que ya estaban en su
> entrada y en su ADR. Se conserva aquí íntegra porque algunos de sus
> párrafos están mejor escritos que la entrada que resumen, y porque uno de
> ellos anota una corrección que no está en ningún otro sitio (que la
> cabecera no se actualizó al cerrar §20).

# QuOSS — Últimos cambios y cosas a considerar

> Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).
> Última actualización: **2026-09-15** — §35 y §36. **§35:** dos literales del
> puente e2e fallaban por 9 ULP en una máquina que no era la suya; ahora se
> comparan contra una cota derivada de 8.15e-13, y al buscar la misma clase de
> defecto en la suite salieron cinco doctests más. Arreglando el camino
> horizontal apareció un defecto peor en el camino compartido: `combined_fade_db`
> devolvía **1.602 dB** donde la respuesta es **0.101** con apuntado despreciable.
> **§36:** `channel/horizontal.py` — presupuesto y QBER de un banco y de un enlace
> de unos kilómetros, con la Tabla 4 de ITU-R P.1814 como V2, y para GE-1 a 1 km
> una lente de 10 cm da **11 veces** la clave de una de 2.5 cm.
>
> Entrada anterior (2026-09-14): **`tests/e2e/test_reference_scenarios.py`**
> (§32) y el [ADR 0016](../docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md).
> El motor afirmaba desde su primera línea que ese fichero probaba **bit a bit** que
> no añade ni pierde nada frente a una cadena cableada a mano; **el fichero no
> existía**. Ahora existe, son 30 tests con igualdad **exacta** de coma flotante, y
> lo primero que cerró es la discrepancia que tapaba.
>
> **La cifra que resume la entrada:** el día de referencia tenía **dos** valores de
> clave finita en el árbol a la vez, **432 985 bits** (etapa 3) y **433 442 bits**
> (`run()`). Son **457 bits, el 0.106 %**, y son **un término**:
> `StationSpec.altitude_m` es a la vez dónde está la estación y dónde empieza la
> integral de turbulencia; el *fixture* de la etapa 3 la pasa a la geometría y deja
> la turbulencia en 0 m, el motor cablea el campo. Las dos cifras se reproducen **a
> la última cifra** desde la misma cadena con un solo argumento distinto, los dos
> enlaces ven **los mismos pases**, y de los nueve términos del presupuesto solo se
> mueve el de centelleo, **0.0185 dB** como mucho. **La que va al paper es la del
> motor**: en un escenario `altitude_m` es un campo y no puede significar dos cosas.
>
> **Y lo que hace que ese 0.1 % no sea un redondeo:** el mismo término vale
> **+35.7 %** en Calar Alto (2 168 m) y **+4.5 %** en la OGS del Teide (2 400 m),
> y **duplica** el segundo pase de Calar Alto (9 817 → 19 724 bits), porque el
> término de superficie del perfil HV tiene 100 m de altura de escala y a 2 168 m
> hay un orden de magnitud menos de turbulencia encima. Las estaciones del enlace
> que viene están en montañas, no al nivel del mar.
>
> **La ambigüedad que había debajo, cerrada con el documento abierto:** el proyecto
> documentaba `station_height_m` como «above ground level» en dieciséis sitios
> mientras le metía la altura sobre el elipsoide. La ITU-R P.1621-2 usa los dos
> nombres para el mismo símbolo y se desempata sola: la frase que sigue a su
> Ec. (13) da el rango de validez como «earth station altitude between 0 km and
> 5 km **above sea level**», y 0-5 km es un rango de sitios, no de mástiles.
>
> Entrada anterior: **los dos primeros módulos de la Etapa 3**,
> `system/passes.py` (§26) y `system/key_volume.py` (§27), con el
> [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md). Entre los dos cierran la
> decisión que el ADR 0010 dejó aplazada: **el bloque es el pase**, y con eso la
> cota finite-key pasa a ser el defecto del proyecto — `pass_key_volume` devuelve
> `FINITE` y **no hay ningún argumento `regime=`**, porque el número asintótico
> solo se alcanza llamando a una función que se llama `asymptotic_…`.
>
> **La cifra que resume la etapa.** Un día del enlace de referencia (estación de
> Castelldefels, telescopio de 0.75 m, SSO a 700 km, noche clara, máscara de 10°):
> la integral asintótica reclama **3.78 Mbit** y la cota finita certifica
> **0.43 Mbit**, el **11.5 %**. Y el cociente no es lo importante: **dos de los
> cuatro pases no certifican nada**, donde el asintótico reclama 320 y 199 kbit.
> El error de reportar la cifra asintótica no es «unas ocho veces optimista», es
> **ilimitado**, justo en los pases bajos que un planificador estaría decidiendo
> si agendar. Y muere de golpe, no poco a poco: el pase 4 tiene 309 867
> detecciones —no es poco— y lo mata la **tasa de error de fase**, que a ese
> tamaño de bloque devuelve `phi = 0.5` y anula el término de un fotón entero
> mientras la corrección de errores se sigue cobrando sobre todos los bits.
>
> **El hallazgo que solo esta etapa puede ver:** la **máscara de elevación tiene
> óptimo interior**, cerca de **8°**. La columna asintótica es monótona en la
> máscara —el recorte a cero muestra a muestra la protege, y por debajo de 5° las
> muestras extra aportan *exactamente* cero— y la finita no lo es: bajar de 8° a
> 2° compra un **71 % más** de segundos útiles y **destruye el 6.0 %** de la clave
> del día, porque las muestras de baja elevación meten sus errores en el bloque
> agrupado, donde la corrección de errores se cobra sobre todas las detecciones.
> Por eso `find_passes` exige la máscara **sin defecto**.
>
> **Y la parte que una leyenda de figura casi siempre falla:** sumar los pases de
> un día suma **longitudes**, que está permitido, pero la clave resultante es
> `n·eps`-segura y **no** `eps`-segura. `composed_security` lo calcula y
> `DailyKeyVolume` lo lleva. La otra dirección está tasada: un día honestamente
> `1e-10`-seguro, con cada bloque a `eps/4`, cuesta el **6.5 %** de la clave.
>
> **Lo que decidió la forma de los contenedores:** el bloque es el pase, ni la
> muestra ni el día. Un bloque por muestra da **cero bits del día entero** (cero
> de 1800 muestras certifica un bit) — la cota **no es aditiva sobre
> sub-bloques**. Un bloque por día mezclaría el QBER del 1.9 % de los pases
> muertos con el 1.24–1.26 % de los buenos, y entre pases no se envía ningún pulso.
>
> Entrada anterior: **tercer y último módulo de la Etapa 2.3**,
> `qkd/finite_key.py` (§25): la cota finite-key componible, y con ella el
> [ADR 0010](../docs/adr/0010-decoy-and-finite-key.md) que la etapa tenía
> aplazado. **La fuente no es la que el roadmap pedía:** decía «Tomamichel» y lo
> implementado es **Lim et al. 2014**, porque el protocolo que hay es decoy con
> pulsos coherentes débiles y el de Tomamichel et al. supone fuente de un fotón —
> y no es apartarse de ellos, es usar el resultado que aplica su relación de
> incertidumbre entrópica al protocolo que tenemos.
>
> **Lo que entra y sale es de otra especie:** entra un **bloque** de cuentas
> acumuladas, sale una **longitud en bits** con dos probabilidades de fallo al
> lado. No es la tasa asintótica por un factor, y tres cosas lo impiden: hay un
> coste fijo de **260 bits por bloque** que no escala con nada; la desviación de
> Hoeffding la comparten las tres intensidades, así que la que se envía 1/21 de
> las veces carga una incertidumbre relativa 21 veces mayor; y el protocolo de
> Lim et al. —base sesgada, clave de las tres intensidades, error estimado en la
> otra base— **no es** el de `bb84.py`.
>
> **La cifra que resume la etapa:** en el enlace de referencia a cenit con el
> reparto 16:1:4, un bloque de 1e10 pulsos —cien segundos de una fuente de
> 100 MHz— certifica **1.1387e-05 bits por pulso** contra los **6.0239e-05** del
> límite asintótico del mismo protocolo. El **18.9 %**. Y a 1e9 pulsos, nada.
>
> **El hallazgo que solo este módulo puede ver:** asintóticamente los pulsos
> decoy son coste puro y su fracción óptima es cero —lo dice el docstring de
> `protocol_efficiency`, y es cierto—; con un bloque de pase el óptimo está
> **cerca del 50 %** y vale un factor **3.4** sobre gastar una décima parte.
>
> **Verificación:** V3 **entre fuentes** —con `mu_3 = 0` y bloque grande, la
> Ec. (3) de Lim et al. **es** la Ec. (34) de Ma et al. que implementa
> `bb84.py`, y el residuo cae exactamente como `1/sqrt(N)`: 4.33e-04 a 1e16
> pulsos, 4.33e-06 a 1e20, 4.33e-08 a 1e24—; y V2 contra su Fig. 1, cuyo cociente
> publicado de **1.75** entre bloques de 1e9 y 1e7 se reproduce en **1.79**. Ese
> cociente es además lo que **decide** una ambigüedad de su modelo de error, y lo
> que **no** se reproduce —su curva de bloque 1e4— queda escrito como hueco 16
> del ADR 0009 y como un test que asierta el desacuerdo.
>
> Entrada anterior: **segundo módulo de la Etapa 2.3**,
> `qkd/bb84.py` (§24): BB84 con pulsos coherentes débiles y estados decoy, la
> primera implementación de `QkdProtocol`. **Cuatro decisiones con su número:**
> (1) se usa el rendimiento **exacto** de Ma et al. Ec. (7) primera línea —que
> **es** `click_probability`— y no su aproximación Ec. (10), que por encima de
> **7.152 cuentas por puerta devuelve una ganancia mayor que uno**; (2) el QBER se
> escribe como **mezcla** para que `E ≤ ½` se cumpla en coma flotante, cosa que el
> numerador publicado no hace a partir de **3.912 cuentas por puerta** —el sol
> brillante de la ITU está un 12.6 % por debajo—; (3) donde la cota decoy no
> certifica nada se devuelve `e_1 = ½` y **no** `e_1 = 0`; (4) `q` cuenta los
> pulsos gastados en decoys. **La intuición que hubo que corregir:** la cota no
> falla por pérdida —de η = 1 a 1e-08 sigue positiva— sino por **intensidad**,
> por encima de µ = 3.72. **Verificación:** V3 contra el programa lineal del que
> la Ec. (34) es forma cerrada (`linprog`, 1e-09), y V2 contra el óptimo analítico
> de µ de la Ec. (12) al 0.1 %, con tolerancia derivada.
>
> Entrada anterior: **primer módulo de la Etapa 2.3**,
> `qkd/base.py` (§23): la frontera entre el canal y un protocolo. Qué entra
> (`LinkConditions`), qué sale (`KeyRate`), qué interfaz se implementa
> (`QkdProtocol`) y qué nombre puede escribir un escenario (`ProtocolRegistry`).
> Sin física dentro: toda fórmula sobre BB84 es de `bb84.py`.
>
> **Las tres trampas que le dan forma.** (1) *Una media no es una probabilidad*:
> `NoiseBudget` da cuentas por puerta como **media** y un protocolo necesita la
> **probabilidad** `Y_0 = 1 - exp(-µ)`. Medido con el día claro de 6 W/(m²·µm·sr)
> que Ntanos et al. citan a 1550 nm, leer la media como probabilidad sobreestima
> **un 3.58 %** en su telescopio de 2.3 m y **un 0.38 %** en el de 0.75 m —
> pequeño, silencioso y a favor del enlace (la versión patológica, 3.42 «de
> probabilidad», ya estaba tasada en §20). La conversión **es**
> `click_probability` con señal cero, no una segunda copia de la exponencial.
> (2) *La transmitancia ya lleva el receptor dentro*, así que `LinkConditions`
> tiene un campo de transmitancia y **ninguno** de eficiencia: no hay par que
> multiplicar, y el doble conteo de 6.36 dB de §22 no tiene por dónde entrar.
> (3) *Por pulso no es por segundo*: solo se guarda la forma por pulso y la otra
> se deriva, como en `LossBudget`.
>
> **La interfaz comprueba a sus implementaciones.** `key_rate` es concreto y
> delega en `_key_rate`, y al volver comprueba tres cosas que se pueden equivocar
> sin que nada parezca raro: la forma (un producto exterior da un `(n, n)` con la
> diagonal correcta), la tasa de pulsos (se copia, no se recalcula) y el nombre.
> Cada una tiene detrás un test con una implementación rota a propósito.
>
> **Y dos ausencias con motivo:** no hay entrada de finite-key por bloques —una
> cota finite-key habla de un bloque, y un bloque es una integral sobre el pase,
> que es `system/key_volume.py`—, así que toda tasa de esta interfaz es
> `ASYMPTOTIC` y lo dice en su propio campo; y el registro no tendrá jamás un
> nombre para E91, CV-QKD, MDI-QKD ni TF-QKD mientras no estén implementados
> (regla del [ADR 0005](../docs/adr/0005-propagation.md), con control negativo
> sobre el registro real).
>
> Entrada anterior: **séptimo y último módulo de la Etapa
> 2.2**, `channel/link_budget.py` (§22): todas las pérdidas en un sitio. **Con
> esto la Etapa 2.2 queda cerrada.**
>
> **El hallazgo:** dos de los seis módulos que ensambla no devuelven un número
> —apuntado devuelve una distribución, turbulencia una varianza— y la práctica
> publicada de **sumar el cuantil al 1 % de cada uno no da un presupuesto al
> 1 %**. Las dos colas tienen forma cerrada *en decibelios*: la de apuntado es
> **exactamente exponencial** y la de escintilación **exactamente gaussiana**,
> así que su suma es una gaussiana modificada exponencialmente y el cuantil
> conjunto es exacto sin Monte Carlo — **1.668 dB donde la suma publicada da
> 2.312 dB**. Son 0.644 dB de margen que nadie pidió y, sobre todo, una etiqueta
> falsa: ese presupuesto es del **0.066 % de outage**, quince veces más estricto
> que el 1 % impreso a su lado.
>
> **La trampa que da forma al módulo:** `click_probability` toma una `efficiency`
> y un presupuesto quiere la cadena del receptor como línea, así que hacer las
> dos cosas la cuenta **dos veces — 12.71 dB en vez de 6.36**, un factor 4.3 en
> tasa de clave. El API guarda las dos transmitancias con nombre y ninguna es el
> producto de la otra por algo que haya que recordar.
>
> **El segundo hallazgo, y salió de perseguir un V2 que no cerraba:** el total
> de bajada de 20 dB de Ntanos et al. §4.2.1 dejaba **4.259 dB** sin explicar, y
> cerrarlos con extinción exigía `L_zen = 0.375` — un orden de magnitud más de lo
> creíble a 1550 nm. **Los decibelios que faltaban no estaban en la atmósfera,
> estaban en el transmisor.** `beam.py` propaga una gaussiana **sin truncar** y
> el borde de la apertura corta el 13.5 % del haz; el número tentador —0.632 dB
> de potencia recortada— es la respuesta a otra pregunta, porque en el eje lo que
> integra es la **amplitud** y la intensidad es su cuadrado. El modelo sin
> truncar sobreestima `[1-exp(-α²)]²/[1-exp(-2α²)]`, que a `α = 1` son
> **3.352 dB**. Con ese término el presupuesto sube a **19.094 dB** y el residuo
> baja a **0.906 dB** (`L_zen = 0.812`, ordinario): **compatible, no
> reproducido**. Y `tests/golden/README.md` llevaba este término predicho en
> **0.63 dB** desde antes de que el módulo existiera — corregido allí, con la
> forma cerrada verificada contra la integral de difracción por cuadratura.
> Hueco 15 del [ADR 0009](../docs/adr/0009-citation-policy.md).
>
> **La extinción atmosférica sigue siendo un hueco declarado**, y por eso
> `zenith_transmittance` es un **argumento obligatorio sin defecto**: la ley de
> escala está publicada y numerada, el número que escala no, porque la UIT
> publica absorción y dispersión **solo como figuras** (hueco 14). Dos cosas más
> de la misma fuente:
> su Ec. (18) **devuelve un número negativo y lo llama pérdida** (es el nivel, no
> la caída — sumarla como está impresa deja el total equivocado en el doble del
> desvanecimiento), y una log-varianza no es un índice de escintilación
> (convertir dos veces cuesta 0.005 dB donde el enlace opera y 2.36 dB en el
> límite de la teoría).
>
> Y un defecto de los hermanos que solo aparece al ensamblarlos: un **eje
> temporal vacío** hacía reventar a `beam`, `turbulence`, `pointing` y
> `background` en el `np.max` con el que deciden si avisan. `detector.py` ya
> tenía la guarda desde §21; ahora la tienen los cinco.
>
> Entrada anterior: **sexto módulo de la Etapa 2.2**, `channel/detector.py`
> (§21): la cadena de eficiencia, las cuentas oscuras, el afterpulsing y el
> tiempo muerto. Lo que el detector pierde, lo que se inventa, y cuándo no está
> escuchando. **La regla que da forma al módulo:** las medias se suman y la
> exponencial se hace una vez, al final — porque las **tres** formas publicadas
> que reproduce son truncamientos a primer orden de eso, excelentes en su punto
> de operación (7e-12, 0.16 % y 1.2e-6) y las tres por encima de 1 en el barrido
> diurno de este proyecto (**1.93, 1.006 y 3.42**). **La trampa:** la cadena de
> eficiencia se aplica a todo lo que entró por la apertura y a nada que naciera
> dentro del detector; aplicársela también a las cuentas oscuras esconde
> **0.94 dB de ruido**. **Y el hallazgo que pone una condición a
> `background.py`:** el gating no toca el afterpulsing, así que estrechar de 1 ns
> a 100 ps vale **10 dB con el nanohilo de Ntanos et al. y 0.22 dB con el APD de
> InGaAs de Lim et al.**
>
> Entrada anterior: **quinto módulo de la Etapa 2.2**,
> `channel/background.py` (§20) — la luz que llega cuando no se envió nada, y la
> Ec. (20) que llama «probability» a un número esperado de cuentas que con la luz
> solar tabulada por la UIT vale 3.42. (La cabecera no se actualizó al cerrar esa
> entrada; queda anotado aquí para que el orden de la bitácora no engañe.)
>
> Entrada anterior: **cuarto módulo de la Etapa 2.2**,
> `channel/pointing.py` (§19): el desvanecimiento por jitter de apuntado, que es
> el efecto que más castiga el enlace y que **devuelve una distribución, no un
> número**. Jitter gaussiano en dos ejes → error radial Rayleigh → ley de
> potencias `F(x) = x^(gamma²)` con un solo parámetro: el radio del haz medido
> en jitters. Medido: la pérdida **media** son 0.22 dB y la que se supera 1 vez
> de cada 100 son **1.03 dB**; con 2 µrad de jitter, 1.35 dB y **7.32 dB**.
> Diseñar con la media es diseñar para un enlace que no existe.
>
> **La trampa que da forma al módulo:** el `A_0` de la Ec. (9) de Farid &
> Hranilovic **es** el acoplamiento geométrico de `beam.py`, así que multiplicar
> «pérdida geométrica × pérdida de apuntado» tal como está publicada cuenta
> `A_0` dos veces — **17.5 dB inventados de la nada**, y un total de 35 dB es
> tan plausible a la vista como el correcto de 17.6 dB. Todas las funciones
> devuelven el factor **relativo**, normalizado a exactamente 1 con apuntado
> perfecto.
>
> Y dos cosas que el oráculo exacto (su Ec. (8), integrada numéricamente) dijo:
> **la fórmula de `beam.py` tiene ahora una segunda fuente publicada
> independiente** —concuerdan a ocho dígitos, una por ganancias de antena y otra
> por integral de superficie— y **la condición de validez que los propios
> autores publican (`W/a > 6`) falla para el telescopio de 2.3 m del sistema de
> referencia**, que es justo la configuración de su mejor presupuesto de enlace.
> Sale en `warnings[]`, con la medida de lo que cuesta al lado: 0.36 % donde el
> jitter pone el haz de verdad, 35 % a tres radios de haz.
>
> Entrada anterior del mismo día: **tercer módulo de la Etapa 2.2**,
> `channel/beam.py` (§18), y con él la etapa entra en la bitácora: §18 recoge
> también lo que la verificación cazó en `atmosphere.py` y `turbulence.py`, que
> hasta ahora vivía solo en los docstrings y en el
> [ADR 0009](../docs/adr/0009-citation-policy.md).
>
> `beam.py` es el término más grande del presupuesto de enlace —decenas de dB
> contra un par de dB de todo lo demás— y sale de algo muy simple: un haz que
> sale de un telescopio de 15 cm mide 8 m de ancho tras 600 km, y un telescopio
> de 0.75 m en tierra intercepta menos del 2 % de él. **El hallazgo de esta
> entrada:** la Ec. (5) de Ntanos et al. 2021 imprime la ganancia de transmisión
> como `(8/w_0)²` cuando la forma que cierra la identidad con la integral
> gaussiana es `8/w_0²` — 8 veces, **9.03 dB optimista**. No hace falta discutir
> qué lectura se quiso: con los propios parámetros del paper (2.3 m a 600 km) la
> forma impresa devuelve una transmitancia de **1.36**, más luz recogida que
> transmitida. QuOSS usa la integral exacta, que satura en 1.
>
> Y la conclusión de diseño que no era obvia: agrandar el telescopio transmisor
> estrecha el haz como `1/D_T` pero reduce el vaivén por turbulencia solo como
> `D_T^(-1/6)`, así que **la razón vaivén/divergencia crece como `D_T^(5/6)`**.
> Un transmisor de subida de 1 m pasea su haz **3.15 anchos de haz**: estrechar
> el haz no ayuda a una subida más allá del punto en que el haz es más fino que
> su propio temblor.
>
> Entrada anterior del mismo día: **la Etapa 2.1 (`orbits/`) queda cerrada** con
> sus dos últimos módulos, `geometry.py` (§16) y `constellations.py` (§17).
>
> `geometry.py` es el módulo que convierte una órbita en lo que un telescopio ve:
> elevación, azimut, distancia oblicua («slant range», la línea recta
> estación↔satélite, que no es la altitud), velocidad de acercamiento, y el
> **ángulo de point-ahead** — cuánto hay que apuntar por delante de donde se ve
> el satélite, porque en el tiempo que la luz tarda en ir y volver el satélite se
> ha movido. La corrección al roadmap la dio la medición: ese ángulo lleva
> **factor 2**, no el `v_perp/c` de una sola vía, porque un terminal monostático
> transmite adelantado y a la vez recibe por donde la luz realmente viene.
> Medido para un paso a 67.1° de elevación sobre Castelldefels en la SSO de
> 700 km de este repo: **50.6 µrad**, contra los 35 µrad que el roadmap citaba
> antes de tener la cuenta hecha.
>
> `constellations.py` (Walker-Delta, inclinación heliosíncrona, traza repetida)
> **queda escrito y aparcado**: la decisión de alcance del 2026-09-10 es hacer un
> solo satélite, así que no se construye nada encima de él por ahora.
>
> Entrada anterior del mismo día: **quinto módulo de la Etapa 2.1**
> (`orbits/tle.py`): parseo de TLE («Two-Line Element set») y propagación con
> SGP4 (`sgp4` de PyPI, sin reimplementar) → [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md).
> `PropagationMethod` gana un tercer miembro, `SGP4`, que `propagate()`
> **deliberadamente no sabe ejecutar** — pedírselo da `NotImplementedError`, no un
> resultado plausible. `tle.py` no construye ningún `ClassicalElements`: la
> disciplina que el ADR 0006 dejó preparada (`MEAN_KOZAI_SGP4`, aún sin usar) se
> cumple por no escribir esa línea, no por una guarda de tipos. Y `parse_tle`
> valida dos trampas reales de `sgp4.api.Satrec.twoline2rv` que la librería deja
> pasar en silencio: un checksum corrupto y una entrada basura, las dos
> verificadas a mano contra el paquete instalado antes de decidir la guarda.
>
> Entrada anterior: **2026-08-04** — **las siete entradas de
> [`INCONSISTENCIAS.md`](INCONSISTENCIAS.md), cerradas** (§14). La grande no era una
> de las seis inconsistencias sino la consideración C1: los «219 km» citados en
> quince sitios, incluido un mensaje de error, **no se reproducían** — la cifra real
> es 5.9 veces mayor, y además no existe una cifra única porque el coste depende de
> en qué punto de la órbita se declaren los elementos.
>
> Entrada anterior a esa: **2026-08-01** — **la bandera osculador/medio**, que no es
> un módulo nuevo sino la pieza que faltaba entre los tres que ya hay. Con sus
> tres subdecisiones resueltas y medidas (→ [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md)).
> El aviso que llevaba tres documentos escrito pasa a ser un `DomainError`, y en
> las **dos** direcciones, no solo en la que parecía.
>
> Entrada anterior del mismo día: cuarto módulo de la Etapa 2.1
> (`orbits/propagator.py`). La simulación adquiere tiempo, y el módulo se envía
> con el enum de métodos **incompleto a propósito**: es mejor un nombre ausente
> que un modo que degrada en silencio.
>
> Y la anterior a esa: tercer módulo (`orbits/perturbations.py`). La Tierra deja
> de ser una masa puntual, y el roadmap se corrige donde la medición dijo que
> estaba equivocado.

---

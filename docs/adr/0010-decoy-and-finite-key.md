# ADR 0010 — La etapa `qkd/`: decoy asintótico y clave finita son dos afirmaciones distintas, no una con corrección

- **Estado:** aceptada
- **Fecha:** 2026-09-12
- **Etapa:** 2.3 (`qkd/base.py`, `qkd/bb84.py`, `qkd/finite_key.py`)
- **Afecta a:** cualquier número que este proyecto llame «tasa de clave», y en
  particular a lo que `system/key_volume.py` y el motor podrán reportar por
  defecto.
- **Extiende** al [ADR 0005](0005-propagation.md), cuya regla —un nombre ausente
  obliga a preguntar, uno presente y no implementado invita a seleccionarlo— es
  la que deja el registro de protocolos con una sola entrada; y al
  [ADR 0009](0009-citation-policy.md), cuya política de citas es la que decide
  qué se pudo transcribir de Lim et al. y qué queda como hueco medido.

---

## Contexto

### Qué se estaba decidiendo, en una frase

Un protocolo QKD convierte lo que hace el canal en bits de clave. Hay dos formas
de decir cuántos, y no se diferencian en un factor: se diferencian en **de qué
hablan**.

- La **asintótica** supone que el bloque de detecciones es infinitamente largo,
  de modo que cada frecuencia observada es exactamente la probabilidad que hay
  detrás. Devuelve una **tasa por pulso**.
- La **finita** supone lo que de verdad pasa: un pase dura unos minutos, el
  bloque tiene el tamaño que tiene, y cada frecuencia observada es una
  estimación con intervalo de confianza. Devuelve una **longitud en bits** para
  un bloque concreto y una probabilidad de fallo declarada.

La pregunta de este ADR es cómo conviven las dos en el mismo paquete sin que
nadie las confunda, y qué fuente se implementa para la segunda.

### Por qué no basta con «multiplicar por un factor de corrección»

Porque el término dominante del coste finito no escala con nada que la fórmula
asintótica conozca. Tres razones, medidas en
`tests/qkd/test_finite_key.py`:

1. **Hay un coste fijo por bloque.** La Ec. (1) de Lim et al. resta
   `6 log2(21/eps_sec) + log2(2/eps_cor)` bits **una vez**, no por pulso: 260 bits
   con `eps_sec = eps_cor = 1e-10`. Despreciable frente a un pase, decisivo
   frente a una demostración de unos cientos de bits, y sin ninguna traducción a
   una tasa.
2. **La desviación estadística la comparten las tres intensidades.** La cota de
   Hoeffding se aplica al reparto del bloque entero entre las tres intensidades,
   así que la misma `delta` absoluta le toca a la intensidad que se envía 1/21
   de las veces que a la que se envía 16/21 — y tras el `1/p_k` que convierte
   cuentas en cantidad por pulso, la incertidumbre *relativa* de la rara es
   veintiuna veces mayor.
3. **El protocolo no es el mismo.** El de Lim et al. tiene base sesgada, extrae
   clave de las **tres** intensidades y estima el error en la **otra** base;
   `bb84.py` es simétrico, hace clave solo con la señal y estima con los mismos
   bits. Comparar término a término es comparar dos protocolos.

La consecuencia práctica se ve en una sola medición: en el enlace de referencia
de este repo a cenit, con el reparto 16:1:4 de Ntanos et al., un bloque de 1e10
pulsos —cien segundos de una fuente de 100 MHz— certifica **1.1387e-05 bits por
pulso**, y el límite asintótico del **mismo** protocolo y el **mismo** enlace es
**6.0239e-05**. El bloque real entrega el **18.9 %**. Y a 1e9 pulsos no certifica
nada en absoluto.

### La fuente: por qué Lim et al. 2014 y no Tomamichel et al. 2012

`notes/ROADMAP.md` escribió «finite-key componible (Tomamichel)» antes de que
existiera `bb84.py`. Lo que hay hoy es un protocolo de **pulsos coherentes
débiles con decoy**, y esa diferencia manda:

- Tomamichel, Lim, Gisin y Renner (*Nature Communications* 3:634, 2012) analizan
  BB84 con **fuente de un fotón**. Aplicarlo aquí exigiría o bien una fuente que
  este proyecto no modela, o bien montar encima un argumento de *tagging* que
  nadie ha publicado en esa combinación.
- Lim, Curty, Walenta, Xu y Zbinden (*PRA* 89, 022307, 2014) analizan
  exactamente el protocolo que hay: tres intensidades, WCP, decoy. Su cota es
  componible, cabe en cinco ecuaciones, y **está construida sobre** la relación
  de incertidumbre entrópica de Tomamichel y Renner: su análisis de secreto cita
  esas dos referencias como el paso central.

Es decir, elegir Lim et al. no es apartarse de Tomamichel: es usar el resultado
que aplica esa técnica al protocolo que tenemos. El roadmap se corrige, no se
contradice.

---

## Decisión

**1. Tres módulos con tres papeles, y ninguna física repetida.**
`base.py` define la frontera (qué entra, qué sale, qué interfaz) y no contiene
ninguna fórmula de BB84. `bb84.py` implementa la tasa asintótica GLLP con decoy
vacío+débil de Ma et al. 2005. `finite_key.py` implementa la cota componible de
Lim et al. 2014. El modelo directo del canal —la ganancia y el QBER de una
intensidad— vive **una sola vez**, en `bb84.simulate_intensity`, y `finite_key`
lo llama: los dos módulos no pueden discrepar sobre lo que hace el enlace.

**2. La cota finita es una entrada a nivel de bloque, y no un `QkdProtocol`.**
`QkdProtocol.key_rate` mapea instantes a instantes. Una afirmación finite-key
habla de un bloque, y un bloque es una integral sobre el pase. Por eso
`finite_key.py` no registra ningún protocolo y su función principal recibe
`DecoyBlockCounts` y devuelve bits. Lo que convierte un pase en un bloque es
`system/key_volume.py`, que es quien tiene el eje temporal.

**3. `KeyRegime` viaja dentro de cada resultado, y en el resultado finito no es
un campo.** `KeyRate.regime` es un campo porque un `QkdProtocol` podría en
principio devolver cualquiera de los dos; `FiniteKeyResult.regime` es una
**propiedad constante** igual a `FINITE`, porque aquí no hay elección posible y
un campo sería una forma de equivocarse.

**4. Las cuentas son `float`, no `int`.** En un experimento son enteras; en una
simulación son **esperanzas**, y redondear 0.4 detecciones a cero borra el
extremo de baja elevación de un pase entero. Todas las fórmulas son continuas en
ellas.

**5. Las esperanzas no se muestrean.** `expected_block_counts` devuelve medias.
La cota finite-key tasa la incertidumbre de **estimación** que queda aunque las
cuentas caigan exactamente en su esperanza; añadir encima un sorteo multinomial
responde a otra pregunta —cuánto dispersa el resultado entre pases— y esa es
`system/monte_carlo.py`.

**6. Donde no se certifica nada, cero bits y una entrada en el log.** Las
Ecs. (2), (3) y (4) son restas de cantidades ruidosas y se vuelven negativas
cuando la estadística es fina. Un número negativo de eventos no es una clave
pequeña: es la ausencia de certificado. Y donde el muestreo no acota nada, la
tasa de error de fase se fija en **1/2** y no en 0, por la misma razón por la que
`bb84.single_photon_bounds` devuelve `e_1 = 1/2`: `h(1/2) = 1` anula el término
de un fotón, mientras que 0 dibujaría un canal perfecto justo donde falló el
análisis.

**7. No se optimiza nada, y no hay defectos.** Ni las intensidades, ni las
probabilidades, ni el sesgo de base, ni `eps`. Lim et al. optimizan cinco
parámetros por enlace y el óptimo se mueve con el tamaño de bloque; eso es un
barrido, y los barridos son `engine/sweep.py`.

---

## Justificación

### Por qué `s_0` cuenta como clave, y por qué eso no es un error de signo

La Ec. (1) de Lim et al. suma `s_{X,0}` —las detecciones en puertas donde Alice
no envió ningún fotón— **entera**, sin cobrarle amplificación de privacidad. Es
correcto y contraintuitivo: un clic en una puerta vacía lo decidió el detector,
no el canal, así que Eve no sabe nada del bit que Bob apuntó. Es ruido que hace
clave.

Se midió cuánto vale, porque una afirmación así invita a creer demasiado. En el
enlace de referencia con 1e12 pulsos:

| Ruido (cuentas/puerta) | `s_0` | Clave | Contribución de `s_0` |
|---|---|---|---|
| 7.9e-07 (noche) | **0** | 5.47e+07 bits | 0 % |
| 1e-05 | 1.51e+06 | 4.58e+07 bits | **3.3 %** |
| 1e-04 | 1.65e+07 | **0** | — |

De noche no se certifica ninguno: hay **37 522** detecciones de vacío en ese
bloque y la desviación de Hoeffding es de **44 399**, así que están dentro del
ruido del reparto y la Ec. (2) sale negativa.
Y a partir de 1e-04 el término crece pero la clave ya es cero, porque la
corrección de errores se cobra sobre **todo** el bloque y el QBER que producen
esas mismas cuentas oscuras se la ha comido antes. O sea: el crédito de vacío es
real, es pequeño, y **nunca rescata** un enlace ruidoso.

### Por qué recortar `s_0` a cero antes de usarlo en la Ec. (3) es seguro

La Ec. (3) lleva `+ (mu_2^2 - mu_3^2)/mu_1^2 * s_0/tau_0`, así que un `s_0` mayor
da un `s_1` **mayor**, y mayor es la dirección insegura. Un lector que audite la
conservación se para aquí, y hace bien.

Es seguro, y merece decirse porque no es evidente: la Ec. (3) está derivada con
el número **verdadero** de eventos de vacío en esa casilla, y es monótona
creciente en él. Sustituir cualquier cota inferior válida del verdadero `s_0` da
una cota inferior válida de `s_1`. Cero es una cota inferior válida de un
recuento de eventos —eso es lo que es un recuento— y es **más ajustada** que un
número negativo. Recortar mantiene la garantía y mejora el resultado, que es lo
contrario del canje habitual.

### La verificación: dos papeles, dos transcripciones, un número

La comprobación más fuerte de la etapa no compara contra un valor publicado:
compara **dos implementaciones independientes de dos fuentes distintas**.

Con `mu_3 = 0` y un bloque tan grande que la desviación de Hoeffding es
despreciable, la Ec. (3) de Lim et al. **es** la Ec. (34) de Ma et al., escrita
en cuentas en vez de en probabilidades. No es una afirmación de prosa: dividiendo
`s_1` entre los pulsos que llevaban un fotón y sobrevivieron al sifting,
`N q_x^2 tau_1`, sale `Y_1`, y `tests/qkd/test_finite_key.py::TestTheAsymptoticLimitIsMaEtAl`
lo comprueba sobre cinco décadas de pérdida.

Y no solo coinciden: **coinciden de la manera correcta**. El residuo relativo es
4.33e-04 con 1e16 pulsos, 4.33e-06 con 1e20 y 4.33e-08 con 1e24 — tres puntos
sobre una recta de pendiente −1/2, que es exactamente como escala `delta`. La
diferencia entre los dos módulos es el término de Hoeffding y nada más. Una
coincidencia en un punto podría ser dos errores que se cancelan; una coincidencia
que converge con la ley correcta, no.

Lo mismo vale para la Ec. (4) contra la Ec. (37) de Ma et al.: `v_1/s_1` converge
a la cota de `e_1` del módulo asintótico.

### El hallazgo que solo el módulo finito puede ver

`Bb84DecoyProtocol.protocol_efficiency` dice que los pulsos decoy son **coste
puro**: asintóticamente la cota que compran es exacta por pocos que se envíen, y
la fracción óptima es cero. Es cierto, y es cierto **solo asintóticamente**.

Barriendo la fracción de decoy en el enlace de referencia, con la fracción de
vacío fija en 5 %:

| Fracción decoy | Clave/pulso a 1e20 | Clave/pulso a 1e10 |
|---|---|---|
| 0.05 | **7.11e-05** | 0 |
| 0.10 | 6.85e-05 | 6.26e-06 |
| 0.50 | 4.77e-05 | **2.12e-05** |
| 0.90 | 2.70e-05 | 1.69e-05 |

Asintóticamente cae de forma monótona, como dice el módulo asintótico.
Con un bloque de pase tiene un **máximo interior cerca del 50 %**, y gastar medio
pase en decoys vale un factor **3.4** sobre gastar una décima parte. Ese óptimo
es invisible desde `bb84.py`, porque la cantidad que `bb84.py` optimiza no
depende de la fracción de decoy en absoluto.

### El V2 de Lim et al., y la parte que no se reproduce

Su §Evaluation fija un modelo de fibra completo y publica dos afirmaciones
comprobables sobre la Fig. 1. Reproducirlas exigió resolver una ambigüedad de la
fuente, y la resolución se hizo **midiendo**, no eligiendo:

- Su tasa de error impresa es
  `e_k = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2`, donde `eta_ch` es
  solo la fibra, mientras que la tasa de detección de al lado lleva
  `eta_sys = eta_ch eta_Bob`, diez veces menor. Ese término aporta entonces
  **3.9 puntos** de QBER a pérdida cero y 4.8 a 100 km en un sistema cuya óptica
  está especificada al 0.5 %; y como es el único término que **no** escala con la
  eficiencia del detector mientras las detecciones de al lado sí lo hacen, la
  tasa de error óptico que implica va como `1/eta_Bob` — un detector mejor
  mejoraría la óptica. Leído con `eta_sys` en los dos sitios —la forma de la
  Ec. (11) de Ma et al.— aporta **0.48 puntos** a cualquier distancia, que es
  `e_mis` diluido por los afterpulses; el cociente entre las dos lecturas es
  **8.07** a pérdida cero y **9.98** a 100 km, o sea el `1/eta_Bob` que sobra.
- Cruzando esa elección con la de si `e_k` cuenta errores por puerta o por
  detección salen cuatro lecturas. Sus cocientes de tasa entre bloques de 1e9 y
  1e7 a 100 km son **1.79**, 2.73, 1.46 y 1.47. El paper dice «about 1.75».
  **Solo la lectura físicamente consistente cae sobre su número publicado**, así
  que es la que implementa el test, y la elección descansa en la cifra del propio
  paper.

Lo que **no** se reproduce, escrito en vez de ajustado: dicen que «even if we use
a block size of 1e4, cryptographic keys can still be distributed over a fiber
length of 135 km». Con esa lectura y un bloque de 1e4 detecciones, esta
implementación no certifica clave **a ninguna distancia**, ni siquiera a pérdida
cero. El desajuste es de exactamente una década: nuestra curva de 1e5 es su curva
de 1e4 —clave positiva a 135 km, muerta antes de 150 km—. Las dos causas
candidatas son un convenio distinto sobre qué cuenta `n_X` y una resolución
distinta de la ambigüedad de `e_k`, y ninguna está decidida por nada impreso en
el paper. Queda como hueco 16 del [ADR 0009](0009-citation-policy.md) y como un
test que **asierta el desacuerdo**: si un cambio futuro hace funcionar los
bloques de 1e4, ese test falla y obliga a reescribir esta sección, que es
justamente lo que debe pasar.

### `gamma`: el único sitio donde la fórmula publicada mezcla dos logaritmos

El término de muestreo aleatorio de su Ec. (5) escribe `cd log 2` en el
denominador y `log2(...)` en el numerador de la **misma** expresión. El primero
es el logaritmo natural de dos, el segundo es base dos. Leer el primero como base
dos lo convierte en `1` en vez de `0.693`, lo que escala `gamma` por
`sqrt(ln 2) = 0.8326`: un **17 % de subestimación** del castigo de muestreo, en
la dirección que favorece a la clave y sin ningún síntoma en ninguna otra parte.
Hay un control negativo que lo mide.

---

## Consecuencias

### Lo que esto cierra

- **Cierra** qué significa «tasa de clave» en este proyecto: o es
  `KeyRegime.ASYMPTOTIC` y es una cota superior, o es `KeyRegime.FINITE` y es una
  longitud con dos probabilidades de fallo al lado. No hay un tercer estado, y
  ningún resultado sale sin etiqueta.
- **Cierra** la duda del roadmap sobre qué análisis finite-key implementar, con
  la razón escrita: el protocolo que hay es decoy con WCP.
- **Cierra** la pregunta de dónde vive el modelo directo del canal: en
  `bb84.simulate_intensity`, y `finite_key` lo llama.

### Lo que no cierra

- **El defecto activo.** El roadmap pide que la cota finita sea lo que se reporta
  por defecto. Este ADR no lo puede fijar: el objeto que posee un pase —y por
  tanto un bloque— es `system/key_volume.py`, y hasta que exista, lo que sale de
  `qkd/` por la interfaz de protocolo sigue siendo asintótico y etiquetado como
  tal.
- **La optimización de parámetros.** Cinco parámetros, un óptimo que se mueve con
  el bloque y con el enlace. Es `engine/sweep.py`.
- **El sorteo de las cuentas.** `system/monte_carlo.py`.
- **BB84 asimétrico en `bb84.py`.** El módulo finito ya acepta un sesgo de base
  porque el protocolo de Lim et al. lo tiene; el asintótico sigue siendo
  simétrico, y sesgarlo allí cobraría la ganancia sin el coste, que es una
  afirmación sobre una muestra finita.
- **El hueco 16.** El bloque de 1e4 de su Fig. 1 sigue sin reproducirse.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Implementar Tomamichel et al. 2012 tal cual, como pedía el roadmap** | Analiza BB84 con fuente de un fotón. Con WCP haría falta un argumento de tagging encima que no está publicado en esa combinación, y el resultado sería una cota escrita por nosotros con la etiqueta de otro |
| **Añadir un `regime=FINITE` a `Bb84DecoyProtocol` y una corrección multiplicativa** | El coste fijo por bloque no es multiplicativo, la desviación compartida cambia el óptimo de los parámetros, y el protocolo de Lim et al. no es el de `bb84.py`. Sería una etiqueta correcta sobre un número que no la merece |
| **Registrar la cota finita como un protocolo más** | `QkdProtocol.key_rate` mapea instantes a instantes; un escenario que la seleccionara recibiría un objeto sin `key_rate` o, peor, uno que finge tenerlo |
| **Muestrear las cuentas dentro de `expected_block_counts`** | Mezcla dos preguntas —qué certifica un bloque típico y cuánto dispersa entre pases— en una función de la que solo se puede leer la suma de las dos |
| **Recortar también `n^-` a cero, que es válido y más ajustado** | Lo es, pero aparta la transcripción de la forma publicada por una ganancia que solo existe donde el bloque ya no certifica nada. La fidelidad a la fuente vale más que ese margen |
| **Elegir la lectura de `e_k` que reproduce el alcance de 1e4** | Es la que da un QBER de 3.6e-5 a 100 km, por debajo del suelo de cuentas oscuras. Reproduciría una afirmación del paper rompiendo la física del modelo, que es la forma más cara de tener razón |

---

## Referencias

- C. C. W. Lim, M. Curty, N. Walenta, F. Xu, H. Zbinden, «Concise security bounds
  for practical decoy-state quantum key distribution», *Phys. Rev. A* **89**,
  022307 (2014); preprint arXiv:1311.7129, abierto el 2026-09-12 vía
  `export.arxiv.org`. Ecs. (1)-(5) del texto principal y Ecs. (1)-(14) del
  material suplementario.
- M. Tomamichel, C. C. W. Lim, N. Gisin, R. Renner, «Tight finite-key analysis for
  quantum cryptography», *Nature Communications* **3**, 634 (2012).
- M. Tomamichel, R. Renner, *Phys. Rev. Lett.* **106**, 110506 (2011): la
  relación de incertidumbre entrópica.
- C.-H. F. Fung, X. Ma, H. F. Chau, *Phys. Rev. A* **81**, 012318 (2010): el
  muestreo aleatorio detrás de `gamma`.
- X. Ma, B. Qi, Y. Zhao, H.-K. Lo, «Practical decoy state for quantum key
  distribution», *Phys. Rev. A* **72**, 012326 (2005).
- A. Ntanos et al., *Photonics* **8**(12):544 (2021), §4.1 y Apéndice A.
- [ADR 0005](0005-propagation.md) (la regla del nombre ausente),
  [ADR 0009](0009-citation-policy.md) (política de citas y lista de huecos).

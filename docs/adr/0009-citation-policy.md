# ADR 0009 — Política de citas: una cita es una fuente que se ha abierto

- **Estado:** aceptada
- **Fecha:** 2026-09-10
- **Etapa:** 2.2 (`channel/`), y por delante 2.3 (`qkd/`)
- **Afecta a:** todos los docstrings de física de `channel/` y `qkd/`, los tests
  V2, y la sección «Gaps, stated rather than filled» de
  [`tests/golden/README.md`](../../tests/golden/README.md).
- **Extiende** al [ADR 0002](0002-frames-and-time-scales.md), que fijó que el
  presupuesto de error se **mide** en vez de afirmarse. Esto es lo mismo aplicado
  a la procedencia: una fórmula se **verifica** en vez de recordarse.

---

## Contexto

### Qué es una cita, en este proyecto

Una cita, aquí, no es un reconocimiento de autoría. Es una **promesa
comprobable**: que la fórmula que hay en el código coincide con la que hay en un
documento concreto, en una página o ecuación concreta, y que un lector puede
abrir ese documento y comprobarlo sin ejecutar nada.

Eso es distinto de lo que suele significar en un paper, y la diferencia importa.
En un paper, «(Andrews & Phillips, 2005)» al final de una frase es suficiente
porque el lector confía en que el autor lo leyó. Aquí el lector **es** el que
tiene que detectar el error, así que la cita tiene que llevarlo al sitio exacto.
Por eso el proyecto pide autor, año, publicación **y número de ecuación o
página**, no solo el apellido y el año.

### Por qué esto necesita un ADR y no basta con «citad bien»

Porque al ir a escribir el canal apareció un problema concreto que no se resuelve
con buena intención.

El canal óptico tiene una referencia canónica: **Andrews & Phillips, *Laser Beam
Propagation through Random Media*, 2.ª ed., SPIE Press PM152, 2005**. Es el libro
que todo el mundo cita para turbulencia atmosférica. El código anterior de este
mismo grupo (SimulCTTC) lo cita **por número de ecuación** repetidamente: «A&P
Eq. 12.46» para beam wander, «Eq. 12.15» para el índice de escintilación en
régimen fuerte, «Eq. 12.12» para el parámetro de Fried, «Eqs. 9.46-9.47» para
gamma-gamma.

**Ninguno de esos números se ha podido verificar.** El libro es de pago, no tiene
texto completo accesible, la biblioteca digital de SPIE no devuelve el contenido,
y no se localizó ninguna fuente secundaria que cite sus ecuaciones por número.

Eso deja dos opciones, y solo una es honesta:

1. Copiar los números de ecuación de SimulCTTC al nuevo código. El resultado
   parece más riguroso —lleva número de ecuación— y es **exactamente** lo que la
   regla del README prohíbe: «no inventar números y etiquetarlos publicados».
   Nadie ha comprobado que la ecuación 12.46 sea la que dice ser.
2. No citar A&P por ecuación, y usar una fuente que sí se pueda abrir.

### Y no es un riesgo hipotético

El propio SimulCTTC se autocorrigió por esto. Su módulo de probabilidad de línea
de vista libre de nubes citaba a Vasylyev et al. y a Pirandola et al., y la
corrección dice, literalmente, que «**neither of which contains any cloud/PCFLOS
content**». Es decir: dos citas que apuntaban a papers que no hablaban del tema.
Estuvieron ahí el tiempo suficiente para que alguien las leyera y las creyera.

Es el mismo modo de fallo que costó los «219 km» de la §14.1 de
[`notes/LAST_CHANGES.md`](../../notes/LAST_CHANGES.md): un número que se citó en
quince sitios, incluido el texto de un mensaje de error, durante tres días,
porque salió de una medición hecha a mano y guardada solo en prosa. Cuando por
fin se le escribió un test, resultó 5.9 veces menor que la realidad.

**El coste de equivocarse:** una cita falsa es peor que ninguna cita. Ninguna
cita invita a comprobar; una cita falsa invita a confiar. Y en un módulo donde
nadie puede detectar a ojo que 45 dB debería ser 39 dB, la confianza mal puesta
es el único fallo que llega hasta el paper.

## Decisión

**Una cita es una fuente que se ha abierto. Si el documento no se ha podido
consultar, no se escribe el número de ecuación — se escribe el hueco. Andrews &
Phillips no se cita por ecuación en ningún sitio. La fuente primaria del canal
pasan a ser las recomendaciones ITU-R P.1621-2 y P.1622, que son gratuitas, están
numeradas y traen tablas de valores.**

| Regla | Qué significa en la práctica |
|---|---|
| **Verificada o no está** | Autor, año, publicación y ecuación/página, comprobados en el documento. Sin verificar, no hay número de ecuación |
| **Prioridad de fuentes** | (a) ITU-R; (b) open access con ecuaciones numeradas; (c) hojas de datos de fabricante para valores de detector |
| **`FORMULAS.md` es un índice, no una fuente** | El registro de fórmulas de SimulCTTC dice **qué buscar**. Cada cita se vuelve a verificar contra el original |
| **Los huecos se declaran** | En `tests/golden/README.md`, no se rellenan con la cita más plausible |
| **Un valor V2 vive junto a su cita** | En el fichero de test, no en `data/`: es un número que un lector contrasta contra la fuente sin ejecutar un generador |

### Las fuentes verificadas, y qué cubre cada una

Todas comprobadas abriendo el documento y extrayendo el texto.

| Tema | Fuente | Ecuaciones |
|---|---|---|
| Viento de Bufton; HV 5/7; malla de integración | **ITU-R P.1621-2** (07/2015) | (5), (6), (7) |
| Parámetro de Fried en camino inclinado | ITU-R P.1621-2 | (8a), (8b) |
| Ángulo isoplanático; constante de tiempo τ₀ | ITU-R P.1621-2 | (14a), (19)–(21) |
| Radiancia de cielo (tabla) y potencia de fondo | ITU-R P.1621-2 **§3.1**, Tabla 1 y Fig. 3 | (1) |
| Varianza de log-irradiancia; asimetría uplink/downlink | **ITU-R P.1622** (04/2003) | (4a)–(4c), (5) |
| Promediado de apertura | ITU-R P.1622 | (6), (7), (8) |
| Beam wander | ITU-R P.1622 | (11a), (11b) |
| Rytov en camino inclinado; escintilación en régimen fuerte | **Ntanos et al. 2021**, *Photonics* 8(12):544 | (12), (13) |
| Perfil HV modificado con la altitud de la estación | Ntanos et al. 2021 | (11) |
| Potencia y cuentas de fondo | Ntanos et al. 2021 | (19), (20) |
| Fading por error de apuntado con jitter | **Farid & Hranilovic 2007**, *JLT* 25(7):1702 | (9), (10), (11) |
| Extinción por visibilidad | **Kim, McArthur & Korevaar 2001**, *Proc. SPIE* 4214:26 | (6) |
| Decoy vacuum+weak; tasa GLLP | **Ma, Qi, Zhao & Lo 2005**, *PRA* 72, 012326 | (1), (7)–(11), (34), (35), (37) |
| Longitud de clave finita componible | **Lim, Curty, Walenta, Xu & Zbinden 2014**, *PRA* 89, 022307 | (1)–(5) |

### Los huecos, declarados

Esta lista es la parte que hace que la de arriba signifique algo.

1. **Andrews & Phillips: ninguna ecuación por número.** El libro es de pago y no
   se pudo abrir. Donde su contenido haga falta, se usa la fuente ITU-R o Ntanos
   equivalente. Se puede citar el libro como referencia general, sin número.
2. **Parámetros α y β de la distribución gamma-gamma.** El origen es Al-Habash,
   Andrews & Phillips, *Opt. Eng.* 40(8):1554 (2001), de pago y no verificado.
   La relación σ²_I = (1+1/α)(1+1/β) − 1 **no está verificada en fuente**.
3. **Modelo de Beckmann/Hoyt con boresight ≠ 0** (error de apuntado con sesgo
   sistemático, no solo jitter de media cero): sin fuente verificada.
4. **Radiancia de cielo a 785 y 810 nm.** ITU-R P.1621-2 tabula 530, 850, 965,
   1060 y 1500 nm. Interpolar entre ellos y presentarlo como valor publicado
   sería inventar un V2.

   **Medido al implementar `channel/background.py` (2026-09-10), que es lo que
   convierte el hueco en una cifra:** dos reglas de interpolación defendibles
   (ley de potencias en log-log, y lineal en λ) difieren **0.48 dB a 785 nm**, y
   la precisión real es **peor que esa diferencia** — quitar un punto interior de
   la tabla y predecirlo desde sus dos vecinos falla entre **16 % y 27 %** con la
   regla en uso (2 % a 32 % con la lineal), porque la banda de vapor de agua de
   940 nm cae dentro de la rejilla y la columna de sol normal **no es monótona**
   ahí (25.12 a 965 nm y 25.32 a 1060 nm). Y la tabla **no tiene ningún punto
   interior entre 530 y 850 nm**, así que el error *en* 785 nm no se puede medir
   con ella, solo acotar por analogía. En el código son dos funciones:
   `tabulated_sky_radiance_w_m2_um_sr` rechaza todo lo que no esté en la rejilla
   e `interpolated_sky_radiance_w_m2_um_sr` interpola registrando un `DEGRADED`
   que lleva dentro el valor de la otra regla.
5. **Valores típicos de detector SPAD.** No se localizó fuente libre y
   autoritativa con una tabla. Se usan los valores **publicados y verificados**
   de Ntanos et al. 2021 §4.1 (SNSPD: η 85 %, 300 cps, jitter 50 ps, tiempo
   muerto 30 ns) y de Lim et al. 2014 §Evaluation (InGaAs: η 10 %,
   p_dc 6e-7, p_ap 4e-2).
6. **Los coeficientes del viento de Bufton no coinciden entre fuentes.** ITU-R
   P.1621-2 Ec. (5) da `v_rms = sqrt(v_g² + 33.11·v_g + 360.31)`; la forma que se
   cita habitualmente de A&P usa 30.69 y 348.91. Las dos dan ≈21 m/s, pero con
   `v_g` distinto (2.3 frente a 2.8 m/s). **Se elige la de ITU** porque es la que
   se puede abrir, y la otra queda escrita aquí para que la discrepancia no se
   redescubra desde cero.
7. **Radiancia de la Tierra: la Tabla 1 la promete en su título y no la trae.**
   El título es «Radiance, H (W/m²/µm/sr), of the sky **and Earth** for several
   frequencies» y la tabla imprime solo las tres columnas de cielo — aunque la
   §3.1 sí dice que «spacecraft pointed at the Earth will also encounter noise
   from sunlight reflected from the Earth's surface». Consecuencia: **no hay
   fondo de subida** en `channel/background.py`, porque no hay radiancia
   publicada para una Tierra iluminada en ninguna de las dos fuentes (Ntanos et
   al. consideran solo bajada).
8. **Las dos fuentes discrepan por un factor diez en la radiancia nocturna.**
   ITU-R P.1621-2 §3.1 da «(1-2)·10⁻⁶ W/m²/µm/sr for most frequencies of
   interest»; Ntanos et al. §4.2.2 dan 1.5e-5 a 1550 nm para noche clara sin
   luna. Mismo tratamiento que el hueco 6: las dos se exponen como constantes con
   su fuente, **ninguna es un defecto**, y la discrepancia **se mide** — contra
   las 300 cps de cuentas oscuras del mismo paper son 1.24x de ruido total con un
   telescopio de 0.75 m y **2.83x** con uno de 2.3 m, así que resolverla solo
   hace falta para el telescopio grande, que es justo el de su mejor presupuesto.
9. **Ningún modelo de la dependencia angular de la radiancia.** La Tabla 1 es
   radiancia **cenital** (lo dice su Fig. 3) y ninguna fuente publica dependencia
   con elevación, azimut o ángulo solar; Ntanos et al. mantienen `H` constante a
   lo largo de un pase entero y lo dicen. Tamaño de lo ignorado: a 20° de
   elevación el camino de dispersión son 2.92 masas de aire, **4.66 dB** si la
   radiancia siguiera a la masa de aire. No se aplica ese escalado, y un test de
   `background.py` aserta *por ausencia* que ninguna función del módulo acepta
   una elevación.
10. **Fase lunar.** El único asidero publicado es un intervalo (1.5e-5 sin luna a
    1.5e-3 con luna llena a 1550 nm, un factor 100), y es lo que se expone. Un
    modelo de irradiancia lunar (ROLO o equivalente) no se localizó libre y
    verificado.
11. **Convención del campo de visión.** Las dos fuentes dan el FOV del receptor
    **en unidades distintas bajo el mismo nombre** —ángulo en la Ec. (1) de la
    UIT, estereorradianes en la Ec. (19) de Ntanos— y ninguna dice si el ángulo
    es completo o semiángulo. La aritmética de la UIT lo resuelve (`π θ²/4` es el
    ángulo sólido de pequeño ángulo de un cono de semiángulo `θ/2`, luego su
    `θ_r` es el ángulo completo) y esa es la convención que usa QuOSS, con el
    nombre del argumento diciéndolo. Las dos lecturas equivocadas están medidas:
    **6.02 dB** leerlo como semiángulo, **41.05 dB** pasar el ángulo a la fórmula
    que quiere estereorradianes.

### El caveat de Ntanos et al. 2021, que es la fuente V2 de punta a punta

Es el mejor candidato a reproducción completa —parámetros declarados, ecuaciones
numeradas, resultado publicado— y por eso hay que escribir lo que no cuadra:

- SimulCTTC documentó que **la Tabla 1 de ese paper no es reproducible** desde
  los parámetros que el propio paper declara: sus números son internamente
  inconsistentes por un factor ~5.5.
- Su `q = 2/5` (§4.1) es **inconsistente con su propia Ec. A1** dada la razón de
  intensidades 4:1:16 que declara; lo consistente es 2/21.
- Lo que **sí** se reprodujo son los ratios entre estaciones: publicado
  1 : 0.28 : 0.084, medido 1 : 0.29 : 0.10.
- Su Ec. (5) **tal como está impresa** (`(8/w_0)²` donde la identidad exige
  `8/w_0²`) es 8 veces mayor, **9.03 dB optimista**, y con sus propios parámetros
  devuelve una transmitancia de 1.36. Encontrado al implementar
  `channel/beam.py`.
- Su Ec. (20) llama «probability» a `t_gate × cps`, que es el **número esperado**
  de cuentas y no una probabilidad: con la luz solar brillante que la propia UIT
  tabula a 850 nm, su receptor y su puerta de 1 ns, esa «probabilidad» vale
  **3.42** (y 1.09 con su telescopio intermedio). QuOSS devuelve `1 - exp(-µ)` y
  avisa por encima de 0.1 cuentas por puerta, umbral **derivado**: es donde la
  lectura lineal sobreestima un 5 %.
- Su afirmación de que «even in the case of full moon, the background radiance
  corresponds to 10 kcps in the photon counter at most» **no es reproducible**
  desde su propia Ec. (19) sin elegir cuál de sus tres telescopios: da 8.1 kcps a
  0.75 m, 24.4 a 1.3 m y **76.4 a 2.3 m**. Con la cadena de pérdidas que la
  misma sección declara, el de 2.3 m baja a 17.7 kcps, todavía 1.8x por encima.

Consecuencia para los tests: se aserta la **forma** de la curva y los **ratios**,
no la cifra absoluta, y el test dice por qué. Un V2 cuyo valor absoluto no cierra
sigue siendo información — pero solo si se declara cuál de sus afirmaciones se
está usando.

## Consecuencias

### Lo que esto cierra

- **Cierra** la cuestión de qué se puede escribir en un docstring de `channel/`.
- **Cierra** la tentación de heredar `FORMULAS.md` tal cual: es un índice de
  búsqueda, y se dice dónde.
- **Cierra** la discrepancia de Bufton antes de que cueste una tarde.

### Lo que no cierra

- **No cierra** el acceso a A&P. Si algún día se consigue el libro, las citas por
  ecuación se pueden añadir, y los huecos 1 y 2 se cierran. Hasta entonces el
  código no pierde nada: las fórmulas ITU-R son las mismas.
- **No cierra** el hueco de los detectores. Cerrarlo es leer hojas de datos de
  Excelitas e ID Quantique, que son públicas, y transcribirlas con su versión.
- **Coste de cambiar de fuente primaria:** bajo mientras los huecos estén
  declarados. Cada fórmula lleva su cita en su docstring, así que cambiar de
  fuente es un grep, no una auditoría.

## Alternativas descartadas

**Copiar las citas de SimulCTTC.** Es lo más rápido y produce un código que
*parece* mejor referenciado que el que resulta de esta decisión, porque lleva
números de ecuación en sitios donde este va a llevar un hueco declarado. Se
descarta porque el proyecto ya tiene un caso propio de cita que apuntaba a un
paper sin el contenido citado, y porque una cita que nadie ha comprobado es una
afirmación sin defensa — justo lo que la Norma 1 de `CLAUDE.md` existe para
impedir.

**Citar A&P sin número de ecuación, pero usando sus fórmulas.** Tentador porque
las fórmulas son correctas y de dominio común. Se descarta porque no resuelve
nada: si la fórmula viene de una fuente que no se ha abierto, el número que sale
tampoco está verificado, y la cita general da una falsa sensación de trazabilidad.
Usar ITU-R cuesta lo mismo y sí se puede comprobar.

**Declarar el canal «no validado» y seguir.** Se descarta porque el canal es
precisamente donde el proyecto se juega el paper, y porque hay fuentes gratuitas
suficientes para no tener que hacerlo.

## Referencias

- [ADR 0002](0002-frames-and-time-scales.md) — el presupuesto de error medido en
  vez de afirmado; misma disciplina, aplicada a la procedencia.
- [`tests/golden/README.md`](../../tests/golden/README.md) — los cuatro niveles
  V1–V4, y la sección «Gaps, stated rather than filled» donde viven los huecos de
  arriba.
- `notes/LAST_CHANGES.md` §14.1 — los «219 km», el precedente que motiva la regla
  de «medido en este repo significa medido por un test que corre».
- Recomendación UIT-R P.1621-2, *Propagation data required for the design of
  Earth-space systems operating between 20 THz and 375 THz*, 07/2015.
- Recomendación UIT-R P.1622, *Prediction methods required for the design of
  Earth-space systems operating between 20 THz and 375 THz*, 04/2003.
- A. Ntanos et al., «LEO Satellites Constellation-to-Ground QKD Links: Greek
  Quantum Communication Infrastructure Paradigm», *Photonics* **8**(12):544, 2021.
- A. A. Farid y S. Hranilovic, «Outage Capacity Optimization for Free-Space
  Optical Links With Pointing Errors», *J. Lightwave Technol.* **25**(7):1702, 2007.
- I. I. Kim, B. McArthur y E. Korevaar, «Comparison of laser beam propagation at
  785 nm and 1550 nm in fog and haze for optical wireless communications»,
  *Proc. SPIE* **4214**:26, 2001.
- X. Ma, B. Qi, Y. Zhao y H.-K. Lo, «Practical decoy state for quantum key
  distribution», *Phys. Rev. A* **72**, 012326, 2005.
- C. C. W. Lim, M. Curty, N. Walenta, F. Xu y H. Zbinden, «Concise security
  bounds for practical decoy-state quantum key distribution», *Phys. Rev. A*
  **89**, 022307, 2014.
- L. C. Andrews y R. L. Phillips, *Laser Beam Propagation through Random Media*,
  2.ª ed., SPIE Press PM152, 2005. **Citado sin número de ecuación, a propósito:
  ver el hueco 1.**

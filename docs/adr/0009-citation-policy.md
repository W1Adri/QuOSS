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
| Escintilación en camino horizontal (onda plana); profundidades de desvanecimiento; extinción específica | **ITU-R P.1814** (2007) | (3), (8), Tabla 4 |
| Onda esférica; promediado de apertura en camino horizontal; asíntotas de régimen fuerte | **Kaushal & Kaddoum**, arXiv:1506.04836 (fuente secundaria, ver hueco 17) | (8)–(11), (20), (21) |
| Rytov en camino inclinado; escintilación en régimen fuerte | **Ntanos et al. 2021**, *Photonics* 8(12):544 | (12), (13) |
| Perfil HV modificado con la altitud de la estación | Ntanos et al. 2021 | (11) |
| Potencia y cuentas de fondo | Ntanos et al. 2021 | (19), (20) |
| Rendimiento y QBER a partir del canal | Ntanos et al. 2021 **Apéndice A** | (A4)–(A6) |
| Tasa de detección, afterpulsing y tasa de error con detector real | **Lim et al. 2014**, §Evaluation | `D_k`, `R_k`, `e_k` (sin numerar en el paper) |
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
   muerto 30 ns, y «no after-pulsing effect») y de Lim et al. 2014 §Evaluation
   (InGaAs: η 10 %, p_dc 6e-7, p_ap 4e-2). Las dos frases se releyeron del PDF
   al implementar `channel/detector.py` (2026-09-10), y las dos son literales.

   **Lo que la implementación midió, que es lo que convierte el hueco en algo
   accionable:** no son «valores típicos» con dispersión, son **dos
   instrumentos** que difieren en 10 dB de eficiencia y en un factor infinito de
   afterpulsing, y la diferencia decide una conclusión de diseño. Con el
   nanohilo, estrechar la puerta de 1 ns a 100 ps quita 10 dB de ruido (lo que
   promete `background.py`); con el APD de InGaAs quita **0.22 dB**, porque el
   afterpulsing no escala con la puerta y a 1e-3 de probabilidad de clic es 67
   veces las cuentas oscuras. Así que «estrecha la puerta» es una frase
   condicional y la condición es qué detector hay dentro. Por eso los dos juegos
   son constantes con el nombre de su fuente en el identificador, y hay un test
   que aserta que ninguna constante del módulo se llama en genérico.

   **Sub-hueco nuevo, y es de unidades:** las dos fuentes publican la cuenta
   oscura en **convenciones distintas** —Ntanos una tasa (300 cps), Lim una
   probabilidad por puerta (6e-7)— y **Lim et al. no declara ninguna anchura de
   puerta en todo el paper**, así que la conversión entre las dos no se puede
   hacer con sus números. `dark_count_rate_from_probability_cps` pide la puerta
   como argumento y la suposición es del llamante. Leído a la puerta de 1 ns de
   Ntanos, el 6e-7 de Lim son 600 cps, el doble del nanohilo; leído a 10 ns son
   60, la mitad. Y hay una **coincidencia que no es corroboración**: los dos
   nanohilos de Ntanos a 300 cps en su propia puerta de 1 ns dan exactamente
   6e-7 por puerta, el mismo número que Lim publica **por detector** para otra
   tecnología. Está asertada como coincidencia
   (`TestAgainstNtanosEtAl::test_the_equality_with_lims_dark_count_probability_is_a_coincidence`)
   precisamente para que nadie la lea como dos fuentes independientes
   confirmándose.
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
12. **Si un afterpulse puede a su vez producir otro afterpulse.** Lim et al.
    multiplican la tasa de detección por `1 + p_ap`: un afterpulse por clic
    primario. Si el afterpulse cascadea —y es una avalancha real, que atrapa
    portadores reales— el factor es la serie geométrica `1/(1 - p_ap)`. Ninguna
    fuente verificada lo decide. La diferencia es `1/(1 - p_ap²)`: **0.16 % con
    el 4e-2 publicado**, 5 % en `p_ap = sqrt(1/21) = 0.2182`. Se devuelve la
    forma publicada y por encima de ese umbral se registra un `WARNING` que
    lleva las dos cifras dentro, igual que la interpolación de radiancia lleva
    la regla alternativa.
13. **Si el tiempo muerto es extensible.** Es una propiedad del hardware —el
    modelo no-paralizable supone una ventana fija tras cada cuenta *registrada*,
    el paralizable la reinicia con cada llegada— y **ninguna de las dos fuentes
    lo dice** de sus detectores. Los dos modelos coinciden a primer orden y se
    separan un 5 % en `R·τ = 0.3554`, que con los 30 ns de Ntanos son 11.8 Mcps;
    sus techos son `1/τ` = 33.3 Mcps y `1/(e·τ)` = 12.3 Mcps. Consecuencia de
    diseño, no solo de precisión: el paralizable **no es invertible** pasado su
    máximo (dos tasas incidentes dan la misma lectura, 16.3 y 59.4 Mcps dan
    10 Mcps), así que `incident_count_rate_cps` existe solo para el otro y la
    ambigüedad es una función que falta en vez de una suposición escondida. Para
    los enlaces publicados el hueco no cuesta nada —a 500 kcps la pérdida es del
    1.5 % con cualquiera de los dos— y eso también está medido.
14. **La extinción atmosférica: la ley de escala está publicada y el número que
    escala no.** La Ec. (7) de Ntanos et al., `L_a = L_zen^(1/cos ζ)`, está
    numerada y es verificable; su `L_zen` —la transmitancia vertical— **no
    aparece en el paper**, que cita una referencia para la ecuación y ningún
    valor. Y la ITU-R P.1621-2 publica la absorción (§2) y la dispersión (§3)
    **solo como figuras**: las Figs. 1, 2 y 4 son gráficas, sin tabla ni forma
    cerrada al lado. Leer un valor de una curva y presentarlo como publicado es
    exactamente lo que esta política prohíbe.

    **Consecuencia en el código, y es una firma:** `zenith_transmittance` es un
    argumento **obligatorio y sin defecto** de `atmospheric_transmittance` y de
    `downlink_loss_budget`. Quien no tenga extinción escribe `1.0` en su propio
    código y con eso lo declara; no hay ningún valor del argumento que
    signifique en silencio «no lo he pensado». Hay un test que aserta que el
    parámetro no tiene defecto, porque la forma fácil de cerrar este hueco por
    accidente es poner uno.

    **Lo que el hueco cuesta, medido:** la §4.2.1 de Ntanos et al. afirma un
    total de bajada de 20 dB a 600 km con telescopio grande. Todos los demás
    términos, calculados con los parámetros que el propio paper declara y
    combinados como él los combina, más el truncamiento de apertura que sus
    ecuaciones no llevan (ver abajo), suman **19.094 dB**. El residuo son
    **0.906 dB**, que leídos por su Ec. (7) son `L_zen = 0.812` — una
    transmitancia cenital de cielo claro perfectamente ordinaria a 1550 nm.

    Así que su 20 dB es **compatible** con este presupuesto más una extinción no
    declarada de tamaño plausible, y hasta ahí llega la afirmación: un residuo
    que cae en un rango creíble **no es prueba** de ser la cosa a la que se
    parece, y el paper no declara extinción en ninguna parte.

    **La mitad más interesante es lo que hubo que añadir para que el residuo
    fuera plausible.** Sin el término de truncamiento, el mismo presupuesto suma
    15.741 dB y deja **4.259 dB**, que exigirían `L_zen = 0.375` — una extinción
    vertical de 4.26 dB a 1550 nm con cielo despejado, un orden de magnitud por
    encima de cualquier valor creíble. Los decibelios que faltaban **no estaban
    en la atmósfera, estaban en el transmisor**. Todo está en
    `tests/channel/test_link_budget.py::TestAgainstNtanosEtAl::test_their_twenty_decibel_best_case_does_not_reproduce`,
    que aserta las dos lecturas y los dos `L_zen` implícitos.

    **Sub-hueco de masa de aire:** el exponente `1/cos ζ` es una atmósfera
    plana, que diverge en el horizonte donde el camino real es finito. La
    comparación honesta aquí no es una cita sino geometría —el camino por una
    capa esférica de 8.5 km sobre una Tierra de 6371 km— y la secante se pasa un
    0.20 % a 30°, **0.50 % a 20°** (el suelo de elevación del propio paper, así
    que ahí no cuesta nada), 2.1 % a 10° y 8.1 % a 5°. El 5 % cae en **6.427°**,
    que es `SECANT_AIRMASS_ELEVATION_LIMIT_RAD`, derivado con un buscador de
    raíces en el test y no elegido. Por debajo sale un `WARNING` con las dos
    masas de aire dentro; el valor devuelto **sigue siendo el del modelo
    publicado**, porque sustituirlo en silencio por el esférico dejaría al módulo
    sin reproducir nada.
15. **El truncamiento de la apertura transmisora: una convención, no una cita —
    y la predicción que el propio repo tenía escrita estaba mal por 2.7 dB.**
    `beam.py` propaga una gaussiana **sin truncar**, con radio de cintura igual
    al **radio** de la apertura, que es lo que implica la Ec. (6) de Ntanos et
    al. Una apertura real es un agujero, y con esa cintura el borde corta
    `exp(-2) = 13.5 %` del haz.

    El número tentador es ese 13.5 %: **0.632 dB** de luz que nunca sale. Es la
    respuesta correcta a otra pregunta. En el eje y en campo lejano lo que
    integra es la **amplitud**, y la intensidad es su cuadrado, así que perder la
    cola de la integral de amplitud cuesta **dos veces** mientras la
    normalización de potencia la recupera **una**. Con `α = a/w_t`, lo que el
    campo lejano sin truncar sobreestima por unidad de potencia **lanzada** es

        η_trunc(α) = [1 - exp(-α²)]² / [1 - exp(-2α²)]

    que a `α = 1` vale 0.4621: **3.352 dB**. Hay tres números y cada uno tiene su
    potencia de referencia —0.632 dB contra el láser, **3.352 dB contra lo que
    salió de la apertura**, 3.984 dB contra el láser con los dos efectos juntos—
    y son **una identidad, no tres medidas**. `link_budget.py` aplica el de en
    medio, porque la potencia de transmisión de un presupuesto de enlace es la
    que salió del telescopio; si la `µ` del llamante está definida en la fuente,
    los 0.632 dB extra van en `static_loss_db` y esa decisión es suya, porque
    ninguna fórmula puede saberlo.

    **Por qué esto es un hueco y no física implementada sin más:** `α` es un
    parámetro de diseño del terminal, no una constante. A `α = 2` el término son
    0.16 dB y a `α = 3` ha desaparecido, que es para lo que existe un expansor de
    haz. El defecto es `α = 1` porque es **el único valor consistente** con los
    radios de haz que calcula `beam.py`, no porque ninguna fuente lo publique, y
    hay un test que lo aserta contra la constante privada de ese módulo para que
    cambiar la convención allí no deje este término huérfano.

    **Y lo que hace falta decir en voz alta:** `tests/golden/README.md` tenía
    este término predicho en **0.63 dB** desde antes de que el módulo existiera.
    Era el número de potencia recortada, no el del error del modelo. Está
    corregido allí con la derivación al lado, y la forma cerrada está verificada
    contra la integral de difracción evaluada por cuadratura
    (`TestTheTransmitterClipsItsOwnBeam`), no contra el álgebra que la produjo.

16. **El modelo de canal de la §Evaluation de Lim et al. 2014 es internamente
    inconsistente, y su curva de bloque 1e4 no se reproduce.** Su tasa de error
    impresa es `e_k = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2`, con
    `eta_ch` —solo la fibra— en el término de desalineamiento, mientras que la
    tasa de detección de al lado lleva `eta_sys = eta_ch eta_Bob`, **diez veces
    menor**. Ese término aporta entonces **3.9 puntos** de QBER a pérdida cero y
    4.8 a 100 km en un sistema cuya óptica está especificada al 0.5 %; con
    `eta_sys` aporta **0.48** a cualquier distancia, que es `e_mis` diluido por
    los afterpulses. El cociente entre las dos lecturas es **8.07** a pérdida
    cero y **9.98** a 100 km —el `1/eta_Bob` que sobra— y, como el término
    impreso no escala con la eficiencia del detector mientras las detecciones de
    al lado sí, la tasa de error óptico que implica mejora al mejorar el
    detector, cosa que no hace ninguna óptica.

    **Medido al implementar `qkd/finite_key.py` (2026-09-12), que es lo que
    convierte la ambigüedad en una decisión:** cruzando esa lectura con la de si
    `e_k` cuenta errores por puerta o por detección salen cuatro modelos, y sus
    cocientes de tasa entre bloques de 1e9 y 1e7 a 100 km son **1.79**, 2.73,
    1.46 y 1.47. El paper dice, de su propia Fig. 1, «about 1.75». Solo la
    lectura físicamente consistente —`eta_sys` en los dos sitios, errores por
    puerta— cae sobre su número, así que es la que se implementa, y la elección
    descansa en una cifra publicada y no en el gusto.

    **Lo que sigue sin reproducirse:** dicen que «even if we use a block size of
    1e4, cryptographic keys can still be distributed over a fiber length of
    135 km». Con esa lectura, un bloque de 1e4 detecciones no certifica clave **a
    ninguna distancia**, ni siquiera a pérdida cero. El desajuste es de
    exactamente una década —nuestra curva de 1e5 es su curva de 1e4: positiva a
    135 km, muerta antes de 150 km— y las dos causas candidatas, un convenio
    distinto sobre qué cuenta `n_X` y una resolución distinta de la ambigüedad de
    arriba, no están decididas por nada impreso. `tests/qkd/test_finite_key.py`
    **asierta el desacuerdo**, para que dejar de tenerlo obligue a reescribir
    esto. Ver [ADR 0010](0010-decoy-and-finite-key.md).

17. **El camino horizontal tiene una fuente primaria para la onda plana y una
    secundaria para el resto.** ITU-R P.1814 da la onda plana y su Tabla 4, y
    nada más de turbulencia. La onda esférica y el promediado de apertura vienen
    de Kaushal & Kaddoum (arXiv:1506.04836), un *survey* de acceso abierto con
    ecuaciones numeradas —prioridad (b)— que cita a Churnside 1991 y Andrews
    1992, que no se pudieron abrir. Leído en el PDF de arXiv; los números de
    ecuación son los de ese PDF. **Lo que lo compensa en parte:** el promediado de
    onda plana coincide al **0.67 %** con las Ecs. (6)–(7) de P.1622 tumbadas
    sobre un camino horizontal (el 1.8 del resultado es exacto). **Lo que no:** el
    promediado de onda esférica, `0.214`, no tiene segunda fuente.
18. **No hay onda gaussiana.** Un haz real no es ni plano ni esférico, y cerca de
    su rango de Rayleigh ninguna de las dos formas cerradas es la correcta. Las
    fórmulas de onda gaussiana están en Andrews & Phillips (hueco 1).
    `horizontal_loss_budget` avisa cuando la onda declarada está del lado
    equivocado del rango de Rayleigh, con el factor 2.46 que separa las dos.
19. **Ni retrorreflector ni *beam wander* horizontal.** Un enlace de ida y vuelta
    cruza el mismo aire dos veces con pasos correlacionados (retrodispersión
    reforzada); tratarlo como un camino de `2L` es una aproximación sin fuente.
    Kaushal & Kaddoum escriben `σ_BW² = 1.44 C_n^2 L² W_0^(-1/3)` para el *beam
    wander*, sin número de ecuación; no se implementa.

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
- Su **total de enlace de 20 dB** (§4.2.1, «the total link loss for a 600 km
  link distance can get as low as 20 dB in total») **no se reproduce**, pero el
  residuo dejó de ser absurdo: sus propios términos suman 15.741 dB, y con el
  truncamiento de apertura que sus ecuaciones no llevan (hueco 15) suben a
  **19.094 dB**. Los **0.906 dB** que quedan son `L_zen = 0.812`, una extinción
  cenital de cielo claro ordinaria. Compatible, no reproducido: el paper no
  declara ni extinción ni truncamiento. Ver los huecos 14 y 15.
- Su Ec. (18) devuelve un **número negativo y lo llama pérdida**: es
  `10 log10` del cuantil de la irradiancia, o sea el **nivel** de señal
  respecto de la media, no la caída desde ella. Vale −1.282 dB en la geometría
  de referencia al 1 % de outage, y sumarla a un presupuesto de pérdidas
  positivas tal como está impresa deja el total equivocado en **el doble** del
  desvanecimiento. `link_budget.scintillation_fade_db` devuelve la forma
  negada, y hay un test con la Ec. (18) transcrita literalmente al lado para
  que la diferencia sea entre dos expresiones y no una afirmación sobre una.
- Su práctica de **sumar dos cuantiles al 1 %** —la pérdida de apuntado de §4.1
  y la Ec. (18), las dos a `p_0 = 1 %`— no da un presupuesto al 1 %. Las dos
  colas tienen forma cerrada en decibelios (exponencial la de apuntado,
  gaussiana la de escintilación), así que su suma es una **gaussiana modificada
  exponencialmente** y el cuantil conjunto es exacto: 1.668 dB donde la suma da
  2.312 dB. Son **0.644 dB** de margen que nadie pidió, y sobre todo una
  etiqueta equivocada — ese presupuesto es del **0.066 %** de outage, quince
  veces más estricto que el número impreso al lado. Es conservador, no
  peligroso; lo que no es, es lo que dice ser.
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
- Su Ec. (A6) escribe el rendimiento de fondo como `Y_0 = P_dc + P_noise`, una
  **suma de probabilidades donde la unión es `1 - (1-P_dc)(1-P_noise)`**. De
  noche las dos coinciden a 1.2e-6 relativo, y esa cifra no es una tolerancia
  sino la respuesta: la suma sobreestima en `µ/2`, el segundo término de
  `1 - exp(-µ)`, con `µ = 2.37e-6`. Con su propio fondo diurno (3.42 cuentas por
  puerta) la suma da 3.42 y la unión 0.967. Es el mismo patrón que su Ec. (20),
  y `detector.py` lo resuelve con una sola regla: **las medias se suman y la
  exponencial se hace una vez, al final**.
- Su afirmación de que «even in the case of full moon, the background radiance
  corresponds to 10 kcps in the photon counter at most» **no es reproducible**
  desde su propia Ec. (19) sin elegir cuál de sus tres telescopios: da 8.1 kcps a
  0.75 m, 24.4 a 1.3 m y **76.4 a 2.3 m**. Con la cadena de pérdidas que la
  misma sección declara, el de 2.3 m baja a 17.7 kcps, todavía 1.8x por encima.

Consecuencia para los tests: se aserta la **forma** de la curva y los **ratios**,
no la cifra absoluta, y el test dice por qué. Un V2 cuyo valor absoluto no cierra
sigue siendo información — pero solo si se declara cuál de sus afirmaciones se
está usando.

**Y una afirmación suya que sí reproduce**, que merece decirse en un documento
donde casi todas las demás no: su §4.2 argumenta que la atenuación del enlace
impide que sus detectores se saturen por tiempo muerto. Con sus propios números
—100 MHz, 30 ns, µ = 0.5 y su mejor caso de 20 dB— entran 500 kcps en un
detector cuyo techo son 33.3 Mcps, y la pérdida es del **1.5 %** (1.0 % en la
forma con puerta). Es correcta, y con dos órdenes de magnitud de margen.

### El caveat de Lim et al. 2014, que es la fuente V2 del detector

Es la primera vez que se usa su §Evaluation, y su forma impresa de la tasa de
detección es una **linealización**: escribe `D_k = 1 - (1 - 2 p_dc) exp(-η_sys k)`,
donde `2 p_dc` es la unión de las cuentas oscuras de sus dos detectores a primer
orden y la unión exacta es `(1 - p_dc)²`. Con su `p_dc = 6e-7` las dos coinciden a
7e-12 —nadie necesitaba esta corrección— pero `1 - 2 p_dc` **se hace negativo por
encima de `p_dc = 0.5`**, y entonces la «probabilidad de detección» pasa de 1: con
el 0.967 de fondo diurno que devuelve `background.py` para el receptor de Ntanos,
la forma impresa da **1.93**. Las dos se separan un 5 % en `p_dc = 0.179`.

QuOSS reproduce su `D_k` exactamente (a 3e-7 relativo, cota **derivada**: el
truncamiento es `p_dc²/(η_sys k + 2 p_dc) ≤ p_dc/2`) sumando medias y
exponenciando una vez, que es la misma regla que arregla la Ec. (A6) de Ntanos.
Y la parte útil de su modelo de error es un cruce, no una fórmula: sus dos
términos de ruido son `p_dc` y `p_ap·D_k/2`, así que el afterpulsing domina en
cuanto `D_k > 2 p_dc/p_ap = 3e-5`, es decir **por debajo de 42 dB de pérdida
total** con µ = 0.5 — o sea en todo el rango útil de un enlace satelital.

**Ampliado el 2026-09-12, al usar su §Evaluation por segunda vez para
`qkd/finite_key.py`:** el tercer término de ese mismo `e_k` lleva `eta_ch` donde
la tasa de detección de al lado lleva `eta_sys`, y esa asimetría no es un detalle
—multiplica por 8 la contribución del desalineamiento al QBER, de 0.48 a 3.9
puntos a pérdida cero—. Cuál de las dos lecturas es la
suya se decidió contra su propio cociente publicado entre tamaños de bloque; es el
hueco 16 de la lista de arriba, con las cuatro cifras que lo deciden.

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
- **No cierra** el hueco de los detectores (hueco 5). Cerrarlo es leer hojas de
  datos de Excelitas e ID Quantique, que son públicas, y transcribirlas con su
  versión. Lo que sí cambió al implementar `channel/detector.py` es que el hueco
  está **medido**: se sabe qué decide (0.22 dB contra 10 dB al estrechar la
  puerta), qué sub-hueco de unidades esconde (Lim no declara puerta) y qué
  coincidencia no hay que leer como corroboración. Un hueco medido se puede
  priorizar; uno declarado solo se puede recordar.
- **No cierra** los huecos 12 y 13, que no son valores sino **modelos**: si un
  afterpulse cascadea y si el tiempo muerto es extensible. Ninguna hoja de datos
  de las de arriba responde al primero; el segundo suele estar en ellas, así que
  se cierra con el mismo trabajo que el hueco 5.
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

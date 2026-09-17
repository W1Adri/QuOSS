# ADR 0021 — Camino horizontal: `C_n^2` constante, sin elevación, y la onda declarada

- **Estado:** aceptada
- **Fecha:** 2026-09-15
- **Etapa:** 2.2 (`channel/`), para la escalera de experimentos de tierra (GE-0b, GE-1).
- **Afecta a:** `channel/horizontal.py` (nuevo), `channel/link_budget.py`
  (`_assembled_loss_budget`, `_emg_cdf`), `channel/pointing.py`
  (`equivalent_beam_radius_m`).
- **Extiende** al [ADR 0009](0009-citation-policy.md): dos fuentes nuevas y tres
  huecos nuevos (17–19).

---

## Contexto

### Qué es un camino horizontal, para quien llegue nuevo

Todo el canal de QuOSS describía un satélite. La luz baja desde fuera de la
atmósfera, y la turbulencia que cruza es la **integral** del perfil
Hufnagel-Valley desde la estación hasta 20 km, recorrida a lo largo de
`1/sin(θ)`. La elevación `θ` cambia cada segundo, y con ella todo.

Un banco con emulador de turbulencia (GE-0b) y un enlace horizontal de unos
cientos de metros a unos kilómetros (GE-1) no tienen nada de eso. La luz cruza
aire a **una** altura, así que `C_n^2` —el parámetro de estructura del índice de
refracción, que mide cuánto dobla la luz el aire, en m^(-2/3)— es **una
constante del camino**, y **no hay elevación**.

### Por qué no vale «el inclinado con un ángulo pequeño»

Es la tentación obvia y es un número plausible y equivocado. La fórmula inclinada
a 0.1° integra el perfil a lo largo de una línea de **11 000 km**: da una varianza
de **7 103 Np²**, contra **0.343** de un kilómetro horizontal en aire con el mismo
`C_n^2` de suelo. Un factor **2.1e4**
(`tests/channel/test_horizontal.py::TestNoSignatureTakesAnElevation::test_a_slant_path_at_a_low_angle_is_not_a_horizontal_path`).

### Y por qué importa antes de comprar nada

GE-1 se dimensiona con dos números: la distancia y la apertura del receptor.
Sin un camino horizontal, QuOSS no podía decir nada de ninguno de los dos.

---

## Decisión

1. **Un módulo propio, `channel/horizontal.py`, cuyas firmas no aceptan elevación,
   ni altura de estación, ni viento.** Asertado por ausencia, como en
   `background.py` y `pcflos.py`, y además por el código fuente: el módulo no
   importa el perfil vertical y de `turbulence` solo toma dos constantes.
2. **Onda plana: ITU-R P.1814 Ec. (8)**, `23.17 k^(7/6) C_n^2 L^(11/6)` en dB²,
   que dividido por 18.861 da **1.2285** en Np². Es la varianza de Rytov del
   libro (1.23) al redondeo de 23.17. **Onda esférica y promediado de apertura:
   Kaushal & Kaddoum** (arXiv:1506.04836), Ecs. (9), (20) y (21).
3. **La onda es un argumento obligatorio, `PathWave`, sin defecto.** Plana y
   esférica difieren un factor **2.46** en la varianza, y cuál describe el haz
   depende del transmisor. `horizontal_loss_budget` avisa cuando la onda
   declarada contradice el rango de Rayleigh del transmisor, con los dos
   números dentro.
4. **La extinción, `extinction_db_per_km`, obligatoria y sin defecto**, por la
   misma razón que `zenith_transmittance` (hueco 14): P.1814 da la forma
   (Ec. (3), dB/km) y las leyes de niebla, lluvia y nieve, pero ningún número de
   aire limpio.

   **Actualizado el 2026-09-15:** ahora hay de dónde sacarlo.
   `channel/extinction.py` ([ADR 0023](0023-traceable-extinction.md)) convierte
   una visibilidad en esta misma unidad por la Ec. **(4)** de la P.1814 —la que
   este ADR no había mirado—, con el detalle de que esa ecuación **imprime
   dB/km y devuelve nepers por kilómetro**, un factor 4.343. El argumento sigue
   sin defecto: lo que cambia es que quien lo rellena puede calcularlo en vez de
   inventarlo. Para GE-1, 23 km de visibilidad son **0.192 dB/km** a 1550 nm,
   frente a los 0.2 dB/km que la tabla de ejemplo de más abajo supone a mano.
5. **Mismo `LossBudget` y mismo ensamblado que la bajada**, por una función
   privada compartida, `_assembled_loss_budget`. Así las dos no pueden sumar sus
   términos de forma distinta, y un modelo de régimen fuerte que se ponga ahí
   (etapa 1.2) lo heredan las dos.
6. **Régimen débil declarado con su coste.** Por encima de una varianza de Rytov
   de 1, `horizontal.weak-fluctuation-limit-exceeded` con la asíntota de régimen
   fuerte de Kaushal & Kaddoum (10)/(11) como medida —no como corrección, porque
   la asíntota solo vale para `σ_R² ≫ 1`—.

### Cómo se comprueba (la defensa de las fuentes)

- **V2:** las seis celdas ópticas de la Tabla 4 de P.1814, a sus dos decimales.
  El error máximo es 0.0039 dB contra una tolerancia derivada de 0.005 dB más el
  redondeo del coeficiente.
- **Entre fuentes, onda plana:** la Ec. (4a) de P.1622 —la integral inclinada que
  el proyecto ya usa— tumbada sobre un camino horizontal. Con `h = s cos ζ` la
  `sec^(11/6)` se cancela exactamente y queda `2.253 · 6/11 = 1.2289`: a
  **3.7e-4** de P.1814, dentro de los 4.4e-4 que permiten los dos coeficientes
  impresos a cuatro cifras.
- **Entre fuentes, promediado:** las Ecs. (6)–(7) de P.1622 tumbadas igual dan
  `A = 1/(1 + 1.8 (D²/λL)^(7/6))`, con el 1.8 **exacto** (`1.1 · 18/11`). La
  Ec. (20) de Kaushal & Kaddoum da `1.07 (π/2)^(7/6) = 1.812`. **0.67 %** de
  diferencia, dentro del 4.5 % que permite el «1.1» de dos cifras. Y de paso
  confirma con una segunda fuente la lectura en micrómetros del 1.1e7 de P.1622:
  en metros discreparía siete órdenes de magnitud.

### Un ejemplo con números, con el régimen de cada fila a la vista

**Corregido el 2026-09-15.** La versión anterior de esta tabla daba «56.8 a 636
kbit/s, un factor 11.2» como un número, y las dos filas estaban calculadas con
`PathWave.PLANE` a **3.16 rangos de Rayleigh** del transmisor —el lado
equivocado de la idealización, que el propio módulo avisaba en un log que nadie
leyó (`horizontal.plane-wave-beyond-the-rayleigh-range`)—.

Ojo a qué varía la comparación, porque es fácil leerla mal: el **transmisor** es
de 2.5 cm en las dos filas y lo que cambia es la **lente receptora**. El rango de
Rayleigh solo depende del transmisor, `z_R = π (D_T/2)² / λ = 316.7 m`, así que
`L / z_R = 3.158` en **las dos**. Las dos filas son el mismo régimen, y no es el
régimen en que se calcularon.

Enlace GE-1 de 1 km, `C_n^2 = 1e-14` (la columna «moderada» de P.1814), 1550 nm,
transmisor de 2.5 cm, 5 µrad de jitter, 0.2 dB/km, receptor Ntanos et al.,
BB84 decoy asintótico al 1 % de outage:

| Lente | `L/z_R` | Geom. | Escint. plana | Escint. esf. | Clave plana | Clave esf. |
|---|---|---|---|---|---|---|
| 2.5 cm | 3.158 | 7.78 dB | 3.80 dB | 2.87 dB | 56.8 kbit/s | **70.2 kbit/s** |
| 10 cm | 3.158 | 0.24 dB | 1.12 dB | 1.45 dB | 636.2 kbit/s | **589.9 kbit/s** |
| factor | — | — | — | — | 11.20 | **8.41** |

A 3.16 rangos de Rayleigh el haz se ha ensanchado a 3.3 veces su cintura, así
que **la columna esférica es la citable** y la plana es el otro borde del
intervalo. La respuesta verdadera es la onda gaussiana, que es el hueco 18 y no
tiene fuente abierta aquí. Lo que este módulo puede afirmar es:

> La lente vale **un factor entre 8.4 y 11.2**, y el enlace de 10 cm da **entre
> 590 y 636 kbit/s**. Un intervalo, no un número.

Y el intervalo **no está ordenado como las varianzas de punto**. Una onda
esférica escintila 2.46 veces menos en un punto, pero su irradiancia está
correlacionada en una escala mayor, así que una lente de 10 cm la promedia peor
(el 0.214 de Kaushal & Kaddoum contra el 1.07). A 2.5 cm la plana es el borde
pesimista y a 10 cm es el optimista: por eso el intervalo hay que **calcularlo**,
no razonarlo desde el 2.46.
(`tests/channel/test_horizontal.py::TestTheHeadlineLensComparisonIsABracket`.)

El QBER apenas se mueve en ninguna de las cuatro celdas (1.01 % contra un suelo
de 1 % de desalineamiento), así que para GE-1 la palanca es la pérdida, no la
tasa de error.

### Los límites de operación, como restricciones y no como notas

Dos cotas duras de GE-1, expuestas como funciones con test y no como frases en
este ADR, por la misma razón que el ADR 0009 da para cualquier número citado:
una frase no se puede llamar ni rederivar, y ya hubo una que estuvo mal en
quince sitios.

- **`weak_theory_path_limit_m`** — la longitud a la que `σ_R²` llega a 1. Para
  `C_n^2 = 1e-14` a 1550 nm son **2 413 m**. Cien veces menos turbulencia solo
  compra un factor `100^(6/11) = 12.3`, no cien: el mismo exponente que hace
  crecer la escintilación deprisa con la distancia hace crecer la distancia
  utilizable despacio con la calidad del sitio. Es el límite de lo que este
  proyecto puede **citar**, no de lo que un enlace puede hacer: con
  `ScintillationRegime.MODERATE_TO_STRONG` ([ADR 0022](0022-the-strong-regime.md))
  se sigue más allá, sobre un heurístico en vez de sobre una recomendación.
- **`equivalent_bench_cn2_m23`** — el `C_n^2` que un banco necesita para igualar
  la varianza de Rytov de un camino largo. **8.87e-10** para que 2 m igualen 1 km
  de aire «moderado». Plegar el camino es la única palanca barata que hay: 10 m
  en vez de 2 necesitan **19.1 veces menos**. Y es condición **necesaria y no
  suficiente** — ver el hueco 20.

---

## Alternativas descartadas

- **Llamar a las funciones inclinadas con `θ` pequeño.** Medido arriba: 2.1e4
  veces la varianza.
- **La Ec. (7) de P.1622 con la altura de escala del perfil.** A elevación cero
  su `sin θ` anula el promediado entero, y su `z0` es la altura de la corriente
  en chorro, no una distancia del camino.
- **Onda plana por defecto.** Sería una elección de un factor 2.46 hecha en
  silencio por quien no la pensó.
- **Implementar la onda gaussiana.** Las fórmulas están en Andrews & Phillips,
  que no se pudo abrir (hueco 1). Sin fuente abierta, un hueco declarado.

---

## Consecuencias

### Lo que cierra

- Dar longitud, `C_n^2` y diámetros y obtener presupuesto, QBER y clave de un
  banco y de un enlace horizontal. La receta, en cuatro llamadas, es
  `tests/channel/test_horizontal.py::ge1_key`.
- **Desde el 2026-09-17 esto ya no es solo una biblioteca**: el
  [ADR 0024](0024-the-horizontal-scenario.md) convierte el camino horizontal en
  un escenario de primera clase (`link: horizontal`), con hash, procedencia,
  exportación y barridos, y las tablas de este ADR las reproduce `run()` a través
  de `engine/sweep.py`.
- Dos defectos del camino compartido que el horizontal destapó (ver
  `notes/LAST_CHANGES.md` §35): `combined_fade_db` devolvía números falsos con
  `γ` grande, y `equivalent_beam_radius_m` desbordaba con lentes mucho más anchas
  que el haz.

### Lo que no cierra

- **Onda gaussiana** (hueco 18). Cerca del rango de Rayleigh ni la plana ni la
  esférica es correcta, y a 5 km la elección vale 21.7 contra 15.1 dB de
  desvanecimiento **con el modelo débil** — 8.41 contra 9.94 dB con el saturado,
  que es la cifra que hay que citar. Ver abajo.
- **Retrorreflector** (hueco 19). Ida y vuelta por el mismo aire, correlacionadas;
  no es un camino de longitud `2L`. **Decidido el 2026-09-17** en el
  [ADR 0025](0025-two-terminals-one-way.md): GE-1 se monta con **dos terminales y
  un solo sentido**, que es la única de las dos arquitecturas que este proyecto
  puede dimensionar con las fuentes que tiene. El hueco sigue abierto.
  **Investigado el 2026-09-15**,
  con el signo ya decidido: en geometría monoestática el doble paso **empeora**
  la escintilación, medido a 1.1 km por Mahon et al. (*Appl. Opt.* 51:6147), y la
  teoría es Andrews otra vez. **Consecuencia:** un GE-1 de un solo sentido con
  dos terminales es modelable hoy y uno con retrorreflector no lo es.
- **Régimen fuerte.** ~~Hasta que exista la etapa 1.2~~ **Cerrado el 2026-09-15**
  por el [ADR 0022](0022-the-strong-regime.md), con el modelo compartido entre la
  bajada y este camino. Con `C_n^2 = 1e-14` la varianza de Rytov sigue llegando a
  1 a **2 413 m**, y más allá `ScintillationRegime.WEAK` avisa y
  `MODERATE_TO_STRONG` satura. Lo que ese ADR mide y este no podía: a 5 km, los
  **6.67 dB** que la sección siguiente atribuye a la elección de onda son
  **1.53 dB** con el modelo saturado, y con el signo invertido — la mayor parte
  de ese número era el modelo débil evaluado cuatro veces más allá de su límite.
- **Emuladores.** `C_n^2` significa aquí turbulencia de Kolmogorov; una pantalla
  de fase en un SLM hay que caracterizarla en esos términos antes de pasarla.
  Para que dos metros de banco igualen un kilómetro moderado hace falta
  `C_n^2 = 8.9e-10`.

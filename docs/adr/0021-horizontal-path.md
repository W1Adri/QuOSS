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

### Un ejemplo con números

Enlace GE-1 de 1 km, `C_n^2 = 1e-14` (la columna «moderada» de P.1814), 1550 nm,
transmisor de 2.5 cm, 5 µrad de jitter, 0.2 dB/km, receptor Ntanos et al.,
BB84 decoy asintótico al 1 % de outage:

| Lente | Geométrico | Escintilación | Clave |
|---|---|---|---|
| 2.5 cm | 7.78 dB | 3.80 dB | 56.8 kbit/s |
| 10 cm | 0.24 dB | 1.12 dB | 636 kbit/s |

Un factor **11.2** de clave por pasar de 2.5 a 10 cm. El QBER apenas se mueve
(1.01 % contra un suelo de 1 % de desalineamiento), así que para GE-1 la palanca
es la pérdida, no la tasa de error.

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
- Dos defectos del camino compartido que el horizontal destapó (ver
  `notes/LAST_CHANGES.md` §35): `combined_fade_db` devolvía números falsos con
  `γ` grande, y `equivalent_beam_radius_m` desbordaba con lentes mucho más anchas
  que el haz.

### Lo que no cierra

- **Onda gaussiana** (hueco 18). Cerca del rango de Rayleigh ni la plana ni la
  esférica es correcta, y a 5 km la elección vale 21.7 contra 15.1 dB de
  desvanecimiento.
- **Retrorreflector** (hueco 19). Ida y vuelta por el mismo aire, correlacionadas;
  no es un camino de longitud `2L`.
- **Régimen fuerte.** Con `C_n^2 = 1e-14` la varianza de Rytov llega a 1 a
  **2.41 km**; más allá todo lleva aviso hasta que exista la etapa 1.2.
- **Emuladores.** `C_n^2` significa aquí turbulencia de Kolmogorov; una pantalla
  de fase en un SLM hay que caracterizarla en esos términos antes de pasarla.
  Para que dos metros de banco igualen un kilómetro moderado hace falta
  `C_n^2 = 8.9e-10`.

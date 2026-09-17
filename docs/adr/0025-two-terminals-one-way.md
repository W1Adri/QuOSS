# ADR 0025 — GE-1: dos terminales y un solo sentido, no un retrorreflector

- **Estado:** aceptada
- **Fecha:** 2026-09-17
- **Etapa:** 4 (`scenario/`), decisión de arquitectura del experimento GE-1.
- **Afecta a:** `scenarios/ge1_1km.yaml`, `scenario/defaults.ge1_two_terminals`,
  y a lo que este proyecto puede afirmar sobre el primer enlace de tierra.
- **Extiende** al [ADR 0021](0021-horizontal-path.md) (hueco 19) y al
  [ADR 0009](0009-citation-policy.md) (huecos 1 y 19).
- **Fuentes:** dos artículos **leídos solo en resumen**, y eso está dicho en cada
  afirmación que descansa en ellos.

---

## Contexto

### Las dos arquitecturas, para quien llegue nuevo

GE-1 es un enlace óptico horizontal de un kilómetro entre dos puntos del suelo,
por el que se quiere pasar QKD. Hay dos formas de montarlo:

1. **Dos terminales, un solo sentido.** Un emisor completo en un extremo y un
   receptor completo en el otro. La luz cruza el aire una vez.
2. **Un terminal y un retrorreflector.** Todo el equipo caro —fuente, detector,
   electrónica— en un extremo; en el otro, un **cubo de esquina**, que es un
   espejo de tres caras perpendiculares con la propiedad de devolver cualquier
   rayo exactamente por donde vino. La luz cruza el aire **dos veces**, ida y
   vuelta, y el montaje es *monoestático*: emisor y receptor están juntos.

La segunda es mucho más barata y mucho más fácil de alinear: no hay que llevar
electrónica de temporización a un tejado ni sincronizar dos relojes. Es la que
uno propone primero.

### Por qué no basta con «modelarlo como un camino de longitud 2L»

Es la tentación obvia y es exactamente el modo de fallo que este proyecto existe
para rechazar: produce un número plausible.

En un camino de ida y vuelta la luz atraviesa **el mismo aire**, con las mismas
burbujas de turbulencia, dos veces y con muy poco tiempo entre medias (a 1 km, el
viaje de vuelta empieza 3.3 µs después de que la ida haya pasado por el mismo
punto, y una celda de turbulencia tarda milisegundos en cambiar). Las dos
travesías **no son independientes**: están correlacionadas, y en geometría
monoestática lo están de la peor manera posible.

Un camino de longitud `2L` supone lo contrario —dos tramos de aire distintos, con
varianzas que se suman— y por tanto subestima la fluctuación. Cuánto, no lo sabe
este proyecto, y ahí está el problema.

---

## Decisión

**GE-1 se monta con dos terminales y un solo sentido.** `scenarios/ge1_1km.yaml`
describe eso y no otra cosa, y el fichero dice por qué en su cabecera.

La razón no es que el retrorreflector sea peor: es que **este proyecto no puede
dimensionarlo con las fuentes que tiene**, y una arquitectura que se puede
dimensionar antes de comprarla vale más que una que no, incluso si la segunda
fuera mejor.

### El signo del efecto está decidido, y es el malo

En geometría monoestática la escintilación de vuelta está **realzada**, no
promediada. El fenómeno tiene nombre —*enhanced backscatter*— y la razón física
es que la ida y la vuelta recorren trayectorias correlacionadas, así que sus
desvanecimientos **se suman en fase** en vez de cancelarse parcialmente.

Medido, sobre un enlace de la escala exacta de GE-1:

> **Mahon, Moore, Ferraro, Rabinovich y Suite, *Applied Optics* 51(25):6147
> (2012)** midieron un enlace **retrorreflectado horizontal de 1.1 km** durante
> cuatro días: «the scintillation measured over close-to-ground retro-reflector
> links can be substantially **enhanced** due to the correlations experienced by
> both the direct and reflected echo beams», con varianzas de flujo de
> irradiancia **saturando en ~10** durante el día.

**Leído solo en resumen.** Es la etiqueta que lleva esta cita y es la que decide
qué se puede afirmar con ella: **el signo, sí; la magnitud, no**. «Saturando en
~10» es una cifra del resumen sobre *su* enlace, *su* óptica y *su* sitio, y
trasladarla a GE-1 sería exactamente la clase de préstamo de número que el ADR
0009 prohíbe. El título del artículo no se transcribe aquí porque no se tiene la
portada delante: lo que identifica la fuente sin riesgo son los autores, la
revista, el volumen, la página y el año, que son los que ya están en el ADR 0009
(hueco 19).

### Y la teoría es la misma fuente que ya no se pudo abrir

La formulación teórica de la escintilación de doble paso correlacionada es
**Andrews, Phillips y Miller, *Applied Optics* 36(3):698 (1997)**, también leída
solo en resumen. Es decir: el hueco 19 del ADR 0021 no es «nadie lo ha
estudiado», es **«lo ha estudiado la misma fuente que el hueco 1 dice que no se
puede abrir»**, que es un hueco de otra clase y merece decirse así.

Decirlo importa porque cambia lo que habría que hacer para cerrarlo: no hay que
buscar literatura, hay que conseguir acceso a Andrews & Phillips o implementar y
**verificar** la teoría desde cero, que es un proyecto y no una tarde.

### Lo que sí se puede dimensionar, con números

La arquitectura de dos terminales y un sentido es modelable hoy, y está medida.
Transmisor de 2.5 cm, lente de 10 cm, `C_n^2 = 1e-14`, 1550 nm, 5 µrad de
jitter, receptor y protocolo de Ntanos et al., noche de estudio, y las dos ondas
como intervalo (el hueco 18):

| `L` | `L/z_R` | `σ_R²` | clave asintótica plana | esférica |
|---|---|---|---|---|
| 200 m | 0.63 | 0.010 | 896 kbit/s | 888 kbit/s |
| 500 m | 1.58 | 0.056 | 825 | 798 |
| **1 km** | **3.16** | **0.199** | **636** | **590** |
| 2 km | 6.32 | 0.709 | 208 | 182 |
| 2.41 km | 7.62 | 1.000 | 122 | 107 |
| 5 km | 15.79 | 3.802 | 4.0 | 4.4 |

**Por qué un kilómetro y no otra cosa.** Por debajo de ~500 m el enlace está
dentro o cerca del rango de Rayleigh del transmisor (316.7 m), donde **ninguna**
de las dos ondas cerradas describe el haz: el intervalo se estrecha al 1 %, pero
por la razón equivocada, y leerlo como «bien determinado» es la conclusión
opuesta a la correcta. Por encima de **2413 m** la teoría débil deja de ser
citable (`weak_theory_path_limit_m` con este `C_n^2` a 1550 nm). Un kilómetro
está en el medio limpio.

**Y la cifra que el dimensionado añade en esta ronda, que no estaba antes:** con
la cota finite-key aplicada a una sesión de 60 s, el enlace de 1 km certifica
**253 kbit/s** (15.2 Mbit) contra los 590 asintóticos, y **a 5 km certifica
exactamente cero** mientras el asintótico sigue reclamando 4.4 kbit/s. Es el
acantilado del [ADR 0011](0011-the-block-is-the-pass.md) aparecido en un enlace
de tierra, y es justo el régimen en que un dimensionado asintótico diría que el
enlace funciona.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Retrorreflector, modelado como un camino de `2L`** | Supone dos travesías independientes. Son correlacionadas, y en monoestático el efecto **realza** la escintilación en vez de promediarla: el modelo erraría en la dirección optimista, y no se sabe por cuánto |
| **Retrorreflector, con el factor de realce de Mahon et al.** | Sus varianzas de flujo saturando en ~10 son de su enlace, su óptica y su clima, leídas en el resumen. Trasladarlas sería un número prestado presentado como propio |
| **Retrorreflector, implementando Andrews, Phillips y Miller (1997)** | La fuente es la del hueco 1: no se pudo abrir. Implementar de memoria una teoría que no se ha leído es la peor versión de todas |
| **Montar el retrorreflector y medir, sin modelo** | Legítimo como experimento y no como dimensionado: la pregunta que GE-1 tiene que contestar **antes** de comprar es qué apertura y qué distancia hacen falta, y sin modelo no hay respuesta |
| **Dos terminales a 5 km, para tener margen** | Certifica cero. Y además está a 2.1 veces el límite de la teoría débil, así que ni siquiera el número asintótico es citable ahí |
| **Dos terminales a 200 m, para estar seguros** | El intervalo entre las dos ondas se estrecha al 1 %, y eso invita a citar un número donde solo hay un bracket que no aplica: dentro del rango de Rayleigh ninguna de las dos idealizaciones describe el haz |

---

## Consecuencias

### Lo que cierra

- **GE-1 tiene una arquitectura, un fichero y un dimensionado**, y la elección
  está defendida con la fuente que la sostiene y con la etiqueta de cómo se
  leyó.
- **El hueco 19 tiene forma**: no es una laguna bibliográfica, es la misma puerta
  cerrada del hueco 1. Eso dice qué haría falta para abrirlo.

### Lo que cuesta

- **Dos terminales completos** en vez de uno y un cubo de esquina: más
  electrónica, dos relojes que sincronizar y una alineación que mantener en los
  dos extremos. Es un coste real y este ADR no pretende que no lo sea.

### Lo que no cierra

- **El retrorreflector sigue sin modelo** (hueco 19), con el signo decidido y la
  magnitud no.
- **La onda gaussiana** (hueco 18) sigue siendo la razón de que todo lo de arriba
  sea un intervalo y no un número.
- **La turbulencia de un sitio concreto.** `C_n^2 = 1e-14` es la columna
  «moderada» de la P.1814, no una medida del tejado donde GE-1 vaya a montarse.
  Un anemómetro y un escintilómetro durante una temporada cambiarían estas
  cifras más que cualquier decisión de este ADR.

---

## Referencias

- Mahon, Moore, Ferraro, Rabinovich y Suite, *Applied Optics* **51**(25):6147
  (2012). **Leído solo en resumen**: sostiene el signo del efecto y no su
  magnitud. Sin título transcrito, por la razón de arriba.
- Andrews, Phillips y Miller, *Applied Optics* **36**(3):698 (1997). **Leído
  solo en resumen**; es la teoría del doble paso, y es la misma fuente del hueco
  1 del [ADR 0009](0009-citation-policy.md), cuya versión de registro es de pago.
- [ADR 0021](0021-horizontal-path.md) — la física del camino horizontal y el
  hueco 19.
- [ADR 0024](0024-the-horizontal-scenario.md) — el escenario que describe este
  experimento, y por qué su bloque finite-key es una declaración.
- [ADR 0011](0011-the-block-is-the-pass.md) — el acantilado que el dimensionado a
  5 km encuentra.

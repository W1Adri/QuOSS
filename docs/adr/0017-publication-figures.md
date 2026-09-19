# ADR 0017 — Las figuras de publicación: tres convenciones que impiden leer lo contrario de lo correcto

- **Estado:** aceptada
- **Fecha:** 2026-09-19
- **Etapa:** 7 (`viz/`)
- **Afecta a:** `viz/plots.py` (todas las `plot_*`, y en particular
  `plot_elevation_and_rate` y `plot_horizontal_key_against_distance`),
  `viz/style.py`, `viz/figures.py`.
- **Número reservado desde el 2026-09-14.** `src/quoss/viz/plots.py` citaba este
  fichero por su nombre exacto antes de que existiera, y `notes/ROADMAP.md` lo
  tenía reservado para esta etapa. Quien escribe la etapa usa **este** número y
  no el siguiente libre, que es la regla de numeración del roadmap.
- **Extiende** al [ADR 0011](0011-the-block-is-the-pass.md) (finita contra
  asintótica: lo que la figura tiene que distinguir es lo que ese ADR decidió),
  al [ADR 0021](0021-horizontal-path.md) y al
  [ADR 0024](0024-the-horizontal-scenario.md) (la banda plana-a-esférica sale de
  ahí), y al [ADR 0026](0026-the-language-ladder.md) («Alternativas
  descartadas»: la única ventaja real de MATLAB es tipográfica y la recupera
  `viz/style.py`).

---

## Contexto

### Qué es una figura, en este proyecto, y por qué merece un ADR

Una figura es **el último sitio donde un número se puede malinterpretar**. Todo
lo demás que este repositorio hace —tolerancias derivadas, `DomainError` en vez
de degradación silenciosa, huecos declarados en vez de rellenados— protege el
número mientras se calcula. Cuando ese número se dibuja, deja de estar protegido
por nada de eso y pasa a depender de **convenciones de dibujo**, que no tienen
tests y que el lector interpreta sin darse cuenta de que está interpretando.

El modo de fallo que este ADR persigue no es «la figura está mal». Es peor y es
el mismo que el proyecto persigue en los números: **una figura correcta que se
lee al revés**. Un lector mira una banda estrecha y concluye «esto está bien
determinado»; mira dos curvas que se cruzan y concluye «aquí la tasa supera a la
elevación»; mira una barra de altura cero y no la ve. En los tres casos el dato
subyacente es exacto y la conclusión es la contraria de la correcta, y no hay
ningún test que pueda fallar, porque no hay nada mal calculado.

De ahí que lo que se decide aquí sean **convenciones**, no estética: cada una
existe porque su alternativa natural produce una lectura invertida concreta, y
cada una se escribe con el caso que la produce.

### Qué había antes de este fichero

`viz/plots.py` existía desde la etapa 7 parcial, con las cuatro reglas de su
docstring ya aplicadas (nada de física en la figura, finita ≠ asintótica,
degradaciones visibles, nada de estado global) y **sin dueño de la
justificación**: el módulo citaba `docs/adr/0017-publication-figures.md` por
nombre y el fichero no existía, que es la [inconsistencia #11](../../notes/INCONSISTENCIAS.md)
cerrada el 2026-09-14 anotando la cita como pendiente. Este ADR la cierra de
verdad.

---

## Decisión

### 1. Elevación y tasa van en **dos paneles**, nunca en un eje `twinx`

**Qué es un `twinx`.** El dibujo obvio para dos magnitudes sobre el mismo tiempo
es un solo panel con un segundo eje vertical a la derecha: la elevación en
grados (0 a 90) a la izquierda, la tasa secreta en bit/s (0 a miles) a la
derecha. Es una línea de `matplotlib` y es lo que hace casi todo el mundo.

**Por qué no.** Con dos escalas en un panel, **dónde se cruzan las dos curvas lo
decide cómo estén rangeados los dos ejes**, no los datos. Mover el límite
superior del eje derecho de 3000 a 5000 bit/s desplaza el cruce sin que ningún
número cambie. La figura, entonces, muestra una relación que es una propiedad de
los límites de los ejes, y un lector no tiene forma de saber que lo es: los
cruces parecen datos.

**Qué se hace en su lugar.** Dos paneles apilados que **comparten el eje de
tiempo**. Se conserva lo único que la figura tiene que comunicar —la alineación
temporal, porque la tasa solo existe dentro de las ventanas sombreadas de
pase— y desaparece el artefacto. El precio es vertical: la figura es más alta.
Es un precio de maquetación contra una lectura inventada.

**El caso que lo demuestra.** En el día de referencia hay cuatro pases. Con
`twinx` y el eje derecho autoescalado al pase más productivo (1 548 341 bits
asintóticos), los dos pases que certifican **cero** quedan pegados al eje
inferior y visualmente indistinguibles de la parte del día en que el satélite
está bajo el horizonte. Con dos paneles, la ventana de pase sigue sombreada en
los dos y el pase muerto se ve como lo que es: una ventana con geometría y sin
clave.

### 2. La banda plana-a-esférica **no es una barra de error**, y se dice en la figura

**De qué banda se trata.** En un camino horizontal la escintilación tiene dos
formas cerradas y este proyecto no puede defender ninguna como *la* respuesta:
un haz colimado dentro de su rango de Rayleigh es casi una **onda plana**, uno
mucho más allá parece una fuente puntual y es casi una **onda esférica**, y un
haz real no es ninguna de las dos (la onda de haz gaussiano, hueco 18 del
[ADR 0009](0009-citation-policy.md), cuyas fórmulas están en una fuente que no
se pudo abrir). La salida honesta es un **intervalo**: las dos formas cerradas,
rellenas entre sí, que es lo que dibuja `plot_horizontal_key_against_distance`.

**Por qué esto es una convención peligrosa y no un detalle.** Una región
sombreada alrededor de una curva **significa incertidumbre estadística** en
prácticamente toda la literatura: un intervalo de confianza, un percentil, un
±1σ. Esta no lo es. No hay distribución detrás y no hay probabilidad asociada:
son **dos modelos, los dos calculados exactamente, acotando un tercero que no
está implementado**. Leerla como una barra de error lleva a dos conclusiones
falsas a la vez —que el valor central es el más probable, y que los bordes son
improbables— cuando lo cierto es que **el valor real puede estar en cualquier
punto del intervalo y la función de dentro no se conoce**.

**Y no está ordenada igual en todas partes**, que es lo que impide tratarla como
«centro ± anchura». Medido (§40, sesión de 60 s, asintótico):

| lente | plana | esférica | quién es el borde pesimista |
|---|---|---|---|
| 2.5 cm | 56.82 kbit/s | 70.15 kbit/s | **la plana** |
| 10 cm | 636.20 kbit/s | 589.92 kbit/s | **la esférica** |

Por eso la firma toma **las dos series** y no un borde y una anchura: una API de
«centro y ±» impondría un orden que los datos no tienen.

**Qué se hace.** La banda se dibuja, el docstring lo dice, y la etiqueta de la
leyenda no dice «incertidumbre» ni lleva un signo ±.

### 3. La región de Rayleigh se sombrea, porque ahí la banda **se estrecha por la razón equivocada**

Esta es la sutil, y la razón de que `plot_horizontal_key_against_distance` exista
en vez de ser una llamada a `plot_sweep`.

**Qué es el rango de Rayleigh.** Es la distancia a la que un haz colimado empieza
a ensancharse apreciablemente por difracción: dentro de él el haz es casi
paralelo, fuera se abre como un cono. Para un transmisor de 2.5 cm a 1550 nm son
**316.7 m**.

**Qué pasa con la banda ahí dentro.** Se estrecha mucho: a 200 m las dos formas
cerradas coinciden dentro del **1 %**. La lectura natural de una banda estrecha
es «aquí el resultado está bien determinado». **Es la conclusión contraria a la
correcta.** Las dos formas no coinciden porque alguna describa el haz —ninguna
lo hace, y dentro del rango de Rayleigh la de onda esférica es la que peor lo
hace— sino porque a esa distancia **domina el término geométrico** y la
diferencia de escintilación no llega a mover la clave. La banda mide lo que la
clave hereda de la diferencia entre los modelos, no cuánto se parecen los
modelos; cuando ese canal de transmisión se estrecha, la banda se estrecha
aunque los modelos discrepen más que nunca.

**Qué se hace.** Se sombrea esa región con su propia etiqueta, distinta de la del
límite de teoría débil, para que «estrecho» no se lea como «determinado».

### 4. Las dos marcas se pasan, no se adivinan

`weak_limit_m` (2413 m) y `rayleigh_range_m` (316.7 m) son argumentos opcionales
y **no se deducen de las filas del barrido**. Los dos son propiedades del aire y
del transmisor, y ninguno está en los datos que la función recibe. Adivinarlos
—por ejemplo, poniendo la marca donde la banda cambia de anchura— dibujaría una
marca que parece medida y es inventada, que es la misma familia de defecto.
`None` deja la marca fuera; no hay valor por defecto.

### 5. Una distancia, o un pase, que certifica cero **se dibuja**

En eje logarítmico un cero no tiene sitio, y en eje lineal una barra de altura
cero es indistinguible de una barra ausente. Los dos casos se resuelven igual:
se dibuja una marca visible —una `×` con un «0» encima en la figura horizontal,
un «0» en la base de la barra en la de pases— con su propio `gid`.

**Por qué es la marca más importante de la figura y no una nota al pie.** Un
punto que certifica cero mientras el cálculo asintótico sigue reclamando tasa
positiva es el acantilado del ADR 0011, y es exactamente el régimen en el que un
dimensionado asintótico diría que el enlace funciona. Medido: a 5 km GE-1
certifica **0 bits** en 60 s mientras el asintótico reclama **267 678**
(4.46 kbit/s). En el día de referencia, **dos de los cuatro pases** certifican
cero donde el asintótico reclama 320 y 199 kbit. Si la figura los pierde, pierde
su hallazgo.

---

## Alternativas descartadas

**Un eje `twinx` con los límites fijados a mano y documentados.** Arregla la
reproducibilidad y no el problema: el cruce sigue siendo una propiedad de dos
números elegidos, y que estén documentados no impide que el lector lea el cruce
como un dato. Un artefacto anotado sigue siendo un artefacto.

**Dibujar solo una de las dos ondas, la «más aplicable» en cada distancia.** Es
lo que un lector esperaría y es una elección de modelo hecha por la rutina de
dibujo. Además tendría una discontinuidad en el cruce, que es el peor sitio
posible: justo donde la elección importa, la curva daría un salto que parecería
física.

**No dibujar la región más allá del límite de teoría débil.** Se rechaza por la
misma razón por la que el módulo avisa en vez de refusar: lo que las curvas dicen
ahí es lo que dice el modelo débil, y esconderlo deja al lector sin manera de ver
cuánto se está extrapolando. Se dibuja y se sombrea.

**Una banda de Monte Carlo diaria.** No se puede construir:
`MonteCarloResults` guarda cuantiles **por pase**, y los cuantiles de un día son
cuantiles de la suma por realización, que no se reconstruyen desde los cuantiles
por pase. Medido en el ensemble de referencia: el P5 del día son 735 329 bits y
la suma de los P5 de los pases son 724 553. Sumarlos dibujaría una banda que
ningún ensemble produjo.

---

## Consecuencias

- **`viz/` no calcula física, y eso es asertable.** La única aritmética
  permitida es de presentación (radianes a grados por `core.units.rad_to_deg`,
  segundos a horas, `90° − elevación` como radio, JDN a fecha por
  `orbits.frames.jd_to_calendar`). Lo vigila la guarda de AST del repo, que
  prohíbe `np.rad2deg` fuera de `core/units.py`.
- **Las convenciones 2 y 3 viven en el docstring *y* aquí, y no es duplicación
  de la justificación.** El docstring dice **qué** convención aplica la función,
  porque quien la llama tiene que saberlo sin salir del editor; este ADR dice
  **por qué** y con qué cifras. La regla del proyecto es que el porqué esté en
  un sitio, y está aquí.
- **Quien añada una `plot_*` nueva hereda la pregunta**, no la respuesta: si su
  convención de dibujo admite una lectura invertida, esa lectura se escribe y se
  neutraliza, o se añade a este ADR.
- **La cita de `viz/plots.py` deja de ser una promesa.** Decía «0017 está
  reservado y no escrito todavía»; ahora dice qué sección leer.

---

## Referencias

- `src/quoss/viz/plots.py` — las cuatro reglas del módulo y las tres
  convenciones de arriba, en el sitio donde se aplican.
- `src/quoss/viz/style.py` — la hoja de estilo: tamaños IEEE, paleta segura para
  daltonismo, y el vocabulario visual (sólido = finita, tramado = asintótica).
- [ADR 0011](0011-the-block-is-the-pass.md) — por qué finita y asintótica no
  pueden parecerse, y el acantilado que produce los ceros.
- [ADR 0021](0021-horizontal-path.md), [ADR 0024](0024-the-horizontal-scenario.md)
  — de dónde sale el intervalo plana-a-esférica y por qué no está ordenado.
- [ADR 0009](0009-citation-policy.md) — hueco 18, la onda de haz gaussiano que
  la banda acota y que no está implementada.
- `notes/LAST_CHANGES.md` §40 — las cifras de la tabla plana/esférica y el cero
  de los 5 km, medidas.

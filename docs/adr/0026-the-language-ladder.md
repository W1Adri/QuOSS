# ADR 0026 — La escalera de lenguajes: cuándo se deja de escribir Python, y qué hay que traer para hacerlo

- **Estado:** aceptada
- **Fecha:** 2026-09-19
- **Etapa:** gobierna la **2.4** (`kernels/`), hoy sin abrir, y cualquier
  propuesta futura de reescribir un trozo de física en otro lenguaje.
- **Afecta a:** `kernels/base.py`, `kernels/numpy_backend.py`,
  `kernels/numba_backend.py` (ninguno existe todavía), el extra `accel` de
  `pyproject.toml:53`, y el bucle sobre satélites de
  `orbits/propagator.py:535`.
- **Procedencia:** esta decisión se tomó el 2026-07-31 en la *Guía de
  reimplementación v3* §2 y ha gobernado el proyecto desde entonces sin estar en
  `docs/adr/`. `LAST_CHANGES.md` §41 lo señaló como hallazgo y no lo cerró,
  porque numerar un ADR es una decisión de quien lo mantiene y no un efecto
  secundario de reordenar notas. Esto lo cierra. El texto original está en
  [`notes/archive/GUIA_REIMPLEMENTACION-v3.md`](../../notes/archive/GUIA_REIMPLEMENTACION-v3.md).

---

## Contexto

### Qué es un «kernel», y por qué alguien querría cambiar de lenguaje

Un **kernel**, en este sentido, es un trozo pequeño de cálculo que se ejecuta
muchísimas veces y donde se va casi todo el tiempo de un programa: el cuerpo de
un bucle, la función que un integrador llama en cada paso, la operación que se
repite por cada muestra de la rejilla temporal. El resto del programa —leer un
YAML, decidir qué etapa toca, escribir un CSV— se ejecuta una vez y su coste es
irrelevante aunque esté escrito de la forma más lenta imaginable.

La tentación, cuando un programa va lento, es reescribirlo en un lenguaje
rápido. Es casi siempre la respuesta equivocada, y conviene ver por qué con
números antes que con adjetivos. Python ejecuta del orden de **10⁷ operaciones
por segundo** cuando cada operación pasa por el intérprete, y del orden de
**10⁹** cuando la operación la hace NumPy sobre un array entero, porque entonces
el bucle está escrito en C dentro de NumPy y el intérprete solo lo arranca una
vez. **Son dos órdenes de magnitud, y los da reescribir el mismo Python de otra
forma, no cambiar de lenguaje.** Cambiar de lenguaje da, sobre lo segundo, un
factor que rara vez pasa de 5.

Los términos que aparecen abajo, definidos la primera vez que se usan:

- **Vectorizar** es escribir la operación sobre el array entero (`a + b` con
  `a` y `b` de un millón de elementos) en vez de sobre un elemento dentro de un
  bucle `for` de Python. El bucle sigue existiendo; lo corre C.
- **Numba** es una biblioteca que lee una función de Python y la compila a
  código máquina la primera vez que se llama, un proceso llamado **JIT**
  (*just-in-time*, «justo a tiempo»). Se activa poniendo un decorador
  `@njit` encima de la función. No hay sistema de compilación, ni fichero
  aparte, ni paso de build: es la misma función en el mismo fichero.
- **PyO3** y **maturin** son, respectivamente, la biblioteca que permite llamar
  a Rust desde Python y la herramienta que empaqueta el resultado en un
  **wheel**, que es el formato de paquete instalable de Python (`pip install`
  descarga wheels).
- **Golden test** aquí significa: un test que compara la salida del kernel
  rápido contra la de una implementación de referencia en NumPy puro, sobre
  entradas fijadas. `tests/golden/README.md` es su dueño.

### Por qué esto necesita una decisión escrita y no un criterio

Porque el coste de equivocarse es asimétrico y va en una dirección sola. Un
kernel acelerado no se puede leer igual que el Python que sustituye: un revisor
que quiera comprobar la física tiene que saber Rust, o confiar. Y no se puede
quitar: en cuanto un resultado publicado sale de él, retirarlo obliga a
re-verificar. El error contrario —dejar el Python un mes de más— cuesta
exactamente el tiempo de máquina que se habría ahorrado, que es lo más barato
que tiene este proyecto.

Y porque el proyecto ya vio el fallo característico. La física de SimulCTTC era
**escalar con bucles Python**, con `samples ≤ 900` puesto como límite de diseño
para que el programa terminara. El diagnóstico está en
[`notes/GUIA_REIMPLEMENTACION.md`](../../notes/GUIA_REIMPLEMENTACION.md) §1. Ese
límite no se quitó cambiando de lenguaje: se quitó vectorizando, que es el
escalón 1 de abajo, y por eso QuOSS corre hoy rejillas de 86 401 muestras sin
que nadie haya escrito una línea que no sea Python.

---

## Decisión

**Python es el lenguaje de la física y de la orquestación, y se queda.** El
valor de este proyecto es corrección física e iteración rápida; el ecosistema
que necesita está en Python (scipy, sgp4, matplotlib, pydantic) y un revisor
puede leerlo sin instalar nada.

**Los cuatro escalones, en orden, y no se salta ninguno sin datos de profiler:**

| # | Escalón | Qué cuesta empezarlo | Cuándo es el correcto |
|---|---|---|---|
| 1 | **NumPy vectorizado** | nada: es reescribir el mismo fichero | siempre primero. Cubre la mayor parte del problema, porque el cuello casi nunca es Python sino física escalar |
| 2 | **Numba** (`@njit`) | un decorador; cero sistema de build | un bucle **irreducible**: uno cuyo paso depende del anterior, que por eso no se puede vectorizar |
| 3 | **Rust** (PyO3 + maturin) | un crate, un job de wheels por plataforma | un kernel realmente caliente, con contrato numérico **estable**, que Numba no cubre |
| 4 | **C++** | lo de Rust más la gestión de memoria | solo si hay que reutilizar una biblioteca C++ que ya existe |

**Rust antes que C++**, y la razón no es de gusto: `maturin` produce wheels
multiplataforma de forma reproducible, el compilador garantiza la seguridad de
memoria, y `rayon` hace el paralelismo de datos trivial. C++ no aporta nada de
eso sobre Rust y sí añade fricción de build; su única ventaja real es poder
enlazar contra una biblioteca C++ existente, y por eso esa es literalmente su
condición de entrada.

### La regla que gobierna los cuatro, que es la parte que importa

Se cambia de escalón **solo** cuando se cumplen las tres a la vez:

1. **Hay una medición de profiler** que nombra la función y dice qué fracción
   del tiempo total se va en ella. No «va lento»: un porcentaje.
2. **El kernel tiene un contrato numérico estable** — entradas, salidas y
   tolerancia fijados. Un kernel que todavía cambia de forma se acelera dos
   veces.
3. **Queda la implementación de referencia en NumPy puro**, y un golden test
   demuestra que las dos coinciden dentro de una tolerancia **derivada**.

*Un kernel acelerado sin su referencia es deuda, no optimización.* La referencia
no es una cortesía: es lo único que permite contestar «¿el número nuevo está mal
o el rápido está mal?» sin releer el ensamblador.

---

## Lo que esto mide hoy, y lo que la medición dice

Todo lo de abajo es de este árbol, en esta máquina (Python 3.13.14, NumPy 2.4.6,
SciPy 1.18.0, 20 núcleos), y se reproduce con
`quoss.engine.profiling`, que ya mete los tiempos por etapa dentro del propio
resultado.

### El día de referencia completo tarda 121 ms

`run(load_scenario("scenarios/reference_castelldefels.yaml"))`, un día entero de
Castelldefels con su cadena completa —órbita, geometría, pases, canal, QKD,
series—:

| Etapa | ms | % |
|---|---|---|
| orbit | 52.4 | 43 % |
| geometry | 27.8 | 23 % |
| channel | 19.5 | 16 % |
| result | 12.9 | 11 % |
| key | 2.8 | 2 % |
| series | 2.2 | 2 % |
| passes | 1.6 | 1 % |
| **total** | **121** | |

**La conclusión operativa es que el escalón 2 no tiene caso que resolver.** El
día de referencia —la simulación que produce las figuras— tarda menos de lo que
tarda `import numpy`. Aunque Numba hiciera la etapa `orbit` instantánea, el
programa pasaría de 121 a 69 ms, y nadie ha esperado nunca esos 52 ms.

### Y donde sí duele, el problema no es la aritmética: es un bucle en serie

El caso grande que el `ROADMAP.md` manda medir antes de tocar nada es una
constelación de 60 satélites sobre un día de rejilla a 1 s (86 401 muestras):

| Método | S | Tiempo | Por satélite |
|---|---|---|---|
| `ZONAL_NUMERIC` | 1 | 0.934 s | 934 ms |
| `ZONAL_NUMERIC` | 10 | 9.306 s | 931 ms |
| `ZONAL_NUMERIC` | 60 | **55.6 s** | 927 ms |
| `TWO_BODY` | 60 | **2.9 s** | 48 ms |

**Las tres filas de `ZONAL_NUMERIC` son la misma cifra por satélite**, 0.93 s,
con menos de un 1 % de dispersión entre S = 1 y S = 60. Eso es la firma de un
bucle estrictamente en serie, y está a la vista en `propagator.py:535`:
`for index in range(n_sat)` alrededor de `propagate_zonal`, una llamada a DOP853
por satélite. `TWO_BODY`, que sí está vectorizado sobre la pila entera, hace los
60 en 2.9 s.

**Por qué esto decide algo.** La lectura ingenua de «55 segundos» es «hace falta
Numba». La lectura correcta es que el factor 19 entre las dos filas de 60 **no
mide la velocidad de la aritmética**: mide que una rama recorre los satélites de
uno en uno y la otra no. El escalón 1 no está agotado, y el trabajo que falta
—repartir ese bucle entre procesos— es de `engine/parallel.py`, no de la física,
exactamente como lo tiene clasificado el `ROADMAP.md` en la etapa 11. Saltar a
Numba aquí aceleraría la evaluación del campo zonal dentro de cada paso de
DOP853 y dejaría intacto el 100 % del serialismo.

**Lo que esto no dice.** No dice que la etapa 2.4 no vaya a hacer falta nunca;
dice que **hoy no hay ninguna medición que la pida**, que es la condición 1 de la
regla de arriba. El día que un barrido de Monte Carlo con miles de
realizaciones, o la evaluación del campo dentro de DOP853 ya paralelizado,
salgan en un profiler con un porcentaje dominante, la condición se cumple y se
abre la etapa.

---

## Decisiones aplazadas, con lo que haría falta para cerrarlas

Al estilo del [ADR 0010](0010-decoy-and-finite-key.md): lo que no está decidido
se escribe como no decidido, con su condición de cierre, en vez de resolverse
por omisión.

| Aplazada | Qué falta para cerrarla |
|---|---|
| **Qué es el primer kernel de `kernels/`.** Los dos candidatos son la evaluación del campo zonal dentro de DOP853 y el muestreo de Monte Carlo de `system/monte_carlo.py`; hoy ninguno tiene un perfil que lo señale | Un perfil del caso grande **después** de paralelizar el bucle sobre satélites. Antes de eso, cualquier perfil mide el serialismo |
| **Si `kernels/base.py` es una interfaz o un módulo de despacho.** El `ROADMAP.md` nombra los tres ficheros; la forma exacta no está decidida | El primer kernel real. Una interfaz diseñada para cero implementaciones se diseña dos veces |
| **La tolerancia del golden test Numba↔NumPy.** Tiene que ser derivada, y la derivación depende de qué operación sea (una suma en otro orden no tiene la misma cota que una `exp`) | El kernel concreto |
| **Si el extra `accel` sigue existiendo mientras no haya kernels.** Hoy `pyproject.toml:53` declara `numba>=0.60` para un backend que no existe, y CI lo instala | Es una decisión de empaquetado y de CI, no de lenguaje. Se mide y se cierra en su PR |

---

## Alternativas descartadas

**MATLAB: no.** No es libre ni redistribuible, lo que rompe a la vez el
contenedor Docker, el servicio público y la reproducibilidad por terceros: un
revisor no debería necesitar una licencia para comprobar una cifra. Su única
ventaja real sobre el stack de Python es la calidad tipográfica de las gráficas,
y eso lo replica `viz/style.py`, que ya existe.

**Cython: no, y es la que menos obvia resulta.** Cython (un dialecto de Python
que se compila a C) hace lo mismo que Numba un escalón más arriba de coste:
exige un fichero `.pyx` aparte, un paso de compilación en el build y un
compilador de C en la máquina de quien instale desde fuente. A cambio no da nada
que Numba no dé para el caso de este proyecto, que es aritmética de coma
flotante sobre arrays. Si el escalón 2 se queda corto, lo que sigue es Rust por
las razones de arriba, no Cython.

**Reescribir la física entera en un lenguaje compilado: no**, y es la
alternativa contra la que existe todo lo demás. Perdería la propiedad que hace
este repo revisable —que la física se lee— a cambio de un factor que las
mediciones de arriba dicen que nadie está esperando.

**Empaquetado como binario, WASM y el lenguaje del frontend** no están aquí:
son decisiones de **distribución**, y su dueño es el
[ADR 0027](0027-four-levels-of-distribution.md). La frontera entre los dos: 0026
decide en qué lenguaje se **escribe** el cálculo, 0027 decide en qué forma se
**entrega**.

---

## Consecuencias

### Lo que cierra

- La etapa 2.4 tiene dueño escrito. Quien la abra encuentra la regla de entrada
  (las tres condiciones) y el número que hoy dice que no toca.
- `kernels/numpy_backend.py` queda definido como **obligatorio y permanente**,
  no como un paso intermedio que se borra cuando funcione el rápido.
- La comparación «55 s contra 2.9 s» deja de ser una sorpresa esperando a
  alguien: está medida, explicada y clasificada como trabajo de
  `engine/parallel.py`.

### Lo que no cierra

- **No hay ningún test que aserte esta decisión**, y no lo puede haber: una
  regla sobre cuándo está permitido escribir un fichero no se puede comprobar
  desde el árbol que aún no lo tiene. Lo que sí queda asertable el día que
  exista un kernel es el golden test contra la referencia, que es la condición 3.
- **Los tiempos de arriba son de una máquina.** Son de orden de magnitud y de
  proporción entre etapas, no cifras portables; lo portable es la **forma** —que
  `ZONAL_NUMERIC` escala lineal en S y `TWO_BODY` no—, que es lo que sostiene la
  conclusión. La puerta de regresión de tiempos es trabajo de `benchmarks/`
  (etapa 11), con techo derivado y no elegido.

---

## Referencias

- `notes/archive/GUIA_REIMPLEMENTACION-v3.md` §2 — el texto original de la
  escalera, 2026-07-31, del que esto es la elevación a ADR sin cambio de fondo.
- `notes/GUIA_REIMPLEMENTACION.md` §1 — el diagnóstico de SimulCTTC: física
  escalar con `samples ≤ 900` por diseño, que es el caso real del escalón 1.
- [ADR 0005](0005-propagation.md) — por qué `propagate` tiene dos métodos y por
  qué el enum está incompleto a propósito.
- [ADR 0027](0027-four-levels-of-distribution.md) — la otra mitad: cómo se
  entrega lo que aquí se decide escribir en Python.
- `tests/golden/README.md` — los cuatro niveles V1–V4, y por qué un golden test
  contra la propia referencia es V4 y **no es validación**.

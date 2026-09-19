# ADR 0029 — Un expediente se genera, va commiteado, y su generador no evalúa física

**Fecha:** 2026-09-19 · **Estado:** aceptado · **Etapa:** 7 (`dossier/`, `cli/`)
· **Gobierna:** `src/quoss/dossier/`, `src/quoss/cli/dossier.py`,
`docs/experiments/*.md`

---

## Contexto: qué es un expediente y por qué no lo cubría nada de lo que ya había

Hasta hoy este proyecto producía **números**: un objeto resultado, un CSV, una
fila de `docs/validation.md`. Lo que no producía es el documento con el que
alguien decide algo — si comprar una lente de 10 cm, si prestar un banco
óptico, si una estación de montaña vale su carretera.

Un **expediente** (*dossier*) es ese documento. No es un artículo y no es un
ADR. Un ADR registra una decisión que este proyecto ya tomó; un expediente dice
lo que el modelo de este proyecto afirma sobre un experimento **que todavía no
existe**, con cada cifra llevando su unidad y la decisión que cambia.

Son tres, uno por experimento, en `docs/experiments/`:

| Documento | Desde | Qué decide |
|---|---|---|
| [`GE-1.md`](../experiments/GE-1.md) | `scenarios/ge1_1km.yaml` | la arquitectura, el presupuesto, la lente, la distancia, el bloque declarado |
| [`GE-0b.md`](../experiments/GE-0b.md) | `scenarios/ge0b_bench.yaml` | qué pregunta de GE-1 contesta el banco, y cuál no |
| [`reference-link.md`](../experiments/reference-link.md) | `scenarios/reference_castelldefels.yaml` | qué pases merece la pena programar, dónde poner la máscara, cuál de los dos enlaces de Ntanos se usa |

---

## Decisión 1 — Ninguna cifra se transcribe: se genera, y el fichero se commitea

**Qué significa.** Cada número de los tres documentos sale de una corrida que
el generador hizo cuando escribió el fichero. El fichero está commiteado, y
`tests/dossier/test_docs.py` lo vuelve a renderizar y **compara byte a byte**.

**Por qué, y no es una preferencia de estilo.** El modo de fallo contrario está
medido en este repositorio dos veces. Los «219 km» del coste de no tener
Brouwer-Lyddane vivieron en **quince sitios** durante meses, defendidos en prosa
cada vez, y eran **5.9 veces menores** que la respuesta correcta
(`notes/archive/LAST_CHANGES-13-24.md` §14). La §46 cerró la misma familia en
los docstrings. Nada lo cazó porque nada podía: **la prosa no corre**.

**Y un expediente es peor que un docstring en exactamente una cosa, que es la
que importa aquí: se lleva a una reunión.** Un docstring rancio engaña a la
siguiente persona que abre el fichero, que tiene el código delante. Un
expediente rancio engaña a una orden de compra, y su lector **no tiene
checkout, ni Python, ni motivo para tener ninguno de los dos**. Para ese lector
el fichero commiteado *es* el artefacto, y su única defensa contra que esté
caducado es que a otra persona se le ponga el build en rojo.

**El ejemplo concreto que lo hace no hipotético.** `GE-1.md` imprime la clave
certificada contra la distancia y dice que a **5 km el enlace certifica cero
bits mientras el cálculo asintótico sigue reclamando 267 678** en la misma
sesión. Si un cambio en el modelo de desvanecimiento moviera ese acantilado a
3 km y el documento siguiera diciendo 5, el documento sería **activamente peor
que no existir**: un argumento seguro de sí mismo, con fuentes y con un hash,
a favor de montar un enlace que no cierra.

**Qué exige esto del renderizado.** Que sea comparable exactamente: sin marcas
de tiempo, sin tiempos de etapa, sin el commit de git, cuatro cifras
significativas, y un hash de escenario que es función pura de las entradas. Lo
único deliberadamente volátil de la cabecera es la versión de QuOSS, y está ahí
a propósito: una release invalida los tres expedientes hasta que se regeneran,
que es el comportamiento que se quiere.

Es el mismo arreglo de tres piezas que `docs/validation.md` tiene desde la etapa
8 ([ADR 0018](0018-validation-is-a-table-not-a-badge.md)), por la misma razón.

---

## Decisión 2 — El generador puede pedirle corridas al motor y **no** puede evaluar física

**La regla.** Un constructor de expedientes puede leer campos de un resultado y
puede pedirle al motor otra corrida o un barrido. No puede importar
`quoss.channel`, `quoss.qkd`, `quoss.system` ni `quoss.orbits`.

**Por qué.** El [ADR 0028](0028-the-cli-computes-nothing.md) enuncia la regla
para la CLI —«la CLI no calcula nada»—. Un generador de informes es esa misma
capa un paso más afuera, y el fallo que produciría es **peor**: un número
calculado en la capa de presentación es un número que ningún test de la física
cubre, impreso para un lector que no puede comprobarlo.

**Lo que la regla costó, medido, porque es la forma que volverá a tener.**
Escribir `GE-1.md` pidió tres cifras que el resultado no llevaba: el factor de
promediado de apertura `A`, el rango de Rayleigh del transmisor y la longitud a
la que deja de valer la teoría débil. Las tres son **una llamada** a una función
pública de `quoss.channel`, y hacerla en el informe habría costado una línea.

En vez de eso subieron a
[`HorizontalBudgetResults`](../../src/quoss/scenario/result.py), donde las
rellena el motor y las comprueba `tests/e2e/test_horizontal_scenario.py` contra
una cadena escrita a mano. **La línea que se habría ahorrado era una línea de
física que ningún test de extremo a extremo alcanza.**

Y las tres tenían ya una razón independiente para estar en el resultado, que es
lo que confirma que el sitio era ese: el [ADR 0017 §4](0017-publication-figures.md)
prohíbe que `plot_horizontal_key_against_distance` **adivine** sus dos marcas a
partir de las filas de un barrido —«una marca adivinada parece medida»—, así que
las exige como argumentos; antes de estos campos, la única forma de dárselas era
que el llamante importara `quoss.channel` y las calculara. El mismo defecto, un
paso más afuera.

**Y la regla se comprueba**, porque una regla que nadie comprueba dura hasta la
primera prisa: `tests/dossier/test_docs.py::TestTheGeneratorEvaluatesNoPhysics`
parsea el AST de cada módulo del paquete y falla si aparece uno de esos cuatro
imports.

**El caso que justifica el tercer campo, y que apareció al escribirlo.** El
primer borrador de `GE-0b.md` decía que la varianza log-irradiancia del receptor
es «la fila de arriba por la de más arriba» — es decir, `A` por la varianza de
Rytov. **Es falso, y de la peor manera: es cierto en el banco y falso en el
campo.** La varianza de Rytov que el resultado reporta es la de **onda plana**,
que es la cifra de referencia contra la que los dos enlaces se afinaron; lo que
ve el detector es `A` por la varianza puntual de la **onda declarada**. GE-0b
declara `plane`, así que ahí el producto sale: 4.45e-05 × 0.1988 = 8.849e-06
Np². GE-1 declara `spherical`, y el mismo producto da 0.04745 contra el 0.01931
que reporta — un factor **2.457** de más, que es la razón entre las dos formas
cerradas. Lo cazó el test que aserta los tres campos nuevos, no la lectura del
documento. Por eso `A` es un campo propio y no algo que un consumidor deduzca
dividiendo: dividir acierta en el banco y falla por 2.46 en el campo.

---

## Decisión 3 — El registro va por nombre de escenario, y no hay plantilla

**Qué se hace.** `quoss.dossier.base.dossier_for` busca el constructor por el
campo `name` del escenario. Un escenario sin constructor es un `ScenarioError`
que **lista los tres que sí lo tienen**. No hay `--kind`, no hay plantilla, y no
hay camino genérico.

**Por qué.** Un expediente es **prosa escrita para un experimento**, no una
forma de informe rellenada con las cifras que un escenario resulte tener.
`GE-0b.md` existe para decir cuál de las preguntas de GE-1 **no** contesta un
banco de dos metros; ninguna plantilla produce esa frase.

**El fallo que esto evita** es el que importaría: un documento con aspecto
convincente —título, tablas, hash en cabecera— generado para un escenario para
el que nadie escribió secciones, cargando las cifras que el camino genérico
alcanzara y **callado sobre todo lo que no**. Sus omisiones serían invisibles
justamente para el lector que no puede comprobarlas. Un error que dice qué
escenarios sí tienen expediente es mejor resultado.

**Corolario:** `--out` es obligatorio y no tiene defecto. El defecto natural
sería la ruta commiteada, y entonces `quoss dossier scenarios/ge1_1km.yaml`
**reescribiría un fichero versionado** como efecto de una orden que alguien
teclea para mirar la salida. Reescribir un documento trazado vale cuatro
palabras más de línea de órdenes. Para los tres a la vez está
`python -m quoss.dossier`, que también tiene `--check` de solo lectura.

---

## Decisión 4 — Cada documento **termina** con lo que el modelo no puede afirmar, y cada hueco lleva su coste

**Qué se hace.** La última sección de los tres es «What this model cannot
claim»: una tabla de huecos declarados del
[ADR 0009](0009-citation-policy.md), cada uno con **qué vale en las cifras de
arriba**. `Limit.__post_init__` levanta `ScenarioError` si esa celda está vacía,
y el test lo comprueba también sobre el texto renderizado.

**Por qué al final y no al principio.** Lo último que se lee es el límite de la
afirmación, no la afirmación. Un lector que abandone a media página habrá
abandonado habiendo leído las salvedades, no un resumen que las omite.

**Por qué el coste es obligatorio.** Una salvedad sin magnitud no se puede usar:
un lector que no puede dimensionar una salvedad, o las ignora todas o se niega a
decidir. Así que `GE-1.md` incluye una sección cuyo único propósito es poner
precio a un decibelio —**uno cuesta 3 435 865 bits, el 22.6 % de la sesión**— y
los huecos que solo se pueden acotar en decibelios se leen a través de ella. Y
un hueco que nunca se ha medido lo dice en esa columna en vez de quedarse fuera
de la tabla.

**El caso que mejor muestra para qué sirve.** El hueco 22 —la altura de escala
del aerosol, que ninguna fuente publica y cuyo rango en uso es un factor 1.67 en
profundidad óptica— vale en GE-1 **exactamente cero bits**, y el documento lo
mide barriendo de 1200 a 2000 m y obteniendo el mismo entero. No por suerte: el
escenario declara la visibilidad a la altura a la que corre el enlace, así que
la altura de escala no tiene diferencia de altitud sobre la que actuar. El
documento dice también la condición bajo la que ese cero deja de valer, que es
lo que un lector necesita antes de mover el enlace a una montaña.

---

## Lo que esto **no** decide

- **No convierte un expediente en validación.** Ninguna de sus cifras es un V2
  ni un V3; son lo que este modelo dice. Las comparaciones con literatura siguen
  siendo `docs/validation.md` y solo esa ([ADR 0018](0018-validation-is-a-table-not-a-badge.md)).
- **No fija cuántos expedientes habrá.** Añadir uno es un módulo con su `SPEC`
  y una línea en `DOSSIER_MODULES`.
- **No mete figuras.** Los tres son texto y tablas. `quoss.viz` dibuja, y una
  figura dentro de un fichero que se compara byte a byte pediría un PNG
  reproducible bit a bit, que matplotlib no garantiza entre versiones.

## Referencias

- [ADR 0028](0028-the-cli-computes-nothing.md) — la regla de la que esta es una
  capa más afuera.
- [ADR 0018](0018-validation-is-a-table-not-a-badge.md) — el arreglo de tres
  piezas (generar, commitear, comparar byte a byte) que esto reutiliza.
- [ADR 0017](0017-publication-figures.md) §2 y §4 — la banda plana-a-esférica que
  no es una barra de error, y las dos marcas que no se adivinan.
- [ADR 0009](0009-citation-policy.md) — el registro de huecos que la sección
  final de cada documento enumera.
- `notes/LAST_CHANGES.md` §47 — las cifras de esta ronda.

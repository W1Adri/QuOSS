# ADR 0030 — Una versión es algo que se puede citar, y el commit no cabe en todas partes

- **Estado:** aceptado
- **Fecha:** 2026-09-19
- **Etapa:** 9–11 (distribución), aunque la decisión es de hoy
- **Sustituye a:** nada
- **Relacionado:** [0014](0014-scenario-contract-and-provenance.md) (procedencia
  en cada resultado), [0018](0018-validation-is-a-table-not-a-badge.md),
  [0027](0027-four-levels-of-distribution.md) (los cuatro niveles de entrega),
  [0029](0029-a-dossier-is-generated.md) (un expediente se genera)

---

## Contexto

### Qué es citar un programa, y por qué no es obvio que haga falta

Citar un artículo es rutina: hay un DOI, hay un año, hay una lista de autores, y
todo el mundo sabe dónde ponerlo. **Citar un programa no lo es**, y el motivo es
que un programa no es un objeto fijo: el «QuOSS» que produjo una cifra en marzo
y el que la produce en septiembre pueden diferir en el modelo de extinción, en
la cota finite-key o en la definición de un pase, y la cifra ser distinta sin
que nada en el nombre lo diga.

Hay entonces dos preguntas distintas, y conviene separarlas antes de decidir
nada:

1. **«¿Cómo nombro este programa en una bibliografía?»** Esta es la pregunta de
   quien escribe un artículo de revisión o un documento de misión. La respuesta
   es un objeto estable —autor, título, versión, año, y a ser posible un DOI— y
   lo que hace falta es que ese objeto exista y sea el mismo para todos.
2. **«¿Con qué código exactamente se calculó esta cifra?»** Esta es la pregunta
   de quien tiene delante un resultado y quiere reproducirlo. La respuesta es un
   commit: cuarenta caracteres hexadecimales que nombran un árbol y solo uno.

Son preguntas distintas porque tienen granularidades distintas. **Una versión
cubre muchos commits**; entre `0.1.0` y `0.2.0` puede haber cien árboles
diferentes, todos llamándose `0.1.0` mientras se trabaja. Para la bibliografía
eso está bien —nadie cita un commit— y para la reproducción no sirve.

### El problema concreto, medido

Hasta esta PR este repositorio contestaba mal las dos.

- **La primera, porque no había nada que citar.** No había `CITATION.cff`, no
  había tags —`git tag -l` devolvía vacío con 29 ADRs y 3 968 tests dentro— y no
  había changelog. Un simulador que produce expedientes reproducibles y no tiene
  forma de ser citado obliga a describirlo en prosa cada vez que se apoya un
  número en él, y dos descripciones en prosa del mismo programa nunca son la
  misma.
- **La segunda, a medias.** `quoss --version` imprimía `quoss 0.1.0` y nada más.
  El commit sí estaba en `Provenance` desde el
  [ADR 0014](0014-scenario-contract-and-provenance.md), así que cualquier
  directorio de salida lo llevaba en `result.json`; pero la herramienta, la que
  alguien ejecuta para saber qué tiene instalado, no lo decía.

---

## Decisión

### 1. El proyecto se cita como software, con `CITATION.cff` y un tag por versión

`CITATION.cff` en la raíz, porque es el formato que GitHub lee para pintar el
botón «Cite this repository» y el que Zenodo convierte en metadatos de depósito
sin intervención. Cada versión lleva su tag anotado `vX.Y.Z`, y el tag es el
disparador: Zenodo, una vez conectado el repositorio, acuña un DOI **por cada
release publicada desde un tag**, más un DOI «de concepto» que siempre apunta a
la última.

**El procedimiento se escribe, no solo el resultado.** `CHANGELOG.md` lleva la
receta de la siguiente versión —subir `__version__`, escribir la entrada, tag,
release— porque un procedimiento que solo existe en la cabeza de quien hizo la
versión anterior es un procedimiento que la siguiente versión no sigue.

### 2. `quoss --version` contesta la segunda pregunta, entera

Cuatro líneas: versión, commit, intérprete, numpy y scipy. Son los mismos cuatro
campos que `Provenance` ya escribe en cada resultado, para que la pregunta «¿qué
produjo esto?» tenga **una sola respuesta** tanto si se le hace a un fichero
como si se le hace al comando.

El commit se lee con `git rev-parse HEAD` sobre el directorio del paquete
instalado, que es lo que ya hacía `Provenance`, y vale `None` fuera de un
checkout. Ese caso se imprime como una frase —«unknown (not running from a git
checkout)»— y no se omite: una línea ausente no distingue «instalado desde PyPI»
de «esta build no supo registrarlo».

### 3. El commit **no** entra en los cuatro documentos generados y commiteados

Los tres expedientes de `docs/experiments/` y `docs/validation.md` llevan la
**versión** en cabecera y no el commit. Esto es deliberado y tiene dos razones,
las dos medibles.

**La primera es aritmética de git y no admite discusión.** Esos cuatro ficheros
están commiteados y un test los compara **byte a byte** con lo que el generador
produce hoy. Un commit no puede contener su propio hash, así que la línea que se
escribiera antes de commitear nombraría el commit *anterior*, y desde el instante
del commit la regeneración daría otra cosa. El test quedaría rojo para siempre, y
la única forma de mantenerlo verde sería excluir esa línea de la comparación —
es decir, dejar de comparar byte a byte justamente el campo que se añadió para
dar garantías.

**La segunda es peor y es la que decide.** `git_commit()` devuelve `None` cuando
no hay repositorio. Los bytes renderizados dependerían entonces de si la máquina
que corre el test tiene un `.git` al lado: el mismo código produciría dos
ficheros distintos en el checkout y en el entorno del wheel. Eso es **un test
que informa de su entorno en vez de del código**, que es exactamente el defecto
que `LAST_CHANGES.md` §32 encontró y cerró, y el que `tests/packaging/` existe
para no volver a tener.

La versión, en cambio, es una función pura del árbol: sale de
`src/quoss/__init__.py`, que es un fichero como cualquier otro. Y hace lo que se
quiere que haga: **una release invalida los cuatro documentos hasta que se
regeneran**, que es la señal correcta, porque una release es precisamente cuando
alguien va a citarlos.

Lo que se pierde con esto es real y se nombra: entre dos tags, un expediente
dice `0.1.0` y eso no nombra un árbol. Quien necesite el árbol lo tiene en el
directorio de salida de la corrida (`result.json` lleva el commit) o ejecutando
`quoss --version` sobre el checkout. El expediente es para decidir, no para
reproducir bit a bit; el que reproduce corre el comando.

---

## Consecuencias

### Lo que esto cierra

- Hay un objeto citable: `CITATION.cff`, tag `v0.1.0`, y un `CHANGELOG.md` que
  dice qué contiene la versión y qué **no** afirma.
- `quoss --version` contesta «con qué código» sin abrir un resultado.
- El procedimiento de la siguiente versión está escrito antes de necesitarlo.

### Lo que no cierra

- **No hay DOI todavía.** Zenodo exige conectar el repositorio desde una cuenta,
  y eso no es una acción que este repositorio pueda hacer por sí mismo. El
  `CHANGELOG.md` lleva los pasos; el día que se ejecuten, el DOI entra en
  `CITATION.cff` y en el README, y esa es una línea de diff.
- **No hay publicación en PyPI.** El wheel se construye y se prueba instalado
  (`tests/packaging/test_wheel.py`), pero nadie lo sube. `pip install quoss`
  todavía no resuelve, y el README dice clonar.
- **Un expediente sigue sin nombrar un árbol entre dos tags**, por lo de arriba.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Meter el commit en los cuatro documentos y excluir esa línea de la comparación byte a byte** | Compra una línea informativa a cambio de abrir un agujero en la garantía. Y el agujero no es donde parece: una vez que el test acepta «todo menos esta línea», la siguiente excepción cuesta un argumento menos |
| **Derivar la versión del `git describe`** (p. ej. `0.1.0+12.gabc1234`) | Resuelve la granularidad, y rompe lo mismo: la versión deja de ser una función pura del árbol, los cuatro documentos vuelven a depender del `.git`, y el wheel construido fuera de un checkout no tendría versión |
| **Hashear `src/quoss/` y poner ese hash en la cabecera** | Es puro y no tiene la paradoja del commit, pero convierte cualquier edición en `src/` —un typo en un docstring— en cuatro documentos que regenerar. Y destruye la señal: hoy un fallo del test byte a byte significa «este cambio movió una cifra en un documento que alguien va a leer», que es informativo; con un hash de fuentes significaría «tocaste un fichero», que no |
| **Un `CITATION.bib` a mano en vez de `.cff`** | BibTeX no lo lee ni GitHub ni Zenodo. `CITATION.cff` se convierte a BibTeX, APA y a metadatos de Zenodo automáticamente; el camino inverso no existe |
| **Esperar a tener DOI para poner tag y `CITATION.cff`** | El tag es lo que **dispara** el DOI. Esperar al DOI para poner el tag es esperar al efecto para provocar la causa |

---

## Referencias

- Citation File Format 1.2.0, `citation-file-format.github.io` — el esquema que
  valida `CITATION.cff`.
- Zenodo, «GitHub integration» — el DOI se acuña desde una *release*, que a su
  vez sale de un tag; el DOI de concepto apunta siempre a la última.
- `notes/LAST_CHANGES.md` §32 — los dos tests que informaban de su entorno en
  vez de del código, que es el argumento de la §3 de este ADR.
- [ADR 0014](0014-scenario-contract-and-provenance.md) — los campos de
  `Provenance`, que son los que `quoss --version` repite.
- [ADR 0029](0029-a-dossier-is-generated.md) — por qué los expedientes se
  comparan byte a byte, que es la restricción bajo la que se decide la §3.

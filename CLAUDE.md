# CLAUDE.md — cómo trabajar en QuOSS

> Único sistema de metadatos de agentes del repo, por la regla de higiene de
> [`notes/archive/GUIA_REIMPLEMENTACION-v3.md`](notes/archive/GUIA_REIMPLEMENTACION-v3.md)
> §5, «Higiene de repo»: **un** sistema, no cuatro. Si hace falta otro fichero de instrucciones, va aquí dentro.

---

## Norma 1 — Explicar como si el lector no supiera nada del tema

**Regla:** toda explicación, tanto de conceptos de física/matemáticas como de
código, se escribe **desde cero, defendida y con un ejemplo concreto**. Sin dar
por sabido ningún término. Aplica a las respuestas en conversación, a los
docstrings, a los ADRs y a las entradas de `notes/LAST_CHANGES.md`.

### Las tres partes, y por qué las tres

Una explicación que cumple la norma tiene siempre estas tres, en este orden:

1. **Qué es** — en palabras llanas, antes de cualquier fórmula. Si aparece un
   término técnico (osculador, secular, argumento de latitud, QBER), se define
   **la primera vez que se usa**, en la misma frase o la siguiente. No vale
   «como es sabido», no vale enlazar y seguir.
2. **Por qué es así / por qué importa** — la defensa. Qué problema resuelve, qué
   pasaría si se hiciera de otra forma, y cuál es el coste de equivocarse. Una
   afirmación sin defensa es una que el lector tiene que ir a comprobar fuera, y
   eso es exactamente el tiempo que esta norma existe para no perder.
3. **Un ejemplo con números** — un caso concreto, con cifras, que se pueda
   seguir a mano o ejecutar. Preferiblemente medido en este repo, no citado de
   memoria.

### Por qué esta norma existe (la defensa de la norma misma)

Este proyecto es sobre todo física poco intuitiva —marcos de referencia,
perturbaciones orbitales, criptografía cuántica— donde **el modo de fallo
característico no es un error, es un número plausible y equivocado**. El README
lo dice de otra forma: «prohibido degradar en silencio».

Un lector que no entiende del todo un concepto no puede detectar un número
plausible y equivocado. Puede leer el código, ver que pasan los tests, y aceptar
un resultado desplazado. Así que explicar mal no es un problema de comodidad: es
un agujero en la única defensa real que tiene el proyecto, que es que la persona
que lo revisa entienda lo que está mirando.

Y el coste es asimétrico. Escribir tres párrafos de más cuesta tres párrafos.
No entender un concepto cuesta reabrirlo entero semanas después, cuando ya hay
código encima que depende de haberlo entendido.

### Ejemplo de la norma aplicada

**Mal** (asume el vocabulario, no defiende, no da números):

> `secular_rates_j2` espera elementos medios. Pasarle osculadores introduce un
> error O(J2).

Un lector que no sepa qué es «medio», «osculador» o «O(J2)» no saca nada de esa
frase, y aun sabiéndolo no sabe si le importa.

(Como **estilo** el ejemplo sigue valiendo, que es para lo que está. Como
**hecho** ya está caducado: desde el [ADR 0006](docs/adr/0006-osculating-vs-mean-elements.md),
pasarle osculadores no introduce un error, levanta un `DomainError`. Es la
diferencia entre lo que la norma quiere ilustrar y lo que el código hace hoy, y
merece decirse porque un ejemplo de mala redacción que además informa mal es una
trampa doble.)

**Bien** (define, defiende, mide):

> Un satélite real no sigue una elipse: la Tierra está achatada y lo empuja fuera
> de ella constantemente. Hay entonces dos formas de describir «su órbita»:
>
> - **Elementos osculadores**: la elipse que el satélite seguiría *en este
>   instante* si la Tierra se volviera de golpe una esfera perfecta. Es tangente
>   a la trayectoria real, y cambia todo el tiempo. Es lo que devuelve
>   `rv_to_coe`.
> - **Elementos medios**: esa elipse con el bamboleo rápido ya restado. Es una
>   elipse que no existe en ningún instante concreto, pero que resume la órbita
>   promediada. Es lo que describen las tasas seculares.
>
> «Secular» aquí no tiene nada que ver con religión: en mecánica celeste
> significa *que crece sin parar*, en contraste con lo que oscila y se cancela.
> `secular_rates_j2` da las tres derivas que no se cancelan.
>
> «O(J2)» significa «del tamaño de J2». J2 = 1.08e-3 es el número que mide cuánto
> se achata la Tierra, así que un error O(J2) es un error de una parte en mil.
> Una parte en mil de 7000 km son 7 km, y por eso importa.
>
> Medido en este repo (`propagate_zonal` como verdad, J2 solo, SSO a 700 km con
> los elementos declarados en ν = 0): alimentar las tasas seculares con
> osculadores da **86 km de error tras una vuelta y 1290 km tras quince**, casi
> todo en la dirección del movimiento. La parte que crece son ~11.5 s de error de
> reloj por vuelta, unos 2.9 minutos al día — contra un pase que dura diez. Y
> cuánto cuesta depende de dónde se declaren los elementos: en ν = 45° la misma
> órbita se queda en 0.07 km por vuelta, así que no hay una cifra única que citar.
> Está en `tests/orbits/test_propagator.py::TestWhatNotHavingBrouwerLyddaneCosts`,
> junto con la derivación que la explica.

La segunda versión es cinco veces más larga y es la que hay que escribir.

**Y una nota sobre el «medido en este repo» de esa última línea, que es la parte
más fácil de saltarse.** Las cifras de arriba estuvieron citadas en quince sitios
—incluido el texto de un `DomainError`— durante tres días, con un valor 5.9 veces
menor, porque salieron de una medición hecha a mano y guardada solo en prosa.
«Medido en este repo» significa **medido por un test que corre**; si no hay test,
lo honesto es escribir de dónde salió el número y que no está reproducido.

### Lo que la norma **no** es

- **No es rebajar el rigor.** Los números, las citas y las tolerancias no se
  redondean para que la explicación fluya. Se explican.
- **No es repetir lo obvio del lenguaje.** `for` no se explica; `arctan2` en vez
  de `arccos`, sí, porque ahí hay una razón numérica.
- **No es prohibir el vocabulario técnico.** Es obligar a definirlo la primera
  vez. El término correcto se usa, con su traducción al lado.

---

## Norma 2 — Al explicar código, decir qué hace *y por qué así*

Misma estructura que la norma 1, aplicada a un fragmento concreto: qué hace esta
línea, por qué esta forma y no la evidente, y un caso donde la diferencia se ve.

Ejemplo, sobre `ClassicalElements.argument_of_latitude_rad`:

```python
return _wrap_two_pi(self._argp_rad + self._true_anomaly_rad)
```

- **Qué hace:** suma dos ángulos y devuelve el resultado dentro de una vuelta
  (`[0, 360°)`). El resultado, `u`, es «cuánto ha avanzado el satélite desde que
  cruzó el ecuador hacia el norte».
- **Por qué el envuelto:** los dos operandos ya vienen dentro de una vuelta, así
  que su suma puede llegar a 720°, y 510° y 150° tienen que ser el mismo ángulo.
- **Por qué sin `if`:** el proyecto es vectorizado sobre el eje temporal; una
  rama obligaría a ramificar por elemento del array. `_wrap_two_pi` es
  aritmética, funciona igual para uno y para mil.
- **El caso que lo demuestra:** `argp = 310°`, `ν = 200°` → la suma cruda es
  510°, la propiedad da 150°. Está en
  `test_argument_of_latitude_wraps_past_one_turn`, con una segunda órbita que
  *no* envuelve en el mismo array, porque una rama solo se notaría cuando los dos
  casos comparten llamada.

---

## Norma 0 — Sincronizar antes de afirmar que algo no existe

**Regla:** lo primero de cualquier sesión, antes de leer nada y antes de decir
que un fichero, un símbolo o una decisión falta:

```bash
git fetch origin --prune && git status -sb
```

**Por qué.** Un checkout local puede estar decenas de commits por detrás de
`origin/main` sin que nada en el árbol lo diga: `ls`, `grep` y `git log` son
igual de rápidos y de convincentes sobre un árbol rancio que sobre uno fresco.
El resultado es una afirmación **defendida con evidencia y falsa** — el modo de
fallo exacto que este proyecto persigue en los números, aplicado por una vez a
la verificación. Y cuesta más ahí: la verificación es lo que se supone que caza
a los números.

**El ejemplo, medido, porque pasó.** El 2026-09-19 una sesión concluyó que
`HorizontalResult`, el tag `link`, `scenarios/ge1_1km.yaml`, los ADRs 0024 y
0025 y el §40 de `LAST_CHANGES.md` no existían, con una tabla de siete filas de
evidencia: siete `grep` con cero ocurrencias, `ls docs/adr/` acabando en 0023,
`git branch -a` sobre trece ramas. Las siete filas eran **ciertas sobre el árbol
que tenía delante y falsas sobre el proyecto**. `git fetch` movió `main` de
`fd3b3fd` a `2596618`: **29 commits**, y once refs remotos que ya no existían.
El `grep` de «cero ocurrencias de `HorizontalResult`» devuelve hoy 94. Está en
`notes/INCONSISTENCIAS.md` #16, abierta, porque **no se puede asertar**: la
suite corre sobre el árbol que tiene, así que ningún test distingue uno fresco
de uno rancio.

---

## Contexto del proyecto — qué leer, en qué orden, y cuánto cuesta

**El orden importa y está medido.** Hasta el 2026-09-19 esta sección era una
tabla de seis ficheros sin orden ni tamaño, y dos de ellos —`LAST_CHANGES.md` con
6 834 líneas y `ROADMAP.md` con 935— **no se leían**: una sesión llegaba a las
primeras pantallas y seguía. El resultado tiene fecha: la PR C la escribió una
sesión que no había leído lo que la PR B dejó dicho. El orden de abajo es de
arriba a abajo, parando cuando ya sepas lo que ibas a hacer.

**La columna de coste es la cota, no la medida de hoy.** Escribir ahí el número
de líneas de hoy fue el defecto que esta misma tabla cometió durante tres días:
decía 910 y 321 cuando los ficheros iban por 1 068 y 401, porque una bitácora
crece en cada PR y un número copiado a mano no. La cota, en cambio, no envejece
—`tests/unit/test_notes.py` la aserta— y es lo que de verdad hace falta saber
antes de abrir el fichero: cuánto puede llegar a costar, no cuánto costó el
martes.

| # | Fichero | Cota de líneas | Para qué | ¿Siempre? |
|---|---|---|---|---|
| 1 | [`notes/INCONSISTENCIAS.md`](notes/INCONSISTENCIAS.md) | ≤ 500 | **Lo que el código o los documentos afirman y hoy no se cumple.** Primero porque es lo único que puede hacerte perder la tarde entera | **sí** |
| 2 | [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md) | ≤ 1 732 | Las **cinco últimas** entradas completas, más un índice de una línea por entrada archivada. Es el estado de hoy y cómo se llegó | **sí** |
| 3 | [`notes/ROADMAP.md`](notes/ROADMAP.md) | ≤ 500 | Qué existe, qué falta, en qué orden. **Estado, no justificación** | **sí** |
| 4 | `docs/adr/<el tuyo>.md` | 1 por decisión | El **porqué**. La tabla del ROADMAP te dice cuál te toca; no los leas todos | el de tu módulo |
| 5 | [`tests/golden/README.md`](tests/golden/README.md) | — | Los cuatro niveles V1–V4, y por qué V4 no es validación | si vas a asertar algo |
| 6 | [`notes/archive/`](notes/archive/) | sin cota | Las entradas §1–§44 íntegras, y la guía v3 con su numeración §0–§5 congelada. Crece a propósito: es lo que deja de pesar en el camino de lectura | solo si el índice te manda |
| 7 | [`notes/GUIA_REIMPLEMENTACION.md`](notes/GUIA_REIMPLEMENTACION.md) | ≤ 500 | Qué era SimulCTTC, y nada más: la escalera de lenguajes se fue al [ADR 0026](docs/adr/0026-the-language-ladder.md) | si tocas `kernels/` |

Las tres cotas de 500 son la misma y están derivadas en
`test_the_other_notes_stay_readable`; la de 1 732 no se elige, sale de
multiplicar las cinco entradas vivas por la más larga jamás escrita y sumar el
índice.

**Hoy `INCONSISTENCIAS.md` tiene una entrada abierta**, y su valor está en cómo
se llenó: de las diecinueve inconsistencias registradas que ha tenido, **ninguna
la detectaba la suite**; una era un número citado en quince sitios que resultó
falso, y otra es una verificación que se hizo contra un árbol de hace 29 commits
(de ahí la norma 0).

**Dónde va lo que escribas al terminar**, que es la otra mitad de la regla:

- **Una entrada nueva en `LAST_CHANGES.md`**, con su cifra resumen. Si con ella
  pasan de cinco, la más vieja se archiva — y solo después de comprobar que todo
  lo que carga peso en ella vive ya en un ADR, un test o un docstring. Lo aserta
  `tests/unit/test_notes.py`.
- **El porqué va al ADR**, no a la bitácora ni al roadmap. Una justificación en
  dos sitios es una que se va a quedar quieta en uno de los dos.
- **Lo que no se pueda cerrar va a `INCONSISTENCIAS.md` con su medida**, nunca a
  un comentario en el código.

Reglas que no se negocian, todas ya escritas en el README y los ADRs:

- **SimulCTTC no es un oráculo.** Diff informativo, nunca un `assert`.
- **V4 no es validación.** Lo que se reporte como validado traza a V2 (valor
  publicado) o V3 (implementación independiente).
- **Prohibido degradar en silencio.** Entrada mala = `DomainError`. Un modelo que
  no se puede evaluar sale en `warnings[]`, nunca en un `except: pass`.
- **No inventar números y etiquetarlos «publicados».** Un hueco declarado es
  mejor que un V2 falso.
- **Tolerancias derivadas, no ajustadas.** Una tolerancia elegida para que pase
  el resultado de hoy no puede fallar nunca, así que no prueba nada.
- **Vectorizado sobre el eje temporal desde la primera línea.** Una firma escalar
  contamina a todos los llamantes.

## Comandos

```bash
uv run pytest            # suite
uv run ruff check .      # lint
uv run ruff format .     # formato
uv run mypy              # tipos
```

# CLAUDE.md — cómo trabajar en QuOSS

> Único sistema de metadatos de agentes del repo, por la regla de higiene de
> [`notes/GUIA_REIMPLEMENTACION.md`](notes/GUIA_REIMPLEMENTACION.md) §5: **un**
> sistema, no cuatro. Si hace falta otro fichero de instrucciones, va aquí dentro.

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

## Contexto del proyecto (lo mínimo antes de tocar nada)

| Fichero | Para qué |
|---|---|
| [`notes/ROADMAP.md`](notes/ROADMAP.md) | En qué orden se construye y por qué ese orden |
| [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md) | Estado actual, decisiones tomadas, y lo pendiente con fecha |
| [`notes/INCONSISTENCIAS.md`](notes/INCONSISTENCIAS.md) | Lo que el código o los documentos afirman y hoy no se cumple. **Hoy está vacío**, y su valor está en cómo se llenó: ninguna de las siete entradas que tuvo la detectaba la suite, y una de ellas era un número citado en quince sitios que resultó falso |
| [`notes/GUIA_REIMPLEMENTACION.md`](notes/GUIA_REIMPLEMENTACION.md) | Por qué la arquitectura es esta y no la de SimulCTTC |
| [`tests/golden/README.md`](tests/golden/README.md) | Los cuatro niveles de verificación V1–V4 |
| `docs/adr/*.md` | Las decisiones no obvias, una por fichero |

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

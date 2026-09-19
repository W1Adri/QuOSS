# QuOSS — las decisiones de arquitectura que no tienen ADR

> **Qué queda aquí, y por qué tan poco.** Este fichero era la *Guía de
> reimplementación v3* (2026-07-31, 267 líneas): el documento que propuso
> reescribir SimulCTTC y que fijó la estructura, el tooling, el orden de
> migración y las mejoras de física. **Esa reimplementación ya ocurrió**, así que
> la mayor parte del documento pasó a describir un pasado — y a duplicar lo que
> `notes/ROADMAP.md`, `CLAUDE.md` y `docs/adr/` ya dicen del presente. Está
> íntegro en [`archive/GUIA_REIMPLEMENTACION-v3.md`](archive/GUIA_REIMPLEMENTACION-v3.md).
>
> **Y desde el 2026-09-19 queda menos todavía, que era el objetivo.** Las dos
> decisiones que este fichero sostenía sin ser su dueño —la escalera de lenguajes
> y los cuatro niveles de distribución— **ya tienen ADR**:
> [0026](../docs/adr/0026-the-language-ladder.md) y
> [0027](../docs/adr/0027-four-levels-of-distribution.md). Estaban aquí porque un
> ADR se numera al escribirse y eso es una decisión de quien lo mantiene, no un
> efecto secundario de reordenar notas; escritos los dos, esas secciones se
> fueron con ellos y no se han duplicado.
>
> Lo que queda es **lo único que no tiene otro dueño**: el diagnóstico de
> SimulCTTC, que es lo que sostiene la regla «SimulCTTC no es un oráculo» —hoy
> citada en el README, en `ROADMAP.md` y en `tests/golden/README.md`, los tres
> sin su defensa— y lo que sostiene el «la web es un cliente» del ADR 0027. El
> día que ese diagnóstico tenga dueño, este fichero desaparece.

---

## 1. Qué era SimulCTTC, y por qué su salida no se congeló

Esto sostiene una regla que aparece en el README, en el `ROADMAP.md` y en
`tests/golden/README.md`: **SimulCTTC no es un oráculo. Diff informativo, nunca
un `assert`.** Sin este apartado esa regla es una afirmación sin defensa.

**SimulCTTC** es el simulador anterior del que QuOSS es la reescritura: un
backend FastAPI con la física dentro, más un frontend de ~16 000 líneas de
JavaScript sin tipos. **Lo bueno era la física**: referenciada y cubriendo la
cadena completa, de órbitas a métricas de sistema. Lo que no se pudo conservar
fue su *salida*.

**Por qué no, y es lo que da la regla.** La tentación obvia al reescribir es
congelar la salida del programa viejo y comprobar que el nuevo la reproduce. Eso
es válido cuando el programa viejo está validado. SimulCTTC **nunca lo estuvo**,
y leerlo destapó cuatro defectos que congelar su salida habría canonizado —
convertidos en «lo correcto» por el propio acto de usarlos como referencia:

1. **Latitud geocéntrica devuelta como geodésica.** Son ángulos distintos en una
   Tierra achatada, y el error es máximo a 45° de latitud.
2. **Estaciones colocadas sobre una esfera**, con hasta **~21 km** de error de
   posición frente al elipsoide WGS-84.
3. **Una tasa «secular» para J3** que no existe: J3 no tiene término secular de
   primer orden. El número que devolvía era una oscilación etiquetada como deriva.
4. **La época caía silenciosamente al reloj de pared** cuando no se declaraba, así
   que dos ejecuciones del mismo escenario daban órbitas distintas.

Ninguno de los cuatro hace que el programa falle: los cuatro producen números
plausibles. Ese es exactamente el modo de fallo contra el que está construido
todo lo demás de este repo.

**Los otros problemas eran de arquitectura, no de física**, y ya están
corregidos: física escalar con bucles Python (`samples ≤ 900` por diseño), ~486
líneas de pipeline **dentro de un handler HTTP**, el escenario existiendo solo
como request, un único `test_all.py` de 118 KB sin CI, globals mutables, y
`except Exception` que devolvían «sin escintilación» sin decirlo. El diagnóstico
completo, con su tabla de costes, está en el archivo.

---

## 2 y 3 — se fueron a `docs/adr/`

Este fichero llevaba dos apartados más: **la escalera de lenguajes** (Python →
Numba → Rust → C++, con «MATLAB no» y su regla de entrada) y **los cuatro
niveles de distribución** (CLI → `serve` → Docker → cloud, con la web como
cliente). `LAST_CHANGES.md` §41 los señaló como decisiones con forma de ADR y
sin ADR, y §42 los escribió:

| Apartado | Dónde está hoy | Qué gobierna |
|---|---|---|
| La escalera de lenguajes | [**ADR 0026**](../docs/adr/0026-the-language-ladder.md) | `kernels/`, etapa 2.4 |
| Los cuatro niveles de distribución | [**ADR 0027**](../docs/adr/0027-four-levels-of-distribution.md) | `cli/`, `api/`, `web/`, `deploy/`; etapas 7 y 9–11 |

**No están aquí *y* allí**, que es el punto: este fichero era la tercera fuente
de verdad de `ROADMAP.md` y de `CLAUDE.md`, y una justificación en dos sitios es
una que se queda quieta en uno de los dos. Los dos ADRs llevan además la
medición que aquí no había —los tiempos por etapa y el coste del bucle en serie
en el 0026, los tamaños del wheel y de lo que arrastra en el 0027—, porque un
ADR de este proyecto trae sus cifras.

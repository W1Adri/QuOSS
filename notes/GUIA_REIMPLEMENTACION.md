# QuOSS — las decisiones de arquitectura que no tienen ADR

> **Qué queda aquí, y por qué tan poco.** Este fichero era la *Guía de
> reimplementación v3* (2026-07-31, 267 líneas): el documento que propuso
> reescribir SimulCTTC y que fijó la estructura, el tooling, el orden de
> migración y las mejoras de física. **Esa reimplementación ya ocurrió**, así que
> la mayor parte del documento pasó a describir un pasado — y a duplicar lo que
> `notes/ROADMAP.md`, `CLAUDE.md` y `docs/adr/` ya dicen del presente. Está
> íntegro en [`archive/GUIA_REIMPLEMENTACION-v3.md`](archive/GUIA_REIMPLEMENTACION-v3.md).
>
> Lo que sigue son las **dos cosas que no tienen otro dueño**: el diagnóstico de
> SimulCTTC, que es lo que sostiene la regla «SimulCTTC no es un oráculo», y la
> escalera de lenguajes, que es una decisión no obvia, todavía vigente, y
> **sin ADR** — ver «Lo que esto deja abierto» al final.

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

## 2. La escalera de lenguajes

**Python se queda como lenguaje de la física y la orquestación.** El valor del
proyecto es corrección física e iteración rápida, el ecosistema está ahí
(scipy, sgp4, astropy, matplotlib), y un revisor puede leerlo.

**No saltes un escalón sin datos de profiler:**

1. **NumPy vectorizado** — cubre el 90 % del problema. El cuello no era Python:
   era que la física era escalar.
2. **Numba** (`@njit`) para los bucles irreducibles. Mismo fichero, un decorador,
   cero sistema de build. Segundo escalón por defecto.
3. **Rust (PyO3 + maturin)** para un kernel realmente caliente y con contrato
   numérico estable. **Rust antes que C++**: `maturin` produce wheels
   multiplataforma de forma reproducible, seguridad de memoria, y paralelismo
   trivial con `rayon`.
4. **C++** solo si hay que reutilizar una librería C++ existente. Si no, no
   aporta sobre Rust y sí añade fricción de build.

**MATLAB: no.** No es libre ni redistribuible, lo que rompe Docker, el servicio
público y la reproducibilidad por terceros — un revisor no debería necesitar una
licencia. Su única ventaja real es la calidad de las gráficas, y eso lo replica
`viz/style.py`.

**Binario descargable (PyInstaller/Nuitka): no.** Empaquetar numpy/scipy da
artefactos de 200–400 MB, frágiles, uno por SO, con notarización en macOS y
Windows, y **no scriptables** — un investigador no puede meterlos en un bucle de
barrido. Un wheel + `uvx quoss` da el mismo «descarga y ejecuta» sin perder nada.

**WASM/Pyodide: descartado por ahora.** El stack numérico en WASM es lento y
pesado.

**Frontend: TypeScript, no JS plano**, con Vite + Svelte y deps **vendorizadas**
(sin CDN). Las figuras del paper salen de Python, no del navegador.

**La regla que gobierna los cuatro escalones:** se cambia de lenguaje solo tras
medir, solo para un kernel con contrato numérico estable, y **siempre** con una
implementación de referencia en NumPy puro contra la que un golden test
demuestre equivalencia. *Un kernel acelerado sin su referencia es deuda, no
optimización.*

---

## 3. Los cuatro niveles de distribución

El mismo motor en los cuatro, y la web como **cliente** y no como simulador.

| Nivel | Qué es | Para quién |
|---|---|---|
| 0 | `uv run quoss run scenario.yaml` | El día a día. Reproducible, scriptable, sin servidor. **Aquí salen las figuras del paper** |
| 1 | `quoss serve` → UI en localhost | Exploración interactiva, cero infra |
| 2 | Imagen Docker publicada | Cualquiera: `docker run …`. **Funciona offline** |
| 3 | Servicio cloud público | Opcional, y con condiciones: cola de jobs, límites de escenario, rate limiting |

**La inversión de jerarquía es la decisión**, no la tabla: en SimulCTTC la web
*era* el simulador, y por eso no había CLI, ni notebook, ni test de extremo a
extremo limpio. Qué fichero va en qué etapa está en
[`ROADMAP.md`](ROADMAP.md) 9–11.

---

## Lo que esto deja abierto

**Los apartados 2 y 3 son decisiones con forma de ADR y no tienen ADR.** Son no
obvias, siguen vigentes, gobiernan trabajo futuro (`kernels/` de la etapa 2.4,
`deploy/` de la 11) y están escritas en un fichero de notas en vez de en
`docs/adr/`, que es donde este proyecto dice que viven las decisiones no obvias.

**No se ha inventado un ADR para ellas aquí**, porque un ADR se numera al
escribirse y escribirlo es una decisión de quien vaya a mantenerlo, no un efecto
secundario de reordenar notas. Queda dicho, que es lo que se puede hacer sin
tomarla: cuando se escriba la etapa 2.4 o la 11, estos dos apartados son el
borrador de sus ADRs y este fichero desaparece.

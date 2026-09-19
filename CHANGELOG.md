# Changelog

Qué contiene cada versión de QuOSS, qué reproduce y **qué no afirma**. Formato
inspirado en [Keep a Changelog](https://keepachangelog.com/); el versionado es
[semántico](https://semver.org/lang/es/), con la salvedad de que en este
proyecto un cambio que mueve una cifra publicable es *breaking* aunque no rompa
ninguna firma.

Este fichero **deriva del índice** de [`notes/LAST_CHANGES.md`](notes/LAST_CHANGES.md)
y no lo reescribe. Son dos documentos con dos lectores: la bitácora es para
quien va a tocar el código y guarda el camino; este es para quien va a citar una
versión y necesita saber qué le está citando. Cuando los dos digan lo mismo, la
bitácora es la que manda, porque es la que tiene la medida al lado.

---

## [0.1.0] — 2026-09-19

Primera versión citable. Cierra el **Hito B** del
[ROADMAP](notes/ROADMAP.md): resultados validados contra literatura y
reproducibles por terceros.

### Qué contiene

Un simulador completo de enlace óptico cuántico, de fichero YAML a clave
certificada, en Python puro y vectorizado sobre el eje temporal.

| | |
|---|---|
| **Órbitas** | Marcos TEME ↔ ITRF ↔ geodésico, Kepler en forma cerrada (Markley 1995), fuerza zonal J2/J3/J4 exacta con integrador DOP853, SGP4 envuelto desde el paquete `sgp4`, geometría de visibilidad con *point-ahead* y Doppler |
| **Canal** | Perfil `C_n²` HV-5/7 sobre 139 capas, escintilación en régimen débil y moderado-a-fuerte, promediado de apertura, desvanecimiento por apuntado como distribución, fondo de cielo solar y lunar, detector con cuentas oscuras y *afterpulsing*, presupuesto de enlace con cuantil conjunto exacto, camino horizontal, extinción por visibilidad |
| **QKD** | BB84 con pulsos coherentes débiles y decoy vacío+débil (Ma et al. 2005), cota finite-key componible de Lim et al. 2014 |
| **Sistema** | Detección de pases contra máscara, clave por pase y por día con el bloque igual al pase, Monte Carlo de *fading* correlacionado con P5/P50/P95 y *outage*, probabilidad de línea de vista libre de nubes, agregación de estaciones, nodo de confianza |
| **Contrato** | Escenario Pydantic v2 `frozen` y `extra="forbid"`, unión discriminada `downlink \| horizontal`, hash canónico SHA-256, procedencia en cada resultado |
| **Entrega** | `quoss run`, `sweep`, `validate`, `dossier`; exportación a directorio autodescrito; figuras de publicación; tres expedientes y una tabla de validación generados y commiteados |

### Qué reproduce

**35 casos de ocho fuentes**, en [`docs/validation.md`](docs/validation.md),
recalculados en cada ejecución de la suite y comparados bajo una tolerancia
derivada de cómo está impreso el valor publicado:

- **17 reproducidos** — entre ellos las dos filas de la Tabla 2 de la ITU-R
  P.1622 completas, el perfil HV-5/7 de la P.1621-2, y las identidades de
  decoy de Ma et al. 2005.
- **3 compatibles** — el desacuerdo se explica por un término acotado que la
  fuente omite, y el término está declarado.
- **8 no reproducidos**, con el desacuerdo escrito. Siete son de Ntanos et al.
  2021, y **eso no es un juicio sobre el paper**: es la fuente con los
  parámetros mejor declarados del proyecto, así que es de la que más
  consecuencias impresas se pueden comprobar.
- **7 huecos de fuente** — la fuente no imprime nada computable.

Las ocho fuentes son ITU-R P.1621-2, ITU-R P.1622, Farid & Hranilovic 2007,
Ntanos et al. 2021, Ma et al. 2005, Lim et al. 2014, Sidhu et al. 2022
(SatQuMA) y Liao et al. 2017 (Micius).

### Qué **no** afirma

Esta sección es la que hay que leer antes de apoyar un número en esta versión.

- **Las cifras publicadas son para una atmósfera que no absorbe ni dispersa.**
  Los siete escenarios de `scenarios/` declaran `zenith_transmittance: 1.0`, así
  que son una cota superior sobre la atmósfera y una afirmación exacta sobre
  todo lo demás. **El precio del decibelio no modelado, medido:** 23 km de
  visibilidad —la línea más limpia del código meteorológico de la ITU-R
  P.1817-1— son **0.230 dB cenitales y el 22.7 %** de los 433 442 bits
  certificados del día de referencia; 10 km son el **47.7 %**; con 2 km de bruma
  el día **no certifica nada**.
- **Veintitrés huecos de cita declarados** en el
  [ADR 0009](docs/adr/0009-citation-policy.md), ninguno rellenado con la fuente
  más plausible. Los que más cuestan:
  - *Hueco 1* — **Andrews & Phillips no se cita por número de ecuación**: el
    libro es de pago y no se pudo abrir, así que ninguna de las cuatro
    ecuaciones que el código anterior citaba de él se hereda.
  - *Hueco 2* — los parámetros α y β de la gamma-gamma **no están verificados en
    fuente**.
  - *Hueco 3* — el modelo de apuntado con *boresight* ≠ 0 está **ausente, no
    aproximado**: `channel/pointing.py` modela solo jitter de media cero.
  - *Hueco 14* — la ley de escala de la extinción está publicada y **el número
    que escala no**. El [ADR 0023](docs/adr/0023-traceable-extinction.md)
    estrecha la mitad de dispersión con la Ec. (4) de la ITU-R P.1814; la
    absorción molecular sigue sin número (*hueco 23*).
  - *Hueco 22* — la altura de escala del aerosol **es un parámetro de sitio sin
    valor publicado**.
- **`kernels/` no existe**, y la etapa que lo contendría **no está justificada
  por ninguna medida de hoy**: los 55.6 s que tardan sesenta satélites en un día
  a 1 s miden un bucle en serie (`orbits/propagator.py:535`), no aritmética
  lenta — 927 ms por satélite con S = 60 contra 934 con S = 1, menos del 1 % de
  dispersión ([ADR 0026](docs/adr/0026-the-language-ladder.md)).
- **No hay `api/`, `web/` ni `deploy/`.** Son distribución, no ciencia
  ([ADR 0027](docs/adr/0027-four-levels-of-distribution.md)).
- **Brouwer-Lyddane, Vallado §9.6 como V2 y la reducción completa GCRF↔ITRF
  están abiertas** y ninguna bloquea nada: el hito B se alcanza sin ellas y
  ninguna cambia hoy un número publicable.
- **SimulCTTC no es un oráculo** y no se usa como tal en ninguna aserción.
- **Un *snapshot* de la salida propia (V4) no es validación**, y nada de lo que
  esta versión reporta como validado traza a uno.

### Verificación de la versión

| | |
|---|---|
| Suite | 3 993 tests, entorno del lock y entorno de suelos declarados |
| Cobertura | 100 % de líneas y ramas en todo `src/quoss` |
| Matriz | Python 3.11 / 3.12 / 3.13, macOS arm64, numpy 2.0, suelos mínimos |
| Reproducibilidad | Los tres expedientes y `docs/validation.md` se comparan byte a byte sobre **dos pilas numéricas distintas** |

---

## Cómo se hace la siguiente versión

Cuatro pasos, en este orden. Está escrito aquí y no en la cabeza de quien hizo
la anterior, porque un procedimiento que no está escrito es uno que la siguiente
versión no sigue.

1. **Subir la versión en un sitio**, `src/quoss/__init__.py`. Es la única
   fuente: `pyproject.toml` la lee con `hatch`, `CITATION.cff` la repite y
   `tests/unit/test_project_config.py` falla si las tres no coinciden.
2. **Escribir la entrada de esta lista**, derivada del índice de
   `notes/LAST_CHANGES.md`, con sus tres secciones: qué contiene, qué reproduce
   (con los números de `docs/validation.md`, recontados y no copiados) y **qué
   no afirma**, con el precio medido de cada hueco que tenga uno.
3. **Regenerar los cuatro documentos** —`uv run python -m quoss.dossier` y
   `uv run python -m quoss.validation --write docs/validation.md`— porque llevan
   la versión en cabecera y una release los invalida hasta que se regeneran, que
   es la señal que se quiere ([ADR 0030](docs/adr/0030-a-release-is-something-you-can-cite.md)).
4. **Tag anotado y release.** `git tag -a v0.2.0 -m "QuOSS 0.2.0"`, push del
   tag, y publicar la release en GitHub desde ese tag.

**El DOI de Zenodo, cuando lo haya, se dispara con el paso 4 y con nada más.**
El procedimiento completo, una vez y para siempre:

1. Entrar en `zenodo.org` con la cuenta de GitHub y activar el repositorio
   `W1Adri/QuOSS` en «GitHub → Repositories». Esto solo habilita el enlace; no
   deposita nada.
2. Publicar una release desde un tag. Zenodo la recoge, acuña un **DOI de
   versión** para ella y un **DOI de concepto** que siempre apunta a la última.
3. Poner el DOI de concepto en `CITATION.cff` (`doi:`) y en el README. El de
   versión no hace falta escribirlo: sale de la release.

Hasta que ese paso 1 se ejecute, **no hay DOI y este fichero no finge que lo
haya** — que es la misma regla que gobierna los huecos de cita.

[0.1.0]: https://github.com/W1Adri/QuOSS/releases/tag/v0.1.0

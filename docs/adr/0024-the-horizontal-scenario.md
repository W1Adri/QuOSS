# ADR 0024 — El escenario horizontal: una unión discriminada, un bloque declarado y un resultado propio

- **Estado:** aceptada
- **Fecha:** 2026-09-17
- **Etapa:** 4 (`scenario/`) + 5 (`engine/`), para la escalera de tierra GE-0b y GE-1.
- **Afecta a:** `scenario/models.py` (`LinkKind`, `HorizontalPathSpec`, `SessionSpec`,
  `HorizontalScenario`, `AnyScenario`), `scenario/io.py`, `scenario/hash.py`,
  `scenario/result.py` (`HorizontalResult` y sus dos contenedores),
  `engine/horizontal.py` (nuevo), `engine/pipeline.py` (`run` despacha),
  `engine/sweep.py` (dos juegos de raíces de métrica), `viz/plots.py`,
  `channel/extinction.py` (`specific_attenuation_at_altitude_db_per_km`).
- **Extiende** al [ADR 0021](0021-horizontal-path.md) (la física del camino ya
  existía; lo que faltaba era el escenario), al
  [ADR 0011](0011-the-block-is-the-pass.md) (el bloque, en el caso que su
  argumento no cubre), al [ADR 0014](0014-scenario-contract-and-provenance.md)
  (el contrato) y al [ADR 0023](0023-traceable-extinction.md) (la extinción, un
  paso de integración antes).

---

## Contexto

### Qué había, y por qué no bastaba

Desde el ADR 0021 `channel/horizontal.py` sabe calcular el presupuesto y el QBER
de un camino horizontal: longitud, `C_n^2` constante, onda declarada, aperturas,
jitter, extinción. Está medido contra la Tabla 4 de la ITU-R P.1814 y contra dos
fuentes cruzadas, y con él se dimensionó GE-1 en `notes/LAST_CHANGES.md` §36 y
§37.

**Y era una biblioteca suelta.** Nadie en `scenario/`, `engine/` ni `system/` la
importaba. Las consecuencias, en orden de gravedad:

1. **Un experimento no se podía dimensionar desde un fichero.** Todas las cifras
   publicadas de GE-1 salen de llamadas a mano dentro de un test. Cambiar la
   lente significa editar Python.
2. **No había procedencia ni hash.** El SHA-256 de `scenario/hash.py` es lo que
   ata una figura a sus entradas; un cálculo hecho a mano no tiene ninguno. Es
   exactamente el problema que `notes/LAST_CHANGES.md` §39 arregló para el
   régimen de escintilación en la bajada, y por la misma razón: dos
   dimensionados que difieren en algo que no está en el hash son dos físicas
   distintas bajo una sola identidad.
3. **No se podía exportar.** `io/export.py` escribe un `SimulationResult`.
4. **No se podía barrer.** `engine/sweep.py` toma un `Scenario`.

### La pregunta que este ADR contesta

No es «¿cómo se mete el camino horizontal en el motor?». Es **«¿es el camino
horizontal el mismo experimento con unos campos a cero, o es otro
experimento?»**, y de esa respuesta salen las tres decisiones de abajo.

---

## Decisión

### 1. El escenario es una **unión discriminada** por un campo `link`

```yaml
link: downlink      # orbit, stations, passes, time…
link: horizontal    # path, session…
```

`AnyScenario = Annotated[Scenario | HorizontalScenario, Field(discriminator="link")]`,
y `scenario/io.py` valida contra la unión.

**Por qué una unión y no campos opcionales.** La alternativa obvia —un solo
`Scenario` con `orbit`, `stations` y `passes` opcionales— hace que la pregunta
«¿este escenario tiene elevación?» se conteste mirando qué campos vinieron a
`None`, que es precisamente lo que el ADR 0021 asertaba **por ausencia** en las
firmas de física. Con la unión, la ausencia es del tipo: `HorizontalScenario` no
tiene `passes`, y como `SpecModel` lleva `extra="forbid"`, escribir `passes:` en
un fichero horizontal es un error de validación **que nombra el campo**, sin que
nadie tenga que escribir ni mantener una regla.

Dicho con número: la regla del ADR 0021 «ninguna firma acepta elevación» estaba
asertada por un test que recorre el AST del módulo. Ahora está asertada además
por el esquema, y en un sitio donde no hace falta recordar comprobarla.

**Por qué discriminada y no una unión a secas.** Sin discriminador, Pydantic
prueba los dos miembros y, si ninguno valida, informa de los errores de los dos:
un fichero de bajada con un campo mal escrito se rechazaría con quejas sobre
`path`, `session` y `link` además de la suya, y el usuario tendría que averiguar
qué mitad del mensaje habla de su fichero. Con discriminador, `link` elige
primero y los errores son los de ese miembro. El precio es que el tag tiene que
estar presente en el fichero; `scenario/io.py` convierte su ausencia en un
mensaje que nombra los dos valores en vez de en la queja interna de Pydantic
(«Unable to extract tag using discriminator 'link'»).

**El defecto del tag, que sí es defendible.** `Scenario.link` tiene defecto
`downlink` y `HorizontalScenario.link` no tiene ninguno. No es una asimetría
descuidada: el de `Scenario` es un `Literal` con **un solo valor legal**, así que
no hay alternativa que pueda esconder — un defecto solo es peligroso cuando
alguien podría haber elegido otra cosa. Eso es exactamente lo contrario de
`ChannelSpec.scintillation_regime`, que tenía dos valores legales y pierde su
defecto en esta misma PR (anexo del [ADR 0022](0022-the-strong-regime.md)). Los
cinco `scenarios/*.yaml` de bajada escriben el tag igualmente.

**Coste, medido:** el digest de referencia se repincha de `303a3729…` a
`17f44003…`. Es un **caso 2** del `DIGEST_HISTORY` de
`tests/scenario/test_hash.py` —la forma canónica gana la clave
`"link":"downlink"` y nada más—, `SCHEMA_VERSION` sigue en 1, y el test lo
demuestra borrando ese campo y recuperando el digest anterior hasta el último
dígito.

### 2. El bloque finite-key es la **sesión de medida declarada**, y eso cambia de quién es la responsabilidad

El [ADR 0011](0011-the-block-is-the-pass.md) decidió que el bloque sobre el que
se evalúa la cota de Lim et al. es **un pase**. El argumento no era de
conveniencia: era que **la geometría lo fija**. Entre dos pases el satélite está
bajo el horizonte y no se emite ni un pulso, así que un pase no es una elección
que alguien haga, es donde los datos se acaban. Por eso el ADR 0011 pudo además
hacer imposible la alternativa: `pass_key_volume` no tiene argumento `regime` y
no existe ninguna función que agrupe los cuatro pases de un día en un bloque.

**Un enlace horizontal es estacionario.** Nada para los datos. El haz sigue
cruzando el mismo aire a la misma potencia el minuto siguiente y el siguiente. El
bloque es, literalmente, lo que el operador decida llamar bloque.

Escribir eso como un campo obligatorio —`session.duration_s`, sin defecto— es
fácil. Lo que hay que decir entero, porque es lo que de verdad cambia, es **qué
significa escribirlo**:

- En la bajada, **el esquema puede impedir que alguien se equivoque**. No hay
  forma de pedirle al motor un bloque de dos pases.
- Aquí **no puede**. Un `duration_s` de 600 s sobre un enlace que estuvo estable
  sesenta segundos produce un número de bits perfectamente plausible, mayor, y
  **falso como afirmación de seguridad**: la cota supone que todas las cuentas
  del bloque salieron del mismo experimento en las condiciones con que se tasó.

Así que la responsabilidad se muda del esquema a la persona, y lo único que el
código puede hacer es no dejar que se mude en silencio. Hace tres cosas:

1. El campo es **obligatorio y sin defecto**, como `minimum_elevation_deg` y
   `zenith_transmittance`, y por la misma regla del ADR 0014.
2. Entra en el **hash**, así que dos longitudes de bloque son dos escenarios y no
   pueden compartir entrada de caché.
3. Cada ejecución registra un `INFO`
   `horizontal.block-is-the-declared-session` que dice la duración, el número de
   pulsos y **que nada en la geometría la fija**. Un resultado no viaja nunca sin
   esa frase.

**Y lo que vale un bloque está medido**, que es lo que impide leer el párrafo
anterior como una formalidad. En GE-1 —con los 0.2 dB/km que el ADR 0021 supuso a
mano, para que estas filas se comparen con sus tablas—, mismo enlace, solo la
sesión:

| sesión | bits certificados | bit/s |
|---|---|---|
| 15 s | 3 115 905 | 207 727 |
| 30 s | 7 027 898 | 234 263 |
| 60 s | 15 205 091 | **253 418** |
| 120 s | 32 059 995 | 267 167 |

Doblar el bloque compra **2.164 veces** la clave, no dos. Dos efectos: el peaje
fijo de la Ec. (1) de Lim et al. (260 bits a `eps = 1e-10`, cobrado una vez por
bloque) y, mucho más grande, las desviaciones de Hoeffding y de muestreo
aleatorio, que crecen como la raíz del bloque y por tanto pesan como uno partido
por esa raíz. Leído al revés: **una sesión declarada más larga de lo que el
enlace estuvo estable compra exactamente ese 16 % de clave que nadie ganó.**
(`tests/e2e/test_horizontal_scenario.py::TestTheBlockIsTheDeclaredSession`.)

### 3. El resultado es un contenedor propio, `HorizontalResult`

No un `SimulationResult` con las etapas orbitales vacías. Las dos formas de
vaciarlo son peores que un tipo nuevo, y la segunda no es una cuestión de gusto:

- **`None` donde hoy hay arrays.** `passes.finite_bits` está tipado `FloatArray`
  y todos sus consumidores —`io/export.py`, `viz/plots.py`, el resolvedor de
  métricas de `engine/sweep.py`— lo indexan sin preguntar. Hacerlo opcional mete
  un `if` en cada uno, y el `if` que a alguien se le olvide es un
  `AttributeError` dentro de una rutina de dibujo, que es el **buen** caso.
- **Arrays de longitud cero.** Pasan el tipado y son peores. Una suma sobre un
  eje vacío es `0.0`, así que `daily.finite_bits.sum()` reportaría **un enlace
  horizontal que certificó 15.2 Mbit como cero bits al día**, sin error en
  ninguna parte y sin que ningún consumidor pudiera distinguirlo de un enlace
  que no cerró. Es el modo de fallo «plausible y equivocado» que el README
  prohíbe, y es la razón decisiva.

Lo que los dos resultados **sí** comparten son los cuatro campos que hablan de la
ejecución y no de la geometría —`scenario`, `provenance`, `warnings`,
`timings`—, con los mismos nombres y tipos, así que cualquier cosa que lea solo
esos (la caché, el impresor de avisos del CLI, un chequeo de procedencia)
funciona con los dos sin saber cuál tiene.

`AnyResult = SimulationResult | HorizontalResult` es una unión y **no una clase
base**: una base con cuatro campos invitaría a escribir contra ella y a alcanzar
`passes` detrás de un `isinstance`. La unión obliga a estrechar en el único sitio
donde importa, y el verificador de tipos lo exige.

**Y las etapas ausentes están ausentes, no a cero.** `HORIZONTAL_STAGES` es
`("channel", "key", "result")`: tres, contra las siete de la bajada. Las cuatro
que faltan —`orbit`, `geometry`, `passes`, `series`— no aparecen con 0.0
segundos, porque una etapa que dice tardar cero se lee como una que corrió
deprisa.

### 4. La extinción reutiliza `ExtinctionSpec`, un paso de integración antes

`horizontal_loss_budget` pide `extinction_db_per_km`. El escenario horizontal lo
declara de **las mismas dos formas excluyentes** que `ChannelSpec`: el número en
dB/km, o un `ExtinctionSpec`. Ninguna tercera, ninguna de las dos por defecto, y
un enlace por aire perfectamente limpio escribe `extinction_db_per_km: 0.0` y lo
ha dicho (hueco 14 del [ADR 0009](0009-citation-policy.md)).

**Lo único que cambia es a qué se evalúa el modelo, y es un paso de integración.**
`ExtinctionSpec` sigue siendo **un solo tipo** con los mismos cuatro campos. La
bajada necesita una *transmitancia vertical*: la columna entera sobre la
estación, un número adimensional, que es lo que integra
`zenith_transmittance_from_visibility`. El horizontal **no tiene columna**:
necesita el *coeficiente de extinción a su propia altura*, una pérdida por
kilómetro. Las dos leen el mismo perfil `β(h) = β_v exp(-(h - h_v)/H)`; la
vertical lo integra desde la estación hacia arriba, la horizontal lo **evalúa** en
`h` y para. `channel/extinction.py` gana
`specific_attenuation_at_altitude_db_per_km` para eso, y las dos comparten el
factor exponencial en una función privada para que no puedan discrepar sobre
hacia dónde apunta el exponente.

**El campo que el cenital no tiene, y su defensa.** `HorizontalPathSpec.altitude_m`:
la altura a la que corre el enlace. En la bajada esa altura es la de la estación
y ya está declarada; aquí no hay estación. Entra **solo** por
`exp(-(altitude_m - visibility_altitude_m)/H)`, así que en el caso ordinario —la
visibilidad medida donde corre el enlace— **se cancela exactamente** y la altura
de escala del hueco 22 no influye en ningún número. Sigue siendo obligatorio por
la misma razón que `visibility_altitude_m`: nada en una cifra de visibilidad dice
a qué altura se tomó, y leer una climatológica de nivel del mar en una meseta de
2 km es otra atmósfera por un factor 5.3.

**Y el hueco 23 sigue abierto y sigue diciéndose.** El modelo es dispersión por
aerosol; la absorción molecular no tiene cifra en ninguna fuente abierta, y eso
está en el docstring del módulo que el horizontal llama, igual que en el cenital.
No se tapa con la dispersión.

### 5. Lo que el motor horizontal **no** hace, y por qué eso es el esquema y no un `if`

No hay Monte Carlo, ni pCFLOS, ni multi-estación, ni relé. **`HorizontalScenario`
no tiene dónde pedirlos**, así que la ausencia es visible en el esquema en vez de
ser una etapa que el motor se salta. En concreto el Monte Carlo no es «lo mismo
con otra semilla»: `system/monte_carlo.py` sortea el desvanecimiento de un
**pase**, con tiempos de correlación contra una geometría que cambia; la
estadística de un enlace estacionario durante una sesión es otra pregunta y no
tiene módulo todavía.

Tampoco se cachea. `engine/cache.py` guarda los arrays de un `SimulationResult`
en `.npz` y un `HorizontalResult` no tiene ninguno; además una corrida horizontal
son milisegundos, contra el Monte Carlo de un día para el que la caché existe.
Pasar una caché con un escenario horizontal **registra un `INFO`
`engine.horizontal-is-not-cached`** y corre, en vez de ignorarla.

---

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Campos opcionales en un solo `Scenario`** | La pregunta «¿tiene elevación?» pasa a contestarse mirando qué vino a `None`. La unión la contesta el tipo, y `extra="forbid"` rechaza `passes:` por su nombre |
| **Unión sin discriminador** | Un fichero de bajada con un campo malo se rechaza con los errores de los dos miembros, y el usuario tiene que separar cuál es el suyo |
| **`link` obligatorio también en `Scenario`** | Rompería cada construcción `Scenario(...)` de la suite por un tag con un solo valor legal. El defecto es defendible precisamente porque no esconde ninguna alternativa |
| **`SimulationResult` con arrays de longitud cero** | `daily.finite_bits.sum()` daría **0.0 bits/día** para un enlace que certifica 15.2 Mbit, sin error en ninguna parte |
| **`SimulationResult` con `None` en las etapas orbitales** | Un `if` en cada consumidor, y el que se olvide es un `AttributeError` dentro de una rutina de dibujo |
| **Una clase base común a los dos resultados** | Cuatro campos compartidos invitan a escribir contra la base y alcanzar `passes` detrás de un `isinstance`. La unión obliga a estrechar donde importa |
| **Un `ExtinctionSpec` horizontal aparte** | Dos tipos para un modelo, con dos sitios donde escribir una altura de escala y dos sitios donde discrepar. Lo que difiere es un paso de integración, no el modelo |
| **Un bloque por defecto (60 s, un minuto «razonable»)** | Es la afirmación de seguridad entera puesta por descuido. Vale 2.16 veces la clave entre 30 y 60 s, medido arriba |
| **Reutilizar `find_passes` con un «pase» de toda la sesión** | Fabricaría una tabla de pases con una elevación que no existe, y el resultado llevaría campos —culminación, Doppler, excursión— que no significan nada. Un `PassTable` de un enlace sin geometría es una mentira con forma de dato |
| **Cachear los resultados horizontales** | La caché guarda `.npz`; este resultado son unas decenas de floats y se recalcula en milisegundos. Se dice, no se ignora |

---

## Consecuencias

### Lo que cierra

- **Dimensionar GE-0b y GE-1 desde un fichero**, con hash, procedencia y
  exportación, y barrerlos con `engine/sweep.py` como cualquier otro escenario.
  Las tablas medidas a mano en `notes/LAST_CHANGES.md` §36 y §37 —el factor 11.2
  de la lente, la curva de 200 m a 5 km— las reproduce ahora `run()` a través de
  `SweepSpec`, bit a bit contra la cadena a mano
  (`tests/e2e/test_horizontal_scenario.py`).
- **La regla del ADR 0021 asertada dos veces**: por ausencia en las firmas y por
  el esquema.
- **Una figura**, `viz.plots.horizontal_key_against_distance`, con el intervalo
  onda-plana-a-esférica como banda y los dos avisos de lectura marcados.

### Lo que esto destapa, y es lo más interesante que ha salido de la PR

**A 5 km GE-1 no certifica nada, mientras el asintótico sigue reclamando
4.0–4.4 kbit/s.** Con 60 s de sesión y el resto de GE-1 igual, la clave
certificada a 4 km es 672–843 bit/s y a 5 km es **exactamente cero**. Es el
acantilado del ADR 0011 —una división por cero en la tasa de error de fase, no un
factor— aparecido por primera vez en un enlace de tierra, y es justo el régimen
en el que un dimensionado que citara la cifra asintótica diría que el enlace
funciona. El resultado lo dice: `horizontal.session-without-key` lleva la cifra
asintótica al lado, para que la comparación esté en el log y no en la cabeza de
quien lo lea.

### Y una segunda cosa que destapa, sobre el banco

**GE-0b iguala la varianza de Rytov de GE-1 y no iguala lo que ve su receptor.**
El `C_n^2` de `equivalent_bench_cn2_m23` hace que las dos varianzas de Rytov
coincidan a precisión de máquina, 0.198845 las dos. Pero esa es la varianza de un
detector puntual; la que llega a la clave es la promediada por la apertura, y el
promediado depende de **a qué distancia** está la turbulencia:

| enlace | `σ_R²` | promediado `A` | margen al 1 % |
|---|---|---|---|
| GE-1, 1 km | 0.198845 | 0.2386 | **1.446 dB** |
| GE-0b, 2 m | 0.198845 | 4.45e-5 | **0.030 dB** |

**2 183 veces menos varianza en el receptor, 1.42 dB menos de margen.** Es la
segunda mitad del hueco 20, y a diferencia de la primera —el argumento de las
pantallas de fase, que queda fuera de lo que QuOSS modela— esta se puede medir
dentro del modelo, y está medida. No hace inútil el banco: hace que la pregunta
que contesta sea otra.

### Lo que no cierra

- **La onda gaussiana** (hueco 18) sigue abierta, y el escenario no la puede
  cerrar: lo que hace es obligar a declarar cuál de las dos idealizaciones se usa
  y avisar cuando contradice el rango de Rayleigh.
- **El retrorreflector** (hueco 19): ver el [ADR 0025](0025-two-terminals-one-way.md).
- **La absorción molecular** (hueco 23) y **la altura de escala** (hueco 22),
  heredados del ADR 0023 sin cambio.
- **El hueco 20** (los emuladores): `scenarios/ge0b_bench.yaml` lo lleva escrito
  en el fichero, que es donde lo lee quien va a comprar algo.
- **La dispersión entre sesiones.** No hay Monte Carlo horizontal. Estas cifras
  son la sesión típica, sin P5/P95, y la reserva es la misma que el ADR 0011
  traslada desde `link_budget.py`.

---

## Referencias

- [ADR 0011](0011-the-block-is-the-pass.md) — el bloque es el pase, y el caso que
  su argumento no cubre.
- [ADR 0014](0014-scenario-contract-and-provenance.md) — el contrato del
  escenario y la regla sobre los defectos invisibles.
- [ADR 0021](0021-horizontal-path.md) — la física del camino horizontal.
- [ADR 0022](0022-the-strong-regime.md), anexo — por qué
  `scintillation_regime` pierde su defecto en el esquema y lo conserva en las
  siete firmas de física.
- [ADR 0023](0023-traceable-extinction.md) — la extinción con modelo, de la que
  esta usa el paso anterior a la integral.
- [ADR 0025](0025-two-terminals-one-way.md) — por qué GE-1 son dos terminales.
- C. C. W. Lim et al., *Phys. Rev. A* **89**, 022307 (2014), Ec. (1): la cota que
  se evalúa sobre el bloque que este ADR define.

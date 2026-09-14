# ADR 0016 — El motor no añade nada, y la altitud de una estación significa una sola cosa

- **Estado:** aceptada
- **Fecha:** 2026-09-14
- **Etapa:** 6 (`engine/`), cerrada hacia atrás: el módulo existía y la prueba que
  lo justificaba, no.
- **Afecta a:** `engine/pipeline.py`, `scenario/models.py` y `scenario/defaults.py`
  (el campo `altitude_m`), `channel/atmosphere.py` y los tres módulos que le pasan
  `station_height_m`, `tests/e2e/` y `tests/system/reference.py`.
- **Extiende** al [ADR 0014](0014-scenario-contract-and-provenance.md) —el escenario
  es un dato, y un dato tiene un significado por campo— y al
  [ADR 0009](0009-citation-policy.md), porque la mitad de esta decisión se resuelve
  abriendo la recomendación y leyendo una frase, no eligiendo la lectura más cómoda.

---

## Contexto

### Qué es el motor y qué afirma, para quien llegue nuevo

`quoss.engine.pipeline.run` toma un **escenario** —la descripción completa y
validada de una simulación, normalmente leída de un YAML— y devuelve un
**resultado**. Por el camino llama, en orden, a las funciones de física que hay
debajo: propagar la órbita, calcular ángulos de visión, segmentar pases, evaluar
el presupuesto de enlace y el de ruido, aplicar el protocolo, integrar sobre el
pase y sobre el día.

Su afirmación es **negativa**, y conviene leerla despacio: *el motor no calcula
nada que no calcularía una persona llamando a esas funciones a mano*. No es una
afirmación sobre la física —de si el número es correcto se ocupan los niveles V2
y V3 de [`tests/golden/README.md`](../../tests/golden/README.md)—, es una
afirmación sobre la **orquestación**: que mover un número de una función a un
contenedor no lo cambia.

### Por qué esa afirmación necesita una prueba y no un docstring

Porque un orquestador es exactamente el sitio donde un número cambia sin que
nada parezca mal. Un `keyword` olvidado, un defecto distinto del que el llamante
habría escrito, una magnitud recalculada en vez de reutilizada: cada uno de
ellos produce un resultado que **sigue teniendo el tamaño correcto**. No hay
excepción, no hay `NaN`, no hay aviso. El README lo llama «prohibido degradar en
silencio»; esta es la forma de degradación silenciosa que le toca a `engine/`.

`src/quoss/engine/__init__.py` afirmaba desde su primera línea que
`tests/e2e/test_reference_scenarios.py` probaba eso **bit a bit**. Ese fichero
no existía. `tests/e2e/` tenía solo `__init__.py` y `oracle.py` —la cadena
cableada a mano, escrita y sin usar—, de modo que la afirmación más fuerte del
paquete era la única sin comprobar.

### Y el síntoma que lo delató: dos números para el mismo día

El día de referencia (Castelldefels, 0.75 m, SSO a 700 km, noche clara, máscara
de 10°, 2025-01-01) tenía dos cifras de clave finita en el árbol a la vez:

- **432 985 bits**, que es la que citan el README, el
  [ADR 0011](0011-the-block-is-the-pass.md), `notes/LAST_CHANGES.md` y los
  docstrings de `system/`, medida por `tests/system/`.
- **433 442 bits**, que es la que devuelve `run(reference_castelldefels())`.

457 bits, el **0.106 %**. Un 0.1 % es justo del tamaño que no llama la atención,
y esa es la razón por la que había que perseguirlo: o una de las dos cifras
estaba mal, o los dos caminos calculaban cosas distintas, y ninguna de las dos
posibilidades puede quedar sin nombre en un proyecto cuyo modo de fallo
característico es «un número plausible y equivocado».

---

## Decisión

**Se escribe `tests/e2e/test_reference_scenarios.py`, que compara el resultado
del motor con la cadena de `tests/e2e/oracle.py` por igualdad exacta de coma
flotante. Y se decide, con la recomendación abierta, que `StationSpec.altitude_m`
significa una sola cosa —la altitud de la estación sobre el nivel del mar— que es
a la vez dónde está la estación para la geometría y dónde empieza la integral de
turbulencia. La cifra del día de referencia que va al paper es la del motor,
433 442 bits.**

### 1. Igualdad exacta, no `approx`, y por qué es una clase distinta de test

Un test de física compara **dos cálculos** de la misma magnitud —una forma
cerrada contra una integral numérica, por ejemplo— y esos dos legítimamente
difieren en los últimos dígitos; por eso necesita una tolerancia derivada del
tamaño del efecto.

Este fichero compara **el mismo cálculo alcanzado por dos rutas**. La misma
función, con los mismos argumentos, en el mismo orden, devuelve los mismos
`double` de IEEE-754: la coma flotante es determinista. Si el número del motor
difiere del de la cadena a mano en una unidad del último lugar, las dos rutas
**no son el mismo cálculo**, y una tolerancia escondería exactamente la
diferencia que el fichero existe para encontrar.

En el lenguaje de `tests/golden/README.md` esto es un **puente V4**: demuestra
que la orquestación es fiel y no dice nada sobre si la física es correcta.

### 2. Los 457 bits son un término, y se prueban reproduciendo **las dos** cifras

`oracle.py` estaba escrito con un solo parámetro que los constructores originales
no tienen: `station_height_m`. Con él se reproducen, **a la última cifra
significativa**, las dos columnas:

| `station_height_m` | Por pase | Día finito | Día asintótico |
|---|---|---|---|
| 0 m | 190 581, 0, 242 404, 0 | **432 985** | 3 776 680.752646787 |
| 30 m | 190 807, 0, 242 635, 0 | **433 442** | 3 779 461.558061474 |

y la segunda fila es, campo por campo, lo que devuelve el motor: la tabla de
pases con sus bordes refinados fuera de la rejilla, los nueve términos del
presupuesto de pérdidas, las ocho columnas de la cota finita, las series y el día.

Como las dos filas salen de **la misma cadena con un solo argumento distinto**,
la diferencia queda atribuida a ese término y a ningún otro. Y el test lo cierra
por los dos lados: los dos enlaces ven **los mismos pases** (misma tabla, mismos
ángulos —`station_height_m` no es la posición de la estación, que es
`station_altitude_km` y vale 30 m en los dos casos—), y de los nueve términos del
presupuesto solo se mueve el de **centelleo**, como mucho 0.0185 dB.

Así que ninguna de las dos cifras está mal en aritmética. Son **dos enlaces
distintos**: uno integra la turbulencia desde el nivel del mar y el otro desde
los 30 m a los que está la estación.

### 3. Cuál va al paper: la del motor

Porque en un escenario `altitude_m` es **un** campo y no puede significar dos
cosas. El esquema ya lo dice en la descripción del propio campo («Height above
the WGS-84 ellipsoid, metres. Also the station height the turbulence profile
starts from»), el motor lo cablea, y **ignorarlo para cuadrar con la cifra
anterior sería degradar en silencio una entrada del usuario**.

`tests/system/reference.py` no está mal: es un *fixture*, no un escenario, y su
`conditions_at` nunca prometió pasar la altura. Lo que estaba mal eran dos
afirmaciones escritas encima de él, y las dos se corrigen aquí:

- `scenarios/reference_castelldefels.yaml` decía que el fichero «convierte en
  exactamente las entradas de física de `tests/system/reference.py`».
- El docstring de `reference_castelldefels()` decía que
  `tests/scenario/test_defaults.py::TestReferenceCastelldefels` «aserta que la
  conversión reproduce **todas** las entradas de física» de ese módulo — cuando
  ese test ya pasaba `station_height_m=30.0` a mano por el lado cableado, es
  decir, ya sabía de la diferencia y no la decía.

### 4. Lo que el término vale, que es lo que un 0.106 % hace fácil de despreciar

A 30 m sobre el mar el término es un redondeo. No lo es en ningún sitio donde se
ponga de verdad un telescopio. Mismo satélite, mismo día, mismo receptor, misma
máscara; solo cambia la estación y por tanto desde dónde empieza la integral:

| Estación | Altitud | Turbulencia desde 0 m | Desde su altitud | Cambio | Razón de `C_n²` integrado |
|---|---|---|---|---|---|
| Castelldefels | 30 m | 432 985 bits | 433 442 bits | **+0.106 %** | 1.26 |
| Calar Alto | 2 168 m | 56 925 bits | 77 244 bits | **+35.7 %** | 9.82 |
| OGS del Teide | 2 400 m | 562 697 bits | 587 863 bits | **+4.5 %** | 10.46 |

Y en el segundo pase vivo de Calar Alto, **9 817 bits contra 19 724**: el término
lo **duplica**. El mecanismo es la forma de la atmósfera y no nada del código: el
término de superficie de la Ec. (6) de la ITU-R P.1621-2 tiene una altura de
escala de 100 m, así que casi toda la turbulencia está en el primer kilómetro y
un telescopio a 2 168 m tiene un orden de magnitud menos encima. Es por lo que
los observatorios están en montañas, dicho como número.

Esto importa para lo que viene: las estaciones del enlace de CLAU son el
Observatori del Montsec y la OGS del Teide, no una estación a nivel del mar.

### 5. La lectura de la altura: resuelta abriendo el documento, no eligiendo

El punto 3 solo vale si `station_height_m` es de verdad **la altitud del sitio
sobre el nivel del mar** y no la altura del telescopio sobre el suelo que pisa.
La diferencia no es semántica: bajo la segunda lectura, una estación en una
montaña está a unos pocos metros sobre *su* suelo y se le aplica la capa límite
entera — es decir, exactamente el 35.7 % de Calar Alto, al revés.

Y el proyecto tenía las dos lecturas escritas a la vez: `channel/atmosphere.py`
documentaba el parámetro como «height above ground level» en dieciséis sitios,
mientras `scenario/models.py` le metía la altura sobre el elipsoide.

La recomendación usa **los dos nombres para el mismo símbolo**, y es ella misma
la que desempata. Define `h0` como «height of the earth station above
ground-level (m)» (§5.1.2, junto a las Ecs. (8b) y (9)), y tres párrafos después,
en la frase que sigue a la Ec. (13) (§5.1.2, p. 11), escribe:

> «The above formula has been derived as an approximation for an **earth station
> altitude between 0 km and 5 km above sea level** and an elevation angle above
> 45°.»

Un rango de 0 a 5 km es un rango de **sitios**, no de mástiles: ningún telescopio
está a 5 km sobre su propio suelo. Así que «ground-level» en la P.1621-2 es «el
suelo, o sea el datum de nivel del mar desde el que se ancla el perfil», y `h0`
es la altitud del emplazamiento. Es la lectura que el motor ya aplicaba; ahora
está escrita con su cita en el docstring del módulo, y los quince parámetros que
la repetían dicen «above mean sea level».

Verificado abriendo el PDF
(`R-REC-P.1621-2-201507-I!!PDF-E.pdf`, el 2026-09-14), como exige el ADR 0009.
**No es un hueco nuevo**: es una ambigüedad de la fuente que la fuente cierra, y
lo que se registra es dónde.

### 6. La única cosa que no es una copia, y es una forma

De todos los arrays comparados, uno difiere entre motor y cadena a mano: el
término de **afterpulsing** del presupuesto de ruido. `_channel` le pasa a
`downlink_noise_budget` un `signal_counts_per_gate` —la señal media detectada por
puerta, que un afterpulse necesita porque un afterpulse sigue a un clic— y la
cadena a mano no.

Con el receptor de referencia (`afterpulse_probability = 0`, «no after-pulsing
effect», Ntanos et al. §4.1) el término es **exactamente cero** por los dos
caminos, así que los dos coinciden en todos los números. En lo que no coinciden
es en que el cero del motor es un array de 1 800 ceros y el de la cadena a mano
es un escalar; y la diferencia desaparece en `LinkConditions`, que los difunde
contra la transmitancia, que es la única forma que el protocolo llega a ver.

Se **aserta** en vez de suavizarse, porque es la forma de un acoplamiento real:
el día que un escenario declare un afterpulsing distinto de cero, el ruido del
motor deja de ser constante a lo largo del pase y la cadena a mano estaría mal.
La identidad se cumple **porque** el término es cero, no porque las dos llamadas
sean la misma llamada.

### 7. Qué policía qué, que no es obvio en la etapa Monte Carlo

Al comprobar que el test muerde —mutando el cableado del motor y viendo qué
falla— apareció algo que merece quedar escrito: mutar `station_height_m` en
`_channel` rompe doce tests y **no** rompe el del conjunto Monte Carlo. No es un
agujero: es que el Monte Carlo **quita** la reserva de desvanecimiento
determinista y vuelve a sortearla, así que el término de `fade_db` se cancela
allí y lo que queda es la **varianza**. El test del conjunto vigila el cableado
de la varianza; el del presupuesto vigila el del desvanecimiento. Mutar la
varianza sí rompe el del conjunto, comprobado.

---

## Consecuencias

### Lo que esto cierra

- La afirmación de `engine/__init__.py` y de `engine/pipeline.py` pasa a ser
  comprobable y comprobada, en 30 tests y 1.5 s.
- Las dos cifras del día de referencia dejan de estar en competencia: **433 442**
  es la del escenario y la que se reporta; **432 985** es la del *fixture* de la
  etapa 3, y las dos están reproducidas y explicadas en el mismo fichero.
- Las etapas opcionales —conjunto Monte Carlo, agregación multi-estación y relé
  de nodo confiable— quedan cubiertas por el mismo puente, que es donde un
  orquestador tiene más sitio para equivocarse: las tres toman *varias* entradas
  y devuelven una respuesta, así que un orden mal puesto seguiría dando un número
  del tamaño correcto.

### Lo que no cierra

- **Las cifras de la etapa 3 no se re-miden.** El *fixture* sigue integrando
  desde el nivel del mar y el ADR 0011 sigue citando 432 985. Rehacerlo movería
  unas cincuenta citas en docstrings, ADRs y notas por un 0.1 %, con el riesgo
  que este proyecto ya conoce de una cifra citada en quince sitios; y las
  conclusiones cualitativas de esa etapa —el óptimo interior de la máscara cerca
  de 8°, el 11.5 %, los dos pases en cero— no se mueven. Lo que sí se hace es que
  ninguno de los dos sitios afirme ser el otro.
- **La Ec. (11) de Ntanos et al.** —el perfil HV modificado con la altitud de la
  estación— sigue sin implementarse: lo que hay es la Ec. (6) de la ITU-R con el
  integral truncado por abajo. Son dos modelos distintos del mismo efecto y solo
  uno está escrito. El roadmap lo listaba como fuente de la etapa 2.2; queda
  anotado aquí porque es donde se vio.
- **El puente es V4 y no valida nada de la física.** Que el motor y la mano
  coincidan no dice que 433 442 sea el número correcto de bits: dice que el
  motor no lo estropea.

### Numeración de ADRs, reconciliada aquí porque bloqueaba

`src/quoss/viz/plots.py` citaba `docs/adr/0017-publication-figures.md` y
`src/quoss/validation/__init__.py` citaba
`docs/adr/0018-validation-is-a-table-not-a-badge.md`; ninguno de los dos existía,
y `docs/adr/` llegaba al 0015. El **0016 no estaba citado por nadie**, así que
esta decisión —la de la etapa 6, que es la que faltaba— lo ocupa, y el 0017 y el
0018 quedan **reservados** a sus etapas (7, `viz/`, y 8, `validation/`) en
`notes/ROADMAP.md`. Las dos citas colgantes se marcan como pendientes en el
propio código, porque citar un fichero que no existe es la misma clase de
afirmación sin cumplir que este ADR corrige.

---

## Alternativas descartadas

- **Cablear `station_height_m = 0.0` en el motor para cuadrar con 432 985.**
  Degradación silenciosa de una entrada del usuario, y en el Teide costaría el
  4.5 % de la clave y en Calar Alto el 26 % (`77 244 → 56 925`). Se descarta por
  la regla, no por el tamaño.
- **Cambiar `tests/system/reference.py` para que pase la altura y re-medir la
  etapa 3.** Es la solución que deja un solo enlace, y es la que se hará el día
  que haya otra razón para tocar esas cifras. Hoy movería ~50 citas por un 0.1 %
  sin cambiar ninguna conclusión.
- **Comparar con `pytest.approx` y una tolerancia holgada.** Haría pasar el test
  precisamente en el caso que existe para detectar; ver el punto 1.
- **Dejar la lectura de la altura como hueco declarado del ADR 0009.** Era la
  salida honesta si el documento no la resolviera. Lo resuelve, en una frase, y
  declarar un hueco que la fuente cierra es tan falso como rellenar uno que no.

---

## Verificación

`tests/e2e/test_reference_scenarios.py`: **30 tests, 1.5 s**, sin marca `slow`.
`ruff check`, `ruff format --check` y `mypy` limpios. Cobertura de los módulos
tocados, con ramas: `channel/atmosphere.py`, `channel/turbulence.py`,
`channel/beam.py`, `channel/link_budget.py` y los cinco de `engine/` al **100 %**
— los cambios de esta entrada en `channel/` son solo de docstring y no mueven
ninguna línea ejecutable. Suite completa: **3 259 tests** (eran 3 229).

Que el test muerde está comprobado por mutación y no supuesto: poner
`station_height_m=0.0` en `_channel` hace fallar 12 de los 30; hacerlo en la
llamada de la varianza del Monte Carlo hace fallar el del conjunto (§7).

## Referencias

- Recomendación **ITU-R P.1621-2** (07/2015), §5.1.1 Ec. (6) y §5.1.2 Ecs.
  (8a)-(13) y la frase del rango de validez, p. 11.
- A. Ntanos et al., «LEO Satellites Constellation-to-Ground QKD Links: Greek
  Quantum Communication Infrastructure Paradigm», *Photonics* **8**(12):544,
  2021, §4.1 («no after-pulsing effect»).
- [ADR 0009](0009-citation-policy.md) huecos 14 y 15;
  [ADR 0011](0011-the-block-is-the-pass.md) §5;
  [ADR 0014](0014-scenario-contract-and-provenance.md).
- [`tests/golden/README.md`](../../tests/golden/README.md), niveles V1-V4.

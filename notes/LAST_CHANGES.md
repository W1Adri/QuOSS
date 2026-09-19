# QuOSS — Últimos cambios

> **Bitácora viva. Se actualiza al cerrar cada etapa del [`ROADMAP.md`](ROADMAP.md).**
> Última entrada: **§49, 2026-09-19** — la puerta de entrada, una versión que se
> puede citar, y la cuarta clase de cita rota, que no era una cita.
>
> **Qué hay aquí y qué no.** Este fichero guarda **las cinco últimas entradas
> completas**. Todo lo anterior está en [`archive/`](archive/), íntegro y sin
> editar, con una línea por entrada en el índice de abajo. Es un cambio de forma
> y no de contenido: no se ha borrado nada.
>
> **Por qué.** El fichero llegó a **6 834 líneas** y `CLAUDE.md` manda leerlo al
> empezar cada sesión. Una bitácora que no cabe en la sesión que la tiene que
> leer deja de ser una bitácora y pasa a ser un archivo — y el efecto real,
> observado, es que se leen las primeras pantallas y se saltan las entradas que
> describen el árbol de hoy. La regla del archivo y la comprobación que la
> respalda están en §41.
>
> **La regla, en una línea:** una entrada se archiva cuando **todo lo que carga
> peso en ella vive ya en un ADR, en un test o en un docstring**; si no, se
> migra primero. Y se aserta: `tests/unit/test_notes.py`.

---

## Índice de lo archivado (§1–§44)

| § | Fecha | La cifra o la regla que la resume | Dónde |
|---|---|---|---|
| §1 | 2026-07-31 | Estado al cerrar `orbits/` a medias: 2 237 tests, 99 % de cobertura, las 513 sentencias nuevas entraron cubiertas | [archivo](archive/LAST_CHANGES-01-12.md) |
| §2 | 2026-08-04 | **SimulCTTC deja de ser el oráculo.** Cuatro defectos suyos, entre ellos estaciones sobre una esfera con hasta ~21 km de error y una época que caía al reloj de pared | [archivo](archive/LAST_CHANGES-01-12.md) |
| §3 | 2026-08-04 | `calendar_to_jd` fallaba **±1 día** fuera de 1900-2100 (usaba la regla de bisiestos juliana). Y los 178 m contra astropy eran **DUT1, no movimiento polar**: rotando por GMST(UT1) caen a 14.4 m | [archivo](archive/LAST_CHANGES-01-12.md) |
| §4 | 2026-08-04 | **Errata de Vallado 4.ª ed.**: imprime `u = 145.60549°` donde el estado que publica da `145.720087°`. El hueco es de **0.1146°, 160 veces** el typo de `|r|` que lo acompaña | [archivo](archive/LAST_CHANGES-01-12.md) |
| §5 | 2026-08-04 | **Los términos seculares de 2.º orden se quedan fuera, por medición:** a `i = 98°` —la inclinación de este proyecto— empeoran el residuo de 1.0e-4 a **1.4e-3** | [archivo](archive/LAST_CHANGES-01-12.md) |
| §6 | 2026-08-04 | La bandera osculador/medio y sus tres subdecisiones → [ADR 0006](../docs/adr/0006-osculating-vs-mean-elements.md). El aviso que llevaba tres documentos escrito pasa a `DomainError`, en las **dos** direcciones | [archivo](archive/LAST_CHANGES-01-12.md) |
| §7 | 2026-08-04 | `propagator.py` → [ADR 0005](../docs/adr/0005-propagation.md). **Enum enviado incompleto a propósito:** un nombre ausente obliga a preguntar, uno presente y equivocado no obliga a nada | [archivo](archive/LAST_CHANGES-01-12.md) |
| §8 | 2026-08-04 | `perturbations.py` → [ADR 0004](../docs/adr/0004-zonal-perturbations.md). Una sola expresión de Legendre para toda la fuerza zonal; J3 no tiene término secular de primer orden, medido y no afirmado | [archivo](archive/LAST_CHANGES-01-12.md) |
| §9 | 2026-08-04 | `frames.py` → [ADR 0002](../docs/adr/0002-frames-and-time-scales.md). Un solo marco inercial (TEME) y un solo giro. Presupuesto medido: 14.4 m de movimiento polar, **274 m** de DUT1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §10 | 2026-08-04 | `kepler.py` → [ADR 0003](../docs/adr/0003-orbital-elements.md). Markley 1995 en forma cerrada, residuo **≤ 1.4e-15 rad** hasta `e = 0.9999`, y la función comprueba su propia post-condición | [archivo](archive/LAST_CHANGES-01-12.md) |
| §11 | 2026-08-04 | Inventario de ficheros de la etapa 2.1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §12 | 2026-08-04 | Entorno y versiones de la etapa 2.1 | [archivo](archive/LAST_CHANGES-01-12.md) |
| §13 | 2026-08-04 | «Cosas a considerar»: la tabla **Pendiente de decidir** y la **Deuda pequeña**. Lo que seguía vivo está hoy en [`ROADMAP.md` § Trabajo abierto](ROADMAP.md); lo cerrado, tachado allí | [archivo](archive/LAST_CHANGES-13-24.md) |
| §14 | 2026-08-04 | **Las siete entradas de la auditoría, cerradas el mismo día.** La grande no era una inconsistencia sino C1: los «219 km» citados en quince sitios **no se reproducían** — la cifra real es **5.9 veces mayor**, y no existe una cifra única | [archivo](archive/LAST_CHANGES-13-24.md) |
| §15 | 2026-09-10 | `tle.py` → [ADR 0007](../docs/adr/0007-tle-and-sgp4-propagation.md). SGP4 envuelto, no reimplementado; `parse_tle` caza un checksum corrupto y una entrada basura que `sgp4` deja pasar en silencio | [archivo](archive/LAST_CHANGES-13-24.md) |
| §16 | 2026-09-10 | **El ángulo de point-ahead lleva factor 2**, no el `v_perp/c` de una vía: **50.6 µrad** a 67.1° de elevación, contra los 35 µrad que el roadmap citaba antes de tener la cuenta hecha | [archivo](archive/LAST_CHANGES-13-24.md) |
| §17 | 2026-09-10 | `constellations.py` → [ADR 0008](../docs/adr/0008-constellation-design.md). Espaciado en anomalía **media**, con control negativo; el `rtol` de `brentq` pasa de literal a `4 * eps` con nombre | [archivo](archive/LAST_CHANGES-13-24.md) |
| §18 | 2026-09-10 | **La Ec. (5) de Ntanos et al. imprime `(8/w_0)²` donde cierra `8/w_0²`: 8 veces, 9.03 dB optimista.** Con sus propios parámetros devuelve una transmitancia de **1.36**, más luz recogida que transmitida | [archivo](archive/LAST_CHANGES-13-24.md) |
| §19 | 2026-09-10 | **El `A_0` de Farid & Hranilovic Ec. (9) *es* el acoplamiento geométrico de `beam.py`**, así que multiplicarlos como está publicado inventa **17.5 dB**. Y la pérdida media son 0.22 dB contra **1.03 dB** una vez de cada cien | [archivo](archive/LAST_CHANGES-13-24.md) |
| §20 | 2026-09-10 | **La Ec. (20) llama «probability» a un número esperado de cuentas que con la luz solar tabulada por la UIT vale 3.42.** El gating es el único parámetro libre del ruido: de 1 ns a 100 ps quita **10 dB de fondo por 0.08 dB de señal** | [archivo](archive/LAST_CHANGES-13-24.md) |
| §21 | 2026-09-10 | **Aplicar la cadena de eficiencia también a las cuentas oscuras esconde 0.94 dB de ruido.** Y el gating vale **10 dB con el nanohilo de Ntanos y 0.22 dB con el APD de Lim**: «estrecha la puerta» es condicional, y la condición es el detector | [archivo](archive/LAST_CHANGES-13-24.md) |
| §22 | 2026-09-12 | **Sumar el cuantil al 1 % de cada término no da un presupuesto al 1 %.** El cuantil conjunto exacto son **1.668 dB donde la suma publicada da 2.312**, y esa etiqueta «1 %» es en realidad **0.066 %**. Más el doble conteo del receptor: 12.71 dB en vez de 6.36 | [archivo](archive/LAST_CHANGES-13-24.md) |
| §23 | 2026-09-12 | `qkd/base.py`: la frontera canal↔protocolo. **Una media no es una probabilidad** — leer una por otra sobreestima **3.58 %** en el telescopio de 2.3 m | [archivo](archive/LAST_CHANGES-13-24.md) |
| §24 | 2026-09-12 | **La Ec. (10) de Ma et al. devuelve una ganancia mayor que uno por encima de 7.152 cuentas por puerta**, así que se usa la exacta. Y «4:1:16» contra «q = 2/5» en la misma frase de Ntanos discrepan por **4.2** | [archivo](archive/LAST_CHANGES-13-24.md) |
| §25 | 2026-09-12 | **La cota finite-key no es la asintótica por un factor:** 1.1387e-05 contra 6.0239e-05 bits por pulso, el **18.9 %**, y a 1e9 pulsos **nada**. La fuente es Lim et al. 2014, no Tomamichel | [archivo](archive/LAST_CHANGES-25-36.md) |
| §26 | 2026-09-13 | `passes.py` → [ADR 0011](../docs/adr/0011-the-block-is-the-pass.md). No refinar la rejilla cuesta **3.79 s del día, el 0.032 % de los bits**, y por eso `find_passes` no interpola la trayectoria | [archivo](archive/LAST_CHANGES-25-36.md) |
| §27 | 2026-09-13 | **El bloque es el pase.** El día asintótico reclama 3.78 Mbit y la cota finita certifica **0.43 Mbit, el 11.5 %** — y **dos de los cuatro pases no certifican nada**. La máscara de elevación tiene **óptimo interior, cerca de 8°** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §28 | 2026-09-14 | **La clave de un pase es una distribución, no un número.** La cifra de diseño —margen devuelto, apuntado en su media— **infrarreporta el día típico un 43 %** (×1.752), y los dos pases muertos siguen muertos | [archivo](archive/LAST_CHANGES-25-36.md) |
| §29 | 2026-09-14 | **Las nubes deciden si el pase existe.** Con un terminal la diversidad compra **2.30 veces** la clave de Castelldefels sola, y los seis pases descartados valían **56 925 bits, el 5.4 %**. La clave relevada espera hasta **9.4 horas** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §30 | 2026-09-14 | `scenario/` → [ADR 0014](../docs/adr/0014-scenario-contract-and-provenance.md). **Lo que valida, convierte:** lo que el motor recibe de aquí no lleva ni un grado. La estación lleva el viento r.m.s. (21.0 m/s), no el de superficie | [archivo](archive/LAST_CHANGES-25-36.md) |
| §31 | 2026-09-14 | `io/` → [ADR 0015](../docs/adr/0015-external-data-isolation-and-snapshots.md). El único sitio que puede abrir un socket, y `TestTheSuiteIsOffline` rompe `socket.socket` para demostrarlo | [archivo](archive/LAST_CHANGES-25-36.md) |
| §32 | 2026-09-14 | **Dos tests que informaban de su entorno en vez de del código.** Un test que pasa por cómo está montada la máquina no prueba nada del árbol | [archivo](archive/LAST_CHANGES-25-36.md) |
| §33 | 2026-09-14 | **El README decía «Etapa 3 en curso» con las etapas 0-6 en el árbol.** Una afirmación que el árbol no sostiene es la misma clase de defecto que un número sin test | [archivo](archive/LAST_CHANGES-25-36.md) |
| §34 | 2026-09-14 | Doppler y point-ahead **salen al resultado** → [ADR 0019](../docs/adr/0019-acquisition-in-the-result.md), [ADR 0020](../docs/adr/0020-declared-doppler-capture-range.md). Point-ahead de **24.685920 a 50.652309 µrad** en el día de referencia; deriva de 41.5 MHz/s | [archivo](archive/LAST_CHANGES-25-36.md) |
| §35 | 2026-09-15 | Dos literales del puente e2e fallaban por **9 ULP** en una máquina que no era la suya; ahora se comparan contra una cota derivada. Y **`combined_fade_db` devolvía 1.602 dB donde la respuesta es 0.101** con apuntado despreciable | [archivo](archive/LAST_CHANGES-25-36.md) |
| §36 | 2026-09-15 | `channel/horizontal.py`: presupuesto y QBER de un banco y de un enlace de unos kilómetros, con la Tabla 4 de la ITU-R P.1814 como V2. **Para GE-1 a 1 km, una lente de 10 cm da 11 veces la clave de una de 2.5 cm** | [archivo](archive/LAST_CHANGES-25-36.md) |
| §37 | 2026-09-15 | `turbulence.py` entra en **régimen moderado-a-fuerte** → [ADR 0022](../docs/adr/0022-the-strong-regime.md). El titular horizontal era un **intervalo, no un número**: la lente de 10 cm vale **entre 8.4 y 11.2**, porque las dos filas se habían calculado con onda plana a **3.16 rangos de Rayleigh** | [archivo](archive/LAST_CHANGES-37-38.md) |
| §38 | 2026-09-15 | `extinction.py` → [ADR 0023](../docs/adr/0023-traceable-extinction.md). La extinción deja de ser una **entrada** del escenario: **0.230 dB cenitales —el aire más limpio del código meteorológico de la UIT— cuestan el 22.7 % de la clave certificada** del día de referencia | [archivo](archive/LAST_CHANGES-37-38.md) |
| §39 | 2026-09-15 | El **régimen de escintilación pasa a ser un campo** del escenario, y con ello entra en el hash. Los 30 m de la estación valen **+457 bits en régimen débil y −206 en saturado**: el cruce está en 27.02° y el día pasa el 67.7 % de sus segundos por debajo | [archivo](archive/LAST_CHANGES-39.md) |
| §40 | 2026-09-17 | El **camino horizontal pasa de biblioteca a escenario** → [ADR 0024](../docs/adr/0024-the-horizontal-scenario.md), [0025](../docs/adr/0025-two-terminals-one-way.md). GE-1 a 1 km certifica **253 935 bit/s** en una sesión de 60 s, y el **acantilado de los 5 km** es lo que impide dimensionar con el número asintótico | [archivo](archive/LAST_CHANGES-40.md) |
| §41 | 2026-09-19 | **Las notas dejan de caber en la sesión que las tiene que leer.** `LAST_CHANGES.md` llegó a **6 834 líneas**; la regla de las cinco entradas vivas y sus dos cotas derivadas se asertan en `tests/unit/test_notes.py`. **240 de los 241 números** del ROADMAP ya vivían en un ADR, un test o un docstring | [archivo](archive/LAST_CHANGES-41.md) |
| §42 | 2026-09-19 | **Las dos decisiones que llevaban cincuenta días sin dueño lo tienen**: los ADR [0026](../docs/adr/0026-the-language-ladder.md) y [0027](../docs/adr/0027-four-levels-of-distribution.md). Y los **55.6 s** de sesenta satélites resultaron medir un bucle en serie, no la aritmética | [archivo](archive/LAST_CHANGES-42.md) |
| §43 | 2026-09-19 | **La CLI existe** → [ADR 0028](../docs/adr/0028-the-cli-computes-nothing.md). Un resultado horizontal tiene **su propia forma de directorio**, y el despacho es sobre qué método ofrece el resultado, **sin un método en común** | [archivo](archive/LAST_CHANGES-43.md) |
| §44 | 2026-09-19 | **La tabla de validación pasa de 22 casos de tres fuentes a 35 de ocho, y de un desacuerdo publicado a ocho** — siete de ellos del paper del que sale el enlace de referencia entero, que hasta entonces no tenía ni una fila | [archivo](archive/LAST_CHANGES-44.md) |

---

## 45. El wheel lleva sus datos, y una cita a un fichero deja de poder envejecer sola

**Fecha:** 2026-09-19. **Ningún módulo de física tocado.** ADRs tocados:
[0015](../docs/adr/0015-external-data-isolation-and-snapshots.md) («Lo que esto
cuesta», que tenía este defecto escrito como aplazado) y
[0027](../docs/adr/0027-four-levels-of-distribution.md) (el segundo de los dos
defectos de nivel 0 que su medición destapó). **Cierra la
[inconsistencia #18](INCONSISTENCIAS.md).**

**La cifra que resume la entrada: el wheel pasa de 90 a 95 entradas, y con ellas
un `pip install quoss` deja de ser una promesa incumplida. Y la comprobación que
lo demuestra no es que los ocho tests nuevos pasen, es que devolviendo el defecto
a mano fallan cinco de los ocho — y los tres que pasan son los tres escenarios.**

### Qué es un «dato de paquete», antes de nada

Un proyecto Python tiene dos clases de fichero que no son código. Están los del
**repositorio**: el `README`, los tests, los escenarios de ejemplo, el `.github/`.
Y están los que el programa **necesita para funcionar**: aquí, el catálogo de
estaciones ópticas (`ogs.yaml`, cuatro telescopios con sus coordenadas) y los dos
*snapshots* —respuestas reales de Celestrak y de Open-Meteo, congeladas con su
fecha y su SHA-256, para que la demo corra sin wifi.

La diferencia no es de contenido, es de **quién los tiene que ver**. Un test solo
lo ejecuta quien clona el repositorio. El catálogo lo abre el programa, y el
programa lo puede estar ejecutando alguien que nunca ha clonado nada: `pip
install quoss` y `quoss run`. Un fichero de la segunda clase se llama **dato de
paquete**, y la regla que lo define es física antes que conceptual: **tiene que
estar físicamente dentro del directorio del paquete**, porque el directorio del
paquete es lo único que se copia dentro del `.whl`.

Un **wheel** (`.whl`) es un ZIP con un nombre normalizado. `pip install` lo
descomprime dentro de `site-packages` y no hace nada más listo que eso. Lo que no
estaba en el ZIP no existe en la instalación, y no hay mensaje que lo diga.

### Qué pasaba, y por qué la suite entera no podía verlo

`data/ogs.yaml` y `data/snapshots/` vivían en la **raíz del repositorio**, fuera
de `src/quoss/`. Los dos lectores los encontraban subiendo tres directorios desde
sí mismos:

```python
DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parents[3] / "data" / "ogs.yaml"
```

Desde `<repo>/src/quoss/io/stations.py`, tres niveles arriba es `<repo>`. Correcto,
y correcto **solo mientras el módulo esté dentro del repositorio**. Desde
`<venv>/lib/python3.13/site-packages/quoss/io/stations.py`, tres niveles arriba es
`<venv>/lib/python3.13/`, que es del intérprete y no tiene nada que ver con QuOSS.
Medido el 2026-09-19 con el wheel instalado en un `.venv` limpio fuera del
checkout, `load_station_catalogue()` levantaba:

```
DataError: Station catalogue not found at
  /tmp/.../venv/lib/python3.13/data/ogs.yaml
```

Ruidoso, que es la regla del proyecto funcionando —«prohibido degradar en
silencio»— y **aun así una promesa incumplida**, porque no había ninguna ruta que
el usuario pudiera haber puesto: el fichero no estaba en el wheel. Sus 90 entradas
eran `quoss/**/*.py` y el `dist-info`, y nada más.

**Y por qué 3 875 tests en verde no lo veían.** Porque todos corren sobre el
checkout. `uv run pytest` pone `src/` en el path y la física no se entera de si el
paquete está instalado: en el árbol, los datos **sí** están tres directorios
arriba, así que cualquier aserción escrita contra el checkout pasa igual antes y
después del arreglo y no prueba nada. Este es el mismo argumento que obligó al
test del *console script* de la etapa 7 a lanzar `quoss` como subproceso: un
`import` no ve una cadena de *entry point* equivocada, y un checkout no ve una
entrada que falta en un ZIP.

### El arreglo: una sola ancla, dentro de lo que se copia

`data/` pasa a `src/quoss/data/`, y `src/quoss/data/__init__.py` define la única
ancla:

```python
DATA_ROOT = Path(__file__).resolve().parent
```

**Un** directorio por encima de sí misma, no tres por encima de otro módulo. La
diferencia es que ese directorio está *dentro* de lo que el backend de
construcción copia, así que la expresión da el mismo resultado en el checkout y
en `site-packages`. `DEFAULT_CATALOGUE_PATH` y `DEFAULT_SNAPSHOT_ROOT` se derivan
de ella, de modo que los dos lectores coinciden por construcción y no porque dos
copias de la misma expresión sigan en paso.

Es también la razón de que sea un módulo con `__init__.py` y no un directorio
suelto: `quoss.data` importable es lo que garantiza que **cualquier** backend lo
trate como paquete, no solo hatchling con esta configuración concreta.

Lo que **no** cubre, dicho en su docstring en vez de descubrirse: un paquete
zipimportado (`python app.pyz`), donde `__file__` nombra una entrada dentro de un
archivo y no hay directorio que abrir. Ninguno de los cuatro niveles de
distribución del ADR 0027 distribuye así.

### La comprobación, y por qué la negativa es la que vale

`tests/packaging/test_wheel.py`, ocho tests: construye el wheel en un directorio
temporal (**no** en `<repo>/dist` — un test que escribe dentro del checkout que
está midiendo ha cambiado lo que mide), crea un `.venv` limpio **fuera del
checkout** —comprobado con un `assert` sobre la ruta, no supuesto—, instala el
wheel y desde ahí carga el catálogo, los dos snapshots con su SHA-256 y corre los
tres escenarios.

| Antes | Después |
|---|---|
| 90 entradas, 648 KB | **95 entradas, 671 KB** |
| `<venv>/lib/python3.13/data/ogs.yaml` → `DataError` | `<venv>/lib/python3.13/site-packages/quoss/data/ogs.yaml` → cuatro estaciones |

**Y la parte que de verdad prueba algo.** Un test de empaquetado que solo ha visto
un paquete que funciona es una fotografía de un paquete que funciona. Se devolvió
el defecto a mano —un `exclude` en `[tool.hatch.build.targets.wheel]` que deja
`quoss/data/` fuera del wheel— y **fallaron cinco de los ocho**: las tres entradas
de datos y los dos lectores.

Los otros tres pasaron. Son los tres escenarios, y **pasaron con los datos
ausentes**. Eso no es un agujero, es la medida que explica por qué los dos tests
de lectura tienen que existir: los escenarios commiteados llevan su estación y su
TLE en línea, así que `quoss run` nunca abre `quoss/data/` y no puede notar que no
está. Es literalmente lo que la inconsistencia #18 reportaba —«corre los tres
escenarios y sale 0» mientras el catálogo no cargaba—, reproducido aquí como
control del instrumento.

**Lo que cuesta:** 17.7 s los ocho, de los cuales 15 son física (0.74 s el
horizontal, 4.86 s la bajada, 9.27 s el TLE) y 0.85 s el empaquetado entero
—0.63 s construir el wheel, 0.22 s crear el venv e instalar— con la caché de `uv`
caliente. Barato, así que corre en los cinco jobs de CI y no en uno aparte; y
porque un `skip` que nadie ve es un test que no existe, CI exporta
`QUOSS_REQUIRE_PACKAGING_TESTS=1` y ahí el `skip` por falta de `uv` es un fallo.

### La otra mitad: una cita a un fichero tampoco puede envejecer sola

Mover ficheros es la operación que en §42 rompió catorce citas a apartados de la
guía ([inconsistencia #17](INCONSISTENCIAS.md)). El remedio que allí funcionó fue
un test que resuelve cada cita; aquí había **la misma clase de cita sin cubrir**:
`test_every_guide_section_cited_from_the_code_exists` comprueba que un **apartado**
citado existe, y nada comprobaba que un **fichero** citado exista. Este cambio
movía quince referencias a `data/`, así que el test se escribió **antes** de mover
nada, no después.

`test_every_path_cited_from_the_code_exists` recorre `src/`, `tests/`, `docs/`,
`pyproject.toml`, `CLAUDE.md`, `README.md` y `notes/ROADMAP.md`, y resuelve cada
ruta citada contra tres anclas —la raíz, `src/` y `src/quoss/`— porque el árbol
usa de verdad las tres grafías (`docs/adr/0018-….md`, `quoss/data/ogs.yaml`,
`channel/atmosphere.py`) e imponer una sola haría fallar 140 citas perfectamente
legibles. **Medido: 186 rutas distintas citadas.** Siete no existen, y las siete
están en `PATHS_DECLARED_ABSENT` con su razón escrita —seis son ficheros de las
etapas 9-11 y 2.4 que el propio ADR declara no escritos en la misma frase, y la
séptima es un marcador dentro de un doctest—; cada una lleva además un test que
**aserta que sigue ausente**, de modo que la lista se encoge sola el día que
alguien escriba uno de esos ficheros.

**Comprobado rompiendo una a mano**, como se hizo con las catorce: renombrando
`scenarios/ge1_1km.yaml` a `.yml`, el test falla nombrando **26 líneas** que la
citan; restaurado, vuelve a pasar.

**Lo que no cubre, dicho en voz alta.** Solo comprueba rutas que acaban en una
extensión conocida, así que una cita a un **directorio** —`data/snapshots/`— le es
invisible. No es pereza: en prosa un nombre terminado en barra es indistinguible
de una lista separada por barras, y el árbol tiene el contraejemplo exacto,
`core ← orbits/channel/qkd ← system` en `README.md:205`, que cualquier regla de
forma-directorio lee como una cita de `src/quoss/orbits/channel/`. Un escaneo que
salte con esa frase se apaga en una semana, y un test apagado no protege nada.

### Verificación

`ruff check`, `ruff format --check`, `mypy` (165 ficheros) y **3 883 tests** en
verde, 3 875 antes: los ocho nuevos son los de empaquetado, y los dos de citas
sustituyen a ninguno. Cobertura **100 %** de líneas y ramas sobre las 9 032
sentencias del paquete, el mismo porcentaje que antes — `quoss/data/__init__.py`
entra cubierto, por su doctest.

Y el wheel se construyó e instaló de verdad, que es lo único que esta entrada
podía dar por supuesto y no ha hecho.

### Ficheros

| Fichero | Qué |
|---|---|
| `src/quoss/data/__init__.py` | **nuevo.** `DATA_ROOT`, y la defensa entera de por qué el ancla se mueve dentro del paquete |
| `src/quoss/data/ogs.yaml`, `src/quoss/data/snapshots/**` | movidos desde `<repo>/data/` |
| `src/quoss/io/stations.py`, `src/quoss/io/snapshots.py` | las dos rutas por defecto derivan de `DATA_ROOT`; la «limitación» del docstring de `snapshots.py` deja de ser una limitación |
| `src/quoss/io/celestrak.py`, `src/quoss/io/openmeteo.py`, `src/quoss/io/__init__.py` | las citas a los ficheros movidos |
| `tests/packaging/test_wheel.py` | **nuevo.** Los ocho tests, el control negativo y lo que cuesta |
| `tests/unit/test_notes.py` | `test_every_path_cited_from_the_code_exists` y su gemelo que vacía la lista de excepciones |
| `tests/conftest.py`, `tests/io/test_stations.py`, `tests/io/test_snapshots.py` | `data_dir` apunta al paquete; dos tests renombrados para que digan lo que comprueban |
| `.github/workflows/ci.yml` | `QUOSS_REQUIRE_PACKAGING_TESTS=1` |
| ADRs 0015 y 0027, `INCONSISTENCIAS.md`, `ROADMAP.md` | el defecto pasa de aplazado a cerrado, con su medida |

---

## 46. Una cita a un nodo tampoco puede envejecer sola, y una excusa de mypy caducada

**Fecha:** 2026-09-19. **Ninguna física tocada.** ADRs tocados:
[0013](../docs/adr/0013-cloud-availability-and-station-aggregation.md),
[0014](../docs/adr/0014-scenario-contract-and-provenance.md) y
[0022](../docs/adr/0022-the-strong-regime.md), los tres solo en citas.

**La cifra que resume la entrada: once citas a nodos de test estaban rotas, y
una de ellas nombraba un test que no se había escrito nunca — para justificar
que tirar entradas de un registro de degradación no pierde nada.**

### Qué es un «nodo de pytest», y por qué citarlos importa aquí

Un **nodo** es la dirección de un test dentro de la suite:
`fichero.py::Clase::metodo`. Es la unidad que `pytest` sabe ejecutar suelta, así
que una cita a un nodo es una **invitación a comprobar**: el docstring dice «esto
está medido» y el nodo dice dónde correr la medición.

Este proyecto vive de eso. La regla de `CLAUDE.md` —«medido en este repo»
significa medido por un test que corre— convierte cada afirmación numérica en
una cita a un nodo. Hay **132** en el árbol.

### Qué fallaba, y por qué no se veía

§44 dejó dicha la clase: nada comprobaba que un nodo citado exista; solo que el
fichero exista. Un fichero sigue existiendo cuando la clase de dentro se
renombra, así que la cita resuelve a medias y **se lee como perfectamente
específica**. Es el mismo modo de fallo de la inconsistencia #17 —una cita que
resuelve al sitio equivocado en vez de a ninguno— un nivel más abajo.

`test_every_pytest_node_cited_from_the_code_exists` encontró **once**, de cuatro
clases:

| Clase | Cuántas | Ejemplo |
|---|---|---|
| Método citado sin su clase | 4 | `test_the_published_answer_satisfies_keplers_equation` es de `TestPublishedVallado21` |
| Clase renombrada | 3 | `TestTheMaskSweep` por `TestTheMaskSweepInBothRegimes` |
| Sintaxis de nodo para una constante | 1 | `REFERENCE_DAY_NUMBER` de `tests/system/reference.py`, que no es un nodo |
| **Un test que no existía** | 1 | `TestNothingIsDroppedWithTheScratchLog` |

**La última es la que importa.** `engine/horizontal.py`, en su etapa `result`,
recalcula dos cantidades con un `DegradationLog` de usar y tirar, y tirar
entradas de un registro de degradación es exactamente lo que el proyecto
prohíbe. El código llevaba la defensa escrita: el presupuesto hizo las mismas dos
llamadas con el registro de verdad un momento antes, así que todo código que el
registro de pega pueda tener ya está en `degradations`, y tirarlo no pierde nada.
La frase terminaba **«That is asserted, not assumed, by …»** y la clase no
existía. Una afirmación de que algo está asertado, cuando no lo está, es peor que
no decir nada: le quita al siguiente lector la razón para comprobarlo.

Se cerró **escribiendo el test**, no suavizando el comentario. Y se escribió sin
repetir la lista de argumentos —reproducir a mano la llamada que el código hace
es un test que se pone verde justo cuando la copia se desincroniza del original—:
se sustituye el `DegradationLog` que el módulo construye por una subclase que
guarda cada instancia, así que lo que se compara es el registro de pega real.
Con dos longitudes, que son el control del propio test: a 1 km de GE-1 solo habla
la llamada de apuntado, y a 5 km —el acantilado que midió §40, usado aquí como
instrumento— la varianza de Rytov pasa de 1 Np² y habla también la de turbulencia.
Con una sola longitud el test no podría distinguir «la propiedad se cumple» de
«no avisó nadie».

**Comprobado rompiendo una a mano**, como las catorce de §42: renombrando
`TestTheMaskSweepInBothRegimes`, el test falla nombrando la cita de
`engine/sweep.py:57`.

**Lo que hace y lo que no.** Resuelve por **AST**, no pidiéndole a pytest que
recolecte: `pytest` dentro de `pytest` es un problema de estado de plugins, y —la
razón que de verdad decide— la recolección solo ve *tests*, mientras que el árbol
cita legítimamente cosas que no lo son, como la fixture
`tests/channel/test_horizontal.py::ge1_key`. Y une los nodos partidos en dos
líneas, que la prosa produce constantemente: **siete** en el árbol, y sin unirlos
se comprobarían 125 citas en vez de 132.

### La otra mitad: `warn_unused_configs`, una excusa que caducó

`pyproject.toml` lo tenía en `false` desde la etapa 0, con una razón **cierta
cuando se escribió**: las secciones por módulo eran anticipatorias, nombraban
paquetes que el roadmap aún no había creado, y avisar de todas ellas habría sido
ruido puro. Las etapas 1-8 están escritas, así que la excusa caducó — y nada
tenía por qué notarlo. Lo notó una fila del ROADMAP.

Puesto a `true`, nombró **tres** secciones muertas:

- `quoss.kernels.*` en la lista estricta: rigor prometido a un paquete que no
  existe, y que el [ADR 0026](../docs/adr/0026-the-language-ladder.md) declara no
  justificado por ninguna medida de hoy.
- `numba.*` y `pyarrow.*` en la de *stubs* ausentes: ninguno de los dos se importa
  donde mypy mira. numba es de la 2.4; pyarrow se alcanza **solo** por
  `importlib.import_module` en `io/export.py`, a propósito, para que Parquet siga
  siendo un extra — y un módulo que mypy nunca ve no necesita que le perdonen los
  stubs.

Las tres fuera, cada una con su razón escrita en el sitio del que salió.

**Y la bandera sola no cierra la fila**, que es lo que hacía falta decir: mypy la
emite como `note:` y **sale 0**. Una comprobación que no puede fallar no prueba
nada —la regla de tolerancias de `CLAUDE.md`—, así que reportaría la próxima
sección muerta a un log de CI que nadie lee. La mitad que falla es
`tests/unit/test_project_config.py`: cada patrón `quoss.*` tiene que nombrar un
paquete que exista en `src/quoss/`, y cada patrón de terceros, una distribución
que el proyecto declare. Los dos lados por separado y no el mismo, porque
significan cosas distintas: si un `override` de stubs **hace falta** depende de
qué esté instalado, y un test que dependa de los extras es un test que informa de
su entorno en vez de del árbol (§32).

### Lo que esta ronda **no** cierra, y por qué

De las siete tareas vivas del ROADMAP, esta entrada cierra **una** y deja seis,
todas comprobadas contra el árbol de hoy antes de tocarlas. Dos merecen su
medida, porque se empezaron y lo que salió es información:

- **El suelo `numpy>=1.26` no es alcanzable con el `scipy` del lock.** Medido:
  `uv run --with "numpy==1.26.4"` revienta en `scipy/sparse/_sputils.py` con
  `AttributeError: module 'numpy' has no attribute 'long'`, porque el scipy
  resuelto (1.18.0) es de la era numpy 2. Un entorno de mínimos de verdad
  —`numpy==1.26.0` con `scipy==1.11.0` sobre Python 3.11— **sí** se construye, y
  ahí el primer fallo que aparece **no es de numpy**: es `matplotlib==3.8.0`
  contra el `pyparsing` de hoy, `PyparsingDeprecationWarning` convertida en error
  por `filterwarnings = ["error"]`. O sea que el suelo que está sin justificar no
  es solo el de numpy, y el job de mínimos que la fila pide tendrá que fijar
  también el del extra `viz`. La fila se queda abierta **con esta medida escrita**
  en vez de cerrarse con un suelo elegido a ojo.
- **`--all-extras` en CI:** comprobado que ni `numba` ni `fastapi` se importan en
  ningún sitio que la suite toque, así que los extras `accel` y `web` son peso
  muerto en los cinco jobs. Lo que falta es la medida del tiempo que cuestan en
  CI, que es lo que la fila pide y no se ha hecho.

Las otras cuatro —Brouwer-Lyddane, Vallado §9.6, la reducción GCRF↔ITRF completa
y el paralelismo del bucle sobre satélites— siguen como estaban, y ninguna es de
esta ronda: las cuatro son trabajo de una etapa, no de una fila.

**Y `benchmarks/` sigue vacío.** La puerta de regresión que la etapa 11 pide no
está escrita, y decirlo aquí es preferible a un directorio con un `.gitkeep` que
parece que sí.

### Verificación

`ruff check`, `ruff format --check`, `mypy` (166 ficheros, ahora con
`warn_unused_configs` activo y sin nota) y la suite en verde.

### Ficheros

| Fichero | Qué |
|---|---|
| `tests/unit/test_notes.py` | `test_every_pytest_node_cited_from_the_code_exists`, su gemelo que vacía la lista de excepciones, y el unido de nodos partidos en dos líneas |
| `tests/engine/test_horizontal.py` | `TestNothingIsDroppedWithTheScratchLog`, el test que el comentario decía que existía |
| `tests/unit/test_project_config.py` | **nuevo.** La mitad que falla de `warn_unused_configs` |
| `pyproject.toml` | `warn_unused_configs = true` y las tres secciones muertas fuera, cada una con su razón |
| `tests/channel/test_atmosphere.py`, `tests/io/test_export.py`, `tests/e2e/test_reference_scenarios.py` | citas arregladas |
| `src/quoss/scenario/models.py`, `src/quoss/engine/sweep.py` | citas arregladas |
| ADRs 0013, 0014 y 0022 | citas arregladas; la del 0014 además dice que desde el ADR 0023 lo que se aserta es el par |
| `notes/ROADMAP.md` | la fila de `warn_unused_configs`, cerrada; las de numpy y los extras, con su medida |

---

## 47. Los tres expedientes: el simulador deja de ser código y pasa a ser respuesta

**Fecha:** 2026-09-19. **ADR nuevo:**
[0029](../docs/adr/0029-a-dossier-is-generated.md). **Física tocada: ninguna** —
ni un modelo, ni una constante, ni una tolerancia.

**La cifra que resume la entrada: tres documentos de 382 líneas que nadie
escribió a mano, y tres cifras que el resultado no llevaba y que subieron al
resultado en vez de bajar al informe.**

### Qué es un expediente, y por qué no lo cubría nada de lo que ya había

Hasta hoy este proyecto producía **números**: un objeto resultado, un CSV, una
fila de `docs/validation.md`. Lo que no producía es el documento con el que
alguien **decide** — si comprar una lente de 10 cm, si prestar un banco óptico,
si una estación de montaña vale su carretera.

Un **expediente** es ese documento. No es un artículo y no es un ADR: un ADR
registra una decisión que este proyecto ya tomó, y un expediente dice lo que el
modelo afirma sobre un experimento **que todavía no existe**, con cada cifra
llevando su unidad y la decisión que cambia. Son tres, en `docs/experiments/`,
generados desde los escenarios por `quoss dossier`:

| Documento | Desde | Líneas | Qué decide |
|---|---|---|---|
| [`GE-1.md`](../docs/experiments/GE-1.md) | `scenarios/ge1_1km.yaml` | 157 | arquitectura, presupuesto, lente, distancia, bloque |
| [`GE-0b.md`](../docs/experiments/GE-0b.md) | `scenarios/ge0b_bench.yaml` | 87 | qué pregunta de GE-1 contesta el banco y cuál no |
| [`reference-link.md`](../docs/experiments/reference-link.md) | `scenarios/reference_castelldefels.yaml` | 138 | qué pases programar, dónde la máscara, cuál enlace de Ntanos |

### Por qué se generan y se commitean, que es la decisión entera

**Porque el modo de fallo contrario está medido dos veces en este repositorio.**
Los «219 km» vivieron en quince sitios, defendidos en prosa cada vez, y eran
**5.9 veces menores** que la respuesta (§14). §46 cerró la misma familia en los
docstrings. Nada lo cazó porque nada podía: **la prosa no corre**.

**Y un expediente es peor que un docstring en exactamente una cosa: se lleva a
una reunión.** Un docstring rancio engaña a quien abre el fichero, que tiene el
código delante. Un expediente rancio engaña a una orden de compra, y su lector
**no tiene checkout ni motivo para tenerlo**. Para ese lector el fichero
commiteado *es* el artefacto.

Así que el arreglo es el de tres piezas que `docs/validation.md` tiene desde la
etapa 8: se genera, se commitea, y `tests/dossier/test_docs.py` lo vuelve a
renderizar y compara **byte a byte**. El renderizado está hecho para permitirlo:
sin marcas de tiempo, sin tiempos de etapa, sin el commit de git, cuatro cifras
significativas. Lo único volátil de la cabecera es la versión de QuOSS, y está a
propósito.

**El ejemplo que lo hace no hipotético:** `GE-1.md` dice que a **5 km el enlace
certifica cero bits mientras el cálculo asintótico sigue reclamando 267 678** en
la misma sesión. Si un cambio movía ese acantilado a 3 km y el documento seguía
diciendo 5, el documento sería peor que no existir: un argumento con fuentes y
con hash a favor de montar un enlace que no cierra.

### La mitad de la regla que es fácil saltarse, y lo que costó

**Un constructor puede pedirle corridas al motor y no puede evaluar física.** El
[ADR 0028](../docs/adr/0028-the-cli-computes-nothing.md) lo dice de la CLI; un
generador de informes es esa capa un paso más afuera, y el fallo sería peor,
porque un número calculado en la capa de presentación es un número que **ningún
test de la física cubre**, impreso para quien no puede comprobarlo.

Escribir `GE-1.md` pidió tres cifras que el resultado no llevaba: el promediado
de apertura `A`, el rango de Rayleigh del transmisor, y la longitud a la que
deja de valer la teoría débil. Las tres son **una llamada** a
`quoss.channel`, y hacerla en el informe habría costado una línea. Subieron a
`HorizontalBudgetResults`, donde las rellena el motor y las comprueba
`tests/e2e/test_horizontal_scenario.py` contra la cadena escrita a mano. **La
línea que se habría ahorrado era una línea de física que ningún test de extremo
a extremo alcanza.**

Y las tres tenían ya razón independiente para estar ahí: el
[ADR 0017 §4](../docs/adr/0017-publication-figures.md) prohíbe que
`plot_horizontal_key_against_distance` **adivine** sus dos marcas —«una marca
adivinada parece medida»— y las exige como argumentos; antes de estos campos, la
única forma de dárselas era que el llamante importara `quoss.channel`.

La regla se comprueba leyendo el AST del paquete:
`tests/dossier/test_docs.py::TestTheGeneratorEvaluatesNoPhysics` falla si
aparece un import de `quoss.channel`, `quoss.qkd`, `quoss.system` o
`quoss.orbits`.

### El número que el test cazó, que es el argumento de la ronda en miniatura

El primer borrador de `GE-0b.md` decía que la varianza log-irradiancia del
receptor es «la fila de arriba por la de más arriba» — `A` por la varianza de
Rytov. **Es falso, y de la peor manera: cierto en el banco y falso en el
campo.** La Rytov que el resultado reporta es la de **onda plana** —la cifra de
referencia contra la que los dos enlaces se afinaron—, y lo que ve el detector
es `A` por la varianza puntual de la onda **declarada**:

| | declarada | `A` × `σ_R²` | lo que reporta | factor |
|---|---|---|---|---|
| GE-0b | `plane` | 8.849e-06 | 8.849e-06 | **1, exacto** |
| GE-1 | `spherical` | 0.04745 | 0.01931 | **2.457** |

Ese 2.457 es la razón entre las dos formas cerradas. Lo cazó el test que aserta
los tres campos nuevos, no la lectura del documento — que es exactamente lo que
esta entrada sostiene que pasa cuando una cifra se escribe a mano. El documento
lleva hoy la nota que lo explica, y `A` es un campo propio precisamente porque
dividir una varianza por la otra acierta en el banco y falla por 2.46 en el
campo.

### Lo que los tres documentos dicen, que es lo que se pidió que dijeran

**GE-1.** La arquitectura de dos terminales y su razón (ADR 0025); el
presupuesto término a término; la clave certificada contra distancia con la
banda plana-esférica y la convención del [ADR 0017](../docs/adr/0017-publication-figures.md)
en el texto —**no es una barra de error**, y no está ordenada igual en las dos
lentes—; el acantilado de los 5 km con la cifra asintótica **al lado**; el bloque
declarado a 15/30/60/120 s, que es decisión del operador y no de la geometría
(ADR 0024); y qué compra la apertura, con el factor medido:

| | 25 mm | 100 mm | factor |
|---|---|---|---|
| certificado, `plane` | 882 428 | 16 546 391 | 18.75 |
| certificado, `spherical` | 1 190 150 | 15 236 099 | 12.8 |
| asintótico, `plane` | 3 415 647 | 38 243 273 | **11.2** |
| asintótico, `spherical` | 4 216 914 | 35 461 378 | **8.409** |

Las dos últimas filas **reproducen el intervalo 8.4–11.2** que §37 publicó, sin
haberlo transcrito: salen del barrido. Y el orden se invierte entre lentes, que
es lo que impide tratar la banda como «centro ± anchura».

**Y el cierre obligatorio, con los huecos 20, 21, 22 y 23 y su coste.** El
documento incluye una sección cuyo único propósito es **poner precio a un
decibelio**, porque una salvedad sin magnitud no se puede usar: medido en el
barrido, **un decibelio no modelado cuesta 3 435 865 bits, el 22.6 % de la
sesión**. El hueco 22 —la altura de escala del aerosol, factor 1.67 en
profundidad óptica— vale en GE-1 **exactamente cero bits**, medido de 1200 a
2000 m, porque el escenario declara la visibilidad a la altura a la que corre el
enlace; el documento dice también la condición bajo la que ese cero deja de
valer. El 21 va con su medida de §44: **el término de altitud saturado aterriza
en +4 bits de 449 308** bajo el otro convenio, o sea entero dentro del hueco.

**GE-0b.** Lo de §40, generado en vez de citado: el banco iguala la varianza de
Rytov a precisión de máquina (0.1988 los dos) y deja **2 183 veces menos
varianza en el receptor y 1.416 dB menos de margen**. Y la pregunta al
fabricante escrita para copiar y pegar —qué `D/r_0`, qué número de Rytov y con
cuántas pantallas, **no** si llega a 8.874e-10—, con el criterio de aceptación
que el proveedor no puede adivinar.

**reference-link.** El día (433 442 bits certificados contra 3 779 462
asintóticos), los **dos pases de cuatro que no certifican nada** mientras el
asintótico reclama 520 538 sobre ellos, la máscara con óptimo interior **y en qué
régimen** —8° en `weak`, 5° en `moderate-to-strong` sobre diez ángulos
muestreados, y el documento dice que es una muestra y no una optimización—, y
las tres estaciones con su término de altitud:

| Estación | Altitud (m) | Apertura (m) | Término de altitud (bits/día) |
|---|---|---|---|
| castelldefels | 30 | 0.75 | +490 |
| cholomondas | 850 | 0.75 | +6 193 |
| skinakas | 1 750 | 1.3 | +19 360 |
| helmos | 2 340 | 2.3 | **−25 310** |

**La cuarta fila cambia de signo**, que es el hallazgo: en la estación más alta
de las tres, estar alto **cuesta** clave certificada. El documento pone el aviso
del hueco 21 justo al lado, porque ese hueco decide el signo de esa columna, y
advierte de que lo que la tabla mide no es la cifra publicada que se le parece:
mover una estación al nivel del mar mueve **el arranque del integral de
turbulencia y además su posición geodésica**, mientras los +457 bits publicados
mueven solo lo primero; las dos concuerdan en un ~7 %, que es el tamaño de la
mitad geométrica.

**Y el apartado que esta ronda volvió obligatorio: cuál de los dos enlaces de
referencia de Ntanos se usa.** Su §4.2.1 declara 20 dB de mejor caso y su §4.3.1
imprime un pico que exige 24.07 dB; están **a 4.07 dB**, las dos están impresas,
y no pueden ser ciertas las dos bajo ningún análisis decoy que reproduzca su
Apéndice A. El documento enlaza las dos filas de `docs/validation.md`
—`ntanos2021.best-case-total-loss` (compatible) y
`ntanos2021.single-pass-peak-skr` (no reproducida)— y dice que **ninguna es
ancla**.

### Y los `warnings[]` entran en el documento, no solo en la consola

Los tres llevan una sección con cada código que la física registró al calcular
sus cifras, deduplicado y contado, con el mensaje **entero**. `quoss.cli.report`
ya los imprime en `stderr`, y eso sirve a quien corrió la orden; no sirve a quien
lee el documento, que nunca la correrá. Un `DEGRADED` significa que se
**sustituyó** un modelo, y esa es una frase que quien decide una compra tiene que
poder encontrar sin un terminal. GE-1 registra 169 entradas, el de referencia
329, el banco 8.

### Verificación

| | |
|---|---|
| Suite | **3 952 passed**, 0 fallos (eran 3 904) |
| Coste añadido | **158 s** contra 138 s de base, medido en esta máquina: **+20 s**, el 14 % |
| Generar los tres | **3.65 s**, de los cuales casi todo son las cuatro corridas de día completo |
| `ruff check` / `ruff format --check` / `mypy` | limpios; `quoss.dossier.*` entra en la lista estricta de mypy |

**El coste de los 20 s merece su línea**, porque es lo que este arreglo cuesta
de verdad: el test byte a byte tiene que **correr la física otra vez**, y no hay
forma de que no la corra. Lo que sí se hizo es que no la corra de más —
`tests/dossier/test_main.py` tiene tres tests y no seis, cada uno haciendo todas
las aserciones que puede desde **una** llamada, porque cada llamada regenera los
tres documentos y CI corre la suite cinco veces.

### Ficheros

| Fichero | Qué |
|---|---|
| `docs/adr/0029-a-dossier-is-generated.md` | nuevo. Las cuatro decisiones y lo que costó la segunda |
| `docs/experiments/{GE-1,GE-0b,reference-link}.md` | nuevos, generados y commiteados |
| `src/quoss/dossier/` | nuevo: `base.py`, un constructor por experimento, `__main__.py` |
| `src/quoss/cli/dossier.py` | nuevo. `quoss dossier <escenario> --out <doc.md>`; `--out` obligatorio a propósito |
| `src/quoss/scenario/result.py` | `HorizontalBudgetResults` gana `aperture_averaging`, `rayleigh_range_m` y `weak_theory_path_limit_m` |
| `src/quoss/engine/horizontal.py` | los rellena, con la razón escrita donde se calculan |
| `tests/dossier/` | `test_docs.py` (byte a byte, el cierre obligatorio, el AST) y `test_main.py` |
| `tests/cli/test_dossier.py` | el subcomando escribe exactamente lo que el generador produce |
| `tests/e2e/test_horizontal_scenario.py` | los tres campos nuevos contra una llamada directa, y el 2.457 que el borrador negaba |
| `notes/archive/LAST_CHANGES-42.md` | §42 archivada por la cota estructural, con su comprobación |
| `notes/ROADMAP.md`, `README.md` | la etapa 7 incluye `dossier/`; ADRs a veintinueve |

---

## 48. Cuatro directorios que prometían cosas, y dos suelos que no estaban sin probar sino equivocados

**Fecha:** 2026-09-19. **Ningún ADR nuevo. Física tocada: ninguna.**

**La cifra que resume la entrada: `numpy>=1.26` y `scipy>=1.11` llevaban desde
la etapa 0 publicados en los metadatos del wheel, y el entorno que describen
**no existe** — la suite no corre ahí y las dos versiones no son instalables
juntas. Ahora hay un job que construye los suelos, y por eso los suelos son
otros.**

### 1. Los cuatro directorios vacíos, borrados

La raíz tenía `benchmarks/`, `deploy/`, `web/` y `validation/`: cuatro
directorios con un `.gitkeep` dentro y **cero bytes** de contenido, desde el
2026-07-31.

**Por qué borrarlos y no dejarlos.** Decir que la puerta de regresión de
rendimiento no está escrita es mejor que fingirla — pero un directorio vacío la
**finge**, y la finge de la única forma que nada puede comprobar: no hay test
que distinga «aún no escrito» de «se borró y nadie lo notó». El peor de los
cuatro era `validation/`, que con `src/quoss/validation/` lleno al lado se leía
como **una segunda implementación**.

**Y arrastraban configuración muerta.** `[tool.ruff.lint.per-file-ignores]`
tenía `"benchmarks/**"` y `"validation/**"` desde la etapa 0, apuntando a los dos
directorios sin código. Una excepción de lint sobre un directorio vacío no puede
estar haciendo nada, **y no se distingue de una que sí** — y a diferencia de
mypy, `ruff` no tiene `warn_unused_configs`: no lo dice ni como nota. El
`"validation/**"` era el peor de los dos por la misma razón que el directorio:
se leía como si cubriera el código de validación, y no lo cubría, porque ese
código está en `src/quoss/validation/` y ninguna entrada de la tabla lo alcanza.
La excepción y el código que parecía excusar **nunca estuvieron en el mismo
sitio**.

La tabla pasa de tres entradas a una, y
`tests/unit/test_project_config.py::test_every_ruff_per_file_ignore_names_something_that_exists`
es lo único que puede volver a cazarlo.

**Decisión tomada, escrita donde se busca:** la puerta de regresión es de la
**etapa 11**, junto al paralelismo del bucle de `propagator.py:535` que es lo
que mediría. Está en `ROADMAP.md`, que es estado y no promete nada por existir.

### 2. Los suelos de dependencias: medidos, y dos eran falsos

La fila abierta decía «el suelo `numpy>=1.26` no está testeado». Construirlo dijo
algo peor:

| Suelo | Declarado | Qué pasa ahí | Hoy |
|---|---|---|---|
| numpy | `>=1.26` | **La suite no corre.** `np.trapezoid` no existe antes de 2.0 (`tests/orbits/test_geometry.py`), y un doctest de `src/quoss/system/correlated_fading.py` imprime `np.float64(0.951)`, que es el `repr` de escalar de numpy 2 y `0.951` antes. **No hay una sola grafía que sirva para las dos**: `np.trapz` está deprecado *después* de 2.0, y `filterwarnings = ["error"]` convierte eso en fallo | `>=2.0` |
| scipy | `>=1.11` | **No es instalable con el numpy de al lado**: 1.11 y 1.12 fijan `numpy<2`. Y `scipy==1.11.0` está **retirado de PyPI** por violación de licencia, así que el suelo nombraba una versión a la que nadie debería resolver | `>=1.13` |
| pyarrow (`export`) | `>=15` | pyarrow 15 fija `numpy<2`; el par es literalmente insatisfacible, `uv` lo dice así | `>=16` |
| matplotlib (`viz`) | `>=3.8` | **Toda matplotlib por debajo de 3.11 llama APIs que el pyparsing de hoy depreca al importar**, dentro de `_rc_params_in_file`: `parseString` hasta 3.8, `oneOf` hasta 3.10.6. Con `filterwarnings = ["error"]`, eso es un fallo de recogida. Medido contra pyparsing 3.3.2: fallan 3.8.4, 3.9.0, 3.9.2, 3.10.0, 3.10.3 y 3.10.6; **3.11.0 es la primera que no** | `>=3.11` |

pydantic, sgp4 y pyyaml se quedan donde estaban, y ahora con un job detrás. El
job fija el suelo declarado; **no busca uno más bajo**, así que «suelo» aquí
significa «este conjunto exacto pasa», no «nada por debajo podría».

**Y los dos extras que nada importa pierden el suyo.** `accel` (numba) y `web`
(fastapi, uvicorn, pydantic-settings) no los importa ningún módulo de este
repositorio: la etapa 2.4 no está escrita ([ADR 0026](../docs/adr/0026-the-language-ladder.md))
y la 9 tampoco ([ADR 0027](../docs/adr/0027-four-levels-of-distribution.md)). Así
que **ningún job puede fijarlos y averiguar si funcionan**, y un `>=` que ningún
entorno construye no es un suelo: es una esperanza publicada en los metadatos del
wheel, que es la misma clase de afirmación incumplida que persigue el ADR 0016,
una capa fuera de la física. El día que se escriba `kernels/` o `api/`, recuperan
suelo **y** una fila en el job, en el mismo commit.

**La regla es de dos caras y se aserta:**
`test_every_shipped_requirement_is_either_floored_and_pinned_or_neither` exige
que cada requisito que el paquete envía o declare suelo **y** esté fijado por el
job `minimums`, o no declare ninguno **y** esté en `FLOORLESS` con su razón. No
hay tercer estado, porque el tercer estado es lo que había. Y el listado
`FLOORLESS` se aserta en el otro sentido también, como
`PATHS_DECLARED_ABSENT`: una excepción que solo puede crecer es una que nadie
puede fechar.

**El job.** `minimums` en `ci.yml`, Python 3.11 —el más viejo soportado, porque
un suelo que solo se sostiene en el intérprete nuevo no es el suelo que dicen los
clasificadores—, `--isolated --no-project --with-editable .` en vez de
`uv sync`, porque el objetivo es construir el entorno que el lock **no**
describe. Medido: **3 968 passed en 165 s**.

**Y de eso sale un resultado que no se buscaba:** los tres expedientes de §47 se
comparan byte a byte en ese entorno también. Es decir, `docs/experiments/*.md`
son reproducibles sobre **dos pilas numéricas distintas** —numpy 2.0.2 + scipy
1.13.0 y las del lock—, no una fotografía de una máquina.

### 3. `--all-extras` fuera de los cinco jobs, y la medida que lo decide

La fila abierta pedía «la medida del tiempo de CI que cuestan». Medida, y **el
tiempo no era el coste**:

| | caché de uv | entorno instalado | sync en frío | sync en caliente |
|---|---|---|---|---|
| `--all-extras` | 709 MiB | 708 MiB | 4.44 s | 0.56 s |
| `--extra viz --extra export` | 499 MiB | 497 MiB | 3.88 s | 0.17 s |

**210 MiB, el 30 %**, y casi todo es `llvmlite` (172 MiB); el extra `web` entero
son unos 5 MiB. Medio segundo por job en caliente no es una razón para nada.

**La razón que sí lo es:** `--all-extras` se lee como la afirmación de que la
suite ejercita todos los extras, y no lo hace. Los cinco jobs sincronizan
`--extra viz --extra export`. `viz` es obligatorio —`tests/viz` importa
matplotlib en el módulo, así que sin él la recogida **falla** en vez de
saltarse—; `export` no lo es —los tests de Parquet se saltan sin pyarrow— y se
sincroniza igual, porque un test que se salta en todos los entornos es un test
que nadie corre.

### 4. Las cuatro que quedan: tres no tenían etapa viva

La comprobación que pedía la ronda, y devolvió un defecto en vez de un visto
bueno:

| Trabajo | Dónde estaba | Dónde está |
|---|---|---|
| Brouwer-Lyddane | fila suelta, columna «`orbits/`» — **ninguna etapa** | **etapa 2.5** |
| Vallado §9.6 como V2 | fila suelta, columna «etapa 8» — **y la etapa 8 está cerrada** | **etapa 2.5** |
| Reducción GCRF↔ITRF | fila suelta, columna «etapa 8» — **cerrada también** | **etapa 2.5** |
| Paralelismo del bucle | etapa 11 | etapa 11, sin cambios |

**Tres de las cuatro apuntaban a un sitio al que ya nadie vuelve.** Una fila que
nombra una etapa terminada es trabajo que nadie va a leer en el momento en que
importa, que es exactamente el defecto que el directorio vacío de arriba comete
en el otro sentido. La **etapa 2.5** existe ahora, colocada entre las etapas de
física y no después de la distribución, porque ahí es donde está en el orden de
dependencias. Y dice lo que hay que decir de las tres: **ninguna bloquea nada**,
el hito B está alcanzado sin ellas, y ninguna cambia hoy un número publicable.
Ninguna se hace en esta PR.

### Verificación

| | |
|---|---|
| Suite, entorno del lock | **3 968 passed**, 0 fallos, 156 s |
| Suite, suelos declarados (py3.11) | **3 968 passed**, 0 fallos, 165 s |
| `ruff check` / `ruff format --check` / `mypy` | limpios |
| `uv lock` | re-resuelto por los suelos nuevos: 8 líneas |

### Ficheros

| Fichero | Qué |
|---|---|
| `benchmarks/`, `deploy/`, `web/`, `validation/` | **borrados**; eran cuatro `.gitkeep` |
| `pyproject.toml` | suelos medidos; `accel` y `web` sin suelo, con la razón; dos `per-file-ignores` fuera |
| `.github/workflows/ci.yml` | job `minimums`; `--all-extras` → `QUOSS_CI_EXTRAS` en los cinco jobs, con la medición al lado |
| `tests/unit/test_project_config.py` | la regla de dos caras de los suelos, `FLOORLESS`, y los `per-file-ignores` |
| `tests/unit/test_notes.py` | los cuatro nombres siguen en `CITED_ROOTS`, y ahora para lo contrario: hacen **fallar** una cita bajo ellos |
| `tests/io/test_export.py` | los «40 MB» de pyarrow que §44 había medido en 152 MiB y que aquí seguían |
| `docs/adr/0027-…` | la cita a `pyproject.toml:48` pasa a nombrar el extra: un número de línea es una cita que envejece sola |
| `notes/ROADMAP.md` | **etapa 2.5**; la puerta de regresión decidida en la 11; dos filas abiertas cerradas |
| `README.md` | los cuatro directorios, los suelos probados, y `--all-extras` con su coste |
| `notes/archive/LAST_CHANGES-43.md` | §43 archivada por la cota estructural, con su comprobación |

---

## 49. La puerta de entrada, una versión que se puede citar, y la cuarta clase de cita rota

**Fecha:** 2026-09-19. **ADR nuevo:** el
[0030](../docs/adr/0030-a-release-is-something-you-can-cite.md).

**La cifra que resume la entrada: la cuarta auditoría de la puerta encontró
cinco afirmaciones falsas, y las cinco son de una clase que los tres tests
escritos para esto no pueden ver — no son citas, son cuentas.** «29 ADRs» no
resuelve a nada: o es el número de ficheros de `docs/adr/` o es mentira, y
distinguirlo exige contarlos.

Esta PR no añade capacidad. Convierte el repositorio en algo que otra persona
pueda usar y citar.

### 1. La auditoría, y por qué la clase volvió a aparecer por una vía nueva

Las tres rondas anteriores cerraron tres vías con tres tests: una cita a un
apartado de la guía (§45), una cita a una ruta (§45), una cita a un nodo de
pytest (§46). Las tres comparten una operación —**coger el identificador que la
cita nombra y resolverlo**— y por eso son **totales**: un regex encuentra todas
las citas de esa forma, así que una escrita mañana queda comprobada el día que
se escribe, sin que nadie la registre.

La cuarta ronda recorrió `README.md`, `CLAUDE.md` y `ROADMAP.md` afirmación por
afirmación contra el árbol. Esto es lo que salió:

| Afirmación | Dónde | El árbol | Qué se hizo |
|---|---|---|---|
| «`INCONSISTENCIAS.md` tiene **dos** entradas abiertas» | `CLAUDE.md` | El fichero dice **una**, y su tabla abierta tiene **una fila** | Corregida, y **asertada** |
| «ninguna de las **quince** que ha tenido» | `CLAUDE.md` | **Diecinueve** filas con identificador distinto en el fichero (1–18 más C1) | Corregida, y asertada |
| «Hoy son **910 y 321**» (líneas de `LAST_CHANGES.md` y `ROADMAP.md`) | `CLAUDE.md` | **1 068 y 401** | La columna pasa a ser **la cota, no la medida**: ≤ 500 y ≤ 1 732, que es lo que `test_the_other_notes_stay_readable` ya aserta y lo que de verdad hace falta saber antes de abrir un fichero |
| Tabla de lectura: `~120`, `~1 140`, `~350`, `6 800` | `CLAUDE.md` | 130, 1 068, 401, 8 099 | Lo mismo: una bitácora crece en cada PR y un número copiado a mano no |
| «las entradas **§1–§38** íntegras» en `archive/` | `CLAUDE.md` | §1–§43, y con esta PR §1–§44 | Corregida |
| «**29 ADRs**» | `README.md` | 29 entonces, **30** al acabar esta PR | Corregida, y asertada |
| «**7 huecos declarados**» (validación) y «**veintitrés** huecos declarados» (ADR 0009) | `README.md`, `ROADMAP.md` | Las dos ciertas, y **la misma frase para dos cosas distintas** | Desambiguadas: **huecos de fuente** (7, filas `gap` de la tabla) y **huecos de cita** (23, la lista numerada del ADR 0009) |
| «`quoss run scenarios/…`, que es lo que instala `pip install quoss`» | `README.md` | El wheel **no lleva** `scenarios/`: son 102 entradas y ninguna es un `.yaml` de escenario | Reescrito: el arranque es un clon, y se dice por qué un escenario es una entrada y no un dato de paquete |
| «`api/` y `kernels/` son paquetes vacíos» | `README.md` | Cuatro directorios con un `.gitkeep` y nada más —`src/quoss/api/`, `src/quoss/kernels/`, `tests/api/`, `tests/physics/`—, y **los dos primeros viajaban dentro del wheel** | **Borrados**, con los trece `.gitkeep` vestigiales que quedaban |
| «**3 640 tests**, al 2026-09-15» | `README.md` | 3 968 entonces, **3 993** al acabar | Corregida, con su fecha |
| «Verificación al 2026-09-15: 100 % de líneas y ramas» | `README.md` | Se sostiene | Sin cambio |
| Las nueve cifras de física (433 442 bits, 3.78 Mbit, 4 pases, 11.637 dB, 253 934.98 bit/s, 0.230 dB, 22.7 %, 47.7 %, 0.1 s) | `README.md` | **Las nueve se reproducen** ejecutándolas hoy | Sin cambio |

**Dos cosas de esa tabla merecen leerse dos veces.** La primera: las cifras de
física, que son las difíciles, **están todas bien**; lo que estaba mal es la
aritmética del documento sobre sí mismo. Es coherente con cómo se llenó
`INCONSISTENCIAS.md` —los números tienen un test detrás porque el proyecto los
persigue; los inventarios no tenían ninguno—. La segunda: los cuatro
directorios vacíos son **el mismo defecto que la PR anterior cerró en la raíz**,
un nivel más abajo, donde no se miró.

### 2. La comprobación que la ronda pedía: se puede, y no es una de las tres

La pregunta era si de las tres clases ya asertadas se podía sacar una sola
comprobación que cubriera también ésta. **La respuesta es que se puede escribir
la comprobación y no se puede fundir con las tres**, y el motivo es concreto:

- Las tres resuelven un **identificador**. Eso las hace totales y sin registro.
- Una cuenta no tiene identificador que resolver. Necesita una **receta** —código
  que vuelva a contar la cosa— y sólo una persona puede escribir «esta frase va
  de los ficheros de `docs/adr/`». El registro es inevitable.

`test_every_inventory_claim_the_door_makes_matches_the_tree` es esa cuarta
comprobación, y la debilidad del registro está acotada igual que `CITED_ROOTS`
acota la de las rutas: **es total sobre un vocabulario**. No busca las frases que
conoce; busca todo «*número* + *sustantivo contable*» sobre trece sustantivos, y
falla ante cualquiera que no tenga receta. Añadir una decimoquinta frase sobre
ADRs al README queda cubierta sin tocar el test; inventar una clase nueva de cosa
contable, no — y ese residuo es el coste honesto de la forma.

Se vacía por el otro lado también, como las dos listas de excepciones de §45
y §46: `test_every_counted_noun_is_claimed_somewhere` falla cuando un sustantivo
deja de usarse, porque una receta que ninguna frase ejercita es código que nada
puede falsar.

**Y dos cosas que deliberadamente no cubre.** El **número de tests** —contar la
suite desde dentro de la suite es autorreferencial: añadir un test a ese módulo
cambia el número que el módulo aserta—, y por eso el README lo da con la fecha
en que se midió. Y las **cifras de física**, que no lo necesitan: cada una tiene
ya el test que la mide, y el README cita ese test. Lo que no estaba asertado
nunca fue la física de la puerta. Era su aritmética sobre sí misma.

**Tres falsos positivos, los tres útiles.** Al escribirlo, el escaneo marcó «en
los dos **casos**» de `CLAUDE.md` —castellano corriente, no la tabla de
validación—, y se arregló pidiendo la cola que la frase real siempre lleva
(«N casos de M fuentes»). Marcó los **dos huecos** de la fila de `satquma.py`,
que son un subconjunto y no un total: el vocabulario cuenta totales de
repositorio, así que una cuenta con alcance tiene que deletrear su alcance, y
esa es la frase que un lector frío necesitaba de todos modos. Y marcó
«cinco **escenarios de bajada**» partido por el salto de línea a ochenta
columnas, de donde salió que un sustantivo de varias palabras tiene que
sobrevivir al plegado.

### 3. `README.md` deja de ser un informe de estado

Antes empezaba con un bloque de cita de setenta y tres líneas titulado
«**Estado, al 2026-09-19**». Eso se lee bien si ya sabes lo que hay dentro. Hoy
la primera frase es la pregunta que el simulador contesta, con «enlace óptico
cuántico», «QKD» y «certifica» definidos donde se usan; la segunda sección son
**las cuatro respuestas** —los tres expedientes y `docs/validation.md`— antes
que ningún proceso; la tercera, instalar y correr. El estado de etapas y la
estructura bajan al final, y el resto se va al ROADMAP.

**Las cinco líneas de arranque se ejecutaron en un clon limpio, no se
escribieron de memoria**, y ejecutarlas es lo que destapó que el wheel no lleva
los escenarios.

### 4. Citable, y qué significa citar un programa

`CITATION.cff` —el formato que GitHub y Zenodo leen sin intervención—, tag
`v0.1.0` y `CHANGELOG.md`. El ADR 0030 separa las dos preguntas que se confunden
aquí: «cómo nombro esto en una bibliografía» (una versión, estable, con DOI) y
«con qué código se calculó esta cifra» (un commit, que una versión no da porque
cubre muchos árboles).

`quoss --version` pasa de imprimir `quoss 0.1.0` a imprimir los **cuatro campos
que `Provenance` ya escribía en cada resultado** —versión, commit, intérprete,
numpy y scipy— para que la pregunta tenga una sola respuesta tanto si se le hace
a un fichero como al comando. Es una acción propia de `argparse` y no
`action="version"` por dos razones medidas: la de serie reenvuelve el texto al
ancho del terminal (cuatro líneas salen como dos), y toma la cadena al construir
el parser, con lo que **cada `quoss run` pagaría el subproceso `git rev-parse`**.

**Y el commit no entra en los cuatro documentos commiteados, por una razón que
no es preferencia.** `docs/validation.md` gana la cabecera de versión que le
faltaba —los tres expedientes ya la tenían—, y no gana el commit porque git no
puede meter el hash de un commit dentro de ese commit: la línea nombraría el
anterior y el test byte a byte quedaría rojo para siempre. Peor: `git_commit()`
vale `None` sin repositorio, así que los bytes dependerían de si la máquina
tiene un `.git` al lado — **un test que informa de su entorno en vez de del
código**, que es exactamente el defecto de §32.

### 5. El ROADMAP deja de listar trabajo

Hito B marcado como **alcanzado y cerrado**. La sección «Etapas 9–11» y la tabla
«Trabajo abierto» se funden en **§ Disparadores**: siete filas que dicen qué
tendría que ocurrir para abrir cada etapa, no cuándo se abrirá. Para la 2.4, la
condición ya está medida (paralelizar el bucle de `propagator.py:535` **primero**,
ADR 0026); para las 9–11, el ADR 0027. Una lista de trabajo envejece hacia
«pendiente desde hace ocho meses»; una lista de condiciones o se cumple —y
entonces hay una PR que escribir— o no, y mientras tanto el silencio es correcto.

### Verificación

| | |
|---|---|
| Suite | **3 993 passed**, 0 fallos (eran 3 968) |
| `ruff check` / `ruff format --check` / `mypy` | limpios |
| Arranque de cinco líneas | ejecutado en un clon limpio con venv nuevo |
| Y de ahí una medida que no se buscaba | `quoss run` sobre el enlace de referencia son **4.8 s** de reloj, de los cuales la física es **0.117 s**: 0.6 s de importar numpy y scipy y **3.9 s de escribir el directorio** (CSV, `.npz` y un SHA-256 por fichero). El README lo desglosa, porque «0.1 s» a secas al lado de una orden que tarda cinco segundos es una cifra cierta que se lee como falsa |
| Wheel | 102 entradas → **93**: caen los nueve `.gitkeep` que viajaban dentro |

### Ficheros

| Fichero | Qué |
|---|---|
| `README.md` | Reescrito como puerta: pregunta, respuestas, arranque, límites, citación, estado al final |
| `CITATION.cff`, `CHANGELOG.md` | Nuevos. El segundo lleva el procedimiento de la siguiente versión y el de Zenodo, no sólo el resultado de ésta |
| `docs/adr/0030-…` | Nuevo: por qué se cita una versión y por qué el commit no cabe en los cuatro documentos |
| `src/quoss/cli/main.py` | `version_report()` y `_VersionAction` |
| `src/quoss/validation/base.py` | Cabecera de versión en `docs/validation.md`, y la razón de que no lleve commit |
| `tests/unit/test_notes.py` | La cuarta comprobación, su vocabulario, y su vaciado por el otro lado |
| `tests/unit/test_project_config.py` | `CITATION.cff` contra `pyproject.toml` y `__init__.py`; el `CHANGELOG` tiene entrada para la versión que el paquete reporta |
| `tests/cli/test_main.py` | `TestWhatVersionAnswers`, incluido el reenvuelto que sólo se ve como subproceso |
| `CLAUDE.md` | Las cinco afirmaciones falsas de la tabla de arriba, y la columna de coste pasa a ser cota |
| `notes/ROADMAP.md` | Hito B cerrado; § Disparadores; ADR 0030 en la tabla de numeración |
| `notes/archive/LAST_CHANGES-44.md` | §44 archivada por la cota estructural |
| 17 `.gitkeep` | Borrados, y con ellos cuatro directorios que prometían etapas |

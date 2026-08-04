# ADR 0001 — Convención de unidades

- **Estado:** aceptada
- **Fecha:** 2026-07-31
- **Etapa:** 1 (`core/`)
- **Afecta a:** todo el código. Es la decisión de mayor alcance del proyecto.

---

## Contexto

`notes/ROADMAP.md` §Etapa 1 marca la convención de unidades como *la* decisión a
tomar en esta etapa: «es la que más fricción ahorra o cuesta durante todo el
proyecto. Elígela y no la cambies».

El coste de equivocarse es asimétrico. Una unidad inconsistente no produce un
error: produce un número plausible. Y un número plausible pero incorrecto en una
figura es, según el diagnóstico de `notes/GUIA_REIMPLEMENTACION.md` §0, «lo peor
posible en un paper».

Hay tres presiones en conflicto:

1. Las fórmulas de física se escriben en radianes y en transmitancia lineal.
2. El ecosistema externo de astrodinámica (`sgp4`, CelesTrak, la literatura)
   trabaja en kilómetros.
3. El usuario piensa en grados, decibelios y nanómetros.

## Decisión

**SI estricto en el interior, con una única excepción: las distancias orbitales
van en kilómetros. Las conversiones ocurren en la frontera. Los nombres llevan
sufijo de unidad siempre que pueda haber ambigüedad.**

| Dominio                                        | Canónica interna     | Frontera (solo I/O) |
| ---------------------------------------------- | -------------------- | ------------------- |
| Distancias ópticas (apertura, beam, wavelength) | m                    | nm                  |
| Distancias orbitales (altitud, slant range)     | **km**               | km                  |
| Ángulos                                        | rad                  | deg                 |
| Pérdidas / transmitancias                      | lineal (0–1)         | dB                  |
| Potencia                                       | W                    | dBm                 |
| Frecuencia                                     | Hz                   | GHz                 |
| Tiempo (transcurrido)                          | s                    | s                   |
| Tiempo (absoluto)                              | fecha juliana (días) | ISO-8601 UTC        |

### Sufijos

`altitude_km`, `slant_range_km`, `aperture_m`, `wavelength_m`, `elevation_rad`,
`tx_power_w`. Sin sufijo solo para la forma adimensional canónica (`eta_total`,
`qber`, una probabilidad) o cuando el contexto no deja lugar a duda.

`_deg` y `_db` existen **únicamente** en el borde. Un `elevation_deg` dentro de
`channel/` es un bug de diseño, no un detalle de estilo.

### Dónde se convierte

En `scenario/io.py`, en la frontera con el usuario. Con **una** excepción
interna, inevitable y documentada: el *slant range* viaja en km pero la pérdida
geométrica lo necesita en metros, junto a la longitud de onda. Esa conversión se
hace al entrar en `channel/` mediante `km_to_m()`, nunca con un `* 1e3` suelto.

## Justificación

### Por qué km para lo orbital y no metros

`sgp4`, CelesTrak y el 100 % de la literatura de astrodinámica trabajan en km.
Internalizar metros pondría un factor ×1000 en cada llamada a SGP4 y un ÷1000 en
cada comparación con un paper. El riesgo de confusión supera la pureza del SI en
este dominio concreto. Además `550.0` se lee mejor que `550_000.0`.

### Por qué lineal y no dB internamente

Las fórmulas de QKD y de canal se escriben en transmitancia lineal:

```python
eta_total = eta_geometric * eta_atmosphere * eta_detector
skr = mu * eta_total * (1 - h(e_bit))
```

En dB solo la *suma* es cómoda. En cuanto una transmitancia se multiplica por
algo más, o entra en `h(e)`, hay que volver a lineal. Los dB son para el link
budget del ingeniero, no para el cálculo del físico.

### Por qué dos pares de conversión dB, no uno

Esta es la parte no obvia, y la razón de que la implementación se desvíe del
mínimo «cuatro helpers y nada más».

Una pérdida en dB es un número **positivo** cuya transmitancia es **menor que
uno**. Con un único `db_to_linear(x) = 10**(x/10)`:

```python
loss_db = 45.0
eta = db_to_linear(loss_db)  # 31622.8  ← mal por 9 órdenes de magnitud
```

El resultado sigue pareciendo una transmitancia. Ninguna comprobación de tipos
ni ningún sufijo lo detecta. Por eso `core/units.py` expone dos pares con nombre
explícito:

| Convención | Función                     | Sentido                            |
| ---------- | --------------------------- | ---------------------------------- |
| Ratio      | `db_to_linear`              | dB positivo → ratio > 1 (ganancia) |
| Ratio      | `linear_to_db`              | inversa                            |
| Pérdida    | `loss_db_to_transmittance`  | dB positivo → η < 1 (atenuación)   |
| Pérdida    | `transmittance_to_loss_db`  | inversa                            |

Ambos pares usan la convención de potencia `10 log10`. QuOSS nunca convierte
amplitudes de campo, así que el `20 log10` no aparece en ningún sitio.

### Por qué el tiempo absoluto entra en la tabla

La propuesta inicial cubría el tiempo transcurrido (`s`) pero no el instante
absoluto. SGP4, GMST y la geometría solar necesitan una fecha juliana. Sin
fijarlo, cada módulo se habría inventado su propia época, y el primer bug sería
un desplazamiento silencioso de un día en una curva Doppler.
`core/types.TimeGrid` lleva el par (`epoch_jd`, `t_s`) junto.

### Por qué las conversiones devuelven `float` para entrada escalar

`np.log10(45.0)` devuelve `np.float64`, que ni `json.dumps` ni `yaml.safe_dump`
saben serializar. Como estas funciones viven justo en la frontera de
serialización, dejar escapar `np.float64` rompería el volcado del escenario y de
la procedencia. Las funciones preservan la forma: escalar → escalar, array →
array.

## Alternativas consideradas

|                              | SI estricto puro           | **Mixto pragmático (elegida)** | Mixto sin convención |
| ---------------------------- | -------------------------- | ------------------------------ | -------------------- |
| Fórmulas de física           | directas                   | directas                       | depende              |
| Interfaz con SGP4/TLE        | factor ×1000 en cada llamada | sin fricción                 | sin fricción         |
| Riesgo de bug silencioso     | bajo con sufijos           | bajo con sufijos               | **alto**             |
| Legibilidad código orbital   | `550_000.0`, incómodo      | `550.0`, natural               | natural              |
| Comparación con papers       | siempre SI                 | orbital km, resto SI           | ambigua              |
| Coste de aprenderla          | una regla                  | una regla + una excepción      | leyendo código       |

También se descartó una librería de unidades (`pint`, `astropy.units`): resuelve
la corrección pero impone un coste de rendimiento y de complejidad sobre cada
operación vectorizada, y el objetivo número uno del rediseño es precisamente la
velocidad del núcleo numérico. Los sufijos en los nombres dan el 90 % del
beneficio con coste cero en tiempo de ejecución.

## Consecuencias

**Positivas**

- Las fórmulas se transcriben desde los papers sin factores de conversión.
- Cero fricción con `sgp4` y con la literatura orbital.
- Las dos convenciones de dB son imposibles de confundir por accidente.
- Los resultados son serializables sin conversión adicional.

**Negativas, y aceptadas**

- Hay que recordar una excepción (km orbital). Los sufijos la hacen visible.
- Existe una frontera interna km→m al entrar en `channel/`. `km_to_m()` la
  nombra en lugar de esconderla.
- Cuatro funciones de dB en vez de dos. Es el precio de que el signo sea
  explícito, y es un precio que merece la pena.

## Cumplimiento

La convención no vive solo en este documento. `tests/unit/test_conventions.py`
la verifica en CI mediante un escaneo AST de `src/quoss`:

- `np.deg2rad` / `np.rad2deg` solo en `core/units.py` y `scenario/io.py`.
- Ningún factor `1e3` / `1e-3` suelto fuera de esos dos módulos.
- Ninguna aparición literal de la velocidad de la luz fuera de `core/constants.py`.

Cuando aparezca una excepción legítima, se añade a la *allowlist* del test con un
comentario que explique por qué. Eso convierte una deriva silenciosa en una
decisión revisada.

## Referencias

- `notes/ROADMAP.md` — Etapa 1
- `notes/GUIA_REIMPLEMENTACION.md` §0, §2.3
- `src/quoss/core/units.py` — la convención como código
- `src/quoss/core/constants.py` — nota sobre WGS-72 vs EGM96

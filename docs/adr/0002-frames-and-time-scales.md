# ADR 0002 — Marcos de referencia y escalas de tiempo

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Etapa:** 2.1 (`orbits/frames.py`)
- **Afecta a:** toda la geometría — propagación, pases, elevación, Doppler,
  apuntado. Cualquier módulo que hable de una posición.

---

## Contexto

«ECI» no es un marco: es una familia de marcos que difieren entre sí decenas de
kilómetros a lo largo de una década. `notes/ROADMAP.md` §2.1 pide «ECI ↔ ECEF ↔
geodésico, GMST, tiempo juliano» sin especificar cuál, y el ADR 0001 fijó que el
tiempo absoluto es una fecha juliana en UTC sin decir contra qué escala se
interpreta.

Hay tres tensiones reales:

1. **SGP4 devuelve TEME**, no J2000 ni GCRF. El propio paquete `sgp4` advierte de
   que no implementa la conversión a marcos oficiales. Y SGP4 no es opcional en
   un simulador de satélites: sin él no hay TLE, y sin TLE no hay Micius ni
   validación contra misiones reales.
2. **GMST es función de UT1**, no de UTC. Y UT1 requiere tablas EOP que caducan.
3. **La reducción completa GCRF ↔ ITRF** (precesión, nutación, movimiento polar)
   es correcta al metro, pero añade `erfa` más datos externos con fecha de
   caducidad — y no cambia ningún número del presupuesto de enlace.

El coste de equivocarse aquí es el mismo que en el ADR 0001 y por la misma razón:
un marco mal elegido no da un error, da una curva desplazada que parece correcta.
Es exactamente el fallo que este proyecto existe para evitar.

## Decisión

**Un único marco inercial, TEME. Un único giro sobre el polo, por GMST (IAU-82),
para llegar al marco fijo a la Tierra. UT1 ≡ UTC. Sin movimiento polar, sin
nutación, sin segundos intercalares. Geodesia siempre WGS-84. Y el presupuesto de
error de esas omisiones medido por un test, no afirmado en un comentario.**

| Cantidad             | Elección                                    |
| -------------------- | ------------------------------------------- |
| Marco inercial       | **TEME** (True Equator, Mean Equinox)       |
| Marco fijo a Tierra  | `ROT3(GMST)·TEME` — estrictamente PEF, tratado como ITRF/ECEF |
| Sidéreo              | GMST IAU-82 (serie de Aoki 1982)            |
| Escala de tiempo     | UTC, usada donde corresponde UT1            |
| Elipsoide            | WGS-84, latitud **geodésica** siempre       |
| Marco topocéntrico   | ENU sobre la normal geodésica               |
| Calendario ↔ JD      | Fliegel–Van Flandern (exacto en gregoriano) |

`Frame` es un `StrEnum` con `TEME`, `ITRF`, `ENU` y `GCRF`. `GCRF` **se declara y
no se implementa**: ninguna función lo produce ni lo consume. Existe para que el
día que entre la reducción completa, todo array ya venga etiquetado y los puntos
de conversión que faltan se encuentren con un grep.

## Consecuencias

### El presupuesto de error, medido

`tests/orbits/test_frames.py::TestFrameErrorBudget` compara este módulo contra la
reducción completa de astropy y **descompone** el residuo en vez de meterlo todo
en una tolerancia opaca:

| Aproximación                    | Error de posición         | Efecto en el enlace          |
| ------------------------------- | ------------------------- | ---------------------------- |
| Movimiento polar ignorado       | **14.4 m** (peor medido)  | ~14 µrad a 1000 km           |
| UT1 ≡ UTC (\|DUT1\| ≤ 0.9 s)    | ≤ 460 m (**274 m** medido)| ≤ 0.03° en elevación         |
| GMST IAU-82 vs IAU-2006         | ~2 m (0.06″, 2000–2030)   | despreciable                 |

La descomposición es lo que hace el test informativo: al rotar por GMST(UT1) en
vez de GMST(UTC), el residuo contra astropy cae a ~14 m, y eso **es** el
movimiento polar. Es decir, el test no dice «se parece bastante»: dice que el giro
es correcto y que todo lo que sobra es exactamente lo que omitimos a propósito.
Los dos términos no suman coherentemente — el error de UT1 es un giro sobre el
polo, así que se anula para un satélite sobre el polo y es máximo sobre el ecuador.

0.03° de elevación cambian el airmass ~0.1 % a 10° y desplazan el instante de un
pase menos de 0.1 s. Nada de eso se ve en una tasa de clave secreta.

**Dónde sí importaría:** apuntado en lazo abierto a precisión de µrad. QuOSS no
lo modela, y un terminal real cierra ese lazo sobre un beacon.

### Lo que esto cierra y lo que no

- **Cierra:** ningún módulo inventa su época ni su marco. No hay conversiones
  TEME↔GCRF de ida y vuelta que añadan error sin añadir exactitud.
- **No cierra:** los segundos intercalares son una restricción real, no de
  redondeo. Una época en un día que lleva un segundo intercalar está desviada
  hasta un segundo en UT1. Esas épocas están excluidas del conjunto de referencia
  por el mismo motivo, y el generador lo documenta.
- **Coste de cambiar a GCRF:** bajo, gracias al enum. Las firmas no cambian; se
  añaden funciones y se cambia qué etiqueta lleva cada array.

### La regla que este módulo fija para toda la etapa 2

`notes/LAST_CHANGES.md` dejó pendiente «firma estándar de una función de física:
¿`log: DegradationLog` en todas, o solo en las que pueden degradar?». Se decide
aquí, con el primer módulo:

> **Una función de física recibe un `DegradationLog` solo si puede decidir en
> tiempo de ejecución calcular algo distinto de lo que su nombre promete.**

Ninguna función de `frames.py` lo recibe. Las tres aproximaciones de arriba son
*elecciones de modelo*, fijas para todo el run, y las registra una sola vez quien
ensambla el pipeline. Registrarlas por llamada emitiría una entrada por muestra
temporal y ahogaría el log que existe para ser legible. Y una entrada mala es un
**error**, no una degradación: levanta `DomainError`.

## Alternativas descartadas

**Reducción completa GCRF ↔ ITRF con `erfa` + EOP.** Correcta al metro. Descartada
*por ahora*: añade una dependencia pesada y tablas que caducan, para mover
números que no afectan a ninguna magnitud publicable. El enum deja la puerta
abierta.

**Soportar varios marcos inerciales desde el principio.** Multiplicaría las rutas
de conversión y con ellas las formas de mezclarlos. Un marco y un enum que impide
confundirlo es más seguro que cuatro marcos bien documentados.

**Vallado Alg. 14 para calendario → JD.** Descartada por incorrecta: su término
de bisiestos, `int(7·(y + int((m+9)/12))/4)`, es la regla juliana de «cada cuatro
años», así que falla por un día al cruzar un año secular no bisiesto. Medida
contra astropy, es exacta solo entre 1900-03-01 y 2100-02-28, y se desvía ±1 día
a ambos lados. **Lo detectó el conjunto de datos de referencia en su primera
ejecución**, que es precisamente el argumento a favor del protocolo de
verificación del ADR siguiente en espíritu (`tests/golden/README.md`).

**Latitud geocéntrica y altitud `|r| − R_eq`.** Es lo que hace SimulCTTC
(`app/physics/propagation.py:180`). Descartada por errónea: hasta 0.19° en latitud
y −21.4 km de altitud en el polo, y coloca las estaciones sobre una esfera. Sesga
toda elevación calculada a partir de ellas. Hay tests que fijan la diferencia
numéricamente, para que nadie la reintroduzca por simplicidad aparente.

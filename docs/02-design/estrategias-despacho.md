# Estrategias de Despacho BESS

## Visión General

El prototipo BESS implementa varias estrategias de despacho que se encadenan a lo largo del rango de análisis, utilizando una quincena representativa que se repite. Todas las estrategias respetan el principio de **balance diario nulo**: carga = descarga en energía.

**Principio clave**: Para respetar la potencia máxima del POI (50 MW), la FV se recorta con una **meseta plana a 50 MW** y las descargas BESS se desplazan a la ventana nocturna **20–24h**, donde no hay generación solar.

---

## 1. Arbitraje

**Objetivo**: Compra en valle nocturno, vende en pico de precio (noche).

**Perfil horario**:
- **00–05h**: Carga de red (`-1.5 MW`)  
  - Aprovecha precios OMIE bajos en valle nocturno
- **20–24h**: Descarga a red (`+2.0 MW`)  
  - Exportación nocturna sin solapamiento solar
  - Asegura rentabilidad en franjas de mayor valor

**Energía diaria**: ~10–12 MWh (medio ciclo)

---

## 2. Arbitraje + Secundaria

**Objetivo**: Arbitraje base + participación en banda de regulación secundaria aFRR.

**Perfil horario**:
- **00–05h**: Carga de red (`-1.5 MW`)
- **12–18h**: Oscilación suave en banda aFRR (`±0.15 MW`)  
  - Responde a desviaciones de frecuencia sin conflicto POI
- **20–24h**: Descarga a red (`+2.0 MW`)

**Energía diaria**: ~11–13 MWh (arbitraje + ingresos secundaria)

---

## 3. Energy Shifting

**Objetivo**: Captura excedentes solares mediodía, exporta al atardecer/noche.

**Perfil horario**:
- **09–15h**: Carga de FV excedentes (`-1.5 MW`)  
  - Absorbe generación solar que no cabe en el POI
  - Típico de plantas híbridas en momento de máxima radiación
- **20–24h**: Descarga a red (`+1.5 MW`)  
  - Exportación en horario nocturno de máximo precio

**Energía diaria**: ~11–13 MWh (ciclo PV-almacenamiento-venta)

---

## 4. Caso de Uso Multiservicio (Showcase)

**Objetivo**: Combinación de múltiples servicios a lo largo del día (referencia operativa).

**Perfil horario**:
- **00–06h**: Carga de red en valle (`-1.2 MW`)  
  - Relleno inicial aprox. 7 MWh a precio bajo
- **06–14h**: FV + carga de excedentes  
  - Modulación suave: `-0.55 + 0.07·sin(2πh/4)` MW
  - Captura excedentes solares sin interrumpir POI
- **14–20h**: Modulación suave (transición)  
  - Potencia no positiva: transición absorbente sin exportación adicional
  - Prepara batería para descarga nocturna
- **18–22h**: Banda aFRR absorbente (regulación secundaria)  
  - Oscilación negativa suave alrededor de 0
  - Apoyo a estabilidad sin competir con la PV en el POI
- **20–24h**: Descarga nocturna máxima (`+2.0 MW`)  
  - Sin solapamiento solar
  - Máxima inyección a red en horario nocturno

**Energía diaria**: ~14–16 MWh (ciclo completo multiservicio)

---

## Parámetros de Consistencia

### Balance Energético
- **Carga total diaria** = **Descarga total diaria** (balance nulo)
- SoC vuelve a su nivel inicial cada día sin deriva
- Energía escalada automáticamente según dataset histórico

### Límites de POI
- **Máximo POI permitido**: 50 MW (parámetro `poi_limit_mw`)
- Garantizado: `POI[i] = PV[i] + BESS[i] ≤ 50 MW` para todo instante i
- Curtailment FV aplicado como: `PV_clip[i] = min(PV[i], 50 MW)`
- Descarga BESS limitada a: `BESS_max[i] = 50 − PV_clip[i]`

### SoC (State of Charge)
- **Integral exacta** de la potencia BESS: `SoC[i] − SoC[i−1] = −∫P·dt/Capacidad`
- Rango operativo: Típicamente 20–100% (dependiendo DoD máximo)
- Recalculado automáticamente si hay limitaciones

---

## Implementación Técnica

### Generación de Perfiles
1. Define forma (patrón de potencia sin escalar)
2. Calcula energía objetivo del dataset
3. Escala proporcionalmente: `P_escalado = P_forma × (E_objetivo / E_forma)`
4. Aplica curtailment FV: `PV_clip = min(PV, límite_poi)`
5. Limita la descarga BESS al margen instantáneo: `BESS_export ≤ límite_poi − PV_clip`
6. Reequilibra la carga diaria para mantener balance energético nulo
7. Recalcula SoC como integral exacta

### Quincena Representativa
| Día | Estrategia | Seed Determinista |
|-----|-----------|------------------|
| 1 | Arbitraje | base_seed × 100 + 0 |
| 2 | Arbitraje + Secundaria | base_seed × 100 + 1 |
| 3 | Energy Shifting | base_seed × 100 + 2 |
| 4–14 | Ciclo repetido | ... |
| 1–5 (dentro del showcase) | Multiservicio | base_seed × 100 + 777 |

---

## Referencia Histórica

- **Última actualización de estrategias**: 2026-07-07
- **Cambio principal**: curtailment FV plano a 50 MW + export BESS nocturno 20–24h
- **Resolución**: 5–15 minutos (adaptativa según rango)
- **Cobertura**: 1 año (365–366 días típicos)

---

## Notas para el Operador

### Desplazamiento de Descargas
Todas las descargas están concentradas en **20–24h** (noche sin PV) para:
- ✅ Garantizar `POI ≤ 50 MW` siempre
- ✅ Reservar margen POI diurno a la producción FV
- ✅ Maximizar ingresos (precios típicamente más altos en noche)
- ✅ Mantener consistencia del histórico

### Curtailment FV en el POI
- Cuando la producción FV supera el límite nominal, se fuerza una **meseta plana a 50 MW** en la curva solar.
- La BESS no añade exportación positiva si ese margen ya está agotado.
- El curtailment forma parte del comportamiento esperado del histórico sintético y debe mantenerse consistente en cualquier modificación futura.

### Impacto en KPIs
- **Round-trip efficiency**: ~88–92% (según ciclos día-noche)
- **Ciclos equivalentes**: ~1.5–2 por día (arbitraje puro)
- **Disponibilidad**: >99% (sin mantenimiento)
- **Vida útil**: ~10 años a ~600 ciclos/año

### Customización
Para cambiar las estrategias, edita:
- `src/bess_simulator/engine/plant.py`
  - `_day_power_shape()`: Formas de arbitraje y energy shifting
  - `_showcase_day_power_shape()`: Caso multiservicio

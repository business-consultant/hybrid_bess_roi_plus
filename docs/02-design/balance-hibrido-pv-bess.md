# Balance energético híbrido PV↔BESS: coste cero de carga solar, crédito de sinergia y curtailment

> Documento explicativo independiente. Describe cómo el simulador reconcilia la
> energía que la PV cede a la BESS, por qué se asigna a **coste de carga cero**,
> cómo se reconoce el **crédito de sinergia** (vitamina el spread del BESS) y
> cómo se **estima el curtailment** (que no se asume nunca cero) y su coste.
>
> Implementación: `src/bess_simulator/engine/hybrid.py`
> (`compute_hybrid_economics`). Parámetros: `src/bess_simulator/storage/app_config.py`.

---

## 1. El problema (la fisura de valor)

El simulador analiza la **PV** y la **BESS** con ROI/VAN **independientes** (no
comparten CAPEX). Ambos activos, sin embargo, comparten el **punto de
interconexión (POI)** y se alimentan mutuamente: una parte de la generación PV se
desvía a la batería en lugar de inyectarse directamente a red
(`pv_to_bess_share`).

Antes de esta reconciliación había una **fisura**:

- La energía `PV → BESS` se **restaba** del ingreso PV (correcto: no se inyecta a
  red, no la cobra la PV).
- Pero **no se acreditaba** en ningún sitio del lado BESS. Esa energía
  desaparecía del balance económico: ~9.000 MWh/año se evaporaban.

Además, el **curtailment** salía ≈ 0 porque solo se medía el recorte físico
instantáneo cuando la PV supera el POI; con el inversor (p. ej. 48 MW AC) por
debajo del límite del POI (50 MW), ese recorte es casi nulo. **Nadie se cree que
el curtailment de una planta híbrida sea cero.**

---

## 2. Criterio adoptado (decisiones de modelado)

| Decisión | Criterio |
|----------|----------|
| **PV→BESS a coste CERO puro** | La PV no cobra esa energía; la BESS la recibe gratis. |
| **Crédito de sinergia** | El ahorro de no comprar esa carga en el pool se reconoce como crédito y **vitamina el spread efectivo** del BESS. |
| **Reconciliación ANUAL** | Se concilia a nivel agregado anual (no intervalo a intervalo), suficiente y robusto para el prototipo. |
| **Curtailment estimado, no cero** | Recorte físico sobre el POI **+** residual por concurrencia PV+BESS en el POI compartido. Ajusta la producción PV vendible. |

---

## 3. Reconciliación energética PV↔BESS

### 3.1 Demanda de carga de la BESS

La energía que la BESS **descarga** en el año 1 ($E_{descarga}^{BESS}$, tomada
directamente del Simulador ROI para coherencia exacta) implica una **demanda de
carga** mayor por el rendimiento de ciclo $\eta_{RTE}$:

$$E_{carga}^{BESS} = \frac{E_{descarga}^{BESS}}{\eta_{RTE}}$$

### 3.2 Fracción de carga de origen solar

La PV cubre una fracción $f_{PV}$ de esa carga (acotada por la demanda):

$$f_{PV} = \frac{\min\!\left(E_{PV\to BESS},\; E_{carga}^{BESS}\right)}{E_{carga}^{BESS}}$$

Con el escenario por defecto, $f_{PV} \approx 9\%$: la PV aporta del orden de una
décima parte de la energía con la que se carga la batería.

---

## 4. Coste cero de carga y crédito de sinergia

La energía `PV → BESS` se asigna a **coste cero**. El valor creado es el coste
**evitado** de no comprar esa carga en el pool, a un precio de carga de red
$P_{carga}$ (proxy del OMIE en ventana valle, parámetro `bess_grid_charge_price`,
por defecto **35 €/MWh**):

$$\text{Crédito}_{sinergia} = \sum_{t=1}^{N}
\frac{E_{PV\to BESS}\cdot \delta_{PV}^{(t)} \cdot P_{carga}}{(1+r)^t}$$

donde $\delta_{PV}^{(t)}$ es el factor de degradación PV del año $t$ y $r$ la tasa
de descuento. El crédito se acumula en el **VAN de planta**:

$$VAN_{planta} = VAN_{BESS} + VAN_{PV} + \text{Crédito}_{sinergia}$$

### Spread efectivo (presentación)

El mismo ahorro, repartido sobre la energía descargada, **vitamina el spread**:

$$\text{spread}_{ef} = \text{spread}_{base} +
\frac{E_{PV\to BESS}\cdot P_{carga}}{E_{descarga}^{BESS}}$$

> **Por qué es una sinergia y no un ingreso del BESS standalone:** la batería
> ciclaría igual cargando de la red; el valor diferencial es **solo** el ahorro
> en el coste de carga al usar PV gratis. Por eso se atribuye a la **planta**, no
> al ROI del BESS aislado (que se mantiene como arbitraje puro y honesto).

---

## 5. Estimación del curtailment (no se asume cero)

El curtailment total tiene dos componentes:

1. **Recorte físico sobre el POI** ($E_{curt}^{POI}$): cuando la potencia PV
   instantánea supera el límite del POI y la BESS no puede absorberla. Relevante
   solo con ILR alto (campo muy sobredimensionado).

2. **Residual por concurrencia** ($E_{curt}^{conc}$): la PV y la descarga de la
   BESS compiten por el **mismo POI**. Aunque un despacho inteligente programa la
   batería para **evitar** recortar PV valiosa, queda un residual inevitable (más
   órdenes de red). Se modela como un porcentaje de la inyección directa
   (parámetro `poi_concurrency_curtail_pct`, por defecto **3 %**):

$$E_{curt}^{conc} = p_{conc}\cdot E_{PV\to red}, \qquad
E_{PV\to red}^{neto} = E_{PV\to red} - E_{curt}^{conc}$$

La **producción PV vendible** se ajusta a $E_{PV\to red}^{neto}$, por lo que el
ingreso y el VAN de la PV ya **descuentan** el curtailment.

### Coste del curtailment

El coste es el ingreso PV **perdido** por la energía recortada (física + de
concurrencia), valorada al precio PV $P_{PV}$ y descontada a vida útil:

$$\text{Coste}_{curt} = \sum_{t=1}^{N}
\frac{\left(E_{curt}^{POI}+E_{curt}^{conc}\right)\cdot \delta_{PV}^{(t)} \cdot P_{PV}}{(1+r)^t}$$

---

## 6. Parámetros (avanzados, sin tocar la UI del operador)

Ambos viven en `DEFAULT_ADVANCED_CONFIG` (pantalla de configuración avanzada del
modelo), de modo que el validador puede ajustarlos sin alterar el formulario del
operador:

| Parámetro | Defecto | Significado |
|-----------|--------:|-------------|
| `bess_grid_charge_price` | 35.0 €/MWh | Precio de carga de red evitado (proxy OMIE valle). Crédito por MWh solar cargado. |
| `poi_concurrency_curtail_pct` | 0.03 | Curtailment residual por concurrencia PV+BESS, como fracción de la inyección directa. |

---

## 7. KPIs en pantalla (Simulador ROI → "Más resultados")

- **VAN planta (BESS + PV)** = VAN BESS + VAN PV + crédito de sinergia.
- **Reconciliación PV↔BESS:** carga BESS de origen solar ($f_{PV}$), spread
  efectivo, crédito de sinergia, coste del curtailment.
- **Flujos híbridos en el POI:** PV→red (neto), PV→BESS, curtailment total,
  clipping del inversor.

---

## 8. Trazabilidad de campos (`HybridEconomics`)

| Campo | Descripción |
|-------|-------------|
| `pv_to_grid_net_mwh` | Inyección directa neta tras curtailment de concurrencia. |
| `pv_curtailed_concurrency_mwh` | Recorte por concurrencia en el POI. |
| `pv_curtailment_total_mwh` | Curtailment total año 1 (POI físico + concurrencia). |
| `pv_curtailment_cost_total` | Ingreso PV perdido por curtailment (vida útil, €). |
| `bess_charge_demand_mwh` | Demanda anual de carga de la BESS. |
| `bess_solar_charge_mwh` | PV→BESS efectiva usada como carga (acotada). |
| `bess_solar_fraction` | $f_{PV}$: fracción de carga BESS de origen solar. |
| `bess_base_spread` / `bess_effective_spread` | Spread base y vitaminado (€/MWh). |
| `synergy_pv_charge_credit` | Crédito de sinergia PV→BESS (vida útil, €, descontado). |

---

## 9. Limitaciones conocidas

- La reconciliación es **anual agregada**: no resuelve el solapamiento intradía
  intervalo a intervalo (modelado como residual paramétrico).
- $P_{carga}$ es un **proxy** (no se separa precio de compra/venta en el motor de
  arbitraje, que trabaja con spread). El valor por defecto (35 €/MWh) es
  defendible como precio de valle OMIE y es ajustable.
- El curtailment de concurrencia es una **estimación paramétrica**, no una
  simulación de despacho co-optimizado; su objetivo es ofrecer una cifra
  **creíble y no nula**, no un valor regulatorio.

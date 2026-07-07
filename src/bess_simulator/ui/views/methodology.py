import streamlit as st


def render_methodology_page():
    from bess_simulator.ui.components.sticky_header import render_sticky_header
    render_sticky_header("Metodología")
    st.markdown(
        "Esta sección describe las reglas de cálculo, modelos de datos sintéticos "
        "y criterios de recomendación utilizados por el simulador."
    )

    # ── Sección 1: Motor de Simulación ──
    with st.expander("Motor de Simulación", expanded=False):
        st.markdown("""
**Resolución temporal:** 15 minutos (96 intervalos/día) durante toda la vida útil del proyecto.

#### Fórmulas principales

**Capacidad disponible:**
```
Capacidad₀ = Potencia × C-Rate × SoH_inicial
Capacidad_t = (1 - Degradación_acumulada_t) × Capacidad₀
```

**Degradación acumulada:**
```
Degradación_t = Degradación_(t-1) + degradación_por_ciclo × ciclos_t
```

**Energía vendida por intervalo (15 min):**
```
Energía = Capacidad_t × Ciclos_intervalo × RTE × DoD_máximo × 0.25h
```

**Ingresos:**
```
Income = Energía_vendida × Precio_SPREAD
```

**Flujo de caja:**
```
Cash_Flow = Income - OPEX_intervalo
OPEX_intervalo = OPEX_anual / (365 × 96)
```

**Flujo de caja descontado (DCF):**
```
DCF_t = Cash_Flow_t / (1 + tasa_descuento)^(t / 365)
```

**VAN (Valor Actual Neto):**
```
VAN = Σ DCF_t  (para todos los intervalos)
```

**ROI (Retorno sobre Inversión):**
```
ROI = DCF_acumulado_final / CAPEX_total
donde DCF_acumulado_final = -CAPEX + Σ DCF_t
```

#### Variabilidad estocástica

Para simular condiciones reales, se aplica variación aleatoria controlada (con seed para reproducibilidad):

| Variable | Variación | Distribución |
|----------|-----------|-------------|
| Ciclos por intervalo | +0% a +40% sobre la base | Uniforme |
| RTE por intervalo | Desde 95% de la base hasta +15% | Uniforme |
| Precio SPREAD | Desde 70% de la base hasta +100% | Uniforme |

#### Incumplimientos SoH

Se cuenta el número de intervalos donde la degradación acumulada supera el umbral `(1 - SoH_mínimo)`.
Ejemplo: si SoH_mín = 75%, el umbral es 25% de degradación.
""")

    # ── Sección 2: Modelo de Precios OMIE ──
    with st.expander("Modelo de Precios OMIE (Datos Sintéticos)", expanded=False):
        st.markdown("""
Los datos históricos del dashboard utilizan un modelo experto del mercado eléctrico español (OMIE)
que combina patrones diarios, semanales y estacionales. Los precios horarios reales son públicos
en [omie.es](https://www.omie.es/en/market-results/daily/daily-market/daily-hourly-price).
Los spreads históricos observados en España oscilaron entre 25 y 67 €/MWh (H1 2021-2023).

#### Curva diaria de precios

```
Precio(hora) = Base + Valle + Pico_mañana + Caída_solar + Pico_tarde
```

| Componente | Centro (hora) | Amplitud (€/MWh) | Efecto |
|-----------|:------------:|:-----------------:|--------|
| Base | — | 55.0 | Nivel base |
| Valle | 04:00 | -10.0 | Madrugada, demanda mínima |
| Pico mañana | 09:00 | +30.0 | Arranque industrial |
| Caída solar | 13:30 | -15.0 | Inyección fotovoltaica |
| Pico tarde | 20:00 | +38.0 | Demanda doméstica máxima |

#### Factores semanales

| Día | Factor |
|-----|:------:|
| Lunes - Viernes | 1.00 |
| Sábado | 0.82 |
| Domingo | 0.78 |

#### Factores estacionales (por mes)

| Mes | Factor | | Mes | Factor |
|-----|:------:|-|-----|:------:|
| Enero | 1.12 | | Julio | 1.10 |
| Febrero | 1.10 | | Agosto | 1.10 |
| Marzo | 0.95 | | Septiembre | 1.00 |
| Abril | 0.85 | | Octubre | 0.95 |
| Mayo | 0.85 | | Noviembre | 1.05 |
| Junio | 0.95 | | Diciembre | 1.15 |

#### Ruido estocástico

- **Ruido diario:** N(0, 5) €/MWh — mismo valor durante todo el día
- **Ruido intradiario:** N(0, 2) €/MWh — varía cada 15 minutos
- **Límites:** precio final recortado a **[20, 150] €/MWh**

#### Ventanas de arbitraje

| Ventana | Horario | Acción | Lógica |
|---------|---------|--------|--------|
| **Carga** | 02:00 - 06:00 | Compra barata | Precios en el valle nocturno |
| **Descarga AM** | 08:00 - 10:00 | Venta en pico matutino | Arranque industrial |
| **Descarga PM** | 19:00 - 21:00 | Venta en pico vespertino | Demanda doméstica |
""")

    # ── Sección 2b: Reconciliación híbrida PV↔BESS ──
    with st.expander("Reconciliación híbrida PV↔BESS (sinergia y curtailment)", expanded=False):
        st.markdown(r"""
La PV y la BESS se analizan con **ROI/VAN independientes** (no comparten CAPEX),
pero comparten el **punto de interconexión (POI)** y se alimentan mutuamente. La
reconciliación se hace a **nivel anual agregado** sobre el año representativo.

#### 1. Energía PV→BESS a coste CERO

La energía PV desviada a la batería ($E_{PV\to BESS}$) se asigna a **coste de
carga cero**: la PV **no cobra** por ella (no entra como ingreso PV, evitando
doble contabilidad) y la BESS la recibe **gratis**.

#### 2. Crédito de sinergia (vitamina el spread)

La demanda anual de carga de la BESS se reconcilia con su energía descargada:

$$E_{carga}^{BESS} = \frac{E_{descarga}^{BESS}}{\eta_{RTE}}, \qquad
f_{PV} = \frac{\min(E_{PV\to BESS},\, E_{carga}^{BESS})}{E_{carga}^{BESS}}$$

La fracción $f_{PV}$ de la carga que aporta la PV evita comprar esa energía en el
pool. Con la PV a coste cero, el **ahorro neto** es el precio de carga de red
evitado $P_{carga}$ (proxy OMIE valle, parámetro `bess_grid_charge_price`):

$$\text{Crédito}_{sinergia} = \sum_{t=1}^{N} \frac{E_{PV\to BESS}^{(t)} \cdot P_{carga}}{(1+r)^t}, \qquad
\text{spread}_{ef} = \text{spread}_{base} + \frac{E_{PV\to BESS}\cdot P_{carga}}{E_{descarga}^{BESS}}$$

El crédito se suma al **VAN de planta** = $VAN_{BESS} + VAN_{PV} + \text{Crédito}_{sinergia}$.

#### 3. Curtailment estimado (no se asume cero)

Además del recorte físico cuando la PV supera el POI, se estima un **residual por
concurrencia** PV+BESS en el POI compartido (parámetro
`poi_concurrency_curtail_pct`), porque ambos compiten por el mismo límite de
evacuación. Reduce la **producción PV vendible** y tiene un coste asociado:

$$E_{curt}^{conc} = p_{conc}\cdot E_{PV\to red}, \qquad
E_{PV\to red}^{neto} = E_{PV\to red} - E_{curt}^{conc}$$

$$\text{Coste}_{curt} = \sum_{t=1}^{N} \frac{E_{curt}^{(t)} \cdot P_{PV}}{(1+r)^t}$$

> Detalle completo y supuestos en `docs/02-design/balance-hibrido-pv-bess.md`.
""")

    # ── Sección 3: Datos Sintéticos ──
    with st.expander("Datos Sintéticos: Histórico vs Proyección", expanded=False):
        st.markdown("""
El dashboard genera dos regímenes de datos separados por la **fecha HOY**:

#### Régimen Histórico (antes de HOY)

Basado en modelado experto. No depende de los parámetros del usuario.

| Variable | Modelo | Valores típicos |
|----------|--------|:---------------:|
| Precios | Curva OMIE completa (ver sección anterior) | 20 - 150 €/MWh |
| Energía vendida | Utilización 70-92% en ventanas de descarga | Variable |
| Capture price | 92-102% del precio de mercado en descarga | Variable |
| Ciclos diarios | Uniformes 0.8 - 1.8 FEC/día | ~1.3 |
| SoH | Degradación calendar 1.5%/año + cíclica 0.01%/ciclo (ver fuentes) | Decreciente |
| RTE | Inicia en 87%, degrada 0.4%/año + ruido N(0, 1.2%) (NREL ATB: 85% ref.) | ~85% |
| Temperatura | Estacional (14-30°C) + diaria (±3°C) + operación (+1.5-3.5°C) | 18 - 38°C |

#### Régimen de Proyección (desde HOY)

Controlado por los parámetros que configura el usuario.

| Variable | Fuente | Comportamiento |
|----------|--------|---------------|
| Precios | OMIE escalado por `spread_usuario / 40` | Misma forma, amplitud ajustada |
| Energía vendida | `Potencia × 0.25h × DoD × utilización (75-90%)` | Controlado por DoD |
| Ciclos | Parámetro del usuario ± 5% | Estable |
| SoH | Continúa desde último valor histórico | `SoH_hist - calendar - ciclo × degradación` |
| RTE | Parámetro del usuario ± N(0, 0.8%) | Estable |
| Temperatura | Mismo modelo estacional que histórico | 18 - 38°C |

#### Continuidad en la frontera HOY

El SoH de la proyección arranca desde el último valor del régimen histórico, garantizando
continuidad en la curva. Los ciclos acumulados también se heredan.
""")

    # ── Sección 4: Matriz de Sensibilidad ──
    with st.expander("Matriz de Sensibilidad", expanded=False):
        st.markdown("""
La matriz de sensibilidad evalúa cómo varía el ROI al cambiar dos parámetros simultáneamente:

- **Filas:** 7 valores de precio de retribución (±30% del valor base, en pasos del 10%)
- **Columnas:** 5 valores de OPEX (±20% del valor base, en pasos del 10%)
- **Celdas:** ROI resultante de ejecutar una simulación completa para cada combinación

La matriz se **centra dinámicamente en el caso base**: la fila y columna centrales (0%)
reproducen exactamente el OPEX y el precio introducidos por el usuario, por lo que la
celda central coincide con el ROI del caso base. Al cambiar los inputs, toda la matriz
se recalcula alrededor del nuevo valor central.

Todos los demás parámetros (CAPEX, tasa de descuento, RTE, degradación, etc.) se mantienen
fijos en los valores del caso base. Esto permite aislar el efecto combinado del coste
operativo y el precio de venta sobre la rentabilidad —ambas son palancas accionables por
el operador, a diferencia del CAPEX, ya comprometido en la fase de inversión.
""")

    # ── Sección 5: Sistema de Recomendaciones ──
    with st.expander("Sistema de Recomendaciones", expanded=False):
        st.markdown("""
El sistema genera recomendaciones automáticas encadenando varias evaluaciones:

```
Alarmas históricas → Evaluación ROI → Evaluación Degradación
→ 5 Sub-recomendaciones → Mensaje compuesto
```

#### Evaluación de Rentabilidad (ROI)

| Condición | Resultado | Color |
|-----------|-----------|:-----:|
| ROI > tasa descuento **y** ROI > 8% | Rentable | Verde |
| ROI ≈ tasa descuento **y** ROI > 8% | Rentable, diversificar | Verde |
| ROI > tasa descuento **y** ROI < 8% | Rentabilidad moderada | Amarillo |
| ROI < tasa descuento **y** ROI > 8% | Rentabilidad moderada-baja | Amarillo |
| ROI < tasa descuento **y** 0% ≤ ROI < 8% | Baja rentabilidad | Amarillo |
| ROI < 0% | No rentable | Rojo |

#### Evaluación de Degradación

| Condición | Resultado | Color |
|-----------|-----------|:-----:|
| Degradación último año ≥ (1 - SoH mínimo) | Compromete SoH mínimo | Rojo |
| Degradación último año < (1 - SoH mínimo) | Margen para ciclar más | Verde |

#### Sub-recomendaciones por parámetro

| Parámetro | OK | Aviso | Alerta |
|-----------|:--:|:-----:|:------:|
| **Tasa descuento** | < 8% | 8% - 10% | > 10% |
| **OPEX** | < 10K €/MW/año | 10K - 15K | > 15K |
| **RTE** | > 90% | 80% - 90% | < 80% |
| **Vida útil** | ≥ 15 años | 10 - 15 años | < 10 años |
| **Precio retribución** | > 45 €/MWh | 30 - 45 €/MWh | < 30 €/MWh |

#### Alarmas operacionales

El sistema monitoriza si los datos históricos de la simulación operan fuera de rangos
aconsejados en: **C-Rate, RTE, DoD, SoC y Temperatura**.

#### Código de colores

- **Verde:** La inversión es rentable y los parámetros están en rango seguro
- **Amarillo:** La inversión puede ser rentable pero hay parámetros a revisar
- **Rojo:** La inversión no es rentable o la degradación compromete la vida útil
""")

    # ── Sección 6: Fuentes y Referencias ──
    with st.expander("Fuentes y Referencias", expanded=False):
        st.markdown("""
Los valores y supuestos del simulador se fundamentan en las siguientes fuentes públicas:

#### Costes y parámetros económicos (CAPEX, OPEX, vida útil)

| Fuente | Datos utilizados |
|--------|-----------------|
| **NREL ATB 2024** — [atb.nrel.gov/electricity/2024/utility-scale_battery_storage](https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage) | RTE de referencia: **85%**. Vida útil: **15 años**. O&M fijo: **2.5% del CAPEX/año**. Asume ~1 ciclo/día. Cubre químicas NMC y LFP |
| **Lazard LCOE+ (Junio 2024)** — [lazard.com/media/xemfey0k/lazards-lcoeplus-june-2024-_vf.pdf](https://www.lazard.com/media/xemfey0k/lazards-lcoeplus-june-2024-_vf.pdf) | LCOS para 100MW/400MWh. Degradación presupuestada: **0.66-1.85% CAPEX/año**. Operación: **1 ciclo/día × 350 días/año** |
| **Ember (2025)** — [ember-energy.org/latest-insights/how-cheap-is-battery-storage](https://ember-energy.org/latest-insights/how-cheap-is-battery-storage/) | CAPEX global: **$125/kWh** (equipo $75 + instalación $50). Europa: **~€120/kWh**. Degradación anual: **≤2%**. RTE AC-AC: **90%**. Ciclos garantizados: **10.000-12.000+**. OPEX anual: **~2% del CAPEX** |

#### Precios de mercado eléctrico

| Fuente | Datos utilizados |
|--------|-----------------|
| **OMIE** — [omie.es/en/market-results](https://www.omie.es/en/market-results/daily/daily-market/daily-hourly-price) | Precios horarios del mercado diario ibérico (España y Portugal). Datos públicos descargables. Base para la curva diaria del modelo sintético |
| **Synertics (2023)** — [synertics.io/blog/69](https://synertics.io/blog/69/arbitrage-navigating-market-deviations-while-maximising-profits) | Spreads de arbitraje observados en España: **25.56** (H1 2021), **67.61** (H1 2022), **44.88** (H1 2023) €/MWh en precios day-ahead |

#### Degradación de baterías LFP

| Fuente | Datos utilizados |
|--------|-----------------|
| **MDPI Applied Sciences (2025)** — "Study on Influencing Factors of Calendar Aging and Cycle Aging of LFP Batteries" — [mdpi.com/2076-3417/15/23/12749](https://www.mdpi.com/2076-3417/15/23/12749) | Calendar aging dominado por SOC y temperatura. Cycle aging dominado por DOD, C-rate y temperatura |
| **MDPI Energies (2021)** — "The Degradation Behavior of LiFePO4/C Batteries during Long-Term Calendar Aging" — [mdpi.com/1996-1073/14/6/1732](https://www.mdpi.com/1996-1073/14/6/1732) | Comportamiento de calendar aging LFP a largo plazo. Celdas a bajo SOC y baja temperatura: **<0.5%/año** |
| **Nature Communications (2025)** — "The importance of degradation mode analysis in parameterising lifetime prediction models" — [nature.com/articles/s41467-025-57968-3](https://www.nature.com/articles/s41467-025-57968-3) | Modelos de predicción de vida útil. Análisis de modos de degradación (SEI, pérdida de litio, pérdida de material activo) |

#### Arbitraje y estrategia operativa BESS

| Fuente | Datos utilizados |
|--------|-----------------|
| **ResearchGate (2023)** — "The value of electricity storage arbitrage on day-ahead markets across Europe" | Valor del arbitraje en mercados europeos, incluyendo España |
| **eFinancialModels** — "What Is The Duck Curve?" — [efinancialmodels.com](https://www.efinancialmodels.com/knowledge-base/templates/battery-energy-storage-system-bess/what-is-the-duck-curve-electricity-pricing-in-the-age-of-solar-and-batteries-624997/) | Patrón de duck curve: exceso solar 11:00-15:00 (precios bajos para carga), picos de demanda vespertinos (precios altos para descarga) |

#### Correspondencia modelo ↔ fuentes

| Parámetro del modelo | Valor usado | Referencia |
|---------------------|:-----------:|-----------|
| RTE base | 85-87% | NREL ATB 2024 (85%), Ember (90% AC-AC) |
| Degradación calendar | 1.5%/año | Conservador respecto a Ember (≤2%/año), en línea con literatura LFP |
| Degradación cíclica | 0.005-0.02%/ciclo | Rango validado por Ember (10K-12K ciclos para 35% fade → ~0.003%/ciclo) |
| CAPEX | 300K-1M €/MW | Rango amplio que cubre mercado europeo actual (~€120/kWh × 4h = ~€480K/MW para 4h) |
| OPEX | 11K-22.5K €/MW/año | Compatible con NREL (2.5% CAPEX) y Ember (2% CAPEX) |
| Vida útil | 10-15 años | NREL ATB 2024 (15 años), Ember (20 años diseño) |
| Ciclos vida útil | 6.000-8.000 | Conservador respecto a Ember (10K-12K garantizados) |
| Precio SPREAD | 20-100 €/MWh | Cubre rango observado OMIE/Synertics (25-67 €/MWh) |
| Ventanas arbitraje | Carga 02-06h, Descarga 08-10h/19-21h | Consistente con duck curve y patrones OMIE |

> **Nota:** Los valores del modelo son aproximaciones calibradas para LiFePO4 (LFP) en el mercado
> ibérico. Para análisis con otras químicas (NMC, NCA) o mercados, los parámetros deberían
> ajustarse según las fuentes específicas del caso.
""")

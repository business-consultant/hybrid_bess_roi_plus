# Parametrización del Simulador BESS

> Referencia visual: [image-1.png](image-1.png), [image-2.png](image-2.png), [image-3.png](image-3.png)
> Fuente de datos: [Financial KPIs & BESS_ROI_Model.xlsx](Financial%20KPIs%20%26%20BESS_ROI_Model.xlsx)

---

## 1. Parámetros de Entrada (Inputs)

### 1.1 Parámetros Económicos (ECONOMIC ASSUMPTIONS)

| Variable | Descripción | Valor ejemplo | Rango válido | Unidad | Origen |
|----------|-------------|---------------|--------------|--------|--------|
| **Initial CAPEX** | Coste inicial de inversión por MW | 400,000 | 300,000 – 1,000,000 | €/MW | Input usuario |
| **Annual OPEX** | Coste operativo anual por MW | 11,000 | 11,000 – 22,500 | €/MW/año | Input usuario |
| **Discount Rate** | Tasa de descuento | 6% | 5% – 10% | % | Input usuario |
| **AvgPrice** | Precio medio de venta del SPREAD de energía | 65 | 20 – 100 | €/MWh | Híbrido (histórico + input usuario) |
| **Impuestos** | Tasa impositiva aplicada | 25% | - | % | Parámetro cálculo |
| **Inflación** | Tasa de inflación anual | 2% | - | % | Parámetro cálculo |

### 1.2 Parámetros Técnicos de la Batería (BESS ASSUMPTIONS)

| Variable | Descripción | Valor ejemplo | Rango válido | Unidad | Origen |
|----------|-------------|---------------|--------------|--------|--------|
| **Rated Installed Power** | Potencia instalada nominal | 50 | - | MW | Input usuario |
| **1/C-Rate** | Capacidad de almacenamiento por MW instalado | 4 | 1 – 8 | MWh/MW | Input usuario |
| **Nominal Power** | Factor de potencia nominal | 1 | - | MW/MW | Input usuario |
| **EqoCycle** | Nº de ciclos de vida útil (lifespan cycles) | 7,000 | 6,000 – 8,000 | ciclos | Input usuario |
| **BESS Lifespan** | Vida útil del proyecto BESS | 15 | 10 – 15 | años | Input usuario |

### 1.3 Parámetros de Eficiencia (EFFICIENCY ASSUMPTIONS)

| Variable | Descripción | Valor ejemplo | Rango válido | Unidad | Origen |
|----------|-------------|---------------|--------------|--------|--------|
| **Initial SoH** | Estado de salud inicial | 100% | 98% – 100% | % | Input usuario |
| **RTE** | Round Trip Efficiency | 84% | 80% – 90% | % | Híbrido (histórico + input usuario) |
| **Degradation** | Tasa de degradación por ciclo | 0.005% | 0.005% – 0.02% | %/ciclo | Híbrido (histórico + input usuario) |
| **SoH (min)** | SoH mínimo garantizado (fin de vida útil) | 75% | 70% – 80% | % | Input usuario |
| **MaxDoD** | Profundidad máxima de descarga | 95% | 80% – 90% | % | Input usuario |
| **MinSoC** | Estado de carga mínimo garantizado | 5% | 5% – 20% | % | Input usuario |

### 1.4 Parámetros de Actividad (ACTIVITY ASSUMPTIONS)

| Variable | Descripción | Valor ejemplo | Rango válido | Unidad | Origen |
|----------|-------------|---------------|--------------|--------|--------|
| **YearCycle** | Nº de ciclos anuales | 466.67 | 300 – 1,000 | ciclos/año | Híbrido (histórico + input usuario) |

### 1.5 Parámetros Calculados / Derivados

| Variable | Fórmula / Derivación | Valor ejemplo | Unidad |
|----------|----------------------|---------------|--------|
| **Capacidad total** | Rated Power × 1/C-Rate | 200 (50×4) | MWh |
| **Potencia salida** | Rated Power × Nominal Power | 50 (50×1) | MW |
| **CAPEX total** | Initial CAPEX × Rated Power | 20,000,000 | € |
| **OPEX total anual** | Annual OPEX × Rated Power | 550,000 | €/año |
| **Ciclos mensuales** | YearCycle / 12 | 38.89 | ciclos/mes |
| **Ciclos diarios** | YearCycle / 365 | 1.28 | ciclos/día |
| **Degradación inicial** | 100% - Initial SoH | 0% (ó 0.25 si SoH=99.75%) | % |

---

## 2. Parámetros de Salida (Outputs)

| Variable | Descripción | Valor ejemplo | Unidad |
|----------|-------------|---------------|--------|
| **ROI** | Retorno sobre la inversión (proyectado a fin de vida útil) | 11.0% | % |
| **VAN (NPV)** | Valor Actual Neto | 24,696,400 | € |

---

## 3. Modelo de Cálculo (Hoja "Cálculos")

Granularidad: **diaria** (DIA 1, DIA 2, ... hasta fin de vida útil)

### 3.1 Variables Calculadas por Periodo

| Variable | Descripción | Unidad |
|----------|-------------|--------|
| **AvailableEnergyCapacity** | Capacidad energética disponible (decrece con degradación) | MWh |
| **Period Degradation** | Degradación acumulada desde el inicio | % |
| **CycleNumber** | Nº de ciclos equivalentes en el periodo (aleatorio) | ciclos |
| **RTE** | Eficiencia del periodo (varía aleatoriamente) | % |
| **AnnualSoldEnergy** | Energía vendida en el periodo | MWh |
| **AvgSpreadSoldPrice** | Precio SPREAD promedio de venta en el periodo | €/MWh |
| **Income** | Ingresos brutos = SoldEnergy × AvgSpreadSoldPrice | € |
| **AnnualOpex** | OPEX diario (OPEX anual / 365) | €/día |
| **PeriodCashFlowIncome** | Flujo de caja del periodo = Income - OPEX | € |
| **Discounted PeriodCashFlow** | Flujo de caja descontado (con tasa de descuento) | € |
| **Accumulated Discounted CashFlow** | Flujo acumulado descontado (inicia en -CAPEX) | € |

### 3.2 Nombres Definidos (Named Ranges)

| Nombre | Referencia | Descripción |
|--------|-----------|-------------|
| `CAPEXxMW` | Inputs!D4 | CAPEX unitario (€/MW) |
| `CAPEX` | Inputs!G4 | CAPEX total = CAPEXxMW × InstalledPower |
| `OPEXanualXMW` | Inputs!D5 | OPEX unitario (€/MW/año) |
| `OPEXANUAL` | Inputs!G5 | OPEX total = OPEXanualXMW × InstalledPower |
| `DiscountRate` | Inputs!D6 | Tasa de descuento |
| `InstalledPower` | Inputs!G3 | Potencia instalada (MW) |
| `EnergyPricexMW` | Inputs!D10 | Precio medio SPREAD (€/MWh) |
| `DEgradation` | Inputs!D11 | Tasa degradación por ciclo |
| `TotalCycles` | Inputs!D12 | Ciclos de vida útil totales |
| `Lifespan` | Inputs!D18 | Vida útil (años) |
| `RTE` | Inputs!D8 | Round Trip Efficiency |
| `DoD` | Inputs!D15 | Profundidad máxima de descarga |
| `ciclosxaño` | Inputs!D17 | Ciclos anuales = TotalCycles / Lifespan |
| `ROI` | Especificaciones!C52:F52 | KPI de retorno de inversión |

### 3.3 Fórmulas Exactas del Excel

**Inputs derivados:**
```
CAPEX_total = CAPEXxMW × InstalledPower
OPEX_total  = OPEXanualXMW × InstalledPower
ciclosxaño  = TotalCycles / Lifespan
MinSoC      = 1 - DoD
```

**Capacidad energética disponible (año 0):**
```
AvailableEnergyCapacity₀ = StorageCapacity_perMW × InstalledPower × Initial_SoH
```

**Capacidad energética disponible (periodo t):**
```
AvailableEnergyCapacity_t = (1 - PeriodDegradation_t) × AvailableEnergyCapacity₀
```

**Degradación acumulada:**
```
PeriodDegradation₁ = DEgradation × CycleNumber₁
PeriodDegradation_t = PeriodDegradation_(t-1) + DEgradation × CycleNumber_t
```

**Energía vendida en el periodo:**
```
AnnualSoldEnergy_t = AvailableEnergyCapacity_t × CycleNumber_t × RTE_t × DoD
```

**Ingresos:**
```
Income_t = AnnualSoldEnergy_t × AvgSpreadSoldPrice_t
```

**OPEX diario:**
```
DailyOpex = OPEXANUAL / 365
```

**Flujo de caja del periodo:**
```
PeriodCashFlow_t = Income_t - DailyOpex
PeriodCashFlow₀  = -CAPEX_total
```

**Flujo de caja descontado:**
```
DiscountedCashFlow_t = PeriodCashFlow_t / (1 + DiscountRate)^(t/365)
```

**Flujo acumulado descontado:**
```
AccumulatedDCF₀ = -CAPEX_total
AccumulatedDCF_t = AccumulatedDCF_(t-1) + DiscountedCashFlow_t
```

**VAN (NPV):**
```
VAN = Σ DiscountedCashFlow_t  (para todos los periodos del año 1 en adelante)
```

**ROI:**
```
ROI = AccumulatedDCF_final / CAPEX_total
```

**Incumplimiento rango garantías:**
```
Si PeriodDegradation_t > (1 - SoH_min) → "SI" (incumplimiento)
Incumplimientos_total = COUNTIF(fila_incumplimientos, 1)
```

**Coste de reposición (Simulaciones):**
```
Coste_reposición = 0.7 × CAPEX × 0.8
```

---

## 4. Representación Gráfica (KPIs)

| Eje | KPI | Rango eje X | Unidad |
|-----|-----|-------------|--------|
| Eje X | Número de ciclos anuales | 6,000 – 8,000 | entries |
| Eje Y₁ | Average energy SPREAD selling price | - | €/MWh |
| Eje Y₂ | Round Trip Efficiency | - | % |
| Eje Y₃ | Degradación | - | % |
| Eje Y₄ | Net Income | - | K€ |

---

## 5. Recomendaciones Inteligentes Reactivas

El sistema genera recomendaciones automáticas según la combinación de parámetros:

| Condición | Recomendación |
|-----------|---------------|
| Degradación con incumplimientos, C-rate alarm, tasa<8%, ROI<tasa, spreads>50€ | Puede haber incumplimientos con el SoH mínimo garantizado. Se recomienda no superar C-rate recomendado |
| tasa>8%, ROI>tasa, spreads>50€ | Similar advertencia de incumplimientos SoH |
| tasa>8%, ROI>tasa, spreads generales | La instalación es moderadamente/aceptablemente rentable. Gestionar horas de compra de energía |
| tasa>8%, ROI>tasa, spreads<30€, degradación al límite | La instalación recupera la inversión pero es poco rentable |
| tasa>8%, ROI>tasa, spreads<30€, degradación<límite | La instalación es aceptablemente rentable |
| ciclos/año < ciclos vida útil/vida útil & ROI<0 | Contexto de precios e infrautilización llevan a no recuperar inversión |
| precio<60€ & ciclos bajos & ROI<0 | Contexto de precios e infrautilización no permiten recuperar inversión |
| precio≥60€ & ciclos bajos & ROI<0 | Contexto de costes e infrautilización no permiten recuperar inversión |
| precio≥60€ & ciclos altos & ROI<0 | Contexto de costes lleva a no recuperar la inversión |
| precio≥60€ & ciclos bajos & ROI<tasa descuento | Se recomienda aumentar el uso de la batería |

---

## 6. Tabla de Simulaciones (Precio SPREAD vs CAPEX)

Matriz de ROI para distintas combinaciones:

| Precio (€/MWh) \ CAPEX (€) | 330,000 | 350,000 | 400,000 | 450,000 | 475,000 |
|-----------------------------|---------|---------|---------|---------|---------|
| 47.5 | -64.9% | -66.9% | -71.0% | -74.2% | -75.6% |
| 50 | -61.5% | -63.7% | -68.2% | -71.7% | -73.2% |
| 55 | -54.7% | -57.3% | -62.6% | -66.8% | -68.5% |
| 60 | -47.9% | -50.9% | -57.1% | -61.8% | -63.8% |
| 65 | -41.2% | -44.5% | -51.5% | -56.9% | -59.1% |
| 70 | -34.4% | -38.2% | -45.9% | -51.9% | -54.4% |
| 76 | -26.3% | -30.5% | -39.2% | -45.9% | -48.8% |

> Nota: Coste de reposición estimado como `0.7 × CAPEX × 0.8`

---

## 7. Fuentes de Precios de Mercado

| Fuente | Descripción | Granularidad | Uso |
|--------|-------------|--------------|-----|
| **OMIE** | Operador del Mercado Ibérico de Energía | Horaria (€/MWh) | Precios mercado diario e intradiario |
| **Esios (REE)** | Red Eléctrica de España | Horaria (€/kWh) | Precios PVPC y mayorista |
| **OMIP** | Mercado de Futuros | Mensual/Trimestral/Anual | Contratos de futuros eléctricos |

---

## 8. Pila de Servicios BESS

| Categoría | Servicio | Precio referencia |
|-----------|----------|-------------------|
| **Generación** | Arbitraje | 30-90 €/MWh/ciclo |
| **Generación** | Suministro eléctrico | - |
| **Serv. Complementarios** | Control 1ario frecuencia | <30seg, obligatorio no remunerado |
| **Serv. Complementarios** | Control 2ario frecuencia | <100seg, 5-15 €/MW/h + 50-100 €/MWh |
| **Serv. Complementarios** | Control 3ario frecuencia | 40-80 €/MWh |
| **Serv. Complementarios** | Reserva de capacidad | 20-50 €/MW/año |
| **Infraestructura TX** | Control tensión / inercia sintética | 5-10 €/MW/h |
| **Infraestructura TX** | Resolución congestiones | 30-60 €/MWh |
| **Infraestructura DX** | Soporte de capacidad | 5-10 €/MW/h |
| **Infraestructura DX** | Soporte contingencia red | 20-50 €/MWh |
| **Gestión Demanda** | Peak shaving | 10-30 €/MW/h |
| **Gestión Demanda** | Gestión costes energía | 20-40 €/MWh |

---

## 9. Resumen de Rangos para Análisis de Sensibilidad

| Parámetro | Mínimo | Máximo | Impacto esperado |
|-----------|--------|--------|------------------|
| CAPEX | 300,000 €/MW | 1,000,000 €/MW | Alto (inversión inicial) |
| OPEX | 11,000 €/MW/año | 22,500 €/MW/año | Medio (coste recurrente) |
| Discount Rate | 5% | 10% | Alto (valoración VAN) |
| RTE | 80% | 90% | Alto (eficiencia energética) |
| Degradación | 0.005%/ciclo | 0.02%/ciclo | Alto (vida útil efectiva) |
| Precio SPREAD | 20 €/MWh | 100 €/MWh | Alto (ingresos) |
| DoD máximo | 80% | 90% | Medio (uso vs desgaste) |
| MinSoC | 5% | 20% | Medio (energía disponible) |
| Ciclos anuales | 300 | 1,000 | Alto (ingresos vs degradación) |
| Ciclos vida útil | 6,000 | 8,000 | Alto (duración total) |
| SoH mínimo | 70% | 80% | Medio (duración proyecto) |
| BESS Lifespan | 10 años | 15 años | Alto (horizonte inversión) |
| 1/C-Rate | 1 MWh/MW | 8 MWh/MW | Alto (capacidad almacenamiento) |

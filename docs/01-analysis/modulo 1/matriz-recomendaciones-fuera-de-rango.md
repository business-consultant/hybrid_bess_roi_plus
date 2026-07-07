# Matriz de recomendaciones — Alarmas de históricos "fuera de rango"

> Referencia capturada de la pizarra de diseño (imagen compartida por el equipo,
> 2026-06). Documento base para la **mejora futura de la matriz de decisiones**
> que genera las recomendaciones (`recommendations/decision_tree.py`).
>
> Pendiente: adjuntar aquí el PNG original de la pizarra. Si quieres conservar la
> captura, déjala en esta carpeta como `matriz-recomendaciones-fuera-de-rango.png`
> y se enlazará desde este documento.

---

## 1. Objetivo

Ampliar las recomendaciones con **avisos de operación fuera de los rangos
aconsejados** detectados en el histórico. Se complementa con la futura
generación de datos sintéticos que inyectará **desviaciones moderadas** en
variables sensibles del contrato (temperatura, RTE, SoH, C-Rate, DoD, SoC) para
que estas alarmas tengan datos que disparar.

## 2. Variables vigiladas (alarmas fuera de rango)

Bloque "Alarmas de históricos fuera de rango" de la pizarra:

| Variable | Símbolo en el mensaje | Naturaleza |
|----------|----------------------|------------|
| C-Rate | `C-RATE` | Potencia / capacidad fuera de diseño |
| Round Trip Efficiency | `RTE` | Eficiencia por debajo de lo garantizado |
| Temperatura | `TRA` | Temperatura de operación fuera de rango |
| Mínimo SoC garantizado | `SoC` | Descarga por debajo del SoC mínimo |
| Máxima profundidad de descarga (DoD %) | `DoD` | DoD por encima del máximo |

**Mensaje generado (plantilla):**

- ES: `"El sistema BESS ha operado puntualmente fuera de los rangos aconsejados en términos de #C-RATE;RTE;TRA;SoC;DoD#"`
- EN: `"BESS system has occasionally operated out of range regarding #C-RATE;RTE;TRA;SoC;DoD#"`

> El marcador `#...#` se rellena dinámicamente solo con las variables que
> efectivamente excedieron su rango en el histórico.

## 3. Ramas de la matriz de decisiones

### 3.1 ROI (%)
(`i` = tasa de descuento)

| Condición | Mensaje |
|-----------|---------|
| ROI > i & ROI > 8% | Políticas de operación e inversión BESS rentables |
| ROI ≈ i & ROI > 8% | Inversión rentable; conveniente diversificar beneficios |
| ROI > i & ROI < 8% | Rentabilidad moderada |
| ROI < i & ROI > 8% | Rentabilidad moderada-baja |
| ROI < i & 0% ≤ ROI < 8% | Baja rentabilidad; aceptable solo si proyecto estratégico / bajo riesgo / sin alternativas |
| ROI < i & ROI < 0% | Inversión no rentable bajo parámetros actuales |

### 3.2 Degradación del último año (LastYearDegr)

| Condición | Mensaje |
|-----------|---------|
| LastYearDegr ≥ 1 − SoHmin | El ciclado compromete el SoH mínimo recomendado al fin de vida (ALERTA) |
| LastYearDegr < 1 − SoHmin | Queda margen: se recomienda ciclar más sin llegar al límite de degradación |

### 3.3 Discount Rate (tasa de descuento)

Tramos: `0% < i < 8%` · `8% ≤ i < 10%` · `10% < i < 15%`.
→ "Se recomienda revisar #la tasa de descuento usada#&#el coste de mtto#&#el
Round Trip Efficiency# y evaluar si es aplicable un valor más favorable."

### 3.4 OPEX (€/MW/año)

Tramos: `OPEX < 10K` · `10K ≤ OPEX < 15K` · `15K ≤ OPEX < 30K`.
→ **Avisar si fuera de rango** y recomendar revisar coste de mantenimiento.

### 3.5 RTE (Round Trip Efficiency)

Tramos: `RTE < 80%` · `80% ≤ RTE < 90%` · `90% ≤ RTE`.
→ Si bajo, recomendar revisar eficiencia / O&M.

### 3.6 Lifespan (vida útil, años)

Tramos: `Lifespan ≥ 20` · `15 ≤ Lifespan < 20` · `10 < Lifespan < 15` · `Lifespan < 10`.
→ "Considere aumentar la vida útil de su instalación BESS."

### 3.7 Retribution Price (precio medio de venta, €/MWh)

Tramos: `spread > 30€` · `30€ < spread < 45€` · `45€ ≤ spread`.
→ "La retribución promedio sugiere revisar estrategias de mercado y/o considerar
nuevos mercados/servicios."

## 4. Mensaje compuesto (ejemplo de la pizarra)

> **EJEMPLO 1:**
> "El sistema BESS ha operado puntualmente fuera de los rangos aconsejados en
> términos de #C-RATE;RTE;TRA;SoC;DoD#"
> + "Actualmente la inversión BESS es rentable pero el coste del capital
> recomienda buscar también beneficios indirectos."
> + "Queda algo de margen para aumentar el nro. de ciclos sin llegar al límite de
> la degradación permitida, se recomienda intentar ciclar más la batería."
> + "Se recomienda revisar #la tasa de descuento usada#&#el coste de mtto#&#el
> Round Trip Efficiency# y evaluar si es aplicable un valor más favorable."
> + "..."

La recomendación final es la **concatenación** de los mensajes activos de cada
rama, empezando por el aviso de fueras de rango histórico.

## 5. Notas para la implementación (futuro)

- Mapear cada variable vigilada a un umbral configurable (idealmente en
  `app_config` / `DEFAULT_ADVANCED_CONFIG`).
- La detección de "fuera de rango" se hace sobre el **histórico** del dataset
  activo (antes de HOY).
- Conectar con la generación sintética de anomalías moderadas (temperatura, RTE,
  SoH, C-Rate, DoD, SoC) para validar que las alarmas se disparan.
- Revisar coherencia con el árbol existente en
  [arbol-decisiones-bess.md](arbol-decisiones-bess.md).

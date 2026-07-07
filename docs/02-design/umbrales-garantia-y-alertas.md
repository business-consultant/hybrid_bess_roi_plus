# Umbrales de garantía y fueras de rango — APM BESS

Documento de referencia de **todos los umbrales** usados en el prototipo APM
para evaluar cumplimiento de garantía (*warranty compliance*) y para detectar
operación fuera de rango. Para cada umbral se indica su **valor por defecto**,
**dónde se define / configura**, **qué dispara** y **en qué se basa**.

> Importante: los valores por defecto son **órdenes de magnitud realistas de
> referencia para un BESS de iones de litio (LFP/NMC) de utility-scale**, no una
> cláusula contractual concreta. Todos los que tienen impacto operativo son
> **parametrizables** desde *Configuración* y se persisten en `app_config`. La
> fuente última de verdad es el contrato de suministro / garantía del fabricante
> de cada proyecto; estos valores se deben sustituir por los de cada planta.

Los datos por unidad de la vista de elementos son **sintéticos y deterministas**
(semilla estable): sirven para demostrar el comportamiento del semáforo, no son
telemetría real.

---

## 1. Resumen de fuentes

| Bloque | Fichero | Configurable en |
| --- | --- | --- |
| Semáforo de garantía (cabecera BMS) | `engine/elements.py` → `DEFAULT_WARRANTY_THRESHOLDS` | *Configuración › Alertas Históricas › Semáforo de garantía* |
| Estado por módulo BMS (tabla) | `engine/elements.py` → `build_bess_snapshot` | umbral térmico vía `alarm_temp_critical_c` |
| Estado por convertidor PCS (tabla) | `engine/elements.py` → `build_pcs_snapshot` | (constantes internas) |
| Alarmas históricas (registro de eventos) | `recommendations/alarms.py` → `check_historical_alarms` | *Configuración › Alertas Históricas › Umbrales de alerta* |
| Inyección de anomalías (histórico sintético) | `data/synthetic.py` → `_inject_anomalies` | *Configuración › Inyección de anomalías* |
| Claves persistidas | `storage/app_config.py` → `DEFAULT_ADVANCED_CONFIG` | base de datos `app_config` |

---

## 2. Semáforo de garantía (cabecera *Warranty compliance*)

Colorea cada KPI de la cabecera del detalle de **Módulos BESS** en
verde (disponible) / ámbar (aviso) / rojo (fallo). Definido en
`DEFAULT_WARRANTY_THRESHOLDS` y aplicado en `build_bess_warranty_kpis`.

La lógica de grados es:

- **Magnitudes donde *más alto es peor*** (`_grade_high`): `fallo` si
  `valor > límite`; `aviso` si `valor > límite − banda_aviso`; verde en otro caso.
- **Magnitudes donde *más bajo es peor*** (`_grade_low`, solo SoH): `fallo` si
  `valor < suelo`; `aviso` si `valor < suelo + margen_aviso`; verde en otro caso.

| KPI | Clave | Defecto | Banda de aviso | Sentido | Base del criterio |
| --- | --- | --- | --- | --- | --- |
| **SoH mínimo** | `soh_min` (+ `soh_warn_margin`) | **80 %** | +2 pp (aviso < 82 %) | bajo = peor | El **80 % de SoH** (capacidad/energía retenida) es el final de vida útil de garantía típico de los fabricantes de baterías de Li-ion en proyectos BESS. El margen de 2 pp avisa antes de incumplir. |
| **SoH spread (grupo)** | `soh_spread_max` | **5 pp** | 30 % del límite (aviso > 3,5 pp) | alto = peor | Dispersión máx. de SoH entre módulos: mide el **desequilibrio/envejecimiento desigual** de la flota. Una dispersión > ~5 pp indica módulos degradándose a ritmos distintos (mantenimiento/recambio selectivo). Criterio de ingeniería, no contractual. |
| **DoD máx. (grupo)** | `dod_max` | **100 %** | 1 pp (aviso > 99 %) | alto = peor | Profundidad de descarga máx. admisible por ciclo. Muchas garantías limitan el **DoD operativo** (p. ej. 90–100 %) para preservar la vida; ciclar al 100 % de forma sostenida acelera la degradación. |
| **Tª máx. celda absoluta** | `cell_temp_max` | **40 °C** (= `alarm_temp_critical_c`) | 2 °C (aviso > 38 °C) | alto = peor | Límite térmico de seguridad/garantía de celda. Las celdas de Li-ion tienen su **ventana óptima ~15–35 °C**; por encima de ~40 °C se acelera la degradación y aumenta el riesgo. Reutiliza el umbral de seguridad de alarmas. |
| **Ciclos equiv. máx.** | `cycles_max` | **6 000** | 15 % del límite (aviso > 5 100) | alto = peor | Tope contractual de **ciclos equivalentes**. Las garantías BESS suelen expresarse como "X años o N ciclos, lo que ocurra antes"; 6 000 ciclos es un orden de magnitud habitual para LFP en arbitraje diario. |

KPIs **informativos** de la cabecera (sin semáforo, mostrados en azul): *Desvío
máx. SoH*, *Desvío máx. Tª*, *Intensidad máxima*, *Desv. máx. tensión celda*.
Señalan el módulo "peor" de cada magnitud para inspección, pero no tienen un
límite de garantía asociado en el prototipo.

### Claves persistidas asociadas (`app_config`)

```python
"alarm_soh_min": 0.80,              # suelo de SoH (compartido con alarmas) → ×100 en el semáforo
"alarm_temp_critical_c": 40.0,      # Tª crítica (compartida con alarmas)
"warranty_soh_spread_max_pp": 5.0,  # dispersión máx. de SoH del grupo (pp)
"warranty_cycles_max": 6000.0,      # tope contractual de ciclos equivalentes
"warranty_dod_max_pct": 100.0,      # DoD máx. admisible por ciclo (%)
```

> El **suelo de SoH** y la **Tª crítica** se reutilizan de los umbrales de
> alerta histórica (sección 4) para mantener una única definición coherente
> entre el registro de eventos y el semáforo.

---

## 3. Estado por unidad en las tablas de detalle

Cada fila (módulo / convertidor) recibe un estado 🟢/🟡/🔴 a partir de reglas
combinadas. Son umbrales **internos de visualización** (no parametrizables salvo
la Tª crítica), calibrados para que un grupo sano muestre mayoría en verde y una
minoría en aviso.

### 3.1 Módulos BESS (`build_bess_snapshot`)

| Estado | Condición (OR) | Base |
| --- | --- | --- |
| 🔴 **Fallo** | `SoH < 80,5 %` **o** `Tª máx. celda > Tª_crítica + 2 °C` **o** `Desv. tensión > 55 mV` | Por debajo del suelo de SoH, sobre-temperatura clara o desbalanceo de celdas severo. |
| 🟡 **Aviso** | `SoH < 82 %` **o** `Tª máx. celda > Tª_crítica − 2 °C` **o** `Desv. tensión > 38 mV` | Margen de proximidad al límite (degradación incipiente, calentamiento o desbalanceo moderado). |
| 🟢 **Disponible** | resto | Operación dentro de rango. |

- `Tª_crítica` = `alarm_temp_critical_c` (defecto 40 °C, configurable).
- **Desviación de tensión entre celdas (mV)**: el balanceo se degrada con el
  envejecimiento; ~55 mV de spread se considera desbalanceo a corregir y ~38 mV
  una señal temprana. Valores de referencia de ingeniería de BMS.

### 3.2 Convertidores PCS (`build_pcs_snapshot`)

| Estado | Condición (OR) | Base |
| --- | --- | --- |
| 🔴 **Fallo** | `Disponibilidad < 90 %` **o** `PR inversor < 78 %` | Indisponibilidad relevante o rendimiento muy por debajo de lo esperado. |
| 🟡 **Aviso** | `Disponibilidad < 95 %` **o** `PR inversor < 82 %` | Proximidad a incumplir disponibilidad contractual o caída de rendimiento. |
| 🟢 **Disponible** | resto | Operación nominal. |

- **Disponibilidad ≥ 95 %** es un objetivo contractual habitual para inversores
  de planta; por debajo de 90 % se considera incidencia.
- **PR (performance ratio) ~78–82 %** se alinea con el RTE mínimo contractual
  (sección 4): el PR del inversor deriva del rendimiento de ciclo medido.

---

## 4. Alarmas históricas (registro de eventos críticos)

`recommendations/alarms.py` escanea el histórico por intervalos y registra los
episodios fuera de rango, clasificados por **categoría de criticidad**
(Seguridad / Salud del activo / Garantía contractual).

| Magnitud | Clave | Defecto | Categoría | Severidad | Dispara cuando | Base |
| --- | --- | --- | --- | --- | --- | --- |
| **Temperatura** | `alarm_temp_critical_c` | **40 °C** | Seguridad | 🔴 crítica | `Tª > 40 °C` | Límite térmico de seguridad de celda Li-ion (ventana óptima ~15–35 °C; por encima de ~40 °C se acelera la degradación y crece el riesgo). |
| **RTE** (round-trip) | `alarm_rte_min` | **0,78 (78 %)** | Garantía contractual | 🟡 aviso | `RTE < 78 %` | Rendimiento de ciclo mínimo garantizado típico de un BESS bien dimensionado (RTE inicial ~85–90 %; el suelo contractual suele rondar 75–80 %). |
| **SoH** | `alarm_soh_min` | **0,80 (80 %)** | Salud / Garantía | 🔴 crítica | `SoH < 80 %` | Final de vida útil de garantía estándar (80 % de capacidad retenida). |

Cada evento agrega: recuento de intervalos afectados, primer y último
*timestamp*, valor peor (pico/mínimo) y el **subelemento responsable**
(`Sistema térmico / HVAC`, `PCS / Inversor BESS`, `Módulos BESS`) usado para el
atajo a la pantalla de detalle.

### Claves persistidas (`app_config`)

```python
"alarm_temp_critical_c": 40.0,  # seguridad
"alarm_rte_min": 0.78,          # garantía de rendimiento
"alarm_soh_min": 0.80,          # salud / garantía de capacidad
```

---

## 5. Inyección de anomalías (histórico sintético)

Para que el registro de eventos tenga contenido demostrable, `data/synthetic.py`
(`_inject_anomalies`) introduce episodios puntuales **fuera de rango** en el
histórico generado. Son parámetros de **generación de datos de demostración**,
no umbrales de evaluación. Los episodios duran 1–4 intervalos consecutivos y se
aplican después del recorte base para que persistan (deterministas por semilla).

| Anomalía | Clave | Defecto | Rango aplicado | Base |
| --- | --- | --- | --- | --- |
| **Activar inyección** | `anomaly_enable` | `True` | — | Permite desactivar las anomalías para datasets "limpios". |
| **Sobre-temperatura: episodios/año** | `anomaly_temp_events_per_year` | **6** | — | Frecuencia plausible de picos térmicos anuales en operación real. |
| **Sobre-temperatura: pico** | `anomaly_temp_peak_c` | **46 °C** | recortado a `[Tª_crítica + 0,5 °C, 60 °C]` | Pico por encima del umbral de seguridad (40 °C) para garantizar que se registre el evento, acotado a un máximo físico de 60 °C. |
| **Caída de RTE: episodios/año** | `anomaly_rte_events_per_year` | **4** | — | Frecuencia plausible de caídas de rendimiento anuales. |
| **Caída de RTE: valor** | `anomaly_rte_dip` | **0,72 (72 %)** | recortado a `[0,50, RTE_mín − 0,005]` | Caída por debajo del mínimo contractual (78 %) para que dispare el evento de garantía, acotada a un mínimo físico de 50 %. |

---

## 6. Umbrales de recomendación de inversión (contexto, no garantía)

Por completitud: el motor de **recomendaciones ROI** usa otro conjunto de
umbrales (`rec_*` en `app_config`) para clasificar la bondad de una inversión
(ROI, tasa de descuento, OPEX, RTE, vida útil, precio). **No** son umbrales de
garantía ni de operación fuera de rango del activo; pertenecen al dominio de
asesoramiento económico y se documentan en el árbol de decisiones
([docs/01-analysis/modulo 1/arbol-decisiones-bess.md](../01-analysis/modulo%201/arbol-decisiones-bess.md)).

| Clave | Defecto | Significado |
| --- | --- | --- |
| `rec_roi_high_threshold` | 0,08 | ROI alto (atractivo) |
| `rec_discount_rate_ok` / `_warning` | 0,08 / 0,10 | Tasa de descuento aceptable / límite |
| `rec_opex_ok` / `_warning` | 10 000 / 15 000 | OPEX anual aceptable / límite |
| `rec_rte_ok` / `_warning` | 0,86 / 0,80 | RTE bueno / límite |
| `rec_lifespan_ok` / `_warning` | 15 / 10 | Vida útil (años) buena / límite |
| `rec_price_ok` / `_warning` | 45,0 / 30,0 | Precio spread (€/MWh) bueno / límite |

---

## 7. Cómo cambiar los umbrales

1. **Interfaz**: *Configuración › Alertas Históricas y Anomalías (APM)* expone
   los umbrales de alerta, el semáforo de garantía y los parámetros de anomalías.
   "Guardar configuración" persiste en `app_config`.
2. **Por defecto en código**: `storage/app_config.py` (`DEFAULT_ADVANCED_CONFIG`)
   y `engine/elements.py` (`DEFAULT_WARRANTY_THRESHOLDS`).
3. **Para un proyecto real**: sustituir los valores por los del **contrato de
   garantía del fabricante** (suelo de SoH, tope de ciclos, RTE mínimo, límites
   térmicos y de DoD) y por los **objetivos de disponibilidad** del PPA / O&M.

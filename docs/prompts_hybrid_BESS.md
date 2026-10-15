# Prompt global: señales BESS híbridas

## Encargo y alcance

Genera datos sintéticos para un entorno de pruebas de una planta BESS híbrida,
preparado para una futura conexión con un SCADA local. El resultado debe contener **solo** las
señales de este documento, con una fila por minuto y el mismo convenio de
timestamp que `bessplant1`.

Usa internamente una resolución de 5-10 segundos para relaciones no lineales y
materializa a un minuto al final. Usa `AVG-1M` para medidas continuas,
`MAX-1M`/`MIN-1M` para extremos, `LAST-1M` para niveles, consignas y límites,
`LAST-1M + Delta` para contadores, y el último valor para `ESTADO-1M` y
`EVENTO-1M`. Las sumas y restas lineales pueden calcularse tras agregar; los
productos y ratios deben calcularse antes de agregar.

## Orden causal obligatorio

Genera BMS/rack, BBANK y BTMS/FPS; después PCS; después BCTRL; finalmente
EMS/PPC, CT y POI. Las agregaciones se derivan siempre del nivel inferior.
Propaga eventos: `SmokeSensorState -> FireAlarm -> MFFPAlarm -> FStop`.
Un `FStop` fuerza BMS e inversor a parada/fallo y potencia activa/DC a cero.
Cuando CT no sea `Normal`, las potencias POI deben tender a cero.

## Catálogo exclusivo de señales

| Elemento | Señales |
|---|---|
| BMS (SBMU/MBMU) | `SystemStatus` (ESTADO), `SOC` (LAST), `SOH` (LAST), `DCCurrent` (AVG), `DCVoltage` (AVG), `DCPower` (AVG, V*I raw), `MaxCellTemp` (MAX), `MinCellTemp` (MIN), `AvgCellTemp` (AVG), `MaxCellVolt` (MAX), `MinCellVolt` (MIN), `AvgCellVolt` (AVG), `DCPowerChargeLim` (LAST), `DCPowerDischargeLim` (LAST), `DCCurrentChargeLim` (LAST), `DCCurrentDischargeLim` (LAST) |
| BBANK | `TemperatureSensorXX` (AVG), `MaxTemp` (MAX raw de todos los sensores), `MaxTempAlarm` (EVENTO), `BTMSAlarm` (EVENTO), `MFFPAlarm` (EVENTO), `FStop` (EVENTO) |
| PCS | `ActivePower` (AVG), `ReactivePower` (AVG), `CosPhi` (AVG, ratio raw), `Frequency` (AVG), `DCVoltage` (AVG), `DCPower` (AVG), `DCCurrent` (AVG), `InverterState` (ESTADO), `TotalEnergy` (LAST + Delta), `TotalImportedEnergy` (LAST + Delta), `InverterAvailability` (DERIVADA), `Performance` (DERIVADA), `SOC` (LAST) |
| BCTRL | `ActivePower` (AVG), `ReactivePower` (AVG), `Setpoint_ActivePower` (LAST), `Setpoint_ReactivePower` (LAST), `SOC` (LAST) |
| BTMS/HVAC | `Temperature` (AVG), `Humidity` (AVG), `Pressure` (AVG), `AirFlow` (AVG), `PowerConsumption` (AVG), `ComponentStatus` (ESTADO), `ControlSignal_Temp` (LAST) |
| FPS/SCI | `SystemStatus` (ESTADO), `SmokeSensorState` (EVENTO), `FireAlarm` (EVENTO), `ExtinctionDischarge` (EVENTO), `MFFPAlarm` (EVENTO) |
| UPS | `SystemStatus` (ESTADO) |
| CT/Power Station | `SystemStatus` (ESTADO) |
| ANL/MTR | `POI_ActivePower` (AVG), `POI_ReactivePower` (AVG) |
| EMS/PPC | `ControlMode` (ESTADO), `Setpoint_ActivePower` (LAST), `Setpoint_ReactivePower` (LAST), `ChargeLimitFromGrid` (LAST), `DischargeLimitToGrid` (LAST) |

## Reglas físicas y de negocio

- BMS: `SOC` integra corriente/potencia y permanece en 5-95%; sube cargando y baja descargando. `SOH` decrece lentamente, sin recuperaciones. La tensión sigue la curva OCV-SOC con caída $I R$; `DCPower = DCVoltage * DCCurrent` a grano fino. Respeta siempre los límites dinámicos de corriente y potencia.
- Temperaturas: `MaxCellTemp >= AvgCellTemp >= MinCellTemp`. Las temperaturas aumentan con $I^2R$, ambiente y peor BTMS. `MaxCellVolt >= AvgCellVolt >= MinCellVolt`; el desbalance aumenta al bajar SOH. Para LFP, usa aproximadamente 2.5-3.65 V por celda y diferencia normal inferior a 50-100 mV.
- BBANK/BTMS: sensores correlacionados y sin saltos; `MaxTemp` se calcula sobre máximos raw. `MaxTempAlarm` usa histéresis. HVAC mantiene 20-25 °C con retardo, humedad 20-70%, y presión/caudal/consumo coherentes. Un fallo de componente reduce caudal y presión y activa `BTMSAlarm`.
- PCS: no hay `ActivePower` ni `ReactivePower` si `InverterState` no es `Running`. Respeta $P^2+Q^2 <= S_{nominal}$. `Performance` alcanza típicamente 96-98% a 50-80% de carga. `SOC` replica el BMS. Los contadores son monótonos: $Delta kWh \approx P_{avg,kW}/60$; importación y exportación no crecen a la vez.
- Control: BCTRL suma PCS y reparte consignas. EMS genera consignas escalonadas dentro de `ChargeLimitFromGrid`, `DischargeLimitToGrid` y POI; en modo Manual permanecen constantes. El CT agrega maniobra/fallo y condiciona POI. POI suma PCS menos auxiliares y no supera el límite de interconexión.
- Eventos: estados y alarmas son poco frecuentes, discretos y causales. FPS suele estar `Armado`; humo precede incendio, extinción solo aparece tras incendio confirmado. UPS permanece en `Red`, pasa a `Batería` ante huecos de tensión y a `Fault` al agotarse.

## Validación automática requerida

Antes de entregar, valida timestamp y cobertura minutal, tipos/unidades, rangos,
invariantes de máximos y mínimos, $SOC \in [0,100]$, SOH no creciente,
contadores monótonos, coherencia $P/V/I$, capacidad aparente PCS, límites de
potencia/corriente, agregaciones BCTRL/POI y todas las propagaciones de eventos.
Entrega además un informe de validación con recuentos de fallos y muestras de
cada escenario anómalo.

## Prompts individuales de implementación

Las tablas siguientes son la especificación operativa completa. La columna
**Prompt** indica cómo generar cada señal; los nombres se interpretan dentro del
elemento de su fila, por lo que nombres repetidos entre elementos no son el
mismo tag.

### BMS: SBMU y MBMU

| Señal | Unidad y grano | Prompt |
|---|---|---|
| `SystemStatus` | Estado, ESTADO-1M | Máquina de estados `Standby/Running/Charging/Discharging/Alarm/Fault/Offline`, gobernada por Start/Stop/Reset del PCS y `FStop`. Prohíbe `Fault -> Running` sin Reset. En `Fault` u `Offline`, congela SOC, SOH y medidas DC en el último valor válido. Generarla antes del resto del BMS. |
| `SOC` | %, LAST-1M | Integra a grano fino mediante Coulomb counting: $Delta SOC=-I Delta t/Capacidad_{nominal}$. Acota la pendiente por C-rate, sube en carga y baja en descarga. Mantén 5-95% salvo escenarios extremos y replica el mismo valor en PCS/BCTRL. |
| `SOH` | %, LAST-1M | Evolución mensual/anual lenta y monótonamente decreciente desde 100% a un suelo 70-80%. Acelera con temperatura de celda fuera de óptimo o DoD alto. No introduzcas saltos ni recuperaciones salvo reemplazo explícito. |
| `DCCurrent` | A, AVG-1M | Genera corriente raw coherente con `DCPower = DCVoltage * DCCurrent`, con signo según convenio de planta. Respeta límites de carga/descarga instantáneos, ruido de sensor de hasta ±0.5% fondo de escala y respuesta rápida ante rampas de BCTRL. Para pruebas de transiciones, añade MIN/MAX auxiliar solo si se solicita. |
| `DCVoltage` | V, AVG-1M | Usa OCV(SOC) de química LFP por celdas en serie menos caída $I R_{interna}$. Mantén el resultado entre límites de tensión de celda multiplicados por el número de celdas. |
| `DCPower` | kW, AVG-1M derivada no lineal | Calcula $V*I$ instante a instante antes de agregar, con el signo de carga/descarga. Respeta límites de potencia y sigue con rampa de primer orden la consigna BCTRL. Debe concordar con el PCS, menos pérdidas de conducción. Nunca multipliques los AVG-1M. |
| `MaxCellTemp` | °C, MAX-1M | Máximo de muestras raw; aumenta con $I^2R$, temperatura de banco y peor BTMS. Rango operativo -20 a 55 °C; por encima de 45-50 °C activa alarma. Debe ser siempre mayor o igual que `AvgCellTemp`. |
| `MinCellTemp` | °C, MIN-1M | Mínimo raw, dentro del rango operativo. Mantén diferencia con máxima normalmente inferior a 5-8 °C; una mayor diferencia representa desequilibrio térmico, sensor o refrigeración defectuosa. |
| `AvgCellTemp` | °C, AVG-1M | Promedio ponderado entre extremos, con inercia respecto a banco y ciclo BTMS. Es referencia para degradación SOH; pondera por celdas válidas cuando el número de muestras cambie. |
| `MaxCellVolt` | V, MAX-1M | Deriva de OCV(SOC), con dispersión sobre el promedio que crece al reducirse SOH. No excedas 3.65 V/celda LFP; un exceso representa sobretensión. |
| `MinCellVolt` | V, MIN-1M | Sigue OCV(SOC), sin bajar de 2.5 V/celda LFP. En estado sano, conserva diferencia Max-Min inferior a 50-100 mV; valores mayores representan desbalanceo. |
| `AvgCellVolt` | V, AVG-1M | OCV(SOC) con mesetas de química y corrección IR. Valida `DCVoltage ~= AvgCellVolt * número de celdas en serie` sobre el mismo grano. |
| `DCPowerChargeLim` | kW, LAST-1M | Derating nominal suave al aproximarse SOC a 100%, con temperaturas frías/calientes o SOH degradado. Solo admite salto abrupto en alarma. |
| `DCPowerDischargeLim` | kW, LAST-1M | Aplica el mismo derating, orientado a SOC bajo y temperaturas altas de celda. |
| `DCCurrentChargeLim` | A, LAST-1M | Calcula con potencia de carga límite y tensión instantánea: $I_{lim} ~= P_{lim}/V$. Sincroniza derating térmico/SOC con `DCPowerChargeLim`. |
| `DCCurrentDischargeLim` | A, LAST-1M | Calcula con `DCPowerDischargeLim` y tensión instantánea; replica su derating. |

### BBANK: Battery Bank Enclosure

| Señal | Unidad y grano | Prompt |
|---|---|---|
| `TemperatureSensorXX` | °C, AVG-1M | Genera un tag por sensor con variación gradual, correlación entre sensores próximos, temperatura exterior y ciclo BTMS. Conserva internamente máximos raw para `MaxTemp`. |
| `MaxTemp` | °C, MAX-1M derivada | Máximo raw de todos los sensores del banco, no máximo de promedios. Normalmente queda por debajo de `MaxCellTemp`; cruza el umbral, por ejemplo 45 °C, para disparar la alarma. |
| `MaxTempAlarm` | Booleano, EVENTO-1M | Activa exclusivamente al cruzar `MaxTemp` el umbral y desactiva con histéresis para evitar parpadeo. |
| `BTMSAlarm` | Booleano, EVENTO-1M | Vincula a `ComponentStatus=Fault` o temperatura sostenida fuera de consigna. Debe ser infrecuente y persistir hasta resolver el fallo HVAC. |
| `MFFPAlarm` | Booleano, EVENTO-1M | Réplica minuto a minuto de `FireAlarm`/humo del FPS asociado; nunca la generes independiente. |
| `FStop` | Booleano, EVENTO-1M | Evento raro que fuerza BMS y PCS asociado a parada/fallo y lleva `ActivePower` y `DCPower` a cero de inmediato, sin rampa. Debe generarse antes de las señales afectadas. |

### PCS: Power Conversion System

| Señal | Unidad y grano | Prompt |
|---|---|---|
| `ActivePower` | kW, AVG-1M | Sigue la consigna BCTRL mediante rampa de primer orden, sin superar potencia nominal. Es la base de agregación BCTRL/POI y debe ser cero si el inversor no está `Running`. |
| `ReactivePower` | kvar, AVG-1M | Sigue modo EMS: consigna fija, cos phi o Q(V), cumpliendo $P^2+Q^2 <= S_{nominal}$. |
| `CosPhi` | Sin unidad, AVG-1M derivada no lineal | Calcula raw como $P/sqrt(P^2+Q^2)$ y agrega; rango [-1,1] con signo de cuadrante. Si se deriva tras agregar, márcalo como aproximación. |
| `Frequency` | Hz, AVG-1M | Sigue frecuencia POI con desviaciones dinámicas ±0.02-0.05 Hz; excursiones mayores solo en huecos/desconexiones. Genera MIN/MAX auxiliar solo cuando haya pruebas de eventos de red. |
| `DCVoltage` | V, AVG-1M | Réplica de tensión BMS asociada, menos una pequeña caída de cableado; mantiene tendencia con SOC. |
| `DCPower` | kW, AVG-1M derivada no lineal | En descarga, divide potencia AC por rendimiento; en carga, aplícala con rendimiento. Debe coincidir con BMS salvo pérdidas PCS y calcularse antes de agregar. |
| `DCCurrent` | A, AVG-1M derivada no lineal | Calcula raw como `DCPower/DCVoltage`, consistente con BMS salvo pérdidas de conducción. |
| `InverterState` | Estado, ESTADO-1M | Máquina `Stopped/Starting/Running/Fault/Standby`, guiada por comandos y BMS. Genera antes de P/Q; fuera de `Running`, P/Q son cero. |
| `TotalEnergy` | kWh, LAST-1M + Delta | Contador monótono de exportación integrando potencia de descarga. Verifica $Delta kWh ~= P_{avg,kW}/60$. Solo puede reiniciarse mediante evento de reset explícito. |
| `TotalImportedEnergy` | kWh, LAST-1M + Delta | Contador monótono de importación integrando potencia de carga. No puede aumentar en el mismo instante que `TotalEnergy`. |
| `InverterAvailability` | %, DERIVADA | Calcula en ventana diaria o mensual como porcentaje fuera de `Fault/Offline`; si se persiste por minuto, replica el último resultado de la ventana. Habitual >95%. |
| `Performance` | %, DERIVADA | Curva campana por carga parcial: inferior en extremos y máximo 96-98% alrededor de 50-80% de nominal. No la uses como fuente para recalcular P/DC. |
| `SOC` | %, LAST-1M | Réplica exacta o con desfase mínimo del SOC BMS asociado; no cálculo independiente. |

### BCTRL: controlador BESS

| Señal | Unidad y grano | Prompt |
|---|---|---|
| `ActivePower` | kW, AVG-1M derivada lineal | Suma las potencias PCS del controlador; aproxima su setpoint salvo SOC extremo, temperatura o fallo parcial. |
| `ReactivePower` | kvar, AVG-1M derivada lineal | Suma reactiva de PCS, coherente con modo reactivo EMS/PPC. |
| `Setpoint_ActivePower` | kW, LAST-1M | Reparte la consigna EMS/PPC por capacidad disponible, SOC y límites térmicos de bancos. Respeta límites EMS de carga/descarga. |
| `Setpoint_ReactivePower` | kvar, LAST-1M | Asigna parte proporcional de reactiva total según capacidad PCS del banco. |
| `SOC` | %, LAST-1M derivada | Media ponderada por capacidad kWh de racks/bancos asociados; úsala para reparto de consignas. |

### BTMS/HVAC

| Señal | Unidad y grano | Prompt |
|---|---|---|
| `Temperature` | °C, AVG-1M | Termostato con retardo e histéresis frente a `ControlSignal_Temp`, alrededor de 20-25 °C. |
| `Humidity` | %, AVG-1M | Rango 20-70% HR, variación lenta e inversa parcial con refrigeración/deshumidificación. |
| `Pressure` | Pa/bar, AVG-1M | Correlaciona positivamente con `AirFlow` y ventiladores; decenas a cientos de Pa y caída abrupta en fallo. |
| `AirFlow` | m3/h, AVG-1M | Proporcional a diferencia entre consigna térmica y temperatura medida, sin exceder nominal. |
| `PowerConsumption` | kW, AVG-1M | Correlaciona con caudal, carga térmica, corriente DC y ambiente. Confirma antes con datos si `bessplant1` lo trata como potencia o contador; si contador, usa LAST + Delta. |
| `ComponentStatus` | Estado, ESTADO-1M | `OK/Warning/Fault`; fallos poco frecuentes que reducen caudal/presión y propagan `BTMSAlarm`. |
| `ControlSignal_Temp` | °C, LAST-1M | Setpoint estable, por ejemplo 22 °C, con cambios deliberados e infrecuentes; es entrada, no medida. |

### FPS/SCI, UPS, CT, ANL/MTR y EMS/PPC

| Elemento / señal | Unidad y grano | Prompt |
|---|---|---|
| FPS `SystemStatus` | Estado, ESTADO-1M | `Armado/Desarmado/Fault/En disparo`; permanece normalmente armado y solo falla en mantenimiento o avería propia. |
| FPS `SmokeSensorState` | Booleano, EVENTO-1M | Sin detección normalmente; es precursor de incendio y se activa antes de confirmarlo. |
| FPS `FireAlarm` | Booleano, EVENTO-1M | Consecuencia de humo o temperatura extrema sostenida. Propaga MFFP y FStop inmediatamente. |
| FPS `ExtinctionDischarge` | Booleano, EVENTO-1M | Nunca espontánea: aparece después de incendio confirmado y dura su ventana de descarga. |
| FPS `MFFPAlarm` | Booleano, EVENTO-1M | Réplica exacta de `FireAlarm` en el mismo minuto. |
| UPS `SystemStatus` | Estado, ESTADO-1M | `Red/Batería/Fault`; funciona en Red, pasa a Batería en hueco de tensión y falla si la batería UPS alcanza mínimo crítico. |
| CT `SystemStatus` | Estado, ESTADO-1M | `Normal/Maniobra/Fault`, derivado de equipos MT; fuera de Normal anula aproximadamente P/Q POI. |
| ANL `POI_ActivePower` | kW, AVG-1M lineal | Suma P PCS/BCTRL menos auxiliares HVAC, UPS y otros. Respeta límite de interconexión y CT. |
| ANL `POI_ReactivePower` | kvar, AVG-1M lineal | Suma Q PCS y ajústala al modo reactivo EMS/PPC. |
| EMS `ControlMode` | Estado, ESTADO-1M | `Local/Remoto/Manual/Automático`, estable y con cambios deliberados. En Manual, setpoints se mantienen hasta acción de operador. |
| EMS `Setpoint_ActivePower` | kW, LAST-1M | Consigna de planta escalonada dentro de límites de carga/descarga y POI; se reparte después en BCTRL. |
| EMS `Setpoint_ReactivePower` | kvar, LAST-1M | Consigna por modo fijo, cos phi o Q(V), dentro de capacidad reactiva agregada. |
| EMS `ChargeLimitFromGrid` | kW o %, LAST-1M | Límite escalón/rampa de operador/red o SOC; disminuye cerca de SOC 100% y acota carga. |
| EMS `DischargeLimitToGrid` | kW o %, LAST-1M | Límite equivalente de descarga; disminuye cerca del SOC mínimo y acota descarga. |
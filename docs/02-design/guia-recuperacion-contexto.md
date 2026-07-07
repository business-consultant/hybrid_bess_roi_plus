# Guía de Recuperación de Contexto

Esta guía sirve para retomar el proyecto desde cualquier instalación de VS Code y llevar a Copilot al último punto de contexto verificado sin tener que reconstruir la historia a mano.

---

## 1. Punto estable verificado

El último estado funcional localizado y verificado del prototipo es:

- **Commit principal**: `70d2983a62b9e6cd285473c779aac2214c497a52` (2026-06-17)
  - Mensaje: `Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI`

---

## 2. Cambios posteriores (2026-07-07)

Se han aplicado cambios operacionales sin versionar aún que **regeneran completamente los datos sintéticos históricos**:

### Optimización de Estrategias de Despacho
- **Curtailment FV fijo**: La producción solar se recorta con una meseta plana a 50 MW cuando alcanza el límite del POI
- **Desplazamiento nocturno**: Todas las descargas BESS están ahora en 20–24h (sin PV)
- **Minimización de conflictos POI**: Garantiza que `POI ≤ 50 MW` siempre
- **Consistencia mantenida**: Balance diario nulo, SoC como integral exacta

**Archivos modificados**:
- `src/bess_simulator/engine/plant.py`:
   - `_day_power_shape()`: Carga (-1.5 MW), Descarga (+2.0 MW en 20-24h)
   - `_showcase_day_power_shape()`: 5 fases con descarga final nocturna y sin exportación positiva diurna
   - `build_power_soc_series()`: curtailment FV a 50 MW + limitación de descarga BESS al margen disponible del POI
- `src/bess_simulator/ui/views/hybrid_plant.py`: Descripción UI actualizada
- **Nuevo**: `docs/02-design/estrategias-despacho.md` (documentación completa)

**Impacto**: Los gráficos de "Potencia PV + BESS y SoC" muestran ahora una meseta FV a 50 MW y descargas BESS concentradas en noche sin solapamiento solar.

---

## 3. Qué se dejó terminado en el punto estable (70d2983)

El commit `70d2983` cerró este bloque funcional:

1. Reconciliación híbrida `PV -> BESS` a coste de carga cero.
2. Crédito de sinergia para la planta híbrida.
3. Estimación de curtailment por concurrencia en el POI.
4. KPIs y VAN de planta actualizados con esa reconciliación.
5. Mejoras de rendimiento UI:
   - series de 15 min pasadas a `Scattergl`
   - sensibilidad y Excel calculados solo al pulsar `Simular`
6. Documentación funcional específica de la reconciliación.
7. Tests nuevos para la lógica híbrida.

Archivos principales tocados por ese hito:

- `docs/02-design/balance-hibrido-pv-bess.md`
- `src/bess_simulator/engine/hybrid.py`
- `src/bess_simulator/models/results.py`
- `src/bess_simulator/storage/app_config.py`
- `src/bess_simulator/ui/components/charts.py`
- `src/bess_simulator/ui/components/kpi_cards.py`
- `src/bess_simulator/ui/views/methodology.py`
- `src/bess_simulator/ui/views/simulator.py`
- `tests/test_hybrid.py`

---

## 3. Procedimiento mínimo para recuperar el estado desde cualquier VS Code

Abrir un terminal en la raíz del repo y ejecutar:

```powershell
git status --short --branch
git log --date=short --pretty=format:"%h %ad %s" --all --since="2026-06-17"
git show --stat --summary 70d2983a62b9e6cd285473c779aac2214c497a52
```

Qué debes esperar:

1. La rama activa debería ser `jlsilva` o una rama derivada consciente.
2. El último commit conocido debería ser `70d2983 2026-06-17 Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI`.
3. Si aparecen cambios locales, distinguir entre:
   - trabajo real nuevo
   - artefactos sueltos de revisión o build

Si quieres repetir exactamente la comprobación que usamos para validar que no había cambios posteriores:

```powershell
git status --porcelain=v2 --branch
git log --date=short --pretty=format:"%h %ad %s" --all --since="2026-06-17"
```

---

## 4. Anclajes para localizar rápido el trabajo correcto

Si no recuerdas por dónde empezar, busca cualquiera de estos anclajes.

### En Git

- Mensaje de commit: `Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI`
- Hash corto: `70d2983`

### En documentación

- `docs/02-design/balance-hibrido-pv-bess.md`
- sección añadida en `src/bess_simulator/ui/views/methodology.py`

### En código

- `compute_hybrid_economics`
- `HybridEconomics`
- `synergy_pv_charge_credit`
- `bess_effective_spread`
- `pv_curtailment_total_mwh`
- `poi_concurrency_curtail_pct`
- `bess_grid_charge_price`

### En tests

- `TestHybridReconciliation`
- `tests/test_hybrid.py`

---

## 5. Orden recomendado de lectura para retomar el contexto

Cuando vuelvas a este proyecto después de tiempo, usa este orden:

1. `docs/02-design/balance-hibrido-pv-bess.md`
   - explica el criterio de negocio y el modelo económico adoptado
2. `tests/test_hybrid.py`
   - fija el comportamiento esperado de la reconciliación
3. `src/bess_simulator/engine/hybrid.py`
   - contiene la implementación principal
4. `src/bess_simulator/ui/views/methodology.py`
   - expone el modelo al usuario dentro de la aplicación
5. `src/bess_simulator/ui/views/simulator.py`
   - muestra los resultados operativos y económicos
6. `src/bess_simulator/models/results.py`
   - define los campos nuevos que arrastran el resultado híbrido

Con ese recorrido sueles recuperar el contexto funcional sin abrir medio repositorio.

---

## 6. Prompt recomendado para poner a Copilot en contexto

Copia este prompt y ajústalo solo si de verdad has avanzado más allá del commit `70d2983`:

```text
Estoy retomando el proyecto hybrid_apm_prototype.

Quiero que tomes como último punto estable conocido el commit 70d2983
("Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI", 2026-06-17).

Primero verifica si hay cambios posteriores versionados o locales relevantes.
Después recupera contexto leyendo solo los anclajes mínimos de ese hito:

- docs/02-design/balance-hibrido-pv-bess.md
- tests/test_hybrid.py
- src/bess_simulator/engine/hybrid.py
- src/bess_simulator/ui/views/methodology.py
- src/bess_simulator/ui/views/simulator.py

Asume que los archivos sueltos _build2.txt y _viewcheck.py, si existen, son auxiliares y no forman parte del producto salvo que detectes lo contrario.

Cuando acabes, resume:
1. si el repo sigue en ese punto o no,
2. qué funcionalidad quedó cerrada,
3. qué superficie de código controla el siguiente cambio.
```

---

## 7. Prompt corto si solo quieres verificar que estás en el mismo punto

```text
Comprueba si este repo sigue en el estado del commit 70d2983 del 2026-06-17 y dime si hay cambios posteriores relevantes o solo archivos locales auxiliares.
```

---

## 8. Estado de contexto que debes considerar como último confirmado

Hasta la revisión del `2026-06-29`, el contexto confirmado era este:

1. La reconciliación híbrida `PV -> BESS` estaba terminada y documentada.
2. No se localizaron commits posteriores al `70d2983`.
3. La rama local `jlsilva` estaba sincronizada con `origin/jlsilva`.
4. Los dos archivos fuera de Git eran auxiliares y no funcionales.
5. El siguiente trabajo todavía no estaba definido en código: solo se acordó “continuar desde aquí con el siguiente paso”.

Eso significa que, si no detectas cambios posteriores, este documento te devuelve exactamente al último punto de contexto fiable conocido.

---

## 9. Qué hacer si el estado ya no coincide

Si al volver encuentras commits posteriores o cambios locales importantes:

1. Ejecuta `git log --date=short --pretty=format:"%h %ad %s" --all -n 15`.
2. Identifica el primer commit posterior a `70d2983`.
3. Lee su `git show --stat`.
4. Sustituye en esta guía el bloque “Punto estable verificado” por el nuevo ancla.
5. Actualiza el prompt recomendado con el nuevo commit y los nuevos archivos clave.

Si no haces esa actualización, en unas semanas volverás a perder tiempo reconstruyendo el hilo.
# hybrid_apm_prototype

Prototipo de simulación y análisis APM para planta híbrida `PV + BESS`, con foco en simulación técnica, evaluación económica, visualización en Streamlit y lógica de recomendaciones.

## Recuperación de contexto

Si vuelves a este proyecto después de unos días, empieza aquí:

- Guía operativa: `docs/02-design/guia-recuperacion-contexto.md`
- Guía general de desarrollo: `docs/02-design/guia-desarrollo.md`
- Último punto estable verificado: commit `70d2983a62b9e6cd285473c779aac2214c497a52`
	- fecha: `2026-06-17`
	- mensaje: `Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI`

## Requisitos

- Python 3.11 o superior
- Entorno virtual local en `.venv`
- Windows para `run_dev.bat`, o ejecución manual equivalente en otros sistemas

## Puesta en marcha

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m streamlit run src/bess_simulator/ui/app.py
```

Alternativamente, en Windows:

```powershell
run_dev.bat
```

## Testing

```powershell
python -m pytest tests/ -v
```

## Documentación funcional

- Estrategias de despacho: `docs/02-design/estrategias-despacho.md`
- Desarrollo: `docs/02-design/guia-desarrollo.md`
- Recuperación de contexto: `docs/02-design/guia-recuperacion-contexto.md`
- Balance híbrido PV+BESS: `docs/02-design/balance-hibrido-pv-bess.md`

## Estado actual

- La serie `PV + BESS` respeta el límite del POI.
- La FV se recorta a 50 MW cuando alcanza el límite del POI.
- La descarga positiva de la BESS se concentra en la ventana nocturna 20–24h.
- El SoC se mantiene consistente con la integral exacta de la potencia.

## Colaboración

Si este repositorio se comparte con nuevos colaboradores, conviene usar issues y pull requests para separar nuevas líneas de avance del histórico anterior.

Comprobación mínima desde terminal:

```powershell
git status --short --branch
git log --date=short --pretty=format:"%h %ad %s" --all --since="2026-06-17"
git show --stat --summary 70d2983a62b9e6cd285473c779aac2214c497a52
```

Si quieres poner a Copilot directamente en el último contexto conocido, usa este prompt:

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


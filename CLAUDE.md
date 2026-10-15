# Bluence APM / hybrid_bess_roi_plus — contexto para Claude

**Lee primero [RESUMEN_TECNICO_ESTADO.md](RESUMEN_TECNICO_ESTADO.md)** — contiene el estado técnico completo del proyecto y el registro de la sesión de trabajo del 2026-10-16 (idioma + resolución de carpetas duplicadas).

## Puntos clave a recordar

- **Esta carpeta (`hybrid_bess_roi_plus`, sin sufijo) es la copia de trabajo canónica.** Tiene `.venv` propio y es la que `run_dev.bat` sirve en `localhost:8502`. No uses ni recrees una carpeta hermana `hybrid_bess_roi_plus_lee` — si aparece, es un clon aislado de una sesión anterior y debe borrarse o ignorarse (ya está en `.gitignore`).
- Rama activa: `feature/mejora_4_e1_plus`, ya empujada a `origin` con el historial real (telemetría BESS + Trending Charts, selector de idioma ES/EN).
- La app tiene un selector de idioma (`src/bess_simulator/i18n.py`, helper `t(es, en)`) en el sidebar. Por defecto español; el inglés cubre toda la UI estática, los gráficos Plotly y el texto generado por el motor de recomendaciones. Las claves internas (nombres de página en `session_state`, categorías de alarma, nombres de subelementos) se mantienen en español a propósito — son identificadores, no texto de usuario.
- Antes de asumir que un cambio en el código "no se ve", verifica qué proceso sirve realmente el puerto en uso (`netstat -ano` + `Get-CimInstance Win32_Process`) — en este equipo ha habido más de una copia local del mismo repo corriendo a la vez.

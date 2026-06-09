# Instrucciones Para Agentes

## Punto De Partida

Mini Task Manager es una app de escritorio nativa en Python con PyQt6. La superficie activa arranca en `main.py`, carga `ui/main_window.ui` con `uic.loadUi`, y concentra la logica de UI y comportamiento en `main_window.py`.

Antes de modificar el proyecto, leer el codigo relevante y resolver primero lo que pueda inferirse del repo. Si queda una ambiguedad relevante que no se pueda resolver por inspeccion, preguntar antes de cambiar archivos. Esta regla aplica especialmente a decisiones de alcance, datos de usuario, UX, arquitectura, dependencias y compatibilidad.

## Estructura Del Proyecto

- `main.py`: entrypoint de la app. Crea `QApplication`, instancia `MainWindow` y usa `tasks.json` como archivo de datos.
- `main_window.py`: controlador principal y widgets auxiliares. Maneja renderizado, categorias, tareas, estadisticas, filtros, estilos QSS, validaciones, colapsado de grupos y guardado.
- `ui/main_window.ui`: layout base de Qt Designer. Los object names definidos aqui son usados por `main_window.py`.
- `models.py`: tipos, constantes compartidas, prioridades, iconos disponibles, etiquetas de iconos y helpers de categorias.
- `task_store.py`: persistencia JSON. Carga y guarda la forma `{"tasks": [], "categories": []}` y resetea a default si falta el archivo o esta corrupto.
- `icons.py`: helpers para resolver, tintar y cachear SVGs de Material Symbols para PyQt6.
- `assets/material_symbols/`: SVGs locales y licencia de Material Symbols. Si se agrega un icono, mantener sincronizados los SVGs y las constantes de `models.py`.
- `tests/`: tests `unittest` existentes para persistencia e iconos.
- `requirements.txt`: dependencia principal actual, `PyQt6>=6.6`.
- `public/`: prototipo legado web/PyWebView con Tailwind y JavaScript. No es la superficie activa. No modificarlo salvo que la tarea lo pida explicitamente.

## Datos Y Persistencia

`tasks.json` contiene datos reales del usuario. No resetear, limpiar, sobrescribir, formatear ni usar como fixture salvo instruccion explicita. Si una prueba necesita datos, usar archivos temporales como hacen los tests actuales.

Esquema actual:

- `tasks[]`: `id`, `title`, `categoryId`, `priority`, `completed`, y `completedAt` cuando la tarea esta completada.
- `categories[]`: `id`, `name`, `color`, `icon`.
- `completedCategoryOrder[]`: orden independiente de categorias para el historial de tareas completadas.

Las prioridades validas son `Baja`, `Media` y `Alta`; la prioridad default es `Media`. Las fechas de completado se guardan como ISO UTC con sufijo `Z`.

Si se cambia el esquema de datos, agregar compatibilidad o migracion explicita y cubrirlo con tests. Evitar cambios que destruyan o reinterpreten silenciosamente datos existentes.

## Reglas De Implementacion

- Mantener los patrones actuales del repo: PyQt6, `uic.loadUi`, QSS en `main_window.py`, persistencia JSON simple y tests con `unittest`.
- No revertir cambios existentes del usuario. Si el repo esta sucio, trabajar alrededor de esos cambios y mencionar solo lo relevante.
- No tocar `tasks.json` ni `git sync/` salvo que la tarea lo pida claramente.
- Para cambios en `ui/main_window.ui`, verificar que los nombres de widgets sigan coincidiendo con los accesos desde `main_window.py`.
- Para cambios visuales, preservar la app como herramienta de escritorio compacta y funcional. Evitar redisenos amplios si la tarea pide un ajuste puntual.
- Para categorias, respetar que no se pueden eliminar si estan en uso por tareas.
- Para iconos, usar Material Symbols locales via `icons.py`; no depender de recursos remotos para la app PyQt6.
- Para colores ingresados o guardados, usar los helpers existentes (`safe_color`, `readable_color`, `qss_rgba`) cuando corresponda.

## Validacion

Comando principal:

```bash
python -m unittest discover -s tests
```

Para cambios que afecten UI o flujo de usuario, ademas de los tests, revisar manualmente el arranque:

```bash
python main.py
```

Si no se puede ejecutar una validacion, registrar el motivo. Para cambios de persistencia, agregar o actualizar tests en `tests/test_task_store.py`. Para cambios de iconos, agregar o actualizar tests en `tests/test_icons.py`.

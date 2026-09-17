@echo off
REM Doble clic: prepara los Excel nuevos, genera el reporte HTML y sube los datos a GitHub.
cd /d "%~dp0"
python actualizar.py --publicar
echo.
pause

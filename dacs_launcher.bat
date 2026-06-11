@echo off
title DACS - Audit ^& Correct
cd /d "C:\Users\johns\OneDrive\Documents\GitHub\Data Auditing and Correction System"
set "PY=C:\Users\johns\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PY%" set "PY=python"
set "INFILE=%~1"
if "%INFILE%"=="" set /p "INFILE=Drag a CSV onto this window (or paste its path) then press Enter: "
if "%INFILE%"=="" ( echo No file given. & pause & exit /b )
echo.
echo Processing: %INFILE%
echo.
"%PY%" dacs.py "%INFILE%" --out "C:\Users\johns\OneDrive\Desktop\Corrected Data"
echo.
echo Done. Corrected files are in:  C:\Users\johns\OneDrive\Desktop\Corrected Data
echo.
pause

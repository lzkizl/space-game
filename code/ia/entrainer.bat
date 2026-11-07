@echo off
chcp 65001 >nul
cd /d "%~dp0"
set MIN=%1
if "%MIN%"=="" set MIN=800
echo Entrainement de l'IA pendant %MIN% minutes (ferme la fenetre pour arreter, le modele est sauvegarde a chaque epoch)
python -X utf8 -u ia.py --train --minutes %MIN%
pause

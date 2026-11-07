@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Mode continu : l'IA lit de nouveaux articles puis continue d'apprendre, sans fin.
echo Ferme la fenetre ou fais Ctrl+C pour arreter (le meilleur modele est deja sauvegarde).
python -X utf8 -u ia.py --continu --cycle 30
pause

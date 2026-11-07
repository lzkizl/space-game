@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Lance 5 fenetres qui tournent sans fin : mots, mots anglais, dialogues quotidiens, dialogues OpenAssistant, dialogues livres.
echo Tu peux relancer ce fichier autant de fois que tu veux : une collecte deja en cours n'est jamais doublee
echo (la nouvelle fenetre se ferme toute seule). Ferme une fenetre ou fais Ctrl+C dedans pour l'arreter
echo (tout est sauvegarde, elle reprendra ou elle s'est arretee).
start "Recuperateur de mots" cmd /k python -X utf8 -u mots.py
start "English words collector" cmd /k python -X utf8 -u mots_en.py
start "Dialogues quotidiens" cmd /k python -X utf8 -u dialogues.py --source quotidien
start "Dialogues OpenAssistant" cmd /k python -X utf8 -u dialogues.py --source oasst2
start "Dialogues livres" cmd /k python -X utf8 -u dialogues.py --source livres

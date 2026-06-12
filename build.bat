@echo off
echo Instalando PyInstaller...
pip install pyinstaller

echo Gerando executavel...
pyinstaller --onefile --name DevBriefNews --add-data "news_prompt.txt;." --add-data "templates\email_template.html;templates" --add-data "assets\logo.png;assets" --hidden-import=tzdata main.py

echo.
echo Build concluido: dist\DailyNewsBot.exe
echo Copie .env e news_prompt.txt para a pasta de deploy junto com o .exe
pause

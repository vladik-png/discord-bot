@echo off
echo Start Lavalink...
cd /d "D:\py"
start "Lavalink Server" java -jar Lavalink.jar

echo Waiting 5 seconds
timeout /t 5 /nobreak >nul

echo Start Bot...
cd /d "D:\py"
start "Bot" python ds.py
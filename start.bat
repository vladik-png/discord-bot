@echo off
color 0A
echo =========================================
echo 1. Starting Lavalink Server...
echo =========================================
start "Lavalink Server" java -jar Lavalink.jar

echo Waiting 5 seconds for Lavalink to boot up...
timeout /t 5 /nobreak > NUL

echo =========================================
echo 2. Starting Discord Bot...
echo =========================================
python ds.py

pause
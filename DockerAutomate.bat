@echo off
echo ===========================
echo Building and Pushing Docker Images
echo ===========================

:: Step 1: Build images
docker compose build
IF %ERRORLEVEL% NEQ 0 (
    echo Build failed!
    exit /b 1
)

:: Step 2: Push images to Docker Hub
docker compose push
IF %ERRORLEVEL% NEQ 0 (
    echo Push failed!
    exit /b 1
)

:: Step 3: SSH into remote and deploy
echo ===========================
echo Deploying to remote server
echo ===========================

:: Sending Files to Server
scp -r ./Anomaly-Evaluator skye@100.108.98.44:/home/skye/programs
scp -r ./ESI-Interface skye@100.108.98.44:/home/skye/programs
scp -r ./The-Market-Hand skye@100.108.98.44:/home/skye/programs

ssh skye@100.108.98.44 "cd /home/skye/programs && docker login && docker-compose build Anomaly-Evaluator The-Market-Hand ESI-Interface"

IF %ERRORLEVEL% NEQ 0 (
    echo Remote deployment failed!
    exit /b 1
)

:: Sending Environment File to Server
scp ./.env skye@100.108.98.44:/home/skye/programs

:: Sending Token to Server
scp ./ESI-Interface/token.json skye@100.108.98.44:/home/skye/programs/ESI-Interface

echo ===========================
echo Deployment complete!
docker compose ps
pause

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
SRC="/mnt/c/Programs/2-EVE/LunaSkye-Core/"
DEST="skye@100.108.98.44:/home/skye/projects/"

rsync -az --info=progress2 "$SRC/Anomaly-Evaluator" "$DEST"
rsync -az --info=progress2 "$SRC/ESI-Interface" "$DEST"
rsync -az --info=progress2 "$SRC/Shared-Content" "$DEST"
rsync -az --info=progress2 "$SRC/The-Market-Hand" "$DEST"

rsync -az --info=progress2 "$SRC/venv" "$DEST"

:: Sending Environment File to Server
scp ./.env skye@100.108.98.44:/home/skye/programs

:: Sending Token to Server
scp ./ESI-Interface/token.json skye@100.108.98.44:/home/skye/programs/ESI-Interface

:: Sending Docker Commands & Files
scp ./docker-compose.yml skye@100.108.98.44:/home/skye/programs

ssh skye@100.108.98.44 "cd /home/skye/programs && docker login && docker-compose up -d"

IF %ERRORLEVEL% NEQ 0 (
    echo Remote deployment failed!
    exit /b 1
)

echo ===========================
echo Deployment complete!
pause

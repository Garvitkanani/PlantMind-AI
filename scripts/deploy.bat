@echo off
REM PlantMind AI - Windows Deployment Script
REM Usage: scripts\deploy.bat [staging|production]

setlocal EnableDelayedExpansion

set "ENVIRONMENT=%~1"
if "%~1"=="" set "ENVIRONMENT=staging"

echo.
echo ==========================================
echo PlantMind AI - Windows Deployment
echo ==========================================
echo Environment: %ENVIRONMENT%
echo.

REM Check prerequisites
echo [INFO] Checking prerequisites...

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    exit /b 1
)

REM Check Docker Compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed
    exit /b 1
)

REM Check .env file
if not exist ".env" (
    echo [WARN] .env file not found. Copying from .env.example
    copy .env.example .env
    echo [WARN] Please edit .env file with your production settings
)

echo [INFO] Prerequisites check passed
echo.

REM Build and deploy
echo [INFO] Building and deploying with Docker Compose...

docker-compose pull
docker-compose build --no-cache

echo [INFO] Stopping existing containers...
docker-compose down 2>nul

echo [INFO] Starting services...
docker-compose up -d

echo [INFO] Waiting for application to start...
timeout /t 15 /nobreak >nul

echo [INFO] Running health check...
curl -sf http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] Health check failed, checking logs...
    docker-compose logs app --tail 50
) else (
    echo [INFO] Application is healthy
)

echo.
echo ==========================================
echo Deployment completed!
echo ==========================================
echo.
echo Local URL:    http://localhost:8000
echo Health Check: http://localhost:8000/health
echo.
echo To view logs:
echo   docker-compose logs -f app
echo.
echo To stop:
echo   docker-compose down
echo.

endlocal

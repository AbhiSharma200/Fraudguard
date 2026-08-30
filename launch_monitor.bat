@echo off
title FraudGuard Module 1 — Live Stream Telemetry Web Monitor
cls
echo Starting FraudGuard Stream Telemetry Web Monitor at http://localhost:8080 ...
python "src\stream_monitor.py"
pause

@echo off
title FraudGuard GitHub Push Tool
cls
echo ==========================================================================
echo        FRAUDGUARD — GITHUB REPOSITORY PUSH TOOL
echo ==========================================================================
echo Target Remote: https://github.com/AbhiSharma200/Fraudguard.git
echo.

cd /d "C:\Users\hp\.gemini\antigravity\scratch\fraudguard-datapipeline"
set GIT_BIN="C:\Users\hp\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"

%GIT_BIN% branch -M main
%GIT_BIN% remote remove origin 2>nul
%GIT_BIN% remote add origin https://github.com/AbhiSharma200/Fraudguard.git
%GIT_BIN% add .
%GIT_BIN% commit -m "Initial commit: FraudGuard Real-Time Fraud Detection & Risk Scoring System" 2>nul

echo.
echo Pushing to GitHub... (A browser window or sign-in popup may appear for GitHub authentication)
%GIT_BIN% push -u origin main

pause

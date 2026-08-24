@echo off
title FraudGuard Git Push Tool
cls
echo ==========================================================================
echo        FRAUDGUARD — GITHUB REPOSITORY PUSH TOOL
echo ==========================================================================
echo Target Remote: https://github.com/AbhiSharma200/Fraudguard.git
echo.

cd /d "C:\Users\hp\.gemini\antigravity\scratch\fraudguard-datapipeline"

git init
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/AbhiSharma200/Fraudguard.git
git add .
git commit -m "Initial commit: FraudGuard Real-Time Fraud Detection & Risk Scoring System"
echo.
echo Pushing to GitHub... (Sign-in window may appear in your browser)
git push -u origin main

pause

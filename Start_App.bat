@echo off
chcp 65001 > nul
title GDKTPL Exam Studio Pro - He Thong Tao De Thi HSG
cd /d "%~dp0"

echo ======================================================================
echo       HỆ THỐNG TẠO ĐỀ THI HỌC SINH GIỎI MÔN GDKT^&PL (CHUẨN GDPT 2018)
echo ======================================================================
echo.
echo Dang khoi dong may chu ung dung...
echo.

if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" run_server.py
) else (
    python run_server.py
)

if %errorlevel% neq 0 (
    echo.
    echo [LOI] Khong the khoi dong ung dung. Vui long kiem tra Python.
    pause
)

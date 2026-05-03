@echo off
chcp 65001 >nul
echo.
echo  ================================
echo   🐼 Panda Agent 安装程序
echo  ================================
echo.
echo  正在检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  ❌ 未检测到 Python
    echo  请先安装 Python：https://python.org
    echo  安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b
)
echo  ✅ Python 已安装
echo.
echo  正在安装依赖...
pip install -r requirements.txt
echo.
echo  ================================
echo   ✅ 安装完成！
echo   双击 start.bat 启动 Panda Agent
echo  ================================
echo.
pause

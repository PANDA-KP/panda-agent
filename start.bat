@echo off
chcp 65001 >nul
echo.
echo  🐼 正在启动 Panda Agent...
echo  浏览器会自动打开，如果没有，请访问 http://localhost:8501
echo  关闭此窗口会停止 Panda Agent
echo.
streamlit run app.py

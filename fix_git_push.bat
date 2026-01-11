@echo off
echo Fixing Git push buffer and timeout issues...
echo.

echo Setting Git HTTP buffer to 500MB...
git config --global http.postBuffer 524288000

echo Setting Git HTTP version to 1.1 for better stability...
git config --global http.version HTTP/1.1

echo Increasing Git timeout settings...
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999

echo Disabling Git compression to reduce processing time...
git config --global core.compression 0

echo.
echo Git configuration updated successfully!
echo.
echo Current Git HTTP settings:
git config --get http.postBuffer
git config --get http.version
git config --get http.lowSpeedLimit
git config --get http.lowSpeedTime
git config --get core.compression

echo.
echo You can now try: git push origin master
pause
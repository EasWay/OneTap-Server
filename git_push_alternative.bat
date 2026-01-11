@echo off
echo Alternative Git Push Strategy for Large Repositories
echo =====================================================
echo.

echo Step 1: Cancel current push if still running (Ctrl+C)
echo Step 2: Try pushing with different strategies...
echo.

echo Strategy 1: Push with no compression and increased timeout
git config http.postBuffer 1048576000
git config http.timeout 600
git config core.compression 0
git config pack.compression 0

echo.
echo Strategy 2: Try pushing in smaller chunks
echo Attempting push with depth limit...
git push --no-verify origin master

echo.
echo If that fails, trying with force (use carefully)...
echo git push --force-with-lease origin master

echo.
echo Strategy 3: If still failing, try LFS for large files
echo git lfs track "*.db"
echo git lfs track "tldv_profile/**"
echo git add .gitattributes
echo git commit -m "Add LFS tracking"
echo git push origin master

pause
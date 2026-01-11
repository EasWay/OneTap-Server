@echo off
echo Cleaning up large files and pushing to Git
echo ==========================================
echo.

echo Step 1: Cancel any running git push (Ctrl+C if needed)
timeout /t 3

echo Step 2: Remove large cache files that shouldn't be in Git
echo Removing Chrome profile cache directories...
rmdir /s /q "tldv_profile\Default\Cache" 2>nul
rmdir /s /q "tldv_profile\Default\Code Cache" 2>nul
rmdir /s /q "tldv_profile\Default\GPUCache" 2>nul
rmdir /s /q "tldv_profile\Default\Service Worker" 2>nul
rmdir /s /q "tldv_profile\Default\IndexedDB" 2>nul
rmdir /s /q "tldv_profile\Default\Local Storage" 2>nul
rmdir /s /q "tldv_profile\Default\Session Storage" 2>nul
rmdir /s /q "tldv_profile\Default\WebStorage" 2>nul
rmdir /s /q "tldv_profile\Default\blob_storage" 2>nul
rmdir /s /q "tldv_profile\GraphiteDawnCache" 2>nul
rmdir /s /q "tldv_profile\GrShaderCache" 2>nul
rmdir /s /q "tldv_profile\ShaderCache" 2>nul

echo Step 3: Remove any backup profiles
rmdir /s /q "youtube_profile" 2>nul

echo Step 4: Add changes to git
git add .
git add .gitignore

echo Step 5: Commit the cleanup
git commit -m "Clean up large cache files and add gitignore"

echo Step 6: Check repository size
echo Repository size after cleanup:
git count-objects -vH

echo Step 7: Try push again with optimized settings
git config http.postBuffer 524288000
git config http.version HTTP/1.1
git config core.compression 1
git config pack.compression 1

echo Attempting push...
git push origin master

echo.
echo If push still hangs, try:
echo git push --no-verify origin master
echo.
echo Or use Git LFS for the profile:
echo git lfs track "tldv_profile/**"
echo git add .gitattributes
echo git commit -m "Add LFS tracking for profile"
echo git push origin master

pause
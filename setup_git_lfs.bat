@echo off
echo Setting up Git LFS for large files
echo ===================================
echo.

echo Installing/initializing Git LFS...
git lfs install

echo Tracking large files with LFS...
git lfs track "tldv_profile/**"
git lfs track "*.db"
git lfs track "*.sqlite"
git lfs track "*.cache"

echo Adding LFS configuration...
git add .gitattributes
git add .gitignore

echo Committing LFS setup...
git commit -m "Add Git LFS for large files"

echo Pushing with LFS...
git push origin master

echo.
echo LFS setup complete!
echo Large files will now be stored in Git LFS instead of the main repository.

pause
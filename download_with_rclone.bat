@echo off
REM Download GEE results from Google Drive using rclone
REM 
REM Setup:
REM   1. Install rclone: https://rclone.org/downloads/
REM   2. rclone config  (add Google Drive remote named 'drive')
REM   3. Chạy script này

rclone copy drive:TinhTuc_GEE_Results .\outputs\gee_results\downloaded\ --drive-export-formats csv,geojson,tif -P

echo Download complete!
echo Files saved to: .\outputs\gee_results\downloaded\
pause

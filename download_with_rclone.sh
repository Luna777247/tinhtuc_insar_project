#!/bin/bash
# Download GEE results from Google Drive using rclone
# 
# Setup:
#   1. Install rclone: https://rclone.org/downloads/
#   2. rclone config  (add Google Drive remote named 'drive')
#   3. Chạy script này

rclone copy drive:TinhTuc_GEE_Results ./outputs/gee_results/downloaded/ --drive-export-formats csv,geojson,tif -P

echo "Download complete!"
echo "Files saved to: ./outputs/gee_results/downloaded/"

# JamSlayer V3 - AGS1 SCADA Alarm Trend Analysis

Automated PEC Blockage trend analysis dashboard for AGS1 Sort Center.
Upload SCADA alarm exports, get instant trend classification and priority rankings.

## Features

- **Auto-detects file format**: XML SpreadsheetML (SCADA export), Excel, CSV
- **Deep trend analysis**: Linear regression, starting-to-block detection, chronic identification
- **Device classification**: WORSENING, STARTING_TO_BLOCK, CHRONIC, IMPROVING, STABLE
- **Priority scoring**: 0-100 weighted score (slope, average, ratio, consistency, severity)
- **Actionable recommendations**: Specific next steps for techs per device

## File Format

The primary input is the SCADA alarm history export from Ignition:
- XML SpreadsheetML format (files may have no extension)
- ~38MB, ~31K rows per 3-week export
- Columns: TimeStamp, Duration, Name, Priority, Acked, UDT, PLC, etc.

## Deploy to Render.com

1. Push all 8 files to a GitHub repo (no subfolders needed)
2. On Render.com: New Web Service > connect repo
3. Settings:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 300`
   - Plan: Free
4. Deploy — get your URL

## Files

| File | Purpose |
|------|---------|
| app.py | Flask server + embedded HTML/CSS/JS dashboard |
| alarm_parser.py | XML SpreadsheetML + Excel/CSV parser |
| analysis.py | Trend detection, classification, priority scoring |
| database.py | SQLite storage and queries |
| requirements.txt | Python dependencies |
| render.yaml | Render.com deploy config |
| README.md | This file |
| .gitignore | Git ignores |

## Usage

1. Open the URL
2. Drag-drop your SCADA alarm export file
3. Wait 30-60 seconds for processing (large files)
4. View device trends, classifications, and priorities
5. Techs use the recommendations to prioritize inspections

## API

- `GET /` - Dashboard
- `POST /upload` - Upload alarm file
- `GET /api/data` - Current analysis JSON
- `GET /api/uploads` - Upload history
- `POST /api/reset` - Clear all data

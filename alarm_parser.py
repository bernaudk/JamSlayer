"""
alarm_parser.py - SCADA Alarm Export Parser for JamSlayer V3
Handles XML SpreadsheetML format (primary), plus .xlsx/.csv fallbacks.
Optimized for large files (~38MB, ~31K rows) using iterparse.
"""

import xml.etree.ElementTree as ET
import io
import re
from datetime import datetime

# SpreadsheetML namespace
SS_NS = 'urn:schemas-microsoft-com:office:spreadsheet'
SS_TAG_ROW = f'{{{SS_NS}}}Row'
SS_TAG_CELL = f'{{{SS_NS}}}Cell'
SS_TAG_DATA = f'{{{SS_NS}}}Data'
SS_ATTR_INDEX = f'{{{SS_NS}}}Index'
SS_ATTR_TYPE = f'{{{SS_NS}}}Type'

# UDT suffix pattern to strip for device grouping
SUFFIX_PATTERN = re.compile(r'-(ACC|CH|BSB|TR|SOS|MRG|DVT|IND|CNV)$', re.IGNORECASE)


class ParseError(Exception):
    """Raised when file parsing fails."""
    pass


def strip_device_suffix(udt):
    """Strip device suffixes for grouping. PLC1001_10010502-ACC -> PLC1001_10010502"""
    if not udt:
        return ''
    return SUFFIX_PATTERN.sub('', udt.strip())


def parse_duration_to_seconds(duration_str):
    """Parse HH:MM:SS duration to seconds."""
    if not duration_str:
        return 0
    duration_str = str(duration_str).strip()
    
    # HH:MM:SS
    match = re.match(r'^(\d+):(\d+):(\d+)$', duration_str)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    
    # MM:SS
    match = re.match(r'^(\d+):(\d+)$', duration_str)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    
    # Try numeric
    try:
        return int(float(duration_str))
    except (ValueError, TypeError):
        return 0


def is_xml_spreadsheet(file_content):
    """Check if file content is XML SpreadsheetML format."""
    # Check first 200 bytes for XML declaration and spreadsheet markers
    header = file_content[:500] if isinstance(file_content, bytes) else file_content.encode()[:500]
    header_str = header.decode('utf-8', errors='ignore')
    return '<?xml' in header_str and 'spreadsheet' in header_str.lower()


def parse_xml_spreadsheet(file_content):
    """
    Parse XML SpreadsheetML (the actual SCADA alarm export format).
    Uses iterparse for memory efficiency on large files.
    
    Returns: list of event dicts
    """
    events = []
    
    # Parse from bytes or string
    if isinstance(file_content, bytes):
        source = io.BytesIO(file_content)
    else:
        source = io.StringIO(file_content)
    
    headers = []
    row_num = 0
    
    try:
        context = ET.iterparse(source, events=('end',))
        
        for event, elem in context:
            if elem.tag == SS_TAG_ROW:
                # Extract cells from this row
                cells = []
                cell_elements = elem.findall(f'.//{SS_TAG_CELL}')
                
                current_index = 1
                for cell in cell_elements:
                    # Handle ss:Index attribute (for sparse rows)
                    idx_attr = cell.get(SS_ATTR_INDEX)
                    if idx_attr:
                        current_index = int(idx_attr)
                    
                    # Pad with None for skipped columns
                    while len(cells) < current_index - 1:
                        cells.append(None)
                    
                    # Get data value
                    data_elem = cell.find(f'.//{SS_TAG_DATA}')
                    if data_elem is not None and data_elem.text:
                        cells.append(data_elem.text)
                    else:
                        cells.append(None)
                    
                    current_index = len(cells) + 1
                
                if row_num == 0:
                    # First row = headers
                    headers = [c if c else f'Col{i}' for i, c in enumerate(cells)]
                else:
                    # Data row — extract what we need
                    if len(cells) >= 6:
                        timestamp = cells[0] if len(cells) > 0 else None
                        duration = cells[1] if len(cells) > 1 else None
                        alarm_name = cells[2] if len(cells) > 2 else None
                        priority = cells[3] if len(cells) > 3 else None
                        udt_raw = cells[5] if len(cells) > 5 else None
                        plc = cells[12] if len(cells) > 12 else None
                        
                        if udt_raw and timestamp:
                            # Parse timestamp to date
                            date_str = ''
                            try:
                                # Format: 2026-07-21T23:59:51.000
                                date_str = timestamp[:10]  # Just YYYY-MM-DD
                            except (ValueError, IndexError):
                                date_str = datetime.now().strftime('%Y-%m-%d')
                            
                            # Parse duration
                            duration_seconds = parse_duration_to_seconds(duration)
                            
                            # Strip suffix for device grouping
                            device = strip_device_suffix(udt_raw)
                            
                            events.append({
                                'device': device,
                                'device_raw': udt_raw.strip(),
                                'alarm_name': alarm_name or 'PEC Blockage',
                                'timestamp': timestamp,
                                'date': date_str,
                                'duration_seconds': duration_seconds,
                                'priority': priority or '',
                                'plc': plc or ''
                            })
                
                row_num += 1
                elem.clear()
    
    except ET.ParseError as e:
        raise ParseError(f"XML parsing failed: {str(e)}")
    
    if not events:
        raise ParseError("No valid alarm events found in XML file")
    
    return events


def parse_xlsx_file(file_content):
    """Fallback parser for .xlsx/.xlsm/.xls files using openpyxl."""
    try:
        import pandas as pd
        
        df = pd.read_excel(io.BytesIO(file_content))
        events = []
        
        # Find key columns (case-insensitive)
        cols = {c.lower(): c for c in df.columns}
        
        udt_col = cols.get('udt', cols.get('device', None))
        ts_col = cols.get('timestamp', cols.get('datetime', None))
        dur_col = cols.get('duration', None)
        name_col = cols.get('name', cols.get('alarmname', None))
        plc_col = cols.get('plc', None)
        
        if not udt_col:
            raise ParseError("Cannot find UDT/Device column in Excel file")
        
        for _, row in df.iterrows():
            udt_raw = str(row[udt_col]).strip() if pd.notna(row[udt_col]) else ''
            if not udt_raw or udt_raw == 'nan':
                continue
            
            timestamp = ''
            date_str = ''
            if ts_col and pd.notna(row[ts_col]):
                try:
                    ts = pd.to_datetime(row[ts_col])
                    timestamp = ts.isoformat()
                    date_str = ts.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    date_str = datetime.now().strftime('%Y-%m-%d')
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            duration_seconds = 0
            if dur_col and pd.notna(row[dur_col]):
                duration_seconds = parse_duration_to_seconds(row[dur_col])
            
            alarm_name = ''
            if name_col and pd.notna(row[name_col]):
                alarm_name = str(row[name_col]).strip()
            
            plc = ''
            if plc_col and pd.notna(row[plc_col]):
                plc = str(row[plc_col]).strip()
            
            device = strip_device_suffix(udt_raw)
            
            events.append({
                'device': device,
                'device_raw': udt_raw,
                'alarm_name': alarm_name or 'PEC Blockage',
                'timestamp': timestamp,
                'date': date_str,
                'duration_seconds': duration_seconds,
                'priority': '',
                'plc': plc
            })
        
        return events
    
    except ImportError:
        raise ParseError("pandas/openpyxl not available for Excel parsing")
    except ParseError:
        raise
    except Exception as e:
        raise ParseError(f"Excel parsing failed: {str(e)}")


def parse_csv_file(file_content):
    """Fallback parser for CSV files."""
    try:
        import pandas as pd
        
        # Try different encodings
        try:
            df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(file_content), encoding='latin-1')
        
        # If single column, try other delimiters
        if len(df.columns) <= 1:
            for sep in [';', '\t', '|']:
                try:
                    df_test = pd.read_csv(io.BytesIO(file_content), sep=sep)
                    if len(df_test.columns) > 1:
                        df = df_test
                        break
                except Exception:
                    continue
        
        # Reuse xlsx parser logic on the DataFrame
        events = []
        cols = {c.lower(): c for c in df.columns}
        
        udt_col = cols.get('udt', cols.get('device', None))
        ts_col = cols.get('timestamp', cols.get('datetime', None))
        dur_col = cols.get('duration', None)
        name_col = cols.get('name', None)
        plc_col = cols.get('plc', None)
        
        if not udt_col:
            raise ParseError("Cannot find UDT/Device column in CSV")
        
        for _, row in df.iterrows():
            udt_raw = str(row[udt_col]).strip() if pd.notna(row[udt_col]) else ''
            if not udt_raw or udt_raw == 'nan':
                continue
            
            date_str = datetime.now().strftime('%Y-%m-%d')
            timestamp = ''
            if ts_col and pd.notna(row[ts_col]):
                try:
                    ts = pd.to_datetime(row[ts_col])
                    timestamp = ts.isoformat()
                    date_str = ts.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    pass
            
            duration_seconds = 0
            if dur_col and pd.notna(row[dur_col]):
                duration_seconds = parse_duration_to_seconds(row[dur_col])
            
            alarm_name = ''
            if name_col and pd.notna(row[name_col]):
                alarm_name = str(row[name_col]).strip()
            
            plc = ''
            if plc_col and pd.notna(row[plc_col]):
                plc = str(row[plc_col]).strip()
            
            device = strip_device_suffix(udt_raw)
            
            events.append({
                'device': device,
                'device_raw': udt_raw,
                'alarm_name': alarm_name or 'PEC Blockage',
                'timestamp': timestamp,
                'date': date_str,
                'duration_seconds': duration_seconds,
                'priority': '',
                'plc': plc
            })
        
        return events
    
    except ParseError:
        raise
    except Exception as e:
        raise ParseError(f"CSV parsing failed: {str(e)}")


def parse_file(file_content, filename='unknown'):
    """
    Main entry point. Auto-detects format and parses.
    Accepts files with NO extension, .xls, .xlsx, .xlsm, .csv
    
    Returns: (events_list, format_type, record_count)
    """
    if not file_content or len(file_content) == 0:
        raise ParseError("File is empty")
    
    # Auto-detect format
    if is_xml_spreadsheet(file_content):
        events = parse_xml_spreadsheet(file_content)
        format_type = 'xml_spreadsheetml'
    else:
        # Try xlsx first, then csv
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        
        if ext in ('xlsx', 'xlsm', 'xls'):
            events = parse_xlsx_file(file_content)
            format_type = 'excel'
        elif ext == 'csv':
            events = parse_csv_file(file_content)
            format_type = 'csv'
        else:
            # No extension — try xlsx, then csv
            try:
                events = parse_xlsx_file(file_content)
                format_type = 'excel'
            except ParseError:
                try:
                    events = parse_csv_file(file_content)
                    format_type = 'csv'
                except ParseError:
                    raise ParseError(
                        "Cannot parse file. Expected XML SpreadsheetML (SCADA export), "
                        "Excel (.xlsx/.xls), or CSV format."
                    )
    
    if not events:
        raise ParseError("No valid alarm events found in file")
    
    return events, format_type, len(events)

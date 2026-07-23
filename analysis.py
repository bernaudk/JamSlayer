"""
analysis.py - Deep Trend Analysis Engine for JamSlayer V3
Produces accurate, tech-friendly results with tight filters.
Classifies devices as WORSENING, CHRONIC, STARTING_TO_BLOCK, IMPROVING, STABLE.
Caps output at 15 devices per category for readability.
"""

import numpy as np
from datetime import datetime
from collections import defaultdict
import database


# === Classification Thresholds ===

# Worsening: clear upward trend
SLOPE_WORSENING = 0.3       # alarms/day increase
RATIO_WORSENING = 1.5       # recent/early must be 1.5x+

# Improving: clear downward trend
SLOPE_IMPROVING = -0.3      # alarms/day decrease
RATIO_IMPROVING = 0.7       # recent/early below 0.7x

# Chronic: consistently high volume
CHRONIC_MIN_AVG = 5.0       # minimum full-period daily avg
CHRONIC_MIN_CONSISTENCY = 0.50  # active 50%+ of days

# Starting-to-block: TIGHT filters to avoid noise
# Device must have meaningful volume AND clear emergence signal
STB_MIN_TOTAL_ALARMS = 14       # must have >= 14 total alarms to qualify
STB_MIN_RECENT_AVG = 3.0        # recent avg must be >= 3/day
STB_MIN_RATIO = 3.0             # recent/early must be 3x+ (standard path)
STB_LOW_BASELINE_MAX_EARLY = 1.0  # "low baseline" = early avg <= 1.0
STB_LOW_BASELINE_MIN_RECENT = 4.0  # recent avg >= 4 for low-baseline path
STB_LOW_BASELINE_MIN_TOTAL = 10    # minimum events for low-baseline path

# Priority score weights
WEIGHT_SLOPE = 0.30
WEIGHT_AVG = 0.25
WEIGHT_INCREASE_RATIO = 0.25
WEIGHT_CONSISTENCY = 0.10
WEIGHT_RECENT_SEVERITY = 0.10

# Dashboard caps
MAX_PER_CATEGORY = 15
MAX_TOP_OVERALL = 20


def linear_regression_slope(values):
    """Calculate linear regression slope for a sequence of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def detect_starting_to_block(counts_aligned, all_dates, total_alarms):
    """
    Detect if a device is emerging from low baseline.
    Uses TIGHT thresholds to avoid flooding the dashboard with noise.
    
    Requirements to qualify:
    - Must have meaningful alarm volume (>= 14 total)
    - Must show clear recent emergence (recent_avg >= 3)
    - Must have strong ratio (>= 3x early average)
    
    Three qualifying paths:
    A) Standard ramp: total>=14, recent_avg>=3, ratio>=3.0
    B) Low-baseline emergence: early<=1.0, recent_avg>=4, total>=10
    C) Moderate baseline with strong jump: early<=2.0, recent_avg>=5, ratio>=2.5, total>=14
    
    Returns: dict with detection info or None
    """
    if not counts_aligned or len(all_dates) < 4:
        return None
    
    total_days = len(all_dates)
    third = max(3, total_days // 3)
    
    early_counts = counts_aligned[:total_days - third]
    recent_counts = counts_aligned[-third:]
    
    early_avg = np.mean(early_counts) if early_counts else 0
    recent_avg = np.mean(recent_counts) if recent_counts else 0
    
    if early_avg <= 0 and recent_avg <= 0:
        return None
    
    ratio = recent_avg / early_avg if early_avg > 0 else (recent_avg + 1)
    
    # Path A: Clear ramp with meaningful volume
    if total_alarms >= STB_MIN_TOTAL_ALARMS and recent_avg >= STB_MIN_RECENT_AVG and ratio >= STB_MIN_RATIO:
        return {
            'path': 'ramp',
            'early_avg': round(early_avg, 2),
            'recent_avg': round(recent_avg, 2),
            'ratio': round(ratio, 1)
        }
    
    # Path B: Low baseline but significant recent emergence
    if (early_avg <= STB_LOW_BASELINE_MAX_EARLY and 
        recent_avg >= STB_LOW_BASELINE_MIN_RECENT and 
        total_alarms >= STB_LOW_BASELINE_MIN_TOTAL):
        return {
            'path': 'low_baseline',
            'early_avg': round(early_avg, 2),
            'recent_avg': round(recent_avg, 2),
            'ratio': round(ratio, 1)
        }
    
    # Path C: Moderate baseline with strong recent jump
    if (early_avg <= 2.0 and recent_avg >= 5.0 and 
        ratio >= 2.5 and total_alarms >= STB_MIN_TOTAL_ALARMS):
        return {
            'path': 'moderate_jump',
            'early_avg': round(early_avg, 2),
            'recent_avg': round(recent_avg, 2),
            'ratio': round(ratio, 1)
        }
    
    return None


def classify_device(slope, full_avg, consistency, increase_ratio, stb_result, days_active):
    """
    Classify device trend status.
    Priority order: WORSENING > STARTING_TO_BLOCK > CHRONIC > IMPROVING > STABLE
    """
    if days_active < 2:
        return 'STABLE'
    
    # WORSENING: clear sustained upward trend
    if slope >= SLOPE_WORSENING and increase_ratio >= RATIO_WORSENING:
        return 'WORSENING'
    
    # STARTING TO BLOCK: emerging from low baseline (tight filter already applied)
    if stb_result is not None and full_avg < CHRONIC_MIN_AVG:
        return 'STARTING_TO_BLOCK'
    
    # CHRONIC: consistently high
    if full_avg >= CHRONIC_MIN_AVG and consistency >= CHRONIC_MIN_CONSISTENCY:
        return 'CHRONIC'
    
    # IMPROVING: clear downward trend
    if slope <= SLOPE_IMPROVING and increase_ratio <= RATIO_IMPROVING:
        return 'IMPROVING'
    
    return 'STABLE'


def calculate_priority_score(slope, full_avg, increase_ratio, consistency, recent_avg):
    """
    Calculate priority score (0-100).
    Higher = more urgent attention needed.
    """
    slope_norm = min(1.0, max(0.0, slope / 5.0))
    avg_norm = min(1.0, max(0.0, full_avg / 50.0))
    ratio_norm = min(1.0, max(0.0, (increase_ratio - 1.0) / 4.0))
    consistency_norm = min(1.0, max(0.0, consistency))
    severity_norm = min(1.0, max(0.0, recent_avg / 30.0))
    
    score = (
        WEIGHT_SLOPE * slope_norm +
        WEIGHT_AVG * avg_norm +
        WEIGHT_INCREASE_RATIO * ratio_norm +
        WEIGHT_CONSISTENCY * consistency_norm +
        WEIGHT_RECENT_SEVERITY * severity_norm
    ) * 100
    
    return round(min(100, max(0, score)), 1)


def get_recommended_action(classification, score, daily_avg):
    """Generate recommended action for techs."""
    if classification == 'WORSENING':
        if score >= 70:
            return "URGENT: Inspect immediately - rapid degradation"
        elif score >= 40:
            return "Schedule inspection within 24h"
        else:
            return "Monitor closely - upward trend"
    elif classification == 'STARTING_TO_BLOCK':
        return "Emerging issue - inspect before next shift"
    elif classification == 'CHRONIC':
        if daily_avg >= 20:
            return "Root cause analysis needed - persistent"
        else:
            return "Add to PM schedule - low-level chronic"
    elif classification == 'IMPROVING':
        return "Verify fix is holding"
    else:
        return "No action required"


def run_analysis():
    """
    Run full trend analysis on all stored alarm data.
    Returns dashboard-ready results capped at 15 per category.
    """
    daily_counts = database.get_daily_counts_by_device()
    device_summary = database.get_device_summary()
    total_stats = database.get_total_stats()
    
    if not daily_counts:
        return {
            'devices': [],
            'stats': total_stats,
            'classifications': {
                'WORSENING': 0, 'CHRONIC': 0, 'STARTING_TO_BLOCK': 0,
                'IMPROVING': 0, 'STABLE': 0
            },
            'worsening': [],
            'chronic': [],
            'starting_to_block': [],
            'top25': [],
            'generated_at': datetime.now().isoformat(),
            'date_range': {'start': None, 'end': None, 'days': 0},
            'empty': True
        }
    
    # Build per-device time series
    device_timeseries = defaultdict(dict)
    for row in daily_counts:
        device_timeseries[row['device']][row['date']] = row['count']
    
    # Get all dates sorted
    all_dates = sorted(set(row['date'] for row in daily_counts))
    total_days = len(all_dates)
    
    # Define periods
    third = max(1, total_days // 3)
    
    # Build device summary map
    summary_map = {s['device']: s for s in device_summary}
    
    # Analyze each device
    device_analyses = []
    classification_counts = {
        'WORSENING': 0, 'CHRONIC': 0, 'STARTING_TO_BLOCK': 0,
        'IMPROVING': 0, 'STABLE': 0
    }
    
    for device, date_counts in device_timeseries.items():
        # Build aligned daily counts (0 for missing days)
        counts_aligned = [date_counts.get(d, 0) for d in all_dates]
        
        # Active days (non-zero)
        active_counts = [c for c in counts_aligned if c > 0]
        days_active = len(active_counts)
        
        # Basic stats
        full_avg = np.mean(counts_aligned) if counts_aligned else 0
        active_avg = np.mean(active_counts) if active_counts else 0
        total_alarms = sum(counts_aligned)
        
        # Early and recent averages
        early_counts_list = counts_aligned[:third]
        recent_counts_list = counts_aligned[-third:]
        early_avg = np.mean(early_counts_list) if early_counts_list else 0
        recent_avg = np.mean(recent_counts_list) if recent_counts_list else 0
        
        # Increase ratio
        if early_avg > 0:
            increase_ratio = recent_avg / early_avg
        else:
            increase_ratio = recent_avg + 1 if recent_avg > 0 else 1.0
        
        # Consistency
        consistency = days_active / total_days if total_days > 0 else 0
        
        # Linear regression slope
        slope = linear_regression_slope(counts_aligned)
        
        # Peak day
        peak_count = max(counts_aligned) if counts_aligned else 0
        peak_date = ''
        if peak_count > 0:
            peak_idx = counts_aligned.index(peak_count)
            peak_date = all_dates[peak_idx] if peak_idx < len(all_dates) else ''
        
        # Starting-to-block detection (with tight filters)
        stb_result = detect_starting_to_block(counts_aligned, all_dates, total_alarms)
        
        # Classification
        classification = classify_device(
            slope, full_avg, consistency, increase_ratio, stb_result, days_active
        )
        classification_counts[classification] += 1
        
        # Priority score
        priority_score = calculate_priority_score(
            slope, full_avg, increase_ratio, consistency, recent_avg
        )
        
        # Recommended action
        action = get_recommended_action(classification, priority_score, active_avg)
        
        # Get PLC from summary
        summary = summary_map.get(device, {})
        plc = summary.get('plc', '')
        
        device_analyses.append({
            'device': device,
            'plc': plc,
            'classification': classification,
            'priority_score': priority_score,
            'slope': round(slope, 3),
            'full_avg': round(full_avg, 2),
            'active_avg': round(active_avg, 1),
            'early_avg': round(early_avg, 2),
            'recent_avg': round(recent_avg, 2),
            'increase_ratio': round(increase_ratio, 2),
            'consistency': round(consistency, 3),
            'days_active': days_active,
            'total_alarms': total_alarms,
            'peak_count': peak_count,
            'peak_date': peak_date,
            'first_seen': summary.get('first_seen', all_dates[0] if all_dates else ''),
            'last_seen': summary.get('last_seen', all_dates[-1] if all_dates else ''),
            'recommended_action': action,
            'stb_info': stb_result
        })
    
    # Sort by priority score
    device_analyses.sort(key=lambda x: x['priority_score'], reverse=True)
    
    # Extract category lists — CAPPED at MAX_PER_CATEGORY for dashboard readability
    worsening = [d for d in device_analyses if d['classification'] == 'WORSENING'][:MAX_PER_CATEGORY]
    chronic = [d for d in device_analyses if d['classification'] == 'CHRONIC'][:MAX_PER_CATEGORY]
    starting_to_block = [d for d in device_analyses if d['classification'] == 'STARTING_TO_BLOCK'][:MAX_PER_CATEGORY]
    improving = [d for d in device_analyses if d['classification'] == 'IMPROVING'][:MAX_PER_CATEGORY]
    top25 = device_analyses[:MAX_TOP_OVERALL]
    
    return {
        'devices': device_analyses,
        'stats': total_stats,
        'classifications': classification_counts,
        'worsening': worsening,
        'chronic': chronic,
        'starting_to_block': starting_to_block,
        'improving': improving,
        'top25': top25,
        'generated_at': datetime.now().isoformat(),
        'date_range': {
            'start': all_dates[0] if all_dates else None,
            'end': all_dates[-1] if all_dates else None,
            'days': total_days
        },
        'total_devices_analyzed': len(device_analyses),
        'empty': False
    }

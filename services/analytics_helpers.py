
from datetime import datetime
import re

def calculate_hours(job):
    # 1. Try exact duration if closed_at and published_at exist (and job is closed)
    if job.closed_at and job.published_at:
        diff = (job.closed_at - job.published_at).total_seconds() / 3600.0
        if 0.5 <= diff <= 24: # Sanity check
            return round(diff, 1)

    # 2. Try parsing shift string
    if job.shift:
        s = job.shift.strip().lower()
        # Regex for "08:30-18:00" or similar
        match = re.search(r'(\d{1,2})[:.](\d{2})\s*-\s*(\d{1,2})[:.](\d{2})', s)
        if match:
            h1, m1, h2, m2 = map(int, match.groups())
            start = h1 + m1/60.0
            end = h2 + m2/60.0
            if end < start: end += 24 # Over midnight
            return round(end - start, 1)
        
        # Keywords
        if 'gece' in s: return 8.0
        if 'tam' in s: return 9.0
        if 'yarım' in s or 'yarim' in s: return 4.5

    # 3. Default or None
    return 0.0

def get_job_km(job):
    # Placeholder: DB'de KM kolonu yok.
    # Note alanında "KM: 150" gibi bir şey varsa regex ile çekebiliriz.
    if job.note:
        match = re.search(r'(?:km|mesafe)[:\s]+(\d+)', job.note, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 0.0

def get_vehicle_info(job):
    # 1. From Team
    if job.team and job.team.vehicle:
        return job.team.vehicle.plate
    # 2. From vehicle_info text
    if job.vehicle_info:
        # Try to extract plate-like string
        match = re.search(r'\d{2}\s*[A-Z]{1,3}\s*\d{2,4}', job.vehicle_info, re.IGNORECASE)
        if match:
            return match.group(0).upper().replace(" ", "")
        return job.vehicle_info # Return raw string if no plate found
    return "Belirsiz"


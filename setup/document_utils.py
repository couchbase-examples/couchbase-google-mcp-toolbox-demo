"""
Document processing utilities shared across the setup module.
"""

from typing import List


def extract_manufacturing_keywords(text: str) -> List[str]:
    """Extract relevant manufacturing keywords from text."""
    manufacturing_keywords = [
        'pressure', 'temperature', 'speed', 'vibration', 'flow', 'motor',
        'pump', 'valve', 'sensor', 'alarm', 'error', 'fault', 'maintenance',
        'calibration', 'inspection', 'cleaning', 'lubrication', 'belt',
        'bearing', 'coupling', 'gearbox', 'hydraulic', 'pneumatic',
        'electrical', 'mechanical', 'safety', 'emergency', 'stop',
        'start', 'operation', 'procedure', 'troubleshoot', 'repair'
    ]
    
    text_lower = text.lower()
    found_keywords = [kw for kw in manufacturing_keywords if kw in text_lower]
    return found_keywords[:10]  # Return top 10 keywords 
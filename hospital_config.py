# hospital_config.py

# 1. OPERATING THEATRES (12 Rooms)
# Structure: ID, Name, Supported Specialties
ROOMS = [
    # Specialized Rooms (Strict Access)
    {'id': 1, 'name': 'OR-1 (Neuro)', 'type': 'Neuro', 'supported': ['Neurological', 'Spinal']},
    {'id': 2, 'name': 'OR-2 (Neuro)', 'type': 'Neuro', 'supported': ['Neurological', 'Spinal']},
    {'id': 3, 'name': 'OR-3 (Cardio)', 'type': 'Cardiac', 'supported': ['Cardiovascular', 'Thoracic']},
    {'id': 4, 'name': 'OR-4 (Cardio)', 'type': 'Cardiac', 'supported': ['Cardiovascular', 'Thoracic']},
    
    # General Rooms (Flexible)
    {'id': 5, 'name': 'OR-5 (General)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cosmetic']},
    {'id': 6, 'name': 'OR-6 (General)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cosmetic']},
    {'id': 7, 'name': 'OR-7 (Ortho)', 'type': 'General', 'supported': ['Orthopedic', 'General']},
    {'id': 8, 'name': 'OR-8 (Ortho)', 'type': 'General', 'supported': ['Orthopedic', 'General']},
    {'id': 9, 'name': 'OR-9 (Hybrid)', 'type': 'General', 'supported': ['General', 'Urology', 'Cosmetic']},
    {'id': 10, 'name': 'OR-10 (Robot)', 'type': 'General', 'supported': ['General', 'Urology']}, # Has Robot
    {'id': 11, 'name': 'OR-11 (General)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cardiovascular']},
    {'id': 12, 'name': 'OR-12 (Cosmetic)', 'type': 'General', 'supported': ['Cosmetic', 'General']},
    {'id': 13, 'name': 'OR-13 (Trauma Bay)', 'type': 'Emergency', 'supported': ['Neurological', 'Cardiovascular', 'Orthopedic', 'General', 'Cosmetic', 'Urology']}  # Emergency only
]

# 2. SURGEONS & SPECIALTIES
SURGEONS = {
    'Dr. Strange': ['Neurological'],
    'Dr. Shepherd': ['Neurological'],
    'Dr. Yang': ['Cardiovascular'],
    'Dr. Burke': ['Cardiovascular'],
    'Dr. House': ['General', 'Orthopedic'],
    'Dr. Grey': ['General'],
    'Dr. Torres': ['Orthopedic'],
    'Dr. Lincoln': ['Orthopedic'],
    'Dr. Avery': ['Cosmetic', 'General'],
    'Dr. Bailey': ['General']
}

# 3. SHARED RESOURCES (Bottlenecks)
EQUIPMENT = {
    'C-Arm': 4,    # Only 4 C-Arms available total
    'Robot': 1     # Only 1 Da Vinci Robot
}

# 4. OPERATIONAL RULES
CONSTANTS = {
    'DAY_START': 8 * 60,   # 08:00 AM (480 mins)
    'DAY_END': 20 * 60,    # 08:00 PM (1200 mins) - Allows for Overtime
    'TURNOVER': 30,        # Minutes to clean room
    'SURGEON_BREAK': 30    # Mandatory surgeon break between consecutive surgeries
}

# 5. TRAUMA BAY (For Code Red Emergencies ONLY)
# This resource is EXCLUDED from regular scheduling
EMERGENCY_RESERVE_ROOM = {
    'id': 13,  # Using OR-13 (Trauma Bay) - dedicated for Code Red only
    'name': 'OR-13 (Trauma Bay)',
    'type': 'Emergency',
    'supported': ['Neurological', 'Cardiovascular', 'Orthopedic', 'General', 'Cosmetic', 'Urology']  # Supports everything
}

# Reserve surgeons (one per specialty) - kept on-call for emergencies
EMERGENCY_RESERVE_SURGEONS = {
    'Neurological': 'Dr. Shepherd',  # Reserve neuro surgeon
    'Cardiovascular': 'Dr. Burke',   # Reserve cardiac surgeon
    'Orthopedic': 'Dr. Lincoln',     # Reserve ortho surgeon
    'General': 'Dr. Grey',           # Reserve general surgeon
    'Cosmetic': 'Dr. Avery',         # Reserve cosmetic surgeon
    'Urology': 'Dr. Grey'            # Reserve urology surgeon
}

# 6. FIXED SURGEON COLORS (Consistent across re-optimization)
SURGEON_COLORS = {
    'Dr. Strange': '#E8B4F0',      # Light Purple
    'Dr. Shepherd': '#D4A5D4',     # Lavender
    'Dr. Yang': '#FFB3BA',         # Light Pink
    'Dr. Burke': '#FFDFBA',        # Peach
    'Dr. House': '#FFFFBA',        # Light Yellow
    'Dr. Grey': '#BAFFC9',         # Mint Green
    'Dr. Torres': '#BAE1FF',       # Light Blue
    'Dr. Lincoln': '#C9C9FF',      # Periwinkle
    'Dr. Avery': '#FFD6A5',        # Apricot
    'Dr. Bailey': '#CAFFBF'        # Pale Green
}
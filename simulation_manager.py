# simulation_manager.py
import pandas as pd
import joblib
from scheduler_engine import EnterpriseScheduler
from hospital_config import ROOMS, SURGEONS, EQUIPMENT, EMERGENCY_RESERVE_ROOM, EMERGENCY_RESERVE_SURGEONS

class HospitalSystem:
    def __init__(self):
        # Filter out OR-11 (Trauma Bay) from regular scheduling - kept empty for emergencies
        self.regular_rooms = [r for r in ROOMS if r['id'] != EMERGENCY_RESERVE_ROOM['id']]
        self.regular_surgeons = {k: v for k, v in SURGEONS.items() if k not in EMERGENCY_RESERVE_SURGEONS.values()}
        
        self.scheduler = EnterpriseScheduler(self.regular_rooms, self.regular_surgeons, EQUIPMENT)
        self.current_schedule = None
        self.active_patients = [] # Stores full dicts        self.room_unavailable = {}  # Track room delays: {room_name: ready_time_mins}        
        # Load AI Model
        try:
            self.artifacts = joblib.load("surgery_model_artifacts.pkl")
            self.model = self.artifacts['model']
            print("AI Model Loaded Successfully")
        except:
            print("WARNING: Model not found. Using fallback durations.")
            self.model = None

    def predict_duration(self, patient_row):
        """Uses XGBoost to predict duration based on patient data"""
        if not self.model: return 120 # Fallback
        
        # Prepare input vector (Must match training columns exactly)
        # Input: Age, Gender(0/1), BMI, SurgeryType(0-3), Anesthesia(0/1), ASA, Comorb
        try:
            # We use the encoders saved in artifacts to transform text -> int
            # Inside simulation_manager.py -> predict_duration method
            # Inside simulation_manager.py -> predict_duration method
            input_df = pd.DataFrame([{
                'Age': patient_row['Age'],
                'Gender': self.artifacts['le_gender'].transform([patient_row['Gender']])[0],
                'BMI': patient_row['BMI'],
                'SurgeryType': self.artifacts['le_surgery'].transform([patient_row['SurgeryType']])[0],
                'AnesthesiaType': self.artifacts['le_anesthesia'].transform([patient_row['AnesthesiaType']])[0],
                'ASA_Score': patient_row['ASA_Score'],
                'Has_Comorbidity': patient_row['Has_Comorbidity'] # Direct mapping now!
            }])
            return int(self.model.predict(input_df)[0])
        except Exception as e:
            print(f"Prediction Error for {patient_row['PatientID']}: {e}")
            return 90 # Safe fallback

    def start_day(self, csv_file):
        """1. Load CSV -> 2. AI Predict -> 3. Optimize"""
        df = pd.read_csv(csv_file)
        
        patients_payload = []
        for _, row in df.iterrows():
            # 1. AI Prediction
            pred_duration = self.predict_duration(row)
            
            # 2. Build Patient Object
            p_obj = {
                'id': row['PatientID'],
                'type': row['SurgeryType'],
                'surgeon': row['Surgeon'],
                'duration': pred_duration,
                'asa_score': row['ASA_Score'],
                'needs_c_arm': row.get('Needs_CArm', False),
                'needs_robot': row.get('Needs_Robot', False)
            }
            patients_payload.append(p_obj)
            
        self.active_patients = patients_payload
        
        # 3. Optimize (scheduler already initialized with filtered rooms/surgeons)
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_emergency(self, patient_id, added_delay, current_time_hhmm):
        """Re-optimizes schedule while pinning past events"""
        print(f"ALERT: Handling Delay: {patient_id} +{added_delay} mins")
        
        # Convert HH:MM to minutes
        h, m = map(int, current_time_hhmm.split(':'))
        current_mins = h * 60 + m
        
        # 1. Update Duration
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if target_p:
            target_p['duration'] += added_delay
            
        # 2. Pin Logic
        if self.current_schedule is not None:
            for p in self.active_patients:
                # Find scheduled start time
                sched_row = self.current_schedule[self.current_schedule['Patient ID'] == p['id']]
                if sched_row.empty: continue
                
                start_mins = sched_row.iloc[0]['start_mins']
                assigned_room = sched_row.iloc[0]['Room']
                
                if start_mins < current_mins:
                    # STARTED IN PAST -> PIN IT
                    p['fixed_start'] = start_mins
                    p['fixed_room'] = assigned_room
                else:
                    # FUTURE -> FREE TO MOVE (But not before now)
                    p.pop('fixed_start', None)
                    p.pop('fixed_room', None)
                    p['min_start_time'] = current_mins

        # 3. Re-Solve
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_start_delay(self, patient_id, delay_reason, new_ready_time_str, current_time_str, room_name=None):
        """
        Handles situations where a surgery cannot start on time.
        
        LOGIC BY DELAY REASON:
        - Surgeon Running Late → ALL surgeries of that surgeon delayed (surgeon unavailable)
        - Patient Not Ready → Only THIS patient delayed (surgeon can do others)
        - Room Cleaning / OT Not Ready → ALL surgeries in that room delayed
        - Equipment Issue → Only THIS patient delayed
        """
        print(f"Start Delay: {patient_id} - Reason: {delay_reason} - Ready at: {new_ready_time_str}")
        
        # Convert times to minutes
        h, m = map(int, current_time_str.split(':'))
        current_mins = h * 60 + m
        
        rh, rm = map(int, new_ready_time_str.split(':'))
        ready_mins = rh * 60 + rm
        
        # Find the target patient to get their surgeon
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if not target_p:
            print(f"WARNING: Patient {patient_id} not found in active patients")
            return self.current_schedule
        
        target_surgeon = target_p.get('surgeon')
        
        # LOGIC: Apply delay based on reason
        if delay_reason == "Surgeon Running Late":
            # SURGEON DELAY: All surgeries of this surgeon must wait
            print(f"Surgeon {target_surgeon} delayed - blocking ALL their surgeries until {new_ready_time_str}")
            for p in self.active_patients:
                if p.get('surgeon') == target_surgeon:
                    # Set ready_time for ALL patients of this surgeon (take MAX to preserve stricter constraints)
                    existing_ready = p.get('ready_time', 0)
                    p['ready_time'] = max(existing_ready, ready_mins)
                    
        elif delay_reason in ["Room Cleaning", "OT Not Ready"]:
            # ROOM DELAY: Mark room as unavailable until ready_time
            if room_name:
                print(f"Room {room_name} not ready - blocking ALL surgeries in this room until {new_ready_time_str}")
                # Track room unavailability (initialize if not exists for backwards compatibility)
                if not hasattr(self, 'room_unavailable'):
                    self.room_unavailable = {}
                self.room_unavailable[room_name] = ready_mins
                
                # Update ALL patients to avoid this room until ready time
                for p in self.active_patients:
                    # Store room constraint on patient
                    if 'room_unavailable' not in p:
                        p['room_unavailable'] = {}
                    p['room_unavailable'][room_name] = ready_mins
            else:
                # Fallback: just delay this patient
                existing_ready = target_p.get('ready_time', 0)
                target_p['ready_time'] = max(existing_ready, ready_mins)
                    
        else:
            # PATIENT DELAY (Patient Not Ready, Equipment Issue, Other): Only this patient
            # Surgeon is FREE to do other surgeries
            print(f"Patient {patient_id} delayed - surgeon {target_surgeon} can do other cases")
            existing_ready = target_p.get('ready_time', 0)
            target_p['ready_time'] = max(existing_ready, ready_mins)
        
        # Pin past surgeries and set min_start_time for future ones
        if self.current_schedule is not None:
            for p in self.active_patients:
                sched_row = self.current_schedule[self.current_schedule['Patient ID'] == p['id']]
                if sched_row.empty: continue
                
                start_mins = sched_row.iloc[0]['start_mins']
                assigned_room = sched_row.iloc[0]['Room']
                
                if start_mins < current_mins:
                    # Already started - pin it
                    p['fixed_start'] = start_mins
                    p['fixed_room'] = assigned_room
                else:
                    # Future surgery - free to move
                    p.pop('fixed_start', None)
                    p.pop('fixed_room', None)
                    # Set min_start_time only if no ready_time or ready_time is earlier
                    if 'ready_time' not in p or p.get('ready_time', 0) < current_mins:
                        p['min_start_time'] = current_mins
        
        # Re-solve with new constraints
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_code_red(self, patient_details, current_time_str):
        """
        Emergency bypass: Books directly into Emergency Reserve Room without re-optimization.
        Used for true emergencies that need immediate attention.
        
        patient_details: dict with keys 'id', 'Age', 'Gender', 'BMI', 'SurgeryType', 
                        'AnesthesiaType', 'Has_Comorbidity', 'ASA_Score'
        current_time_str: string like "10:30"
        """
        print(f"CODE RED: Emergency case {patient_details['id']} - Direct booking initiated")
        
        # 1. Convert Current Time to Minutes (e.g., "10:30" -> 630)
        h, m = map(int, current_time_str.split(':'))
        current_mins = h * 60 + m
        
        # 2. Get Predicted Duration using AI model
        duration = self.predict_duration(patient_details)
        
        # 3. Assign Reserved Resources
        surgery_type = patient_details['SurgeryType']
        assigned_surgeon = EMERGENCY_RESERVE_SURGEONS.get(surgery_type, 'Dr. Grey')  # Default to Dr. Grey
        
        # 4. Calculate end time
        end_mins = current_mins + duration
        
        # 5. Create the Schedule Row
        new_row = {
            "Patient ID": patient_details['id'],
            "Type": surgery_type,
            "Surgeon": assigned_surgeon,
            "Room": EMERGENCY_RESERVE_ROOM['name'],
            "Start Time": f"{current_mins//60:02d}:{current_mins%60:02d}",
            "End Time": f"{end_mins//60:02d}:{end_mins%60:02d}",
            "Duration": duration,
            "start_mins": current_mins,
            "end_mins": end_mins,
            "Risk (ASA)": patient_details.get('ASA_Score', 3)  # Emergency cases are typically high risk
        }
        
        # 6. Append to existing schedule
        if self.current_schedule is None:
            self.current_schedule = pd.DataFrame([new_row])
        else:
            self.current_schedule = pd.concat([self.current_schedule, pd.DataFrame([new_row])], ignore_index=True)
        
        # Sort by start time for proper visualization
        self.current_schedule = self.current_schedule.sort_values('start_mins').reset_index(drop=True)
        
        print(f"Emergency booked: {patient_details['id']} in {EMERGENCY_RESERVE_ROOM['name']} at {current_time_str}")
        return self.current_schedule
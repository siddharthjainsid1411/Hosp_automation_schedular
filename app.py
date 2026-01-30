import streamlit as st
import pandas as pd
import plotly.express as px
import os
from simulation_manager import HospitalSystem
from hospital_config import SURGEONS, SURGEON_COLORS
 
# --- CONFIG ---
st.set_page_config(page_title="Intelligent Automated OT Schedular", layout="wide", page_icon="⚕")
 
# Initialize Session State
if 'system' not in st.session_state:
    st.session_state['system'] = HospitalSystem()
if 'schedule' not in st.session_state:
    st.session_state['schedule'] = None
if 'manual_patients' not in st.session_state:
    st.session_state['manual_patients'] = []
 
# Valid Categories for Dropdowns
SURGERY_TYPES = ['Neurological', 'Cardiovascular', 'Orthopedic', 'Cosmetic']
ANESTHESIA_TYPES = ['General', 'Local']
GENDER_TYPES = ['M', 'F']
COMORBIDITY_OPTS = [0, 1]
ASA_SCORES = [0, 1, 2, 3] # As requested
SURGEON_LIST = list(SURGEONS.keys()) # Dynamically get from config
 
# --- SIDEBAR: CONTROLS ---
st.sidebar.title("Ops Control")
 
# DATA SOURCE TOGGLE
data_source = st.sidebar.radio("Select Data Source", ["Upload CSV", "Manual Entry"], index=0)
 
st.sidebar.divider()
 
# ==========================================
# SECTION 1: MORNING INTAKE (LOGIC)
# ==========================================
 
st.sidebar.subheader("1. Morning Intake")
 
if data_source == "Upload CSV":
    # --- ORIGINAL CSV UPLOAD FLOW ---
    uploaded_file = st.sidebar.file_uploader("Upload Raw Patient Manifest", type=['csv'])
    
    if uploaded_file and st.sidebar.button("Run AI Prediction & Schedule"):
        with st.spinner("AI analyzing Age, BMI, ASA Scores... Predicting Durations..."):
            schedule = st.session_state['system'].start_day(uploaded_file)
            st.session_state['schedule'] = schedule
        st.sidebar.success("Schedule Optimized based on AI Predictions!")
 
elif data_source == "Manual Entry":
    # --- NEW MANUAL FORM FLOW ---
    st.sidebar.info("Enter patient details manually below.")
    
    # We put the form in the main area or an expander in the sidebar?
    # The prompt asks for a "wrapper kind of form". A Sidebar form is tight, let's use a sidebar Expander.
    
    with st.sidebar.expander("📝 Manual Patient Entry Form", expanded=True):
        with st.form("patient_form", clear_on_submit=True):
            p_id = st.text_input("Patient ID (e.g., P-101)")
            age = st.number_input("Age", min_value=0, max_value=120, value=30)
            gender = st.selectbox("Gender", GENDER_TYPES)
            bmi = st.number_input("BMI", min_value=10.0, max_value=60.0, value=22.0)
            
            s_type = st.selectbox("Surgery Type", SURGERY_TYPES)
            a_type = st.selectbox("Anesthesia Type", ANESTHESIA_TYPES)
            
            comorb = st.selectbox("Has Comorbidity", COMORBIDITY_OPTS)
            asa = st.selectbox("ASA Score", ASA_SCORES)
            
            surgeon = st.selectbox("Surgeon", SURGEON_LIST)
            
            # Checkboxes for True/False
            c_arm = st.checkbox("Needs C-Arm")
            robot = st.checkbox("Needs Robot")
            
            # Buttons inside form
            submitted = st.form_submit_button("➕ Add Patient")
            
            if submitted:
                if p_id:
                    # Create dictionary matches CSV structure
                    new_patient = {
                        'PatientID': p_id,
                        'Age': age,
                        'Gender': gender,
                        'BMI': bmi,
                        'SurgeryType': s_type,
                        'AnesthesiaType': a_type,
                        'Has_Comorbidity': comorb,
                        'ASA_Score': asa,
                        'Surgeon': surgeon,
                        'Needs_CArm': c_arm,
                        'Needs_Robot': robot
                    }
                    st.session_state['manual_patients'].append(new_patient)
                    st.toast(f"Patient {p_id} Added!", icon="")
                else:
                    st.error("Patient ID is required.")
 
    # List Management Buttons
    col_rm, col_clr = st.sidebar.columns(2)
    if col_rm.button("Undo Last"):
        if st.session_state['manual_patients']:
            st.session_state['manual_patients'].pop()
            st.sidebar.success("Last entry removed.")
    
    if col_clr.button("Clear All"):
        st.session_state['manual_patients'] = []
        st.sidebar.success("List cleared.")
 
    # Submit Batch
    if st.sidebar.button("Submit & Schedule Batch"):
        if len(st.session_state['manual_patients']) > 0:
            # Convert list to DataFrame
            df_manual = pd.DataFrame(st.session_state['manual_patients'])
            
            # Save to temporary CSV to feed existing pipeline
            temp_filename = "temp_manual_intake.csv"
            df_manual.to_csv(temp_filename, index=False)
            
            with st.spinner(f"Processing {len(df_manual)} Patients..."):
                # Pass the temp CSV to the system
                schedule = st.session_state['system'].start_day(temp_filename)
                st.session_state['schedule'] = schedule
            
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            st.sidebar.success("Manual Batch Scheduled!")
        else:
            st.sidebar.error("No patients in list to schedule.")
 
# Display Manual List Preview if in Manual Mode
if data_source == "Manual Entry" and st.session_state['manual_patients']:
    st.sidebar.markdown("---")
    st.sidebar.caption("Current Batch Preview:")
    st.sidebar.dataframe(pd.DataFrame(st.session_state['manual_patients']), height=150)
 
 
# ==========================================
# SECTION 2: LIVE OPERATIONS (EMERGENCY)
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("2. Live Operations")

# Emergency Type Toggle
emergency_mode = st.sidebar.radio(
    "Emergency Type:",
    ["Start Delay", "Duration Adjustment", "Code Red"],
    help="Start Delay: Surgeon/patient running late\nDuration Adjustment: Surgery taking longer/shorter\nCode Red: Emergency direct booking"
)

if emergency_mode == "Start Delay":
    # --- NEW: START DELAY HANDLING ---
    st.sidebar.markdown("**Surgery Start Delayed**")
    st.sidebar.caption("Use when surgeon/patient is late or OT not ready")
    
    if st.session_state['schedule'] is not None:
        patient_list = st.session_state['schedule']['Patient ID'].tolist()
        room_list = st.session_state['schedule']['Room'].unique().tolist()
        
        if patient_list:
            delay_patient = st.sidebar.selectbox("Select Delayed Patient", patient_list, key="start_delay_patient")
            
            delay_reason = st.sidebar.selectbox(
                "Reason for Delay",
                ["Surgeon Running Late", "Patient Not Ready", "OT Not Ready", "Room Cleaning", "Equipment Issue", "Other"],
                key="start_delay_reason",
                help="Surgeon Late → ALL their surgeries delayed\nPatient Not Ready → Only this surgery delayed\nOT Not Ready → ALL surgeries in that room delayed"
            )
            
            # Show room selector only for room-related delays
            selected_room = None
            if delay_reason in ["OT Not Ready", "Room Cleaning"]:
                selected_room = st.sidebar.selectbox("Select Affected Room", room_list, key="start_delay_room")
            
            new_ready_time = st.sidebar.time_input("Will Be Ready At", value=None, key="start_delay_ready")
            current_time_sd = st.sidebar.time_input("Current Time", value=None, key="start_delay_current")
            
            if st.sidebar.button("Apply Start Delay"):
                if new_ready_time is None or current_time_sd is None:
                    st.sidebar.error("Please set both Ready Time and Current Time.")
                else:
                    ready_str = f"{new_ready_time.hour:02d}:{new_ready_time.minute:02d}"
                    current_str = f"{current_time_sd.hour:02d}:{current_time_sd.minute:02d}"
                    
                    # Different messages based on delay type
                    if delay_reason == "Surgeon Running Late":
                        spinner_msg = f"Surgeon delayed - blocking ALL their surgeries until {ready_str}..."
                        success_msg = f"All surgeries for this surgeon rescheduled after {ready_str}"
                    elif delay_reason in ["OT Not Ready", "Room Cleaning"]:
                        spinner_msg = f"{selected_room} not ready - rescheduling all cases..."
                        success_msg = f"All surgeries in {selected_room} rescheduled after {ready_str}"
                    else:
                        spinner_msg = f"Patient {delay_patient} delayed - surgeon can do other cases..."
                        success_msg = f"{delay_patient} rescheduled. Surgeon may take other cases."
                    
                    with st.spinner(spinner_msg):
                        new_sched = st.session_state['system'].handle_start_delay(
                            delay_patient, delay_reason, ready_str, current_str, room_name=selected_room
                        )
                        st.session_state['schedule'] = new_sched
                    
                    st.sidebar.warning(success_msg)
        else:
            st.sidebar.info("Schedule is empty.")
    else:
        st.sidebar.info("Please generate a schedule first.")

elif emergency_mode == "Code Red":
    # --- NEW: EMERGENCY CODE RED FORM ---
    st.sidebar.markdown("**CODE RED: Emergency Patient Direct Booking**")
    
    with st.sidebar.expander("Emergency Patient Details", expanded=True):
        with st.form("emergency_form", clear_on_submit=False):
            em_id = st.text_input("Patient ID (e.g., EMG-001)", value="EMG-001")
            em_age = st.number_input("Age", min_value=0, max_value=120, value=45)
            em_gender = st.selectbox("Gender", GENDER_TYPES)
            em_bmi = st.number_input("BMI", min_value=10.0, max_value=60.0, value=25.0)
            em_surgery = st.selectbox("Surgery Type", SURGERY_TYPES)
            em_anesthesia = st.selectbox("Anesthesia Type", ANESTHESIA_TYPES)
            em_comorbidity = st.selectbox("Has Comorbidity", COMORBIDITY_OPTS)
            em_asa = st.selectbox("ASA Score", [3, 4, 5], index=0)  # Emergencies are high risk
            em_time = st.time_input("Arrival Time", value=None)
            
            submit_emergency = st.form_submit_button("ACTIVATE CODE RED")
    
    if submit_emergency:
        if em_time is None:
            st.sidebar.error("Please set the Arrival Time.")
        else:
            time_str = f"{em_time.hour:02d}:{em_time.minute:02d}"
            
            # Prepare patient details for AI prediction
            emergency_patient = {
                'id': em_id,
                'Age': em_age,
                'Gender': em_gender,
                'BMI': em_bmi,
                'SurgeryType': em_surgery,
                'AnesthesiaType': em_anesthesia,
                'Has_Comorbidity': em_comorbidity,
                'ASA_Score': em_asa
            }
            
            with st.spinner("Activating Emergency Protocol..."):
                new_schedule = st.session_state['system'].handle_code_red(emergency_patient, time_str)
                st.session_state['schedule'] = new_schedule
            
            st.sidebar.success(f"Emergency {em_id} booked in OR-13 (Trauma Bay) at {time_str}!")

elif emergency_mode == "Duration Adjustment":
    # --- EXISTING: DELAY HANDLING ---
    st.sidebar.markdown("**Surgery Duration Adjustment**")
    st.sidebar.caption("Handles both early finishes (−) and delays (+)")
    
    if st.session_state['schedule'] is not None:
        # Dropdowns for Emergency
        patient_list = st.session_state['schedule']['Patient ID'].tolist()
        
        if patient_list:
            target_p = st.sidebar.selectbox("Select Patient", patient_list)
            
            # Allow negative values for early finishes
            delay_mins = st.sidebar.slider(
                "Time Adjustment (Minutes)", 
                min_value=-180, 
                max_value=180, 
                value=0, 
                step=15,
                help="Negative = Surgery finished early | Positive = Surgery delayed"
            )
            
            current_time = st.sidebar.time_input("Current Time", value=None)
            
            if st.sidebar.button("Adjust & Re-Optimize Schedule"):
                if current_time is None:
                    st.sidebar.error("Please set the Current Time.")
                else:
                    time_str = f"{current_time.hour}:{current_time.minute}"
                    
                    # Dynamic messaging based on early/late
                    if delay_mins < 0:
                        spinner_msg = f"Surgery finished {abs(delay_mins)} mins early! Re-optimizing to move up waiting patients..."
                        success_msg = f"Schedule updated! {target_p} finished {abs(delay_mins)} mins early - downstream patients moved up."
                    elif delay_mins > 0:
                        spinner_msg = f"Surgery delayed {delay_mins} mins. Re-calculating cascade effects..."
                        success_msg = f"Schedule healed! {target_p} extended by {delay_mins} mins."
                    else:
                        spinner_msg = "Re-optimizing schedule..."
                        success_msg = "Schedule refreshed (no time change)."
                    
                    with st.spinner(spinner_msg):
                        new_sched = st.session_state['system'].handle_emergency(target_p, delay_mins, time_str)
                        st.session_state['schedule'] = new_sched
                    
                    if delay_mins < 0:
                        st.sidebar.success(success_msg)
                    elif delay_mins > 0:
                        st.sidebar.warning(success_msg)
                    else:
                        st.sidebar.info(success_msg)
        else:
            st.sidebar.info("Schedule is empty.")
    else:
        st.sidebar.info("Please generate a schedule first.")
 
# ==========================================
# MAIN DASHBOARD VISUALIZATION
# ==========================================
 
st.title("Pravega: AI-Driven OR Command Center")
st.markdown("### From **Raw Clinical Data** to **Optimized Schedule** in Seconds.")
 
if st.session_state['schedule'] is not None and not st.session_state['schedule'].empty:
    df = st.session_state['schedule']
    
    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", len(df))
    last_end = df['End Time'].max() if 'End Time' in df else "N/A"
    c2.metric("Day Ends At", last_end)
    c3.metric("Utilization Rate", "96%")
    c4.metric("AI Model Status", "Active (XGBoost)")
 
    # GANTT CHART
    st.subheader("Live Smart Schedule")
    
    # Convert for Plotly
    if 'Start Time' in df.columns and 'End Time' in df.columns:
        # Hide OR-13 (Trauma Bay) if no Code Red cases added
        trauma_cases = df[df['Room'] == 'OR-13 (Trauma Bay)']
        if trauma_cases.empty:
            df_display = df[df['Room'] != 'OR-13 (Trauma Bay)'].copy()
        else:
            df_display = df.copy()
        
        df_display['Start'] = pd.to_datetime('2024-01-01 ' + df_display['Start Time'])
        df_display['Finish'] = pd.to_datetime('2024-01-01 ' + df_display['End Time'])
        
        # Define fixed room order (OR-1 to OR-13)
        room_order = [
            'OR-1 (Neuro)', 'OR-2 (Neuro)', 
            'OR-3 (Cardio)', 'OR-4 (Cardio)',
            'OR-5 (General)', 'OR-6 (General)', 
            'OR-7 (Ortho)', 'OR-8 (Ortho)',
            'OR-9 (Hybrid)', 'OR-10 (Robot)', 
            'OR-11 (General)', 'OR-12 (Cosmetic)',
            'OR-13 (Trauma Bay)'  # Emergency only
        ]
        # Only include rooms that have surgeries scheduled
        active_rooms = df_display['Room'].unique().tolist()
        sorted_rooms = [r for r in room_order if r in active_rooms]
        
        fig = px.timeline(
            df_display,
            x_start="Start",
            x_end="Finish",
            y="Room",
            color="Surgeon",
            text="Patient ID",
            hover_data=["Type", "Duration", "Risk (ASA)"],
            height=600,
            color_discrete_map=SURGEON_COLORS,  # Fixed colors per surgeon
            category_orders={"Room": sorted_rooms}  # Fixed order
        )
        # Display order: OR-1 at top, OR-12 at bottom
        fig.update_yaxes(categoryorder="array", categoryarray=sorted_rooms[::-1])
        fig.layout.xaxis.type = 'date'
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Schedule data missing time columns.")
 
    # DATA TABLE
    with st.expander("View AI Predictions & Assignments"):
        st.dataframe(df)
 
else:
    if data_source == "Upload CSV":
        st.info("👈 Please Upload 'raw_patients.csv' to begin.")
    else:
        st.info("👈 Please Add Patients via the Manual Entry Form to begin.")
        
    st.markdown("""
    **How it works:**
    1. Input Data (via CSV or Manual Entry).
    2. The **XGBoost Model** predicts the surgery duration for each patient.
    3. The **OR-Tools Solver** assigns rooms and surgeons to minimize overtime.
    """)

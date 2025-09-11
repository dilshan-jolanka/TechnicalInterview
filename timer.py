import streamlit as st
import time
from datetime import datetime, timedelta
import json
import os

# This is a standalone timer app that will be loaded in an iframe

# Load the session data to get the timer information
def load_session_data():
    """Load session data from the session state file"""
    try:
        session_file = 'data/session_state.json'
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                saved_state = json.load(f)
                
                # Extract timer data
                timer_data = {}
                if 'start_time' in saved_state and saved_state['start_time']:
                    # Parse ISO format datetime string
                    timer_data['start_time'] = datetime.fromisoformat(saved_state['start_time'])
                else:
                    timer_data['start_time'] = None
                
                timer_data['time_limit'] = saved_state.get('time_limit', 60)  # Default 60 minutes
                timer_data['time_expired'] = saved_state.get('time_expired', False)
                
                return timer_data
        return None
    except Exception as e:
        st.error(f"Error loading timer data: {str(e)}")
        return None

# Main timer display function
def display_timer():
    """Display the timer with automatic updates"""
    # Set page config to minimize UI elements
    st.set_page_config(
        page_title="Timer",
        page_icon="⏱️",
        layout="centered", 
        initial_sidebar_state="collapsed",
        menu_items=None
    )
    
    # Hide Streamlit elements
    hide_streamlit_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stApp {
            background: transparent;
        }
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Load timer data
    timer_data = load_session_data()
    
    if not timer_data or not timer_data.get('start_time'):
        st.markdown("<div style='text-align:center;'>Timer not started</div>", unsafe_allow_html=True)
        # Auto refresh every second until timer starts
        st.markdown(
            """
            <script>
                setTimeout(function() {
                    window.location.reload();
                }, 1000);
            </script>
            """, 
            unsafe_allow_html=True
        )
        return
    
    # Calculate time remaining
    current_time = datetime.now()
    elapsed_time = current_time - timer_data['start_time']
    time_limit_seconds = timer_data['time_limit'] * 60
    
    # Calculate remaining time
    remaining_seconds = max(time_limit_seconds - elapsed_time.total_seconds(), 0)
    remaining_minutes = int(remaining_seconds // 60)
    remaining_secs = int(remaining_seconds % 60)
    
    # Calculate progress percentage
    progress_percent = min(100, (1 - remaining_seconds / time_limit_seconds) * 100)
    
    # Determine timer color based on remaining time
    timer_color = "#4CAF50"  # Green by default
    if remaining_seconds < 300:  # Less than 5 minutes
        timer_color = "#f44336"  # Red
    elif remaining_seconds < 600:  # Less than 10 minutes
        timer_color = "#ff9800"  # Orange
    
    # Display timer
    st.markdown(
        f"""
        <div style="text-align:center; padding:10px;">
            <div style="font-size:28px; font-weight:bold; color:{timer_color};">
                {remaining_minutes:02d}:{remaining_secs:02d}
            </div>
            <div style="width:100%; height:6px; background-color:#f0f2f6; border-radius:3px; margin-top:10px;">
                <div style="width:{progress_percent}%; height:100%; background-color:{timer_color}; border-radius:3px;"></div>
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Check if time is expired
    if remaining_seconds <= 0 and not timer_data.get('time_expired', False):
        # Signal to parent window that time is up
        st.markdown(
            """
            <script>
                // Tell parent window time is expired
                if (window.parent) {
                    window.parent.postMessage('timer_expired', '*');
                }
            </script>
            """,
            unsafe_allow_html=True
        )
    
    # Auto refresh the timer every second
    if remaining_seconds > 0:
        st.markdown(
            """
            <script>
                setTimeout(function() {
                    window.location.reload();
                }, 1000);
            </script>
            """, 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    display_timer()

import streamlit as st

# Simple test to verify button functionality
st.title("Button Test")

if 'counter' not in st.session_state:
    st.session_state.counter = 0

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Previous", key="prev_test"):
        st.session_state.counter -= 1
        st.rerun()

with col2:
    st.write(f"Counter: {st.session_state.counter}")

with col3:
    if st.button("Next", key="next_test"):
        st.session_state.counter += 1
        st.rerun()

st.write("If you can see the counter changing, the basic button functionality works.")

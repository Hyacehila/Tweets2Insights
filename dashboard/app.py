"""Compatibility launcher for the new Intelligent UI."""
from intelligent_ui.app import main
import streamlit as st
st.navigation([st.Page(main,title='智能工作台',default=True)]).run()

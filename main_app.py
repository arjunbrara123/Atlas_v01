import streamlit as st
import importlib
import registry_service

from auth.auth_service import AuthService
from common.layout import render_frame

from config import ALL_PAGES, SECTION_ICONS
from security import (
    get_user_session,
    ensure_logged_in,
    get_allowed_pages_for_role,
)
from ui_nav import build_sidebar

# -------------------------------------------
# PAGE CONFIG
# -------------------------------------------
# ─── Page Config & CSS ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Commercial & Risk Intelligence",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded"
)
@st.cache_data
def load_css(file_path):
    with open(file_path) as f:
        return f.read()

# --- In your main script ---
css = load_css("style.css")
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
# st.markdown("""
#     <style>
#       .block-container { padding:2rem 4rem !important; }
#       [data-testid="stExpander"] [data-testid="stVerticalBlock"] { gap:0.3rem; }
#     </style>
# """, unsafe_allow_html=True)

# 1. Auth / session ---------------------------------
session = get_user_session()
auth = AuthService(mode="local")

# if not session["authenticated"]:
#     ensure_logged_in(auth)  # will render login form or set session
#     st.stop()

role = "admin" #session["role"]
user = session["user"]


# 2. Figure out what this role can see ----------------
allowed_envs = registry_service.get_visible_environments(user_role=role)
allowed_pages = get_allowed_pages_for_role(role, ALL_PAGES)

if not allowed_pages:
    st.error("Your role does not have access to any dashboards in Atlas.")
    st.stop()

# We must initialize the 'environment' in session state here.
# Get the list of all valid environment IDs
all_allowed_env_ids = [env['env_id'] for env in allowed_envs]

# Check if state is uninitialized OR if the current env is no longer valid
if ("environment" not in st.session_state
        or st.session_state["environment"] not in all_allowed_env_ids):

    # Set a new, valid default.
    # If the list is NOT empty, set to the first item.
    if all_allowed_env_ids:
        st.session_state["environment"] = all_allowed_env_ids[0]
    # If the list IS empty, set to None.
    else:
        st.session_state["environment"] = None

# 3. Draw sidebar + get nav state ---------------------
nav_state = build_sidebar(
    user=user,
    role=role,
    allowed_envs=allowed_envs,
    section_icons=SECTION_ICONS,
    allowed_pages=allowed_pages,
)

if nav_state["logout"]:
    # wipe session & rerun
    st.session_state.clear()
    st.rerun()

active_section = nav_state["active_section"]
active_page_label = nav_state["active_page_label"]
environment = nav_state["environment"]

# 4. Load and render the chosen page ------------------
module_path = allowed_pages[active_section][active_page_label]["module"]

try:
    module = importlib.import_module(f"apps.{module_path}")
    body_component, meta = module.render_page(
        role=role,
        environment=environment
    )
except ModuleNotFoundError:
    # "Coming soon" placeholder
    body_component = None
    meta = {
        "title_override": active_page_label,
        "last_updated": "N/A",
        "owner": "TBD",
        "data_source": "N/A",
        "coming_soon": True
    }
except Exception as e:
    # Catch any other error from within the page module
    st.error(f"An error occurred while rendering '{active_page_label}'.")
    st.exception(e) # Show the full traceback for debugging
    body_component = None
    meta = { "title_override": "Page Error" } # etc.

# 5. Wrap it in the Pulse frame -----------------------
render_frame(
    title_override = meta.get("title_override", active_page_label),
    body_component = body_component,
    last_updated   = meta.get("last_updated", "N/A"),
    owner          = meta.get("owner", "TBD"),
    data_source    = meta.get("data_source", "N/A"),
    coming_soon    = meta.get("coming_soon", False)
)
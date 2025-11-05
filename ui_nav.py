# ui_nav.py

import streamlit as st


def build_sidebar(user, role, allowed_envs, section_icons, allowed_pages):
    """
    Draw the sidebar UI and update session state
    (active_section, active_page_label, environment).

    This version is updated to use the DYNAMIC environment list, which is
    a list of dictionaries from the registry_service.

    Returns a dict:
      {
        "active_section": ...,
        "active_page_label": ...,
        "environment": ...,
        "logout": True/False
      }
    """

    # --- 1. Create a simple list of the ALLOWED ENV_IDs ---
    # This is for checking if the state is valid
    allowed_env_ids = [env['env_id'] for env in allowed_envs]

    # --- 2. Initialize Session State (Defaults) ---
    # (This section is now much simpler because main_app.py initialized it)

    if "active_section" not in st.session_state or st.session_state["active_section"] not in allowed_pages:
        st.session_state["active_section"] = list(allowed_pages.keys())[0]

    if (
            "active_page_label" not in st.session_state
            or st.session_state["active_page_label"] not in allowed_pages[st.session_state["active_section"]]
    ):
        st.session_state["active_page_label"] = list(
            allowed_pages[st.session_state["active_section"]].keys()
        )[0]

    if ("environment" not in st.session_state
            or st.session_state["environment"] not in allowed_env_ids):

        # Only set to [0] if the list is NOT empty
        if allowed_env_ids:
            st.session_state["environment"] = allowed_env_ids[0]
        else:
            # If no environments exist, set the state to None
            st.session_state["environment"] = None

    # --- 3. Get Active State ---
    active_section = st.session_state["active_section"]
    active_page_label = st.session_state["active_page_label"]
    # 'environment' is now the ACTIVE ENV_ID (a string, e.g., "Rep.Q225")
    environment = st.session_state["environment"]

    with st.sidebar:
        st.image("images/company_logo.png")

        st.write(f"**User:** {user}")

        # --- 4. Navigation (Unchanged) ---
        for section_name, pages in allowed_pages.items():
            icon = section_icons.get(section_name, "📁")
            expanded_default = (section_name == active_section)
            with st.expander(f"{icon} {section_name}", expanded=expanded_default):
                for page_label in pages.keys():
                    is_current = (section_name == active_section and page_label == active_page_label)
                    button_label = f"• {page_label}"
                    if is_current:
                        button_label = f"✅ {page_label}"
                    clicked = st.button(
                        button_label,
                        key=f"nav::{section_name}::{page_label}"
                    )
                    if clicked:
                        st.session_state["active_section"] = section_name
                        st.session_state["active_page_label"] = page_label
                        st.rerun()

        # --- 5. Help & Notes (Unchanged) ---
        with st.expander("🤔 Help & Support", expanded=False):
            st.markdown("**What changed this month**")
            st.caption(
                "- Capital model v1.3 approved\n- Ops repeat-visit metric added\n- New 'Live Q325' snapshot available")
            st.markdown("**Known data gaps**")
            st.caption("- Competitor feed (Scotland) under review")
            st.markdown("**Raise an issue**")
            st.caption("Log via System Status & Drafts (Admin / Dev).")

        # --- 6. Environment Picker (THE CRITICAL FIX) ---

        # We need to tell the selectbox *what* to display
        # This function takes a row (e.g., {"env_id": "Rep.Q225", "env_name": "Reporting_Q225"})
        # and returns the string to show the user (e.g., "Reporting_Q225")
        def format_env_option(env_dict):
            return env_dict['env_name']

        # We also need to find the index of the *currently selected* env_id
        current_env_index = 0
        for i, env_dict in enumerate(allowed_envs):
            if env_dict['env_id'] == environment:
                current_env_index = i
                break

        new_env_dict = st.selectbox(
            "Select environment",
            options=allowed_envs,
            index=current_env_index,
            format_func=format_env_option,  # <-- Tells selectbox to show the 'env_name'
            label_visibility="visible"
        )

        # new_env_dict is the *full dictionary* of the selected env
        # The rest of the app needs just the ID
        if new_env_dict:
            new_env_id = new_env_dict['env_id']  # <--- This line is now safe
            if new_env_id != environment:
                st.session_state["environment"] = new_env_id  # <-- Store just the ID
                st.rerun()
        elif st.session_state["environment"] is not None:
            # This should not happen if allowed_envs is not empty,
            # but it's safe to handle.
            st.session_state["environment"] = None
            st.rerun()

        # --- 7. Sidebar Footer (Unchanged) ---
        st.markdown("---")
        st.write(f"**Role:** `{role}`")

        alice_popup = st.button("🙋‍♀️ Ask Alice")
        logout_clicked = st.button("🔐 Log Out")

    # --- 8. Return the active STATE (all strings) ---
    return {
        "active_section": st.session_state["active_section"],
        "active_page_label": st.session_state["active_page_label"],
        "environment": st.session_state["environment"],  # This is now the 'env_id' string
        "logout": logout_clicked
    }
# security.py

import streamlit as st

# Which environments each role can see.
# Two parts:
#  - "explicit": named envs they're allowed
#  - "prefixes": any env starting with this string is also allowed
ROLE_ENV_RULES = {
    "admin": {
        "explicit": [
            "dev", "test", "preprod", "prod",
            "archive_2025-09", "archive_2025-10"
        ],
        "prefixes": ["Live Q"]
    },
    "developer": {
        "explicit": [
            "dev", "test", "preprod"
        ],
        "prefixes": []
    },
    "inputs_admin": {
        "explicit": [
            "dev", "test", "preprod"
        ],
        "prefixes": []
    },
    "risk": {
        "explicit": [
            "preprod",
            "prod",
            "archive_2025-09",
            "archive_2025-10"
        ],
        "prefixes": ["Live Q"]
    },
    "commercial": {
        "explicit": [
            "prod",
            "archive_2025-09",
            "archive_2025-10"
        ],
        "prefixes": ["Live Q"]
    },
    "exec": {
        "explicit": [
            "prod"
        ],
        "prefixes": ["Live Q"]
    }
}


def get_user_session():
    """Return (and initialise if needed) the session dict for auth."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["role"] = None
        st.session_state["user"] = None
    if "active_section" not in st.session_state:
        st.session_state["active_section"] = None
    if "active_page_label" not in st.session_state:
        st.session_state["active_page_label"] = None
    if "environment" not in st.session_state:
        st.session_state["environment"] = None

    return {
        "authenticated": st.session_state["authenticated"],
        "role": st.session_state["role"],
        "user": st.session_state["user"]
    }


def ensure_logged_in(auth_service):
    """
    If not logged in, render login UI and update session on success.
    auth_service = AuthService(...)
    """
    st.title("Pulse Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Log in")

    if login_btn:
        result = auth_service.login(username, password)
        if result.authenticated:
            st.session_state["authenticated"] = True
            st.session_state["role"] = result.role
            st.session_state["user"] = result.user
            st.rerun()
        else:
            st.error(result.error or "Login failed.")


def get_allowed_envs_for_role(role, all_envs):
    """
    Return the list of environments this role can access, in the
    global order of all_envs.
    """
    rules = ROLE_ENV_RULES.get(role, {"explicit": [], "prefixes": []})
    explicit = set(rules["explicit"])
    prefixes = rules["prefixes"]

    # Add environments that match any allowed prefix
    for env in all_envs:
        for pref in prefixes:
            if env.startswith(pref):
                explicit.add(env)

    # Keep the order from all_envs
    ordered = [env for env in all_envs if env in explicit]
    return ordered


def get_allowed_pages_for_role(role, all_pages):
    """
    Filter ALL_PAGES down to only the sections/pages this role can view.
    Returns a dict in the same shape as ALL_PAGES but pruned.
    """
    filtered = {}
    for section_name, pages in all_pages.items():
        allowed_pages = {}
        for page_label, page_info in pages.items():
            if role in page_info["allowed_roles"]:
                allowed_pages[page_label] = page_info
        if allowed_pages:
            filtered[section_name] = allowed_pages
    return filtered

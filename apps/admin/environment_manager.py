"""
apps/internal/environment_manager.py

This is a FOCUSED admin dashboard for managing the environment
lifecycle (Table 1). It is the "Infrastructure" tool.

It does NOT manage File Blueprints (Table 2) or System Health.
Those are in separate dashboards.

[NEW FEATURES]
This dashboard has been upgraded to a true "Mission Control":
- "Dashboard" [Tab 1] now includes a "Visual Lineage" graph
  to show how all environments are related.
- "Create Workspace" [Tab 2] now includes an "Optional] Clone
  Project Plan" feature to provision new envs with a pre-built plan.
- "Manage & Audit" [Tab 4] now shows "Quick Stats" for any
  selected environment and includes a [DESTRUCTIVE] "Prune Files"
  action for 'Archived' environments.
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import json
import graphviz # <-- [NEW] For Visual Lineage

# --- Helper Functions (specific to this dashboard) ---

def render_env_status_badge(status):
    """Renders a colored badge for an environment status."""
    color_map = {
        "Active": "blue",
        "Locked": "green",
        "Archived": "gray",
        "Pending": "orange",
        "Rejected": "red",
    }
    st.markdown(f"Status: **<span style='color:{color_map.get(status, 'gray')};'>●</span> {status}**", unsafe_allow_html=True)

# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        self.role = role
        self.app_environment = environment # The *app's* current env
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.meta = {
            "title_override": "Environment Manager",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        # Define role lists for forms
        self.all_roles = ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        self.env_categories = ["Production", "Reporting", "Validation", "Testing", "Development"]
        self.env_statuses = ["Active", "Locked", "Archived", "Pending"]
        self.all_folders = ["Data Inputs", "Actuarial Models", "Results & Validation", "Reports & Insights"]
        self.versioning_logics = ["Latest Approved", "Full History (No Superseded)", "Carbon Copy (Forensic)"]

        # Load data on init
        self.refresh_data()

    def refresh_data(self):
        """Gets all environments from the registry service."""
        try:
            self.all_envs = registry_service.get_all_environments()
        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.all_envs = []

    # --- TAB 1: DASHBOARD ---
    def _render_dashboard_tab(self):
        """Displays all environments in a filterable table."""
        st.subheader("📊 Environment Dashboard")
        st.markdown("A 'mission control' view of all environments currently in the registry.")

        if not self.all_envs:
            st.info("No environments found. Use the 'Create' tab to add one.")
            return

        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Environments", len(self.all_envs))
        c2.metric("Active Workspaces", len([e for e in self.all_envs if e['current_status'] == 'Active']))
        c3.metric("Locked Snapshots", len([e for e in self.all_envs if e['current_status'] == 'Locked']))

        st.markdown("---")

        # --- [NEW] Feature: Visual Lineage ---
        with st.expander("🗺️ Show Visual Environment Lineage Graph"):
            st.markdown(
                """
                This "family tree" shows how all environments are related. It is
                generated automatically by reading the `source_env_id` from
                each environment's record.
                """
            )
            self._render_lineage_graph()

        st.markdown("---")
        st.subheader("Registry Details")

        # --- Filters ---
        c1, c2 = st.columns(2)
        filter_cat = c1.multiselect("Filter by Category", self.env_categories, default=self.env_categories)
        filter_status = c2.multiselect("Filter by Status", self.env_statuses, default=["Active", "Locked"])

        filtered_envs = [
            env for env in self.all_envs
            if env['env_cat'] in filter_cat and env['current_status'] in filter_status
        ]

        st.markdown(f"Displaying **{len(filtered_envs)}** environments.")
        st.dataframe(filtered_envs, use_container_width=True, column_order=(
            "env_id", "env_name", "env_cat", "current_status", "allowed_roles", "source_env_id", "created_at", "creator_user_id"
        ))

        st.markdown("---")
        st.subheader("🔍 Recent Environment Audit Log")
        st.caption("A view of the last 100 *human actions* taken on environments in the registry (from Table 8).")
        try:
            audit_log = registry_service.get_environment_audit_log_all()
            if not audit_log:
                st.info("No audit history found for any environment.")
            else:
                st.dataframe(audit_log, use_container_width=True, height=300, column_order=(
                    "timestamp", "user_id", "action", "target_id", "signoff_capacity", "comment"
                ))
        except Exception as e:
            st.error(f"Failed to load audit log: {e}")

    def _render_lineage_graph(self):
        """
        [NEW] Renders a Graphviz "family tree" of all environments
        based on their `source_env_id`.
        """
        if not self.all_envs:
            st.info("No environments to graph.")
            return

        try:
            dot = graphviz.Digraph(comment='Environment Lineage')
            dot.attr(rankdir='LR', splines='ortho', ranksep='1.0', nodesep='0.5')
            dot.attr('node', shape='box', style='rounded,filled', fillcolor='white', fontname='Arial')
            dot.attr('edge', fontname='Arial', fontsize='10', arrowsize='0.7')

            # Define nodes with colors
            color_map = {
                "Production": "#D1E8FF", # light blue
                "Reporting": "#D1FFD6", # light green
                "Validation": "#FFF0D1", # light orange
                "Testing": "#E8D1FF", # light purple
                "Development": "#F5F5F5", # light gray
                "Archived": "#E0E0E0"
            }

            for env in self.all_envs:
                env_id = env['env_id']
                label = f"{env['env_name']}\n({env_id})"

                # Determine fill color
                fillcolor = color_map.get(env['env_cat'], '#F5F5F5')
                if env['current_status'] == 'Archived':
                    fillcolor = color_map['Archived']

                dot.node(env_id, label=label, fillcolor=fillcolor)

            # Define edges
            for env in self.all_envs:
                source_id = env.get('source_env_id')
                if source_id:
                    # Check if source exists to prevent orphan edges
                    if any(e['env_id'] == source_id for e in self.all_envs):
                        dot.edge(source_id, env['env_id'], label="Cloned")

            st.graphviz_chart(dot, use_container_width=True)

        except Exception as e:
            st.error(f"Could not render lineage graph. Is Graphviz installed? Error: {e}")


    # --- TAB 2: CREATE / CLONE WIZARD (THE "SMART" UI) ---
    def _render_create_wizard_tab(self):
        """Form for creating a new environment from scratch OR by cloning."""
        st.subheader("➕ Create / Clone Wizard")
        st.markdown(
            "Use this wizard to create a new, self-contained environment."
            "This will create its 'blueprint' (Table 1) and its"
            "physical 4-folder structure."
        )

        # --- STEP 1: CHOOSE METHOD (OUTSIDE THE FORM) ---
        st.markdown("##### 1. How do you want to create this?")
        create_method = st.radio(
            "Creation Method",
            ["Create new empty environment (Start from scratch)",
             "Clone an existing environment (Start from a copy of *files*)"],
            key="create_method",
            label_visibility="collapsed"
        )

        # --- STEP 2: THE FORM (CONDITIONAL UI) ---
        with st.form("create_env_form"):

            st.markdown("##### 2. What is this new environment for?")
            c1, c2 = st.columns(2)
            env_cat_prefix_map = registry_service.ENV_CATEGORY_PREFIX_MAP
            env_cat = c1.selectbox("Environment Category", self.env_categories)
            env_id_suffix = c2.text_input("Environment Name Suffix", "Q425_Draft_v1", help="e.g., Q425_Draft_v1 or NewFeature_Test")

            # Enforce naming convention
            env_id_prefix = env_cat_prefix_map.get(env_cat, "NA")
            final_env_id = f"{env_id_prefix}.{env_id_suffix}"
            final_env_name = f"{env_cat}_{env_id_suffix}"

            st.info(f"**Final Environment ID:** `{final_env_id}`\n\n**Final Folder Name:** `{final_env_name}`")

            # --- STEP 3: DYNAMIC CLONE OPTIONS ---
            source_env_id = None
            folders_to_clone = self.all_folders # Default to all
            versioning_logic = "Carbon Copy (Forensic)" # Default to safest

            if "Clone" in create_method:
                st.markdown("##### 3a. Clone *File* Settings")
                if not self.all_envs:
                    st.error("No environments exist to be cloned.")
                    st.form_submit_button("Create Environment", disabled=True)
                    return

                env_options = {env['env_id']: f"{env['env_id']} ({env['env_name']})" for env in self.all_envs}
                source_env_id = st.selectbox(
                    "Select Source Environment to Clone *Files* From",
                    options=env_options.keys(),
                    format_func=lambda x: env_options.get(x)
                )

                # --- This is the "Smart UI" Logic ---
                if env_cat in ["Development", "Testing"]:
                    # "Max Flexibility" Mode
                    st.markdown("**Developer/Test Options (Max Flexibility):**")
                    folders_to_clone = st.multiselect("Which folders to clone?", self.all_folders, default=self.all_folders)
                    versioning_logic = st.radio("Which file versions to clone?", self.versioning_logics, index=2)

                elif env_cat == "Production":
                    # "Analyst" Mode (Safe)
                    st.markdown("**Production Workspace Options (Safe):**")
                    clone_data_only = st.checkbox("Pre-populate with 'Data Inputs' (Latest Approved Only)", value=True)
                    if clone_data_only:
                        folders_to_clone = ["Data Inputs"]
                        versioning_logic = "Latest Approved"
                    else:
                        folders_to_clone = []

                elif env_cat in ["Reporting", "Validation"]:
                    st.error(f"**Action Blocked:** `Reporting` and `Validation` environments are high-governance and cannot be created here. Please use the **'Promote & Validate'** tab.")
                    st.form_submit_button("Create Environment", disabled=True)
                    return

            # --- [NEW] Feature: Clone Project Plan ---
            st.markdown("##### 3b. [Optional] Clone Project Plan")
            st.caption("Provision this new environment with a copy of an existing project plan.")

            if not self.all_envs:
                st.info("No environments exist to clone a plan from.")
                clone_plan_from_env_id = None
            else:
                plan_env_options = {env['env_id']: f"{env['env_id']} ({env['env_name']})" for env in self.all_envs}
                # Add "None" option
                plan_env_options = {"NONE": "Do not clone a project plan", **plan_env_options}

                clone_plan_from_env_id = st.selectbox(
                    "Select Source Environment to Clone *Plan* From",
                    options=plan_env_options.keys(),
                    format_func=lambda x: plan_env_options.get(x)
                )
                if clone_plan_from_env_id == "NONE":
                    clone_plan_from_env_id = None

            st.markdown("##### 4. Governance & Purpose")
            allowed_roles = st.multiselect("Allowed Roles (Who can see this?)", self.all_roles, default=self.all_roles)
            purpose = st.text_area("Purpose", help="Briefly describe the business purpose of this environment.")

            st.markdown("##### 5. Confirmation")
            comment = st.text_input("Audit Comment", value="Initial creation.")
            submitted = st.form_submit_button("Create Environment")

            if submitted:
                if not all([env_id_suffix, env_cat, purpose, allowed_roles, comment]):
                    st.error("All fields are required.")
                elif "Clone" in create_method and not source_env_id:
                    st.error("You must select a source environment to clone *files* from.")
                else:
                    action_noun = "Cloning" if source_env_id else "Creating"
                    with st.spinner(f"{action_noun} '{final_env_id}'... This may take a few minutes if cloning files or plans."):

                        if source_env_id:
                            # --- CLONE WORKFLOW ---
                            success, message = registry_service.clone_environment(
                                source_env_id=source_env_id,
                                new_env_id=final_env_id, new_env_name=final_env_name, new_cat=env_cat,
                                new_purpose=purpose, new_allowed_roles=allowed_roles,
                                user_id=self.user_id, comment=comment, new_status="Active",
                                folders_to_clone=folders_to_clone,
                                versioning_logic=versioning_logic,
                                clone_plan_from_env_id=clone_plan_from_env_id # <-- [NEW] Pass this in
                            )
                        else:
                            # --- CREATE NEW WORKFLOW ---
                            success, message = registry_service.create_new_environment(
                                final_env_id, final_env_name, env_cat, purpose, allowed_roles, self.user_id, comment,
                                clone_plan_from_env_id=clone_plan_from_env_id # <-- [NEW] Pass this in
                            )

                        if success:
                            st.success(message); self.refresh_data(); st.rerun()
                        else:
                            st.error(message)

    # --- TAB 3: PROMOTE & VALIDATE ---
    def _render_promote_validate_tab(self):
        # ... (This function remains unchanged) ...
        st.subheader("🚀 Promote & Validate")
        st.markdown("These are high-level governance actions to create **locked snapshots** or **forensic copies** for audit.")

        if not self.all_envs:
            st.warning("No environments found. Please create one in the 'Create' tab.")
            return

        prod_envs = [e for e in self.all_envs if e['env_cat'] == 'Production' and e['current_status'] == 'Active']
        all_active_envs = [e for e in self.all_envs if e['current_status'] in ['Active', 'Locked']]

        col1, col2 = st.columns(2)

        # --- Section 1: Promote to Reporting ---
        with col1:
            with st.form("promote_form"):
                st.markdown("##### 🚀 Promote to Reporting (Go Live)")
                st.markdown(f"Create a **clean, locked** `Reporting` snapshot from a `Production` workspace.")

                if not prod_envs:
                    st.error("No 'Active' `Production` environments exist to be promoted.")
                    st.form_submit_button("Promote to Reporting", disabled=True)
                else:
                    env_options = {env['env_id']: f"{env['env_id']} ({env['env_name']})" for env in prod_envs}
                    source_env_id = st.selectbox("Select `Production` Environment to Promote", options=env_options.keys(), format_func=lambda x: env_options.get(x))

                    promote_env_suffix = st.text_input("New 'Reporting' Suffix", "Q425_v1", help="e.g., Q425_v1 or Q425_Restatement_v2")
                    promote_purpose = st.text_area("Purpose", f"Reporting snapshot from {source_env_id}.")
                    promote_roles = st.multiselect("Allowed Roles", self.all_roles, default=self.all_roles)
                    promote_comment = st.text_input("Audit Comment", "Promoting to Reporting for ExCo.")

                    promote_submitted = st.form_submit_button("Promote to Reporting")

                    if promote_submitted:
                        final_env_id = f"Rep.{promote_env_suffix}"
                        final_env_name = f"Reporting_{promote_env_suffix}"

                        with st.spinner(f"Creating 'Clean Snapshot' {final_env_id}..."):
                            success, message = registry_service.clone_environment(
                                source_env_id=source_env_id,
                                new_env_id=final_env_id, new_env_name=final_env_name, new_cat="Reporting",
                                new_purpose=promote_purpose, new_allowed_roles=promote_roles,
                                user_id=self.user_id, comment=promote_comment, new_status="Locked",
                                folders_to_clone=self.all_folders, # Clone all folders
                                versioning_logic="Latest Approved", # Use "Clean Snapshot" logic
                                clone_plan_from_env_id=source_env_id # <-- [NEW] Promote the plan too!
                            )
                            if success: st.success(message); self.refresh_data(); st.rerun()
                            else: st.error(message)

        # --- Section 2: Clone for Validation ---
        with col2:
            with st.form("validate_form"):
                st.markdown("##### 🛡️ Clone for Validation (Audit)")
                st.markdown(f"Create a **full, forensic carbon copy** of *any* environment for audit or peer review.")

                if not all_active_envs:
                    st.error("No environments exist to be cloned.")
                    st.form_submit_button("Clone for Validation", disabled=True)
                else:
                    env_options = {env['env_id']: f"{env['env_id']} ({env['env_name']})" for env in all_active_envs}
                    source_env_id = st.selectbox("Select *Any* Environment to Clone", options=env_options.keys(), format_func=lambda x: env_options.get(x))

                    validate_env_suffix = st.text_input("New 'Validation' Suffix", f"{source_env_id}_Audit_01")
                    validate_env_id = f"Val.{validate_env_suffix}"
                    validate_env_name = f"Validation_{validate_env_suffix}"
                    st.info(f"This will create: `{validate_env_id}`")

                    validate_purpose = st.text_area("Purpose", f"Forensic clone of {source_env_id} for audit.")
                    validate_roles = st.multiselect("Allowed Roles", self.all_roles, default=['admin', 'risk'])
                    validate_comment = st.text_input("Audit Comment", "Creating validation clone for auditors.")

                    validate_submitted = st.form_submit_button("Clone for Validation")

                    if validate_submitted:
                        with st.spinner(f"Creating 'Forensic Copy' {validate_env_id}..."):
                            success, message = registry_service.clone_environment(
                                source_env_id=source_env_id,
                                new_env_id=validate_env_id, new_env_name=validate_env_name, new_cat="Validation",
                                new_purpose=validate_purpose, new_allowed_roles=validate_roles,
                                user_id=self.user_id, comment=validate_comment, new_status="Active",
                                folders_to_clone=self.all_folders, # Clone all folders
                                versioning_logic="Carbon Copy (Forensic)", # Use "Full History" logic
                                clone_plan_from_env_id=source_env_id # <-- [NEW] Clone the plan too!
                            )
                            if success: st.success(message); self.refresh_data(); st.rerun()
                            else: st.error(message)

    # --- TAB 4: MANAGE & AUDIT ---
    def _render_manage_tab(self):
        """UI for Editing and Archiving existing environments."""
        st.subheader("⚙️ Manage & Audit Environment")
        st.markdown("Use this tab to **Edit** an environment's metadata (e.g., name or roles), view its **Quick Stats**, or **Archive / Prune** it.")

        if not self.all_envs:
            st.warning("No environments found. Please create one in the 'Create' tab.")
            return

        env_options = {env['env_id']: f"{env['env_id']} ({env['env_name']})" for env in self.all_envs}
        selected_env_id = st.selectbox("Select Environment to Manage/Audit", options=env_options.keys(), format_func=lambda x: env_options.get(x))

        if not selected_env_id:
            return

        try:
            env_data = registry_service.get_environment_by_id(selected_env_id)
            if not env_data:
                st.error("Could not load environment data."); return
        except Exception as e:
            st.error(f"Failed to load environment data: {e}"); return

        st.markdown("---")
        render_env_status_badge(env_data['current_status'])

        # --- [NEW] Feature: Quick Stats ---
        st.markdown("##### Quick Stats")
        st.caption(f"A high-level summary of the contents of **{selected_env_id}**.")
        try:
            stats = registry_service.get_environment_quick_stats(selected_env_id)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Files (All Versions)", stats.get('file_count_total', 0))
            c2.metric("Project Tasks", f"{stats.get('plan_task_complete', 0)} / {stats.get('plan_task_total', 0)} Complete")
            c3.metric("Open Action Items", stats.get('action_item_open', 0))
        except Exception as e:
            st.error(f"Failed to load quick stats: {e}")

        st.markdown("---")

        # --- Section 1: Edit Metadata / Archive ---
        with st.form("edit_form"):
            st.markdown("##### Edit or Archive Environment")
            st.caption(f"You are editing **{selected_env_id}**.")

            c1, c2 = st.columns(2)
            env_name = c1.text_input("Environment Name", value=env_data['env_name'])

            if env_data['current_status'] == 'Locked':
                available_statuses = ['Locked', 'Archived']
            else:
                available_statuses = ['Active', 'Pending', 'Archived']
            status = c2.selectbox("Set Current Status", available_statuses, index=available_statuses.index(env_data['current_status']))

            purpose = st.text_area("Purpose", value=env_data['purpose'])
            allowed_roles = st.multiselect("Allowed Roles", self.all_roles, default=env_data['allowed_roles'].split(','))

            comment = st.text_input("Audit Comment for this change", help="e.g., 'Archiving as Q4 cycle is complete.'")
            edit_submitted = st.form_submit_button("Save Changes")

            if edit_submitted:
                if not comment:
                    st.error("An 'Audit Comment' is required to make any changes.")
                else:
                    with st.spinner("Updating environment..."):
                        success, message = registry_service.edit_environment(
                            selected_env_id, env_name, purpose, allowed_roles, status, self.user_id, comment
                        )
                        if success: st.success(message); self.refresh_data(); st.rerun()
                        else: st.error(message)

        # --- [NEW] Feature: Prune Files "Danger Zone" ---
        if env_data['current_status'] == 'Archived':
            st.markdown("---")
            with st.expander("🔥 [DANGER ZONE] Prune Archived Environment", expanded=True):
                st.error(
                    """
                    **WARNING: This is a destructive and irreversible action.**
                    
                    This will **permanently delete all physical files and folders**
                    associated with this environment from the file server.
                    
                    The database records (audit logs, file history, etc.) will be
                    **kept** for a perfect historical record.
                    """
                )

                with st.form("prune_form"):
                    st.markdown(f"To confirm, please type the environment ID: **{selected_env_id}**")
                    confirmation = st.text_input("Confirmation ID")

                    prune_submitted = st.form_submit_button("🔥 Prune All Physical Files")

                    if prune_submitted:
                        if confirmation != selected_env_id:
                            st.error("Confirmation ID does not match. Action cancelled.")
                        else:
                            with st.spinner(f"Pruning files for {selected_env_id}..."):
                                success, message = registry_service.prune_archived_environment(
                                    selected_env_id, self.user_id
                                )
                                if success:
                                    st.success(message)
                                    # We don't need to rerun, the status is the same
                                else:
                                    st.error(message)


    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It injects CSS and renders the tabs.
        """

        st.markdown(
            """
            <style>
                div[data-testid="stForm"] {
                    border: 1px solid #E0E0E0;
                    border-radius: 10px;
                    padding: 1.5rem;
                    margin-top: 1rem;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Define the tabs
        tab_dash, tab_create, tab_promote_validate, tab_manage_audit = st.tabs(
            [
                "📊 Dashboard & Lineage", # [MODIFIED]
                "➕ Create Workspace",
                "🚀 Promote & Validate",
                "⚙️ Manage & Audit"
            ]
        )

        # Render content for each tab
        with tab_dash:
            self.refresh_data()
            self._render_dashboard_tab()

        with tab_create:
            self._render_create_wizard_tab()

        with tab_promote_validate:
            self._render_promote_validate_tab()

        with tab_manage_audit:
            self._render_manage_tab()

# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
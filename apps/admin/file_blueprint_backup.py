"""
apps/internal/file_blueprint_manager.py

This is a FOCUSED admin dashboard for managing the
File Blueprints (Table 2). It is the "Data Governance" tool.

v5 (The "Best Possible" UI):
- Rebuilds the "Create/Manage" tab into a 3-step "Smart Wizard"
  per user feedback.
- Fixes the `st.form` conditional UI bug permanently.
- Fixes the `TypeError` by correctly packaging `form_data` as a dict.
- Adds the "Create by Cloning" feature.
- Implements "Safe Delete" (with dependency check) on the Health tab.
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import json

# --- Helper Functions (specific to this dashboard) ---

def render_blueprint_status_badge(status):
    """Renders a colored badge for a blueprint status."""
    color_map = {"Active": "blue", "Archived": "gray"}
    st.markdown(f"Status: **<span style='color:{color_map.get(status, 'gray')};'>●</span> {status}**", unsafe_allow_html=True)

def _parse_structure_to_json(file_type: str, structure_input: str) -> str:
    """Builds the "messy JSON" in the background from simple user input."""
    try:
        if file_type == "Spreadsheet":
            tabs = [s.strip() for s in structure_input.split(",") if s.strip()]
            if not tabs: return "{}"
            return json.dumps({"tabs": tabs})
        elif file_type == "CSV/TXT":
            cols = [c.strip() for c in structure_input.split(",") if c.strip()]
            if not cols: return "{}"
            return json.dumps({"columns": cols})
        else:
            return "{}"
    except Exception as e:
        st.error(f"Error building structure JSON: {e}")
        return "{}"

def _parse_json_to_ui(structure_json: str) -> (str, str):
    """Reverse-engineers the JSON to populate the simple UI fields."""
    try:
        data = json.loads(structure_json or "{}")
        if "tabs" in data and data["tabs"]:
            return "Spreadsheet", ", ".join(data["tabs"])
        if "columns" in data and data["columns"]:
            return "CSV/TXT", ", ".join(data["columns"])
    except json.JSONDecodeError:
        return "Other (JSON, Parquet, etc.)", structure_json
    return "Other (JSON, Parquet, etc.)", ""

# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        self.role = role
        self.app_environment = environment
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.meta = {
            "title_override": "File Blueprint Manager",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        # --- Define all our form options ---
        self.all_roles = ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        self.file_blueprint_stages = ["Data Inputs", "Actuarial Models", "Results & Validation", "Reports & Insights"]
        self.file_creation_methods = ["Manual Upload", "User-Triggered Job"]
        self.file_signoff_workflows = ["Doer Only", "Doer + Reviewer"]
        self.file_types_map = {
            "Spreadsheet": [".xlsx", ".xlsb", ".xlsm"],
            "CSV/TXT": [".csv", ".txt", ".prn"],
            "Other (JSON, Parquet, etc.)": [".parquet", ".json", ".zip"]
        }
        self.file_types = list(self.file_types_map.keys())

        self.refresh_data()

    def refresh_data(self):
        """Gets all blueprints from the registry service."""
        try:
            self.all_blueprints = registry_service.get_all_file_blueprints()
        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.all_blueprints = []

    # --- TAB 1: DASHBOARD / DATA CATALOG ---
    def _render_dashboard_tab(self):
        """Displays all file blueprints in a filterable table."""
        st.subheader("📖 File Blueprint Dashboard (Data Catalog)")
        st.markdown("This is the 'master list' of all *valid file types* the platform is allowed to use.")

        if not self.all_blueprints:
            st.info("No File Blueprints found. Use the 'Create/Manage' tab to add one.")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Blueprints", len(self.all_blueprints))
        c2.metric("Active Blueprints", len([b for b in self.all_blueprints if b['template_status'] == 'Active']))
        c3.metric("Archived Blueprints", len([b for b in self.all_blueprints if b['template_status'] == 'Archived']))
        st.markdown("---")

        c1, c2, c3 = st.columns(3)
        filter_stage = c1.multiselect("Filter by Stage", self.file_blueprint_stages, default=self.file_blueprint_stages)
        all_owners = sorted(list(set(b['data_owner_team'] for b in self.all_blueprints if b['data_owner_team'])))
        filter_owner = c2.multiselect("Filter by Owner", all_owners, default=all_owners if len(all_owners) < 10 else None)
        filter_status = c3.multiselect("Filter by Status", ["Active", "Archived"], default=["Active"])

        filtered_bps = [
            bp for bp in self.all_blueprints
            if bp['stage'] in filter_stage and
               (not filter_owner or bp['data_owner_team'] in filter_owner) and
               bp['template_status'] in filter_status
        ]

        st.markdown(f"Displaying **{len(filtered_bps)}** file blueprints.")
        st.dataframe(filtered_bps, use_container_width=True, column_order=(
            "template_id", "template_name", "stage", "data_owner_team", "template_status", "signoff_workflow",
            "source_type", "expected_extension"
        ))

    # --- TAB 2: CREATE / MANAGE BLUEPRINT (THE "SMART UI" WIZARD) ---
    def _render_manage_tab(self):
        """UI for Creating and Editing File Blueprints (Table 2)."""
        st.subheader("⚙️ Create / Manage Blueprints")
        st.markdown("Use this wizard to create, edit, or clone a file blueprint.")

        # --- STEP 1: THE WIZARD CONTROLLER (OUTSIDE THE FORM) ---

        # We use session state to manage the wizard's mode.
        if 'bp_manage_action' not in st.session_state:
            st.session_state.bp_manage_action = "Create New"
        if 'bp_selected_id' not in st.session_state:
            st.session_state.bp_selected_id = None
        if 'bp_create_file_type' not in st.session_state:
            st.session_state.bp_create_file_type = self.file_types[0] # Default

        # --- This is your new 2-column controller ---
        c1, c2 = st.columns(2)

        # Column 1: Select the Action


        action = c1.segmented_control(
            "Choose a BluePrint Option",
            options=["💡 Create New", "🛠️ Edit Existing", "🏗️ Clone Existing"],
            key="bp_action_radio",
            selection_mode="single"
        )

        # Column 2: The *Dynamic* Selector
        bp_options = {bp['template_id']: f"{bp['template_id']} ({bp['template_name']})" for bp in self.all_blueprints}

        if action == "💡 Create New":
            file_type = c2.selectbox("Select File Type", self.file_types, key="bp_file_type_select")
            # Store the choices in state
            st.session_state.bp_manage_action = "CREATE"
            st.session_state.bp_create_file_type = file_type

        elif action == "🛠️ Edit Existing":
            selected_id = c2.selectbox("Select Blueprint to Edit", options=[""] + list(bp_options.keys()),
                                       format_func=lambda x: "Select..." if x == "" else bp_options.get(x))
            st.session_state.bp_manage_action = "EDIT"
            st.session_state.bp_selected_id = selected_id

        elif action == "🏗️ Clone Existing":
            selected_id = c2.selectbox("Select Blueprint to Clone", options=[""] + list(bp_options.keys()),
                                       format_func=lambda x: "Select..." if x == "" else bp_options.get(x))
            st.session_state.bp_manage_action = "CLONE"
            st.session_state.bp_selected_id = selected_id

        st.markdown("---")

        # --- STEP 2: THE FORM (CONDITIONAL) ---

        # We check the state we just set
        current_mode = st.session_state.bp_manage_action

        # Load the correct data for the form
        bp = {} # Our blank form data
        is_new = True

        if current_mode == "CREATE":
            is_new = True
            form_title = "Create New File Blueprint"
            bp['file_type'] = st.session_state.bp_create_file_type
            bp['expected_extension'] = self.file_types_map.get(bp['file_type'], ['.csv'])[0]
            bp['structure_str'] = ""

        elif current_mode in ["EDIT", "CLONE"]:
            if not st.session_state.bp_selected_id:
                st.info("Please select a blueprint from the dropdown above to continue.")
                return

            bp_data = registry_service.get_file_blueprint_by_id(st.session_state.bp_selected_id)
            if not bp_data:
                st.error(f"Error: Could not find blueprint {st.session_state.bp_selected_id}")
                return
            bp = dict(bp_data) # Convert from Row to dict

            # Pre-fill the file type and structure string
            bp['file_type'], bp['structure_str'] = _parse_json_to_ui(bp.get('expected_structure', ''))

            if current_mode == "EDIT":
                is_new = False
                form_title = f"Editing Blueprint: {bp.get('template_id')}"

            if current_mode == "CLONE":
                is_new = True # A clone is a "NEW" record
                form_title = f"Creating New Blueprint (Cloned from {bp.get('template_id')})"
                # CRITICAL: We clear the template_id to force the user to create a new, unique one.
                bp['template_id'] = ""
                bp['template_name'] = f"Copy of {bp.get('template_name')}"

        else:
            # No mode selected, don't show a form.
            return

        # --- This is the new, user-friendly form ---
        with st.form("blueprint_form"):
            st.markdown(f"##### {form_title}")

            st.markdown("##### Basic Details")
            c1, c2 = st.columns(2)
            template_id = c1.text_input("Template ID (e.g., `biz_plan_q4`)", value=bp.get('template_id', ''),
                                        disabled=not is_new, help="This is the 🗝️ Key and cannot be changed after creation.")
            template_name = c2.text_input("Template Name", value=bp.get('template_name', ''))
            stage = st.selectbox("Data Flow Stage", self.file_blueprint_stages,
                                 index=self.file_blueprint_stages.index(bp.get('stage')) if bp.get('stage') in self.file_blueprint_stages else 0)

            st.markdown("##### Governance & Source")
            c1, c2 = st.columns(2)
            data_owner_team = c1.text_input("Data Owner Team", value=bp.get('data_owner_team', ''))
            source_team_from = c2.text_input("Source Team/Vendor", value=bp.get('source_team_from', ''))
            data_sensitivity = c1.selectbox("Data Sensitivity", ["Confidential", "Internal", "Public"],
                                            index=["Confidential", "Internal", "Public"].index(bp.get('data_sensitivity', 'Internal')))
            source_type = c2.selectbox("Source Type", ["Internal", "External Market", "External Third Party"],
                                       index=["Internal", "External Market", "External Third Party"].index(bp.get('source_type', 'Internal')))

            st.markdown("##### Process & Sign-off Rules")
            c1, c2 = st.columns(2)
            creation_method = c1.selectbox("Creation Method", self.file_creation_methods,
                                           index=self.file_creation_methods.index(bp.get('creation_method')) if bp.get('creation_method') in self.file_creation_methods else 0)
            signoff_workflow = c2.selectbox("Sign-off Workflow", self.file_signoff_workflows,
                                            index=self.file_signoff_workflows.index(bp.get('signoff_workflow')) if bp.get('signoff_workflow') in self.file_signoff_workflows else 0)

            c1, c2 = st.columns(2)
            default_doer_roles = [r for r in bp.get('doer_roles', 'admin,inputs_admin').split(',') if r in self.all_roles]
            doer_roles_list = c1.multiselect("Doer Roles (Who can create this?)", self.all_roles, default=default_doer_roles)

            default_reviewer_roles = [r for r in bp.get('reviewer_roles', 'admin').split(',') if r in self.all_roles]
            reviewer_roles_list = c2.multiselect("Reviewer Roles (Who can approve this?)", self.all_roles, default=default_reviewer_roles)

            st.markdown("##### Validation Rules")

            c1, c2 = st.columns(2)

            # This is now just a label, its value is set by the *controller*
            file_type = c1.text_input("File Type", value=bp['file_type'], disabled=True)

            # Get conditional options for extension
            ext_options = self.file_types_map.get(bp['file_type'], [])
            default_ext_index = 0
            if bp.get('expected_extension') in ext_options:
                default_ext_index = ext_options.index(bp.get('expected_extension'))

            expected_extension = c2.selectbox("Expected Extension", ext_options, index=default_ext_index,
                                              help="This list is based on the 'File Type' you selected.")

            # Conditional text box for structure
            structure_input = ""
            if bp['file_type'] == "Spreadsheet":
                structure_input = st.text_input("Expected Sheet Names (comma-separated)", bp.get('structure_str', ''), help="e.g., Summary, Inputs, Calcs")
            elif bp['file_type'] == "CSV/TXT":
                structure_input = st.text_input("Expected Column Names (comma-separated)", bp.get('structure_str', ''), help="e.g., date, region, value")
            else:
                st.caption("No structure validation will be performed for 'Other' file types.")

            c1, c2 = st.columns(2)
            min_file_size_kb = c1.number_input("Min File Size (KB)", value=bp.get('min_file_size_kb', 1), min_value=0)
            max_file_size_kb = c2.number_input("Max File Size (KB)", value=bp.get('max_file_size_kb', 102400), min_value=1) # 100MB

            purpose = st.text_area("Purpose", value=bp.get('purpose', ''))

            template_status = "Active"
            if not is_new:
                template_status = st.selectbox("Template Status", ["Active", "Archived"],
                                               index=["Active", "Archived"].index(bp.get('template_status', 'Active')))

            submit_col, _, cancel_col = st.columns([1, 2, 1])
            blueprint_submitted = submit_col.form_submit_button("Save Changes")
            if cancel_col.form_submit_button("Cancel"):
                st.session_state.bp_manage_action = None
                st.session_state.bp_selected_id = None
                st.rerun()

            if blueprint_submitted:
                if not all([template_id, template_name, stage, expected_extension, purpose]):
                    st.error("Template ID, Name, Stage, Extension, and Purpose are required.")
                else:
                    # --- Build the "messy" JSON and form_data dict ---
                    try:
                        expected_structure_json = _parse_structure_to_json(file_type, structure_input)

                        # --- THIS IS THE FIX for the TypeError ---
                        # Package all form data into a single dictionary
                        form_data = {
                            "template_name": template_name,
                            "stage": stage,
                            "purpose": purpose,
                            "data_owner_team": data_owner_team,
                            "data_sensitivity": data_sensitivity,
                            "source_type": source_type,
                            "source_team_from": source_team_from,
                            "creation_method": creation_method,
                            "signoff_workflow": signoff_workflow,
                            "doer_roles": ",".join(doer_roles_list),
                            "reviewer_roles": ",".join(reviewer_roles_list),
                            "expected_extension": expected_extension,
                            "min_file_size_kb": min_file_size_kb,
                            "max_file_size_kb": max_file_size_kb,
                            "expected_structure": expected_structure_json,
                            "template_status": template_status,
                        }

                    except Exception as e:
                        st.error(f"Error packing form data: {e}"); return

                    with st.spinner(f"Saving blueprint '{template_id}'..."):

                        if is_new: # This handles both "CREATE" and "CLONE"
                            # Add the "Key" which is not in the edit form
                            form_data['template_id'] = template_id

                            success, message = registry_service.create_file_blueprint(
                                form_data=form_data,
                                user_id=self.user_id
                            )
                        else: # This handles "EDIT"
                            # We don't send the template_id in the form_data for an edit
                            success, message = registry_service.edit_file_blueprint(
                                template_id=template_id,
                                form_data=form_data,
                                user_id=self.user_id
                            )

                        if success:
                            st.success(message); self.refresh_data(); st.session_state.bp_manage_action = None; st.session_state.bp_selected_id = None; st.rerun()
                        else: st.error(message)

    # --- TAB 3: AUDIT LOG ---
    def _render_audit_tab(self):
        """Displays the audit log for a selected blueprint."""
        st.subheader("🔍 Blueprint Audit Log")

        if not self.all_blueprints:
            st.warning("No File Blueprints found.")
            return

        bp_options = {bp['template_id']: f"{bp['template_id']} ({bp['template_name']})" for bp in self.all_blueprints}
        selected_bp_id = st.selectbox("Select File Blueprint to Audit", options=bp_options.keys(),
                                      format_func=lambda x: bp_options.get(x))

        if not selected_bp_id:
            return

        st.markdown("---")
        st.caption(f"Showing all human actions for **{selected_bp_id}** (from Table 8).")

        try:
            audit_log = registry_service.get_audit_log_for_target("file_blueprints", selected_bp_id)
            if not audit_log:
                st.info("No audit history found for this blueprint.")
            else:
                st.dataframe(audit_log, use_container_width=True, column_order=(
                    "timestamp", "user_id", "action", "signoff_capacity", "comment"
                ))
        except Exception as e:
            st.error(f"Failed to load audit log: {e}")

    # --- TAB 4: SYSTEM HEALTH ---
    def _render_health_tab(self):
        """UI for running health checks on Table 2."""
        st.subheader("❤️ Blueprint Health Check")
        st.markdown("Run these checks to find inconsistencies in the registry.")

        st.markdown("---")
        st.markdown("##### Broken Instance Links")
        st.markdown(
            """
            This checks for "orphaned" files (in Tables 3-6) that point to a
            File Blueprint `template_id` that **does not exist** in Table 2.
            This is a critical data integrity error.
            """
        )
        if st.button("Scan for Broken Links"):
            with st.spinner("Scanning all file tables..."):
                broken_links = registry_service.find_broken_blueprint_links()
                if not broken_links:
                    st.success("No broken links found. All files are linked to a valid blueprint.")
                else:
                    st.error(f"Found {len(broken_links)} broken links:")
                    st.dataframe(broken_links, use_container_width=True)

        st.markdown("---")
        st.markdown("##### Unused Blueprints")
        st.markdown(
            """
            This scans for 'Active' File Blueprints (Table 2) that are **not
            being used** by *any* file in *any* environment (Tables 3-6).
            These may be safe to 'Archive'.
            """
        )
        if st.button("Scan for Unused Blueprints"):
            with st.spinner("Scanning..."):
                unused = registry_service.find_unused_blueprints()
                if not unused:
                    st.success("No unused blueprints found.")
                else:
                    st.warning(f"Found {len(unused)} 'Active' blueprints with no file instances:")
                    st.dataframe(unused, use_container_width=True)

        st.markdown("---")
        st.markdown("##### Invalid JSON Structures")
        st.markdown(
            "This checks the `expected_structure` column in **all** blueprints to make sure it contains valid JSON.")
        if st.button("Validate All JSON"):
            with st.spinner("Validating..."):
                errors = registry_service.validate_all_blueprint_json()
                if not errors:
                    st.success("All `expected_structure` fields contain valid JSON.")
                else:
                    st.error(f"Found {len(errors)} blueprints with invalid JSON:")
                    st.dataframe(errors, use_container_width=True)

        st.markdown("---")
        st.markdown("##### Destructive Actions")
        st.error("**DANGER ZONE:** Only use this if you are 100% sure.")

        bp_options_del = {bp['template_id']: f"{bp['template_id']} ({bp['template_name']})" for bp in self.all_blueprints}
        selected_bp_id_del = st.selectbox("Select Blueprint to Delete", options=[""] + list(bp_options_del.keys()),
                                          format_func=lambda x: "Select..." if x == "" else bp_options_del.get(x),
                                          key="bp_delete_select")

        if st.button(f"Permanently Delete '{selected_bp_id_del}'", disabled=(selected_bp_id_del == "")):
            st.warning(
                f"This will **permanently delete** the blueprint `{selected_bp_id_del}`. This will fail if any file in the system is still using it. It is safer to 'Archive' it from the 'Create/Manage' tab.")

            if 'confirm_delete_bp' not in st.session_state:
                st.session_state.confirm_delete_bp = selected_bp_id_del
                st.rerun()

        if st.session_state.get('confirm_delete_bp') == selected_bp_id_del and selected_bp_id_del:
            st.markdown(f"**Are you absolutely sure? This cannot be undone.**")
            c1, c2 = st.columns(2)
            if c1.button("Yes, PERMANENTLY Delete", type="primary"):
                with st.spinner(f"Deleting blueprint {selected_bp_id_del}..."):
                    success, message = registry_service.delete_file_blueprint(
                        selected_bp_id_del, self.user_id
                    )
                    if success:
                        st.success(message); self.refresh_data(); st.session_state.confirm_delete_bp = None; st.rerun()
                    else:
                        st.error(message)
            if c2.button("Cancel"):
                st.session_state.confirm_delete_bp = None
                st.rerun()

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
                    margin-top: 1.5rem; /* Add space above the form */
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Define the tabs
        tab_dash, tab_manage, tab_audit, tab_health = st.tabs(
            [
                "📊 Data Catalog (Dashboard)",
                "⚙️ Create / Manage Blueprints",
                "🔍 Blueprint Audit Log",
                "❤️ System Health"
            ]
        )

        # Render content for each tab
        with tab_dash:
            self.refresh_data()  # Always get fresh data for dashboard
            self._render_dashboard_tab()

        with tab_manage:
            self._render_manage_tab()

        with tab_audit:
            self.refresh_data() # Ensure we can audit newly created BPs
            self._render_audit_tab()

        with tab_health:
            self._render_health_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta


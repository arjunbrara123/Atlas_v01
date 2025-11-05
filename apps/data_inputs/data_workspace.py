"""
apps/inputs/data_inputs_workspace.py

This is the user-facing "Doer" and "Reviewer" dashboard for the
"🚢 Data Inputs" stage of the workflow.

-------------------------------------------------------------------------------
PURPOSE:
-------------------------------------------------------------------------------
This is a single, consolidated "Workspace" for all data input tasks.
It is a "smart" dashboard that reads the `file_blueprints` (Table 2) and
dynamically builds its UI based on the rules for each file.

-------------------------------------------------------------------------------
CORE FUNCTIONALITY:
-------------------------------------------------------------------------------
It is designed as a 4-tab application to manage the full lifecycle:

1.  "Create / Run Data Input":
    - This is the "Doer" creation UI.
    - It *only* shows blueprints the user has the `doer_roles` for.
    - It *conditionally* shows a "File Uploader" (for `Manual Upload`)
      or a "Run Job" button (for `User-Triggered Job`).
    - It calls the "Engine" (`registry_service.py`) to perform all
      validation (hashing, schema, size) and logging.

2.  "My Pending 'Doer' Sign-Offs":
    - An "inbox" of all files the current user has created (as "Doer")
      that they have not yet signed off on.
    - This is the UI for the *first* signature in the "Doer + Reviewer"
      workflow.

3.  "My Reviewer Inbox":
    - An "inbox" of all files (created by others) that are "Doer"
      approved and are now awaiting the current user's "Reviewer"
      sign-off.
    - This UI is *also* controlled by the `reviewer_roles` in Table 2.
    - This is where `REJECT` or `REVOKE` actions are performed.

4.  "All 'Data Input' Files":
    - A simple, read-only "File Explorer" showing all files in the
      `data_files` (Table 3) for the currently selected environment,
      along with their *current governance status*.

-------------------------------------------------------------------------------
ARCHITECTURE:
-------------------------------------------------------------------------------
- This file is a "dumb" UI. It contains *only* Streamlit code.
- It imports `registry_service.py` (the "Engine") to do all the work.
- It follows the "Class-based Recipe" pattern, so `main_app.py`
  calls `render_page()` to get the `render_body` callable and `meta`.
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import json
import pandas as pd


# --- Helper Functions (specific to this dashboard) ---

def render_gov_status(file_row, audit_log, blueprint):
    """
    Checks the audit log and blueprint to show the *governance* status.
    This is the "virtual" status logic.
    """
    try:
        workflow = blueprint.get('signoff_workflow', 'Doer Only')

        # Check for signatures
        doer_signed = any(log['signoff_capacity'] == 'Doer' and log['action'] == 'SIGN_OFF' for log in audit_log)
        reviewer_signed = any(
            log['signoff_capacity'] == 'Reviewer' and log['action'] == 'SIGN_OFF' for log in audit_log)

        # Check for rejections
        latest_action = audit_log[0]['action'] if audit_log else None

        # current_status is the "snapshot" from the (Option 2) Hybrid Model
        if file_row['current_status'] == 'Rejected':
            st.error("🔴 **Rejected**")
            st.caption(f"Reason: {audit_log[0]['comment']} (by {audit_log[0]['user_id']})")
            return "Rejected"
        if file_row['current_status'] == 'Superseded':
            st.markdown("⚪️ **Superseded**")
            st.caption("A newer version of this file exists.")
            return "Superseded"

        # Check for completion
        if workflow == 'Doer + Reviewer':
            if doer_signed and reviewer_signed:
                st.success("🟢 **Fully Approved**")
                return "Approved"
            elif doer_signed:
                st.info("🔵 **Awaiting Review**")
                return "Pending"
            else:
                st.warning("🟠 **Awaiting Doer Sign-off**")
                return "Pending"
        else:  # Doer Only
            if doer_signed:
                st.success("🟢 **Approved** (Doer Only)")
                return "Approved"
            else:
                st.warning("🟠 **Awaiting Doer Sign-off**")
                return "Pending"

    except Exception as e:
        st.error(f"Could not get status: {e}")
        return "Error"


# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        """
        Initializes the Page object.
        - Sets user/role/environment.
        - Sets page metadata.
        - Calls refresh_data() to load all data for the dashboard.
        """
        self.role = role
        self.env_id = environment  # The *app's* current env_id
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.meta = {
            "title_override": f"Data Inputs Workspace ({self.env_id})",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        # Load all data for all tabs on init
        self.refresh_data()

    def refresh_data(self):
        """
        Gets all blueprints and files needed for this dashboard.
        This is the main data-loading function.
        """
        try:
            # 1. Get *all* "Data Inputs" blueprints
            all_bps = registry_service.get_all_file_blueprints(stage='Data Inputs')
            self.blueprint_map = {bp['template_id']: bp for bp in all_bps}

            # 2. Filter them by what this user is *allowed to create* (Doer)
            self.allowed_blueprints = [
                bp for bp in all_bps
                if 'all' in (bp['doer_roles'] or 'admin').split(',')
                   or self.role in (bp['doer_roles'] or 'admin').split(',')
            ]

            # 3. Get all data for the user's inboxes & file explorer
            # This one "Engine" function is smart and gets all data for our 3 tabs
            dashboard_data = registry_service.get_files_for_user_dashboard(
                env_id=self.env_id,
                stage="Data Inputs",
                user_id=self.user_id,
                user_role=self.role
            )

            self.pending_doer = dashboard_data['pending_doer']
            self.pending_reviewer = dashboard_data['pending_reviewer']
            self.all_files = dashboard_data['all_files']

        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.allowed_blueprints = []
            self.all_files = []
            self.pending_doer = []
            self.pending_reviewer = []
            self.blueprint_map = {}

    def _get_file_audit_log(self, file_row):
        """Helper to safely get pre-fetched audit log from the file row."""
        return file_row.get('audit_log', [])

    # --- TAB 1: CREATE / RUN DATA INPUT ---
    def _render_create_tab(self):
        """
        Renders the 'Create / Run' tab.
        This is the "Smart UI" that reads the creation_method from
        the blueprint and shows the correct UI.
        """
        st.subheader("📥 Create or Run a New Data Input")
        st.markdown(
            """
            This is the start of the workflow. Select a file blueprint to either
            upload a file or run an automated job. The options in this list
            are filtered by your user role.
            """
        )

        if not self.allowed_blueprints:
            st.warning(
                "No 'Data Input' file blueprints are defined for your 'Doer' role. Please contact an admin to be granted permissions.")
            return

        blueprint_options = {bp['template_id']: bp['template_name'] for bp in self.allowed_blueprints}

        # --- This is the "Smart UI" Controller ---
        template_id = st.selectbox(
            "Select a Data Input to Create:",
            options=blueprint_options.keys(),
            format_func=lambda x: blueprint_options.get(x),
            help="This list is filtered by your 'Doer' permissions."
        )

        if not template_id:
            st.info("Please select a file type to begin.")
            return

        # Get the rules for the selected file
        bp = self.blueprint_map.get(template_id)
        if not bp:
            st.error("Could not find blueprint details.")
            return

        st.markdown("---")

        # --- Render the UI based on the *Blueprint's* rules ---

        if bp['creation_method'] == 'Manual Upload':
            # --- "Manual Upload" Workflow ---
            st.markdown(f"#### ⬆️ Upload: **{bp['template_name']}**")
            st.caption(f"**Source:** {bp['source_type']} ({bp['source_name']})")

            with st.form("upload_form"):
                uploaded_file = st.file_uploader(
                    f"Upload your {bp['expected_extension']} file",
                    type=[ext.strip().lstrip('.') for ext in bp['expected_extension'].split(',')]
                )

                st.markdown("---")
                st.caption("This action will supersede any existing 'Active' file of this type in this environment.")
                submitted = st.form_submit_button("Upload and Log File")

                if submitted:
                    if not uploaded_file:
                        st.error("Please upload a file.")
                    else:
                        with st.spinner(f"Uploading and validating '{uploaded_file.name}'..."):
                            # This is the call to our "Engine"
                            success, message = registry_service.upload_new_file_instance(
                                user_id=self.user_id,
                                user_role=self.role,
                                env_id=self.env_id,
                                template_id=template_id,
                                uploaded_file=uploaded_file,
                                source_ids_map=None  # This is for models, not data inputs
                            )
                            if success:
                                st.success(message)
                                self.refresh_data()  # Refresh data for all tabs
                                st.rerun()
                            else:
                                st.error(message)

        elif bp['creation_method'] == 'User-Triggered Job':
            # --- "User-Triggered Job" Workflow ---
            st.markdown(f"#### 🔌 Run Job: **{bp['template_name']}**")
            st.caption(f"**Source:** {bp['source_type']} ({bp['source_name']})")

            st.info(
                f"""
                This is a user-triggered job. Clicking the button below will
                command the Atlas "Engine" to:
                1. Securely connect to: `{bp['source_name']}`
                2. Download the file from: `{bp['source_specifier']}`
                3. Validate, hash, and log the file to the registry.
                """
            )

            with st.form("job_form"):
                st.markdown("---")
                st.caption("This action will supersede any existing 'Active' file of this type in this environment.")
                submitted = st.form_submit_button("Run Job")

                if submitted:
                    with st.spinner(f"Running job '{bp['template_name']}'..."):
                        # This is the call to our *other* "Engine" function
                        success, message = registry_service.run_external_connection_job(
                            user_id=self.user_id,
                            user_role=self.role,
                            env_id=self.env_id,
                            template_id=template_id,
                            source_ids_map=None
                        )
                        if success:
                            st.success(message)
                            self.refresh_data()
                            st.rerun()
                        else:
                            st.error(message)

        else:
            st.error(f"Blueprint Error: Unknown creation method '{bp['creation_method']}'.")

    # --- TAB 2: "DOER" INBOX ---
    def _render_doer_inbox_tab(self):
        st.subheader("📝 My Pending 'Doer' Sign-Offs")
        st.markdown("These are files you created that you have not yet signed off on.")

        if not self.pending_doer:
            st.success("Your 'Doer' inbox is empty. All your created files are signed off or awaiting review.")
            return

        st.warning(f"You have **{len(self.pending_doer)}** files awaiting your 'Doer' sign-off.")

        for file in self.pending_doer:
            file_id = file['file_id']
            table_name = file['table_name']
            bp = self.blueprint_map.get(file['template_id'], {})

            with st.expander(f"**{bp.get('template_name', file['template_id'])}** (File ID: `{file_id}`)",
                             expanded=True):
                st.caption(f"File Path: `{file['file_path']}` | Created: {file['created_at']}")
                st.info("You created this file, but have not yet completed your 'Doer' sign-off.")

                with st.form(f"doer_form_{file_id}"):
                    comment = st.text_area("Sign-off Comment",
                                           f"As Doer, I confirm this file is complete and accurate.",
                                           key=f"doer_comment_{file_id}")
                    submitted = st.form_submit_button("Sign Off as 'Doer'")

                    if submitted:
                        with st.spinner("Logging sign-off..."):
                            success, message = registry_service.log_user_signoff(
                                user_id=self.user_id, user_role=self.role,
                                target_table=table_name, target_id=file_id,
                                action="SIGN_OFF", capacity="Doer", comment=comment
                            )
                            if success:
                                st.success(message); self.refresh_data(); st.rerun()
                            else:
                                st.error(message)

    # --- TAB 3: "REVIEWER" INBOX ---
    def _render_reviewer_inbox_tab(self):
        st.subheader("🧐 Reviewer Inbox")
        st.markdown("These are files created by others that are now awaiting your 'Reviewer' sign-off.")

        if not self.pending_reviewer:
            st.success(
                "Your 'Reviewer' inbox is empty. All files are either pending 'Doer' sign-off or are fully approved.")
            return

        st.warning(f"You have **{len(self.pending_reviewer)}** files in your inbox.")

        for file in self.pending_reviewer:
            file_id = file['file_id']
            table_name = file['table_name']
            bp = self.blueprint_map.get(file['template_id'], {})
            audit_log = self._get_file_audit_log(file)

            with st.expander(f"**{bp.get('template_name', file['template_id'])}** (File ID: `{file_id}`)",
                             expanded=True):
                st.caption(f"File Path: `{file['file_path']}` | Created By: {file['created_by']}")

                # Show the Doer's comment
                doer_log = next((log for log in audit_log if log['signoff_capacity'] == 'Doer'), None)
                if doer_log:
                    st.info(f"**Doer ({doer_log['user_id']}) Comment:** \"{doer_log['comment']}\"")

                with st.form(f"reviewer_form_{file_id}"):
                    comment = st.text_area("Sign-off or Rejection Comment", key=f"rev_comment_{file_id}",
                                           help="A comment is *mandatory* for all Reviewer actions.")

                    c1, c2, c3 = st.columns([1, 1, 3])
                    approve_submitted = c1.form_submit_button("Approve", type="primary")
                    reject_submitted = c2.form_submit_button("Reject")
                    # Future: Add a "Revoke" button if the user *is* the one who signed it off

                    if approve_submitted:
                        if not comment:
                            st.error("A comment is required for all approvals.");
                            return
                        with st.spinner("Logging Approval..."):
                            success, message = registry_service.log_user_signoff(
                                user_id=self.user_id, user_role=self.role,
                                target_table=table_name, target_id=file_id,
                                action="SIGN_OFF", capacity="Reviewer", comment=comment
                            )
                            if success:
                                st.success(message); self.refresh_data(); st.rerun()
                            else:
                                st.error(message)

                    if reject_submitted:
                        if not comment:
                            st.error("A comment is *mandatory* for all rejections.");
                            return
                        with st.spinner("Logging Rejection..."):
                            success, message = registry_service.log_user_signoff(
                                user_id=self.user_id, user_role=self.role,
                                target_table=table_name, target_id=file_id,
                                action="REJECT", capacity="Reviewer", comment=comment
                            )
                            if success:
                                st.success(message); self.refresh_data(); st.rerun()
                            else:
                                st.error(message)

    # --- TAB 4: ALL FILES ---
    def _render_all_files_tab(self):
        st.subheader(f"📂 All 'Data Input' Files in `{self.env_id}`")
        st.markdown(
            "This is a read-only view of all file *versions* that exist in this environment's 'Data Inputs' folder.")

        if not self.all_files:
            st.info("No 'Data Input' files found in this environment.")
            return

        # We need to add the blueprint and status info
        display_data = []
        for file in self.all_files:
            bp = self.blueprint_map.get(file['template_id'], {})
            audit_log = self._get_file_audit_log(file)

            # Get latest human action
            latest_action = audit_log[0]['action'] if audit_log else "Pending"
            gov_status = file['current_status']  # This is 'Active', 'Rejected', 'Superseded'

            if gov_status == 'Active':
                # It's 'Active', but is it 'Approved'?
                workflow = bp.get('signoff_workflow', 'Doer Only')
                doer_signed = any(l['signoff_capacity'] == 'Doer' and l['action'] == 'SIGN_OFF' for l in audit_log)
                reviewer_signed = any(
                    l['signoff_capacity'] == 'Reviewer' and l['action'] == 'SIGN_OFF' for l in audit_log)

                if workflow == 'Doer + Reviewer':
                    gov_status = "Fully Approved" if doer_signed and reviewer_signed else "Pending"
                else:
                    gov_status = "Approved" if doer_signed else "Pending"

            display_data.append({
                "File ID": file['file_id'],
                "Name": bp.get('template_name', file['template_id']),
                "Status": gov_status,
                "Version Status": file['current_status'],
                "Created At": file['created_at'],
                "Created By": file['created_by'],
                "File Path": file['file_path']
            })

        st.dataframe(
            display_data,
            use_container_width=True,
            column_config={
                "Status": st.column_config.TextColumn("Governance Status"),
                "Version Status": st.column_config.TextColumn("Version Status")
            }
        )

    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
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

        st.caption(f"You are working in the **{self.env_id}** environment. All actions are logged.")

        # Define the tabs
        tab_create, tab_doer, tab_reviewer, tab_all = st.tabs(
            [
                "📥 Create / Run Data Input",
                f"📝 My Pending Doer ({len(self.pending_doer)})",
                f"🧐 My Reviewer Inbox ({len(self.pending_reviewer)})",
                "📂 All Data Input Files"
            ]
        )

        # Render content for each tab
        with tab_create:
            self._render_create_tab()

        with tab_doer:
            self._render_doer_inbox_tab()

        with tab_reviewer:
            self._render_reviewer_inbox_tab()

        with tab_all:
            self._render_all_files_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main_app.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta

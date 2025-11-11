"""
apps/inputs/data_inputs_workspace.py

This is the user-facing "Doer" and "Reviewer" dashboard for the
"🚢 Data Inputs" stage of the workflow.

-------------------------------------------------------------------------------
PURPOSE & FUNCTIONALITY (V8 "Best Possible" Build):
-------------------------------------------------------------------------------
This is a single, consolidated "Workspace" for all data input tasks,
rebuilt for a best-in-class, secure, and auditable user workflow.

1.  "Create New": (Tab 1)
    - A clean, dedicated "Doer" UI for creating files from scratch
      (Upload or Run Job).

2.  "My Action Inbox": (Tab 2) - The "Smart Inbox"
    - Combines "Doer" and "Reviewer" inboxes into one simple list.
    - This tab is "context-aware" and provides the perfect tool:
    - [DOER TASK - NEW]: Shows a "Preview" button.
    - [DOER TASK - EDIT]: Shows the *full comparison* (with visual diff)
      so the Doer can review their own changes before submitting.
    - [REVIEWER TASK - NEW]: Shows Doer's comment + Full File Preview.
    - [REVIEWER TASK - EDIT]: Shows Doer's justification + Full Comparison
      (with visual diff).

3.  "Data Explorer": (Tab 3) - The "Read-Only" Forensic Tool
    - A powerful two-part tool:
    - [Sub-Tab A] "Forensic Comparison": Allows a user to select a file
      template and compare *any two versions* from its history.
    - [Sub-Tab B] "Full Version History": Shows the complete, time-stamped
      "life story" (all edits, comments, sign-offs) for a file.

4.  "Data Editor": (Tab 4) - Secured & Separate
    - This is the high-risk "write" tool.
    - The tab is *only visible* to users with a role in the
      `EDITOR_ROLES` list and *only* in non-Validation environments.
    - Allows a user to edit an 'Active' file, provide a justification,
      and save it as a new, superseded version.
-------------------------------------------------------------------------------
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import json
import pandas as pd
import io

# --- Helper Functions (specific to this dashboard) ---

def render_gov_status(file_row, audit_log, blueprint):
    """
    Renders the human-readable governance status for a file.
    """
    try:
        workflow = blueprint.get('signoff_workflow', 'Doer Only')
        doer_signed = any(log['signoff_capacity'] == 'Doer' and log['action'] == 'SIGN_OFF' for log in audit_log)
        reviewer_signed = any(log['signoff_capacity'] == 'Reviewer' and log['action'] == 'SIGN_OFF' for log in audit_log)

        if file_row['current_status'] == 'Rejected':
            st.error("🔴 **Rejected**")
            st.caption(f"Reason: {audit_log[0]['comment']} (by {audit_log[0]['user_id']})")
        elif file_row['current_status'] == 'Superseded':
            st.markdown("⚪️ **Superseded**")
            st.caption("A newer version of this file exists.")
        elif workflow == 'Doer + Reviewer':
            if doer_signed and reviewer_signed:
                st.success("🟢 **Fully Approved**")
            elif doer_signed:
                st.info("🔵 **Awaiting Review**")
            else:
                st.warning("🟠 **Awaiting Doer Sign-off**")
        else:  # Doer Only
            if doer_signed:
                st.success("🟢 **Approved** (Doer Only)")
            else:
                st.warning("🟠 **Awaiting Doer Sign-off**")
    except Exception as e:
        st.error(f"Could not get status: {e}")

# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        """
        Initializes the Page object.
        """
        self.role = role
        self.env_id = environment
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")
        self.table_name = "inst_data_input_files" # Hardcoded for this workspace

        self.meta = {
            "title_override": f"Data Inputs Workspace ({self.env_id})",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
        }

        # --- Security & Environment Checks (for the Editor tab) ---
        try:
            self.env_data = registry_service.get_environment_by_id(self.env_id)
            self.env_cat = self.env_data.get('env_cat') if self.env_data else 'Unknown'

            editor_roles = registry_service.get_editor_roles()
            self.is_editor = self.role in editor_roles

            # The Editor tab is visible if the user has the role AND is NOT in Validation
            # Production and Reporting are OK, as requested.
            self.show_editor_tab = self.is_editor and (self.env_cat != 'Validation')

        except Exception as e:
            st.error(f"Failed to load environment/role permissions: {e}")
            self.env_cat = 'Unknown'
            self.is_editor = False
            self.show_editor_tab = False

        # Load all data for all tabs on init
        self.refresh_data()

    def refresh_data(self):
        """
        Gets all blueprints and files needed for this dashboard.
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
            # ASSUMES: This function now returns 'superseded_file_id'
            dashboard_data = registry_service.get_files_for_user_dashboard(
                env_id=self.env_id,
                stage="Data Inputs",
                user_id=self.user_id,
                user_role=self.role
            )

            self.pending_doer = dashboard_data['pending_doer']
            self.pending_reviewer = dashboard_data['pending_reviewer']
            self.all_files = dashboard_data['all_files']

            # 4. Combine inboxes into one list for the new "Action Inbox" tab
            doer_tasks = [dict(f, task_type='doer') for f in self.pending_doer]
            reviewer_tasks = [dict(f, task_type='reviewer') for f in self.pending_reviewer]
            self.action_inbox = doer_tasks + reviewer_tasks
            self.action_inbox.sort(key=lambda x: x['created_at'], reverse=True)

        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.allowed_blueprints = []
            self.all_files = []
            self.action_inbox = []
            self.blueprint_map = {}

    def _get_file_audit_log(self, file_row):
        """Helper to safely get pre-fetched audit log from the file row."""
        return file_row.get('audit_log', [])

    # --- UI Helper: Renders a file preview ---
    def _render_file_preview(self, file_path: str, expected_hash: str):
        """
        Calls the engine to get file data (with hash check)
        and renders the correct Streamlit preview widget.
        """
        with st.spinner(f"Validating and loading preview for {file_path}..."):
            preview_data = registry_service.get_file_preview(file_path, expected_hash)

            if preview_data['type'] == 'excel':
                st.info(f"Showing {len(preview_data['data'])} sheet(s) from Excel file.")
                for sheet_name, df in preview_data['data'].items():
                    st.markdown(f"**Sheet: `{sheet_name}`**")
                    st.dataframe(df, use_container_width=True)

            elif preview_data['type'] == 'dataframe':
                st.dataframe(preview_data['data'], use_container_width=True)

            elif preview_data['type'] == 'raw_text':
                st.code(preview_data['data'], language='text')

            elif preview_data['type'] == 'error':
                st.error(f"Could not load file: {preview_data['data']}")

            else: # 'unsupported'
                st.warning(preview_data['data'])

            return preview_data # Return data for the editor

    # --- UI Helper: Applies Red/Green styling to diffs ---
    def _style_comparison(self, df_old, df_new, modified_rows_old, modified_rows_new):
        """
        Applies red/green cell highlighting to side-by-side dataframes.
        Returns two styled Pandas DataFrames.
        """
        try:
            # Create a 'diff' mask of booleans (True where cells differ)
            diff_mask = (df_old.fillna('') != df_new.fillna(''))

            # Function to apply CSS
            def apply_highlight(df, mask, color):
                # We need to create an empty DataFrame of strings to hold styles
                styler = pd.DataFrame('', index=df.index, columns=df.columns)
                # Apply the background color where the mask is True
                styler = styler.where(~mask, f'background-color: {color}')
                return styler

            # Apply red to old, green to new
            # Using light colors for readability
            red = '#ffcdd2'  # Light Red
            green = '#c8e6c9' # Light Green

            styled_old = df_old.style.apply(apply_highlight,
                                            mask=diff_mask, color=red, axis=None)
            styled_new = df_new.style.apply(apply_highlight,
                                            mask=diff_mask, color=green, axis=None)

            return styled_old, styled_new
        except Exception as e:
            # Fallback for complex diffs (e.g., changed columns)
            st.warning(f"Could not apply visual highlighting: {e}")
            return df_old.style, df_new.style # Return unstyled

    # --- UI Helper: Renders the full file comparison dashboard ---
    def _render_file_comparison(self, new_file_id: int, old_file_id: int, justification_log: dict = None):
        """
        Renders the full "Change Review" dashboard, including
        justification, change report and side-by-side views.
        """

        # 1. 💬 The Justification
        if justification_log:
            st.info(f"**Editor ({justification_log['user_id']}) Justification:**\n\n \"{justification_log['comment']}\"")
        else:
            st.warning("No justification comment was found for this new version.")

        # 2. 📊 The Comparison (in tabs)
        with st.container(border=True):
            st.markdown("#### Comparison to Superseded Version")

            # Call our new "Engine" function
            diff = registry_service.get_file_comparison(self.table_name, new_file_id, old_file_id)

            if diff['type'] == 'error':
                st.error(diff['data'])
            elif diff['type'] == 'no_changes':
                st.success(diff['data'])
            elif diff['type'] == 'comparison':

                tab_report, tab_side_by_side = st.tabs(["📊 Change Report", "👀 Side-by-Side (Visual Diff)"])

                with tab_report:
                    st.markdown("This is an auto-generated report of all changes.")

                    st.subheader("New Rows")
                    if diff['new_rows'].empty:
                        st.caption("No new rows added.")
                    else:
                        st.dataframe(diff['new_rows'], use_container_width=True)

                    st.subheader("Deleted Rows")
                    if diff['deleted_rows'].empty:
                        st.caption("No rows deleted.")
                    else:
                        st.dataframe(diff['deleted_rows'], use_container_width=True)

                    st.subheader("Modified Rows")
                    if diff['modified_rows_new'].empty:
                        st.caption("No modified rows found.")
                    else:
                        st.markdown("**Before (Old Version)**")
                        st.dataframe(diff['modified_rows_old'], use_container_width=True)
                        st.markdown("**After (New Version)**")
                        st.dataframe(diff['modified_rows_new'], use_container_width=True)

                with tab_side_by_side:
                    st.markdown("This is a full preview of both files with changes highlighted.")

                    # Call our new styling helper
                    styled_old, styled_new = self._style_comparison(
                        diff['full_old'],
                        diff['full_new'],
                        diff['modified_rows_old'],
                        diff['modified_rows_new']
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Before (Old Version)**")
                        st.dataframe(styled_old, use_container_width=True)
                    with col2:
                        st.markdown("**After (New Version)**")
                        st.dataframe(styled_new, use_container_width=True)

            else:
                st.warning("Could not generate a comparison for this file type.")

    # --- TAB 1: CREATE NEW ---
    def _render_create_tab(self):
        st.subheader("📥 Create or Run a New Data Input")
        st.markdown(
            """
            Select a file blueprint to either upload a file from your 
            computer or run an automated job.
            """
        )

        if not self.allowed_blueprints:
            st.warning(
                "No 'Data Input' file blueprints are defined for your 'Doer' role.")
            return

        blueprint_options = {bp['template_id']: bp['template_name'] for bp in self.allowed_blueprints}
        template_id = st.selectbox(
            "Select a Data Input to Create:",
            options=blueprint_options.keys(),
            format_func=lambda x: blueprint_options.get(x),
            help="This list is filtered by your 'Doer' permissions."
        )

        if not template_id:
            st.info("Please select a file type to begin."); return

        bp = self.blueprint_map.get(template_id)
        if not bp:
            st.error("Could not find blueprint details."); return

        st.markdown("---")

        if bp['creation_method'] == 'Manual Upload':
            st.markdown(f"#### ⬆️ Upload: **{bp['template_name']}**")
            with st.form("upload_form"):
                uploaded_file = st.file_uploader(
                    f"Upload your {bp['expected_extension']} file",
                    type=[ext.strip().lstrip('.') for ext in bp['expected_extension'].split(',')]
                )
                st.markdown("---")
                submitted = st.form_submit_button("Upload and Log File")
                if submitted:
                    if not uploaded_file:
                        st.error("Please upload a file.")
                    else:
                        with st.spinner(f"Uploading and validating '{uploaded_file.name}'..."):
                            success, message = registry_service.upload_new_file_instance(
                                user_id=self.user_id, user_role=self.role,
                                env_id=self.env_id, template_id=template_id,
                                uploaded_file=uploaded_file, source_ids_map=None
                            )
                            if success:
                                st.success(message); self.refresh_data(); st.rerun()
                            else:
                                st.error(message)

        elif bp['creation_method'] == 'User-Triggered Job':
            st.markdown(f"#### 🔌 Run Job: **{bp['template_name']}**")
            st.info(f"This job will connect to `{bp['source_name']}` and download the file from `{bp['source_specifier']}`.")
            with st.form("job_form"):
                st.markdown("---")
                submitted = st.form_submit_button("Run Job")
                if submitted:
                    with st.spinner(f"Running job '{bp['template_name']}'..."):
                        success, message = registry_service.run_external_connection_job(
                            user_id=self.user_id, user_role=self.role,
                            env_id=self.env_id, template_id=template_id,
                            source_ids_map=None
                        )
                        if success:
                            st.success(message); self.refresh_data(); st.rerun()
                        else:
                            st.error(message)

    # --- TAB 2: MY ACTION INBOX (THE "SMART INBOX") ---
    def _render_action_inbox_tab(self):
        st.subheader(f"📬 My Action Inbox ({len(self.action_inbox)})")
        st.markdown("This is your combined inbox for all files awaiting your sign-off or review.")

        if not self.action_inbox:
            st.success("Your Action Inbox is empty. You have no pending tasks.")
            return

        for task in self.action_inbox:
            file_id = task['data_file_id']
            bp = self.blueprint_map.get(task['template_id'], {})

            # This is the "smart" part. We check if the engine gave us an ID.
            old_file_id = task.get('superseded_file_id')
            is_an_update = (old_file_id is not None)

            if task['task_type'] == 'doer':
                # --- RENDER A DOER TASK ---
                title = f"📝 **Sign-off Your File:** {bp.get('template_name', '...')} (ID: `{file_id}`)"
                if is_an_update:
                    title = f"📝 **Sign-off Your Edit:** {bp.get('template_name', '...')} (ID: `{file_id}`)"

                with st.expander(title, expanded=True):
                    self._render_doer_task_form(task, is_an_update, old_file_id)

            elif task['task_type'] == 'reviewer':
                # --- RENDER A REVIEWER TASK ---
                title = f"🧐 **Review New File:** {bp.get('template_name', '...')} (ID: `{file_id}`)"
                if is_an_update:
                    title = f"🧐 **Review Edit:** {bp.get('template_name', '...')} (ID: `{file_id}`)"

                with st.expander(title, expanded=True):
                    self._render_reviewer_task_form(task, is_an_update, old_file_id)

    def _render_doer_task_form(self, file_row, is_an_update, old_file_id):
        """Renders the UI for a 'Doer' sign-off task."""
        file_id = file_row['data_file_id']

        st.caption(f"File Path: `{file_row['file_path']}` | Created: {file_row['created_at']}")

        with st.form(f"doer_form_{file_id}"):
            if is_an_update:
                st.info("This is an edit you made. Please review the auto-generated comparison of your changes below before signing off.")
                with st.container(border=True):
                    # We pass 'None' for justification_log because we are the one writing it.
                    self._render_file_comparison(file_id, old_file_id, justification_log=None)
            else:
                st.info("This is a new file you created. Please provide a comment and sign off.")
                # Show a simple preview button
                if st.form_submit_button("Show File Preview"):
                    with st.container(border=True):
                        self._render_file_preview(file_row['file_path'], file_row['file_hash_sha256'])

            st.markdown("---")
            comment_label = "Sign-off Comment"
            if is_an_update:
                comment_label = "Justification (This will be shown to the Reviewer)"

            comment = st.text_area(comment_label,
                                   key=f"doer_comment_{file_id}",
                                   help="Provide a clear comment for the audit trail. If you made an edit, explain *why*.")

            submitted = st.form_submit_button("Sign Off as 'Doer'")

            if submitted:
                if not comment: st.error("A comment is mandatory."); return
                with st.spinner("Logging sign-off..."):
                    success, message = registry_service.log_user_signoff(
                        user_id=self.user_id, user_role=self.role,
                        target_table=self.table_name, target_id=file_id,
                        action="SIGN_OFF", capacity="Doer", comment=comment
                    )
                    if success: st.success(message); self.refresh_data(); st.rerun()
                    else: st.error(message)

    def _render_reviewer_task_form(self, file_row, is_an_update, old_file_id):
        """Renders the 'Smart' UI for a 'Reviewer' sign-off task."""
        file_id = file_row['data_file_id']
        audit_log = self._get_file_audit_log(file_row)

        st.caption(f"File Path: `{file_row['file_path']}` | Created By: {file_row['created_by']}")

        with st.form(f"reviewer_form_{file_id}"):
            # --- DYNAMIC CONTEXT BLOCK ---
            # Get the Doer's comment first
            doer_log = next((log for log in audit_log if log['signoff_capacity'] == 'Doer'), None)

            if is_an_update:
                st.markdown("This is an **updated version** of a file. Please review the justification and changes below.")
                with st.container(border=True):
                    self._render_file_comparison(file_id, old_file_id, justification_log=doer_log)
            else:
                st.markdown("This is a **new file** (first version). Please review the full file preview below.")
                if doer_log:
                    st.info(f"**Doer ({doer_log['user_id']}) Comment:**\n\n \"{doer_log['comment']}\"")
                with st.container(border=True):
                    self._render_file_preview(file_row['file_path'], file_row['file_hash_sha256'])
            # --- END DYNAMIC BLOCK ---

            st.markdown("---")
            st.markdown("##### Your Review Action")
            comment = st.text_area("Sign-off or Rejection Comment", key=f"rev_comment_{file_id}",
                                   help="A comment is *mandatory* for all Reviewer actions.")

            c1, c2, c3 = st.columns([1, 1, 3])
            approve_submitted = c1.form_submit_button("Approve", type="primary")
            reject_submitted = c2.form_submit_button("Reject")

            if approve_submitted:
                if not comment: st.error("A comment is required for all approvals."); return
                with st.spinner("Logging Approval..."):
                    success, message = registry_service.log_user_signoff(
                        user_id=self.user_id, user_role=self.role,
                        target_table=self.table_name, target_id=file_id,
                        action="SIGN_OFF", capacity="Reviewer", comment=comment
                    )
                    if success: st.success(message); self.refresh_data(); st.rerun()
                    else: st.error(message)

            if reject_submitted:
                if not comment: st.error("A comment is *mandatory* for all rejections."); return
                with st.spinner("Logging Rejection..."):
                    success, message = registry_service.log_user_signoff(
                        user_id=self.user_id, user_role=self.role,
                        target_table=self.table_name, target_id=file_id,
                        action="REJECT", capacity="Reviewer", comment=comment
                    )
                    if success: st.success(message); self.refresh_data(); st.rerun()
                    else: st.error(message)

    # --- TAB 3: DATA EXPLORER (FORENSIC COMPARE) ---
    def _render_explorer_tab(self):
        st.subheader(f"🔎 Data Explorer (Forensic Audit Tool)")
        st.markdown(
            "Select a file template to see its full history or compare any two versions.")

        if not self.blueprint_map:
            st.info("No 'Data Input' files found in this environment."); return

        # 1. Dropdown 1: Select File Template
        bp_options = {bp['template_id']: bp['template_name'] for bp in self.blueprint_map.values()}
        template_id = st.selectbox(
            "Select a File Template to Explore",
            options=[None] + list(bp_options.keys()),
            format_func=lambda x: "Select..." if x is None else bp_options.get(x)
        )

        if not template_id:
            return

        # 2. Get all versions for that template
        with st.spinner("Fetching file history..."):
            all_versions = registry_service.get_all_versions_for_template(self.env_id, template_id)

        if not all_versions:
            st.warning("No file versions found for this template in this environment.")
            return

        # Create the version map for dropdowns
        version_map = {}
        for v in all_versions:
            v_id = v['data_file_id']
            v_date = v['created_at'].split('T')[0]
            version_map[v_id] = f"ID: {v_id} ({v['current_status']}) - {v_date} by {v['created_by']}"

        st.markdown("---")

        tab_compare, tab_history = st.tabs(["Forensic Comparison", "Full Version History"])

        with tab_compare:
            st.markdown("Compare any two versions of this file, past or present.")
            col1, col2 = st.columns(2)

            new_file_id = col1.selectbox(
                "Compare Version:",
                options=version_map.keys(),
                format_func=lambda x: version_map.get(x)
            )

            old_file_id = col2.selectbox(
                "Against Version:",
                options=version_map.keys(),
                format_func=lambda x: version_map.get(x),
                index=min(1, len(version_map)-1) # Default to the second item
            )

            if new_file_id == old_file_id:
                st.error("Please select two different versions to compare.")
            elif new_file_id and old_file_id:
                st.markdown("---")
                with st.container(border=True):
                    # Call the comparison helper with the justification set to None
                    # We pass the justification from the *new file's* log
                    log_new = registry_service.get_audit_log_for_target(self.table_name, new_file_id)
                    justification = next((log for log in log_new if log['signoff_capacity'] == 'Doer' and log['action'] == 'CREATE'), None)

                    self._render_file_comparison(new_file_id, old_file_id, justification_log=justification)

        with tab_history:
            st.markdown("This is the complete 'life story' of all versions of this file, from oldest to newest.")

            # We reverse the list to show a chronological timeline
            for version in reversed(all_versions):
                v_id = version['data_file_id']
                v_status = version['current_status']

                with st.container(border=True):
                    st.markdown(f"**Version ID: `{v_id}` (Status: {v_status})**")
                    st.caption(f"Created: {version['created_at']} by {version['created_by']}")
                    st.text_input("File Hash", version['file_hash_sha256'], disabled=True, key=f"hash_{v_id}")

                    # Get the audit log *for this specific version*
                    audit_log = registry_service.get_audit_log_for_target(self.table_name, v_id)

                    if not audit_log:
                        st.caption("No human actions logged for this version.")
                    else:
                        st.markdown("**Version-Specific Actions:**")
                        for log in audit_log:
                            if log['action'] == 'CREATE':
                                st.info(f"**{log['action']}** by **{log['user_id']}** ({log['signoff_capacity']})")
                            elif log['action'] == 'SIGN_OFF':
                                st.success(f"**{log['action']}** by **{log['user_id']}** ({log['signoff_capacity']})")
                            elif log['action'] == 'REJECT':
                                st.error(f"**{log['action']}** by **{log['user_id']}** ({log['signoff_capacity']})")
                            st.caption(f"Comment: \"{log['comment']}\"")

    # --- TAB 4: DATA EDITOR (SECURED) ---
    def _render_editor_tab(self):
        st.subheader(f"✏️ Data Editor")
        st.error("**HIGH-RISK ACTION:** This tool will create a new, auditable version of a file. All changes are permanently logged and sent for review.")

        # 1. Get only *Active* files
        active_files = [f for f in self.all_files if f['current_status'] == 'Active']

        if not active_files:
            st.info("No 'Active' files are available to edit in this environment.")
            return

        file_options = {}
        for f in active_files:
            bp_name = self.blueprint_map.get(f['template_id'], {}).get('template_name', f['template_id'])
            file_options[f['data_file_id']] = f"{bp_name} (ID: {f['data_file_id']})"

        selected_id = st.selectbox(
            "Select an 'Active' File to Edit",
            options=[None] + list(file_options.keys()),
            format_func=lambda x: "Select a file..." if x is None else file_options.get(x)
        )

        if not selected_id:
            return

        file = next((f for f in active_files if f['data_file_id'] == selected_id), None)
        if not file: st.error("File not found."); return

        st.markdown("---")

        # 2. Load the file data for editing
        preview_data = registry_service.get_file_preview(file['file_path'], file['file_hash_sha256'])
        ext = os.path.splitext(file['file_path'])[1].lower()

        if preview_data['type'] == 'error':
            st.error(f"Cannot edit this file. Load error: {preview_data['data']}")
            return
        elif preview_data['type'] == 'unsupported':
            st.warning(f"In-app editing is not supported for {ext} files.")
            return
        elif preview_data['type'] == 'excel':
            st.warning("Editing multi-sheet Excel files is not yet supported. Only the first sheet can be edited.")

        with st.form(f"edit_form_{file['data_file_id']}"):
            edited_data = None
            if preview_data['type'] == 'excel':
                first_sheet_name = list(preview_data['data'].keys())[0]
                st.info(f"Editing first sheet: **{first_sheet_name}**")
                df = preview_data['data'][first_sheet_name]
                edited_data = st.data_editor(df, num_rows="dynamic", use_container_width=True)

            elif preview_data['type'] == 'dataframe':
                df = preview_data['data']
                edited_data = st.data_editor(df, num_rows="dynamic", use_container_width=True)

            elif preview_data['type'] == 'raw_text':
                edited_data = st.text_area("File Content", preview_data['data'], height=400)

            st.markdown("---")
            justification = st.text_area(" **Justification for Edit (Mandatory)**",
                                         key=f"edit_justification_{file['data_file_id']}",
                                         help="Explain *why* you are making this change. This will be sent to the Reviewer.")

            submitted = st.form_submit_button("Save as New Version")

            if submitted:
                if not justification:
                    st.error("A justification comment is mandatory to save a new version.")
                    return

                with st.spinner("Saving and logging new file version..."):
                    success, message = registry_service.upload_edited_file(
                        user_id=self.user_id,
                        user_role=self.role,
                        env_id=self.env_id,
                        template_id=file['template_id'],
                        edited_data=edited_data,
                        file_extension=ext,
                        justification_comment=justification
                    )
                    if success:
                        st.success(message); self.refresh_data(); st.rerun()
                    else:
                        st.error(message)

    # --- This is the "recipe" function that gets returned ---
    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
        """
        # CSS to make the review containers stand out
        st.markdown(
            """
            <style>
                div[data-testid="stForm"] {
                    border: 1px solid #E0E0E0;
                    border-radius: 10px;
                    padding: 1.5rem;
                    margin-top: 1rem;
                }
                div[data-testid="stContainer"] > div[data-testid="stVerticalBlock"] {
                    border: 1px dashed #C0C0C0;
                    padding: 1rem;
                    border-radius: 10px;
                    margin-top: 1rem;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.caption(f"You are working in the **{self.env_id}** environment (Category: {self.env_cat}). All actions are logged.")

        # --- Dynamic Tab Creation ---
        tabs_to_render = [
            "📥 Create New",
            f"📬 My Action Inbox ({len(self.action_inbox)})",
            "🔎 Data Explorer"
        ]

        # Only add the "Editor" tab if the user has permission AND
        # the environment is not "Validation"
        if self.show_editor_tab:
            tabs_to_render.append("✏️ Data Editor")

        tab_widgets = st.tabs(tabs_to_render)

        # Render common tabs
        tab_create = tab_widgets[0]
        tab_inbox = tab_widgets[1]
        tab_explorer = tab_widgets[2]

        with tab_create:
            self._render_create_tab()
        with tab_inbox:
            self._render_action_inbox_tab()
        with tab_explorer:
            self._render_explorer_tab()

        # Render conditional "Editor" tab
        if self.show_editor_tab:
            tab_editor = tab_widgets[3]
            with tab_editor:
                self._render_editor_tab()

# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main_app.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
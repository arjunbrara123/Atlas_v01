"""
apps/inputs/data_readiness.py
(Or inputs_overview.py)

This is the user-facing "Managerial" overview dashboard for the
"🚢 Data Inputs" stage of the workflow.

-------------------------------------------------------------------------------
PURPOSE:
-------------------------------------------------------------------------------
This dashboard is the "Mission Control" for the Data Inputs stage. It is a
read-only dashboard designed for managers and stakeholders to answer:
1.  Are we on track? (What is our data readiness?)
2.  Where are the bottlenecks? (Who is work waiting on?)
3.  What is the full history of a file? (The "File Explorer")

It is the perfect *read-only complement* to the "Data Inputs Workspace,"
which is the "write" dashboard for Doers and Reviewers.

-------------------------------------------------------------------------------
CORE FUNCTIONALITY:
-------------------------------------------------------------------------------
It is designed as a 3-tab application:

1.  "📊 Readiness Dashboard":
    - High-level KPIs (e.g., Readiness Score, Files Pending).
    - A "Governance Status" donut chart (the "big picture").
    - "Pending Files by Data Owner" chart (shows bottlenecks).
    - "File Status by Source Type" chart.

2.  "📥 Consolidated Inbox":
    - A single, read-only list of *all* pending actions (Doer & Reviewer)
      in the current environment.
    - Provides a one-click link to the "Data Inputs Workspace" to action them.

3.  "📂 File & Version Explorer":
    - "All Active Files": A simple view of *only* the latest, "Active"
      versions of all files.
    - "File Version History": A powerful "deep-dive" tool. A user
      selects a File Blueprint (e.g., "Business Plan") and sees
      *every version* ever uploaded (e.g., v1-Superseded, v2-Rejected,
      v3-Active) and its full audit log.

-------------------------------------------------------------------------------
ARCHITECTURE:
-------------------------------------------------------------------------------
- This file is a "dumb" UI. It contains *only* Streamlit code.
- It imports `registry_service.py` (the "Engine") to do all the work.
- It relies on new, powerful functions in the "Engine" like:
  - `get_files_for_user_dashboard()` (which we also use in the Workspace)
  - `get_audit_log_for_target()`
  - `get_all_files_in_environment()`
-------------------------------------------------------------------------------
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import json
import pandas as pd

# --- Helper Functions (specific to this dashboard) ---

def _get_status_from_logs(file_row, audit_log, blueprint):
    """
    Checks the audit log and blueprint to show the *governance* status.
    (This logic is duplicated from the Workspace for reliability/readability.)
    """
    # This is the "snapshot" status from the (Option 2) Hybrid Model
    if file_row['current_status'] == 'Rejected':
        return "Rejected"
    if file_row['current_status'] == 'Superseded':
        return "Superseded"

    # If it's 'Active', we check the sign-off workflow
    workflow = blueprint.get('signoff_workflow', 'Doer Only')
    doer_signed = any(log['signoff_capacity'] == 'Doer' and log['action'] == 'SIGN_OFF' for log in audit_log)
    reviewer_signed = any(log['signoff_capacity'] == 'Reviewer' and log['action'] == 'SIGN_OFF' for log in audit_log)

    if workflow == 'Doer + Reviewer':
        if doer_signed and reviewer_signed:
            return "Fully Approved"
        elif doer_signed:
            return "Pending Review"
        else:
            return "Pending Doer"
    else:  # Doer Only
        if doer_signed:
            return "Approved (Doer Only)"
        else:
            return "Pending Doer"

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
            "title_override": f"Data Inputs Overview ({self.env_id})",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        # We store the main dataframe on the class
        self.files_df = pd.DataFrame()
        self.pending_doer = []
        self.pending_reviewer = []

        # Load all data for all tabs on init
        self.refresh_data()

    def refresh_data(self):
        """
        Loads and processes all data needed for this dashboard.
        This is the main "engine" of the UI.
        """
        try:
            # 1. Get *all* "Data Inputs" blueprints to build a lookup map
            all_bps = registry_service.get_all_file_blueprints(stage='Data Inputs')
            blueprint_map = {bp['template_id']: bp for bp in all_bps}

            # 2. Get *all* "Data Input" files in this environment
            all_files_list = registry_service.get_all_files_in_environment(self.env_id, stage='Data Inputs')

            if not all_files_list:
                self.files_df = pd.DataFrame() # Ensure dataframe is empty
                return

            # 3. Get all data for the user's inboxes
            # This is a separate, smart call to the engine
            inbox_data = registry_service.get_files_for_user_dashboard(
                env_id=self.env_id,
                stage="Data Inputs",
                user_id=self.user_id,
                user_role=self.role
            )
            self.pending_doer = inbox_data['pending_doer']
            self.pending_reviewer = inbox_data['pending_reviewer']

            # 4. Get all audit logs for all files in this stage
            # This is *far* more efficient than looping (it's one query)
            file_ids_str = [f['file_id'] for f in all_files_list]
            all_audit_logs_list = registry_service.get_audit_log_for_target_list(
                target_table='data_files',
                target_ids=file_ids_str
            )
            # Convert list of logs into a dict for fast lookup
            # { "1001": [log, log, ...], "1002": [log, ...]}
            self.audit_log_map = {}
            for log in all_audit_logs_list:
                if log['target_id'] not in self.audit_log_map:
                    self.audit_log_map[log['target_id']] = []
                self.audit_log_map[log['target_id']].append(log)

            # 5. Build the Master DataFrame
            processed_data = []
            for file in all_files_list:
                bp = blueprint_map.get(file['template_id'], {})
                audit_log = self.audit_log_map.get(file['file_id'], [])

                status = _get_status_from_logs(file, audit_log, bp)

                processed_data.append({
                    "File ID": file['file_id'],
                    "Blueprint": bp.get('template_name', file['template_id']),
                    "template_id": file['template_id'],
                    "Data Owner": bp.get('data_owner_team', 'N/A'),
                    "Source Type": bp.get('source_type', 'N/A'),
                    "Governance Status": status,
                    "Version Status": file['current_status'],
                    "Created At": file['created_at'],
                    "Created By": file['created_by'].split('@')[0], # Clean up email
                    "File Path": file['file_path']
                })

            if processed_data:
                self.files_df = pd.DataFrame(processed_data)
                self.files_df['Created At'] = pd.to_datetime(self.files_df['Created At'])
            else:
                self.files_df = pd.DataFrame()

        except Exception as e:
            st.error(f"Failed to load dashboard data: {e}")
            self.files_df = pd.DataFrame()

    # --- TAB 1: READINESS DASHBOARD ---
    def _render_dashboard_tab(self):
        """Displays KPIs and charts for a managerial overview."""
        st.subheader("📊 Data Readiness Dashboard")
        st.markdown(f"This is the high-level governance status for the **{self.env_id}** environment.")

        if self.files_df.empty:
            st.info("No 'Data Input' files found in this environment.")
            return

        # --- 1. KEY PERFORMANCE INDICATORS (KPIs) ---
        df_active = self.files_df[self.files_df['Version Status'] == 'Active']

        total_active_blueprints = df_active['template_id'].nunique()
        total_approved = df_active[df_active['Governance Status'].str.contains('Approved')].shape[0]
        total_pending = df_active[df_active['Governance Status'].str.contains('Pending')].shape[0]
        total_rejected = df_active[df_active['Governance Status'] == 'Rejected'].shape[0]

        # Calculate Readiness Score
        total_active_files = total_approved + total_pending + total_rejected
        readiness_score = (total_approved / total_active_files) if total_active_files > 0 else 0

        st.markdown("---")
        st.markdown("##### Environment Vitals")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Data Files (Active Versions)", total_active_files)
        col2.metric("Files Fully Approved", total_approved)
        col3.metric("Files Pending Review", total_pending)
        col4.metric("Files Rejected", total_rejected)

        # Readiness Score Progress Bar
        st.markdown("**Overall Data Readiness**")
        st.progress(readiness_score, text=f"{readiness_score:.1%} Complete")
        st.caption("Readiness is the percentage of all *active* (latest version) files that are 'Fully Approved'.")


        # --- 2. GOVERNANCE CHARTS ---
        st.markdown("---")
        st.subheader("Governance Status Breakdowns")

        chart1, chart2 = st.columns(2)

        with chart1:
            st.markdown("##### 🔍 Status by File Type")
            st.caption("This shows the governance status for the *latest version* of each file type.")
            if not df_active.empty:
                bp_status_counts = df_active.groupby('Blueprint')['Governance Status'].value_counts().unstack(fill_value=0)
                st.bar_chart(bp_status_counts, use_container_width=True)
            else:
                st.info("No active files to display.")

        with chart2:
            st.markdown("##### 🌍 Status by Data Owner")
            st.caption("This helps identify which teams have the most pending or rejected files.")
            if not df_active.empty:
                owner_status_counts = df_active.groupby('Data Owner')['Governance Status'].value_counts().unstack(fill_value=0)
                # We only care about the actionable items
                actionable_statuses = [col for col in ['Pending Doer', 'Pending Review', 'Rejected'] if col in owner_status_counts.columns]
                if actionable_statuses:
                    st.bar_chart(owner_status_counts[actionable_statuses], use_container_width=True, stacked=True)
                else:
                    st.success("All files are approved!")
            else:
                st.info("No active files to display.")

    # --- TAB 2: CONSOLIDATED INBOX ---
    def _render_inbox_tab(self):
        """Displays a read-only consolidated inbox for all pending actions."""
        st.subheader("📥 Consolidated Inbox")
        st.markdown("A combined view of all files in this stage and environment that require an action.")

        st.info("To action these items, please go to the **Data Inputs Workspace** dashboard.", icon="ℹ️")

        st.markdown("---")
        st.markdown("##### 🧐 Files Awaiting **My Review** (Reviewer Inbox)")
        if not self.pending_reviewer:
            st.success("Your 'Reviewer' inbox is empty.")
        else:
            st.warning(f"You have **{len(self.pending_reviewer)}** files to review.")
            pending_review_data = []
            for file in self.pending_reviewer:
                bp = self.blueprint_map.get(file['template_id'], {})
                audit_log = self._get_file_audit_log(file)
                doer_log = next((log for log in audit_log if log['signoff_capacity'] == 'Doer'), {})
                pending_review_data.append({
                    "Name": bp.get('template_name', file['template_id']),
                    "File ID": file['file_id'],
                    "Created By": file['created_by'],
                    "Doer's Comment": doer_log.get('comment', 'N/A')
                })
            st.dataframe(pending_review_data, use_container_width=True)

        st.markdown("---")
        st.markdown("##### 📝 Files Awaiting **My Sign-Off** (Doer Inbox)")
        if not self.pending_doer:
            st.success("Your 'Doer' inbox is empty.")
        else:
            st.warning(f"You have **{len(self.pending_doer)}** files to sign-off as 'Doer'.")
            pending_doer_data = []
            for file in self.pending_doer:
                bp = self.blueprint_map.get(file['template_id'], {})
                pending_doer_data.append({
                    "Name": bp.get('template_name', file['template_id']),
                    "File ID": file['file_id'],
                    "Created At": file['created_at'],
                })
            st.dataframe(pending_doer_data, use_container_width=True)

    # --- TAB 3: FILE & VERSION EXPLORER ---
    def _render_explorer_tab(self):
        """A read-only deep-dive explorer."""
        st.subheader("📂 File & Version Explorer")
        st.markdown("A complete, read-only view of all files in this environment, including their full version history.")

        if self.files_df.empty:
            st.info("No 'Data Input' files found in this environment.")
            return

        # --- View 1: All Active Files ---
        st.markdown("##### All Active Files (Latest Versions)")
        st.caption("This table shows *only* the most recent, active version of each file blueprint.")
        active_files_display = self.files_df[self.files_df['Version Status'] == 'Active'].copy()

        st.dataframe(
            active_files_display.sort_values(by="Name"),
            use_container_width=True,
            column_order=("Name", "Governance Status", "Data Owner", "Source Type", "Created By", "File ID"),
            column_config={
                "Governance Status": st.column_config.TextColumn("Status"),
                "File ID": st.column_config.TextColumn("File ID", width="small"),
            }
        )

        # --- View 2: File Version History ---
        st.markdown("---")
        st.markdown("##### History Deep-Dive")
        st.caption("Select a file blueprint to see *all* of its versions (including superseded and rejected).")

        blueprint_names = sorted(self.files_df['Blueprint'].unique())
        selected_bp_name = st.selectbox(
            "Select a File Blueprint to see its full version history:",
            options=blueprint_names
        )

        if selected_bp_name:
            history_df = self.files_df[self.files_df['Blueprint'] == selected_bp_name].copy()
            history_df.sort_values(by="Created At", ascending=False, inplace=True)

            st.dataframe(
                history_df,
                use_container_width=True,
                column_order=("Version Status", "Governance Status", "Created At", "Created By", "File ID", "File Path"),
                column_config={
                    "Created At": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
                    "Version Status": st.column_config.TextColumn("Version"),
                    "Governance Status": st.column_config.TextColumn("Status"),
                }
            )

            # --- Show Audit Log for a Selected Version ---
            st.markdown("###### Audit Trail for a Selected Version")
            file_id_options = history_df['File ID'].tolist()
            selected_file_id = st.selectbox("Select a File ID to see its specific audit log:", options=file_id_options)

            if selected_file_id:
                try:
                    # We must fetch this log on-demand
                    audit_log = registry_service.get_audit_log_for_target('data_files', selected_file_id)
                    if not audit_log:
                        st.info("No audit history found for this specific file version.")
                    else:
                        st.dataframe(audit_log, use_container_width=True, column_order=(
                            "timestamp", "user_id", "action", "signoff_capacity", "comment"
                        ))
                except Exception as e:
                    st.error(f"Failed to load audit log: {e}")

    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
        """

        st.caption(f"You are viewing the **{self.env_id}** environment. This is a read-only dashboard.")

        # Define the tabs
        tab_dash, tab_inbox, tab_explorer = st.tabs(
            [
                "📊 Readiness Dashboard",
                f"📥 Consolidated Inbox ({len(self.pending_doer) + len(self.pending_reviewer)})",
                "📂 File & Version Explorer"
            ]
        )

        # Render content for each tab
        with tab_dash:
            self._render_dashboard_tab()

        with tab_inbox:
            self._render_inbox_tab()

        with tab_explorer:
            self._render_explorer_tab()

# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta

"""
apps/internal/system_status.py

This dashboard is the central "Mission Control" for the Atlas platform.
It is a **read-only** dashboard for admins to monitor the
health, status, and integrity of the entire registry and file system.

It is designed to:
- Show high-level KPIs, graphs, and charts.
- Display a live feed of all human actions (from the audit trail).
- Provide a UI for running all "health check" scans.
- This dashboard is READ-ONLY and has no destructive actions.
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import pandas as pd


# --- Helper Functions (specific to this dashboard) ---

def render_health_check(title, description, scan_function, format_results=False):
    """Helper to create a consistent UI for each health check button."""
    st.markdown(f"##### {title}")
    st.caption(description)

    if st.button(f"Scan for {title}"):
        with st.spinner("Scanning registry..."):
            try:
                results = scan_function()
                if not results:
                    st.success(f"**No issues found.** The registry is clean for this check.")
                else:
                    st.error(f"**Found {len(results)} issues!**")
                    if format_results:
                        # Format list of dicts for better display
                        st.dataframe(pd.DataFrame(results), use_container_width=True)
                    else:
                        st.dataframe(results, use_container_width=True)
            except Exception as e:
                st.exception(f"An error occurred during the scan: {e}")


# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        self.role = role
        self.app_environment = environment  # This is the *global* env
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.meta = {
            "title_override": "System Status & Health",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        # Load all data on init
        self.refresh_data()

    def refresh_data(self):
        """Gets all data needed for this dashboard."""
        try:
            self.kpis = registry_service.get_system_kpis()
            self.pending_actions = registry_service.get_pending_actions_dashboard()
            self.recent_activity = registry_service.get_audit_log_all_actions(limit=50)

            # Data for charts
            all_files = registry_service.get_all_files_in_environment(env_id=None,
                                                                      stage=None)  # A small bug in old service, assuming it gets ALL files
            self.files_df = pd.DataFrame(all_files)
            if not self.files_df.empty:
                self.files_df['created_at'] = pd.to_datetime(self.files_df['created_at'])

            self.all_envs = registry_service.get_all_environments()
            self.envs_df = pd.DataFrame(self.all_envs)

        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.kpis = {}
            self.pending_actions = []
            self.recent_activity = []
            self.files_df = pd.DataFrame()
            self.envs_df = pd.DataFrame()

    # --- TAB 1: PLATFORM VITALS (KPIs & Charts) ---
    def _render_vitals_tab(self):
        """Displays KPIs, charts, pending actions, and recent activity."""
        st.subheader("📊 Platform Vitals")
        st.markdown("A real-time overview of the platform's key objects and activity.")

        # 1. KPIs
        k = self.kpis
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Environments", k.get("environment_blueprints", 0))
        c2.metric("File Blueprints", k.get("file_blueprints", 0))
        total_files = k.get("data_files", 0) + k.get("model_files", 0) + k.get("result_files", 0) + k.get(
            "report_files", 0)
        c3.metric("Total File Instances", total_files)
        c4.metric("Total Audit Events", k.get("audit_trail", 0))

        st.markdown("---")

        # 2. Charts
        st.subheader("Charts & Trends")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Environments by Category")
            if not self.envs_df.empty:
                env_counts = self.envs_df.groupby('env_cat').size().reset_index(name='count')
                st.bar_chart(env_counts, x='env_cat', y='count')
            else:
                st.caption("No environment data to display.")

        with col2:
            st.markdown("##### File Instances by Stage")
            if not self.files_df.empty:
                stage_map = {
                    'data_files': 'Data Inputs',
                    'model_files': 'Actuarial Models',
                    'result_files': 'Results & Validation',
                    'report_files': 'Reports & Insights'
                }
                self.files_df['stage'] = self.files_df['table_name'].map(stage_map)
                stage_counts = self.files_df.groupby('stage').size().reset_index(name='count')
                st.bar_chart(stage_counts, x='stage', y='count')
            else:
                st.caption("No file data to display.")

        st.markdown("---")

        # 3. Pending Actions
        st.subheader("Action Required: Files Awaiting Sign-Off")
        st.caption(
            "A summary of all 'Active' files across the platform that are awaiting 'Doer' or 'Reviewer' sign-off.")

        if not self.pending_actions:
            st.success("✅ Inbox Zero! No files are currently awaiting sign-off.")
        else:
            st.warning(f"Found **{len(self.pending_actions)}** files awaiting sign-off.")
            st.dataframe(
                self.pending_actions,
                use_container_width=True,
                column_config={
                    "file_id": st.column_config.TextColumn("File ID", width="small"),
                    "template_id": st.column_config.TextColumn("Blueprint"),
                    "env_id": st.column_config.TextColumn("Environment"),
                    "created_by": st.column_config.TextColumn("Created By"),
                    "created_at": st.column_config.DatetimeColumn("Created At", format="YYYY-MM-DD HH:mm"),
                },
                column_order=("created_at", "template_id", "env_id", "created_by", "file_id")
            )

        st.markdown("---")

        # 4. Recent Activity
        st.subheader("Recent Platform Activity")
        st.caption("The 50 most recent human actions recorded in the `audit_trail` (Table 8).")

        if not self.recent_activity:
            st.info("No audit history found.")
        else:
            st.dataframe(
                self.recent_activity,
                use_container_width=True,
                height=400,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
                    "user_id": st.column_config.TextColumn("User"),
                    "action": st.column_config.TextColumn("Action", width="small"),
                    "target_table": st.column_config.TextColumn("Object Type"),
                    "target_id": st.column_config.TextColumn("Object ID"),
                    "comment": st.column_config.TextColumn("Comment", width="large")
                },
                column_order=("timestamp", "user_id", "action", "target_table", "target_id", "comment")
            )

    # --- TAB 2: REGISTRY INTEGRITY ---
    def _render_integrity_tab(self):
        """UI for running read-only health checks."""
        st.subheader("❤️ Registry Integrity Checks")
        st.markdown("Run these scans to find inconsistencies between the database and the file system.")
        st.info("These scans are **read-only** and will not make any changes.")

        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                render_health_check(
                    title="Orphaned File Records",
                    description="Finds DB records (Tables 3-6) that point to a physical file that no longer exists on the server.",
                    scan_function=registry_service.find_orphaned_files,
                    format_results=True
                )

        with col2:
            with st.container(border=True):
                render_health_check(
                    title="Orphaned Folders",
                    description="Finds physical environment folders on the server that do not have a matching record in the `environment_blueprints` (Table 1).",
                    scan_function=registry_service.find_orphaned_folders,
                    format_results=True
                )

        st.markdown("---")
        st.subheader("Blueprint Integrity Checks")

        col3, col4, col5 = st.columns(3)

        with col3:
            with st.container(border=True):
                render_health_check(
                    title="Broken Blueprint Links",
                    description="Finds files (Tables 3-6) that point to a `template_id` that no longer exists in `file_blueprints` (Table 2).",
                    scan_function=registry_service.find_broken_blueprint_links,
                    format_results=True
                )

        with col4:
            with st.container(border=True):
                render_health_check(
                    title="Unused Blueprints",
                    description="Finds 'Active' blueprints in Table 2 that are not being used by *any* file in *any* environment.",
                    scan_function=registry_service.find_unused_blueprints,
                    format_results=True
                )

        with col5:
            with st.container(border=True):
                render_health_check(
                    title="Invalid JSON Structures",
                    description="Scans the `expected_structure` column in `file_blueprints` (Table 2) for invalid JSON syntax.",
                    scan_function=registry_service.validate_all_blueprint_json,
                    format_results=False  # Simple list is fine
                )

    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
        """

        # Define the tabs
        tab_vitals, tab_integrity = st.tabs(
            [
                "📊 Platform Vitals",
                "❤️ Registry Integrity"
            ]
        )

        # Render content for each tab
        with tab_vitals:
            self.refresh_data()  # Always get fresh data for dashboard
            self._render_vitals_tab()

        with tab_integrity:
            self._render_integrity_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta

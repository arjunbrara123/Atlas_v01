"""
apps/inputs/data_readiness.py
(Data Inputs Overview - "Mission Control")

This is the user-facing "Managerial" overview dashboard for the
"🚢 Data Inputs" stage of the workflow.

-------------------------------------------------------------------------------
PURPOSE:
-------------------------------------------------------------------------------
This dashboard is the "Mission Control" for the Data Inputs stage. It is a
100% read-only dashboard designed for managers, stakeholders, and auditors
to answer key business questions without any "write" capabilities.

It is the analytical companion to the "Data Workspace" (the "Workshop").

-------------------------------------------------------------------------------
CORE FUNCTIONALITY (6 TABS):
-------------------------------------------------------------------------------
1.  "📊 Readiness & Timeline":
    Answers "Are we on track?"
    - High-level KPIs (Readiness %, Pending Actions).
    - Readiness-by-Owner chart.
    - Integrated Project Milestone Gantt Chart.
    - "At-Risk Milestones" (tasks linked to unapproved files).

2.  "📈 Bottleneck Analysis":
    Answers "Where are the bottlenecks?"
    - "Pending Actions by User" (finds who is slow).
    - "Process Health KPIs" (Rejection Rate, Version Churn).
    * "Review SLA Timer" (shows items waiting the longest).

3.  "🛡️ Risk & Compliance":
    Answers "Is our data governed and secure?"
    - "Governance by Data Sensitivity" (highlights risk).
    - "Stale Data Report" (finds old, un-updated files).
    - "Blueprint Policy View" (a read-only view of all rules).

4.  "📜 Live Audit Log":
    Answers "What just happened?"
    - A simple, filterable, environment-wide feed of the
      `gov_audit_trail` table.

5.  "🩺 System Integrity & Access":
    Answers "Is the system healthy and auditable?"
    - "File Integrity Report" (Orphans, Hash Mismatches).
    - "User Permissions Matrix" (who can do what).

6.  "🌐 End-to-End Lineage":
    Answers "How does our data flow?"
    - A visual, color-coded graph of all file dependencies,
      showing how files connect from data to report.
-------------------------------------------------------------------------------
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import pandas as pd
import plotly.express as px
import graphviz
import sys
import os

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

# -----------------------------------------------------------------------------
# DATA LOADING FUNCTIONS (CACHED)
#
# This is the FIX for the UnhashableParamError.
# We use standalone, cached functions to load data.
# The Page class will then call these fast functions.
# -----------------------------------------------------------------------------

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_master_files_df(env_id):
    """(Cached) Gets the 'Master DataFrame' for the entire dashboard."""
    try:
        df = registry_service.get_all_files_dataframe_for_env(env_id)
        if not df.empty:
             df['created_at'] = pd.to_datetime(df['created_at'])
        return df
    except Exception as e:
        st.error(f"Error in get_master_files_df: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_milestones_df(env_id):
    """(Cached) Gets the project milestones."""
    try:
        df = pd.DataFrame(registry_service.get_milestones_for_env(env_id))
        if not df.empty:
            df['due_date'] = pd.to_datetime(df['due_date'])
            # Fill in calculated dates for Gantt chart
            df['calc_start_date'] = pd.to_datetime(df['calc_start_date']).fillna(df['due_date'] - pd.to_timedelta(df['duration_days'], unit='d'))
            df['calc_due_date'] = pd.to_datetime(df['calc_due_date']).fillna(df['due_date'])
        return df
    except Exception as e:
        st.error(f"Error in get_milestones_df: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_audit_log_df(env_id):
    """(Cached) Gets all audit logs for the environment."""
    try:
        return pd.DataFrame(registry_service.get_audit_log_for_environment(env_id))
    except Exception as e:
        st.error(f"Error in get_audit_log_df: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_lineage_graph(env_id):
    """(Cached) Gets the lineage graph data."""
    try:
        return registry_service.get_full_lineage_graph(env_id)
    except Exception as e:
        st.error(f"Error in get_lineage_graph: {e}")
        return {'nodes': [], 'edges': []}

@st.cache_data(ttl=300)
def get_integrity_report(env_id):
    """(Cached) Gets the system integrity report."""
    try:
        return registry_service.get_system_integrity_report(env_id)
    except Exception as e:
        st.error(f"Error in get_integrity_report: {e}")
        return {'orphaned_files': [], 'orphaned_folders': [], 'hash_mismatches': []}

@st.cache_data(ttl=300)
def get_permissions():
    """(Cached) Gets the permissions matrix."""
    try:
        return registry_service.get_all_permissions()
    except Exception as e:
        st.error(f"Error in get_permissions: {e}")
        return {'by_user': {}, 'by_file': {}}

@st.cache_data(ttl=300)
def get_blueprint_map():
    """(Cached) Gets all blueprints as a dictionary."""
    try:
        all_bps_list = registry_service.get_all_file_blueprints()
        # Convert the list into a dictionary (a "map") using template_id as the key
        return {bp['template_id']: bp for bp in all_bps_list}
    except Exception as e:
        st.error(f"Error in get_blueprint_map: {e}")
        return {}

# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        """
        Initializes the Page object.
        """
        self.role = role
        self.env_id = environment
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.meta = {
            "title_override": f"Data Inputs Overview ({self.env_id})",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
        }

        # --- Initialize data containers ---
        self.files_df = pd.DataFrame()
        self.milestones_df = pd.DataFrame()
        self.audit_log_df = pd.DataFrame()
        self.lineage_graph = {'nodes': [], 'edges': []}
        self.integrity_report = {'orphaned_files': [], 'orphaned_folders': [], 'hash_mismatches': []}
        self.permissions_map = {'by_user': {}, 'by_file': {}}
        self.blueprint_map = {}

        # Load all data for all tabs on init
        self.refresh_data()

    def refresh_data(self):
        """
        Loads and processes all data needed for this dashboard.
        This function is NOT cached. It calls the fast, cached "getter" functions.
        """
        try:
            # Call our new, cached functions
            self.files_df = get_master_files_df(self.env_id)
            self.milestones_df = get_milestones_df(self.env_id)
            self.audit_log_df = get_audit_log_df(self.env_id)
            self.lineage_graph = get_lineage_graph(self.env_id)
            self.integrity_report = get_integrity_report(self.env_id)
            self.permissions_map = get_permissions()
            self.blueprint_map = get_blueprint_map()

        except Exception as e:
            # This is a fallback
            st.error(f"Failed to refresh dashboard data: {e}")

    # --- TAB 1: READINESS DASHBOARD ---
    def _render_dashboard_tab(self):
        st.subheader("📊 Readiness & Project Timeline")
        st.markdown(f"This is the high-level governance and project status for the **{self.env_id}** environment.")

        if self.files_df.empty:
            st.info("No files found in this environment."); return

        # --- [T1-KPIs] ---
        try:
            # Filter for *only* "Data Inputs" and *only* the latest versions
            df_active_data = self.files_df[
                (self.files_df['stage'] == 'Data Inputs') &
                (self.files_df['current_status'] == 'Active')
            ]

            if df_active_data.empty:
                st.info("No *active* 'Data Input' files found in this environment to report on.")
                return

            total_active_files = df_active_data['template_id'].nunique()
            total_approved = df_active_data[df_active_data['governance_status'] == 'Fully Approved'].shape[0]
            total_pending = df_active_data[df_active_data['governance_status'].isin(['Pending Doer', 'Pending Review'])].shape[0]
            total_rejected = df_active_data[df_active_data['governance_status'] == 'Rejected'].shape[0]

            readiness_score = (total_approved / total_active_files) if total_active_files > 0 else 0

            st.markdown("---")
            st.markdown("##### Environment Vitals (Data Inputs Only)")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Active File Types", total_active_files)
            col2.metric("Files Fully Approved", total_approved)
            col3.metric("Files Pending Action", total_pending)
            col4.metric("Files Rejected", total_rejected)

            st.progress(readiness_score, text=f"Overall Data Readiness: {readiness_score:.1%}")
        except Exception as e:
            st.error(f"Could not calculate KPIs: {e}")

        # --- [T1-CHARTS] ---
        st.markdown("---")
        st.subheader("Data Readiness Status")

        try:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### Readiness by Data Owner")
                st.caption("This shows the governance status for the *latest version* of each file, grouped by owner.")
                if not df_active_data.empty:
                    owner_status_counts = df_active_data.groupby('data_owner_team')['governance_status'].value_counts().unstack(fill_value=0)
                    st.bar_chart(owner_status_counts, use_container_width=True)
                else:
                    st.info("No active data input files to display.")

            with col2:
                st.markdown("##### Readiness by Source Type")
                st.caption("This shows if 'External Connection' files are failing more often than 'Manual Uploads'.")
                if not df_active_data.empty:
                    source_status_counts = df_active_data.groupby('source_type')['governance_status'].value_counts().unstack(fill_value=0)
                    st.bar_chart(source_status_counts, use_container_width=True)
                else:
                    st.info("No active data input files to display.")
        except Exception as e:
            st.error(f"Could not render readiness charts: {e}")

        # --- [T1-TIMELINE] ---
        st.markdown("---")
        st.subheader("Project Timeline & At-Risk Milestones")

        try:
            if self.milestones_df.empty:
                st.info("No project milestones are defined for this environment.")
                return

            st.markdown("##### Project Gantt Chart")
            # Use Plotly for an interactive Gantt chart
            fig = px.timeline(
                self.milestones_df,
                x_start="calc_start_date",
                x_end="calc_due_date",
                y="title",
                color="status",
                title="Project Milestones",
                labels={"title": "Milestone Task"}
            )
            fig.update_yaxes(autorange="reversed") # Show top-to-bottom
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("##### At-Risk Milestones")
            st.caption("These are open tasks from the plan that are linked to a data file that is NOT yet 'Fully Approved'.")

            # Merge milestones with the file status
            # ASSUMES: milestone target_id is the template_id and target_table is correct
            df_active_files_simple = df_active_data[['template_id', 'governance_status']].rename(columns={'template_id': 'target_id'})

            df_milestones_open = self.milestones_df[
                (self.milestones_df['status'] != 'Complete') &
                # This logic is simplified; a real app might need a more robust join
                (self.milestones_df['target_table'].str.startswith('inst_'))
            ]

            df_at_risk = pd.merge(
                df_milestones_open,
                df_active_files_simple,
                on='target_id',
                how='left'
            )

            # Filter for at-risk items
            df_at_risk = df_at_risk[df_at_risk['governance_status'] != 'Fully Approved']

            if df_at_risk.empty:
                st.success("No milestones are currently at risk.")
            else:
                st.dataframe(
                    df_at_risk,
                    column_order=['title', 'due_date', 'owner_user_id', 'governance_status'],
                    column_config={"title": "Milestone", "due_date": "Due", "owner_user_id": "Owner", "governance_status": "File Status"}
                )
        except Exception as e:
            st.error(f"Could not render project timeline: {e}")


    # --- TAB 2: BOTTLENECK ANALYSIS ---
    def _render_bottleneck_tab(self):
        st.subheader("📈 Bottleneck & Process Analysis")
        st.markdown("This tab helps identify who work is waiting on and highlights inefficiencies in the process.")

        if self.files_df.empty:
            st.info("No files found in this environment."); return

        df_active = self.files_df[self.files_df['current_status'] == 'Active']
        df_all_versions = self.files_df[self.files_df['stage'] == 'Data Inputs']

        # --- [T2-BOTTLENECKS] ---
        st.markdown("---")
        st.markdown("##### Pending Actions by Assignee")
        st.caption("This shows which users or teams are holding up the workflow right now.")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Pending 'Doer' Sign-off** (by Creator)")
            pending_doer_df = df_active[df_active['governance_status'] == 'Pending Doer']
            if pending_doer_df.empty:
                st.success("No files are awaiting Doer sign-off.")
            else:
                doer_bottlenecks = pending_doer_df.groupby('created_by').size()
                st.bar_chart(doer_bottlenecks)

        with col2:
            st.markdown("**Pending 'Review'** (by Data Owner Team)")
            pending_review_df = df_active[df_active['governance_status'] == 'Pending Review']
            if pending_review_df.empty:
                st.success("No files are awaiting Review.")
            else:
                review_bottlenecks = pending_review_df.groupby('data_owner_team').size()
                st.bar_chart(review_bottlenecks)

        # --- [T2-SLA] ---
        st.markdown("---")
        st.markdown("##### Review SLA Timer")
        st.caption("These files are 'Pending Review' and sorted by the longest waiting time.")

        if pending_review_df.empty:
            st.success("No files are awaiting review.")
        else:
            pending_review_df['Days Waiting'] = (datetime.now() - pending_review_df['created_at']).dt.days
            st.dataframe(
                pending_review_df.sort_values(by='Days Waiting', ascending=False),
                column_order=['blueprint_name', 'data_owner_team', 'created_by', 'Days Waiting'],
                use_container_width=True
            )

        # --- [T2-PROCESS-HEALTH] ---
        st.markdown("---")
        st.markdown("##### Process Health KPIs")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Rejection Rate by File Type**")
            st.caption("A high rejection rate may indicate unclear requirements or a bad blueprint.")
            # We look at *all* versions, not just active
            # --- THIS IS THE FIX ---
            # 1. Get the full DataFrame of rejection rates
            reject_rate_df = df_all_versions.groupby('blueprint_name')['current_status'].value_counts(normalize=True).unstack(fill_value=0)

            # 2. Check if the 'Rejected' column exists.
            if 'Rejected' in reject_rate_df.columns:
                # Plot just the 'Rejected' Series, which is valid
                st.bar_chart(reject_rate_df['Rejected'])
            else:
                # If no 'Rejected' column exists, show a message instead of plotting '0'
                st.caption("No files have been rejected.")
            # --- END OF FIX ---

        with col2:
            st.markdown("**Version Churn by File Type**")
            st.caption("A high number of versions may indicate a file is unstable or has a complex workflow.")
            version_churn = df_all_versions.groupby('blueprint_name')['file_id'].count().sort_values(ascending=False)
            st.dataframe(version_churn.head(10), use_container_width=True)


    # --- TAB 3: RISK & COMPLIANCE ---
    def _render_risk_tab(self):
        st.subheader("🛡️ Risk & Compliance Overview")
        st.markdown("This tab provides a read-only view of data sensitivity, stale files, and all governance rules.")

        if self.files_df.empty:
            st.info("No files found in this environment."); return

        df_active = self.files_df[self.files_df['current_status'] == 'Active']

        # --- [T3-SENSITIVITY] ---
        st.markdown("---")
        st.markdown("##### Governance Status by Data Sensitivity")
        st.caption("This matrix highlights governance gaps for your most sensitive data. (Data Inputs only)")

        df_active_data = self.files_df[
                (self.files_df['stage'] == 'Data Inputs') &
                (self.files_df['current_status'] == 'Active')
            ]

        if df_active_data.empty:
            st.info("No active data input files to analyze.")
        else:
            risk_matrix = df_active_data.groupby('data_sensitivity')['governance_status'].value_counts().unstack(fill_value=0)
            st.dataframe(risk_matrix, use_container_width=True)

            # Highlight high-risk items
            high_risk_count = 0
            columns_to_check = ['Pending Doer', 'Pending Review', 'Rejected']
            indices_to_check = ['Confidential', 'Restricted']

            for status in columns_to_check:
                if status in risk_matrix.columns:
                    for sensitivity in indices_to_check:
                        if sensitivity in risk_matrix.index:
                            high_risk_count += risk_matrix.loc[sensitivity, status]

            if high_risk_count > 0:
                st.error(f"**Risk Alert:** You have **{high_risk_count}** sensitive files that are not fully approved.")
            else:
                st.success("All sensitive files are fully approved.")

        # --- [T3-STALE] ---
        st.markdown("---")
        st.markdown("##### Stale Data Report")
        st.caption("These 'Active' files have not been updated in over 90 days.")

        stale_threshold = datetime.now() - pd.to_timedelta(90, unit='d')
        df_stale = df_active[df_active['created_at'] < stale_threshold]

        if df_stale.empty:
            st.success("No stale files found.")
        else:
            st.warning(f"Found **{len(df_stale)}** active files older than 90 days.")
            st.dataframe(
                df_stale.sort_values(by='created_at'),
                column_order=['blueprint_name', 'data_owner_team', 'created_at', 'file_id'],
                use_container_width=True
            )

        # --- [T3-POLICY] ---
        st.markdown("---")
        st.markdown("##### Blueprint Policy View (All Stages)")
        st.caption("This is a read-only view of all *current rules* from the File Blueprint Manager.")

        if not self.blueprint_map:
            st.warning("No blueprints are defined in the system.")
        else:
            # This line is now fixed because self.blueprint_map is a dict
            bp_df = pd.DataFrame(self.blueprint_map.values())
            st.dataframe(
                bp_df,
                use_container_width=True,
                column_order=['template_name', 'stage', 'data_owner_team', 'data_sensitivity', 'signoff_workflow', 'primary_key_column', 'doer_roles', 'reviewer_roles'],
                column_config={"template_name": "Blueprint"}
            )


    # --- TAB 4: LIVE AUDIT LOG ---
    def _render_audit_tab(self):
        st.subheader("📜 Live Audit Log")
        st.markdown(f"The complete, filterable audit trail of all human actions in the **{self.env_id}** environment.")

        if self.audit_log_df.empty:
            st.info("No audit logs found for this environment."); return

        # --- [T4-FILTERS] ---
        st.markdown("##### Filter Log")

        col1, col2 = st.columns(2)

        # Filter by Action
        actions = self.audit_log_df['action'].unique()
        selected_actions = col1.multiselect("Filter by Action", options=actions, default=actions)

        # Filter by User
        users = self.audit_log_df['user_id'].unique()
        selected_users = col2.multiselect("Filter by User", options=users, default=users)

        # Apply filters
        filtered_df = self.audit_log_df[
            (self.audit_log_df['action'].isin(selected_actions)) &
            (self.audit_log_df['user_id'].isin(selected_users))
        ]

        st.dataframe(filtered_df, use_container_width=True)


    # --- TAB 5: SYSTEM INTEGRITY & ACCESS ---
    def _render_integrity_tab(self):
        st.subheader("🩺 System Integrity & Access Report")
        st.markdown("A read-only report on system health and user permissions.")

        # --- [T5-INTEGRITY] ---
        st.markdown("---")
        st.markdown("##### File Integrity Report")
        st.caption("Checks for 'orphaned' files and file tampering (hash mismatches).")

        report = self.integrity_report

        col1, col2, col3 = st.columns(3)
        col1.metric("Orphaned Files (DB only)", len(report['orphaned_files']))
        col2.metric("Orphaned Folders (Disk only)", len(report['orphaned_folders']))
        col3.metric("File Hash Mismatches", len(report['hash_mismatches']))

        if report['hash_mismatches']:
            st.error(f"**CRITICAL SECURITY ALERT:** {len(report['hash_mismatches'])} files on disk do not match their database hash. This indicates tampering.")
            st.dataframe(report['hash_mismatches'], use_container_width=True)
        else:
            st.success("File integrity check passed. No hash mismatches found.")

        if report['orphaned_files'] or report['orphaned_folders']:
            with st.expander("View Orphan Details"):
                st.markdown("Orphaned Files (Record exists in DB, but file is missing from disk)")
                st.dataframe(report['orphaned_files'], use_container_width=True)
                st.markdown("Orphaned Folders (File exists on disk, but has no DB record)")
                st.dataframe(report['orphaned_folders'], use_container_width=True)

        # --- [T5-PERMISSIONS] ---
        st.markdown("---")
        st.markdown("##### User Permissions Matrix")
        st.caption("A read-only tool to audit 'who can do what' in this application.")

        permissions = self.permissions_map
        if not permissions or not self.blueprint_map:
            st.warning("Could not load permissions map."); return

        tab_user, tab_file = st.tabs(["View by User", "View by File"])

        with tab_user:
            user_list = sorted(permissions['by_user'].keys())
            selected_user = st.selectbox("Select a User", options=user_list)
            if selected_user:
                st.dataframe(permissions['by_user'][selected_user], use_container_width=True)

        with tab_file:
            bp_list = sorted(self.blueprint_map.keys())
            selected_bp = st.selectbox(
                "Select a File Blueprint",
                options=bp_list,
                format_func=lambda x: self.blueprint_map.get(x, {}).get('template_name', x)
            )
            if selected_bp:
                st.dataframe(permissions['by_file'].get(selected_bp, {}), use_container_width=True)

    # --- TAB 6: END-TO-END LINEAGE ---
    def _render_lineage_tab(self):
        st.subheader("🌐 End-to-End Lineage Explorer")
        st.markdown("A visual graph of how data files flow through models to create results and reports.")

        graph_data = self.lineage_graph
        if not graph_data or not graph_data['nodes']:
            st.info("No file lineage (parent/child links) has been created in this environment yet."); return

        try:
            # --- [T6-FILTERS] ---
            node_map = {n['id']: n for n in graph_data['nodes']}
            edge_children = {e['to'] for e in graph_data['edges']}
            root_nodes = [n['id'] for n in graph_data['nodes'] if n['id'] not in edge_children]

            focused_template = st.selectbox(
                "Focus on a Data Flow (Select a Root File)",
                options=['All'] + [node_map[n]['label'] for n in root_nodes],
            )

            # --- [T6-GRAPH] ---
            dot = graphviz.Digraph(
                comment='Data Lineage Graph',
                graph_attr={'rankdir': 'LR', 'splines': 'ortho'}
            )
            dot.attr('node', shape='box', style='filled', fontname='Arial', fontsize='10')
            dot.attr('edge', fontname='Arial', fontsize='9')

            nodes_to_render = set()
            if focused_template == 'All':
                nodes_to_render = {n['id'] for n in graph_data['nodes']}
            else:
                start_node_id = next((n['id'] for n in graph_data['nodes'] if n['label'] == focused_template), None)
                if start_node_id:
                    q = [start_node_id]
                    while q:
                        current = q.pop(0)
                        if current in nodes_to_render: continue
                        nodes_to_render.add(current)
                        for edge in graph_data['edges']:
                            if edge['from'] == current:
                                q.append(edge['to'])

            # Add nodes to graph
            for node in graph_data['nodes']:
                if node['id'] not in nodes_to_render:
                    continue

                # Color code by status
                if node['status'] == 'Fully Approved': color = '#c8e6c9' # Green
                elif node['status'] == 'Rejected': color = '#ffcdd2' # Red
                elif 'Pending' in node['status']: color = '#ffe0b2' # Orange
                else: color = '#eeeeee' # Grey

                dot.node(
                    node['id'],
                    label=f"{node['label']}\n(ID: {node['id'].split('_')[-1]})\nStatus: {node['status']}",
                    fillcolor=color
                )

            # Add edges to graph
            for edge in graph_data['edges']:
                if edge['from'] in nodes_to_render and edge['to'] in nodes_to_render:
                    dot.edge(edge['from'], edge['to'])

            st.graphviz_chart(dot)

        except Exception as e:
            st.error(f"Could not render lineage graph: {e}")
            st.error("Please ensure the 'Graphviz' system library is installed on the server.")


    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
        """

        st.caption(f"You are viewing the **{self.env_id}** environment. This is a read-only dashboard.")

        # Define the tabs
        tab_list = [
            "📊 Readiness & Timeline",
            "📈 Bottleneck Analysis",
            "🛡️ Risk & Compliance",
            "📜 Live Audit Log",
            "🩺 System Integrity & Access",
            "🌐 End-to-End Lineage"
        ]

        tab_dash, tab_bottleneck, tab_risk, tab_audit, tab_integrity, tab_lineage = st.tabs(tab_list)

        with st.spinner("Loading Mission Control Dashboard..."):
            # Render content for each tab
            with tab_dash:
                self._render_dashboard_tab()

            with tab_bottleneck:
                self._render_bottleneck_tab()

            with tab_risk:
                self._render_risk_tab()

            with tab_audit:
                self._render_audit_tab()

            with tab_integrity:
                self._render_integrity_tab()

            with tab_lineage:
                self._render_lineage_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main_app.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
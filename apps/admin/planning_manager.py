"""
apps/admin/planning_manager.py

This is the "Dynamic Backward-Planning Engine" and "Action Tracking"
control panel for the Atlas platform.

This powerful dashboard is built for deadline-driven work. It
understands that projects are planned *backward* from a final
delivery date.

This dashboard's "Project Plan" tab will:
1.  Allow you to set a final **Due Date** for your "root" (final) tasks.
2.  Allow you to define **Duration** (e.g., "5 days") for all other tasks.
3.  Allow you to create a **Dependency Chain** by linking tasks to their
    *successors* (the next task in the chain).
4.  The **Dynamic Engine** will then instantly work *backward* from your
    final deadline, calculating the start and end date for every
    task in the entire project.
"""

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
import graphviz # For the Visual Workflow Planner
from collections import deque # For the re-planning engine

# --- Helper Functions (specific to this dashboard) ---

def _calculate_project_plan(milestones_from_db: list) -> (list, dict):
    """
    This is the "Dynamic Backward-Planning Engine."

    It takes the raw list of milestones and works *backward* from
    the "root" (final) tasks to calculate the true start/end date
    for every task in the dependency chain.

    Returns:
    1. A list of *updated* milestone dicts, now with 'calc_start_date'
       and 'calc_due_date' keys.
    2. A dictionary of calculated KPIs (project_start, project_end, etc.).
    """

    if not milestones_from_db:
        return [], {
            "project_start_date": "N/A",
            "project_end_date": "N/A",
            "total_duration_days": 0,
            "total_tasks": 0,
            "tasks_complete": 0
        }

    tasks = {m['milestone_id']: dict(m) for m in milestones_from_db}

    # Build a REVERSED graph {child_id: [parent_ids...]}
    # This lets us traverse backward from the roots.
    rev_graph = {mid: [] for mid in tasks}
    successor_map = {} # {task_id: successor_id}
    root_tasks = [] # "Root" means "Final Deadline" task (no successor)

    for task_id, task in tasks.items():
        successor_id = task.get('successor_milestone_id')
        if successor_id and successor_id in tasks:
            rev_graph[successor_id].append(task_id)
            successor_map[task_id] = successor_id
        else:
            # This is a "root" (final) task
            root_tasks.append(task_id)

    # Initialize the queue with all root/final tasks
    queue = deque(root_tasks)

    calculated_start_dates = {}
    calculated_end_dates = {}

    # Process tasks in reverse topological order
    while queue:
        task_id = queue.popleft()
        task = tasks[task_id]

        # 1. Get Duration
        duration_days = task.get('duration_days') or 1
        if duration_days < 1: duration_days = 1

        # 2. Determine Due Date
        successor_id = successor_map.get(task_id)
        if successor_id and successor_id in calculated_start_dates:
            # This is a dependent task. It ends the day before its successor starts.
            due_date = calculated_start_dates[successor_id] - timedelta(days=1)
        else:
            # This is a root task. Its due date is static.
            due_date = task.get('due_date')
            if isinstance(due_date, str):
                due_date = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
            if not due_date:
                due_date = datetime.now() # Fallback

        # 3. Determine Start Date (working backward)
        # A 1-day task starts and ends on the same day.
        # A 2-day task (Mon-Tue) starts 1 day before it ends.
        start_date = due_date - timedelta(days=duration_days - 1)

        # 4. Store calculations
        calculated_start_dates[task_id] = start_date
        calculated_end_dates[task_id] = due_date
        task['calc_start_date'] = start_date
        task['calc_due_date'] = due_date

        # 5. Add *predecessors* (parents) to queue
        for parent_id in rev_graph[task_id]:
            # This logic assumes a simple chain.
            # A more complex (DAG) sort would use in-degrees.
            if parent_id not in queue:
                queue.append(parent_id)

    # --- Calculate KPIs ---
    tasks_complete = sum(1 for t in tasks.values() if t['status'] == 'Complete')

    if calculated_start_dates:
        project_start_date = min(calculated_start_dates.values())
        project_end_date = max(calculated_end_dates[tid] for tid in root_tasks if tid in calculated_end_dates)
        total_duration = (project_end_date - project_start_date).days + 1
    else:
        project_end_date = datetime.now()
        project_start_date = datetime.now()
        total_duration = 0

    kpis = {
        "project_start_date": project_start_date.strftime('%Y-%m-%d'),
        "project_end_date": project_end_date.strftime('%Y-%m-%d'),
        "total_duration_days": total_duration,
        "total_tasks": len(tasks),
        "tasks_complete": tasks_complete
    }

    return list(tasks.values()), kpis


# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        self.role = role
        self.default_env_id = environment
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")
        self.all_users = [self.user_id, "jane.smith", "bob.wilson", "alice.jones", "david.c", "helen.k", "tom.h",
                          "carol.d"]  # Placeholder user list

        self.meta = {
            "title_override": "Dynamic Planning Engine",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Atlas Registry DB",
            "coming_soon": False,
        }

        self.milestone_statuses = ["Pending", "Complete"]
        self.action_statuses = ["Open", "Closed"]
        self.refresh_data()

    def refresh_data(self):
        """
        Gets all data needed for the *selectors* in the dashboard.
        """
        try:
            self.all_active_envs = registry_service.get_all_environments()
            self.env_options = {
                env['env_id']: f"{env['env_id']} ({env['env_name']})"
                for env in self.all_active_envs
                if env['current_status'] in ['Active', 'Locked', 'Pending']
            }

            self.all_blueprints = registry_service.get_all_file_blueprints()
            self.blueprint_options = {
                bp['template_id']: f"Blueprint: {bp['template_name']}"
                for bp in self.all_blueprints
            }

        except Exception as e:
            st.error(f"Failed to load registry data: {e}")
            self.all_active_envs = []
            self.env_options = {}
            self.all_blueprints = []
            self.blueprint_options = {}

    def _get_default_index(self):
        """Finds the index of the app's active env to set the selectbox default."""
        if self.default_env_id in self.env_options:
            return list(self.env_options.keys()).index(self.default_env_id)
        elif self.env_options:
             return 0
        return None

    # --- TAB 1: MY OPEN ITEMS ---
    def _render_my_open_items_tab(self):
        """
        UI for the user-centric, cross-environment "To-Do List".
        """
        st.subheader(f"📝 My Open Items ({self.user_id})")
        st.info(
            """
            This is your personal, cross-platform to-do list. **This tab ignores the 
            environment selector** to show you all open milestones and actions
            assigned to *you* from *all* environments.
            """
        )

        try:
            my_milestones_raw = registry_service.get_milestones_by_owner(
                self.user_id,
                status="Pending" # "Pending" means "Not Complete"
            )
            my_actions = registry_service.get_action_items_by_owner(
                self.user_id,
                status="Open"
            )

            # Note: This tab shows static, un-calculated dates.
            # The *true* calculated dates are only visible in the
            # "Dynamic Project Plan" tab for a specific environment.

            my_milestones = sorted(
                my_milestones_raw,
                key=lambda x: x.get('due_date') or '9999-12-31'
            )

        except Exception as e:
            st.error(f"Could not load your open items: {e}")
            return

        cols = st.columns(2)
        cols[0].metric("My Open Milestones", len(my_milestones))
        cols[1].metric("My Open Action Items", len(my_actions))

        st.markdown("---")

        st.markdown("##### My Open Milestones (Project Tasks)")
        if not my_milestones:
            st.success("You have no open milestones assigned to you.")
        else:
            display_data = []
            for ms in my_milestones:
                display_data.append({
                    "Due Date": (ms.get('due_date') or 'N/A').split(' ')[0],
                    "Duration (Days)": ms.get('duration_days', 'N/A'),
                    "Milestone": ms['title'],
                    "Environment": ms['env_id'],
                })
            st.dataframe(
                display_data,
                use_container_width=True,
                column_order=("Due Date", "Duration (Days)", "Milestone", "Environment"),
            )

        st.markdown("##### My Open Action Items (Simple To-Do's)")
        if not my_actions:
            st.success("You have no open action items assigned to you.")
        else:
            display_data = []
            for item in sorted(my_actions, key=lambda x: x['due_date'] or '9999-12-31'):
                display_data.append({
                    "Due": (item.get('due_date') or 'N/A').split(' ')[0],
                    "Action": item['description'],
                    "Environment": item['env_id'],
                    "Created By": item['created_by']
                })
            st.dataframe(
                display_data,
                use_container_width=True,
                column_order=("Due", "Action", "Environment", "Created By"),
            )

    # --- TAB 2: DYNAMIC PROJECT PLAN ---
    def _render_project_plan_tab(self):
        """
        UI for managing the Dynamic Project Plan (Table 9).
        This is the main "engine" tab.
        """
        st.subheader("🚀 Dynamic Backward-Planning Engine")
        st.markdown(
            """
            This is the **environment-centric** project engine. Use the selector
            to load an environment's plan.
            
            The **Project Timeline** is calculated *dynamically* by working
            **backward** from your final deadlines. If you change a task's
            duration, the entire plan will instantly recalculate.
            """
        )

        if not self.env_options:
            st.warning("No 'Active', 'Locked' or 'Pending' environments found.")
            return

        default_idx = self._get_default_index()
        if default_idx is None:
            st.warning("No environments available to select.")
            return

        selected_env_id = st.selectbox(
            "Select an Environment to View/Manage Milestones",
            options=self.env_options.keys(),
            format_func=lambda x: self.env_options.get(x),
            index=default_idx,
            key="milestone_env_select"
        )
        if not selected_env_id:
            return

        st.markdown("---")

        # --- 1. Run the Dynamic Re-planning Engine ---
        milestones_from_db = registry_service.get_milestones_for_env(selected_env_id)

        try:
            calculated_tasks, kpis = _calculate_project_plan(milestones_from_db)
        except Exception as e:
            st.error(f"Error calculating project plan: {e}")
            st.caption("This can be caused by a circular dependency (e.g., Task A feeds Task B, and Task B feeds Task A).")
            return

        # --- 2. Display KPIs ---
        st.markdown(f"##### Project Vitals for `{selected_env_id}`")
        cols = st.columns(4)
        cols[0].metric("Calculated Project Start Date", kpis['project_start_date'])
        cols[1].metric("Final Project Due Date", kpis['project_end_date'])
        cols[2].metric("Total Calculated Duration (Days)", kpis['total_duration_days'])
        cols[3].metric("Tasks Complete", f"{kpis['tasks_complete']} / {kpis['total_tasks']}")

        st.markdown("---")

        # --- 3. Create New Tasks ---
        with st.expander("➕ Create New Project Task"):
            self._render_create_task_form(selected_env_id, milestones_from_db)

        # --- 4. Dynamic Gantt Chart ---
        st.markdown("##### Dynamic Project Timeline")
        st.caption(
            """
            This Gantt chart shows the *true duration* of each task, calculated
            backward from your deadlines. Tasks colored **green** are 'Complete'.
            All other tasks are 'Pending' (light blue) or 'In Progress' (orange)
            if their calculated start date is today or in the past.
            """
        )
        if not calculated_tasks:
            st.info("No project tasks have been set for this environment. Add one above to see the timeline.")
        else:
            self._render_dynamic_gantt(calculated_tasks, selected_env_id)

        # --- 5. Display & Edit Task List ---
        st.markdown("##### Project Task List")
        st.caption(
            """
            This is the full list of all project tasks, sorted by their
            dynamically calculated start date. Mark a task 'Complete' to
            lock in its status.
            """
        )
        if not calculated_tasks:
            st.caption("No tasks found.")
            return

        for task in sorted(calculated_tasks, key=lambda x: x['calc_start_date']):
            with st.container(border=True):

                c1, c2, c3 = st.columns([3, 2, 1])

                # Column 1: Task Title & Status
                c1.markdown(f"**{task['title']}**")
                db_status = task.get('status', 'Pending')
                if db_status == 'Complete':
                    c1.markdown(f"<span style='color:green;'>●</span> **Complete**", unsafe_allow_html=True)
                else:
                    c1.markdown(f"<span style='color:gray;'>●</span> Pending", unsafe_allow_html=True)

                # Column 2: Dates & Owner
                start_str = task['calc_start_date'].strftime('%Y-%m-%d')
                end_str = task['calc_due_date'].strftime('%Y-%m-%d')
                c2.markdown(f"**Owner:** {task['owner_user_id']}")
                c2.markdown(f"**Start:** {start_str} | **Due:** {end_str} | **({task['duration_days']} days)**")

                # Column 3: Actions
                with c3:
                    if db_status == 'Pending':
                        if st.button("Mark Complete", key=f"complete_{task['milestone_id']}", use_container_width=True):
                            with st.spinner("Updating..."):
                                registry_service.update_milestone_status(task['milestone_id'], "Complete", self.user_id)
                            st.success("Task Marked Complete!")
                            st.rerun()

                    if st.button("Delete Task", key=f"delete_{task['milestone_id']}", use_container_width=True, type="secondary"):
                        with st.spinner("Deleting..."):
                            success, msg = registry_service.delete_milestone(task['milestone_id'], self.user_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                                st.rerun()

    def _render_create_task_form(self, selected_env_id, milestones):
        """Internal helper for the 'Create Task' smart form."""

        with st.form("create_task_form"):
            st.markdown("##### Create a New Project Task")
            st.caption(
                """
                Create a task by defining its **Duration** and its **Dependency**.
                The system will automatically calculate its start and end dates.
                """
            )

            c1, c2, c3 = st.columns(3)
            title = c1.text_input("Task Title", "Final Data Review")
            duration = c2.number_input("Duration (Days)", min_value=1, value=3)
            owner = c3.selectbox("Owner", self.all_users, index=0, key="task_owner")

            st.markdown("---")
            st.markdown("##### Set Task Dependency")

            # This is the "smart" part of the form
            dependency_type = st.radio(
                "Is this a final deadline, or does it feed into another task?",
                ["It's a Final Deadline (Root Task)", "It Feeds Into Another Task (Dependent Task)"],
                horizontal=True
            )

            due_date = None
            successor_id = None

            milestone_options = {m['milestone_id']: m['title'] for m in milestones}

            if "Final Deadline" in dependency_type:
                due_date_input = st.date_input("Final Due Date", datetime.now() + timedelta(days=30))
                due_date = datetime.combine(due_date_input, datetime.max.time()).replace(microsecond=0)
            else:
                if not milestone_options:
                    st.warning("You must create a 'Final Deadline' task first to be able to add dependencies.")
                    st.form_submit_button("Create Task", disabled=True)
                    return

                successor_id = st.selectbox(
                    "This Task Feeds Into (Successor Task)",
                    options=milestone_options.keys(),
                    format_func=lambda x: milestone_options[x],
                    key="parent_task"
                )

            st.markdown("---")
            st.markdown("**(Optional) Link Task to a File Blueprint**")

            link = st.selectbox(
                "Link Task to...",
                options=(["NONE"] + list(self.blueprint_options.keys())),
                format_func=lambda x: "No Link" if x == "NONE" else self.blueprint_options[x],
                key="task_link"
            )

            submitted = st.form_submit_button("Create Task")
            if submitted:
                target_table, target_id = None, None
                if link != "NONE":
                    target_table = "bp_file_templates"
                    target_id = link

                with st.spinner("Creating task..."):
                    success, message = registry_service.create_milestone(
                        env_id=selected_env_id, title=title,
                        owner_user_id=owner, user_id=self.user_id,
                        duration_days=duration,
                        due_date=due_date, # Will be NULL if not a root task
                        successor_milestone_id=successor_id, # Will be NULL if a root task
                        target_table=target_table, target_id=target_id
                    )
                    if success:
                        st.success(message); st.rerun()
                    else:
                        st.error(message)


    def _render_dynamic_gantt(self, calculated_tasks, selected_env_id):
        """Internal helper to render the true Dynamic Gantt Chart."""
        chart_data = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for task in calculated_tasks:
            # Determine color
            status = task['status']
            if status == 'Pending':
                if task['calc_due_date'] < today:
                    color = "#D4380D" # Missed
                elif task['calc_start_date'] <= today:
                    color = "#f59e0b" # In Progress
                else:
                    color = "#6b7280" # Pending
            else: # Complete
                color = "#08A045"

            chart_data.append({
                "Task": task['title'],
                "Start": task['calc_start_date'],
                "Finish": task['calc_due_date'],
                "Status": task['status'],
                "Owner": task['owner_user_id'],
                "Color": color
            })

        df = pd.DataFrame(chart_data)

        if not df.empty:

            # --- THIS IS THE ALTAIR BUG FIX ---
            # We define the axis on `x` and only the
            # end-point field on `x2`.

            chart = alt.Chart(df).mark_bar(opacity=0.8).encode(
                x=alt.X('Start', title='Project Timeline', axis=alt.Axis(format="%Y-%m-%d")),
                x2=alt.X2('Finish'), # <-- FIX APPLIED
                y=alt.Y('Task', sort=None, title="Task"),
                color=alt.Color('Color', scale=None), # Use the raw color value
                tooltip=[
                    alt.Tooltip('Task'),
                    alt.Tooltip('Owner'),
                    alt.Tooltip('Start', format="%Y-%m-%d"),
                    alt.Tooltip('Finish', format="%Y-%m-%d"),
                    alt.Tooltip('Status')
                ]
            ).properties(
                title=f"Dynamic Project Plan for {selected_env_id}"
            ).interactive()
            st.altair_chart(chart, use_container_width=True)

    # --- TAB 3: ACTION ITEM TRACKER ---
    def _render_actions_tab(self):
        """UI for managing Action Items (Table 10)."""
        st.subheader("🏃 Action Item Tracker (Simple To-Do's)")
        st.markdown(
            """
            This is the **environment-centric** tracker for "small tasks."
            **These items are simple to-do's and are *not* part of the
            Dynamic Project Plan.** Use this for ad-hoc tasks, meeting notes,
            and follow-ups.
            """
        )

        if not self.env_options:
            st.warning("No 'Active' or 'Locked' environments found.")
            return

        default_idx = self._get_default_index()
        if default_idx is None:
            st.warning("No environments available to select.")
            return

        selected_env_id = st.selectbox(
            "Select an Environment to View/Manage Actions",
            options=self.env_options.keys(),
            format_func=lambda x: self.env_options.get(x),
            index=default_idx,
            key="action_env_select"
        )
        if not selected_env_id:
            return

        st.markdown("---")

        with st.expander("➕ Log New Action Item"):
            self._render_create_action_form(selected_env_id)

        status_filter = st.radio("Filter Status", ["Open", "Closed", "All"], index=0, horizontal=True)
        actions = registry_service.get_action_items(selected_env_id, status=status_filter)

        if not actions:
            st.info(f"No '{status_filter}' action items found for this environment.")
            return

        st.markdown(f"**{len(actions)} '{status_filter}' Actions for `{selected_env_id}`**")

        for item in sorted(actions, key=lambda x: x['due_date'] or '9999-12-31'):
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 2, 1])
                c1.markdown(f"**{item['description']}**")

                due_date_str = "N/A"
                if item.get('due_date'):
                    try:
                        if isinstance(item['due_date'], str):
                            due_date_str = datetime.strptime(item['due_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
                        else:
                            due_date_str = item['due_date'].strftime('%Y-%m-%d')
                    except ValueError:
                         due_date_str = str(item['due_date']).split(' ')[0]

                c2.markdown(f"**Owner:** {item['owner_user_id']} \n\n **Due:** {due_date_str}")

                with c3:
                    render_status_badge(item['status'], type="action")
                    if item['status'] == 'Open':
                        if st.button("Close Action", key=f"close_{item['action_id']}", use_container_width=True):
                            with st.spinner("Closing..."):
                                registry_service.close_action_item(item['action_id'], self.user_id)
                            st.rerun()

    def _render_create_action_form(self, selected_env_id):
        """Internal helper for the 'Create Action' form (with smart links)."""
        with st.form("create_action_form"):
            st.markdown(f"Adding new action item to **{selected_env_id}**")
            description = st.text_area("Action Description", "Confirm inflation assumption with Finance team")
            c1, c2 = st.columns(2)
            owner_user_id = c1.selectbox("Owner", self.all_users, index=0)
            due_date_input = c2.date_input("Due Date (Optional)", None)

            due_date = None
            if due_date_input:
                due_date = datetime.combine(due_date_input, datetime.max.time()).replace(microsecond=0)

            st.markdown("**(Optional) Link to a File or Blueprint**")

            all_files = registry_service.get_all_files_in_environment(selected_env_id, stage=None)
            file_options = {
                (f['file_id'], f['table_name']): f"{f['table_name']}: {f['file_path']}"
                for f in all_files
            }
            link_options = {
                "NONE": "No Link",
                **self.blueprint_options,
                **file_options
            }
            selected_link = st.selectbox(
                "Link Action to...",
                options=link_options.keys(),
                format_func=lambda x: "No Link" if x == "NONE" else (file_options.get(x) or self.blueprint_options.get(x)),
                key="action_link_select"
            )

            submitted = st.form_submit_button("Log Action")
            if submitted:
                target_table, target_id = None, None
                if selected_link != "NONE":
                    if isinstance(selected_link, tuple):
                        target_id, target_table = selected_link
                    else:
                        target_table = "bp_file_templates"
                        target_id = selected_link

                with st.spinner("Logging action..."):
                    success, message = registry_service.create_action_item(
                        env_id=selected_env_id, description=description,
                        owner_user_id=owner_user_id, due_date=due_date,
                        user_id=self.user_id,
                        target_table=target_table, target_id=target_id
                    )
                    if success:
                        st.success(message); st.rerun()
                    else:
                        st.error(message)

    # --- TAB 4: VISUAL WORKFLOW PLANNER ---
    def _render_workflow_planner_tab(self):
        """
        Renders a read-only dependency graph of File Blueprints [T2].
        This shows the *target* workflow, as opposed to the *actual* plan.
        """
        st.subheader("🗺️ Target Workflow (from Blueprints)")
        st.markdown(
            """
            This is a read-only visual map of your **target project workflow**. It is
            generated automatically by reading your **File Blueprints** [T2]
            and their `source_template_id` relationships.
            """
        )
        st.info(
            """
            **How to use this:**
            - This graph shows how your file *types* are connected (e.g., 'Market Data' -> 'Capital Model').
            - Use this as a *reference* to build your **Dynamic Project Plan** in the
              previous tab. It helps you visualize the dependencies you need to create.
            - Milestones linked to blueprints are shown on the nodes.
            """
        )

        if not self.env_options:
            st.warning("No 'Active' or 'Locked' environments found.")
            return

        default_idx = self._get_default_index()
        if default_idx is None:
            st.warning("No environments available to select.")
            return

        selected_env_id = st.selectbox(
            "Select an Environment to View",
            options=self.env_options.keys(),
            format_func=lambda x: self.env_options.get(x),
            index=default_idx,
            key="workflow_env_select"
        )
        if not selected_env_id:
            return

        st.markdown("---")

        try:
            milestones = registry_service.get_milestones_for_env(selected_env_id)
            kpis, updated_milestones = _calculate_project_plan(milestones)
        except Exception as e:
            st.error(f"Could not load planning data: {e}")
            return

        if not self.all_blueprints:
            st.info("No File Blueprints have been created yet. This graph is built from blueprints.")
            return

        # --- Build Graphviz Chart ---
        dot = graphviz.Digraph(comment='Project Workflow')
        dot.attr(rankdir='LR', splines='ortho', ranksep='1.5', nodesep='0.5')
        dot.attr('node', shape='box', style='rounded,filled', fillcolor='white', fontname='Arial')
        dot.attr('edge', fontname='Arial', fontsize='10')

        stages = sorted(list(set(bp['stage'] for bp in self.all_blueprints)))
        for stage in stages:
            with dot.subgraph(name=f"cluster_{stage.replace(' ', '_')}") as c:
                c.attr(label=stage, style='rounded,filled', fillcolor='#F0F2F6', fontname='Arial')

                for bp in [b for b in self.all_blueprints if b['stage'] == stage]:
                    template_id = bp['template_id']

                    # Find milestones linked *to this blueprint type*
                    linked_milestones = [
                        m for m in updated_milestones
                        if m['target_table'] == 'bp_file_templates'
                        and m['target_id'] == template_id
                    ]

                    label = f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='0'><TR><TD><B>{bp['template_name']}</B></TD></TR>"
                    if linked_milestones:
                        label += "<TR><TD><HR/></TD></TR>"
                        for m in linked_milestones:
                            status = m['status']
                            color = "#08A045" if status == 'Complete' else "#6b7280"
                            date_str = m['calc_due_date'].strftime('%Y-%m-%d')
                            label += (
                                f"<TR><TD ALIGN='LEFT' VALIGN='TOP'>"
                                f"<FONT COLOR='{color}'>●</FONT> {m['title']} (Due: {date_str})"
                                "</TD></TR>"
                            )
                    label += "</TABLE>>"

                    dot.node(template_id, label=label)

        # Add blueprint dependencies
        for bp in self.all_blueprints:
            if bp['source_template_id']:
                if bp['source_template_id'] in self.blueprint_options and bp['template_id'] in self.blueprint_options:
                    dot.edge(bp['source_template_id'], bp['template_id'], label="generates")

        st.graphviz_chart(dot, use_container_width=True)

    # --- This is the "recipe" function that gets returned ---
    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        """

        st.markdown(
            """
            <style>
                div[data-testid="stForm"] {
                    border: 1px solid #E0E0E0;
                    border-radius: 10px;
                    padding: 1.5rem;
                }
                div[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
                    border: 1px solid #E0E0E0;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        tab_my_items, tab_plan, tab_actions, tab_workflow = st.tabs(
            [
                "📝 My Open Items",
                "🚀 Dynamic Project Plan",
                "🏃 Action Item Tracker",
                "🗺️ Target Workflow"
            ]
        )

        with tab_my_items:
            self._render_my_open_items_tab()

        with tab_plan:
            self._render_project_plan_tab()

        with tab_actions:
            self._render_actions_tab()

        with tab_workflow:
            self._render_workflow_planner_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main_app.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
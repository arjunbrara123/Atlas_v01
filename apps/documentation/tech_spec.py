"""
apps/documentation/tech_spec.py

This dashboard is the central "user manual" for the Atlas application.
It details the system architecture, data model, environment strategy,
and development processes.

VERSION 6.0 (Major Refactor for 11-Table Model)
- Updated to reflect the 11-TABLE SCHEMA (incl. plan_dependencies).
- [NEW] "Overview" tab is now a LIVE DASHBOARD with real-time KPIs.
- [NEW] Added "System Architecture" tab to explain the 3-Tier model.
- [FIXED] "Data Model" tab now shows the 11-table "many-to-many" diagram
  and a new "Backward-Planning" scenario.
- [FIXED] "Data Dictionaries" tab has a correct [T9] and new [T11].
- [NEW] Added "The Planning Engine" tab for a deep dive on the
  backward-planning, critical path, and firewall logic.
- [ENHANCED] "Environments" tab now includes "Cloning Rules" for
  files and project plans.
- [NEW] Added "Security & Roles" tab with a full Permissions Matrix.
- [ENHANCED] "Add a New Workflow" tab is updated with the "Clone Plan"
  feature.
"""

import streamlit as st
from datetime import datetime
import registry_service  # <-- [NEW] For Live KPIs
import graphviz          # <-- [NEW] For advanced diagrams

# --- Helper function for injecting custom CSS ---

@st.cache_data
def _inject_css():
    """
    Injects custom CSS to make diagrams and content visually appealing.
    """
    st.markdown(
        """
        <style>
        /* Style for Graphviz diagrams to make them "pop" */
        div[data-testid="stGraphVizChart"] > svg {
            background-color: #F8F9FA;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid #E0E0E0;
            width: 100%; /* Make diagrams responsive */
        }
        
        /* Custom "key point" boxes for the overview tab */
        .key-point {
            background-color: #E6F7FF;
            border-left: 5px solid #1890FF;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 15px;
        }
        .key-point strong {
            color: #0056B3;
        }
        
        /* Style for code blocks */
        div[data-testid="stCodeBlock"] {
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        
        /* Ensure tab content has some padding */
        div[data-testid="stTabsBody"] {
            padding-top: 20px;
        }
        
        /* New styles for the Scenario walkthroughs */
        .scenario-box {
            background: #F9F9F9;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            padding: 1.25rem 1.5rem;
            margin-top: 1rem;
        }
        .scenario-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #1890FF;
            margin-bottom: 0.75rem;
        }
        .scenario-body {
            font-size: 0.9rem;
            line-height: 1.6;
        }
        .scenario-body code {
            font-size: 0.85rem;
            background-color: #EFEFEF;
            padding: 2px 5px;
            border-radius: 4px;
        }
        
        /* [NEW] For Security Matrix */
        table.permissions-matrix {
            width: 100%;
            border-collapse: collapse;
        }
        table.permissions-matrix th, table.permissions-matrix td {
            border: 1px solid #E0E0E0;
            padding: 10px;
            text-align: left;
        }
        table.permissions-matrix th {
            background-color: #F8F9FA;
        }
        table.permissions-matrix td {
            text-align: center;
            font-family: monospace;
            font-size: 1.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- Helper for Environment Badge ---
# (This is defined *outside* the class so it can be used by the class)

def _environment_pill(environment: str) -> str:
    """Render an environment badge (pill) with environment-aware colour."""
    env_lower = environment.lower() if environment else ""

    if env_lower.startswith("rep"): # Reporting
        bg = "linear-gradient(90deg,#10b981 0%,#047857 100%)"  # green
        color = "#0b1f18"
    elif env_lower.startswith("prod"): # Production
        bg = "linear-gradient(90deg,#7c3aed 0%,#4c1d95 100%)"  # purple
        color = "#ffffff"
    elif env_lower.startswith("val"): # Validation
        bg = "linear-gradient(90deg,#f59e0b 0%,#b45309 100%)"  # amber
        color = "#1f1302"
    elif env_lower.startswith("dev") or env_lower.startswith("test"): # Dev/Test
        bg = "linear-gradient(90deg,#6b7280 0%,#374151 100%)"  # grey
        color = "#ffffff"
    else:
        bg = "linear-gradient(90deg,#6b7280 0%,#374151 100%)"  # grey
        color = "#ffffff"

    return (
        "<span style='"
        f"background:{bg};" f"color:{color};"
        "display:inline-block; padding:2px 8px; border-radius:6px;"
        "font-size:0.7rem; font-weight:600; line-height:1.4;"
        "box-shadow:0 10px 20px rgba(0,0,0,0.4);"
        "white-space:nowrap;"
        "vertical-align:middle;"
        "'>" f"{environment}" "</span>"
    )

# --- Tab-Specific Rendering Functions ---
# (These are defined as methods *inside* the Page class)

class Page:
    def __init__(self, role: str, environment: str):
        """
        This page is static documentation, so its metadata is simple
        and hard-coded.
        """
        self.role = role
        self.environment = environment # The app's active environment

        self.meta = {
            "title_override": "Technical Specification",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "owner": "Atlas Platform Team",
            "data_source": "System Documentation & Live KPIs",
            "coming_soon": False,
        }

        # [NEW] Load live data for the Overview tab
        self.load_live_data()

    def load_live_data(self):
        """
        [NEW] Makes a live call to the registry_service to get
        high-level KPIs for the overview tab.
        """
        try:
            self.kpis = registry_service.get_system_kpis()
        except Exception as e:
            self.kpis = {}
            st.info(
                f"""
                **Note:** Could not connect to the `registry_service` to load live
                KPIs. Displaying static documentation only.
                
                *Error: {e}*
                """,
                icon="ℹ️"
            )

    def _render_overview_tab(self):
        """
        [ENHANCED] Renders the 'Overview' tab with live KPIs.
        """

        # --- [NEW] Live KPI Metrics ---
        st.subheader("Live Platform Status")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Environments",
                self.kpis.get('bp_environments', 'N/A')
            )
        with col2:
            file_count = (
                self.kpis.get('inst_data_input_files', 0) +
                self.kpis.get('inst_actuarial_model_files', 0) +
                self.kpis.get('inst_result_files', 0) +
                self.kpis.get('inst_report_files', 0)
            )
            st.metric(
                "Total Files Logged",
                f"{file_count:,}" if isinstance(file_count, int) else 'N/A'
            )
        with col3:
            st.metric(
                "Project Tasks Logged",
                self.kpis.get('plan_project_milestones', 'N/A')
            )
        with col4:
            st.metric(
                "Open Action Items",
                # Note: 'pending_actions' is the key from get_system_kpis
                self.kpis.get('pending_actions', 'N/A')
            )

        st.markdown("---")

        st.markdown(
            """
            <div class="key-point">
                <strong>Welcome to the Atlas Platform Specification.</strong>
            </div>
            
            This dashboard is the single source of truth for understanding 
            the design, data, and processes that power the Atlas application.
            
            It is a living document designed to help two core groups:
            
            1.  **Stakeholders & Business Users:** Understand *where data comes from*, 
                *what it means*, and *how to trust it*.
            2.  **Developers, Analysts & Data Teams:** Understand the *governance rules*, 
                *how to build new features*, and *how to get work approved*.
            """,
            unsafe_allow_html=True,
        )

        st.subheader("How to Navigate This Technical Specification Doc")
        st.markdown(
            """
            - **🛡️ Governance Workflow:** The "big picture" of how our platform works,
              explaining the "Doer vs. Reviewer" model.
            - **🏛️ System Architecture:** **(For Developers)** The 3-Tier "Gatekeeper"
              model for building new features.
            - **🗃️ Data Model:** The *most important* tab. A detailed diagram and 
              explanation of the **11 database tables** that run the platform.
            - **📚 Data Dictionaries:** A detailed, column-by-column breakdown
              of all 11 tables.
            - **🚀 The Planning Engine:** A "deep dive" into our powerful
              backward-planning and "Critical Path" logic.
            - **🚦 Environments:** Explains the 4 Environment Types, the "Promotion"
              process, and the rules for *cloning files and plans*.
            - **🔐 Security & Roles:** A "Permissions Matrix" explaining what
              each user role can and cannot do.
            - **➡️ Add a New Workflow:** A non-technical, step-by-step checklist 
              for analysts on how to add a new file or model to the platform.
            """
        )

    def _render_governance_workflow_tab(self):
        """
        Renders the content for the 'Governance Workflow' tab.
        This explains the "Doer vs. Reviewer" concept.
        (This tab's content is still correct and unchanged).
        """
        st.subheader("🛡️ The Atlas Governance Workflow")
        st.markdown(
            """
            This is not an automated system; it is a **user-driven workflow** that 
            ensures every piece of data, model, and result is reviewed and 
            signed-off by the right people. 
    
            This "Separation of Duties" between a **"Doer"** (who creates the file) 
            and a **"Reviewer"** (who approves it) is the core of our audit trail.
            """
        )

        workflow_diagram = """
        digraph {
            rankdir=LR;
            fontname="sans-serif";
            fontsize=12;
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12];
            edge [fontname="sans-serif", fontsize=10];

            // --- 1. The "Doer" (Analyst) ---
            subgraph "cluster_Doer" {
                label = "The 'Doer' (e.g., Analyst, Actuary)";
                style="filled";
                fillcolor="#E6F7FF"; // Light blue
                node [fillcolor="#FFFFFF", stroke="#1890FF"];
                
                Action1 [label="1. User Uploads Data\n(e.g., Business Plan)"];
                Action2 [label="2. User Runs Model\n(e.g., Cold Weather Model)"];
            }

            // --- 2. The "Instance Logs" (The Work) ---
            subgraph "cluster_Logs" {
                label = "File Logs (Tables 3-6)\n(The 'Work-in-Progress')";
                style="filled";
                fillcolor="#F0F0F0";
                node [fillcolor="#FFFFFF", stroke="#555555"];
                
                Log3 [label="📦 inst_data_input_files"];
                Log4 [label="🤖 inst_actuarial_model_files"];
            }

            // --- 3. The "Reviewer" (Manager) ---
            subgraph "cluster_Reviewer" {
                label = "The 'Reviewer' (e.g., Manager, Peer)";
                style="filled";
                fillcolor="#F6FFED"; // Light green
                node [fillcolor="#FFFFFF", stroke="#08A045"];
                
                ActionReview [label="User Reviews Work\n(e.g., 'Does this look right?')"];
                ActionSignOff [label="User Clicks 'Sign Off'\n or 'Reject'"];
                
                ActionReview -> ActionSignOff [style=solid, penwidth=1, color="#333333"];
            }

            // --- 4. The "Audit Trail" ---
            Audit [label="✍️ gov_audit_trail (Table 8)\n(The Central 'Sign-off' Log)", 
                   fillcolor="#FFF7E6", stroke="#D48806", penwidth=2];

            // --- 5. Relationships ---
            edge [style=dashed, penwidth=2];
            Action1 -> Log3 [label=" APPENDS ROW", color="#1890FF"];
            Action2 -> Log4 [label=" APPENDS ROW", color="#1890FF"];
            
            edge [style=dashed, penwidth=1, color="#777777", label="  reads"];
            Log3 -> ActionReview;
            Log4 -> ActionReview;
            
            edge [style=dashed, penwidth=2, color="#08A045", label=" APPENDS ROW"];
            ActionSignOff -> Audit;
        }
        """
        st.graphviz_chart(workflow_diagram)

        # --- [FIXED] Explanation of the Workflow ---
        st.markdown(
            """
            ### The "Doer" vs. "Reviewer" Model
    
            Our entire governance process relies on this "separation of duties" workflow, 
            which is tracked by our database tables.
    
            <div class="scenario-box" style="background: #E6F7FF; border-color: #1890FF;">
                <div class="scenario-title" style="color: #0056B3;">Step 1: The "Doer" (Analyst) Creates Files</div>
                <div class="scenario-body">
                When a user (the "Doer") performs an action like uploading data or 
                running a model, the app:
                <ol>
                    <li>Checks the <b><code>bp_file_templates</code> (Table 2)</b> to 
                        see if the file is a <b>valid type</b> and the user has the 
                        correct <b>`doer_roles`</b>.</li>
                    <li>If all checks pass, it <b>appends a new row</b> to one of the 
                        "File Logs" (Tables 3-6), stamping the file with the Doer's 
                        <code>created_by</code> user ID.</li>
                    <li>This file is now "Pending" and appears in the Doer's "My Pending" inbox.</li>
                </ol>
                </div>
            </div>
    
            <div class="scenario-box" style="background: #F6FFED; border-color: #08A045;">
                <div class="scenario-title" style="color: #047857;">Step 2: The "Reviewer" (Manager) Approves Work</div>
                <div class="scenario-body">
                When a *different* user (the "Reviewer") signs off on that file:
                <ol>
                    <li>The app checks the <b><code>bp_file_templates</code> (Table 2)</b> 
                        to ensure this user has the correct <b>`reviewer_roles`</b>.</li>
                    <li>If they do, their action <b>appends a new row</b> to the 
                        <b><code>gov_audit_trail</code> (Table 8)</b>.</li>
                    <li>This row is a "digital receipt," linking their 
                        <code>user_id</code> to the specific file (e.g., 
                        <code>target_table='inst_data_input_files'</code> and 
                        <code>target_id='1001'</code>).</li>
                </ol>
                </div>
            </div>
    
            <div class="scenario-box" style="background: #F0F2F6; border-color: #555;">
            <div class="scenario-title" style="color: #333;">The Result: A Perfect, Auditable Trail</div>
            <div class="scenario-body">
            The app determines if a file is "Fully Approved" by checking that it has 
            both its "Doer" and "Reviewer" (if required) sign-offs in the 
            <code>gov_audit_trail</code>. This gives us a complete, unchangeable history.
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    def _render_architecture_tab(self):
        """
        [NEW] Renders the "System Architecture" tab (Idea 1).
        This explains the 3-Tier "Gatekeeper" model.
        """
        st.subheader("🏛️ System Architecture (The \"Gatekeeper\" Model)")
        st.markdown(
            """
            This application is built on a **3-Tier Architecture**. This design
            is critical for security, stability, and maintainability. It separates
            the "presentation" (what you see) from the "logic" (the rules)
            and the "data" (the database).
            """
        )

        st.markdown(
            """
            <div class="key-point">
                <strong>The Golden Rule for Developers:</strong>
                <br>
                No UI file (e.g., <code>planning_manager.py</code>) may 
                <em>ever</em> import <code>sqlite3</code> or <code>shutil</code>.
                All business logic, database queries, and file system
                operations <strong>MUST</strong> live in the 
                <code>registry_service.py</code> file.
            </div>
            """,
            unsafe_allow_html=True
        )

        architecture_diagram = """
        digraph {
            rankdir=TB;
            fontname="sans-serif";
            fontsize=12;
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12, width=3];
            edge [fontname="sans-serif", fontsize=10];

            UI [
                label="Tier 1: The 'Dumb' UI\n(e.g., planning_manager.py)",
                fillcolor="#E6F7FF", stroke="#1890FF", height=1.5
            ];
            
            Service [
                label="Tier 2: The 'Smart' Engine (The Gatekeeper)\n(registry_service.py)",
                fillcolor="#F6FFED", stroke="#08A045", penwidth=2, height=1.5
            ];
            
            Data [
                label="Tier 3: The 'Passive' Data Stores\n(atlas_registry.db, File System)",
                fillcolor="#F0F0F0", stroke="#555555", height=1.5
            ];
            
            UI -> Service [
                label=" Makes function calls\n (e.g., create_milestone(...) )",
                penwidth=2, style=dashed
            ];
            
            Service -> Data [
                label=" Executes all SQL & File I/O\n (e.g., INSERT, UPDATE, rmtree)",
                penwidth=2, style=solid
            ];
        }
        """
        st.graphviz_chart(architecture_diagram)

        st.markdown("### The Three Tiers")
        st.markdown(
            """
            1.  **Tier 1: The 'Dumb' UI (The `apps/` folder)**
                * **What it is:** A collection of Streamlit (`.py`) files.
                * **Its Job:** To *only* draw buttons, tabs, and tables. It
                    knows *nothing* about how the database works.
                * **Example:** When you click "Save," the UI's only job is
                    to collect the form data and pass it to the "engine"
                    (e.g., `registry_service.create_milestone(data)`).
            
            2.  **Tier 2: The 'Smart' Engine (The `registry_service.py` file)**
                * **What it is:** A single Python file with all the business
                    logic. This is the **Gatekeeper** and "brain" of the app.
                * **Its Job:** To validate data, enforce security rules, run
                    database transactions, and perform file operations.
                * **Example:** The `create_milestone` function in this file
                    is responsible for running the "Circular Dependency Check"
                    (the firewall), starting a database transaction, `INSERT`ing
                    into `plan_project_milestones` [T9], and `INSERT`ing
                    into `plan_dependencies` [T11], all in one safe operation.
            
            3.  **Tier 3: The 'Passive' Data (The Database & File System)**
                * **What it is:** Our `atlas_registry.db` SQLite file and the
                    physical file server.
                * **Its Job:** To *only* store data. It has no logic of its own
                    (besides what's in the schema, like `ON DELETE CASCADE`).
            
            **Why this matters:** This model makes the app *safe*. We can
            build 50 new UI tabs, and none of them can *ever* corrupt
            the database because they are all forced to go through the one
            central, secure "Gatekeeper" service.
            """
        )


    def _render_data_model_tab(self):
        """
        [FIXED] Renders the 'Data Model' tab.
        This is the full 11-table model, with sections and scenarios.
        """
        # --- 1. The 2-Column Intro ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🗃️ 1. The Atlas Governance Registry")
            st.markdown(
                """
                This is our "single source of truth" for **metadata**.
                
                -   **What it is:** A central database (`atlas_registry.db`).
                -   **What it tracks:** *Who* signed off, *when* data 
                    updated, and *what* its status is.
                -   **Why it matters:** Provides **Trust, Auditability, & Lineage**.
                """
            )
        with col2:
            st.subheader("📂 2. The Environment Data Structure")
            st.markdown(
                """
                This is our "logical folder system" for the **actual files**.
                
                -   **What it is:** A standard set of folders/schemas.
                -   **What it tracks:** *Where* data, models, and results are 
                    physically stored.
                -   **Why it matters:** Provides **Consistency & Reproducibility**.
                """
            )
        st.markdown("---")

        st.subheader("Data Model 1: The Atlas Governance Registry (11-Table Model)")
        st.markdown(
            """
            This is our "single source of truth" for **metadata**. It tracks 
            *who* signed off, *when* data updated, and *what* its status is.
            
            The "Atlas" is comprised of four interconnected sets of
            **eleven (11) tables** that all link together.
            """
        )

        # --- [FIXED] The 11-Table Diagram ---
        conceptual_flow = """
        digraph {
            rankdir=TB;
            fontname="sans-serif";
            fontsize=12; 
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12];
            edge [fontname="sans-serif", fontsize=10];

            subgraph "cluster_Section1" {
                label = "SECTION 1: THE 'BLUEPRINTS'\n(Define What Can Exist)";
                style="filled"; fillcolor="#F0F0F0";
                node [fillcolor="#FFFFFF", stroke="#555555"];
                T1 [label="🌍 bp_environments (Table 1)"];
                T2 [label="📖 bp_file_templates (Table 2)"];
            }

            subgraph "cluster_Section2" {
                label = "SECTION 2: THE 'FILE LOGS'\n(Log What Does Exist)";
                style="filled"; fillcolor="#E6F7FF";
                node [fillcolor="#FFFFFF", stroke="#1890FF"];
                T3 [label="📦 inst_data_input_files (Table 3)"];
                T4 [label="🤖 inst_actuarial_model_files (Table 4)"];
                T5 [label="✅ inst_result_files (Table 5)"];
                T6 [label="📊 inst_report_files (Table 6)"];
                T3 -> T4 -> T5 -> T6 [style=solid, penwidth=2, color="#333333", label="  feeds"];
            }

            subgraph "cluster_Section3" {
                label = "SECTION 3: THE 'GOVERNANCE'\n(Link & Approve Files)";
                style="filled"; fillcolor="#F6FFED";
                node [fillcolor="#FFFFFF", stroke="#08A045"];
                T7 [label="🔗 gov_file_lineage (Table 7)\n(The 'Recipe' - File-to-File)"];
                T8 [label="✍️ gov_audit_trail (Table 8)\n(The 'Ledger' - Human-to-File)"];
            }
            
            subgraph "cluster_Section4" {
                label = "SECTION 4: THE 'PLANNING'\n(Track Deadlines & Dependencies)";
                style="filled"; fillcolor="#FFF7E6";
                node [fillcolor="#FFFFFF", stroke="#D48806"];
                T9 [label="📅 plan_project_milestones (Table 9)\n(The Tasks)"];
                T10 [label="📝 plan_action_items (Table 10)\n(The To-Do's)"];
                T11 [label="🖇️ plan_dependencies (Table 11)\n(The Links)"];
                
                // [NEW] The "Many-to-Many" loop for planning
                T9 -> T11 [label=" has links in", dir=back, style=dashed, penwidth=2, color="#D48806"];
                T11 -> T9 [label=" links tasks in", style=dashed, penwidth=2, color="#D48806"];
            }

            // --- Relationships ---
            edge [style=dotted, penwidth=1, color="#777777"];
            T1 -> T3 [label="hosts"]; T1 -> T4 [label="hosts"]; T1 -> T5 [label="hosts"]; T1 -> T6 [label="hosts"];
            T2 -> T3 [label="defines"]; T2 -> T4 [label="defines"]; T2 -> T5 [label="defines"]; T2 -> T6 [label="defines"];
            T1 -> T9 [label="tracks"]; T1 -> T10 [label="tracks"];
            
            edge [style=dashed, penwidth=2, color="#08A045"];
            T3 -> T8 [label=" is signed-off by"]; T4 -> T8 [label=" is signed-off by"];
            T5 -> T8 [label=" is signed-off by"]; T6 -> T8 [label=" is signed-off by"];
            
            edge [style=dashed, penwidth=2, color="#1890FF"];
            T3 -> T7 [label=" is parent of"]; T4 -> T7 [label=" is child of"];
        }
        """
        st.graphviz_chart(conceptual_flow)
        st.markdown("---")

        # --- 4. The Scenarios ---
        st.subheader("How It All Works: Common Scenarios")
        st.markdown(
            "These examples show how the 11 tables work together in real-time."
        )

        # --- [FIXED] Scenario 1 ---
        st.markdown(
            """
            <div class="scenario-box">
                <div class="scenario-title">Scenario 1: The High-Stakes Manual Upload (Business Plan)</div>
                <div class="scenario-body">
                <b>The Scene:</b> Sarah, an analyst, gets an email from Finance with the final
                <code>Q4_2025_Business_Plan.xlsx</code>. She needs to get this into the 
                <code>Production.Q425_Draft</code> environment.
                <ol>
                    <li><b>(One-Time Setup):</b> An Admin has already created the 
                       <code>Production.Q425_Draft</code> environment in 
                       <b><code>bp_environments</code> (Table 1)</b>.</li>
                    <li><b>Sarah (The "Doer") uploads the file:</b> She navigates to the 
                       "🚢 Data Inputs" -> "Internal Inputs" dashboard, selects the 
                       <code>Production.Q425_Draft</code> environment, and uploads the file.
                        <ul>
                            <li><b>System Check:</b> The app checks the 
                                <b><code>bp_file_templates</code> (Table 2)</b>. 
                               It confirms <code>template_id='biz_plan_q4'</code> exists, 
                               allows the <code>.xlsx</code> extension, and confirms 
                               Sarah's role is in the <code>doer_roles</code> list.</li>
                            <li><b>Table Updated:</b> <code>inst_data_input_files</code> (Table 3)</li>
                            <li><b>How:</b> A new row is <b>APPENDED</b>.</li>
                            <li><b>Example Row:</b> <code>data_file_id=1001</code>, 
                               <code>template_id='biz_plan_q4'</code>, 
                               <code>env_id='Prod.Q425_Draft'</code>, 
                               <code>created_by='sarah.j'</code>.</li>
                        </ul>
                    </li>
                    <li><b>Sarah (The "Doer") signs off:</b> On that same dashboard, she 
                       finds her upload (ID <code>1001</code>) in the "Awaiting Sign-Off" list, 
                       clicks "Sign Off," and adds her comment.
                        <ul>
                            <li><b>Table Updated:</b> <code>gov_audit_trail</code> (Table 8)</li>
                            <li><b>How:</b> A new row is <b>APPENDED</b>.</li>
                            <li><b>Example Row:</b> <code>audit_log_id=5001</code>, <code>user_id='sarah.j'</code>, 
                               <code>action='SIGN_OFF'</code>, <code>target_table='inst_data_input_files'</code>, 
                               <code>target_id='1001'</code>, <code>signoff_capacity='Doer'</code>.</li>
                        </ul>
                    </li>
                    <li><b>David (The "Reviewer") signs off:</b> Sarah pings her manager, David. 
                       David logs in, reviews the file, and adds his "Reviewer" sign-off.
                        <ul>
                            <li><b>Table Updated:</b> <code>gov_audit_trail</code> (Table 8)</li>
                            <li><b>How:</b> A new row is <b>APPENDED</b>.</li>
                            <li><b>Example Row:</b> <code>audit_log_id=5002</code>, <code>user_id='david.c'</code>, 
                               <code>action='SIGN_OFF'</code>, <code>target_table='inst_data_input_files'</code>, 
                               <code>target_id='1001'</code>, <code>signoff_capacity='Reviewer'</code>.</li>
                        </ul>
                    </li>
                    <li><b>Result:</b> The file <code>1001</code> is now "fully blessed" and 
                       can be used by the Actuarial Model run.</li>
                </ol>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- [FIXED] Scenario 2 ---
        st.markdown(
            """
            <div class="scenario-box">
                <div class="scenario-title">Scenario 2: The "Rejection" Workflow (Model Review)</div>
                <div class="scenario-body">
                <b>The Scene:</b> Tom, a Risk Analyst, runs the Cold Weather Model (file 
                <code>2001</code>) and signs it off as the "Doer". He messages 
                his manager, Maria, for the "Reviewer" sign-off.
                <ol>
                    <li><b>Maria (The "Reviewer") REJECTS the file:</b> She reviews file 
                       <code>2001</code> and finds an error.
                        <ul>
                            <li><b>Table Updated:</b> <code>gov_audit_trail</code> (Table 8)</li>
                            <li><b>How:</b> A new row is <b>APPENDED</b>.</li>
                            <li><b>Example Row:</b> <code>audit_log_id=5003</code>, 
                               <code>user_id='maria.v'</code>, <code>action='REJECT'</code>, 
                               <code>target_table='inst_actuarial_model_files'</code>, 
                               <code>target_id='2001'</code>, 
                               <code>comment='Wrong inflation assumption.'</code></li>
                            <li><b>Also:</b> The app runs an <code>UPDATE</code> on 
                                <b><code>inst_actuarial_model_files</code> (Table 4)</b> to set 
                                <code>current_status='Rejected'</code> for file <code>2001</code>.</li>
                        </ul>
                    </li>
                    <li><b>Tom (The "Doer") re-runs the model:</b> Tom sees the comment, fixes 
                       the parameters, and re-runs. This creates a <b>brand new file</b>.
                        <ul>
                            <li><b>Table Updated:</b> <code>inst_actuarial_model_files</code> (Table 4)</li>
                            <li><b>How:</b> A new row is <b>APPENDED</b>.</li>
                            <li><b>Example Row:</b> <code>model_file_id=2002</code>, 
                               <code>env_id='prod'</code>, <code>created_by='tom.h'</code>.</li>
                            <li><b>Also:</b> The app runs an <code>UPDATE</code> on 
                                <b><code>inst_actuarial_model_files</code> (Table 4)</b> to set 
                                <code>current_status='Superseded'</code> for the old file <code>2001</code>.</li>
                        </ul>
                    </li>
                    <li><b>Tom & Maria approve the *new* file:</b> They both sign off on 
                       file <code>2002</code>, creating two new rows (<code>5004</code> and 
                       <code>5005</code>) in the <b><code>gov_audit_trail</code> (Table 8)</b>.</li>
                    <li><b>Result:</b> The app only shows file <code>2002</code> as the "latest 
                       blessed" version. The full audit trail of the rejection is perfectly 
                       preserved.</li>
                </ol>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- [FIXED] Scenario 3/4: The Dynamic Plan ---
        st.markdown(
            """
            <div class="scenario-box">
                <div class="scenario-title">Scenario 3: The Dynamic Backward-Plan (Our New Engine)</div>
                <div class="scenario-body">
                <b>The Scene:</b> A Project Manager needs to plan the Q4 report,
                which is due on **Dec 20th**. The "Final Report" [C] depends on
                both "Data Gathering" [A] and "Model Run" [B].
                <ol>
                    <li><b>The PM creates the "Final Deadline" task:</b>
                        <ul>
                            <li><b>Action:</b> Creates task "Final Report" [C]
                                (1 day duration) with a hard-coded 
                                <b><code>due_date</code></b> of <b>Dec 20</b>.
                            <li><b>Table Updated:</b> <code>plan_project_milestones</code> (Table 9)
                            <li><b>Example Row:</b> <code>milestone_id=101</code>,
                                <code>title='Final Report'</code>, 
                                <code>duration_days=1</code>, <code>due_date='2025-12-20'</code>.</li>
                        </ul>
                    </li>
                    <li><b>The PM creates the "Predecessor" tasks:</b>
                        <ul>
                            <li><b>Action:</b> Creates "Data Gathering" [A] (10 days) and
                                "Model Run" [B] (5 days). For *both* of them, she
                                uses the "This task depends on..." multiselect
                                to choose "Final Report" [C].</li>
                            <li><b>Table Updated (1):</b> <code>plan_project_milestones</code> [T9]
                                receives two new rows for Task A (ID <code>102</code>)
                                and Task B (ID <code>103</code>). Their 
                                <code>due_date</code> is <code>NULL</code>.</li>
                            <li><b>Table Updated (2):</b> <code>plan_dependencies</code> (Table 11)</li>
                            <li><b>How:</b> *Two* new rows are <b>APPENDED</b> to create the links.</li>
                            <li><b>Row 1:</b> <code>task_id=101</code> (Task C), 
                                <code>predecessor_task_id=102</code> (Task A). 
                                (Meaning: "C depends on A")</li>
                            <li><b>Row 2:</b> <code>task_id=101</code> (Task C), 
                                <code>predecessor_task_id=103</code> (Task B).
                                (Meaning: "C depends on B")</li>
                        </ul>
                    </li>
                    <li><b>The "Planning Engine" (in the UI) does the magic:</b>
                        <ul>
                            <li><b>The Logic:</b> The engine finds the root (Task C, due Dec 20).
                                It sees C must start on Dec 20.</li>
                            <li>It tells all of C's predecessors (A and B): "You must
                                both be finished by **Dec 19th**."</li>
                            <li><b>Calculates Task A:</b> 10 days, due Dec 19 ->
                                <b>Calculated Start: Dec 10</b>.</li>
                            <li><b>Calculates Task B:</b> 5 days, due Dec 19 ->
                                <b>Calculated Start: Dec 15</b>.</li>
                        </ul>
                    </li>
                    <li><b>Result:</b> The dashboard displays the "Calculated Project
                       Start Date" as **Dec 10th**. The engine has identified
                       "Data Gathering" [A] as the **Critical Path**.</li>
                </ol>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- [FIXED] Data Model 2 ---
        st.markdown("---")
        st.subheader("Data Model 2: The Environment Data Structure")
        st.markdown(
            """
            This model defines the *logical structure* for how we organize our artifacts 
            (data, files, etc.) within each environment. This standardized "folder" 
            (or schema) structure ensures that our code is reproducible and that 
            we can easily find any asset.
            """
        )

        col1_dm2, col2_dm2 = st.columns([1, 1])

        with col1_dm2:
            # Visual Storytelling: Folder/Schema Structure Flow
            st.markdown("### Data Flow Diagram")
            structure_diagram = """
                digraph {
                    rankdir=TD;
                    node [shape=record, style="filled,rounded", fillcolor="#FFFFFF", fontname="sans-serif", stroke="#333"];
                    edge [fontname="sans-serif"];

                    data [
                        label = "{🚢 Data Inputs |
                            Raw data, views, and final tables. \\l
                            (e.g., fct_sales.csv)
                        }"
                        fillcolor="#FFF7E6"
                    ];

                    models [
                        label = "{🧪 Actuarial Models |
                            Model files. \\l
                            (eg. model_results.xlsx)
                        }"
                        fillcolor="#E6F7FF"
                    ];

                    validations [
                        label = "{🏗️ Results & Validation |
                            Logs from quality checks. \\l
                            (e.g., validation_log.txt)
                        }"
                        fillcolor="#F6FFED"
                    ];

                    reports [
                        label = "{📊 Reports & Insights |
                            Dashboard-ready data. \\l
                            (e.g., cached_summary.parquet)
                        }"
                        fillcolor="#F9F0FF"
                    ];

                    data -> models [label="  is used to train"];
                    models -> validations [label="  is checked by"];
                    data -> reports [label="  is read by"];
                    validations -> reports [label="  is checked by"];
                }
                """
            st.graphviz_chart(structure_diagram)

        with col2_dm2:
            st.markdown("### Practical Benefits")
            st.markdown(
                """
                We maintain an identical, separate copy of this 4-folder 
                structure for **every single environment**.
        
                This "self-contained" design is our superpower for governance:
        
                -   **Easy Testing:** We can test a new model in 
                    `Testing.Q126` using `Testing.Q126` data, with 
                    **zero risk** of breaking the `Production` app.
        
                -   **Simple Audits:** Need to see what happened last quarter? An
                    auditor can be given read-only access to the 
                    `Reporting.Q425.v1` environment, and *all* the data, 
                    models, and results are perfectly locked in one place.
        
                -   **Reliable Cloning:** A user can create a new 
                    `Production` workspace by "cloning" the *Data Inputs* folder from a previous `Reporting` environment, giving 
                    them a clean, blessed starting point for their work.
                """
            )


    def _render_data_dictionaries(self):
        """
        [FIXED] Renders the content for the data dictionaries.
        Now shows 11 tables and a correct [T9].
        """

        # --- 1. The Table Dictionaries ---
        st.subheader("The 11-Table Data Dictionary")
        st.markdown(
            "Below are all **11 tables** that make up the Atlas Registry. "
            "Click on each one to see its detailed schema."
        )

        # --- [FIXED] Section 1 ---
        st.markdown("### Section 1 of 4: The 'Blueprints' (Definition Tables)")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🌍 Table 1: `bp_environments`")
            st.markdown(
                """
                - **What it is:** The master list of all valid environments.
                - **How it's Used:** This is the "parent" table. Everything else
                  (data, models, reports) must belong to one of these environments.
                - **Why it matters:** Lets you know *which version* of the truth you
                  are looking at (e.g., 'Production' vs. 'Reporting').
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `env_id` | 🗝️ **Key**: A *Unique* text identifier ID (short name). | `Rep.Q225` |
                    | `env_name` | The human-friendly text name/folder name. | `Reporting_Q225` |
                    | `env_cat` | Category: `Production`, `Reporting`, `Validation`, `Testing`. | `Reporting` |
                    | `purpose` | A free-text description of the business purpose. | `For Q2 2025 regulatory reporting.` |
                    | `allowed_roles` | 🔒 **Security**: Comma-separated list of roles that can see this. | `admin,risk,exec` |
                    | `current_status` | ⚠️ **(Mutable)** The *workflow state* of this env. | `Locked` |
                    | `source_env_id` | 🔗 **Linked**: The `env_id` this was *cloned from*. | `Prod.Q225_Draft` |
                    | `created_at` | The timestamp of when this *record* was first created. | `2025-05-01 10:30:00` |
                    | `creator_user_id` | The text user ID of the person who first registered this. | `jane.smith` |
                    """
                )

        with col2:
            st.markdown("#### 📖 Table 2: `bp_file_templates`")
            st.markdown(
                """
                - **What it is:** The "master list" or "blueprint" for all *valid file types*.
                - **How it's Used:** Before a file can be uploaded, its *type* must 
                  be defined here. This table stores all the validation rules.
                - **Why it matters:** Guarantees that all data is *standardized*. No 
                  "rogue" or undefined files can break the system.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `template_id` | 🗝️ **Key**: A *Unique* text identifier for the file *type*. | `biz_plan_q4` |
                    | `template_name` | The human-friendly text name for this file type. | `Q4 Business Plan` |
                    | `stage` | The 4-folder data flow step this file belongs to. | `Data Inputs` |
                    | `purpose` | A free-text description of *what this file type is for*. | `Holds the final, approved business plan.` |
                    | `source_template_id` | 🔗 **Linked**: The `template_id` this file *derives from*. | `model_v2_output` |
                    | `data_owner_team`| The name of the team (text) responsible for this data. | `Finance` |
                    | `data_sensitivity`| Category: `Confidential`, `Internal`, `Public`. | `Confidential`|
                    | `source_type` | Category: `Internal`, `External Third Party`, `External Connection`. | `Internal` |
                    | `source_name`| Polymorphic: Team, Vendor, or Domain Key. | `Finance Team` |
                    | `source_specifier`| Polymorphic: Contact, Vendor Contact, or URL Path. | `sarah.j@company.com` |
                    | `creation_method` | The method (text) used to create this file. | `Manual Upload` |
                    | `signoff_workflow`| The *human approval* ruleset (text) for this file. | `Doer + Reviewer` |
                    | `doer_roles` | 🔒 **Security**: Comma-separated list of roles allowed as "Doer". | `admin,finance` |
                    | `reviewer_roles`| 🔒 **Security**: Comma-separated list of roles allowed as "Reviewer". | `admin,finance_manager` |
                    | `expected_extension`| The *expected* file extension (text). | `.xlsx` |
                    | `min_file_size_kb`| The *minimum* valid file size in KB (a number). | `100` |
                    | `max_file_size_kb`| The *maximum* valid file size in KB (a number). | `10240` |
                    | `expected_structure`| A flexible JSON (text) blob of the *expected* structure. | `{"tabs": ["Summary", "Inputs"]}` |
                    | `primary_key_column`| Optional field specifying which column of the first available data table should be used as a primary key. | `Date` |
                    | `template_status` | The current status (text) of *this template*. | `Active` |
                    | `created_at` | The timestamp of when this template was first registered. | `2024-10-01 09:00:00` |
                    | `created_by` | The text user ID of the person who registered this template. | `data.engineer@company.com` |
                    """
                )

        # --- [FIXED] Section 2 ---
        st.markdown("---")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Section 2 of 4: The 'File Logs' (Instance Tables)")

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("#### 📦 Table 3: `inst_data_input_files`")
            st.markdown(
                """
                - **What it is:** A log of all *raw data files* for the 
                  **"🚢 Data Inputs"** stage.
                - **How it's Used:** A user (the "Doer") uploads a file, which 
                  **APPENDS** a new row here.
                - **Why it matters:** This is the 'raw material'. The app's `data_last_updated` 
                  time comes from the `created_at` timestamp of the 
                  *latest signed-off file* from this table.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `data_file_id` | 🗝️ **Key**: A *Unique identifying number* for this file. | `1001` |
                    | `template_id` | 🔗 **Linked**: The text ID from the `file_blueprints` table. | `biz_plan_q4` |
                    | `env_id` | 🔗 **Linked**: The text ID from the `environment_blueprints` table. | `Prod.Q425_Draft` |
                    | `file_path` | The full text path to the actual, physical file. | `Prod.Q425_Draft/Data Inputs/Q4_Business_Plan...` |
                    | `file_hash_sha256` | 💎 **Fingerprint**: A unique hash (text) of the file's contents. | `a1b2c3d4...` |
                    | `file_size_kb` | The *actual* file size in KB (a number) for validation. | `2048` |
                    | `actual_structure` | A flexible JSON (text) blob of the file's *actual* metrics. | `{"tabs": ["Summary", "Inputs"]}` |
                    | `job_status` | The status (text) of the user's upload/creation. | `Upload Succeeded` |
                    | `validation_status` | The automated status (text) from checking the file. | `Passed` |
                    | `validation_summary` | A free-text summary of the validation checks. | `File size and schema OK.` |
                    | `current_status` | ⚠️ **(Mutable)** The *workflow state* (`Active`, `Superseded`, `Rejected`). | `Active` |
                    | `created_at` | The timestamp of when this log row was created. | `2025-05-01 10:45:00` |
                    | `created_by` | The text user ID of the *person* (the "Doer") who uploaded this. | `sarah.j` |
                    """
                )

            st.markdown("#### ✅ Table 5: `inst_result_files`")
            st.markdown(
                """
                - **What it is:** A log of the final, *validated, and aggregated* result files.
                - **How it's Used:** A user runs a "validation" job, which consumes 
                  model files (Table 4) and **APPENDS** a new row here.
                - **Why it matters:** This is the "blessed" set of results *after* all 
                  automated validation checks have passed.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `result_file_id` | 🗝️ **Key**: A *Unique identifying number* for this file. | `3001` |
                    | `template_id` | 🔗 **Linked**: The text ID from the `file_blueprints` table. | `validated_forecast` |
                    | `env_id` | 🔗 **Linked**: The text ID from the `environment_blueprints` table. | `Prod.Q425_Draft` |
                    | `file_path` | The full text path to the actual, physical file. | `Prod.Q425_Draft/Results & Validation/validated...` |
                    | `file_hash_sha256` | 💎 **Fingerprint**: A unique hash (text) of the file's contents. | `i9j0k1l2...` |
                    | `validation_status` | The automated status (text) from the validation. | `Passed` |
                    | `current_status` | ⚠️ **(Mutable)** The *workflow state* of this file. | `Active` |
                    | `created_at` | The timestamp of when this file was created. | `2025-05-10 13:00:00` |
                    | `created_by` | The text user ID of the person (the "Doer") that ran this. | `bi.developer@company.com` |
                    """
                )

        with col4:
            st.markdown("#### 🤖 Table 4: `inst_actuarial_model_files`")
            st.markdown(
                """
                - **What it is:** A log of all files generated *during* a model run 
                  (parameters, intermediate steps, etc.).
                - **How it's Used:** When a user (the "Doer") runs a model, it 
                  **APPENDS** new rows here.
                - **Why it matters:** Provides 100% *reproducibility*. We can link every 
                  calculation *exactly* to its file fingerprint and the code that ran.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `model_file_id` | 🗝️ **Key**: A *Unique identifying number* for this file. | `2001` |
                    | `template_id` | 🔗 **Linked**: The text ID from the `file_blueprints` table. | `cwm_parameters` |
                    | `env_id` | 🔗 **Linked**: The text ID from the `environment_blueprints` table. | `Prod.Q425_Draft` |
                    | `model_run_id` | A text ID to *group* all files from the same model run. | `run_abc_123` |
                    | `file_path` | The full text path to the actual, physical file. | `Prod.Q425_Draft/Actuarial Models/params...` |
                    | `file_hash_sha256` | 💎 **Fingerprint**: A unique hash (text) of the file's contents. | `e5f6g7h8...` |
                    | `current_status` | ⚠️ **(Mutable)** The *workflow state* of this file. | `Active` |
                    | `created_at` | The timestamp of when this file was created. | `2025-05-10 11:20:00` |
                    | `created_by` | The text user ID of the person (the "Doer") that ran this. | `actuary.user@company.com` |
                    """
                )

            st.markdown("#### 📊 Table 6: `inst_report_files`")
            st.markdown(
                """
                - **What it is:** A log of the final, dashboard-ready files. This 
                  is the **last step** in the data flow.
                - **How it's Used:** A user runs a "reporting" job which consumes 
                  result files (Table 5) and **APPENDS** a new row here.
                - **Why it matters:** This is the final, pre-calculated data 
                  that makes the dashboards load *instantly*.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `report_file_id` | 🗝️ **Key**: A *Unique identifying number* for this file. | `4001` |
                    | `template_id` | 🔗 **Linked**: The text ID from the `file_blueprints` table. | `exec_dashboard_data` |
                    | `env_id` | 🔗 **Linked**: The text ID from the `environment_blueprints` table. | `Prod.Q425_Draft` |
                    | `file_path` | The full text path to the actual, physical file. | `Prod.Q425_Draft/Reports & Insights/exec...` |
                    | `file_hash_sha256` | 💎 **Fingerprint**: A unique hash (text) of the file's contents. | `m3n4o5p6...` |
                    | `current_status` | ⚠️ **(Mutable)** The *workflow state* of this file. | `Active` |
                    | `created_at` | The timestamp of when this file was created. | `2025-05-10 14:00:00` |
                    | `created_by` | The text user ID of the person (the "Doer") that ran this. | `bi.developer@company.com` |
                    """
                )

        # --- [FIXED] Section 3 ---
        st.markdown("---")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Section 3 of 4: The 'Governance' (Linking Tables)")

        col7, col8 = st.columns(2)

        with col7:
            st.markdown("#### 🔗 Table 7: `gov_file_lineage`")
            st.markdown(
                """
                - **What it is:** The factual "recipe" book. It's a simple log of 
                  parent-child links.
                - **How it's Used:** When a "Doer" runs a model, the app 
                  **APPENDS** rows here to log *which* input files were used 
                  to create *which* output file.
                - **Why it matters:** This provides full, queryable, end-to-end 
                  lineage. It answers the question, "What *exactly* built this report?"
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `lineage_id` | 🗝️ **Key**: A unique ID for this link. | `7001` |
                    | `parent_table` | The text name of the "parent" (input) file's table. | `inst_data_input_files` |
                    | `parent_id` | 🔗 **Linked**: The ID of the "parent" (input) file. | `1001` |
                    | `child_table` | The text name of the "child" (output) file's table. | `inst_model_files` |
                    | `child_id` | 🔗 **Linked**: The ID of the "child" (output) file. | `2001` |
                    | `created_at` | The timestamp of when this link was logged. | `2025-05-10 11:20:00` |
                    """
                )

        with col8:
            st.markdown("#### ✍️ Table 8: `gov_audit_trail`")
            st.markdown(
                """
                - **What it is:** The **central, append-only AUDIT TRAIL** for all 
                  *human decisions*.
                - **How it's Used:** When a "Reviewer" clicks "Sign Off" or "Reject", 
                  the app **APPENDS** a new row here.
                - **Why it matters:** This is the "receipt" for all human sign-offs. 
                  It's the core of our audit trail and the ultimate **source of trust**.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `audit_log_id` | 🗝️ **Key**: A *Unique identifying number* for this log entry. | `5001` |
                    | `timestamp` | The timestamp of when the action was performed. | `2025-05-10 15:00:00` |
                    | `user_id` | The text user ID of the person who took the action. | `jane.smith` |
                    | `action` | The type of action (text): `SIGN_OFF`, `REJECT`, `REVOKE`, `COMMENT`. | `SIGN_OFF` |
                    | `target_table` | The text name of the table this action applies to. | `inst_result_files` |
                    | `target_id` | The 🔗 **Linked** ID of the *specific row* being signed off. | `3001` |
                    | `signoff_capacity` | The role (text) in which the person was acting. | `Reviewer` |
                    | `comment` | A (mandatory) free-text comment explaining the action. | `Validated results against source models.` |
                    """
                )

        st.markdown("---")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Section 4 of 4: The 'Planning' (Project Management Tables)")

        # --- [FIXED] Section 4: Planning [T9, T10] ---
        col9, col10 = st.columns(2)

        with col9:
            st.markdown("#### 📅 Table 9: `plan_project_milestones`")
            st.markdown(
                """
                - **What it is:** A log of the "big rocks," or individual
                  tasks that make up a project plan.
                - **How it's Used:** A manager uses the "Planning Engine" to
                  create tasks and define their duration and dependencies.
                - **Why it matters:** This table stores the *tasks*. The
                  *links* are stored in Table 11.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `milestone_id` | 🗝️ **Key**: A *Unique identifying number* for this task. | `101` |
                    | `env_id` | 🔗 **Linked**: The environment this task belongs to. | `Prod.Q425_Draft` |
                    | `title` | The text description of the task. | `Final Data Review` |
                    | `duration_days` | The estimated number of days this task will take. | `5` |
                    | `due_date` | **(Nullable)** The *hard-coded* deadline. **Only set for "Final" tasks.** | `2025-12-20 17:00:00` |
                    | `owner_user_id` | The text user ID of the person accountable for this. | `sarah.j` |
                    | `status` | The current status (text): `Pending` or `Complete`. | `Pending` |
                    | `created_at` | The timestamp of when this milestone was created. | `2025-10-01 10:00:00` |
                    | `created_by` | The text user ID of the person who created this. | `admin@company.com` |
                    | `target_table` | (Optional) The *type* of file that proves this is done. | `bp_file_templates` |
                    | `target_id` | (Optional) The ID of the file/blueprint. | `exec_dashboard_data` |
                    """
                )

        with col10:
            st.markdown("#### 📝 Table 10: `plan_action_items`")
            st.markdown(
                """
                - **What it is:** A log of the "small tasks" or ad-hoc actions.
                - **How it's Used:** A user logs a "to-do" and assigns an owner.
                - **Why it matters:** A central, auditable "to-do" list.
                - **Note:** This table is *separate* from the main project plan.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `action_id` | 🗝️ **Key**: A *Unique identifying number* for this action. | `9001` |
                    | `env_id` | 🔗 **Linked**: The environment this action relates to. | `Prod.Q425_Draft` |
                    | `description` | The text description of the task. | `Confirm inflation assumption with Finance` |
                    | `owner_user_id` | The text user ID of the person who must do this. | `bob.w` |
                    | `due_date` | (Optional) The timestamp of when this is due. | `2025-10-03 17:00:00` |
                    | `status` | The current status (text): `Open` or `Closed`. | `Open` |
                    | `created_at` | The timestamp of when this action was created. | `2025-10-02 11:00:00` |
                    | `created_by` | The text user ID of the person who logged this. | `alice.j` |
                    | `target_table` | (Optional) The file or milestone this action relates to. | `file_blueprints` |
                    | `target_id` | (Optional) The ID of the file/milestone. | `cwm_parameters` |
                    """
                )

        # --- [NEW] Table 11 ---
        st.markdown("<br>", unsafe_allow_html=True)
        col11, col12 = st.columns(2)
        with col11:
            st.markdown("#### 🖇️ Table 11: `plan_dependencies`")
            st.markdown(
                """
                - **What it is:** The **new** "linking table" that creates the
                  dependency web for our Planning Engine.
                - **How it's Used:** When a user says "Task C depends on Task A",
                  a new row is added here.
                - **Why it matters:** This allows a task to have *multiple*
                  predecessors, enabling true "Critical Path" planning.
                """
            )
            with st.expander("👇 Expand to see this table's Data Dictionary..."):
                st.markdown(
                    """
                    | Column | Purpose | Example Entry |
                    | :--- | :--- | :--- |
                    | `dependency_id` | 🗝️ **Key**: A unique ID for this link. | `1` |
                    | `task_id` | 🔗 **Linked**: The ID of the *successor* task (e.g., 'Final Report'). | `101` |
                    | `predecessor_task_id` | 🔗 **Linked**: The ID of the *predecessor* task (e.g., 'Data Gathering'). | `102` |
                    """
                )

    def _render_planning_engine_tab(self):
        """
        [NEW] Renders the "Planning Engine" tab (Idea 2).
        This is a deep dive into the backward-planning logic.
        """
        st.subheader("🚀 The Dynamic Planning Engine (A Deep Dive)")
        st.markdown(
            """
            The "Dynamic Project Plan" in the `Planning Manager` is the most
            powerful tool in the Atlas platform. It's not just a to-do list;
            it's a full **Critical Path Method (CPM)** engine that works
            *backward* from your deadlines.
            """
        )

        st.markdown(
            """
            <div class="key-point">
                <strong>The Core Concept: We Plan Backward.</strong>
                <br>
                This engine is designed for reporting cycles. You don't provide
                a "Start Date." You provide a final **"Due Date"** and a
                **"Duration"** for each task. The engine then calculates the
                *true* "Project Start Date" *for* you.
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### 1. The Goal: Why We Plan Backward")
        st.markdown(
            """
            A "Forward-Planning" engine (like MS Project) asks: "If we start on
            Nov 1, when will we finish?" This is useless for a reporting cycle.
            
            Our **Backward-Planning** engine asks: "To finish our report by
            **Dec 20**, when is the absolute *latest* we must start?"
            """
        )

        st.markdown("### 2. The Model: ""Multiple Dependencies"" (The Critical Path)")
        st.markdown(
            """
            Real projects are not a simple `A -> B -> C` chain. Our engine
            is built to handle complex "webs" using two tables:
            
            * **`plan_project_milestones` [T9]:** Stores the tasks (e.g., "Final Review," "5 days").
            * **`plan_dependencies` [T11]:** Stores the *links* (e.g., "Final Review" depends on "Data Gathering").
            
            When the engine calculates dates, it automatically finds the
            **"Critical Path"**—the *longest* chain of dependencies that
            dictates the project's start date.
            """
        )

        critical_path_diagram = """
        digraph {
            rankdir=LR;
            fontname="sans-serif";
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12];
            edge [fontname="sans-serif", fontsize=10];

            subgraph "cluster_Main" {
                label = "Backward-Planning Calculation";
                style="filled"; fillcolor="#F8F9FA";
                
                A [label="Task A: Data Gathering\n(Duration: 10 days)", fillcolor="#FFF7E6", stroke="#D48806", penwidth=2];
                B [label="Task B: Model Run\n(Duration: 5 days)", fillcolor="#FFFFFF", stroke="#555"];
                C [label="Task C: Final Report\n(Due Date: Dec 20)", fillcolor="#F6FFED", stroke="#08A045"];
                
                A -> C [label=" C depends on A"];
                B -> C [label=" C depends on B"];
            }
            
            Start [label="CALCULATED\nProject Start Date:\nDec 10", shape=rarrow, fillcolor="#D4380D", stroke="#D4380D", fontcolor=white];
            Start -> A [label=" This is the 'Critical Path'", style=dashed, color="#D4380D", penwidth=2, fontcolor="#D4380D"];
        }
        """
        st.graphviz_chart(critical_path_diagram)
        st.markdown(
            """
            In this example, **Task C** is due on **Dec 20**.
            1.  The engine works backward. It tells both A and B they must be
                finished by **Dec 19**.
            2.  **Task B (5 days):** Calculates its start date as **Dec 15**.
            3.  **Task A (10 days):** Calculates its start date as **Dec 10**.
            4.  **Result:** The engine correctly identifies **Task A** as the
                "Critical Path" and reports the *true* project start date as
                **Dec 10**.
            """
        )

        st.markdown("### 3. The ""Firewall"": Preventing Circular Dependencies")
        st.markdown(
            """
            The `registry_service` (our "engine") contains a "firewall"
            to protect the plan.
            
            When you try to add a new dependency (e.g., you try to make "Task A"
            depend on "Task C"), the service *first* performs a check.
            It traverses the graph to see if this new link would create
            an impossible `A -> B -> C -> A` loop.
            
            If it does, the save is **blocked** and an error is shown,
            making it impossible to corrupt the project plan.
            """
        )

    def _render_environments_tab(self):
        """
        [ENHANCED] Renders the 'Environments' tab.
        Now includes the new "Cloning & Provisioning" rules.
        """
        # --- [FIXED] Section 1 ---
        st.subheader("What is an Environment?")
        st.markdown(
            """
            Think of an environment as a **self-contained "parallel universe"**. Each
            environment has its *own* identical set of the four data folders,
            but the *files* inside them are completely separate.
            
            This is our most important control: it means we can
            work on a draft `Production` report without *any*
            risk of breaking the "live" `Reporting` environment.
            """
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("##### The 4-Folder Structure")
            st.markdown(
                "Every single environment (e.g., `Prod.Q425_Draft`, `Rep.Q425.v1`)"
                "contains its own instance of this 4-folder structure. The"
                "`atlas_registry.db`(our 11 tables) tracks which files are in"
                "which folder, in which environment."
            )

            # We re-use the excellent diagram from the Data Model tab
            structure_diagram = """
                digraph {
                    rankdir=TD;
                    node [shape=record, style="filled,rounded", fillcolor="#FFFFFF", fontname="sans-serif", stroke="#333"];
                    edge [fontname="sans-serif"];

                    data [label = "{📦 Data Inputs}", fillcolor="#FFF7E6"];
                    models [label = "{🤖 Actuarial Models}", fillcolor="#E6F7FF"];
                    validations [label = "{✅ Results & Validation}", fillcolor="#F6FFED"];
                    reports [label = "{📊 Reports & Insights}", fillcolor="#F9F0FF"];
                    data -> models; models -> validations; validations -> reports;
                }
                """
            st.graphviz_chart(structure_diagram)

        with col2:
            st.markdown(
                """
                <div class="scenario-box" style="background: #F0F2F6; border-color: #555; margin-top: 3.5rem;">
                <div class="scenario-title" style="color: #333;">The Golden Rule:</div>
                <div class="scenario-body">
                The environment you select in the sidebar dictates which "parallel 
                universe" you are looking at.
                
                <ul>
                <li>If you are in <code>Reporting.Q425.v1</code>, you are seeing 
                    the <b>final, locked, signed-off</b> Q4 2025 files.</li>
                <li>If you are in <code>Production.Q425_Draft</code>, you are seeing 
                    the <b>un-reviewed, in-progress</b> files for that same report.</li>
                </ul>
                
                Always check your environment pill in the header!
                </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # --- [FIXED] Section 2 ---
        st.markdown("---")
        st.subheader("The Four Environment Categories")
        st.markdown(
            "Every environment you create must be one of these four types. "
            "Each has a different purpose and level of governance."
        )

        colA, colB = st.columns(2)

        with colA:
            st.markdown(
                """
                <div class="scenario-box" style="background: #F9F0FF; border-color: #7c3aed;">
                    <div class="scenario-title" style="color: #4c1d95;">Production (The "Workspace")</div>
                    <div class="scenario-body">
                    <ul>
                        <li><b>What it is:</b> The main "draft" environment where analysts
                            and actuaries build their numbers for an upcoming report.</li>
                        <li><b>Key Purpose:</b> Running models, uploading data, and
                            getting "Doer" sign-offs.</li>
                        <li><b>Example:</b> <code>Prod.Q425_Draft</code></li>
                    </ul>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(
                """
                <div class="scenario-box" style="background: #FFF7E6; border-color: #f59e0b;">
                    <div class="scenario-title" style="color: #b45309;">Validation (The "Sandbox")</div>
                    <div class="scenario-body">
                    <ul>
                        <li><b>What it is:</b> A *clone* of a <code>Production</code> or 
                            <code>Reporting</code> environment.</li>
                        <li><b>Key Purpose:</b> Used by auditors or peer reviewers to 
                            freely investigate, test, and validate work *without*
                            any risk of changing the original.</li>
                        <li><b>Example:</b> <code>Val.Q425_Audit</code></li>
                    </ul>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with colB:
            st.markdown(
                """
                <div class="scenario-box" style="background: #F6FFED; border-color: #08A045;">
                    <div class="scenario-title" style="color: #047857;">Reporting (The "Snapshot")</div>
                    <div class="scenario-body">
                    <ul>
                        <li><b>What it is:</b> A *locked, immutable* environment that 
                            represents the final, "blessed" truth for a given period.</li>
                        <li><b>Key Purpose:</b> Powers the dashboards for senior
                            leadership. This is the <b>final source of truth</b>.</li>
                        <li><b>Example:</b> <code>Rep.Q425.v1</code></li>
                    </ul>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(
                """
                <div class="scenario-box" style="background: #F0F2F6; border-color: #6b7280;">
                    <div class="scenario-title" style="color: #374151;">Testing (The "UAT")</div>
                    <div class="scenario-body">
                    <ul>
                        <li><b>What it is:</b> An environment for *business users*
                            to test new platform *features* (e.g., "Does this new 
                            upload button work?").</li>
                        <li><b>Key Purpose:</b> User Acceptance Testing (UAT) of the
                            app, not the data.</li>
                        <li><b>Example:</b> <code>Test.v2_Upgrade</code></li>
                    </ul>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("*(Note: A `Development` environment also exists, but is used only by the platform development team.)*")

        # --- [FIXED] Section 3 ---
        st.markdown("---")
        st.subheader("The Promotion Path: How a 'Draft' Becomes 'Official'")
        st.markdown(
            """
            This is a **user-driven workflow** to make a "draft" report official. 
            It moves from a flexible `Production` workspace to a locked `Reporting` 
            snapshot, with a `Validation` loop for review.
            """
        )

        promotion_diagram = """
        digraph {
            rankdir=LR;
            fontname="sans-serif";
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12];
            edge [fontname="sans-serif", fontsize=10];

            Prod [label="🟣 Production\n(Workspace)\n'Prod.Q425_Draft'", fillcolor="#F9F0FF", stroke="#7c3aed"];
            Validate [label="🟠 Validation\n(Sandbox)\n'Val.Q425_Audit'", fillcolor="#FFF7E6", stroke="#f59e0b"];
            Report [label="🟢 Reporting\n(Locked Snapshot)\n'Rep.Q425.v1'", fillcolor="#F6FFED", stroke="#08A045", penwidth=2];
            
            edge [style=solid, penwidth=2, color="#333333"];
            Prod -> Report [label=" User Action:\n'Promote to Reporting' "];
            
            // The "Validation/Audit" loop
            edge [style=dashed, penwidth=1, color="#333333"];
            Prod -> Validate [label=" User Action:\n'Clone for Validation' "];
        }
        """
        st.graphviz_chart( promotion_diagram )

        st.markdown(
            """
            1.  **Start in `Production`:** An analyst creates `Prod.Q425_Draft` 
                and begins uploading data and running models.
            2.  **Internal Review:** All work (data, models, results) is signed off
                by a "Doer" and "Reviewer" *inside* that `Production` environment.
            3.  **(Optional) `Validation`:** An auditor can `Clone for Validation` to
                create `Val.Q425_Audit`. They can do their own checks here without
                disturbing the main workflow.
            4.  **Final "Go Live":** Once all sign-offs are complete, a manager takes 
                the user action to `"Promote to Reporting"`. This clones the *entire* `Prod.Q425_Draft` environment into a *new, locked, read-only* environment called `Rep.Q425.v1`.
            5.  **Done:** Leadership now views the `Rep.Q425.v1` environment as the
                single source of truth. If a restatement is needed, the process
                is repeated to create `Rep.Q425.v2`.
            """
        )

        # --- [NEW] Section 4: Cloning Rules ---
        st.markdown("---")
        st.subheader("Cloning & Provisioning Rules")
        st.markdown(
            """
            Cloning is a core feature of the `Environment Manager`. We have
            two different types of cloning: cloning **Files** and cloning
            **Project Plans**.
            """
        )

        colRule1, colRule2 = st.columns(2)

        with colRule1:
            st.markdown("#### 1. Cloning *Files*")
            st.markdown(
                """
                When you "Clone an existing environment," the UI gives you
                options for how to copy the *files*. This is critical
                for governance.
                """
            )
            st.markdown(
                """
                | Logic Name | What It Copies | Use Case |
                | :--- | :--- | :--- |
                | **Latest Approved** | Copies *only* files that are `Active` AND `Fully Signed-Off`. | **Promoting to `Reporting`**. Creates a "Clean Snapshot" of only the blessed files. |
                | **Full History** | Copies `Active` and `Rejected` files, but *skips* `Superseded` files. | **Developer `Testing`**. Gives a clean view of current and failed work, without old versions. |
                | **Carbon Copy (Forensic)** | Copies *every single file* (`Active`, `Rejected`, `Superseded`) AND their *entire* audit trail [T8]. | **`Validation` / Audit**. Creates a perfect, bit-for-bit copy for auditors. |
                """
            )

        with colRule2:
            st.markdown("#### 2. Cloning *Project Plans*")
            st.markdown(
                """
                This is a separate, optional feature in the `Create Workspace`
                tab. It allows a new project to be "provisioned" with a
                standard plan.
                """
            )
            st.markdown(
                """
                <div class="scenario-box">
                <div class="scenario-title">How Plan Cloning Works</div>
                <div class="scenario-body">
                <ol>
                    <li>You select "Clone Plan from <code>Prod.Q425</code>".</li>
                    <li>The service queries all tasks [T9] and links [T11]
                        from `Prod.Q425`.</li>
                    <li>It creates **brand new** tasks and links, re-maps
                        all the IDs, and saves them to your *new* environment.</li>
                </ol>
                <br>
                <strong>This is a 100% SAFE COPY.</strong> The new plan is
                completely independent. You can delete or edit the old
                plan with zero risk of breaking the new one.
                </div>
                </div>
                """,
                unsafe_allow_html=True
            )


    def _render_security_tab(self):
        """
        [NEW] Renders the "Security & Roles" tab (Idea 3).
        This shows the master Permissions Matrix.
        """
        st.subheader("🔐 Security & Roles (Permissions Matrix)")
        st.markdown(
            """
            This matrix defines what each user role can do. Access is
            controlled by the "Role" assigned to a user (e.g., `admin`,
            `risk`) and enforced by the "Rules" set in the
            `environment_blueprints` [T1] and `file_blueprints` [T2].
            """
        )

        st.markdown(
            """
            <table class="permissions-matrix">
                <thead>
                    <tr>
                        <th>Role</th>
                        <th>Description</th>
                        <th>Can Manage<br>Environments?</th>
                        <th>Can Manage<br>File Blueprints?</th>
                        <th>Can Manage<br>Project Plans?</th>
                        <th>Can Prune<br>Files?</th>
                        <th>Can Sign-Off<br>as "Doer"?</th>
                        <th>Can Sign-Off<br>as "Reviewer"?</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>admin</strong></td>
                        <td>Platform Administrators. Have god-mode.</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>✅</td>
                    </tr>
                    <tr>
                        <td><strong>developer</strong></td>
                        <td>Data Engineers / Platform Devs.</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>❌</td>
                        <td>✅</td>
                        <td>✅</td>
                    </tr>
                    <tr>
                        <td><strong>exec</strong></td>
                        <td>Senior Leadership (e.g., CRO, CFO).</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>❌</td>
                    </tr>
                    <tr>
                        <td><strong>risk</strong></td>
                        <td>Managers / Governors (e.g., Risk, Finance).</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>✅</td>
                        <td>❌</td>
                        <td>✅</td>
                        <td>✅</td>
                    </tr>
                    <tr>
                        <td><strong>commercial</strong></td>
                        <td>Analysts / Actuaries (The "Doers").</td>
                        <td>❌</td>
                        <td>❌</td>
                        <td>✅</td>
                        <td>❌</td>
                        <td>✅</td>
                        <td>❌</td>
                    </tr>
                </tbody>
            </table>
            <br>
            <p>
            <strong>Note on Sign-Offs:</strong> A "Doer" or "Reviewer"
            can only sign off on a file if their role (e.g., `risk`) is
            <em>also</em> in that specific file's `doer_roles` or
            `reviewer_roles` list in <b><code>bp_file_templates</code> [T2]</b>.
            </p>
            """,
            unsafe_allow_html=True
        )


    def _render_add_workflow_tab(self):
        """
        [ENHANCED] Renders the 'Add a New Workflow' tab.
        Now includes the "Clone Plan" step.
        """
        st.subheader("🚀 How to Add a New Workflow")
        st.markdown(
            """
            Adding a new report or data flow to Atlas is a governed, 
            multi-step process. It's designed to be safe and auditable, 
            not fast. Here is the non-technical checklist.
            """
        )

        st.markdown(
            """
            <div class="scenario-box" style="background: #F0F0F0; border-color: #999;">
            <div class="scenario-title" style="color: #333;">Step 1: Define the "Blueprint" (Admin Task)</div>
            <div class="scenario-body">
            You cannot upload a "rogue" file. The platform must first 
            be <b>taught</b> what your new files are.
            
            <ol>
            <li>Contact a <b>Platform Admin</b> (e.g., the Atlas Team).</li>
            <li>In the sidebar, open up <b>`🗃️ Admin Panel`</b> -> 
                <b>`📖 File Blueprint Manager`</b>.</li>
            <li>The Admin will work with you to create a new blueprint 
                for each new file in your workflow (e.g., a new 
                <code>template_id</code> for your input data, your model, 
                and your final report).</li>
            <li>They will set the <b>rules</b>, like `Expected Extension`, 
                `Sign-off Workflow`, and the `Doer/Reviewer Roles`.</li>
            </ol>
            </div>
            </div>
            
            <div class="scenario-box" style="background: #E6F7FF; border-color: #1890FF;">
            <div class="scenario-title" style="color: #0056B3;">Step 2: Create your "Workspace" (User Task)</div>
            <div class="scenario-body">
            You need a "parallel universe" to do your work in.
            
            <ol>
            <li>In the sidebar, open up <b>`🗃️ Admin Panel`</b> -> 
                <b>`🚦 Environment Manager`</b> ->
                <b>`➕ Create Workspace`</b>.</li>
            <li>Select <b>"Create new empty environment"</b> (or clone files
                from a previous run if needed).</li>
            <li>Set the <b>Category</b> to `Production` (your draft workspace).</li>
            <li>Set the <b>Name Suffix</b> (e.g., `NewModel_Draft_v1`).</li>
            <li>
                <b>[NEW]</b> In the "<b>Clone Project Plan</b>" section,
                select your "golden standard" plan (e.g., `Prod.Q425_Template`)
                to automatically populate your new environment with all its tasks.
            </li>
            <li>Click <b>Create</b>. Your new environment 
                (e.g., `Prod.NewModel_Draft_v1`) will now 
                appear in your sidebar, fully equipped with its project plan.</li>
            </ol>
            </div>
            </div>

            <div class="scenario-box" style="background: #F6FFED; border-color: #08A045;">
            <div class="scenario-title" style="color: #047857;">Step 3: Follow the "Doer/Reviewer" Workflow</div>
            <div class="scenario-body">
            Now you can start your work <b>inside</b> your new environment.
            
            <ol>
            <li>Go to the <b>`🚢 Data Inputs`</b> dashboard (or other workspaces).</li>
            <li>Select your new environment (`Prod.NewModel_Draft_v1`).</li>
            <li>Upload your raw data, run your models, and sign them off as "Doer".</li>
            <li>Ask your Manager to log in and <b>Sign Off</b> as "Reviewer".</li>
            <li>As you complete file sign-offs, link them to your tasks
                in the <b>`🚀 Dynamic Planning Engine`</b>.</li>
            </ol>
            </div>
            </div>
            
            <div class="scenario-box" style="background: #F0F2F6; border-color: #555;">
            <div class="scenario-title" style="color: #333;">Step 4: Promote to "Reporting" (Manager Task)</div>
            <div class="scenario-body">
            Once your entire workflow is "green" (all steps are signed-off 
            and all project tasks are "Complete"), a manager can make it "live".
            
            <ol>
            <li>In the sidebar, open up <b>`🗃️ Admin Panel`</b> -> 
                <b>`🚦 Environment Manager`</b> ->
                <b>`🚀 Promote & Validate`</b>.</li>
            <li>Select your `Prod.NewModel_Draft_v1` environment.</li>
            <li>Fill out the form to create the new `Reporting` snapshot
                (e.g., `Rep.NewModel.v1`).</li>
            <li>Click <b>Promote</b>.</li>
            <li><b>Done.</b> The new report is now live and locked in its 
                own `Reporting` environment for executives to see.</li>
            </ol>
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    # --- This is the "recipe" function that gets returned ---

    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It injects CSS and renders the tabs.
        It must accept role and environment.
        """

        # Inject all custom CSS
        _inject_css()

        # Define the tabs. This is the first UI element.
        tabs = st.tabs([
            "📖 Overview",
            "🛡️ Governance",
            "🏛️ System Model",
            "🗃️ Data Model",
            "📚 Data Dictionaries",
            "🚀 Planning Engine",
            "🚦 Env Management",
            "🔐 Security & Roles",
            "➡️ Add New Workflow",
        ])

        # Render content for each tab
        with tabs[0]:
            self._render_overview_tab()

        with tabs[1]:
            self._render_governance_workflow_tab()

        with tabs[2]:
            self._render_architecture_tab()

        with tabs[3]:
            self._render_data_model_tab()

        with tabs[4]:
            self._render_data_dictionaries()

        with tabs[5]:
            self._render_planning_engine_tab()

        with tabs[6]:
            self._render_environments_tab()

        with tabs[7]:
            self._render_security_tab()

        with tabs[8]:
            self._render_add_workflow_tab()


# --- The Public Function (Required by main.py) ---

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.

    1. It creates an instance of the Page (running __init__ to get meta
       and load live KPIs).
    2. It returns the "recipe" (page.render_body) and the dynamic meta.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
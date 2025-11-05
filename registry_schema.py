"""
Atlas Governance Registry Schema (10-Table Master Blueprint)

===============================================================================
PURPOSE:
===============================================================================
This file is the "Master Blueprint" for the entire Atlas governance
database (the `atlas_registry.db` SQLite file).

It is designed to be run ONCE from the command line to create the empty,
pristine 10-table database.

$ python registry_schema.py

It is safe to re-run. It contains no application logic, only the `CREATE TABLE`
and `CREATE INDEX` statements, and it will only create tables and indexes
that do not already exist.

===============================================================================
QUICK NAVIGATION / TABLE OF CONTENTS
===============================================================================
Use your editor's search function (Ctrl+F) to find these tags:

[S1]  SECTION 1: THE "BLUEPRINTS" (The Catalogs)
[T1]    - bp_environments:      The "Project" catalog
[T2]    - bp_file_templates:    The "Data" catalog (rules for files)

[S2]  SECTION 2: THE "FILE LOGS" (The Instances)
[T3]    - inst_data_input_files:      Log of "Data Input" files
[T4]    - inst_actuarial_model_files: Log of "Model" files
[T5]    - inst_result_files:          Log of "Result" files
[T6]    - inst_report_files:          Log of "Report" files

[S3]  SECTION 3: THE "GOVERNANCE" (The Connections)
[T7]    - gov_file_lineage:     The "Recipe" (file-to-file links)
[T8]    - gov_audit_trail:      The "Sign-off Sheet" (human-to-file links)

[S4]  SECTION 4: THE "PLANNING" (The Future)
[T9]    - plan_project_milestones:  The "Big Deadlines"
[T10]   - plan_action_items:        The "To-Do List"
[T11]   - plan_dependencies:        The "Dependency Links"

[S5]  SECTION 5: THE "INDEXES" (Performance)
[I1] - [I10] Indexes to make the database fast

[INIT]  initialize_database(): The main function that runs everything

===============================================================================
THE 4-SECTION MODEL (THE "STORY"):
===============================================================================
The 10 tables are organized into four distinct conceptual groups that tell
the "story" of our data governance process.

1. SECTION 1: THE "BLUEPRINTS" (2 Definition Tables) [S1]
   - These are our "catalogs." They define WHAT *can* exist.
   - (e.g., "We can have a 'Production' environment called 'Q4 2025'.")
   - (e.g., "We can have a file type called 'business_plan' that must be an .xlsx.")
   

2. SECTION 2: THE "FILE LOGS" (4 Instance Tables) [S2]
   - These are our append-only "logs" of *files*. They record WHAT *does* exist.
   - (e.g., "Sarah.j created file 'Q4_Plan_v1.xlsx' in the 'Q4 2025' env.")
   - This section maps 1-to-1 with the 4 folders in an environment.
   

3. SECTION 3: THE "GOVERNANCE" (2 Linking Tables) [S3]
   - These are the "paperwork" tables that govern the files.
   - `file_lineage`: Logs the factual "Recipe" (WHAT files were used to make this?).
   - `audit_trail`: Logs the human "Sign-off" (WHO approved this file?).
   

4. SECTION 4: THE "PLANNING" (2 Project Management Tables) [S4]
   - These tables track the *future*: deadlines, tasks, and actions.
   - `project_milestones`: Logs the "big rocks" (e.g., "Data Inputs Due").
   - `action_items`: Logs the "small tasks" (e.g., "Follow up with Finance").
   [Image of a project Gantt chart]

(We also have a Section 5 for Indexes, which just makes this all run fast!)

-------------------------------------------------------------------------------
"""

import sqlite3
import sys

# The name of the database file that will be created
DB_FILE = "atlas_registry.db"


# --- [S1] SECTION 1: THE "BLUEPRINTS" (DEFINITION TABLES) ---

# --- [T1] bp_environments (The "Project" Catalog) -----------------
# PURPOSE: Defines a single project or 'environment' (e.g., "Q4 2025 Prod").
#          This is the top-level "folder" for all work.
# EXAMPLE: ('q4_2025_prod', 'Q4 2025 Production', 'Production', 'Annual run...', ...)
# LINKS:   - This is the "parent" for almost everything.
#          - All files [T3-T6] and tasks [T9-T10] *must* belong to one environment.
# ------------------------------------------------------------------
CREATE_ENV_BLUEPRINTS = """
CREATE TABLE IF NOT EXISTS bp_environments (
    env_id TEXT PRIMARY KEY,
    env_name TEXT NOT NULL UNIQUE,
    env_cat TEXT NOT NULL,
    purpose TEXT,
    allowed_roles TEXT DEFAULT 'all',
    current_status TEXT DEFAULT 'Pending',
    source_env_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    creator_user_id TEXT,
    
    FOREIGN KEY (source_env_id) REFERENCES bp_environments (env_id)
);
"""

# --- [T2] bp_file_templates (The "Data" Catalog) -------------------
# PURPOSE: Defines the rules for a *type* of file (e.g., "Finance Plan").
#          It specifies owners, sensitivity, and validation rules.
# EXAMPLE: ('fin_plan_q4', 'Q4 Finance Plan', 'Input', 'Finance team data', ...)
# LINKS:   - Every file in the logs [T3-T6] *must* point to one of these templates.
# ------------------------------------------------------------------
CREATE_FILE_BLUEPRINTS = """
CREATE TABLE IF NOT EXISTS bp_file_templates (
    template_id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL UNIQUE,
    stage TEXT NOT NULL,
    purpose TEXT,
    source_template_id TEXT,
    
    -- Governance
    data_owner_team TEXT,
    data_sensitivity TEXT,
    template_status TEXT DEFAULT 'Active',
    
    -- Source
    -- The master switch: 'Internal', 'External Third Party', 'External Connection'
    source_type TEXT,
    -- This column is "polymorphic" (it stores 3 different things):
    -- 1. For 'Internal': The Internal Team Name (e.g., "Finance")
    -- 2. For 'External Third Party': The Vendor Name (e.g., "Aon")
    -- 3. For 'External Connection': The Whitelisted Domain Key (e.g., "MET_OFFICE")
    source_name TEXT,
    -- This column is also "polymorphic":
    -- 1. For 'Internal': The Contact Person (e.g., "sarah.j@company.com")
    -- 2. For 'External Third Party': The Vendor Contact (e.g., "john.doe@aon.com")
    -- 3. For 'External Connection': The URL Path/Endpoint (e.g., "/pub/data/weather/latest.txt")
    source_specifier TEXT,
    
    -- Process Rules
    creation_method TEXT,
    signoff_workflow TEXT,
    doer_roles TEXT DEFAULT 'admin',
    reviewer_roles TEXT DEFAULT 'admin',

    -- Validation Rules
    expected_extension TEXT,
    min_file_size_kb INTEGER,
    max_file_size_kb INTEGER,
    expected_structure TEXT,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    FOREIGN KEY (source_template_id) REFERENCES bp_file_templates (template_id)
);
"""

# --- [S2] SECTION 2: THE "FILE LOGS" (INSTANCE TABLES) ---

# --- [T3] inst_data_input_files ------------------------------------
# PURPOSE: Logs every "Data Input" file that has been uploaded or created.
# EXAMPLE: (1, 'fin_plan_q4', 'q4_2025_prod', '/files/q4_2025_prod/data_inputs/plan.xlsx', ...)
# LINKS:   - Points to [T1] bp_environments (which project it's in).
#          - Points to [T2] bp_file_templates (what *kind* of file it is).
# ------------------------------------------------------------------
CREATE_DATA_FILES = """
CREATE TABLE IF NOT EXISTS inst_data_input_files (
    data_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    
    -- File Identity & Validation
    file_path TEXT NOT NULL UNIQUE,
    file_hash_sha256 TEXT NOT NULL,
    file_size_kb INTEGER,
    actual_structure TEXT,
    
    -- Status
    job_status TEXT,
    validation_status TEXT,
    validation_summary TEXT,
    current_status TEXT DEFAULT 'Active',

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    FOREIGN KEY (template_id) REFERENCES bp_file_templates(template_id),
    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [T4] inst_actuarial_model_files -------------------------------
# PURPOSE: Logs every "Actuarial Model" file (e.g., a script, a .zip).
# EXAMPLE: (1, 'model_v2', 'q4_2025_prod', 'run_abc_123', '/files/.../model.zip', ...)
# LINKS:   - Points to [T1] bp_environments.
#          - Points to [T2] bp_file_templates.
# ------------------------------------------------------------------
CREATE_MODEL_FILES = """
CREATE TABLE IF NOT EXISTS inst_actuarial_model_files (
    model_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    model_run_id TEXT NOT NULL,
    
    -- File Identity
    file_path TEXT NOT NULL UNIQUE,
    file_hash_sha256 TEXT NOT NULL,
    
    -- Status
    current_status TEXT DEFAULT 'Active',
    
    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    FOREIGN KEY (template_id) REFERENCES bp_file_templates(template_id),
    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [T5] inst_result_files ----------------------------------------
# PURPOSE: Logs every "Result" file generated by a model.
# EXAMPLE: (1, 'raw_results', 'q4_2025_prod', '/files/.../results.csv', ...)
# LINKS:   - Points to [T1] bp_environments.
#          - Points to [T2] bp_file_templates.
# ------------------------------------------------------------------
CREATE_RESULT_FILES = """
CREATE TABLE IF NOT EXISTS inst_result_files (
    result_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    
    -- File Identity
    file_path TEXT NOT NULL UNIQUE,
    file_hash_sha256 TEXT NOT NULL,

    -- Status
    validation_status TEXT,
    current_status TEXT DEFAULT 'Active',

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    FOREIGN KEY (template_id) REFERENCES bp_file_templates(template_id),
    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [T6] inst_report_files ----------------------------------------
# PURPOSE: Logs every final "Report" or "Insight" file.
# EXAMPLE: (1, 'final_summary', 'q4_2025_prod', '/files/.../summary.pdf', ...)
# LINKS:   - Points to [T1] bp_environments.
#          - Points to [T2] bp_file_templates.
# ------------------------------------------------------------------
CREATE_REPORT_FILES = """
CREATE TABLE IF NOT EXISTS inst_report_files (
    report_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    
    -- File Identity
    file_path TEXT NOT NULL UNIQUE,
    file_hash_sha256 TEXT NOT NULL,
    
    -- Status
    current_status TEXT DEFAULT 'Active',
    
    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    FOREIGN KEY (template_id) REFERENCES bp_file_templates(template_id),
    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [S3] SECTION 3: THE "GOVERNANCE" (LINKING TABLES) ---

# --- [T7] gov_file_lineage (The "Recipe" Log) ----------------------
# PURPOSE: Creates the "recipe" of how files are made. It links
#          "parent" files (inputs) to "child" files (outputs).
# EXAMPLE: (1, 'inst_data_input_files', '1', 'inst_result_files', '1')
#          This means: "Data file #1 was used to create Result file #1"
# LINKS:   - This is a "polymorphic" table. It can link ANY file in
#          - [T3-T6] to any other file in [T3-T6].
#          - We use TEXT for IDs to be consistent with [T8].
# ------------------------------------------------------------------
CREATE_FILE_LINEAGE = """
CREATE TABLE IF NOT EXISTS gov_file_lineage (
    lineage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- The "Parent" file (the input)
    parent_table TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    
    -- The "Child" file (the output that was made)
    child_table TEXT NOT NULL,
    child_id TEXT NOT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# --- [T8] gov_audit_trail (The "Sign-off Sheet") -------------------
# PURPOSE: The single, central log of all human actions, such as
#          "sign-off," "validate," "comment," or "approve."
# EXAMPLE: (1, '2025-10-01', 'sarah.j', 'Approve', 'inst_report_files', '1', ...)
#          This means: "Sarah J. approved Report File #1"
# LINKS:   - This is "polymorphic." It can point to ANY record in ANY table.
#          - e.g., Target can be a file [T3-T6], a project [T1], or a task [T9].
# ------------------------------------------------------------------
CREATE_AUDIT_TRAIL = """
CREATE TABLE IF NOT EXISTS gov_audit_trail (
    audit_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    
    -- The "Polymorphic" link to ANY other table
    target_table TEXT NOT NULL,
    target_id TEXT NOT NULL, -- TEXT to link to env_id, template_id, or int file_ids
    
    -- Context
    signoff_capacity TEXT,
    comment TEXT
);
"""

# --- [S4] SECTION 4: THE "PLANNING" (PROJECT MANAGEMENT TABLES) ---

# --- [T9] plan_project_milestones (The "Big Deadlines") ------------
# PURPOSE: Tracks the "big rocks" or key deadlines for a project.
# EXAMPLE: (1, 'q4_2025_prod', 'All Data Inputs Due', '2025-11-01', 'david.k', ...)
# LINKS:   - Must point to one environment [T1].
#          - Can optionally point to a target file (e.g., the final report [T6]).
# ------------------------------------------------------------------
CREATE_PROJECT_MILESTONES = """
CREATE TABLE IF NOT EXISTS plan_project_milestones (
    milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id TEXT NOT NULL,
    title TEXT NOT NULL,

    -- DURATION: How long this task takes (e.g., "5" days)
    duration_days INTEGER DEFAULT 1,

    -- DEADLINE: (Nullable) Only set for "Final Deadline" tasks.
    -- All other task due dates will be calculated by the engine.
    due_date DATETIME,

    owner_user_id TEXT,
    status TEXT DEFAULT 'Pending', -- Pending, Complete

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,

    -- Link to the final deliverable (e.g., a specific report file)
    target_table TEXT,
    target_id TEXT,

    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [T10] plan_action_items (The "To-Do List") --------------------
# PURPOSE: Tracks "small tasks" or ad-hoc to-do items.
# EXAMPLE: (1, 'q4_2025_prod', 'Follow up with Finance on plan.xlsx', 'sarah.j', ...)
# LINKS:   - Must point to one environment [T1].
#          - Can optionally point to a specific file [T3-T6] or milestone [T9].
# ------------------------------------------------------------------
CREATE_ACTION_ITEMS = """
CREATE TABLE IF NOT EXISTS plan_action_items (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    due_date DATETIME,
    status TEXT DEFAULT 'Open', -- Open, Closed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    
    -- Link to a specific file or milestone if needed
    target_table TEXT,
    target_id TEXT,
    
    FOREIGN KEY (env_id) REFERENCES bp_environments(env_id)
);
"""

# --- [T11] plan_dependencies (The "Dependency Links") -------------
# PURPOSE: This is the "linking table" that creates the dependency web.
#          It allows a task to have MULTIPLE predecessors.
# EXAMPLE: (1, 12, 10)  <- "Task 12 depends on Task 10"
#          (2, 12, 11)  <- "Task 12 also depends on Task 11"
# LINKS:   - Points to [T9] for the task itself.
#          - Points to [T9] for the task's predecessor.
# ------------------------------------------------------------------
CREATE_DEPENDENCIES = """
CREATE TABLE IF NOT EXISTS plan_dependencies (
    dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- The "successor" task (e.g., Task C)
    task_id INTEGER NOT NULL, 

    -- The "predecessor" task (e.g., Task A)
    -- This is the task that must be done *before* task_id
    predecessor_task_id INTEGER NOT NULL,

    -- This ensures that all links are deleted if a task is deleted
    FOREIGN KEY (task_id) 
        REFERENCES plan_project_milestones(milestone_id) 
        ON DELETE CASCADE,
    FOREIGN KEY (predecessor_task_id) 
        REFERENCES plan_project_milestones(milestone_id) 
        ON DELETE CASCADE,

    -- Ensures the same dependency link can't be entered twice
    UNIQUE(task_id, predecessor_task_id)
);
"""

# --- [S5] SECTION 5: THE "INDEXES" (PERFORMANCE) ---
# PURPOSE: These statements don't create new data, but they make
#          searching for data *much* faster. They are like the
#          index in the back of a book.

# [I1] Index for all file logs [T3-T6] by environment
CREATE_IDX_FILES_BY_ENV = """
CREATE INDEX IF NOT EXISTS idx_files_by_env
ON {} (env_id);
"""

# [I2] Index for all file logs [T3-T6] by template
CREATE_IDX_FILES_BY_TEMPLATE = """
CREATE INDEX IF NOT EXISTS idx_files_by_template
ON {} (template_id);
"""

# [I3] Index for file lineage [T7] by parent file
CREATE_IDX_LINEAGE_BY_PARENT = """
CREATE INDEX IF NOT EXISTS idx_lineage_by_parent
ON gov_file_lineage (parent_table, parent_id);
"""

# [I4] Index for file lineage [T7] by child file
CREATE_IDX_LINEAGE_BY_CHILD = """
CREATE INDEX IF NOT EXISTS idx_lineage_by_child
ON gov_file_lineage (child_table, child_id);
"""

# [I5] Index for audit trail [T8] by target (for finding all actions on one item)
CREATE_IDX_AUDIT_BY_TARGET = """
CREATE INDEX IF NOT EXISTS idx_audit_by_target
ON gov_audit_trail (target_table, target_id);
"""

# [I6] Index for audit trail [T8] by user (for finding all actions by one person)
CREATE_IDX_AUDIT_BY_USER = """
CREATE INDEX IF NOT EXISTS idx_audit_by_user
ON gov_audit_trail (user_id);
"""

# [I7] Index for milestones [T9] by environment
CREATE_IDX_MILESTONES_BY_ENV = """
CREATE INDEX IF NOT EXISTS idx_milestones_by_env
ON plan_project_milestones (env_id);
"""

# [I8] Index for action items [T10] by environment
CREATE_IDX_ACTIONS_BY_ENV = """
CREATE INDEX IF NOT EXISTS idx_actions_by_env
ON plan_action_items (env_id);
"""

# [I9] Index for action items [T10] by owner
CREATE_IDX_ACTIONS_BY_OWNER = """
CREATE INDEX IF NOT EXISTS idx_actions_by_owner
ON plan_action_items (owner_user_id);
"""

# [I10] Index for model files [T4] by model_run_id
CREATE_IDX_MODELS_BY_RUN_ID = """
CREATE INDEX IF NOT EXISTS idx_models_by_run_id
ON inst_actuarial_model_files (model_run_id);
"""

# [I11] Index for dependencies [T11] by task (Find all predecessors FOR a task)
CREATE_IDX_DEPS_BY_TASK = """
CREATE INDEX IF NOT EXISTS idx_deps_by_task
ON plan_dependencies (task_id);
"""

# [I12] Index for dependencies [T11] by predecessor (Find all tasks that DEPEND ON a task)
CREATE_IDX_DEPS_BY_PREDECESSOR = """
CREATE INDEX IF NOT EXISTS idx_deps_by_predecessor
ON plan_dependencies (predecessor_task_id);
"""

# --- [INIT] Main Initializer Function ---

def initialize_database():
    """
    Connects to the SQLite database file and executes all
    CREATE TABLE and CREATE INDEX statements in a single, safe transaction.

    Run this file ONCE from your terminal:
    $ python registry_schema.py
    """
    conn = None
    try:
        print(f"Connecting to database file: {DB_FILE}...")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # --- CRITICAL ---
        # Enable Foreign Key support in SQLite (it's OFF by default)
        c.execute("PRAGMA foreign_keys = ON;")

        print("Initializing database...")
        print("  - SECTION 1: Blueprints")
        c.execute(CREATE_ENV_BLUEPRINTS)
        c.execute(CREATE_FILE_BLUEPRINTS)

        print("  - SECTION 2: Instance File Logs")
        c.execute(CREATE_DATA_FILES)
        c.execute(CREATE_MODEL_FILES)
        c.execute(CREATE_RESULT_FILES)
        c.execute(CREATE_REPORT_FILES)

        print("  - SECTION 3: Governance")
        c.execute(CREATE_FILE_LINEAGE)
        c.execute(CREATE_AUDIT_TRAIL)

        print("  - SECTION 4: Planning")
        c.execute(CREATE_PROJECT_MILESTONES)
        c.execute(CREATE_ACTION_ITEMS)
        c.execute(CREATE_DEPENDENCIES)
        
        print(f"... 11 tables created (if they didn't exist).")

        print("  - SECTION 5: Indexes (for performance)")
        
        # [I1] & [I2] on all four file tables
        file_tables = [
            'inst_data_input_files', 
            'inst_actuarial_model_files', 
            'inst_result_files', 
            'inst_report_files'
        ]
        for table in file_tables:
            c.execute(CREATE_IDX_FILES_BY_ENV.format(table))
            c.execute(CREATE_IDX_FILES_BY_TEMPLATE.format(table))
        
        # [I3] - [I10]
        c.execute(CREATE_IDX_LINEAGE_BY_PARENT)
        c.execute(CREATE_IDX_LINEAGE_BY_CHILD)
        c.execute(CREATE_IDX_AUDIT_BY_TARGET)
        c.execute(CREATE_IDX_AUDIT_BY_USER)
        c.execute(CREATE_IDX_MILESTONES_BY_ENV)
        c.execute(CREATE_IDX_ACTIONS_BY_ENV)
        c.execute(CREATE_IDX_ACTIONS_BY_OWNER)
        c.execute(CREATE_IDX_MODELS_BY_RUN_ID)
        c.execute(CREATE_IDX_DEPS_BY_TASK)
        c.execute(CREATE_IDX_DEPS_BY_PREDECESSOR)

        print(f"... 12 indexes created (if they didn't exist).")

        # Commit all changes at once
        conn.commit()

        print("\n-------------------------------------------------")
        print(f"SUCCESS: Database '{DB_FILE}' is initialized and ready.")
        print("-------------------------------------------------")

    except sqlite3.Error as e:
        print("\n!!! --- SQL ERROR --- !!!")
        print(f"An error occurred: {e}")
        print("Rolling back all changes.")
        if conn:
            conn.rollback()
        sys.exit(1) # Exit with an error code
    except Exception as e:
        print(f"\n!!! --- UNEXPECTED ERROR --- !!!")
        print(f"An error occurred: {e}")
        print("Rolling back all changes.")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    # This block allows you to run this file directly from the terminal
    initialize_database()
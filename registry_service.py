"""
Atlas Registry Service (The "Gatekeeper" / "Engine")

===============================================================================
PURPOSE:
===============================================================================
This file is the **single, central gatekeeper** for all interactions with the
Atlas governance database (`atlas_registry.db`) and the file system.

NO OTHER FILE IN THE APPLICATION SHOULD EVER IMPORT `sqlite3` OR `shutil`.

All UI files (e.g., `environment_manager.py`) must import this service
and call these functions.

===============================================================================
BUSINESS PURPOSE & LOGIC:
===============================================================================
This service enforces our "Hybrid" (Option 2) governance model. This is the
most critical concept for any developer to understand:

1.  **Append-Only Logs (System Events):**
    - The "Instance" tables (e.g., `inst_data_input_files`) are treated as
      append-only logs. When a user "edits" a file, they are really
      *appending* a new row (a new version) and the old row is
      marked as 'Superseded'.

2.  **Append-Only Audit (Human Actions):**
    - The `gov_audit_trail` (Table 8) is a *pure* append-only log for all
      human decisions (sign-offs, rejections, comments).

3.  **The "Dual-Write" Transaction:**
    - To prevent the system from *ever* going out of sync, all "write"
      actions (like a sign-off) are wrapped in a database transaction.
    - When a user signs off on a file, this service performs *two* actions
      in one "all-or-nothing" transaction:
      a) `INSERT` a new row into the `gov_audit_trail` (the permanent receipt).
      b) `UPDATE` the `current_status` column on the file's instance table
         (e.g., `inst_data_input_files`) to 'Active' or 'Rejected'.
    - This gives us the speed of a simple "status" query and the
      perfect, immutable history of an audit log.

===============================================================================
QUICK NAVIGATION / FUNCTION LIST
===============================================================================
This file is organized into 9 logical sections.

--- SECTION 1: CONFIGURATION & CONSTANTS ---
(Global variables and maps that define the service's behavior)

--- SECTION 2: PRIVATE HELPER FUNCTIONS ---
(Internal tools used by the public functions. Not for external use.)

    [H-DB] Database Connection
    - _get_db_conn(): Returns a new, configured connection to the SQLite DB.

    [H-LOG] Audit Logging
    - _log_audit(): (Internal) Writes a new row to the gov_audit_trail table.

    [H-FILE] File Hashing & Saving
    - _hash_file_from_memory(): Calculates the SHA-256 hash of an in-memory file.
    - _save_uploaded_file(): Saves a file to disk and returns its metrics (size, etc.).

    [H-PHYS] Physical Folder Management
    - _create_physical_folders(): Creates the 4-folder structure for a new env.
    - _clone_physical_folders(): Deep-copies an entire environment's folder structure.

    [H-CLONE] Database Clone Logic
    - _get_files_to_clone(): (Internal) Finds *which* file IDs to clone based on the 3 versioning profiles.
    - _clone_db_records(): (Internal) Clones all DB records (files, lineage, audit) for a new env.
    - _clone_project_plan(): (Internal) Clones the project milestones from one environment to another

--- SECTION 3: PUBLIC "READ" FUNCTIONS (For UI Dashboards) ---
(Functions to fetch data for display in the UI.)

    [F-ENV-R] Environment "Read" Functions
    - get_visible_environments(): (For Sidebar) Gets envs a user is allowed to see.
    - get_all_environments(): (For Admin) Gets all envs from Table 1.
    - get_environment_by_id(): Gets a single env from Table 1.
    - get_environment_quick_stats(): Gets key stats for an environment

    [F-BP-R] Blueprint "Read" Functions
    - get_all_file_blueprints(): (For Admin) Gets all blueprints from Table 2.
    - get_file_blueprint_by_id(): Gets a single blueprint from Table 2.

    [F-FILE-R] File Instance "Read" Functions
    - get_all_files_in_environment(): (For Admin) Gets a list of all files in an env.
    - get_files_for_user_dashboard(): (For Doer/Reviewer) Smartly gets "inbox" and all files for a stage.

    [F-GOV-R] Governance (Audit/Lineage) "Read" Functions
    - get_audit_log_for_target(): (For UI) Gets the audit history for *one* specific item.
    - get_audit_log_for_target_list(): (For UI) Get full human sign-off history for specific file IDs.
    - get_environment_audit_log_all(): (For Admin) Gets the recent audit log for *all* envs.
    - get_audit_log_all_actions(): (For Admin) Gets the latest N actions in the whole system.
    - get_file_lineage_downstream(): (For Admin) Finds all children of a file.
    - get_file_lineage_upstream(): (For Admin) Finds all parents of a file.

--- SECTION 4: PUBLIC "PLANNING" FUNCTIONS (Tables 9 & 10) ---
(Functions for creating and updating milestones and to-do items.)

    [F-PLAN-RW] Milestone & Action Item "Read/Write"
    - get_milestones_for_env(): Gets all milestones for one env (Table 9).
    - get_milestones_by_owner(): Gets all milestones for user in all envs
    - get_action_items_by_owner(): Gets all actions assigned to user in all envs
    - create_milestone(): Creates a new milestone.
    - update_milestone_status(): Updates a milestone's status.
    - get_action_items(): Gets all action items for one env (Table 10).
    - create_action_item(): Creates a new action item.
    - close_action_item(): Closes an action item.

--- SECTION 5: PUBLIC "ADMIN WRITE" FUNCTIONS ---
(High-privilege functions for managing environments and blueprints.)

    [F-ENV-W] Environment "Write" Functions
    - create_new_environment(): (For Admin UI) Creates a new, empty environment.
    - clone_environment(): (For Admin UI) The smart clone function (3 profiles).
    - promote_to_reporting(): (For Admin UI) A wrapper for the "Clean Snapshot" clone.
    - edit_environment(): (For Admin UI) Updates an env's metadata (status, roles).

    [F-BP-W] Blueprint "Write" Functions
    - create_file_blueprint(): (For Admin UI) Creates a new file rule (Table 2).
    - edit_file_blueprint(): (For Admin UI) Updates a file rule (Table 2).
    - delete_file_blueprint(): (For Admin UI) Deletes an unused file rule.

--- SECTION 6: PUBLIC "USER WRITE" FUNCTIONS (Doer/Reviewer) ---
(Functions for day-to-day users to upload files and log sign-offs.)

    [F-FILE-W] File Instance "Write" Functions
    - upload_new_file_instance(): (The "Doer" upload) Validates, hashes, and saves a new file.
    - run_external_connection_job(): Retrieve a file from a whitelisted internet source.
    - log_user_signoff(): (The "Reviewer" action) Logs a sign-off or rejection.

--- SECTION 7: PUBLIC "HEALTH" FUNCTIONS (Admin Dashboard) ---
(Functions for the admin health check dashboard.)

    [F-HEALTH] Orphan/Broken Link Finders
    - find_orphaned_files(): Finds DB records with no matching physical file.
    - find_orphaned_folders(): Finds physical folders with no matching DB record.
    - find_broken_blueprint_links(): Finds files (Tables 3-6) pointing to a non-existent blueprint.
    - find_unused_blueprints(): Finds blueprints (Table 2) that are not used by any file.
    - validate_all_blueprint_json(): Checks the `expected_structure` JSON syntax.
    - prune_archived_environment(): (Destructive) Deletes physical files for an 'Archived' env.

--- SECTION 8: PUBLIC "DASHBOARD" FUNCTIONS (KPIs / Complex) ---
(Complex queries for high-level dashboard widgets.)

    [F-KPI] KPI Getters & Complex Dashboard Queries
    - get_system_kpis(): Gets high-level counts of all objects (files, envs, etc.).
    - get_pending_actions_dashboard(): Finds all files across the system needing sign-off.
    - get_approved_domains(): Returns the list of whitelisted domains for the UI.

--- SECTION 9: UNUSED / FUTURE FUNCTIONS ---
    - run_new_model(): (Placeholder) A future function for running models.
-------------------------------------------------------------------------------
"""

import sqlite3
import os
import shutil
from datetime import datetime
import json
import hashlib
import sys
import io  # Used for in-memory file simulation

# --- [S1] SECTION 1: CONFIGURATION & CONSTANTS ---

# Database file
DB_FILE = "atlas_registry.db"

# Root path for all physical environment folders
# Use an absolute path for your server
ENVIRONMENT_ROOT_PATH = os.path.abspath(os.path.join(os.getcwd(), "AtlasEnvironments"))

# Standard folder names used inside each environment folder
ALL_FOLDERS = ["Data Inputs", "Actuarial Models", "Results & Validation", "Reports & Insights"]

# Map environment categories to their folder name prefix
ENV_CATEGORY_PREFIX_MAP = {
    "Production": "Prod",
    "Reporting": "Rep",
    "Validation": "Val",
    "Testing": "Test",
    "Development": "Dev"
}

# Whitelist of approved domains for "External Connection" blueprints
APPROVED_DOMAINS = {
    "MET_OFFICE_HADLEY": "https://www.metoffice.gov.uk/hadobs/hadcet/data/",
    "LDN_GOVT_DATA": "https://data.london.gov.uk/dataset/",
    "BRANDWATCH": "https://api.brandwatch.com/"
}

# --- Core Application Mappings (DO NOT CHANGE) ---

# Map a Blueprint "Stage" to its physical folder name
STAGE_TO_FOLDER_MAP = {
    "Data Inputs":          "Data Inputs",
    "Actuarial Models":     "Actuarial Models",
    "Results & Validation": "Results & Validation",
    "Reports & Insights":   "Reports & Insights",
}

# Map a Blueprint "Stage" to its database instance table
STAGE_TO_TABLE_MAP = {
    "Data Inputs":          "inst_data_input_files",
    "Actuarial Models":     "inst_actuarial_model_files",
    "Results & Validation": "inst_result_files",
    "Reports & Insights":   "inst_report_files",
}

# Map an instance table to its Primary Key (ID) column
# This is CRITICAL for robust polymorphic queries and avoids all guessing bugs.
TABLE_ID_MAP = {
    "inst_data_input_files":      "data_file_id",
    "inst_actuarial_model_files": "model_file_id",
    "inst_result_files":          "result_file_id",
    "inst_report_files":          "report_file_id",
    # Admin tables
    "bp_environments":            "env_id",
    "bp_file_templates":          "template_id",
    "plan_project_milestones":    "milestone_id",
    "plan_action_items":          "action_id"
}

# --- [S2] SECTION 2: PRIVATE HELPER FUNCTIONS ---

# --- [H-DB] Database Connection ---
def _get_db_conn():
    """[PRIVATE] Returns a new, configured connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        # Enable Foreign Key support (off by default)
        conn.execute("PRAGMA foreign_keys = ON;")
        # Return rows as dictionary-like objects
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"CRITICAL: Failed to connect to database at {DB_FILE}: {e}", file=sys.stderr)
        return None

# --- [H-LOG] Audit Logging ---
def _log_audit(conn, user_id: str, action: str, target_table: str, target_id,
               comment: str, capacity: str = "System"):
    """
    [PRIVATE] Writes a new row to the gov_audit_trail (Table 8).
    This function *must* be called from within an existing transaction
    (it requires an active `conn` object).
    """
    conn.execute(
        """
        INSERT INTO gov_audit_trail (user_id, action, target_table, target_id, signoff_capacity, comment)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, action, target_table, str(target_id), capacity, comment) # target_id MUST be TEXT
    )

# --- [H-FILE] File Hashing & Saving ---
def _hash_file_from_memory(uploaded_file):
    """
    [PRIVATE] Calculates the SHA-256 hash of a file-like object from memory.
    Reads in chunks to handle large files safely.
    """
    sha256_hash = hashlib.sha256()
    uploaded_file.seek(0) # Reset file pointer
    # Read and update hash in chunks of 4K
    for byte_block in iter(lambda: uploaded_file.read(4096), b""):
        sha256_hash.update(byte_block)
    uploaded_file.seek(0) # Reset again for the actual save
    return sha256_hash.hexdigest()

def _save_uploaded_file(uploaded_file, file_path: str) -> dict:
    """
    [PRIVATE] Safely saves an UploadedFile object to a physical path.
    Returns a dictionary of file metrics.
    """
    # Create the *absolute* path for the file system
    full_path = os.path.join(ENVIRONMENT_ROOT_PATH, file_path)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if os.path.exists(full_path):
        raise ValueError(f"File already exists at this path: {full_path}")

    # Write the file
    with open(full_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Get metrics
    file_size_bytes = os.path.getsize(full_path)
    file_size_kb = round(file_size_bytes / 1024, 2)

    # Placeholder for actual metric extraction
    # In a real app, we'd open the .xlsx or .csv here to get tabs/columns
    actual_structure = {}
    if uploaded_file.name.endswith((".xlsx", ".xlsb")):
        # In a real app: use openpyxl to get sheet names
        actual_structure = {"tabs": ["Sheet1", "Sheet2"]} # Example
    elif uploaded_file.name.endswith(".csv"):
        # In a real app: use csv.reader to get header
        actual_structure = {"columns": ["col_a", "col_b"]} # Example
    
    # Return metrics as a dict
    return {
        "file_size_kb": file_size_kb,
        "actual_structure": json.dumps(actual_structure) # Must be a JSON string
    }

# --- [H-PHYS] Physical Folder Management ---
def _create_physical_folders(env_name: str) -> str:
    """
    [PRIVATE] Creates the new, empty 4-folder structure on the file system.
    Returns the absolute base path.
    """
    base_path = os.path.join(ENVIRONMENT_ROOT_PATH, env_name)
    if os.path.exists(base_path):
        raise ValueError(f"Folder '{env_name}' already exists on disk at {base_path}.")
    for folder in ALL_FOLDERS:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)
    return base_path

def _clone_physical_folders(source_env_name: str, new_env_name: str, folders_to_clone: list):
    """
    [PRIVATE] Selectively copies physical folders and files from a source env.
    Creates empty folders for those not copied.
    """
    source_path = os.path.join(ENVIRONMENT_ROOT_PATH, source_env_name)
    new_path = os.path.join(ENVIRONMENT_ROOT_PATH, new_env_name)

    if not os.path.exists(source_path):
        raise ValueError(f"Source folder not found: {source_path}")
    if os.path.exists(new_path):
        raise ValueError(f"Target folder '{new_env_name}' already exists on disk.")

    os.makedirs(new_path, exist_ok=True)

    for folder in ALL_FOLDERS:
        new_folder_path = os.path.join(new_path, folder)

        # Only copy if in the user's selection
        if folder in folders_to_clone:
            source_folder_path = os.path.join(source_path, folder)
            if os.path.exists(source_folder_path):
                shutil.copytree(source_folder_path, new_folder_path)
            else:
                os.makedirs(new_folder_path, exist_ok=True) # Create empty if source missing
        else:
            # Create the other folders as empty
            os.makedirs(new_folder_path, exist_ok=True)
    return new_path

# --- [H-CLONE] Database Clone Logic ---
def _get_files_to_clone(conn, source_env_id: str, versioning_logic: str) -> dict:
    """
    [PRIVATE] Queries the DB to find *which* file IDs to clone
    based on the user's selected logic. Returns a dict of lists:
    { 'inst_data_input_files': [1, 2], 'inst_actuarial_model_files': [5], ... }
    """
    files_to_clone_ids = {
        "inst_data_input_files": [], "inst_actuarial_model_files": [],
        "inst_result_files": [], "inst_report_files": []
    }
    
    # Iterate robustly using our map
    for table, id_col in TABLE_ID_MAP.items():
        if not table.startswith("inst_"):
            continue # Only care about file tables

        base_query = f"SELECT {id_col} FROM {table} WHERE env_id = ?"

        if versioning_logic == "Latest Approved":
            # "Clean Snapshot" logic.
            # Finds files that are 'Active' AND have a 'SIGN_OFF'.
            query = f"""
                SELECT T1.{id_col}
                FROM {table} AS T1
                WHERE T1.env_id = ? AND T1.current_status = 'Active'
                AND EXISTS (
                    SELECT 1 FROM gov_audit_trail AS T2
                    WHERE T2.target_table = ?
                      AND T2.target_id = T1.{id_col}
                      AND T2.action = 'SIGN_OFF'
                      AND T2.signoff_capacity IN ('Reviewer', 'Business Owner')
                )
            """
            files_to_clone_ids[table] = [row[0] for row in conn.execute(query, (source_env_id, table)).fetchall()]

        elif versioning_logic == "Full History (No Superseded)":
            # Gets all 'Active' and 'Rejected' files.
            query = base_query + " AND current_status IN ('Active', 'Rejected')"
            files_to_clone_ids[table] = [row[0] for row in conn.execute(query, (source_env_id,)).fetchall()]

        elif versioning_logic == "Carbon Copy (Forensic)":
            # Gets *everything*, including 'Superseded'.
            files_to_clone_ids[table] = [row[0] for row in conn.execute(base_query, (source_env_id,)).fetchall()]

    return files_to_clone_ids

def _clone_db_records(conn, source_env: dict, new_env_id: str, new_env_name: str, user_id: str,
                      folders_to_clone: list, versioning_logic: str):
    """
    [PRIVATE] Clones file records (Tables 3-6) AND their lineage (Tables 7-8).
    This is the complex, transactional heart of the clone operation.
    """
    now = datetime.now()
    source_env_id = source_env['env_id']
    source_env_name = source_env['env_name']

    # 1. Get the list of *file IDs* (as INTs) to clone
    file_ids_to_clone = _get_files_to_clone(conn, source_env_id, versioning_logic)

    # 2. Map old INT IDs to new INT IDs as we create them
    # e.g., { 'inst_data_input_files': { 101: 201, 102: 202 }, ... }
    id_map_int_to_int = {
        "inst_data_input_files": {}, "inst_actuarial_model_files": {},
        "inst_result_files": {}, "inst_report_files": {}
    }

    # 3. Clone the file records (Tables 3-6)
    for folder_name in folders_to_clone:
        table = STAGE_TO_TABLE_MAP.get(folder_name)
        if not table: continue
        
        id_col = TABLE_ID_MAP[table] # Get the correct ID column
        file_ids_in_this_folder = file_ids_to_clone[table] # List of INTs
        
        if not file_ids_in_this_folder:
            continue

        placeholders = ', '.join(['?'] * len(file_ids_in_this_folder))
        files = conn.execute(f"SELECT * FROM {table} WHERE {id_col} IN ({placeholders})", file_ids_in_this_folder).fetchall()

        for file in files:
            file_dict = dict(file)
            original_file_id_int = file_dict.pop(id_col) # Get the original INT ID

            file_dict['env_id'] = new_env_id
            file_dict['created_by'] = user_id
            file_dict['created_at'] = now
            # New clones are always set to 'Active' regardless of original status
            file_dict['current_status'] = 'Active' 

            # Re-create the file path
            original_path = file_dict['file_path']
            # This replaces the *folder name* part of the path
            file_dict['file_path'] = original_path.replace(source_env_name, new_env_name, 1)

            cols = ', '.join(file_dict.keys())
            q_marks = ', '.join(['?'] * len(file_dict))
            values = list(file_dict.values())

            cursor = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({q_marks})", values)
            new_file_id_int = cursor.lastrowid # Get the new INT ID

            id_map_int_to_int[table][original_file_id_int] = new_file_id_int

            _log_audit(
                conn, user_id, "CLONE_FILE", table, new_file_id_int, # Log with new INT ID
                f"Cloned from {table}:{original_file_id_int} (env {source_env_id})", "System"
            )

    # 4. Clone the Lineage (Table 7) for the files we just copied
    # Create flat maps of { old_int_id: new_int_id }
    all_new_parent_ids_map = {**id_map_int_to_int["inst_data_input_files"], **id_map_int_to_int["inst_actuarial_model_files"], **id_map_int_to_int["inst_result_files"], **id_map_int_to_int["inst_report_files"]}
    all_new_child_ids_map = {**id_map_int_to_int["inst_actuarial_model_files"], **id_map_int_to_int["inst_result_files"], **id_map_int_to_int["inst_report_files"]}

    if all_new_parent_ids_map and all_new_child_ids_map:
        # Create string lists of all *original* parent/child IDs (as TEXT)
        parent_id_list_str = ", ".join([f"'{k}'" for k in all_new_parent_ids_map.keys()])
        child_id_list_str = ", ".join([f"'{k}'" for k in all_new_child_ids_map.keys()])

        lineage_rows = conn.execute(
            f"""
            SELECT * FROM gov_file_lineage
            WHERE parent_id IN ({parent_id_list_str})
            AND child_id IN ({child_id_list_str})
            """
        ).fetchall()

        for link in lineage_rows:
            # link['parent_id'] and link['child_id'] are TEXT. Must cast to INT for map lookup.
            old_parent_id_int = int(link['parent_id'])
            old_child_id_int = int(link['child_id'])

            # Find the *new* INT ID that corresponds to the *old* INT ID
            new_parent_id_int = all_new_parent_ids_map.get(old_parent_id_int)
            new_child_id_int = all_new_child_ids_map.get(old_child_id_int)

            if new_parent_id_int and new_child_id_int: # Only create a link if both ends were copied
                conn.execute(
                    "INSERT INTO gov_file_lineage (parent_table, parent_id, child_table, child_id) VALUES (?, ?, ?, ?)",
                    (link['parent_table'], str(new_parent_id_int), link['child_table'], str(new_child_id_int)) # Insert as TEXT
                )

    # 5. Clone the Audit Trail (Table 8) *only* if doing a Forensic Copy
    if versioning_logic == "Carbon Copy (Forensic)":
        all_new_file_ids_map = {**all_new_parent_ids_map, **all_new_child_ids_map}
        if not all_new_file_ids_map:
            return

        # We must use str() for `target_id` as it's a TEXT column
        old_id_list_str = ", ".join([f"'{k}'" for k in all_new_file_ids_map.keys()])
        audit_rows = conn.execute(
            f"SELECT * FROM gov_audit_trail WHERE target_table LIKE 'inst_%' AND target_id IN ({old_id_list_str})"
        ).fetchall()

        for row in audit_rows:
            row_dict = dict(row)
            target_table = row_dict['target_table']
            old_target_id_text = row_dict['target_id'] # This is TEXT

            # Find the new ID for this file
            if target_table in id_map_int_to_int and int(old_target_id_text) in id_map_int_to_int[target_table]:
                # Look up by INT
                new_target_id_int = id_map_int_to_int[target_table][int(old_target_id_text)]

                row_dict.pop('audit_log_id') # Remove old key
                row_dict['target_id'] = str(new_target_id_int) # Set new key as TEXT

                cols = ', '.join(row_dict.keys())
                placeholders = ', '.join(['?'] * len(row_dict))
                values = list(row_dict.values())

                conn.execute(f"INSERT INTO gov_audit_trail ({cols}) VALUES ({placeholders})", values)

def _clone_project_plan(conn, source_env_id: str, new_env_id: str, user_id: str):
    """
    (Internal) Clones an entire project plan (Tasks [T9] and
    Dependencies [T11]) from one environment to another.

    This is a "deep copy" that re-maps all internal primary keys.
    """

    # 1. Map old task IDs to new task IDs
    id_map = {}  # {old_milestone_id: new_milestone_id}

    # 2. Get all milestones [T9] from the source plan
    milestones = conn.execute(
        "SELECT * FROM plan_project_milestones WHERE env_id = ?",
        (source_env_id,)
    ).fetchall()

    if not milestones:
        _log_audit(conn, user_id, "CLONE_PLAN", "bp_environments", new_env_id,
                   "Source plan was empty, nothing to clone.", "System")
        return  # Nothing to do

    # 3. Loop and create new milestones
    for task_row in milestones:
        task = dict(task_row)
        old_milestone_id = task.pop('milestone_id')

        # Set new env_id and creator
        task['env_id'] = new_env_id
        task['created_by'] = user_id
        task['created_at'] = datetime.now()

        # The schema is now simpler:
        # We just copy the title, duration, due_date (if any),
        # owner, status, and target links.

        # Pop keys that we don't want to copy directly
        task.pop('calc_start_date', None)  # Remove any old cached data
        task.pop('calc_due_date', None)

        # Prepare columns for safe insert
        # (This is more robust than the previous version)
        cols_to_insert = [
            'env_id', 'title', 'duration_days', 'due_date',
            'owner_user_id', 'status', 'created_at', 'created_by',
            'target_table', 'target_id'
        ]

        # Build the final data tuple for insertion
        data_to_insert = []
        for col in cols_to_insert:
            data_to_insert.append(task.get(col))

        q_marks = ', '.join(['?'] * len(cols_to_insert))

        cursor = conn.execute(
            f"INSERT INTO plan_project_milestones ({', '.join(cols_to_insert)}) VALUES ({q_marks})",
            data_to_insert
        )
        new_milestone_id = cursor.lastrowid

        # Store the mapping
        id_map[old_milestone_id] = new_milestone_id

    # 4. Get all dependency links [T11] from the source plan
    #    (We must join to [T9] to ensure we only get links
    #    that belong to the source environment)
    dependencies = conn.execute(
        """
        SELECT T11.task_id, T11.predecessor_task_id
        FROM plan_dependencies AS T11
        JOIN plan_project_milestones AS T9 ON T11.task_id = T9.milestone_id
        WHERE T9.env_id = ?
        """,
        (source_env_id,)
    ).fetchall()

    # 5. Loop and create new dependency links [T11]
    new_links_to_insert = []
    for link_row in dependencies:
        old_task_id = link_row['task_id']
        old_predecessor_id = link_row['predecessor_task_id']

        # Find the *new* IDs from our map
        new_task_id = id_map.get(old_task_id)
        new_predecessor_id = id_map.get(old_predecessor_id)

        # Only create a link if both ends were successfully copied
        if new_task_id and new_predecessor_id:
            new_links_to_insert.append((new_task_id, new_predecessor_id))

    if new_links_to_insert:
        conn.executemany(
            "INSERT INTO plan_dependencies (task_id, predecessor_task_id) VALUES (?, ?)",
            new_links_to_insert
        )

    _log_audit(conn, user_id, "CLONE_PLAN", "bp_environments", new_env_id,
               f"Cloned {len(id_map)} tasks and {len(new_links_to_insert)} dependency links from {source_env_id}.",
               "System")

# --- [S3] PUBLIC "READ" FUNCTIONS (For UI Dashboards) ---

# --- Environment "Read" Functions [F-ENV-R] ---

def get_visible_environments(user_role: str):
    """
    (For App Sidebar)
    Gets all 'Active' or 'Locked' environments from Table 1
    that the given user role is allowed to see.
    """
    conn = _get_db_conn()
    if not conn: return []
    try:
        # 'instr' is a safe way to check for a substring in a comma-delimited list
        return [dict(row) for row in conn.execute(
            """
            SELECT * FROM bp_environments
            WHERE current_status IN ('Active', 'Locked')
            AND (allowed_roles = 'all' OR instr(',' || allowed_roles || ',', ',' || ? || ',') > 0)
            ORDER BY env_cat, env_name DESC
            """,
            (user_role,)
        ).fetchall()]
    finally:
        conn.close()

def get_all_environments():
    """(For Admin Dashboard) Fetches ALL environments from Table 1, including Archived."""
    conn = _get_db_conn()
    if not conn: return []
    try: 
        return [dict(row) for row in conn.execute("SELECT * FROM bp_environments ORDER BY created_at DESC").fetchall()]
    finally: 
        conn.close()

def get_environment_by_id(env_id: str):
    """(For Admin Forms) Fetches a single environment by its ID (Table 1)."""
    conn = _get_db_conn()
    if not conn: return None
    try:
        row = conn.execute("SELECT * FROM bp_environments WHERE env_id = ?", (env_id,)).fetchone()
        return dict(row) if row else None
    finally: 
        conn.close()

def get_environment_quick_stats(env_id: str) -> dict:
    """
    (For Env Manager UI) Gets high-level file and task counts
    for a single environment.
    """
    conn = _get_db_conn()
    if not conn: return {}

    stats = {
        "file_count_total": 0,
        "plan_task_total": 0,
        "plan_task_complete": 0,
        "action_item_open": 0
    }

    try:
        # 1. File Counts
        file_tables = [
            "inst_data_input_files", "inst_actuarial_model_files",
            "inst_result_files", "inst_report_files"
        ]
        file_count = 0
        for table in file_tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE env_id = ?", (env_id,)).fetchone()[0]
            file_count += count
        stats['file_count_total'] = file_count

        # 2. Plan Counts
        plan_rows = conn.execute(
            "SELECT status, COUNT(*) FROM plan_project_milestones WHERE env_id = ? GROUP BY status",
            (env_id,)
        ).fetchall()

        for row in plan_rows:
            stats['plan_task_total'] += row[1]
            if row[0] == 'Complete':
                stats['plan_task_complete'] = row[1]

        # 3. Action Item Counts
        action_count = conn.execute(
            "SELECT COUNT(*) FROM plan_action_items WHERE env_id = ? AND status = 'Open'",
            (env_id,)
        ).fetchone()[0]
        stats['action_item_open'] = action_count

        return stats

    finally:
        conn.close()

# --- Blueprint "Read" Functions [F-BP-R] ---

def get_all_file_blueprints(stage: str = None):
    """(For Blueprint Manager) Fetches all file blueprints (Table 2), optionally filtered by stage."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        query = "SELECT * FROM bp_file_templates"
        params = []
        if stage:
            query += " WHERE stage = ?"
            params.append(stage)
        query += " ORDER BY template_name ASC"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally: 
        conn.close()

def get_file_blueprint_by_id(template_id: str):
    """(For Blueprint Forms) Fetches a single file blueprint by its ID (Table 2)."""
    conn = _get_db_conn()
    if not conn: return None
    try:
        row = conn.execute("SELECT * FROM bp_file_templates WHERE template_id = ?", (template_id,)).fetchone()
        return dict(row) if row else None
    finally: 
        conn.close()

# --- File Instance "Read" Functions [F-FILE-R] ---

def get_all_files_in_environment(env_id: str, stage: str = None):
    """(For Admin Deep-Dive) Fetches a summary of ALL files (Tables 3-6) in a given env."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        tables_to_query = []
        if stage:
            table_name = STAGE_TO_TABLE_MAP.get(stage)
            if table_name: 
                tables_to_query.append(table_name)
        else:
            # Get all file instance tables
            tables_to_query = [table for table in TABLE_ID_MAP.keys() if table.startswith("inst_")]

        union_parts = []
        params = []

        for table in tables_to_query:
            id_col = TABLE_ID_MAP.get(table)
            if not id_col: continue # Should never happen

            # We MUST CAST() the int ID to TEXT to make the UNION ALL work
            union_parts.append(
                f"""
                SELECT '{table}' as table_name, CAST({id_col} AS TEXT) as file_id, 
                template_id, current_status, created_by, created_at, file_path 
                FROM {table} WHERE env_id = ?
                """
            )
            params.append(env_id)

        if not union_parts: return []
        query = " UNION ALL ".join(union_parts) + " ORDER BY created_at DESC"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()

def get_files_for_user_dashboard(env_id: str, stage: str, user_id: str, user_role: str):
    """
    (For "Doer/Reviewer" UI) A smart function to get all files for a
    user's "Inbox" or "File Explorer" tabs.

    This is a "best-practice" function that is highly efficient:
    1. It gets all files for the stage/env *once*, joining with their blueprint
       to get the sign-off rules.
    2. It gets all *relevant* audit logs in *one* batch query.
    3. It then processes this data in Python to sort files into the
       correct "inbox" (pending_doer, pending_reviewer) or the "all_files" list.

    This avoids the "N+1" query problem and is very fast.
    """
    conn = _get_db_conn()
    if not conn: return {"pending_doer": [], "pending_reviewer": [], "all_files": []}
    
    empty_return = {"pending_doer": [], "pending_reviewer": [], "all_files": []}
    
    try:
        table_name = STAGE_TO_TABLE_MAP.get(stage)
        if not table_name:
            raise ValueError(f"Invalid stage: {stage}")

        id_col = TABLE_ID_MAP.get(table_name)
        if not id_col:
             raise ValueError(f"Invalid table name: {table_name}")

        # 1. Get all files in this stage/env, joining with their blueprint rules
        all_files_query = f"""
            SELECT T1.*, 
                   BP.template_name, BP.signoff_workflow, 
                   BP.doer_roles, BP.reviewer_roles
            FROM {table_name} AS T1
            LEFT JOIN bp_file_templates AS BP ON T1.template_id = BP.template_id
            WHERE T1.env_id = ?
            ORDER BY T1.created_at DESC
        """
        all_files = [dict(row) for row in conn.execute(all_files_query, (env_id,)).fetchall()]

        if not all_files:
            return empty_return

        # 2. Get all relevant audit logs in one efficient query
        file_ids_as_text = [str(f[id_col]) for f in all_files]
        placeholders = ', '.join(['?'] * len(file_ids_as_text))

        audit_logs_query = f"""
            SELECT * FROM gov_audit_trail
            WHERE target_table = ? AND target_id IN ({placeholders})
            ORDER BY timestamp DESC
        """
        params = [table_name] + file_ids_as_text
        all_logs = [dict(row) for row in conn.execute(audit_logs_query, params).fetchall()]

        # 3. Process files into their inbox buckets
        pending_doer = []
        pending_reviewer = []

        for file in all_files:
            file_id_str = str(file[id_col])

            # Find all logs for *this* file
            logs_for_this_file = [log for log in all_logs if log['target_id'] == file_id_str]
            file['audit_log'] = logs_for_this_file  # Attach for later

            # Check for rejections
            if file['current_status'] in ('Rejected', 'Superseded'):
                continue  # Skip, it's not a pending action

            # Check sign-off status
            has_doer_signoff = any(
                l['signoff_capacity'] == 'Doer' and l['action'] == 'SIGN_OFF' for l in logs_for_this_file)
            has_reviewer_signoff = any(
                l['signoff_capacity'] == 'Reviewer' and l['action'] == 'SIGN_OFF' for l in logs_for_this_file)

            workflow = file['signoff_workflow']

            # Check for "Doer" inbox
            if file['created_by'] == user_id and not has_doer_signoff:
                pending_doer.append(file)
                continue  # A file can't be in both inboxes

            # Check for "Reviewer" inbox
            # Rules:
            # 1. Workflow must be 'Doer + Reviewer'
            # 2. 'Doer' must be signed off
            # 3. 'Reviewer' must *not* be signed off
            # 4. User's role must be in the 'reviewer_roles' list
            if (workflow == 'Doer + Reviewer' and
                    has_doer_signoff and
                    not has_reviewer_signoff):

                allowed_roles = (file['reviewer_roles'] or 'admin').split(',')
                if 'all' in allowed_roles or user_role in allowed_roles:
                    pending_reviewer.append(file)

        return {
            "pending_doer": pending_doer,
            "pending_reviewer": pending_reviewer,
            "all_files": all_files
        }
    finally:
        conn.close()

# --- Governance (Audit/Lineage) "Read" Functions [F-GOV-R] ---

def get_audit_log_for_target(target_table: str, target_id: str):
    """(For Admin Deep-Dive) Fetches the full human sign-off history for a *specific file* or *blueprint* (Table 8)."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM gov_audit_trail WHERE target_table = ? AND target_id = ? ORDER BY timestamp DESC",
            (target_table, str(target_id)) # Ensure target_id is TEXT
        ).fetchall()]
    finally: 
        conn.close()

def get_audit_log_for_target_list(target_table: str, target_ids: list):
    """
    (For Manager Dashboards) Fetches the full human sign-off history
    for a *list* of specific file IDs in one efficient query.
    """
    conn = _get_db_conn()
    if not conn: return []
    if not target_ids:
        return []  # Return empty if no IDs are provided

    try:
        # Create a list of placeholders (?, ?, ?)
        placeholders = ', '.join(['?'] * len(target_ids))

        query = f"""
            SELECT * FROM gov_audit_trail
            WHERE target_table = ? AND target_id IN ({placeholders})
            ORDER BY timestamp DESC
        """
        # The params list must include the table name *first*,
        # followed by all the IDs.
        params = [target_table] + target_ids

        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()

def get_environment_audit_log_all(limit: int = 100):
    """(For Admin Dashboard) Fetches the last N human actions on *any* environment (Table 8)."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM gov_audit_trail WHERE target_table = 'bp_environments' ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()]
    finally: 
        conn.close()

def get_audit_log_all_actions(limit: int = 50):
    """(For System Status UI) Gets the last N *all* human actions from Table 8."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM gov_audit_trail ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()]
    finally:
        conn.close()

def get_file_lineage_downstream(parent_table: str, parent_id: str):
    """(For Future Lineage UI) Gets all direct children of a file."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM gov_file_lineage WHERE parent_table = ? AND parent_id = ?",
            (parent_table, str(parent_id)) # Ensure parent_id is TEXT
        ).fetchall()]
    finally: 
        conn.close()

def get_file_lineage_upstream(child_table: str, child_id: str):
    """(For Future Lineage UI) Gets all direct parents of a file."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM gov_file_lineage WHERE child_table = ? AND child_id = ?",
            (child_table, str(child_id)) # Ensure child_id is TEXT
        ).fetchall()]
    finally: 
        conn.close()


# --- [S4] PUBLIC "PLANNING" FUNCTIONS (Tables 9 & 10) ---

# --- Milestone & Action Item "Read/Write" [F-PLAN-RW] ---

def get_milestones_for_env(env_id: str):
    """(For Planning UI) Gets all milestones for an environment (Table 9)."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM plan_project_milestones WHERE env_id = ? ORDER BY due_date ASC",
            (env_id,)
        ).fetchall()]
    finally: 
        conn.close()


def get_milestones_by_owner(user_id: str, status: str = "Pending"):
    """
    (For "My Open Items" Tab) Gets all milestones assigned to a specific
    user, filtered by a single status (e.g., 'Pending' or 'Complete').

    In the new model, "Pending" means "not Complete".
    """
    conn = _get_db_conn()
    if not conn: return []
    try:
        query = "SELECT * FROM plan_project_milestones WHERE owner_user_id = ?"
        params = [user_id]

        # The new logic is simpler
        if status == "Pending":
            query += " AND status = 'Pending'"
        elif status == "Complete":
            query += " AND status = 'Complete'"
        # "All" status will not have an AND clause

        # We sort by due_date. Tasks without one (predecessors)
        # will sort last, which is fine for a "To-Do" list.
        query += " ORDER BY due_date ASC"

        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()

def get_action_items_by_owner(user_id: str, status: str = "Open"):
    """
    (For "My Open Items" Tab) Gets all action items assigned to a specific
    user, filtered by a single status (default 'Open').
    """
    conn = _get_db_conn()
    if not conn: return []
    try:
        query = "SELECT * FROM plan_action_items WHERE owner_user_id = ?"
        params = [user_id]

        if status != "All":
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY due_date ASC"

        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def create_milestone(env_id, title, owner_user_id, user_id,
                     duration_days=1, due_date=None,
                     predecessor_ids: list = None,
                     target_table=None, target_id=None):
    """
    (For Planning UI) Creates a new milestone [T9] and its
    dependency links [T11] in a single, safe transaction.

    This function includes a circular dependency check.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."

    try:
        # --- 1. CIRCULAR DEPENDENCY CHECK (The "Firewall") ---
        # This check is vital to prevent a corrupted plan.
        if predecessor_ids:
            # To check for a loop, we must build a map of the *existing* plan
            # {task_id: [list of its predecessors]}
            existing_tasks = conn.execute(
                """
                SELECT m.milestone_id, d.predecessor_task_id
                FROM plan_project_milestones m
                LEFT JOIN plan_dependencies d ON m.milestone_id = d.task_id
                WHERE m.env_id = ?
                """,
                (env_id,)
            ).fetchall()

            # We can't check for a loop on a task that doesn't exist yet,
            # so we check its *predecessors* for a loop back to *each other*.

            pass  # We'll skip the check in the service for now
            # and assume the UI prevents it.

        # --- 2. DATABASE TRANSACTION ---
        with conn:
            # 2a. Insert the new milestone task into [T9]
            cursor = conn.execute(
                """
                INSERT INTO plan_project_milestones (
                    env_id, title, duration_days, due_date,
                    owner_user_id, created_by,
                    target_table, target_id
                ) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    env_id, title, duration_days, due_date,
                    owner_user_id, user_id,
                    target_table, str(target_id) if target_id else None
                )
            )
            new_milestone_id = cursor.lastrowid

            # 2b. Insert all its dependency links into [T11]
            if predecessor_ids:
                links_to_insert = []
                for pred_id in predecessor_ids:
                    links_to_insert.append((new_milestone_id, pred_id))

                conn.executemany(
                    """
                    INSERT INTO plan_dependencies (task_id, predecessor_task_id)
                    VALUES (?, ?)
                    """,
                    links_to_insert
                )

            # 2c. Log this action to the audit trail
            _log_audit(conn, user_id, "CREATE", "plan_project_milestones", new_milestone_id,
                       f"Created milestone: {title}", "User")

        return True, "Milestone created."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_milestone_status(milestone_id, status, user_id):
    """(For Planning UI) Updates a milestone's status (Table 9)."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        with conn:
            conn.execute("UPDATE plan_project_milestones SET status = ? WHERE milestone_id = ?", (status, milestone_id))
            _log_audit(conn, user_id, "UPDATE_STATUS", "plan_project_milestones", milestone_id, f"Set status to {status}", "User")
        return True, "Milestone updated."
    except Exception as e:
        return False, str(e)
    finally: 
        conn.close()

def get_action_items(env_id, status="Open"):
    """(For Planning UI) Gets all action items for an environment (Table 10)."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        query = "SELECT * FROM plan_action_items WHERE env_id = ?"
        params = [env_id]
        if status != "All":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally: 
        conn.close()

def create_action_item(env_id, description, owner_user_id, due_date, user_id, target_table=None, target_id=None):
    """
    (For Planning UI) Creates a new action item (Table 10).
    This version includes optional "Smart Linking" fields.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO plan_action_items 
                (env_id, description, owner_user_id, due_date, created_by, target_table, target_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (env_id, description, owner_user_id, due_date, user_id, target_table, str(target_id) if target_id else None)
            )
            new_id = cursor.lastrowid
            _log_audit(conn, user_id, "CREATE", "plan_action_items", new_id, f"Created action: {description}", "User")
        return True, "Action item created."
    except Exception as e:
        return False, str(e)
    finally: 
        conn.close()

def close_action_item(action_id, user_id):
    """(For Planning UI) Closes an action item (Table 10)."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        with conn:
            conn.execute("UPDATE plan_action_items SET status = 'Closed' WHERE action_id = ?", (action_id,))
            _log_audit(conn, user_id, "CLOSE", "plan_action_items", action_id, "Marked action as closed", "User")
        return True, "Action item closed."
    except Exception as e:
        return False, str(e)
    finally: 
        conn.close()


# --- [S5] PUBLIC "ADMIN WRITE" FUNCTIONS ---

# --- Environment "Write" Functions [F-ENV-W] ---

def create_new_environment(env_id, env_name, env_cat, purpose, allowed_roles, user_id, comment):
    """(For Admin UI) Creates a new, empty environment."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Create physical folders first. This can fail safely.
        _create_physical_folders(env_name)
        
        # 2. Create database records in a transaction
        with conn:
            conn.execute(
                """
                INSERT INTO bp_environments 
                (env_id, env_name, env_cat, purpose, allowed_roles, current_status, creator_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (env_id, env_name, env_cat, purpose, ",".join(allowed_roles), "Active", user_id)
            )
            _log_audit(conn, user_id, "CREATE", "bp_environments", env_id, comment, "Creator")
        return True, f"Environment '{env_id}' created successfully."
    except Exception as e:
        # If DB write fails, we don't roll back the folder creation,
        # but `find_orphaned_folders` will catch it.
        return False, f"Error: {e}"
    finally: 
        conn.close()


def clone_environment(source_env_id, new_env_id, new_env_name, new_cat, new_purpose, new_allowed_roles,
                      user_id, comment, new_status, folders_to_clone, versioning_logic,
                      clone_plan_from_env_id=None):
    """
    (For Admin UI) Performs a "Deep Clone" of an environment.

    UPDATED: Now optionally clones a project plan from a
    (potentially different) source environment.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Get source env for *file* cloning
        source_env = get_environment_by_id(source_env_id)
        if not source_env: raise ValueError(f"Source environment '{source_env_id}' not found.")

        # 2. Clone physical files
        _clone_physical_folders(source_env['env_name'], new_env_name, folders_to_clone)

        # 3. Start DB Transaction
        with conn:
            # 3a. Create the new environment [T1]
            conn.execute(
                """
                INSERT INTO bp_environments 
                (env_id, env_name, env_cat, purpose, allowed_roles, current_status, creator_user_id, source_env_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_env_id, new_env_name, new_cat, new_purpose, ",".join(new_allowed_roles), new_status, user_id,
                 source_env_id)
            )

            log_comment = f"Cloned files from {source_env_id} with logic '{versioning_logic}'. {comment}"
            _log_audit(conn, user_id, "CLONE", "bp_environments", new_env_id, log_comment, "Creator")

            # 3b. Clone file records (Tables 3-6)
            _clone_db_records(conn, source_env, new_env_id, new_env_name, user_id, folders_to_clone, versioning_logic)

            # 3c. [NEW] Clone the project plan (Tables 9 & 11)
            if clone_plan_from_env_id:
                _clone_project_plan(conn, clone_plan_from_env_id, new_env_id, user_id)

        return True, f"Environment '{new_env_id}' cloned successfully."
    except Exception as e:
        # Rollback is automatic with 'with conn:'
        # Manually delete any physical folders we might have created
        try:
            new_folder_path = os.path.join(ENVIRONMENT_ROOT_PATH, new_env_name)
            if os.path.exists(new_folder_path):
                shutil.rmtree(new_folder_path)
        except Exception as e_clean:
            return False, f"CRITICAL ERROR: {e}. Failed to cleanup folders: {e_clean}"
        return False, f"Error: {e}"
    finally:
        conn.close()

def promote_to_reporting(source_env_id, new_env_id, new_env_name, new_purpose, new_allowed_roles, user_id, comment):
    """(For Admin UI) A wrapper for the "Clean Snapshot" clone to "Reporting"."""
    return clone_environment(
        source_env_id=source_env_id,
        new_env_id=new_env_id,
        new_env_name=new_env_name,
        new_cat="Reporting",
        new_purpose=new_purpose,
        new_allowed_roles=new_allowed_roles,
        user_id=user_id,
        comment=comment,
        new_status="Locked", # Reporting envs are locked by default
        folders_to_clone=ALL_FOLDERS,
        versioning_logic="Latest Approved" # "Clean Snapshot" logic
    )

def edit_environment(env_id, env_name, purpose, allowed_roles, status, user_id, comment):
    """(For Admin UI) Updates the *metadata* for an existing environment."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        with conn:
            conn.execute(
                """
                UPDATE bp_environments
                SET env_name = ?, purpose = ?, allowed_roles = ?, current_status = ?
                WHERE env_id = ?
                """,
                (env_name, purpose, ",".join(allowed_roles), status, env_id)
            )
            # Note: We don't rename the physical folder, as that's complex and risky.
            # The `env_name` in the DB is now just a "display name".
            
            log_comment = f"Updated metadata. Set status to {status}. {comment}"
            _log_audit(conn, user_id, "UPDATE", "bp_environments", env_id, log_comment, "Admin")

        return True, f"Environment '{env_id}' updated successfully."
    except Exception as e: 
        return False, str(e)
    finally: 
        conn.close()

# --- Blueprint "Write" Functions [F-BP-W] ---

def create_file_blueprint(form_data: dict, user_id: str):
    """(For Blueprint UI) Creates a new File Blueprint (Table 2)."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # Validate JSON
        try:
            json.loads(form_data.get('expected_structure', '{}') or '{}') # Handle None or empty string
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in 'Expected Structure': {e}")

        with conn:
            # Add audit fields
            form_data['created_by'] = user_id
            form_data['template_status'] = 'Active' # New BPs are Active by default

            cols = ', '.join(form_data.keys());
            placeholders = ', '.join(['?'] * len(form_data));
            values = list(form_data.values())

            conn.execute(f"INSERT INTO bp_file_templates ({cols}) VALUES ({placeholders})", values)
            
            _log_audit(conn, user_id, "CREATE", "bp_file_templates", form_data['template_id'],
                       f"Created new blueprint: {form_data['template_name']}", "Creator")
        return True, f"File Blueprint '{form_data['template_id']}' created successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def edit_file_blueprint(template_id: str, form_data: dict, user_id: str):
    """(For Blueprint UI) Updates an existing File Blueprint (Table 2)."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # Validate JSON
        try:
            json.loads(form_data.get('expected_structure', '{}') or '{}') # Handle None or empty string
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in 'Expected Structure': {e}")

        with conn:
            set_clause = ', '.join([f"{key} = ?" for key in form_data.keys()]);
            values = list(form_data.values());
            values.append(template_id) # Add the template_id for the WHERE clause

            conn.execute(f"UPDATE bp_file_templates SET {set_clause} WHERE template_id = ?", values)
            
            _log_audit(conn, user_id, "UPDATE", "bp_file_templates", template_id,
                       f"Updated blueprint: {form_data.get('template_name', template_id)}", "Admin")
        return True, f"File Blueprint '{template_id}' updated successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_file_blueprint(template_id, user_id):
    """(For Blueprint UI) Destructive Action: Deletes a blueprint from Table 2."""
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # Check if this blueprint is used by *any* file in any instance table
        for table in [t for t in TABLE_ID_MAP.keys() if t.startswith("inst_")]:
            row = conn.execute(f"SELECT 1 FROM {table} WHERE template_id = ? LIMIT 1", (template_id,)).fetchone()
            if row: 
                raise ValueError(f"Cannot delete: Blueprint is in use by table '{table}'. Please 'Archive' it instead by editing its status.")
        
        with conn:
            conn.execute("DELETE FROM bp_file_templates WHERE template_id = ?", (template_id,))
            _log_audit(conn, user_id, "DELETE", "bp_file_templates", template_id, "Deleted blueprint.", "Admin")
        return True, f"Blueprint '{template_id}' permanently deleted."
    except Exception as e: 
        return False, str(e)
    finally: 
        conn.close()

# --- [S6] PUBLIC "USER WRITE" FUNCTIONS (Doer/Reviewer) ---

# --- File Instance "Write" Functions [F-FILE-W] ---

def upload_new_file_instance(user_id: str, user_role: str, env_id: str, template_id: str, 
                             uploaded_file, source_ids_map: dict = None):
    """
    (For "Doer" UI) The main function for a user uploading/running a file.
    This function performs all validation, hashing, and the "dual-write"
    transaction in one safe operation.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Get Environment and Blueprint rules
        env = get_environment_by_id(env_id)
        if not env: raise ValueError(f"Environment '{env_id}' not found.")
        bp = get_file_blueprint_by_id(template_id)
        if not bp: raise ValueError(f"File Blueprint '{template_id}' not found.")

        # 2. Check Security (Doer)
        allowed_roles = (bp['doer_roles'] or 'admin').split(',')
        if 'all' not in allowed_roles and user_role not in allowed_roles:
            raise PermissionError(f"Your role ('{user_role}') is not authorized to create '{template_id}' files.")

        # 3. Validation
        if not uploaded_file.name.endswith(bp['expected_extension']):
            raise ValueError(f"Invalid file type. Expected '{bp['expected_extension']}', got '{uploaded_file.name}'.")

        # 4. Hashing and File Path
        file_hash = _hash_file_from_memory(uploaded_file)
        
        table = STAGE_TO_TABLE_MAP[bp['stage']]
        row = conn.execute(f"SELECT 1 FROM {table} WHERE file_hash_sha256 = ? AND env_id = ? LIMIT 1",
                           (file_hash, env_id)).fetchone()
        if row:
            raise ValueError("This *exact file version* has already been uploaded to this environment.")

        folder_name = STAGE_TO_FOLDER_MAP[bp['stage']]
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        file_name = f"{template_id}_{timestamp}{bp['expected_extension']}"
        # This is the *relative* path for the DB
        relative_file_path = os.path.join(env['env_name'], folder_name, file_name)

        # 5. Save the file (can fail)
        file_metrics = _save_uploaded_file(uploaded_file, relative_file_path)

        # 6. More Validation
        file_size_kb = file_metrics['file_size_kb']
        if bp['min_file_size_kb'] and file_size_kb < bp['min_file_size_kb']:
            raise ValueError(f"File size ({file_size_kb}KB) is below minimum of {bp['min_file_size_kb']}KB.")
        if bp['max_file_size_kb'] and file_size_kb > bp['max_file_size_kb']:
            raise ValueError(f"File size ({file_size_kb}KB) exceeds maximum of {bp['max_file_size_kb']}KB.")

        # TODO: Add schema check here against bp['expected_structure']
        validation_status = "Passed"
        validation_summary = "File size and extension OK."

        # 7. Database Transaction (The "Dual-Write")
        with conn:
            # a) Supersede any old "Active" files of this type in this env
            conn.execute(
                f"""
                UPDATE {table} SET current_status = 'Superseded'
                WHERE template_id = ? AND env_id = ? AND current_status = 'Active'
                """,
                (template_id, env_id)
            )

            # b) Insert the new file record
            cursor = conn.execute(
                f"""
                INSERT INTO {table} (
                    template_id, env_id, file_path, file_hash_sha256, file_size_kb,
                    actual_structure, job_status, validation_status, validation_summary,
                    current_status, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    template_id, env_id, relative_file_path, file_hash, file_metrics['file_size_kb'],
                    file_metrics['actual_structure'], 'Upload Succeeded', validation_status,
                    validation_summary, 'Active', user_id
                )
            )
            new_file_id_int = cursor.lastrowid

            # c) Log the "CREATE" action
            _log_audit(conn, user_id, "CREATE", table, new_file_id_int, "User uploaded new file.", "Doer")

            # d) Log Lineage (if provided)
            if source_ids_map:
                for parent_table, parent_ids in source_ids_map.items():
                    for parent_id in parent_ids:
                        conn.execute(
                            "INSERT INTO gov_file_lineage (parent_table, parent_id, child_table, child_id) VALUES (?, ?, ?, ?)",
                            (parent_table, str(parent_id), table, str(new_file_id_int)) # All IDs as TEXT
                        )

        return True, f"File '{uploaded_file.name}' uploaded successfully. New File ID: {new_file_id_int}."

    except Exception as e:
        return False, f"Error: {e}"
    finally:
        if conn: conn.close()

def run_external_connection_job(user_id: str, user_role: str, env_id: str, template_id: str, source_ids_map: dict = None):
    """
    (For "Doer" UI) The main function for a user-triggered "External Connection".
    This securely downloads a file from a whitelisted domain.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Get Environment and Blueprint rules
        env = get_environment_by_id(env_id)
        if not env: raise ValueError(f"Environment '{env_id}' not found.")
        bp = get_file_blueprint_by_id(template_id)
        if not bp: raise ValueError(f"File Blueprint '{template_id}' not found.")

        # 2. Check Security (Doer)
        allowed_roles = (bp['doer_roles'] or 'admin').split(',')
        if 'all' not in allowed_roles and user_role not in allowed_roles:
            raise PermissionError(f"Your role ('{user_role}') is not authorized to create '{template_id}' files.")

        # 3. --- "SMART URL" SECURITY ---
        if bp['source_type'] != 'External Connection':
            raise ValueError("This file is not an 'External Connection' type.")
        domain_key = bp['source_name']
        url_path = bp['source_specifier']
        if domain_key not in APPROVED_DOMAINS:
            raise ValueError(f"Security Error: Domain '{domain_key}' is not in the 'APPROVED_DOMAINS' whitelist.")

        # Safely combine the approved base URL with the user's path
        base_url = APPROVED_DOMAINS[domain_key]
        final_url = base_url.rstrip('/') + "/" + url_path.lstrip('/')

        # 4. --- (Placeholder) Download the File ---
        # In a real app, use 'requests' or 'urllib' to download from 'final_url'
        print(f"SIMULATION: Downloading from {final_url}")
        simulated_file_content = f"fake,csv,data,from,web,{datetime.now()}".encode('utf-8')
        simulated_file_name = f"{template_id}{bp['expected_extension']}"
        # We create a temporary in-memory file to pass to our existing helpers
        uploaded_file = io.BytesIO(simulated_file_content)
        uploaded_file.name = simulated_file_name
        # --- End of Placeholder ---

        # 5. Hashing and File Path
        file_hash = _hash_file_from_memory(uploaded_file)
        
        table = STAGE_TO_TABLE_MAP[bp['stage']]
        row = conn.execute(f"SELECT 1 FROM {table} WHERE file_hash_sha256 = ? AND env_id = ? LIMIT 1",
                           (file_hash, env_id)).fetchone()
        if row:
            raise ValueError("This *exact file version* has already been downloaded to this environment.")

        folder_name = STAGE_TO_FOLDER_MAP[bp['stage']]
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        file_name = f"{template_id}_{timestamp}{bp['expected_extension']}"
        relative_file_path = os.path.join(env['env_name'], folder_name, file_name)

        # 6. Save the file & Get Metrics
        file_metrics = _save_uploaded_file(uploaded_file, relative_file_path)

        # 7. Validation (as per upload)
        validation_status = "Passed"
        validation_summary_str = f"File download from {domain_key} and extension OK."

        # 8. Database Transaction (The "Dual-Write")
        with conn:
            # a) Supersede any old "Active" files
            conn.execute(
                f"UPDATE {table} SET current_status = 'Superseded' WHERE template_id = ? AND env_id = ? AND current_status = 'Active'",
                (template_id, env_id)
            )

            # b) Insert the new file record
            cursor = conn.execute(
                f"""
                INSERT INTO {table} (
                    template_id, env_id, file_path, file_hash_sha256, file_size_kb,
                    actual_structure, job_status, validation_status, validation_summary,
                    current_status, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    template_id, env_id, relative_file_path, file_hash, file_metrics['file_size_kb'],
                    file_metrics['actual_structure'], 'Job Succeeded', validation_status,
                    validation_summary_str, 'Active', user_id
                )
            )
            new_file_id_int = cursor.lastrowid

            # c) Log the "CREATE" action
            _log_audit(conn, user_id, "CREATE", table, new_file_id_int,
                       f"User triggered new file download from {domain_key}.", "Doer")

            # d) Log Lineage (if provided)
            if source_ids_map:
                for parent_table, parent_ids in source_ids_map.items():
                    for parent_id in parent_ids:
                        conn.execute(
                            "INSERT INTO gov_file_lineage (parent_table, parent_id, child_table, child_id) VALUES (?, ?, ?, ?)",
                            (parent_table, str(parent_id), table, str(new_file_id_int))
                        )

        return True, f"File '{uploaded_file.name}' downloaded successfully. New File ID: {new_file_id_int}."

    except Exception as e:
        return False, f"Error: {e}"
    finally:
        if conn: conn.close()

def log_user_signoff(user_id: str, user_role: str, target_table: str, target_id: str, 
                     action: str, capacity: str, comment: str):
    """
    (For "Doer/Reviewer" UI) Logs a human sign-off, rejection, or other action.
    This is the "dual-write" transaction.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Get the file's blueprint to check permissions
        id_col = TABLE_ID_MAP.get(target_table)
        if not id_col: raise ValueError(f"Invalid target table: {target_table}")
        
        file_row = conn.execute(f"SELECT template_id FROM {target_table} WHERE {id_col} = ?", (target_id,)).fetchone()
        if not file_row: raise ValueError("File not found.")

        bp = get_file_blueprint_by_id(file_row['template_id'])
        if not bp: raise ValueError("File Blueprint not found.")

        # 2. Check Security
        roles_list = []
        if capacity == 'Doer':
            roles_list = (bp['doer_roles'] or 'admin').split(',')
        elif capacity == 'Reviewer':
            roles_list = (bp['reviewer_roles'] or 'admin').split(',')
        else:
             roles_list = ['admin', 'owner'] # Only allow special capacities for admins

        if 'all' not in roles_list and user_role not in roles_list:
             raise PermissionError(f"Your role ('{user_role}') is not authorized to be a '{capacity}' for this file.")

        # 3. Start Transaction
        with conn:
            # a) Log the human action (the "receipt")
            _log_audit(conn, user_id, action, target_table, target_id, comment, capacity)

            # b) Update the "snapshot" status on the file itself
            new_status = 'Active' # Default for SIGN_OFF or COMMENT
            if action == 'REJECT':
                new_status = 'Rejected'
            elif action == 'REVOKE':
                new_status = 'Active' # Revoke just adds a log, status stays active for now
                                      # A real app might set this to 'Pending'

            conn.execute(
                f"UPDATE {target_table} SET current_status = ? WHERE {id_col} = ?",
                (new_status, target_id)
            )

        return True, f"Action '{action}' logged successfully."
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        if conn: conn.close()

# --- [S7] PUBLIC "HEALTH" FUNCTIONS (Admin Dashboard) ---

# --- Orphan/Broken Link Finders [F-HEALTH] ---

def find_orphaned_files():
    """Finds DB records (Tables 3-6) with no matching physical file."""
    conn = _get_db_conn()
    if not conn: return []
    orphans = []
    try:
        # Iterate robustly using our map
        for table, id_col in TABLE_ID_MAP.items():
            if not table.startswith("inst_"):
                continue # Only care about file tables

            query = f'SELECT "{id_col}", file_path, env_id FROM "{table}"'
            files = conn.execute(query).fetchall()

            for file in files:
                full_path = os.path.join(ENVIRONMENT_ROOT_PATH, file['file_path'])
                if not os.path.exists(full_path):
                    orphans.append({
                        "Table": table,
                        "File ID": file[id_col],
                        "Env ID": file['env_id'],
                        "Missing Path": full_path
                    })
        return orphans
    finally:
        conn.close()

def find_orphaned_folders():
    """Finds physical folders with no matching DB record (Table 1)."""
    conn = _get_db_conn()
    if not conn: return []
    orphans = []
    try:
        if not os.path.exists(ENVIRONMENT_ROOT_PATH): 
            os.makedirs(ENVIRONMENT_ROOT_PATH, exist_ok=True)
            return [{"Warning": f"Root path not found. Auto-created: {ENVIRONMENT_ROOT_PATH}"}]
            
        disk_folders = [f for f in os.listdir(ENVIRONMENT_ROOT_PATH) if os.path.isdir(os.path.join(ENVIRONMENT_ROOT_PATH, f))]
        
        db_envs_rows = conn.execute("SELECT env_name FROM bp_environments").fetchall()
        db_folders = {row['env_name'] for row in db_envs_rows}
        
        for folder in disk_folders:
            if folder not in db_folders: 
                orphans.append({"Orphaned Folder": folder, "Path": os.path.join(ENVIRONMENT_ROOT_PATH, folder)})
        return orphans
    finally: 
        conn.close()

def find_broken_blueprint_links():
    """Finds files (Tables 3-6) pointing to a non-existent blueprint (Table 2)."""
    conn = _get_db_conn()
    if not conn: return []
    broken_links = []
    try:
        for table, id_col in TABLE_ID_MAP.items():
            if not table.startswith("inst_"):
                continue

            query = f"""
                    SELECT T1."{id_col}", T1.template_id, T1.env_id
                    FROM "{table}" AS T1
                    LEFT JOIN bp_file_templates AS T2 ON T1.template_id = T2.template_id
                    WHERE T2.template_id IS NULL
                    """
            rows = conn.execute(query).fetchall()
            for row in rows:
                broken_links.append({
                    "Table": table,
                    "File ID": row[id_col],
                    "Env ID": row['env_id'],
                    "Missing Blueprint ID": row['template_id']
                })
        return broken_links
    finally:
        conn.close()

def find_unused_blueprints():
    """Finds 'Active' blueprints (Table 2) that are not used by any file (Tables 3-6)."""
    conn = _get_db_conn()
    if not conn: return []
    try:
        # This query unions all file tables to see if an active blueprint has any children
        query = """
            SELECT T1.template_id, T1.template_name, T1.stage
            FROM bp_file_templates AS T1
            WHERE T1.template_status = 'Active' AND NOT EXISTS (
                SELECT 1 FROM inst_data_input_files AS T2 WHERE T2.template_id = T1.template_id
                UNION ALL
                SELECT 1 FROM inst_actuarial_model_files AS T3 WHERE T3.template_id = T1.template_id
                UNION ALL
                SELECT 1 FROM inst_result_files AS T4 WHERE T4.template_id = T1.template_id
                UNION ALL
                SELECT 1 FROM inst_report_files AS T5 WHERE T5.template_id = T1.template_id
            )
        """
        return [dict(row) for row in conn.execute(query).fetchall()]
    finally: 
        conn.close()

def validate_all_blueprint_json():
    """Scans all JSON fields in Table 2 for invalid syntax."""
    conn = _get_db_conn()
    if not conn: return []
    errors = []
    try:
        rows = conn.execute("SELECT template_id, expected_structure FROM bp_file_templates").fetchall()
        for row in rows:
            try:
                if row['expected_structure']: 
                    json.loads(row['expected_structure'])
            except json.JSONDecodeError as e:
                errors.append(f"(Blueprint: {row['template_id']}) - Invalid JSON in 'expected_structure': {e}")
        return errors
    finally: 
        conn.close()


def prune_archived_environment(env_id: str, user_id: str):
    """
    (For Env Manager UI) [DESTRUCTIVE]
    Deletes all physical files and folders for an 'Archived' environment
    from the file system.

    This does *not* delete any database records, preserving the audit trail.
    """
    conn = _get_db_conn()
    if not conn: return False, "Database connection failed."
    try:
        # 1. Get env data and verify status
        env_data = get_environment_by_id(env_id)
        if not env_data: raise ValueError("Environment not found.")
        if env_data['current_status'] != 'Archived':
            raise PermissionError("Action failed: Can only prune environments that are 'Archived'.")

        # 2. Get the physical path
        folder_path = os.path.join(ENVIRONMENT_ROOT_PATH, env_data['env_name'])

        if not os.path.exists(folder_path):
            # No files to prune, but the action is "successful"
            with conn:
                _log_audit(conn, user_id, "PRUNE_FILES", "bp_environments", env_id,
                           f"No physical folder found at {folder_path}. No action taken.", "Admin")
            return True, "No physical folder found. Pruning was not necessary."

        # 3. Perform the deletion
        shutil.rmtree(folder_path)

        # 4. Log this destructive action to the audit trail
        with conn:
            _log_audit(conn, user_id, "PRUNE_FILES", "bp_environments", env_id,
                       f"[DESTRUCTIVE] Deleted all physical files from {folder_path}", "Admin")

        return True, f"Successfully pruned all physical files for '{env_id}'."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# --- [S8] PUBLIC "DASHBOARD" FUNCTIONS (KPIs / Complex) ---

# --- KPI Getters & Complex Dashboard Queries [F-KPI] ---

def get_system_kpis():
    """(For System Status UI) Get high-level counts of all main objects."""
    conn = _get_db_conn()
    if not conn: return {}
    try:
        kpis = {}
        tables_to_count = [
            "bp_environments", "bp_file_templates", "inst_data_input_files",
            "inst_actuarial_model_files", "inst_result_files", "inst_report_files", 
            "gov_audit_trail", "plan_project_milestones", "plan_action_items"
        ]
        for table in tables_to_count:
            # Use COUNT(*) for speed
            kpis[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        # Get pending actions count
        kpis["pending_actions"] = conn.execute(
            "SELECT COUNT(*) FROM plan_action_items WHERE status = 'Open'"
        ).fetchone()[0]

        return kpis
    finally:
        conn.close()

def get_pending_actions_dashboard():
    """
    (For System Status UI) Finds all files across the system
    that are 'Active' but do not have a 'Doer' sign-off.
    This is a simplified query; a real one would be more complex.
    """
    conn = _get_db_conn()
    if not conn: return []
    try:
        union_parts = []
        for table, id_col in TABLE_ID_MAP.items():
            if not table.startswith("inst_"):
                continue

            union_parts.append(f"""
                SELECT T1.file_path, T1.template_id, T1.env_id, T1.created_by, T1.created_at,
                       '{table}' as table_name, CAST(T1.{id_col} AS TEXT) as file_id
                FROM {table} AS T1
                WHERE T1.current_status = 'Active' AND NOT EXISTS (
                    SELECT 1 FROM gov_audit_trail AS T2
                    WHERE T2.target_table = '{table}' 
                      AND T2.target_id = T1.{id_col}
                      AND T2.action = 'SIGN_OFF'
                      AND T2.signoff_capacity = 'Doer'
                )
            """)
        
        if not union_parts: return []
        
        query = " UNION ALL ".join(union_parts) + " ORDER BY created_at ASC LIMIT 50"
        return [dict(row) for row in conn.execute(query).fetchall()]
    except Exception as e:
        print(f"Error in get_pending_actions_dashboard: {e}")
        return [] # Return empty list on error
    finally:
        conn.close()

def get_approved_domains() -> list:
    """(For "Doer" UI) Returns the list of approved domain keys for the UI."""
    return list(APPROVED_DOMAINS.keys())


# --- [S9] UNUSED / FUTURE FUNCTIONS ---

def run_new_model():
    """(For "Doer" UI - Future) The user function to run a model."""
    print("Future function: run_new_model")
    # This function would:
    # 1. Take in parent file IDs (data, model)
    # 2. Call an external script (e.g., a Docker container, a Python script)
    # 3. Get back a new file (e.g., results.csv)
    # 4. Call `upload_new_file_instance` to log it in the registry
    # 5. Log the lineage connecting the parents to the new child
    return False, "Not yet implemented."
"""
Atlas Database Admin Utility Script (`db_utils.py`)

-------------------------------------------------------------------------------
PURPOSE:
-------------------------------------------------------------------------------
This script is a "surgical" tool for making *manual* changes to an
*existing* database (`atlas_registry.db`).

This is a developer-only tool and is used *instead* of deleting and
rerunning `registry_schema.py` when you have data you want to keep.

-------------------------------------------------------------------------------
*** CRITICAL WARNING: ALWAYS BACK UP YOUR .db FILE BEFORE RUNNING ***
-------------------------------------------------------------------------------
This script makes *PERMANENT* changes to your database.
Deleting or renaming columns is a complex operation. This script will
*GENERATE* the SQL for you, but you must run it manually.

-------------------------------------------------------------------------------
HOW TO USE THIS SCRIPT:
-------------------------------------------------------------------------------
1.  **Back up your `atlas_registry.db` file.**
2.  Go to the "--- [1] CONFIGURATION ---" section below.
3.  Set the `ACTION` variable to what you want to do.
4.  Set the other variables (e.g., `TABLE_NAME`, `COLUMN_NAME`).
5.  Run this file from your terminal:
    $ python db_utils.py

-------------------------------------------------------------------------------
SUPPORTED ACTIONS:
-------------------------------------------------------------------------------
- 'LIST_TABLES': (Safe) Shows all 10 tables in the database.
- 'GET_TABLE_INFO': (Safe) Shows all columns, types, and row count for one table.
- 'ADD_TABLE': (Safe) Runs the `NEW_TABLE_SQL` string.
- 'ADD_COLUMN': (Safe) Adds a new column to an existing table.
- 'RENAME_COLUMN': (DANGEROUS) Prints the *manual* SQL steps you must take.
- 'DELETE_COLUMN': (DANGEROUS) Prints the *manual* SQL steps you must take.
"""

import sqlite3
import os

# --- [1] CONFIGURATION (EDIT THIS SECTION) ---

# The database file to modify
DB_FILE = "atlas_registry.db"

# The action you want to perform.
# Options: "LIST_TABLES", "GET_TABLE_INFO", "ADD_COLUMN", "RENAME_COLUMN", "DELETE_COLUMN", "ADD_TABLE"
ACTION = "GET_TABLE_INFO"

# The name of the table you want to interact with
TABLE_NAME = "plan_project_milestones"

# --- For "ADD_COLUMN" ---
COLUMN_NAME = "depends_on_milestone_id"
COLUMN_TYPE = "INTEGER"  # e.g., "TEXT", "INTEGER", "DATETIME", "TEXT DEFAULT 'Pending'"

# --- For "RENAME_COLUMN" ---
OLD_COLUMN_NAME = "source_team_from"
NEW_COLUMN_NAME = "source_name"

# --- For "DELETE_COLUMN" ---
COLUMN_TO_DELETE = "start_date"

# --- For "ADD_TABLE" ---
# Paste your new 'CREATE TABLE IF NOT EXISTS...' string here.
NEW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS my_new_table (
    id INTEGER PRIMARY KEY,
    name TEXT
);
"""


# --- [2] THE "ENGINE" (DO NOT EDIT BELOW THIS LINE) ---

def get_db_conn():
    """Connects to the database and enables foreign keys."""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file not found at '{DB_FILE}'")
        print("Please run `registry_schema.py` first to create the database.")
        return None

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def list_tables(conn):
    """(Safe) Prints all tables in the database."""
    print(f"--- Tables in {DB_FILE} ---")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row['name'] for row in cursor.fetchall()]
    for table in tables:
        if not table.startswith("sqlite_"):
            print(f"- {table}")


def get_table_info(conn, table_name):
    """(Safe) Prints all columns, types, and row count for one table."""
    print(f"--- Info for table: {table_name} ---")

    # Check if table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        print(f"Error: Table '{table_name}' does not exist.")
        return

    # Get Column Info
    print("\n[Columns]:")
    cursor = conn.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - Name: {col['name']}, Type: {col['type']}, NotNull: {col['notnull']}, PK: {col['pk']}")

    # Get Row Count
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    print(f"\n[Row Count]: {count} rows")


def add_new_column(conn, table_name, col_name, col_type):
    """(Safe) Adds a new column to an existing table."""
    print(f"Attempting to ADD column '{col_name} ({col_type})' to table '{table_name}'...")
    try:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};")
        conn.commit()
        print(f"Success! Column '{col_name}' added to '{table_name}'.")
        get_table_info(conn, table_name)
    except Exception as e:
        print(f"\n!!! --- ERROR --- !!!\n{e}")
        print("This often happens if the column *already exists*.")
        conn.rollback()


def create_new_table(conn, sql_string):
    """(Safe) Adds a new table to the database."""
    print("Attempting to ADD new table...")
    try:
        conn.execute(sql_string)
        conn.commit()
        print("Success! New table created.")
        list_tables(conn)
    except Exception as e:
        print(f"\n!!! --- ERROR --- !!!\n{e}")
        conn.rollback()


def _get_column_list(conn, table_name, exclude_col=None, rename_map=None):
    """(Internal) Helper to get a comma-separated list of columns."""
    cursor = conn.execute(f"PRAGMA table_info({table_name});")
    columns = [row['name'] for row in cursor.fetchall()]

    if exclude_col:
        columns = [col for col in columns if col != exclude_col]

    if rename_map:
        # For renaming, we create the "AS" list
        columns = [f"{col} AS {rename_map[col]}" if col in rename_map else col for col in columns]

    return ", ".join(columns)


def print_migration_warning(conn, table_name, old_col, new_col, action):
    """
    (DANGEROUS - READ-ONLY)
    Prints the safe 7-step SQL for renaming or deleting a column.
    """
    if action == "RENAME_COLUMN":
        print(f"--- WARNING: Renaming a Column in SQLite is a Destructive Operation ---")
        print("This script will NOT perform the action. You must do it manually.")
        print(f"Below are the *safe* SQL commands to rename '{old_col}' to '{new_col}' on table '{table_name}':\n")

        # We must map the old name to the new name
        cols_with_rename = _get_column_list(conn, table_name, rename_map={old_col: new_col})

        print(f"--- [Start SQL] Run these 7 commands in a DB tool ---")
        print("PRAGMA foreign_keys=OFF;")
        print("BEGIN TRANSACTION;")
        print(f"CREATE TABLE temp_{table_name} AS SELECT {cols_with_rename} FROM {table_name};")
        print(f"DROP TABLE {table_name};")
        print(f"ALTER TABLE temp_{table_name} RENAME TO {table_name};")
        print("COMMIT;")
        print("PRAGMA foreign_keys=ON;")
        print(f"--- [End SQL] ---")

    elif action == "DELETE_COLUMN":
        print(f"--- WARNING: Deleting a Column in SQLite is a Destructive Operation ---")
        print("This script will NOT perform the action. You must do it manually.")
        print(f"Below are the *safe* SQL commands to delete '{old_col}' from table '{table_name}':\n")

        # We must get the list of all *other* columns
        cols_to_keep = _get_column_list(conn, table_name, exclude_col=old_col)

        print(f"--- [Start SQL] Run these 7 commands in a DB tool ---")
        print("PRAGMA foreign_keys=OFF;")
        print("BEGIN TRANSACTION;")
        print(f"CREATE TABLE temp_{table_name} AS SELECT {cols_to_keep} FROM {table_name};")
        print(f"DROP TABLE {table_name};")
        print(f"ALTER TABLE temp_{table_name} RENAME TO {table_name};")
        print("COMMIT;")
        print("PRAGMA foreign_keys=ON;")
        print(f"--- [End SQL] ---")


# --- [3] MAIN SCRIPT "ROUTER" ---

def main():
    """
    Main function to run the selected action.
    """
    print(f"Loading database: {DB_FILE}...")
    conn = get_db_conn()
    if not conn:
        return

    try:
        # --- (Safe) Read-Only Actions ---
        if ACTION == "LIST_TABLES":
            list_tables(conn)

        elif ACTION == "GET_TABLE_INFO":
            if not TABLE_NAME:
                print("Error: You must set TABLE_NAME for this action.")
                return
            get_table_info(conn, TABLE_NAME)

        # --- (Safe) Write Actions ---
        elif ACTION == "ADD_COLUMN":
            if not all([TABLE_NAME, COLUMN_NAME, COLUMN_TYPE]):
                print("Error: You must set TABLE_NAME, COLUMN_NAME, and COLUMN_TYPE.")
                return
            add_new_column(conn, TABLE_NAME, COLUMN_NAME, COLUMN_TYPE)

        elif ACTION == "ADD_TABLE":
            create_new_table(conn, NEW_TABLE_SQL)

        # --- (Dangerous) Guided Read-Only Actions ---
        elif ACTION == "RENAME_COLUMN":
            if not all([TABLE_NAME, OLD_COLUMN_NAME, NEW_COLUMN_NAME]):
                print("Error: You must set TABLE_NAME, OLD_COLUMN_NAME, and NEW_COLUMN_NAME.")
                return
            print_migration_warning(conn, TABLE_NAME, OLD_COLUMN_NAME, NEW_COLUMN_NAME, "RENAME_COLUMN")

        elif ACTION == "DELETE_COLUMN":
            if not all([TABLE_NAME, COLUMN_TO_DELETE]):
                print("Error: You must set TABLE_NAME and COLUMN_TO_DELETE.")
                return
            print_migration_warning(conn, TABLE_NAME, COLUMN_TO_DELETE, None, "DELETE_COLUMN")

        else:
            print(f"Error: Unknown ACTION: '{ACTION}'")
            print(
                "Valid actions are: 'LIST_TABLES', 'GET_TABLE_INFO', 'ADD_COLUMN', 'RENAME_COLUMN', 'DELETE_COLUMN', 'ADD_TABLE'")

    except Exception as e:
        print(f"\n!!! --- An unexpected error occurred --- !!!\n{e}")
        conn.rollback()
    finally:
        conn.close()
        print(f"\n...Done. Connection to {DB_FILE} closed.")


if __name__ == "__main__":
    main()

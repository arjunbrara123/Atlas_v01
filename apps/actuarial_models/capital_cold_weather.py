"""
apps/actuarial/cold_weather_model.py

This is the user-facing "Interactive Workshop" for the
"🧪 Actuarial Models" stage of the workflow.

-------------------------------------------------------------------------------
PURPOSE & "LAB NOTEBOOK" WORKFLOW:
-------------------------------------------------------------------------------
This dashboard is a secure, auditable "Lab Notebook" for actuaries to
run the Cold Weather Capital (GLM) Model. It fully integrates the
domain-specific logic from `data_loader.py` with the Atlas
governance framework.

It features a "Smart Setup" process to guide users, an auto-saving
workshop, and a "one-stop-shop" for finalizing and signing off results.

-------------------------------------------------------------------------------
CRITICAL PREREQUISITES (READ FIRST)
-------------------------------------------------------------------------------
This dashboard is a "UI" file. It WILL NOT WORK until its "Engine"
and "Blueprint" dependencies are met in the Atlas platform.

[1] REQUIRED FILE BLUEPRINTS:
This app requires 4 File Blueprints to exist in the registry.
The app's "Setup" screen (which appears on first launch) will
help you install these.

    1. ACT_CWC_MODEL_RUN (Model "Save File")
    2. ACT_CWC_RESULT (Model "Output File")
    3. DATA_MET_OFFICE_TEMPS (Input Data)
    4. DATA_DEMAND (Input Data)

[2] REQUIRED 'registry_service.py' FUNCTIONS:
This UI calls "Engine" functions. It assumes the following
functions (which we have been building) exist in registry_service.py.

    # For Setup:
    1. create_file_blueprint(form_data, user_id)

    # For Loading Data:
    2. get_all_files_for_template(env_id, template_id, user_id)
    3. get_approved_files_for_blueprint(env_id, template_id)
    4. get_file_by_id(table_name, file_id)
    5. get_lineage_for_file(table_name, file_id)
    6. get_finalized_results_for_template(env_id, template_id)
    7. get_parent_model_run(result_file_id)
    8. get_file_preview(file_path, expected_hash)
    9. get_all_file_blueprints()

    # For Writing Data:
    10. create_draft_model_file(...)
    11. create_lineage(...)
    12. update_model_file_parameters(...)
    13. run_and_save_model_result(...)
-------------------------------------------------------------------------------
"""

# --- [FIX] Add Project Root to Python Path ---
import sys
import os

from apps.actuarial_models import data_loader

# This finds the root "Commercial_And_Risk_Platform_v01" folder and adds it
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# -----------------------------------------------

import streamlit as st
import registry_service  # <-- The "Engine"
from datetime import datetime
import pandas as pd
import numpy as np
import json
import io

# --- Model & Calculation Dependencies ---
# We are including simplified, functional stubs for calcs/charts
# to make this file self-contained and runnable.
import statsmodels.api as sm
from scipy.stats import lognorm
import plotly.express as px

# -----------------------------------------------------------------------------
# [STUB] CALCULATION FUNCTIONS
# (This logic would be in a `common/calcs.py` file)
# -----------------------------------------------------------------------------

def calcs_build_design_matrix(df, predictors):
    """Builds the X matrix for the GLM."""
    X = df[predictors]
    if 'Weekend' in predictors:
        X = pd.get_dummies(X, columns=['Weekend'], drop_first=True)
    return X

def calcs_fit_poisson_glm(X, y):
    """Fits the Poisson GLM and returns the model."""
    try:
        X_with_const = sm.add_constant(X, prepend=True)
        glm_poisson = sm.GLM(y, X_with_const, family=sm.families.Poisson())
        model = glm_poisson.fit()
        return model
    except Exception as e:
        st.error(f"GLM Fit Error: {e}")
        return None

def calcs_calculate_monthly_aggregate(temp_df, model, predictors):
    """Simulates claims based on historical temps and fitted model."""
    X = calcs_build_design_matrix(temp_df, predictors)
    X_with_const = sm.add_constant(X, prepend=True)
    temp_df['Predicted_Freq'] = model.predict(X_with_const)
    temp_df['Month'] = temp_df['Date'].dt.month
    monthly_agg = temp_df.groupby('Month')['Predicted_Freq'].sum().reset_index()
    return monthly_agg

def calcs_fit_lognormal(data):
    """Fits a lognormal distribution to the simulated data."""
    shape, loc, scale = lognorm.fit(data, floc=0)
    return shape, loc, scale

def calcs_percentile_lognormal(shape, loc, scale, percentile=99.5):
    """Gets the 99.5th percentile from the fitted distribution."""
    return lognorm.ppf(percentile / 100.0, shape, loc=loc, scale=scale)

# -----------------------------------------------------------------------------
# [STUB] CHARTING FUNCTIONS
# (This logic would be in a `common/charts.py` file)
# -----------------------------------------------------------------------------

def charts_plot_actual_vs_predicted(y_actual, y_fitted, title):
    """Plots actual vs. fitted values."""
    df = pd.DataFrame({'Actual': y_actual, 'Fitted': y_fitted}).reset_index()
    df_melted = df.melt('index', var_name='Type', value_name='Frequency')

    fig = px.line(df_melted, x='index', y='Frequency', color='Type', title=title)
    st.plotly_chart(fig, use_container_width=True)

def charts_plot_simulation_histogram(data, scr_value, title):
    """Plots the histogram of simulated results."""
    fig = px.bar(data, x='Month', y='Predicted_Freq', title=title)
    fig.add_hline(y=scr_value, line_dash="dash", line_color="red", annotation_text=f"99.5th Percentile: {scr_value:,.0f}")
    st.plotly_chart(fig, use_container_width=True)

def charts_plot_winter_comparison_boxplot(recent, prev10, value_col="Value", title="Winter Temperature Distribution", xaxis_title="Temperature", winter_months=None):
    """Plots a boxplot comparing recent vs. historical data."""
    if winter_months:
        winter_months_str = [datetime(1900,m,1).strftime("%b") for m in winter_months]
        recent = recent[recent['Month_Name'].isin(winter_months_str)]
        prev10 = prev10[prev10['Month_Name'].isin(winter_months_str)]

    recent['Period'] = f'Recent ({recent["Year"].min()})'
    prev10['Period'] = f'Historical ({prev10["Year"].min()}-{prev10["Year"].max()})'
    df = pd.concat([recent, prev10])

    fig = px.box(df, x=value_col, y="Period", orientation='h', title=title, labels={value_col: xaxis_title})
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# DATA LOADING FUNCTIONS (CACHED)
# -----------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_model_runs(env_id, template_id, user_id):
    """(Cached) Gets all Model Runs for this user in this environment."""
    try:
        return registry_service.get_all_files_for_template(
            env_id=env_id, template_id=template_id, user_id=user_id
        )
    except Exception as e:
        st.error(f"Error loading model runs: {e}")
        return []

@st.cache_data(ttl=300)
def get_approved_data_files(env_id, template_id):
    """(Cached) Gets all "Fully Approved" data files for dropdowns."""
    try:
        return registry_service.get_approved_files_for_blueprint(
            env_id=env_id, template_id=template_id
        )
    except Exception as e:
        st.error(f"Error loading approved data for {template_id}: {e}")
        return []

@st.cache_data(ttl=300)
def get_processed_input_data(file_path: str, expected_hash: str, data_type: str):
    """
    (Cached) Safely loads and processes a file from the registry.
    Uses simple, hashable arguments for caching.
    """
    try:
        # --- 1. Get Full Path & Validate Hash ---
        full_path = os.path.join(registry_service.ENVIRONMENT_ROOT_PATH, file_path)

        if not os.path.exists(full_path):
            return None, f"File not found on disk at: {file_path}"

        preview = registry_service.get_file_preview(file_path, expected_hash)
        if preview['type'] == 'error':
            return None, preview['data'] # Pass on "TAMPERING DETECTED"

        # --- 2. Run data_loader logic ---
        if data_type == 'temp':
            raw_df, aug_df = data_loader.load_temperature_data(full_path)
            return aug_df, None
        elif data_type == 'demand':
            raw_df, aug_df = data_loader.load_demand_data(full_path)
            return aug_df, None

        return None, "Unknown data type."

    except Exception as e:
        st.error(f"Error loading file data: {e}")
        return None, str(e)

@st.cache_data(ttl=300)
def get_finalized_scr_results(env_id, result_template_id):
    """(Cached) Gets all finalized SCR results for the Comparison Workbench."""
    try:
        return registry_service.get_all_files_for_template(
            env_id=env_id,
            template_id=result_template_id,
            user_id=None # Get all users
        )
    except Exception as e:
        st.error(f"Error loading finalized results: {e}")
        return []

@st.cache_data(ttl=300)
def get_blueprint_map():
    """(Cached) Gets all blueprints as a dictionary for the prereq check."""
    try:
        all_bps_list = registry_service.get_all_file_blueprints()
        return {bp['template_id']: bp for bp in all_bps_list}
    except Exception as e:
        st.error(f"Error in get_blueprint_map: {e}")
        return {}

# --- Streamlit Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        """Initializes the Page object."""
        self.role = role
        self.env_id = environment
        self.user_id = (st.session_state.get("user") or {}).get("email", "admin@company.com")

        self.table_name_model = "inst_actuarial_model_files"
        self.id_col_model = "model_run_id"
        self.table_name_data = "inst_data_input_files"
        self.id_col_data = "data_file_id"
        self.table_name_result = "inst_result_files"
        self.id_col_result = "result_file_id"

        # --- Blueprint Prerequisites ---
        self.template_id_model = "ACT_CWC_MODEL_RUN"
        self.template_id_result = "ACT_CWC_RESULT"
        self.template_id_temp = "DATA_MET_OFFICE_TEMPS"
        self.template_id_demand = "DATA_DEMAND"

        self.all_required_blueprints = [
            self.template_id_model, self.template_id_result,
            self.template_id_temp, self.template_id_demand
        ]

        self.meta = {
            "title_override": f"Cold Weather Capital Model ({self.env_id})",
            "owner": "Actuarial Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # --- Initialize Session State ---
        if 'current_model_run_id' not in st.session_state:
            st.session_state.current_model_run_id = None
        if 'current_model_run_data' not in st.session_state:
            st.session_state.current_model_run_data = {}
        if 'loaded_input_dfs' not in st.session_state:
            st.session_state.loaded_input_dfs = {}
        if 'loaded_input_links' not in st.session_state:
            st.session_state.loaded_input_links = {}
        if 'newly_finalized_result_id' not in st.session_state:
            st.session_state.newly_finalized_result_id = None

        self.refresh_data()

    def refresh_data(self):
        """Loads all data needed for the app."""
        self.all_blueprints_map = get_blueprint_map()
        self.model_runs = get_model_runs(self.env_id, self.template_id_model, self.user_id)
        self.approved_temps = get_approved_data_files(self.env_id, self.template_id_temp)
        self.approved_demands = get_approved_data_files(self.env_id, self.template_id_demand)

    def _set_active_run(self, model_run_id):
        """Loads a selected model run into session state."""
        run_data = next((r for r in self.model_runs if r[self.id_col_model] == model_run_id), {})
        st.session_state.current_model_run_id = model_run_id
        st.session_state.current_model_run_data = run_data
        st.session_state.loaded_input_dfs = {}
        st.session_state.newly_finalized_result_id = None

        links = registry_service.get_lineage_for_file(self.table_name_model, model_run_id)
        st.session_state.loaded_input_links = {
            'temp': links.get(self.template_id_temp),
            'demand': links.get(self.template_id_demand),
        }

    # --- TAB 1: USER GUIDE & SETUP ---
    def _render_user_guide_tab(self):
        st.subheader("📚 User Guide & Prerequisites")

        st.markdown("### How to Use This 'Lab Notebook'")
        st.markdown(
            """
            This dashboard is an auditable workshop for running the Cold Weather Capital Model.
            
            1.  **Tab 2: Model Run Instance**
                - You must start here. A "Model Run" is your "save file."
                - **Create a New Run** and give it a name (e.g., "YE 2025 - Test 1").
                - Or, **Load an Existing Run** to continue your work.
            
            2.  **Tab 3: Select Data Inputs**
                - Once a run is loaded, use the dropdowns to select the **Approved** data files from the Atlas registry.
                - Click **"Load & Link Data"** for each file. This creates a permanent *lineage link* and runs the validation checks from `data_loader.py`.
            
            3.  **Tab 4: Parameters & GLM Workshop**
                - This is your interactive workbench.
                - All changes you make (e.g., to "Avg Cost" or "GLM Predictors") are **auto-saved** to your "Model Run" file.
                - Apply the GWA Adjustment and select your predictors to fit the GLM live.
            
            4.  **Tab 5: Finalize & Sign-Off**
                - When you are happy with your model, go to this tab.
                - Click **"Finalize & Save Result to Atlas"**. This saves your SCR calculation as a new, official "Result File" in Atlas.
                - You will then be asked to **"Sign Off as Doer"** in the same screen. This submits your result to a Reviewer.
            
            5.  **Tab 6: Comparison Workbench**
                - Use this read-only tool to compare any two *finalized* results you have created in the past.
            """
        )
        st.markdown("---")
        st.markdown("### Setup & Prerequisites")
        st.warning(
            "This Model Workshop requires **4 File Blueprints** to be created in the "
            "**File Blueprint Manager** before it can be used."
        )
        st.markdown(
            "This app can **auto-install** all 4 blueprints for you. "
            "Please review the settings in each expander on the **'Setup'** screen (if visible) "
            "and click **Install** for each missing blueprint."
        )

    # --- "SETUP" SCREEN (This is not a tab) ---
    def _render_setup_screen(self, missing_blueprints):
        """
        This function is called *instead* of the tabs if
        prerequisites are not met.
        """
        st.subheader("🚀 Model Setup Required")
        st.warning(
            f"The **Cold Weather Capital Model** is not yet configured for this environment. "
            f"Please install the required File Blueprints below."
        )
        st.markdown("---")

        # --- "Nice Looking" Status Check ---
        st.markdown("##### Prerequisite Status Check")
        st.caption("This app requires 4 blueprints to exist in the registry. The status of each is listed below.")

        # We use st.columns to create a clean, grid-like layout
        cols = st.columns(4)
        status_map = {
            self.template_id_model: cols[0],
            self.template_id_result: cols[1],
            self.template_id_temp: cols[2],
            self.template_id_demand: cols[3],
        }

        for bp_id in self.all_required_blueprints:
            with status_map[bp_id]:
                if bp_id in missing_blueprints:
                    st.error(f"**Missing**\n`{bp_id}`")
                else:
                    st.success(f"**Found**\n`{bp_id}`")
        st.markdown("---")

        # --- Helper function to install a blueprint ---
        def _install_blueprint(form_data):
            try:
                # We call the *existing* engine function
                success, msg = registry_service.create_file_blueprint(form_data, self.user_id)
                if success:
                    st.success(f"Successfully installed: {form_data['template_id']}")
                    st.rerun()
                else:
                    if "UNIQUE constraint failed" in msg:
                        st.info(f"{form_data['template_id']} is already installed.")
                        st.rerun()
                    else:
                        st.error(f"Failed to install {form_data['template_id']}: {msg}")
            except Exception as e:
                st.error(f"Failed to install {form_data['template_id']}: {e}")

        # --- 1. Model Run Blueprint ---
        with st.expander(f"**Action: Install `{self.template_id_model}`** (Model 'Save File')"):
            st.markdown("This is the 'virtual' blueprint for this app's 'Lab Notebook' save file. It holds your saved parameters.")
            if self.template_id_model in missing_blueprints:
                if st.button("Install `ACT_CWC_MODEL_RUN`"):
                    bp_run_data = {
                        "template_id": self.template_id_model,
                        "template_name": "Cold Weather Model Run (Lab Notebook)",
                        "stage": "Actuarial Models", "data_owner_team": "Actuarial",
                        "source_type": "Internal", "signoff_workflow": "Doer Only",
                        "doer_roles": "admin,developer,actuarial", "reviewer_roles": "admin",
                        "expected_extension": ".json", "primary_key_column": "",
                        "purpose": "Virtual save file for the CWC Model Workshop. App-generated."
                    }
                    _install_blueprint(bp_run_data)
            else:
                st.success(f"`{self.template_id_model}` is already installed.")

        # --- 2. Model Result Blueprint ---
        with st.expander(f"**Action: Install `{self.template_id_result}`** (Model 'Output File')"):
            st.markdown("This is the blueprint for the *final output file* of this model (the .csv report).")
            if self.template_id_result in missing_blueprints:
                if st.button("Install `ACT_CWC_RESULT`"):
                    bp_result_data = {
                        "template_id": self.template_id_result,
                        "template_name": "Cold Weather Model (Final SCR Result)",
                        "stage": "Results & Validation", "data_owner_team": "Actuarial",
                        "source_type": "Internal", "signoff_workflow": "Doer + Reviewer",
                        "doer_roles": "admin,developer,actuarial", "reviewer_roles": "admin,actuarial",
                        "expected_extension": ".csv", "primary_key_column": "",
                        "purpose": "Final calculated SCR from the CWC Model. App-generated."
                    }
                    _install_blueprint(bp_result_data)
            else:
                st.success(f"`{self.template_id_result}` is already installed.")

        # --- 3. Data - Temps Blueprint ---
        with st.expander(f"**Action: Install `{self.template_id_temp}`** (Data Input)"):
            st.markdown(
                "This blueprint is for the **raw temperature data**. This "
                "is an 'External Connection' file that must be set up correctly."
            )
            st.markdown("**Settings to be installed:**")
            st.json({
                "template_id": self.template_id_temp,
                "source_type": "External Connection",
                "source_name": "MET_OFFICE_HADLEY",
                "source_specifier": "meantemp_daily_totals.txt",
                "expected_extension": ".txt",
                "expected_structure": '{"columns": ["Date", "Value"]}',
                "primary_key_column": "Date"
            })
            if self.template_id_temp in missing_blueprints:
                if st.button(f"Install `{self.template_id_temp}`"):
                    bp_temp_data = {
                        "template_id": self.template_id_temp,
                        "template_name": "Met Office Temperature Data",
                        "stage": "Data Inputs", "data_owner_team": "Actuarial",
                        "source_type": "External Connection",
                        "source_name": "MET_OFFICE_HADLEY",
                        "source_specifier": "meantemp_daily_totals.txt",
                        "expected_extension": ".txt",
                        "expected_structure": json.dumps({"columns": ["Date", "Value"]}),
                        "primary_key_column": "Date",
                        "purpose": "Daily historical temperature data from the Met Office."
                    }
                    _install_blueprint(bp_temp_data)
            else:
                st.success(f"`{self.template_id_temp}` is already installed.")

        # --- 4. Data - Demand Blueprint ---
        with st.expander(f"**Action: Install `{self.template_id_demand}`** (Data Input)"):
            st.markdown(
                "This blueprint is for the **raw claims data**. This "
                "is an 'Internal' file that must be uploaded."
            )
            st.markdown("**Settings to be installed:**")
            st.json({
                "template_id": self.template_id_demand,
                "source_type": "Internal",
                "expected_extension": ".csv",
                "expected_structure": '{"columns": ["Date", "ClaimFreq"]}',
                "primary_key_column": "Date"
            })
            if self.template_id_demand in missing_blueprints:
                if st.button(f"Install `{self.template_id_demand}`"):
                    bp_demand_data = {
                        "template_id": self.template_id_demand,
                        "template_name": "Claims Demand Data",
                        "stage": "Data Inputs", "data_owner_team": "Actuarial",
                        "source_type": "Internal",
                        "expected_extension": ".csv",
                        "expected_structure": json.dumps({"columns": ["Date", "ClaimFreq"]}),
                        "primary_key_column": "Date",
                        "purpose": "Daily historical claims frequency."
                    }
                    _install_blueprint(bp_demand_data)
            else:
                st.success(f"`{self.template_id_demand}` is already installed.")

        st.markdown("---")
        st.markdown("Once all 4 blueprints are installed, please refresh this page.")
        if st.button("Refresh Page"):
            st.rerun()

    # --- TAB 2: MODEL RUN INSTANCE (The "Lab Notebook") ---
    def _render_instance_tab(self):
        st.subheader("📓 Model Run Instance")
        st.markdown("This is your 'Lab Notebook.' You must create a new run or load an existing run to begin.")

        st.markdown("##### Load Existing Model Run")
        draft_runs = [r for r in self.model_runs if r['current_status'] == 'Pending']
        run_map = {r[self.id_col_model]: r.get('file_path', f"Run {r[self.id_col_model]}") for r in draft_runs}

        selected_id = st.selectbox(
            "Select a draft run to continue working on:",
            options=[None] + list(run_map.keys()),
            format_func=lambda x: "Select a run..." if x is None else run_map[x],
            key="load_run_select"
        )

        if st.button("Load Selected Run"):
            if selected_id:
                self._set_active_run(selected_id)
                st.rerun()

        st.markdown("---")
        with st.form("create_new_run_form"):
            st.markdown("##### Create New Model Run")
            run_name = st.text_input("New Run Name", f"Cold Weather Run - {datetime.now().strftime('%Y-%m-%d')}")
            justification = st.text_area("Purpose / Justification", "Initial run for YE 2025.")

            submitted = st.form_submit_button("Create New Run")
            if submitted:
                if not run_name or not justification:
                    st.error("Name and Justification are required.")
                else:
                    with st.spinner("Creating new model run..."):
                        success, result_data = registry_service.create_draft_model_file(
                            env_id=self.env_id, user_id=self.user_id,
                            user_role=self.role, template_id=self.template_id_model,
                            run_name=run_name, justification=justification
                        )
                        if success:
                            st.success(f"Created new run: {run_name}")
                            self.model_runs.append(result_data)
                            self._set_active_run(result_data[self.id_col_model])
                            st.rerun()
                        else:
                            st.error(f"Failed to create run: {result_data}")

    # --- TAB 3: SELECT DATA INPUTS (The "Ingredients") ---
    def _render_inputs_tab(self):
        st.subheader("📚 Select Data Inputs")
        if not st.session_state.current_model_run_id:
            st.info("Please create or load a Model Run in `Tab 2` to begin.")
            return

        st.success(f"Working in Run: **{st.session_state.current_model_run_data.get('file_path', '...')}**")
        st.markdown("Select the **approved** data files from the Atlas registry to link to this model run.")

        def _link_and_load_data(data_type_key, file_id_str, file_list, table_name):
            if not file_id_str:
                st.session_state.loaded_input_dfs[data_type_key] = None
                return
            file_id = int(file_id_str)
            model_run_id = st.session_state.current_model_run_id

            success, msg = registry_service.create_lineage(
                parent_table=table_name, parent_id=file_id,
                child_table=self.table_name_model, child_id=model_run_id
            )
            if not success:
                st.error(f"Failed to link data: {msg}"); return

            file_info = next((f for f in file_list if f[self.id_col_data] == file_id), None)
            if not file_info:
                st.error("Could not find file info."); return

            aug_df, err = get_processed_input_data(
                file_info['file_path'],
                file_info['file_hash_sha256'],
                data_type_key
            )
            if err:
                st.error(f"Failed to load/process data: {err}")
                st.session_state.loaded_input_dfs[data_type_key] = None
            else:
                st.success(f"Linked & Processed File ID: {file_id}")
                st.session_state.loaded_input_dfs[data_type_key] = aug_df

        links = st.session_state.loaded_input_links

        st.markdown("##### 1. Met Office Temperature Data")
        temp_map = {f[self.id_col_data]: f"{f['created_at'].split('T')[0]} - {f['created_by']}" for f in self.approved_temps}
        if not temp_map:
            st.error(f"**Data Missing:** No approved '{self.template_id_temp}' files found. Please go to the Data Workspace, run the 'External Connection' job, and get the file signed off.")
            return

        selected_temp_id = st.selectbox(
            "Select Temperature File",
            options=[None] + list(temp_map.keys()),
            format_func=lambda x: "Select..." if x is None else temp_map[x],
            key="select_temp",
            index=([None] + list(temp_map.keys())).index(links.get(self.template_id_temp))
        )
        if st.button("Load & Link Temperature Data"):
            _link_and_load_data('temp', selected_temp_id, self.approved_temps, self.table_name_data)

        if 'temp' in st.session_state.loaded_input_dfs and st.session_state.loaded_input_dfs['temp'] is not None:
            st.success("Temperature Data is Loaded.")
            df_tmp = st.session_state.loaded_input_dfs['temp']
            latest_year = datetime.now().year - 1
            charts_plot_winter_comparison_boxplot(
                df_tmp[df_tmp['Year'] == latest_year],
                df_tmp[df_tmp['Year'] < latest_year]
            )

        st.markdown("##### 2. Demand Data")
        demand_map = {f[self.id_col_data]: f"{f['created_at'].split('T')[0]} - {f['created_by']}" for f in self.approved_demands}
        if not demand_map:
            st.error(f"**Data Missing:** No approved '{self.template_id_demand}' files found. Please go to the Data Workspace, upload one, and get it signed off.")
            return

        selected_demand_id = st.selectbox(
            "Select Demand File",
            options=[None] + list(demand_map.keys()),
            format_func=lambda x: "Select..." if x is None else demand_map[x],
            key="select_demand",
            index=([None] + list(demand_map.keys())).index(links.get(self.template_id_demand))
        )
        if st.button("Load & Link Demand Data"):
            _link_and_load_data('demand', selected_demand_id, self.approved_demands, self.table_name_data)

        if 'demand' in st.session_state.loaded_input_dfs and st.session_state.loaded_input_dfs['demand'] is not None:
            st.success("Demand Data is Loaded.")
            df_demand = st.session_state.loaded_input_dfs['demand']
            ly = df_demand['Date'].dt.year.max()
            charts_plot_winter_comparison_boxplot(
                df_demand[df_demand['Date'].dt.year == ly],
                df_demand[df_demand['Date'].dt.year < ly],
                value_col="ClaimFreq", title="Claims Frequency Distribution", xaxis_title="Claim Freq"
            )

    # --- TAB 4: PARAMETERS & GLM WORKSHOP (The "Experiment") ---
    def _render_workshop_tab(self):
        st.subheader("🔬 Parameters & GLM Workshop")
        if not st.session_state.current_model_run_id:
            st.info("Please create or load a Model Run in `Tab 2` to begin."); return
        if not all(k in st.session_state.loaded_input_dfs for k in ['temp', 'demand']):
            st.warning("Please load all 2 data inputs in `Tab 3` to run the GLM."); return

        def _save_parameters():
            params = {
                'gwa_toggle': st.session_state.get('param_gwa_toggle', True),
                'winter_months': st.session_state.get('param_winter_months', [1, 2, 3, 11, 12]),
                'avg_cost_prev': st.session_state.get('param_avg_cost_prev', 100.0),
                'avg_cost': st.session_state.get('param_avg_cost', 123.0),
                'avg_holdings_prev': st.session_state.get('param_avg_holdings_prev', 6000),
                'avg_holdings': st.session_state.get('param_avg_holdings', 6100),
                'glm_predictors': st.session_state.get('param_glm_predictors', ['Temperature', 'Cold_Spell'])
            }
            registry_service.update_model_file_parameters(
                st.session_state.current_model_run_id,
                json.dumps(params)
            )
            st.session_state.current_model_run_data['parameters_json'] = json.dumps(params)
            st.toast("Parameters auto-saved.", icon="💾")

        try:
            params = json.loads(st.session_state.current_model_run_data.get('parameters_json') or '{}')
        except:
            params = {}

        st.markdown("##### Model Parameters (Auto-Saves on Change)")
        with st.container(border=True):
            st.toggle("Apply Global Warming Adjustment (GWA)", value=params.get('gwa_toggle', True), key='param_gwa_toggle', on_change=_save_parameters)
            st.multiselect(
                "☃️ Winter Months (for GWA & Validation Charts)",
                options=[1,2,3,4,5,6,7,8,9,10,11,12],
                default=params.get('winter_months', [1, 2, 3, 11, 12]),
                key='param_winter_months',
                on_change=_save_parameters
            )
            c1, c2 = st.columns(2)
            c1.number_input("🏭 Previous Avg Cost", 0.0, 1e6, params.get('avg_cost_prev', 100.0), 1.0, key='param_avg_cost_prev', on_change=_save_parameters)
            c1.number_input("🏢 Current Avg Cost", 0.0, 1e6, params.get('avg_cost', 123.0), 1.0, key='param_avg_cost', on_change=_save_parameters)
            c2.number_input("🏭 Prev YE Holdings", 0, 1_000_000, params.get('avg_holdings_prev', 6000), 1, key='param_avg_holdings_prev', on_change=_save_parameters)
            c2.number_input("🏢 Curr YE Holdings", 0, 1_000_000, params.get('avg_holdings', 6100), 1, key='param_avg_holdings', on_change=_save_parameters)

        st.markdown("##### GLM Workshop")
        with st.container(border=True):
            temp_df = st.session_state.loaded_input_dfs['temp']
            demand_df = st.session_state.loaded_input_dfs['demand']

            if st.session_state.param_gwa_toggle:
                temp_df_adj = data_loader.GWA_adjustment(
                    temp_df,
                    winter_toggle=True,
                    winter_months=st.session_state.param_winter_months
                )
            else:
                temp_df_adj = temp_df.copy()
                temp_df_adj['Temperature'] = temp_df_adj['Value'] # Use unadjusted

            merged = pd.merge(demand_df, temp_df_adj, on='Date', how='inner')
            # 'Weekend' and 'Cold_Spell' are from data_loader

            vars_ = ['Temperature', 'Temp_Lag_1_Day', 'Cold_Spell', 'Weekend']
            st.multiselect(
                "Select GLM Predictors",
                vars_,
                default=params.get('glm_predictors', ['Temperature', 'Cold_Spell']),
                key='param_glm_predictors',
                on_change=_save_parameters
            )

            predictors = st.session_state.param_glm_predictors
            if predictors:
                missing_preds = [p for p in predictors if p not in merged.columns]
                if missing_preds:
                    st.error(f"Error: Predictor(s) not found in data: {', '.join(missing_preds)}")
                else:
                    X = calcs_build_design_matrix(merged, predictors)
                    y = merged['ClaimFreq']
                    model = calcs_fit_poisson_glm(X, y)
                    if model:
                        st.session_state.glm_model = model
                        st.subheader("GLM Coefficients")
                        st.dataframe(model.params.to_frame("Coefficient"))
                        charts_plot_actual_vs_predicted(y, model.fittedvalues, "Actual vs. Fitted")
            else:
                st.info("Select at least one predictor to fit the GLM.")

    # --- TAB 5: FINALIZE & SIGN-OFF (The "One-Stop-Shop") ---
    def _render_finalize_tab(self):
        st.subheader("🏁 Run, Finalize & Sign-Off")
        if not st.session_state.current_model_run_id:
            st.info("Please create or load a Model Run in `Tab 2` to begin."); return
        if not st.session_state.get('glm_model'):
            st.warning("Please fit a GLM in `Tab 4` to run the final calculation."); return

        model_run_data = st.session_state.current_model_run_data

        if model_run_data.get('final_result_id'):
            st.info(f"This model run has already been finalized and saved as Result File ID: {model_run_data['final_result_id']}")
            return

        if st.session_state.newly_finalized_result_id:
            self._render_doer_signoff_form(st.session_state.newly_finalized_result_id)
            return

        st.markdown("##### Final SCR Calculation")

        try:
            model = st.session_state.glm_model
            params = json.loads(model_run_data.get('parameters_json') or '{}')
            predictors = params.get('glm_predictors', [])
            temp_df_aug = st.session_state.loaded_input_dfs['temp']

            if params.get('gwa_toggle', True):
                temp_df_adj = data_loader.GWA_adjustment(
                    temp_df_aug,
                    winter_toggle=True,
                    winter_months=params.get('winter_months', [])
                )
            else:
                temp_df_adj = temp_df_aug.copy()
                temp_df_adj['Temperature'] = temp_df_adj['Value']

            monthly_agg = calcs_calculate_monthly_aggregate(temp_df_adj, model, predictors)
            shape, loc, scale = calcs_fit_lognormal(monthly_agg['Predicted_Freq'])
            scr_99_5 = calcs_percentile_lognormal(shape, loc, scale, 99.5)
            final_cost = scr_99_5 * params.get('avg_cost', 0) * params.get('avg_holdings', 0)

            st.session_state.final_scr_cost = final_cost

            st.metric("Final 99.5% SCR (Full Year)", f"£ {final_cost:,.0f}")
            charts_plot_simulation_histogram(monthly_agg.set_index('Month'), scr_99_5, "Simulated Monthly Claim Frequency")

            if st.button("Finalize & Save Result to Atlas"):
                with st.spinner("Saving final result to registry..."):
                    result_data = {
                        'scr_99_5': scr_99_5, 'final_cost': final_cost,
                        'shape': shape, 'loc': loc, 'scale': scale,
                        'monthly_agg': monthly_agg.to_dict()
                    }
                    success, new_result_file = registry_service.run_and_save_model_result(
                        env_id=self.env_id, user_id=self.user_id,
                        user_role=self.role, model_run_id=st.session_state.current_model_run_id,
                        result_template_id=self.template_id_result,
                        result_data=result_data
                    )
                    if success:
                        st.success("Result file saved to registry!")
                        st.session_state.newly_finalized_result_id = new_result_file[self.id_col_result]
                        st.rerun()
                    else:
                        st.error(f"Failed to save result: {new_result_file}")

        except Exception as e:
            st.error(f"Failed to run final calculation: {e}")

    def _render_doer_signoff_form(self, result_file_id):
        """Renders the "Doer Sign-off" form directly in this app."""
        st.success(f"Result File (ID: `{result_file_id}`) has been created and is awaiting your 'Doer' sign-off.")
        st.markdown("Please provide a final comment for the audit trail to submit this to the Reviewer.")

        with st.form("doer_signoff_form"):
            comment = st.text_area(
                "Doer Sign-off Comment",
                f"I have run the {st.session_state.current_model_run_data['file_path']} model. "
                f"The final SCR is £ {st.session_state.get('final_scr_cost', 0):,.0f}. "
                f"This is ready for review."
            )
            submitted = st.form_submit_button("Sign Off and Submit for Review")

            if submitted:
                if not comment:
                    st.error("A sign-off comment is mandatory."); return

                with st.spinner("Logging sign-off..."):
                    success, message = registry_service.log_user_signoff(
                        user_id=self.user_id, user_role=self.role,
                        target_table=self.table_name_result,
                        target_id=result_file_id, action="SIGN_OFF",
                        capacity="Doer", comment=comment
                    )
                    if success:
                        st.success("Sign-off complete! This run is now submitted for review.")
                        st.session_state.current_model_run_id = None
                        st.session_state.current_model_run_data = {}
                        st.session_state.loaded_input_dfs = {}
                        st.session_state.newly_finalized_result_id = None
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(message)

    # --- TAB 6: COMPARISON WORKBENCH (The "What-If") ---
    def _render_comparison_tab(self):
        st.subheader("📊 Comparison Workbench")
        st.markdown("Select any two **finalized** model runs to compare their inputs, parameters, and results.")

        final_results = get_finalized_scr_results(self.env_id, self.template_id_result)

        if not final_results:
            st.info("No finalized results found to compare."); return

        result_map = {}
        for res in final_results:
            try:
                model_run = registry_service.get_parent_model_run(res[self.id_col_result])
                if model_run:
                    res['parameters'] = json.loads(model_run.get('parameters_json', '{}'))
                    res['run_name'] = model_run.get('file_path', 'N/A')
                    result_map[res[self.id_col_result]] = res
            except Exception as e:
                print(f"Error loading comparison data: {e}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### Compare Run A:")
            run_a_id = st.selectbox(
                "Select Run A",
                options=[None] + list(result_map.keys()),
                format_func=lambda x: "Select..." if x is None else f"{result_map.get(x,{}).get('run_name','N/A')} (ID: {x})",
                key="compare_a"
            )
        with col2:
            st.markdown("##### Against Run B:")
            run_b_id = st.selectbox(
                "Select Run B",
                options=[None] + list(result_map.keys()),
                format_func=lambda x: "Select..." if x is None else f"{result_map.get(x,{}).get('run_name','N/A')} (ID: {x})",
                key="compare_b"
            )

        st.markdown("---")

        if run_a_id and run_b_id:
            if run_a_id == run_b_id:
                st.warning("Please select two different runs to compare."); return

            run_a_data = result_map.get(run_a_id)
            run_b_data = result_map.get(run_b_id)

            if not run_a_data or not run_b_data:
                st.error("Could not load data for one or both runs."); return

            col1, col2 = st.columns(2)

            def render_comparison_card(run_data):
                st.subheader(run_data['run_name'])
                st.caption(f"Result ID: `{run_data[self.id_col_result]}`")
                try:
                    params = run_data['parameters']
                    result = json.loads(run_data.get('result_data_json', '{}'))

                    st.metric("Final SCR Cost", f"£ {result.get('final_cost', 0):,.0f}")
                    st.markdown("---")
                    st.markdown("**Parameters**")
                    st.json(params, expanded=False)
                except Exception as e:
                    st.error(f"Could not parse run data: {e}")

            with col1:
                render_comparison_card(run_a_data)
            with col2:
                render_comparison_card(run_b_data)

    # --- This is the "recipe" function that gets returned ---
    def render_body(self, role: str, environment: str) -> None:
        """
        This is the main function called by render_frame.
        It renders the tabs for this user-facing dashboard.
        """

        st.caption(f"You are working in the **{self.env_id}** environment. All actions are logged.")

        # --- [PREREQUISITE CHECK] ---
        # First, check if all required blueprints exist.
        missing_bps = [
            bp_id for bp_id in self.all_required_blueprints
            if bp_id not in self.all_blueprints_map
        ]

        if missing_bps:
            self._render_setup_screen(missing_bps)
            st.stop()
        # --- [END OF CHECK] ---

        # If all checks pass, render the main app
        run_is_loaded = (st.session_state.current_model_run_id is not None)
        data_is_loaded = all(k in st.session_state.loaded_input_dfs for k in ['temp', 'demand'])
        model_is_fit = (st.session_state.get('glm_model') is not None)

        tab_list = [
            "📚 User Guide & Setup",
            f"📓 Model Run Instance {'✅' if run_is_loaded else '...'} ",
            f"📚 Select Data Inputs {'✅' if data_is_loaded else '...'}",
            f"🔬 Parameters & GLM {'✅' if model_is_fit else '...'}",
            "🏁 Finalize & Sign-Off",
            "📊 Comparison Workbench"
        ]

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(tab_list)

        with tab1:
            self._render_user_guide_tab()
        with tab2:
            self._render_instance_tab()
        with tab3:
            self._render_inputs_tab()
        with tab4:
            self._render_workshop_tab()
        with tab5:
            self._render_finalize_tab()
        with tab6:
            self._render_comparison_tab()

# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main_app.py interacts with.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
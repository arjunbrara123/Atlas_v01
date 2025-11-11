# config.py

# Which pages exist in Pulse.
# Each section has pages. Each page maps to a module.
ALL_PAGES = {
    # 1. HOME / GETTING STARTED
    "Home": {
        "Overview": {
            "module": "documentation.overview",
            "allowed_roles": ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        }
    },

    # 2. DATA INPUTS (data ingestion, validation, readiness)
    "Data Inputs": {
        "Inputs Overview": {
            "module": "data_inputs.inputs_overview",
            "allowed_roles": ["inputs_admin", "admin", "developer"]
        },
        "Data Workspace": {
            "module": "data_inputs.data_workspace",
            "allowed_roles": ["inputs_admin", "admin", "developer", "commercial", "exec"]
        },
    },

    # 3. ACTUARIAL MODELS (calculation layer: capital + BI + scenarios)
    "Actuarial Models": {
        "Cold Weather Model": {
            "module": "actuarial_models.capital_cold_weather",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Plumbing & Drains": {
            "module": "actuarial_models.capital_plumbing_drains",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Attritional Loss": {
            "module": "actuarial_models.capital_attritional_loss",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Market Risk": {
            "module": "actuarial_models.capital_market_risk",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Operational Risk": {
            "module": "actuarial_models.capital_operational_risk",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Counterparty Default": {
            "module": "actuarial_models.capital_counterparty_default",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },
        "Credit Risk": {
            "module": "actuarial_models.capital_credit_risk",
            "allowed_roles": ["risk", "admin", "exec", "developer"]
        },

        # Underwriting performance model logic
        "Underwriting Metrics": {
            "module": "actuarial_models.underwriting_performance_model",
            "allowed_roles": ["commercial", "admin", "exec", "developer"]
        },

        # Competitor intelligence modelling (market position, pricing deltas)
        "Competitor Intel": {
            "module": "actuarial_models.competitor_intel_model",
            "allowed_roles": ["commercial", "admin", "exec", "developer"]
        }
    },

    # 4. RESULTS (certified numbers: what we tell the business)
    "Results & Validation": {
        # Signed-off capital position, diversification, SCR headroom
        "Regulatory Capital": {
            "module": "results.capital_results",
            "allowed_roles": ["risk", "admin", "exec"]
        },

        # Book performance, loss ratios, retention, margin
        "Underwriting": {
            "module": "results.underwriting_results",
            "allowed_roles": ["commercial", "admin", "exec", "developer"]
        },

        # Signed-off capital position, diversification, SCR headroom
        "Commercial & Risk": {
            "module": "results.capital_results",
            "allowed_roles": ["risk", "admin", "exec"]
        },

        # Data quality checks, reconciliations, control evidence
        "Validations & Signoffs": {
            "module": "results.validation_controls",
            "allowed_roles": ["admin", "developer", "risk"]
        },

        # Audit trail, sign-offs, change log, submissions
        "Audit Reports": {
            "module": "results.audit_reports",
            "allowed_roles": ["admin", "risk", "exec"]
        }
    },

    # 5. INTELLIGENCE (board / exec / decision layer)
    "Reports & Intel": {
        "Exec Overview": {
            "module": "reports.exec_overview",
            "allowed_roles": ["exec", "admin", "risk", "commercial", "developer"]
        },
        "Risk & Capital": {
            "module": "reports.risk_and_capital",
            "allowed_roles": ["risk", "admin", "exec"]
        },
        "Commercial": {
            "module": "reports.commercial_performance",
            "allowed_roles": ["commercial", "admin", "exec"]
        },
        "Competitor Intel": {
            "module": "reports.competitor_intel",
            "allowed_roles": ["commercial", "admin", "exec"]
        }
        # (If you later want a pure 'Operational Pressure / Service Strain' view,
        #  you'd add it here too, e.g. "Service Pressure & Retention".)
    },

    # 6. ADMIN / DEV (internal only, not for board)
    "Admin Panel": {
        # Release notes, known issues, draft dashboards not yet cleared
        "System Status": {
            "module": "admin.system_status",
            "allowed_roles": ["admin", "developer"]
        },

        "Planning": {
            "module": "admin.planning_manager",
            "allowed_roles": ["admin"]  # Only admins should use this!
        },

        "Env Manager": {
            "module": "admin.environment_manager",
            "allowed_roles": ["admin"]  # Only admins should use this!
        },

        # Registry of approved data inputs (which file/version is 'live' in each environment)
        "File BluePrints": {
            "module": "admin.file_blueprint_manager",
            "allowed_roles": ["admin", "developer"]
        },
        # # Role / access visibility for governance comfort
        # "Access & Roles": {
        #     "module": "admin.access_audit",
        #     "allowed_roles": ["admin", "developer"]
        # },
    },

    # 7. DOCUMENTATION
    "Documentation": {
        "How to Guide (Users)": {
            "module": "documentation.how_to_use",
            "allowed_roles": ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        },
        # "Methodology (Math)": {
        #     "module": "documentation.background_methodologies",
        #     "allowed_roles": ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        # },
        "Tech Spec (Tech)": {
            "module": "documentation.tech_spec",
            "allowed_roles": ["admin", "developer", "exec", "risk", "commercial", "inputs_admin"]
        },
    },

}

# Sidebar icons for each section
SECTION_ICONS = {
    "Home":                  "🏡",
    "Data Inputs":           "🚢",
    "Actuarial Models":      "🧪",
    "Results & Validation":  "🏗️",
    "Reports & Intel":       "📊",
    "Admin Panel":           "🗃️",
    "Documentation":         "📚"
}

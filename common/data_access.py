# common/data_access.py

def get_scr_headline(period: str):
    """
    Return a fake SCR position for demo purposes.
    In production this would pull from certified capital results.
    """
    return {
        "scr_amount_gbp": 92_000_000,      # £92m required capital
        "headroom_pct": 142,               # 142% coverage vs requirement
        "last_updated": "2025-09-30 10:15",
        "approved_version": "v1.3"
    }

def get_loss_ratio_summary(period: str):
    """
    Return a fake loss ratio for demo purposes.
    In production this would come from Underwriting Results / finance sign-off.
    """
    return {
        "loss_ratio_pct": 43.0,            # combined loss ratio
        "movement_vs_last_month_pp": +1.2, # percentage point movement
        "last_updated": "2025-09-30 09:02",
        "approved_version": "v1.3"
    }

def get_ops_metrics(period: str):
    """
    Return basic operational pressure metrics (dummy).
    This would come from service/ops data feeds in Inputs.
    """
    return {
        "avg_wait_time_days": 2.1,
        "delta_wait_time_vs_last_month_days": -0.3,
        "repeat_visit_rate_pct": 8.0,
        "last_updated": "2025-09-30 08:40"
    }

def get_top_actions(period: str):
    """
    Example AI-style summary of 'what to do' this cycle.
    In production this could be LLM-generated from validated inputs.
    """
    return [
        "Increase engineering capacity in North region to protect wait times.",
        "Reprice high-deterioration segment in Plumbing cover.",
        "Escalate cold-weather exposure scenario to CRO: capital impact up £0.75m under stress."
    ]

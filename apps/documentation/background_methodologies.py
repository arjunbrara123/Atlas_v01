"""
apps/methodology.py

This page explains the definitions, data sources, and business logic
used across the Pulse dashboards.

This file follows the 'recipe' pattern compatible with render_frame:
1.  _render_page_body: A "recipe" function containing all Streamlit UI.
2.  render_page: The main function that returns the recipe and metadata.
"""

import streamlit as st


# ----------------------------------------------------------------------------
# "RECIPE" - This is the private function that has all the Streamlit UI
# ----------------------------------------------------------------------------

def _render_page_body(role: str, environment: str) -> None:
    """
    Renders the main body of the methodology page.
    This function is CALLED by common/layout.py's render_frame.
    """

    # You can use the 'role' or 'environment' if you need to,
    # but for a static page like this, we might not.
    # Example: st.write(f"Viewing documentation as {role} for {environment}")

    # st.title("Methodology & Definitions")
    # st.markdown(
    #     """
    #     This page details the definitions for key metrics, data sources,
    #     and business logic used to generate the dashboards in Pulse.
    #     """
    # )

    # Use tabs for clean navigation of a text-heavy page
    tab1, tab2 = st.tabs([
        "🧮 Key Metrics",
        "🤼 Governance & Contacts"
    ])

    # --- Tab 1: Key Metrics ---
    with tab1:
        st.subheader("Metric Definitions")
        st.markdown(
            "Below are the official definitions for primary KPIs. "
            "Use the expanders to see details."
        )

        with st.expander("**Monthly Recurring Revenue (MRR)**"):
            st.markdown(
                """
                - **Definition:** The total predictable revenue a company can 
                  expect to receive on a monthly basis.
                - **Calculation:** `(Sum of all active subscription fees per month)`
                - **Notes:** - Excludes one-time setup fees.
                    - Includes active, paid accounts only.
                    - Data is locked on the 3rd business day of the following month.
                """
            )

        with st.expander("**Active User (AU)**"):
            st.markdown(
                """
                - **Definition:** A user who has performed at least one significant 
                  action (e.g., login, run report, add item) within the specified 
                  time period (e.g., Daily, Monthly).
                - **Calculation:** `COUNT(DISTINCT user_id) FROM events_table 
                  WHERE event_name = 'meaningful_action' ...`
                - **Notes:** - Excludes internal employee accounts.
                    - A user is counted once, regardless of session count.
                """
            )

        with st.expander("**Conversion Rate (CR)**"):
            st.markdown(
                """
                - **Definition:** The percentage of users who completed a 
                  desired action (e.g., completed purchase, signed up).
                - **Calculation:** `(Total number of conversions / Total number of 
                  unique visitors) * 100`
                - **Notes:** - Attribution window is set to 7 days.
                """
            )

    # --- Tab 2: Governance & Contacts ---
    with tab2:
        st.subheader("Data Ownership")
        st.markdown(
            """
            Accountability for data quality is managed by the following teams:

            | Data Domain | Owning Team | Contact Person |
            | :--- | :--- | :--- |
            | Sales & Opportunity | Revenue Operations | Jane Doe |
            | Financials (Booked) | Finance Team | John Smith |
            | Product Usage | Data Science & Eng | Ai Chan |
            | **Atlas Platform** | **Actuarial & Risk Team** | **atlas-support@yourcompany.com** |
            """
        )

        st.subheader("Have a Question?")
        st.markdown(
            "For questions about the dashboard, metric definitions, or to report "
            "an issue, please contact the **Actuarial & Risk Team**."
        )


# ----------------------------------------------------------------------------
# "METADATA" - This is the public function that returns the recipe + meta
# ----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    Returns the "recipe" function and metadata for this page.
    This function is CALLED by main.py.
    """

    meta = {
        "title_override": "Methodology & Definitions",
        "last_updated": "2025-10-15",  # This is a 'document', so it's updated manually
        "owner": "BI & Analytics Team",
        "data_source": "N/A (Documentation)",
        "coming_soon": False  # Set to False because this page is ready
    }

    # Return the "recipe" function and the metadata
    return _render_page_body, meta
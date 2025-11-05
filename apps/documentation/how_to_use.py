"""
apps/documentation/how_to_use.py

Atlas Onboarding / Orientation.
This version is refactored into the "Class-based Recipe" pattern
to be compatible with the app's main render_frame layout.

VERSION 6.0 (Major Refactor for 11-Table Model)
- [CRITICAL] Replaced the `Environments` tab with the correct
  4-category model (Production, Reporting, etc.) from the tech_spec.
- [CRITICAL] Replaced the `Find Your Role` content to point to the
  correct, new environment types.
- [NEW] Added a new tab: "The Planning Engine," to explain
  the new backward-planning feature to non-technical users.
- [NEW] Replaced the old "Governance" tab with the "Security & Roles"
  matrix from the tech_spec.
- [FIXED] Updated the `_environment_pill` helper to be data-driven
  and match the official `tech_spec.py` helper.
"""

import streamlit as st
from datetime import datetime
import graphviz # For the new planning explanation

# --- Performance: Cache all CSS ---

@st.cache_data
def _get_css() -> str:
    """Returns the CSS for this page as a single, cached string."""
    # This CSS is unchanged from your previous version, as it's excellent.
    return """
<style>
.atlas-font {
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, sans-serif;
}
/* HERO PANEL */
.atlas-hero {
    background: radial-gradient(circle at 100% 0%, #1e3a8a 0%, #111827 40%, #000000 90%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 1.5rem 1.75rem 1.5rem 1.75rem;
    color: #fff;
    box-shadow: 0 30px 60px rgba(0,0,0,0.6);
    position: relative;
    overflow: hidden;
    margin-bottom: 1rem;
}
.atlas-hero:after {
    content: "";
    position: absolute;
    top: -80px;
    right: -80px;
    width: 220px;
    height: 220px;
    background: radial-gradient(circle at 30% 30%, rgba(56, 189, 248, 0.3) 0%, rgba(0,0,0,0) 70%);
    filter: blur(40px);
}
.atlas-hero-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #fff;
    line-height: 1.4;
    margin-bottom: 0.4rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}
.atlas-hero-sub {
    font-size: 0.8rem;
    font-weight: 400;
    color: #cbd5e1;
    line-height: 1.5;
    max-width: 900px;
}
.atlas-card-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    margin-top: 1.5rem;
}
/* GLASS FEATURE CARDS */
.atlas-feature-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    padding: 1rem 1rem 0.75rem 1rem;
    box-shadow: 0 24px 48px rgba(0,0,0,0.4);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    color: #e2e8f0;
    min-height: 220px;
}
.atlas-feature-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #f1f5f9; /* Lighter for dark bg */
    color: #012973;
    line-height: 1.4;
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.atlas-feature-body {
    font-size: 0.8rem;
    font-weight: 400;
    color: #cbd5e1; /* Lighter for dark bg */
    color: #012973;
    line-height: 1.5;
}
.atlas-feature-body ul {
    margin-top: 0.5rem;
    margin-bottom: 0.75rem;
    padding-left: 1.1rem;
}
.atlas-feature-body li {
    margin-bottom: 0.4rem;
}
@media (max-width: 992px) {
    .atlas-card-container {
        grid-template-columns: 1fr;
    }
}
/* CALLOUT BLOCKS */
.atlas-block {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    box-shadow: 0 12px 24px rgba(0,0,0,0.05);
    font-size: 0.8rem;
    line-height: 1.5;
    color: #1f2937;
    margin-bottom: 1rem;
}
.atlas-block-strong {
    background: #fff7ed;
    border: 1px solid #fdba74;
}
/* [NEW] For Scenario Boxes */
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
/* DATA FLOW TIMELINE */
.atlas-timeline-wrapper {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
}
.atlas-timeline-left {
    flex: 1 1 380px;
    min-width: 280px;
    max-width: 800px;
}
.atlas-timeline {
    position: relative;
    padding-left: 1.5rem;
    margin-top: 1rem;
}
.atlas-timeline:before {
    content: "";
    position: absolute;
    left: 0.5rem;
    top: 0.2rem;
    bottom: 0.2rem;
    width: 2px;
    background: linear-gradient(#14b8a6,#0f766e);
    border-radius: 2px;
}
.atlas-tl-step {
    position: relative;
    margin-bottom: 1.5rem;
}
.atlas-tl-icon {
    position: absolute;
    left: -0.05rem;
    top: 0;
    font-size: 0.7rem;
    background: radial-gradient(circle at 30% 30%, #14b8a6 0%, #0f172a 70%);
    color:#ecfdf5;
    border-radius: 999px;
    width: 1.2rem;
    height: 1.2rem;
    line-height: 1.2rem;
    text-align: center;
    font-weight: 600;
    box-shadow: 0 12px 24px rgba(20,184,166,0.55);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, sans-serif;
}
.atlas-tl-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #0f172a;
    margin-left: 1.5rem;
    line-height: 1.4;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, sans-serif;
}
.atlas-tl-desc {
    font-size: 0.75rem;
    font-weight: 400;
    color: #4b5563;
    margin-left: 1.5rem;
    line-height: 1.5;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, sans-serif;
    margin-top: 0.4rem;
}
.atlas-tl-desc ul {
    margin-top: 0.4rem;
    margin-bottom: 0.75rem;
    padding-left: 1.1rem;
}
.atlas-tl-desc li {
    margin-bottom: 0.4rem;
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
"""

# --- [FIXED] Environment Pill Helper ---
# This is the new, correct, data-driven helper from tech_spec.py
# It is NOT part of the Page class, it's a standalone function.

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

# --- The Page Class ---

class Page:
    def __init__(self, role: str, environment: str):
        self.role = role
        self.environment = environment

        self.meta = {
            "title_override": "How to Use Atlas",
            "owner": "Atlas Platform Team",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Internal Atlas Onboarding",
            "coming_soon": False,
        }

    # --- Tab Rendering Functions ---

    def _render_overview_tab(self):
        """Renders the content for the 'Overview' tab."""

        # [FIXED] Call the standalone helper function
        hero_html_start = (
            f"<div class='atlas-hero atlas-font'>"
            # --- Part 1: Hero Title & Subtext ---
            "<div class='atlas-hero-title'>"
            "🗺 Atlas · Advanced Capital & Commercial, and Risk Console&nbsp;"
            f"{_environment_pill(self.environment)}"
            "</div>"
            "<div class='atlas-hero-sub'>"
            "Atlas ingests operational, financial, and market data in near real time, "
            "runs actuarial and commercial models, locks the signed-off position of the business, "
            "and then generates the decision-support narrative for leadership. "
            "There is no second source of truth."
            "</div>"
        )

        hero_html_end = "</div>" # End of .atlas-hero

        st.markdown(hero_html_start, unsafe_allow_html=True)

        # --- This content is still conceptually correct ---
        with st.container():
            st.markdown("<div class='atlas-card-container'>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    """
                    <div class='atlas-feature-card atlas-font'>
                    <div class='atlas-feature-title'>📥 Data Inputs</div>
                    <div class='atlas-feature-body'>
                    Atlas continuously ingests, tags, and validates the feeds the business runs on.
                    <ul>
                    <li>Claims, exposure, finance, service performance</li>
                    <li>Competitor position, pricing signals, weather stress, regulatory shifts</li>
                    <li>Each feed is freshness-scored and approval-stamped</li>
                    </ul>
                    </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    """
                    <div class='atlas-feature-card atlas-font'>
                    <div class='atlas-feature-title'>⚙ Actuarial & Commercial Models</div>
                    <div class='atlas-feature-body'>
                    Approved inputs feed our governed engines:
                    <ul>
                    <li>Capital models (Cold Weather, Attritional Loss, Operational Risk, Counterparty, etc.)</li>
                    <li>Underwriting Performance model (margin by segment, loss ratios, retention pressure)</li>
                    <li>Competitor Intelligence model (where we're winning or losing in market)</li>
                    </ul>
                    This is where solvency coverage, appetite pressure, and margin risk 
                    are quantified objectively.
                    </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    """
                    <div class='atlas-feature-card atlas-font'>
                    <div class='atlas-feature-title'>📊 Results & AI Intelligence</div>
                    <div class='atlas-feature-body'>
                    Atlas publishes the official position of the business, then layers AI on top 
                    to explain what it means and what action is needed.
                    <ul>
                    <li>SCR, diversification headroom, solvency coverage</li>
                    <li>Loss ratios, churn risk, unit economics</li>
                    <li>AI narrative for ExCo: 'Where are we off-plan and why?'</li>
                    </ul>
                    </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True) # End of .atlas-card-container

        st.markdown(hero_html_end, unsafe_allow_html=True)

    def _render_flow_tab(self):
        """
        Renders the content for the 'Data Flow' tab.
        This content is conceptually correct and remains unchanged.
        """
        st.markdown(
            (
                "<div class='atlas-hero atlas-font'>"
                "<div class='atlas-hero-title'>"
                "🔄 Atlas Data Flow"
                "</div>"
                "<div class='atlas-hero-sub'>"
                "This is the operational loop. We pull live inputs, run the actuarial and commercial engines, "
                "lock the official result, then generate AI-driven decision support. "
                "It's an always-on solvency and margin early-warning system."
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='atlas-timeline-wrapper atlas-font'>"
                "<div class='atlas-timeline-left'>"
                "<div class='atlas-timeline'>"
                "<div class='atlas-tl-step'>"
                "<div class='atlas-tl-icon'>1</div>"
                "<div class='atlas-tl-title'>Data Inputs</div>"
                "<div class='atlas-tl-desc'>"
                "Atlas ingests internal and external feeds and stamps them with freshness and approval."
                "<ul>"
                "<li>Internal: claims, exposure, finance, service performance</li>"
                "<li>External: competitor pricing/position, weather stress, regulatory signals</li>"
                "</ul>"
                "Nothing moves forward until data quality clears."
                "</div>"
                "</div>"
                "<div class='atlas-tl-step'>"
                "<div class='atlas-tl-icon'>2</div>"
                "<div class='atlas-tl-title'>Actuarial & Commercial Models</div>"
                "<div class='atlas-tl-desc'>"
                "Approved inputs power the governed models:"
                "<ul>"
                "<li>Capital models (Cold Weather, Attritional Loss, Operational Risk, Counterparty, etc.)</li>"
                "<li>Underwriting Performance model (margin by segment, loss ratios, retention stress)</li>"
                "<li>Competitor Intelligence model (where we're strong / weak vs market)</li>"
                "</ul>"
                "This is where solvency coverage, appetite pressure, and margin risk are actually quantified."
                "</div>"
                "</div>"
                "<div class='atlas-tl-step'>"
                "<div class='atlas-tl-icon'>3</div>"
                "<div class='atlas-tl-title'>Results & Governance</div>"
                "<div class='atlas-tl-desc'>"
                "We publish the position of the business. That includes:"
                "<ul>"
                "<li>SCR, diversification benefit, solvency headroom</li>"
                "<li>Loss ratios, churn risk, unit economics</li>"
                "<li>Validation evidence, reconciliation, and audit trail</li>"
                "</ul>"
                "This is the single position we defend to CRO / CFO / Board."
                "</div>"
                "</div>"
                "<div class='atlas-tl-step'>"
                "<div class='atlas-tl-icon'>4</div>"
                "<div class='atlas-tl-title'>AI Intelligence for Leadership</div>"
                "<div class='atlas-tl-desc'>"
                "Atlas then builds an exec-facing narrative:"
                "<ul>"
                "<li>Highlights where we're drifting off appetite or plan</li>"
                "<li>Explains <i>why</i> metrics moved (not just that they moved)</li>"
                "<li>Surfaces the decision required now (pricing action, capacity shift, cost intervention)</li>"
                "</ul>"
                "This is what actually goes into the room."
                "</div>"
                "</div>"
                "</div>"
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    def _render_quick_tab(self):
        """
        [FIXED] Renders the content for the 'Find Your Role' tab.
        All content is now updated to the new Environment model.
        """
        st.markdown(
            (
                "<div class='atlas-hero atlas-font'>"
                "<div class='atlas-hero-title'>"
                "🚀 Find Your Role&nbsp;"
                f"{_environment_pill(self.environment)}"
                "</div>"
                "<div class='atlas-hero-sub'>"
                "Use this guide to find exactly which dashboard and environment"
                "you need to get your job done."
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        c_left, c_right = st.columns(2)
        with c_left:
            st.subheader("If you are an Exec / Senior Leader", anchor=False)
            st.markdown(
                """
                <div class="atlas-block atlas-block-success atlas-font">
                <ol>
                    <li>Go to the <b>`📊 Reports & Insights`</b> dashboards.</li>
                    <li>
                        In the sidebar, make sure you select a <b><code>Reporting</code></b>
                        environment (e.g., <code>Rep.Q425.v1</code>).
                    </li>
                    <li>These numbers are **locked, audited, and final**. They are
                        the "single source of truth" for ExCo and Board.</li>
                </ol>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.subheader("If you are an Analyst / Actuary (a ""Doer"")", anchor=False)
            st.markdown(
                """
                <div class="atlas-block atlas-font">
                <ol>
                    <li>You do your work in the <b>`🚢 Data Inputs`</b> and
                        <b>`🧪 Actuarial Models`</b> workspaces.</li>
                    <li>
                        In the sidebar, you must select a <b><code>Production</code></b>
                        environment (e.g., <code>Prod.Q126_Draft</code>).
                    </li>
                    <li>Your job is to upload data, run models, and use the
                        "Sign-Off" tabs to get your work approved by a Reviewer.</li>
                    <li>Use the <b>`🚀 Dynamic Planning Engine`</b> to track your
                        deadlines.</li>
                </ol>
                </div>
                """,
                unsafe_allow_html=True
            )
        with c_right:
            st.subheader("If you are a Manager / Governor (a ""Reviewer"")", anchor=False)
            st.markdown(
                """
                <div class="atlas-block atlas-font">
                <ol>
                    <li>Your work lives in the <b>"Reviewer Inbox"</b> tabs
                        on all dashboards (e.g., in `🚢 Data Inputs`).</li>
                    <li>
                        You will select the same <b><code>Production</code></b> environment
                        as your team (e.g., <code>Prod.Q126_Draft</code>).
                    </li>
                    <li>Your job is to review your team's work and use the
                        <b>"Approve"</b> or <b>"Reject"</b> buttons, which creates
                        the audit trail.</li>
                    <li>You can also go to the <b>`🗃️ Admin Panel`</b> to
                        manage project plans or promote a `Production` env
                        to a `Reporting` env.</li>
                </ol>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.subheader("If you are an Auditor / Peer Reviewer", anchor=False)
            st.markdown(
                """
                <div class="atlas-block atlas-block-warning atlas-font">
                <ol>
                    <li>You work in a **<code>Validation</code>** environment
                        (e.g., <code>Val.Q425_Audit</code>).</li>
                    <li>This is a "sandbox" cloned from a `Production` or
                        `Reporting` environment.</li>
                    <li>You can re-run models and do any analysis you want,
                        **100% safely**, with no risk of breaking the "live"
                        version.</li>
                </ol>
                </div>
                """,
                unsafe_allow_html=True
            )

    def _render_env_tab(self):
        """
        [FIXED] Renders the 'Environments' tab.
        This is now 100% copied from the tech_spec.py file
        to ensure consistency.
        """
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
                is repeated to create `Rep.Q4BET.v2`.
            """
        )

    def _render_planning_engine_tab(self):
        """
        [NEW] Renders a user-friendly guide to the Dynamic Planning Engine.
        """
        st.markdown(
            (
                "<div class='atlas-hero atlas-font'>"
                "<div class='atlas-hero-title'>"
                "🚀 The Dynamic Planning Engine"
                "</div>"
                "<div class='atlas-hero-sub'>"
                "Atlas includes a powerful project management tool. Instead of"
                "you calculating dates in Excel, the engine does it *for* you."
                "It works **backward from your final deadline** to build a"
                "perfect, dynamic plan."
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        st.subheader("How It Works: A 3-Step Guide")
        st.markdown(
            """
            The entire process is driven by the **`🚀 Dynamic Project Plan`** tab
            in the **`🗃️ Admin Panel`** -> **`🚀 Planning Manager`**.
            """
        )

        # --- 3-Step Diagram ---
        planning_diagram = """
        digraph {
            rankdir=TB;
            fontname="sans-serif";
            fontsize=12;
            node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=12];
            edge [fontname="sans-serif", fontsize=10];

            subgraph "cluster_Step1" {
                label = "Step 1: Set Your Final Deadline";
                style="filled"; fillcolor="#F6FFED";
                node [fillcolor="#FFFFFF", stroke="#08A045"];
                S1 [label="You create a 'Final Deadline' task:\n'Report Due' (1 day)\nDue Date: Dec 20"];
            }

            subgraph "cluster_Step2" {
                label = "Step 2: Add Tasks & Dependencies";
                style="filled"; fillcolor="#E6F7FF";
                node [fillcolor="#FFFFFF", stroke="#1890FF"];
                S2_A [label="Task: 'Final Review' (5 days)"];
                S2_B [label="Task: 'Data Gathering' (10 days)"];
            }
            
            subgraph "cluster_Step3" {
                label = "Step 3: The Engine Calculates The Plan";
                style="filled"; fillcolor="#F0F0F0";
                node [fillcolor="#FFFFFF", stroke="#555555"];
                S3 [
                    label="The engine works BACKWARD:\l\l" +
                          "1. 'Final Review' must finish by Dec 19.\l" +
                          "   Calculated Start: Dec 15\l\l" +
                          "2. 'Data Gathering' must finish by Dec 14.\l" +
                          "   Calculated Start: Dec 5\l",
                    align=left
                ];
            }
            
            edge [style=dashed, penwidth=2, color="#333333"];
            S1 -> S2_A [label=" 'Final Review' depends on 'Report Due'"];
            S2_A -> S2_B [label=" 'Data Gathering' depends on 'Final Review'"];
            S2_B -> S3 [label=" Engine finds the 'Critical Path'"];
        }
        """
        st.graphviz_chart(planning_diagram)

        st.markdown("### What This Means For You")
        st.markdown(
            """
            * **No More Guesswork:** You never have to guess a "start date"
                again. Just give the engine your durations and your final
                deadline, and it will *tell you* the "Calculated Project
                Start Date."
            * **Multiple Dependencies:** The engine is smart. If "Task C"
                depends on "Task A" (10 days) and "Task B" (5 days), it
                knows "Task A" is the "Critical Path" and will base the
                project start date on that.
            * **Dynamic Re-planning:** If you change a task's duration
                from 10 days to 15, the *entire plan* recalculates
                instantly.
            """
        )

    def _render_gov_tab(self):
        """
        [FIXED] Renders the 'Governance & Roles' tab.
        This is now a simple, clear permissions matrix.
        """
        st.subheader("🔐 Security & Roles (Who Can Do What?)")
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
                        <th>Can Manage<Vbr>File Blueprints?</th>
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
            </Example>
            </p>
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

        # Inject all custom CSS (cached for performance)
        st.markdown(_get_css(), unsafe_allow_html=True)

        # [FIXED] Define the new tabs
        tab_overview, tab_flow, tab_quick, tab_env, tab_planning, tab_gov = st.tabs(
            [
                "🚁 Overview",
                "🔄 Data Flow",
                "🚀 Find Your Role",
                "🚦 Environments",
                "✨ The Planning Engine",
                "🔐 Governance & Roles",
            ]
        )

        # Render content for each tab
        with tab_overview:
            self._render_overview_tab()

        with tab_flow:
            self._render_flow_tab()

        with tab_quick:
            self._render_quick_tab()

        with tab_env:
            self._render_env_tab()

        with tab_planning:
            self._render_planning_engine_tab()

        with tab_gov:
            self._render_gov_tab()


# -----------------------------------------------------------------------------
# META HEADER DETAILS BACK TO MAIN
# -----------------------------------------------------------------------------

def render_page(role: str, environment: str) -> (callable, dict):
    """
    This is the public function that main.py interacts with.

    1. It creates an instance of the Page (running __init__ to get meta).
    2. It returns the "recipe" (page.render_body) and the dynamic meta.
    """
    page = Page(role=role, environment=environment)
    return page.render_body, page.meta
"""
common/layout.py

This module defines shared layout helpers for Pulse pages.

This version is "all-in-one": it embeds its own CSS inside the
st.markdown() call to create an "ultra-thin" header bar.
No external style.css is needed for this header.

v4 Changes:
- Adds a "pulse" GIF to the end of the header bar.
"""

from typing import Optional, Any, Callable
import streamlit as st
import base64  # To embed the logo

@st.cache_data
def get_image_as_base64(path):
    """Caches and loads a local image as a base64 string."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        st.error(f"Could not load logo: {e}")
        return None

def render_frame(
    title_override: str,
    body_component: Optional[Callable],
    last_updated: str,
    owner: str,
    data_source: str,
    coming_soon: bool = False,
    environment: Optional[str] = None,
) -> None:
    """
    Render the Pulse header strip for the current dashboard.

    This version uses custom HTML/CSS for an ultra-thin, rich header.
    """

    # --- 1. Load Assets ---
    logo_base64 = get_image_as_base64("favicon.ico")
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="header-logo">' \
        if logo_base64 else "🩺"

    env_badge = f'<span class="env-badge">{environment}</span>' if environment else ""
    coming_soon_tag = '<span class="coming-soon-badge">⚠ Coming Soon</span>' if coming_soon else ""

    # --- 2. Define the CSS (Embedded) ---
    header_css = """
<style>
    /* Removes top padding from the main container */
    div.block-container {
        padding-top: 1.8rem !important; 
    }

    /* The main header container */
    .pulse-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.3rem 1.25rem; /* 5px top/bottom, 20px left/right */
        
        /* Visuals */
        background-image: linear-gradient(90deg, #00416A, #E4E5E6);
        background-image: linear-gradient(90deg, #4B9FFF, #FFFFFF);
        background-image: linear-gradient(90deg, #000000, #4B9FFF);
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
    }

    /* --- Left Side: Logo, Title, Badges --- */
    .header-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: white; /* Left-side text is white */
    }
    .header-logo {
        width: 24px;
        height: 24px;
    }
    .header-left h2 {
        font-size: 1.1rem;
        font-weight: 500;
        margin: 0;
        padding: 0;
        line-height: 1;
        color: white;
    }
    .env-badge, .coming-soon-badge {
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        line-height: 1.0;
    }
    .env-badge {
        font-family: 'Consolas', 'Menlo', 'monospace';
        background-color: rgba(255, 255, 255, 0.15);
        color: white;
    }
    .coming-soon-badge {
        background-color: #FFC107;
        color: #333;
        margin-top: 30px;
    }

    /* --- Right Side: Metadata (Owner, Updated, Source) --- */
    .header-right {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 1.25rem; /* This will also add space before the new GIF */
        font-size: 0.8rem;
        color: #eee; /* Dark text for the light background */
    }
    .meta-item {
        line-height: 1;
        white-space: nowrap;
    }
    .meta-item strong {
        font-weight: 600;
        color: #aaa; 
    }
    
    /* --- NEW CSS CLASS FOR THE GIF --- */
    .header-gif {
        height: 28px;  /* Keeps it thin, slightly taller than logo */
        width: auto;   /* Maintain aspect ratio */
        border-radius: 4px;
    }

</style>
"""

    # --- 3. Define the HTML (Un-indented) ---
#{logo_html}
    header_html = f"""
<div class="pulse-header">
<div class="header-left">
<img src="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdHgwcXp4eG11M21jNXp5YjM5YW1uZXh3a24xcXN2czBzZnAycW5obiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/kfLxX6jUuFTZMMQEvK/giphy.gif" class="header-gif" alt="Pulse GIF">

<h2>Atlas · {title_override}  </h2>
{env_badge} 
<h2>{coming_soon_tag}</h2>
</div>
<div class="header-right">
<div class="meta-item">
    <strong>Owner:</strong> {owner}
</div>
<div class="meta-item">
    <strong>Updated:</strong> {last_updated}
</div>
<div class="meta-item">
    <strong>Source:</strong> {data_source}
</div>

<img src="https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWNuNHQ5eDZtYjJuZmdidXdxMTIyZmV3YWU5eGg4aHB5aXBlaDF3MiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/mWnDeIKilkwDcrM2VT/giphy.gif" class="header-gif" alt="Pulse GIF">
<img src="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExZGp1bzllMTNnMTQ0NTE3bm1ubnEycWhjcTVvMW1iOGpkM3oxM2RyMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/WuqP3UOesePK/giphy.gif" class="header-gif" alt="Pulse GIF">

</div>
</div>
"""

    # --- 4. Render CSS and HTML ---
    st.markdown(header_css, unsafe_allow_html=True)
    st.markdown(header_html, unsafe_allow_html=True)


    # --- 5. Render Page Content ---
    # This logic remains the same as before.

    if coming_soon:
        st.info(
            "This dashboard location has been reserved in Atlas, "
            "but the underlying view is still being built."
        )
        st.stop()

    elif body_component:
        # Call the "recipe" function to render the page body
        body_component(
            role=st.session_state.role,
            environment=environment
        )

    else:
        st.error(
            f"**Page Rendering Error:** The page '{title_override}' is not marked "
            "'Coming Soon' but did not provide a valid body component to render."
        )
        st.stop()
import pandas as pd
import streamlit as st
from pressure_scraper import BaseballReferenceScraper

# 1. Initialize Scraper Package
br_scraper = BaseballReferenceScraper()

# 2. Page Configuration
st.set_page_config(
    page_title="Universal MLB Pressure Pitch Calculator",
    page_icon="⚾",
    layout="centered",
)

st.title("⚾ Universal MLB Pressure Pitch & pERA Search Engine")
st.markdown(
    "Type any pitcher's name in the search bar below to evaluate their RISP"
    " run vulnerability and pressure-adjusted ERA."
)


# 3. Load Master Database for Auto-Suggestions
@st.cache_data
def load_master():
  return pd.read_csv("all_mlb_rosters_2026.csv")


df_master = load_master()

# 4. Sidebar Postseason Skew Toggle
st.sidebar.markdown("### ⚙️ Model Adjustments")
apply_postseason_skew = st.sidebar.toggle(
    "🔥 Apply Postseason Leverage Skew",
    value=True,
    help=(
        "Multiplies base pressure by 1.05x for starters and 1.10x for relievers"
        " to account for October game stakes."
    ),
)

# 5. Free-Text Search Input
search_query = st.text_input(
    "🔍 Search Pitcher Name:",
    value="",
    placeholder="Type name (e.g., Gerrit Cole, Paul Skenes, Tarik Skubal)...",
)

# 6. Query Execution via Scraper Package
if search_query:
  # Find matching names in the master dataset to handle partial queries
  matches = df_master[
      df_master["Pitcher"].str.contains(search_query, case=False, na=False)
  ]

  if matches.empty:
    st.warning(
        f"❌ No pitchers found matching '{search_query}'. Check spelling or"
        " try another name."
    )
  else:
    # If multiple matches, let the user select the exact one from a dropdown
    if len(matches) > 1:
      selected_idx = st.selectbox(
          "Multiple matches found. Select correct pitcher:",
          options=matches.index,
          format_func=lambda idx: (
              f"{matches.loc[idx, 'Pitcher']} ({matches.loc[idx, 'Team']} -"
              f" {matches.loc[idx, 'Role']})"
          ),
      )
      target_name = matches.loc[selected_idx, "Pitcher"]
    else:
      target_name = matches.iloc[0]["Pitcher"]

    # Call your custom scraper package function
    data = br_scraper.get_pitcher_risp_stats(target_name)

    if data:
      st.success(f"Data successfully retrieved via {data['Source']}")
      st.divider()

      # Top-Level Details
      col1, col2, col3 = st.columns(3)
      col1.metric("Team", data["Team"])
      col2.metric("Role", data["Role"])
      col3.metric("RISP Plate App.", data["PA_RISP"])

      # Underlying Metrics Breakdown
      st.markdown("### 📊 Underlying RISP Components")
      c1, c2, c3 = st.columns(3)
      c1.metric("Hits Allowed (H)", data["H_RISP"])
      c2.metric("Walks Issued (BB)", data["BB_RISP"])
      c3.metric("Runs Allowed (R)", data["R_RISP"])

      st.divider()

      # Calculations & Postseason Skew
      base_pp = data["Base_PP"]
      multiplier = 1.05 if "Starter" in data["Role"] else 1.10
      postseason_ppp = round(base_pp * multiplier, 3)

      st.subheader("🔥 Pressure Index Results")
      res1, res2 = st.columns(2)

      if apply_postseason_skew:
        res1.metric("Base Pressure Pitch (PP)", f"{base_pp:.3f}")
        res2.metric(
            "Postseason Skewed PPP",
            f"{postseason_ppp:.3f}",
            delta=f"+{round((postseason_ppp - base_pp), 3)} Oct Skew",
        )
      else:
        res1.metric("Base Pressure Pitch (PP)", f"{base_pp:.3f}")
        res2.metric(
            "Postseason Skewed PPP",
            "Disabled",
            help="Toggle sidebar to enable",
        )

      # Run Prevention & pERA Context
      st.markdown("### 📉 Run Prevention & pERA Context")
      col_era1, col_era2 = st.columns(2)
      col_era1.metric("Standard Baseline ERA", f"{data['Standard_ERA']:.2f}")
      col_era2.metric(
          "Pressure-Adjusted ERA (pERA)",
          f"{data['Pressure_Adjusted_ERA']:.2f}",
          delta=f"{round(data['Pressure_Adjusted_ERA'] - data['Standard_ERA'], 2)} Variance",
          help=(
              "Blends standard ERA with high-leverage RISP vulnerability. Lower"
              " pERA means lockdown pressure control."
          ),
      )

      # Dynamic Analysis Callout
      final_score_to_evaluate = postseason_ppp if apply_postseason_skew else base_pp
      if final_score_to_evaluate < 0.380:
        st.success(
            "**Profile:** Elite pressure management. Minimizes walks and"
            " suppresses run conversion under heavy traffic."
        )
      elif final_score_to_evaluate < 0.450:
        st.info(
            "**Profile:** Stable reliability. Performs consistently under"
            " standard leverage conditions."
        )
      else:
        st.warning(
            "**Profile:** High vulnerability. Prone to spike innings and run"
            " conversion when traffic builds up."
        )
else:
  st.info(
      "👆 Type any pitcher's name in the search bar above to begin exploring"
      " stats."
  )
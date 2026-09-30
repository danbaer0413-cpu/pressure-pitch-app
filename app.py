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

st.title("⚾ Universal MLB Pressure Pitch & Trend Engine")
st.markdown(
    "Type any pitcher's name below to analyze their sample-adjusted RISP"
    " vulnerability, recent 10-appearance trend lean, and pressure tiers."
)


# 3. Master Database Loader
@st.cache_data
def load_master():
  return pd.read_csv("all_mlb_rosters_2026.csv")


df_master = load_master()

# 4. Sidebar Postseason Skew & Trend Adjustments
st.sidebar.markdown("### ⚙️ Model Adjustments")
apply_postseason_skew = st.sidebar.toggle(
    "🔥 Apply Postseason Leverage Skew",
    value=True,
    help=(
        "Multiplies adjusted pressure by 1.05x for starters and 1.10x for"
        " relievers to account for October game stakes."
    ),
)

include_recent_lean = st.sidebar.toggle(
    "📈 Weight Prior 10 Appearance Trend",
    value=True,
    help=(
        "Blends season-long baseline with their recent 10-game hot/cold form"
        " trend."
    ),
)

# 5. Free-Text Search Input
search_query = st.text_input(
    "🔍 Search Pitcher Name:",
    value="",
    placeholder="Type name (e.g., Gerrit Cole, Paul Skenes, Tarik Skubal)...",
)

# 6. Query Execution & Results Display
if search_query:
  matches = df_master[
      df_master["Pitcher"].str.contains(search_query, case=False, na=False)
  ]

  if matches.empty:
    st.warning(
        f"❌ No pitchers found matching '{search_query}'. Check spelling or"
        " try another name."
    )
  else:
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

    data = br_scraper.get_pitcher_risp_stats(target_name)

    if data:
      st.success(f"Data successfully retrieved via {data['Source']}")
      st.divider()

      # Fetch detailed row data including Bayesian shrinkage and Prior 10 stats
      match_row = df_master[
          df_master["Pitcher"].str.lower() == target_name.strip().lower()
      ].iloc[0]
      adjusted_pp = float(match_row["Adjusted_Pressure_Pitch"])
      prior_10_pp = float(match_row["Prior_10_PP"])
      trend_delta = float(match_row["Trend_Delta"])

      # Blend recent 10 appearance lean if toggled on in sidebar
      if include_recent_lean:
        active_pp = round((adjusted_pp * 0.7) + (prior_10_pp * 0.3), 3)
      else:
        active_pp = adjusted_pp

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
      multiplier = 1.05 if "Starter" in data["Role"] else 1.10
      postseason_ppp = round(active_pp * multiplier, 3)
      eval_score = postseason_ppp if apply_postseason_skew else active_pp

      # Determine color-coded badge tier
      if eval_score < 0.350:
        tier_label, badge_color, text_color = "ELITE", "#FFD700", "#594500"  # Gold
      elif eval_score < 0.400:
        tier_label, badge_color, text_color = "GREAT", "#2ecc71", "#ffffff"  # Green
      elif eval_score < 0.450:
        tier_label, badge_color, text_color = "SHAKY", "#f1c40f", "#594500"  # Yellow
      else:
        tier_label, badge_color, text_color = "BAD", "#e74c3c", "#ffffff"  # Red

      # Display Pressure Index Results & Trend Lean
      st.subheader("🔥 Pressure Index & Recent Trend")
      res1, res2, res3 = st.columns(3)

      res1.metric(
          "Active Pressure Pitch",
          f"{active_pp:.3f}",
          help="Blends season baseline with recent form",
      )
      res2.metric(
          "Prior 10 Outings PP",
          f"{prior_10_pp:.3f}",
          delta=f"{trend_delta:+.3f} Trend",
          help="Rolling pressure score over last 10 appearances",
      )
      res3.metric(
          "Postseason Skewed PPP",
          f"{postseason_ppp:.3f}" if apply_postseason_skew else "Disabled",
      )

      # Render Custom Color-Coded Tier Badge
      st.markdown(
          f"""
            <div style="padding: 15px; border-radius: 10px; background-color: {badge_color}; text-align: center; margin-top: 15px; margin-bottom: 15px;">
                <h3 style="color: {text_color}; margin: 0; font-weight: 800;">PRESSURE TIER: {tier_label} (Score: {eval_score:.3f})</h3>
            </div>
            """,
          unsafe_allow_html=True,
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
              "Blends standard ERA with sample and trend-adjusted high-leverage"
              " RISP vulnerability."
          ),
      )

      # Dynamic Analysis Callout
      if eval_score < 0.350:
        st.success(
            "**Profile:** Lockdown elite pressure management. Minimizes walks"
            " and suppresses run conversion under heavy traffic."
        )
      elif eval_score < 0.400:
        st.info(
            "**Profile:** Great performance. Consistently suppresses runs and"
            " manages leverage well."
        )
      elif eval_score < 0.450:
        st.warning(
            "**Profile:** Shaky reliability. Prone to elevated traffic stress"
            " and occasional run conversion."
        )
      else:
        st.error(
            "**Profile:** High vulnerability (Bad). Spikes in run conversion"
            " when pressure builds up."
        )
else:
  st.info(
      "👆 Type any pitcher's name in the search bar above to begin exploring"
      " stats."
  )
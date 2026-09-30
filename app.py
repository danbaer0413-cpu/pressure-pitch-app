import pandas as pd
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Pressure Pitch Calculator", page_icon="⚾", layout="centered"
)

st.title("⚾ MLB Pressure Pitch (PP) Search Engine")
st.markdown(
    "Type or select any pitcher's name to instantly query their RISP stats and"
    " calculate their **Pressure Pitch** score."
)


# 2. Load Master Database
@st.cache_data
def load_data():
  return pd.read_csv("red_sox_yankees_stable_pressure_pitch.csv")


df = load_data()

# 3. Search Box Component
pitcher_names = sorted(df["Pitcher"].unique().tolist())
selected_pitcher = st.selectbox(
    "🔍 Search Pitcher Name:",
    options=pitcher_names,
    index=0,
    help="Type to search any pitcher in the database",
)

# 4. Filter Data and Run Lookup
if selected_pitcher:
  match = df[df["Pitcher"].str.lower() == selected_pitcher.strip().lower()]

  if not match.empty:
    row = match.iloc[0]

    st.divider()

    # Display Top-Level Details
    col1, col2, col3 = st.columns(3)
    col1.metric("Team", row["Team"])
    col2.metric("Role", row["Role"])
    col3.metric("RISP Plate App. (PA)", int(row["PA_RISP"]))

    # Display Underlying RISP Metrics
    st.markdown("### 📊 Component Breakdown")
    c1, c2, c3 = st.columns(3)
    c1.metric("Hits Allowed (H)", int(row["H_RISP"]))
    c2.metric("Walks Issued (BB)", int(row["BB_RISP"]))
    c3.metric("Runs Allowed (R)", int(row["R_RISP"]))

    st.divider()

    # Formula Execution & Calculations
    pp_score = row["Pressure_Pitch"]
    multiplier = 1.05 if row["Role"] == "Starter" else 1.10
    postseason_ppp = round(pp_score * multiplier, 3)

    st.subheader("🔥 Pressure Index Results")
    res_col1, res_col2 = st.columns(2)
    res_col1.metric("Base Pressure Pitch (PP)", f"{pp_score:.3f}")
    res_col2.metric(
        "Postseason Skewed PPP",
        f"{postseason_ppp:.3f}",
        help="Adjusted for October game leverage & WPA intensity",
    )

    # Dynamic Analysis Callout
    if pp_score < 0.380:
      st.success(
          "**Profile:** Elite pressure management. Minimizes walks and"
          " suppresses run conversion under heavy traffic."
      )
    elif pp_score < 0.450:
      st.info(
          "**Profile:** Stable reliability. Performs consistently under"
          " standard leverage conditions."
      )
    else:
      st.warning(
          "**Profile:** High vulnerability. Prone to spike innings and run"
          " conversion when traffic builds up."
      )
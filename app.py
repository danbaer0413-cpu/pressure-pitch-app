import pandas as pd
import streamlit as st

import pressure_engine as eng

st.set_page_config(
    page_title="2026 MLB Pressure Pitch Engine", page_icon="⚾", layout="centered"
)

st.title("⚾ 2026 MLB Pressure Pitch & Trend Engine")
st.markdown(
    "Evaluating **2026 single-season** pitcher performance with runners in"
    " scoring position (RISP), using sample-adjusted pressure scores, recent"
    " form, and pressure-adjusted ERA."
)


@st.cache_data
def get_data():
    return eng.load_master()


@st.cache_data
def get_scored(recent_lean, postseason_skew):
    df, _ = get_data()
    return eng.score_frame(df, recent_lean, postseason_skew)


try:
    _, source_label = get_data()
except Exception as e:  # missing file, bad columns, etc.
    st.error(f"Could not load data: {e}")
    st.stop()

# ---- Sidebar ---------------------------------------------------------------
st.sidebar.markdown("### ⚙️ 2026 Model Adjustments")
apply_postseason_skew = st.sidebar.toggle(
    "🔥 Apply Postseason Leverage Skew",
    value=False,
    help="Multiplies pressure by 1.05x for starters and 1.10x for relievers.",
)
include_recent_lean = st.sidebar.toggle(
    "📈 Weight Prior 10 Appearance Trend",
    value=True,
    help="Blends the season baseline (70%) with the last 10 outings (30%).",
)
st.sidebar.caption(f"Data source: {source_label}")

scored = get_scored(include_recent_lean, apply_postseason_skew)

tab_search, tab_board = st.tabs(["🔍 Pitcher Search", "🏆 Leaderboard"])

# ---- Search tab ------------------------------------------------------------
with tab_search:
    query = st.text_input(
        "Search 2026 Pitcher Name:",
        placeholder="Type name (e.g., Gerrit Cole, Paul Skenes, Tarik Skubal)...",
    )

    if not query:
        st.info("👆 Type a pitcher's name to begin.")
    else:
        matches = scored[
            scored["Pitcher"].str.contains(query, case=False, na=False, regex=False)
        ]
        if matches.empty:
            st.warning(f"❌ No 2026 pitchers found matching '{query}'.")
        else:
            if len(matches) > 1:
                idx = st.selectbox(
                    "Multiple matches found. Select correct pitcher:",
                    options=matches.index,
                    format_func=lambda i: (
                        f"{matches.loc[i, 'Pitcher']} ({matches.loc[i, 'Team']}"
                        f" - {matches.loc[i, 'Role']})"
                    ),
                )
            else:
                idx = matches.index[0]
            p = matches.loc[idx]

            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Team", p["Team"])
            c2.metric("Role", p["Role"])
            c3.metric("RISP Plate App.", int(p["PA_RISP"]))

            st.markdown("### 📊 RISP Components")
            c1, c2, c3 = st.columns(3)
            c1.metric("Hits Allowed (H)", int(p["H_RISP"]))
            c2.metric("Walks Issued (BB)", int(p["BB_RISP"]))
            c3.metric("Runs Allowed (R)", int(p["R_RISP"]))
            if p["PA_RISP"] < 40:
                st.caption(
                    "⚠️ Small RISP sample. Scores are shrunk toward league"
                    " average, so treat this one with caution."
                )

            st.divider()
            st.subheader("🔥 Pressure Index & Recent Trend")
            r1, r2, r3 = st.columns(3)
            r1.metric("Active Pressure Pitch", f"{p['Active_PP']:.3f}")
            r2.metric(
                "Prior 10 Outings PP",
                f"{p['Prior_10_PP']:.3f}",
                delta=f"{p['Trend_Delta']:+.3f} Trend",
                delta_color="inverse",  # lower pressure pitch is better
                help="Rolling pressure score over the last 10 appearances.",
            )
            r3.metric(
                "Postseason Skewed PPP",
                f"{p['Postseason_PP']:.3f}" if apply_postseason_skew else "Disabled",
            )

            bg, fg = eng.TIER_STYLE[p["Tier"]]
            st.markdown(
                f"""
                <div style="padding:15px;border-radius:10px;background-color:{bg};
                            text-align:center;margin:15px 0;">
                  <h3 style="color:{fg};margin:0;font-weight:800;">
                    PRESSURE TIER: {p['Tier']} (Score: {p['Eval_Score']:.3f})
                  </h3>
                </div>
                """,
                unsafe_allow_html=True,
            )
            role_word = "starters" if "starter" in p["Role"].lower() else "relievers"
            st.caption(
                f"Better than ~{int(p['Better_Than_Pct'])}% of 2026 {role_word}"
                " on this score."
            )

            st.markdown("### 📉 Run Prevention & pERA")
            e1, e2 = st.columns(2)
            e1.metric("Standard ERA", f"{p['Standard_ERA']:.2f}")
            e2.metric(
                "Pressure-Adjusted ERA (pERA)",
                f"{p['pERA']:.2f}",
                delta=f"{p['pERA_Variance']:+.2f} vs ERA",
                delta_color="inverse",  # lower ERA is better
                help="Standard ERA blended with the pressure score used for the tier.",
            )

            callouts = {
                "ELITE": (st.success, "Lockdown pressure management. Limits walks and run conversion with traffic on."),
                "GREAT": (st.info, "Consistently suppresses runs and manages leverage well."),
                "SHAKY": (st.warning, "Prone to traffic stress and occasional run conversion."),
                "BAD": (st.error, "High vulnerability. Runs tend to score once pressure builds."),
            }
            fn, text = callouts[p["Tier"]]
            fn(f"**Profile:** {text}")

# ---- Leaderboard tab -------------------------------------------------------
with tab_board:
    f1, f2 = st.columns(2)
    role_filter = f1.selectbox("Role", ["All", "Starters", "Relievers"])
    min_pa = f2.slider("Minimum RISP PA", 0, int(scored["PA_RISP"].max()), 20)

    board = scored[scored["PA_RISP"] >= min_pa]
    if role_filter != "All":
        is_start = board["Role"].str.contains("Starter", case=False, na=False)
        board = board[is_start if role_filter == "Starters" else ~is_start]

    cols = ["Pitcher", "Team", "Role", "PA_RISP", "Eval_Score", "Tier",
            "Standard_ERA", "pERA"]
    board = board.sort_values("Eval_Score")[cols].reset_index(drop=True)
    board.index += 1

    st.caption("Lower score is better. Sorted best to worst.")
    st.dataframe(board, use_container_width=True)

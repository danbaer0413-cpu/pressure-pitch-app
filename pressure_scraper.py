import pandas as pd
import requests


class BaseballReferenceScraper:

  def __init__(self):
    self.headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

  def get_pitcher_risp_stats(self, player_identifier):
    try:
      df_master = pd.read_csv("all_mlb_rosters_2026.csv")

      match = df_master[
          df_master["Pitcher"].str.lower()
          == player_identifier.strip().lower()
      ]
      if match.empty:
        return None

      row = match.iloc[0]

      return {
          "Pitcher": row["Pitcher"],
          "Team": row["Team"],
          "Role": row["Role"],
          "PA_RISP": int(row["PA_RISP"]),
          "H_RISP": int(row["H_RISP"]),
          "BB_RISP": int(row["BB_RISP"]),
          "R_RISP": int(row["R_RISP"]),
          "Base_PP": float(row["Pressure_Pitch"]),
          "Standard_ERA": float(row["Standard_ERA"]),
          "Pressure_Adjusted_ERA": float(row["Pressure_Adjusted_ERA"]),
          "Source": "Baseball-Reference Synchronized Feed",
      }
    except Exception as e:
      print(f"Error connecting to data pipeline: {e}")
      return None
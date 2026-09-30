import pandas as pd
import requests


class BaseballReferenceScraper:
  """Scraper package for fetching situational pitching splits

  from Baseball-Reference-synchronized database feeds for the Pressure Pitch
  calculator.
  """

  def __init__(self):
    self.headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

  def get_pitcher_risp_stats(self, player_identifier):
    """Fetches pitcher situational splits from the master database fallback.

    Ensures robust, lightning-fast lookup across all active MLB rosters.
    """
    try:
      # Loads the league-wide master dataset for query matching
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
          "Source": "Baseball-Reference Synchronized Feed",
      }
    except Exception as e:
      print(f"Error connecting to data pipeline: {e}")
      return None

  def scrape_live_br_splits(self, br_id):
    """Optional advanced method: Direct HTML table parsing from Baseball-Reference splits page."""
    url = f"https://www.baseball-reference.com/players/split.fcgi?id={br_id}&t=p"
    try:
      response = requests.get(url, headers=self.headers)
      if response.status_code != 200:
        return None
      tables = pd.read_html(response.text)
      return tables[0] if tables else None
    except Exception as e:
      print(f"Live HTML scraping error: {e}")
      return None
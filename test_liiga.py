
import requests
import json

# Base address of the Liiga Stats API from Swagger.
BASE_URL = "https://prod.liiga-backend.liiga.fi/stats"

# The endpoint for retrieving games.
ENDPOINT = "/api/v1/games"

# Query parameters documented in Swagger.
params = {
    "season": 2027,          # 2026-2027 season
    "serie": "RUNKOSARJA",    # Regular season
    "limit": 100              # Retrieve at most 100 games
}

try:
    # Send an HTTP GET request.
    response = requests.get(
        f"{BASE_URL}{ENDPOINT}",
        params=params,
        timeout=15
    )

    # Display the exact URL that Python requested.
    print("Request URL:", response.url)

    # Raise an exception if the HTTP request failed.
    response.raise_for_status()

    # Convert the JSON response into Python objects.
    data = response.json()

    # The V1 Swagger schema describes an object
    # containing a list under the key "games".
    games = data["games"]

    print(f"\nNumber of games returned: {len(games)}")
    print(f"Data columns can be taken are: {list(games[0].keys()) if games else 'No games returned'}")
    # Display a readable summary of each match.
    for game in games:
        home = game["homeTeam"]
        away = game["awayTeam"]

        print("------------------------------")
        print("Match ID:", game["id"])
        print("Date:", game["start"])
        print(
            f"{home['teamName']} {home['goals']}"
            f" - {away['goals']} {away['teamName']}"
        )
        print("Finished:", game["ended"])

    # Print a formatted JSON example for inspection.
    if games:
        with open("json_data.json", "w") as f:
            json.dump(games[0], f, indent=2, ensure_ascii=False)

except requests.exceptions.RequestException as error:
    print("HTTP request failed:", error)

except (KeyError, TypeError, ValueError) as error:
    print("Unexpected response structure:", error)

import datetime
import time
from typing import List, Tuple, Optional, Dict, Any

import arrow
import pycountry
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.transfermarkt.co.uk"
USER_AGENT = "Mozilla/5.0"


def find_player(player_name: str) -> List[Tuple[str, str]]:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={player_name}",
        headers=headers,
    )

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"class": "items"})

    players_data = []
    try:
        for row in table.find_all("table", {"class": "inline-table"}):
            hrefs = row.find("a", {"class": "spielprofil_tooltip"})
            player_id = hrefs["id"]
            player_url = hrefs["href"]
            player_ref_url = player_url.split("/")[1]
            players_data.append((player_id, player_ref_url))
            break
    except:
        raise ValueError(f"{player_name} not found!")

    return players_data


def get_club_data(
    player_id: str, player_ref_url: str, date: str = None
) -> Tuple[
    str,
    str,
    str,
    str,
    str,
    Dict[str, Tuple[int, int, int, int, int, int]],
    Dict[str, int],
]:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        f"{BASE_URL}/{player_ref_url}/profil/spieler/{player_id}",
        headers=headers,
    )
    _date = arrow.get(date, "DD/MM/YYYY")
    team = None
    time_in_team = None
    soup = BeautifulSoup(response.text, "html.parser")
    birth_date = None
    citizenship = None
    position = None
    for row in soup.find("table", {"class": "auflistung"}).find_all("tr"):
        if row.find("th").text.lower().strip() == "date of birth:":
            birth_date = row.find("a").text.strip()
        elif row.find("th").text.lower().strip() == "position:":
            position = row.find("a").text.strip()
        elif row.find("th").text.lower().strip() == "citizenship:":
            country = row.find("img").attrs["title"]
            try:
                citizenship = pycountry.countries.search_fuzzy(country)[
                    0
                ].alpha_3
            except:
                try:
                    citizenship = pycountry.countries.search_fuzzy(
                        country.split("-")
                    )[0].alpha_3
                except:
                    citizenship = country
    for row in soup.find_all("tr", {"class": "zeile-transfer"}):
        cells = row.find_all("td")
        cell_date = arrow.get(cells[1].text, "MMM D, YYYY")
        if cell_date > _date:
            continue
        team = cells[-4].text.strip()
        time_in_team = arrow.get(
            datetime.datetime.now() - (_date - cell_date)
        ).humanize()
        break
    assert team is not None
    assert time_in_team is not None
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        f"{BASE_URL}/{player_ref_url}/"
        f"leistungsdaten/spieler/{player_id}/0?saison={_date.year - 1}",
        headers=headers,
    )
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"class": "items"})

    summary_data = {}
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        summary_data[cells[1].text.strip()] = (
            cells[2].text.strip(),
            cells[3].text.strip(),
            cells[4].text.strip(),
            cells[5].text.strip(),
            cells[6].text.strip(),
            cells[7].text.strip(),
        )

    goals_against = {}
    data_divs = soup.find_all("div", {"class": "responsive-table"})
    if len(data_divs) == 0:
        return (
            birth_date,
            citizenship,
            position,
            team,
            time_in_team,
            summary_data,
            goals_against,
        )
    data_div_of_not_summary = data_divs[1:]
    for data_div in data_div_of_not_summary:
        for row in data_div.find("tbody").find_all("tr", {"class": ""}):
            cells = row.find_all("td")
            if len(cells) < 9:
                continue
            team_against = cells[5].text.strip().lower()
            if not team_against:
                team_against = cells[6].text.strip().lower()
            if team_against not in goals_against:
                goals_against[team_against] = 0
            goals = cells[8].text.strip()
            try:
                int(goals)
            except:
                if len(goals) > 0:
                    goals = cells[9].text.strip()
            if goals:
                goals_against[team_against] += int(goals)
    return (
        birth_date,
        citizenship,
        position,
        team,
        time_in_team,
        summary_data,
        goals_against,
    )


def get_national_team_data(
    player_id: str,
    player_ref_url: str,
    from_date: str = None,
    to_date: str = None,
) -> Tuple[int, int, int, Dict[str, int]]:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(
        f"{BASE_URL}/{player_ref_url}/nationalmannschaft/spieler/{player_id}",
        headers=headers,
    )
    soup = BeautifulSoup(response.text, "html.parser")
    data_divs = soup.find_all("div", {"class": "responsive-table"})
    total_goals = 0
    total_assists = 0
    total_presences = 0
    goals_against = {}
    if len(data_divs) == 0:
        return total_presences, total_goals, total_assists, goals_against
    data_div = data_divs[-1]
    for row in data_div.find("tbody").find_all("tr", {"class": ""})[1:]:
        cells = row.find_all("td")
        if len(cells) <= 5:
            continue
        date = cells[2].text.strip()
        if not is_date_between(date, from_date=from_date, to_date=to_date):
            break
        team_against = cells[6].text.strip().lower()
        if team_against not in goals_against:
            goals_against[team_against] = 0
        goals = cells[9].text.strip()
        assists = cells[10].text.strip()
        # print((date, team_against, goals, assists))
        if goals:
            total_goals += int(goals)
            goals_against[team_against] += int(goals)
        if assists:
            total_assists += int(assists)
        total_presences += 1
    return total_presences, total_goals, total_assists, goals_against


def is_date_between(
    date: str, from_date: Optional[str], to_date: Optional[str]
) -> bool:
    _date = arrow.get(date, "M/D/YY")
    if from_date:
        _from_date = arrow.get(from_date, "DD/MM/YYYY")
        if to_date:
            _to_date = arrow.get(to_date)
            return _date.is_between(_from_date, _to_date)
        return _from_date < _date
    if to_date:
        _to_date = arrow.get(to_date, "DD/MM/YYYY")
        return _to_date > _date
    return True


def get_complete_data(
    players: List[str],
    lookup_date: str,
    team_against: str = None,
    to_print: bool = False,
) -> List[Dict[str, Any]]:
    ret_data = []
    for player in players:
        player_data = {}
        data = find_player(player)
        for player_id, player_ref_url in data:
            [
                nat_presences,
                nat_goals,
                nat_assists,
                nat_goals_data,
            ] = get_national_team_data(
                player_id, player_ref_url, to_date=lookup_date
            )
            goal_against = -1
            if team_against:
                goal_against = nat_goals_data.get(team_against.lower(), -1)

            player_data["full_name"] = player
            player_data["id"] = player_id
            player_data["ref_url"] = player_ref_url
            player_data["nat_presences"] = nat_presences
            player_data["nat_goals"] = nat_goals
            player_data["nat_assists"] = nat_assists
            player_data["nat_goals_against"] = nat_goals_data
            if to_print:
                print(
                    f"{player}|{nat_presences}|{nat_goals}|{nat_assists}|"
                    f"{goal_against}"
                )

            [
                birth_date,
                citizenship,
                position,
                team,
                time_in_team,
                team_summary_data,
                team_goals_against,
            ] = get_club_data(player_id, player_ref_url, date=lookup_date)
            goal_against = -1
            if team_against:
                goal_against = team_goals_against.get(team_against.lower(), -1)
            _date = arrow.get(lookup_date, "DD/MM/YYYY")
            cell_date = arrow.get(birth_date, "MMM D, YYYY")
            age = arrow.get(
                datetime.datetime.now() - (_date - cell_date)
            ).humanize()
            player_data["birth_date"] = birth_date
            player_data["age"] = age
            player_data["country"] = citizenship
            player_data["position"] = position
            player_data["team"] = team
            player_data["time_in_team"] = time_in_team
            player_data["year_summary_data"] = team_summary_data
            player_data["team_goals_against"] = team_goals_against
            if to_print:
                print(
                    f"{player}|{age}|{birth_date}|{citizenship}|{team}|"
                    f"{time_in_team}|{goal_against}|{team_summary_data}|"
                )
            ret_data.append(player_data)
    return ret_data


if __name__ == "__main__":
    start_time = time.time()
    curr_date = "09/05/2018"
    juventus_players = [
        "Gianluigi Buffon",
        "Juan Cuadrado",
        "Andrea Barzagli",
        "Medhi Benatia",
        "Kwadwo Asamoah",
        "Sami Khedira",
        "Miralem Pjanic",
        "Blaise Matuidi",
        "Paulo Dybala",
        "Mario Mandzukic",
        "Douglas Costa",
    ]
    juventus_bench = [
        "Carlo Pinsoglio",
        "Wojciech Szczesny",
        "Mattia De Sciglio",
        "Claudio Marchisio",
        "Gonzalo Higuain",
        "Alex Sandro",
        "Benedikt Howedes",
        "Daniele Rugani",
        "Stephan Lichtsteiner",
        "Stefano Sturaro",
        "Rodrigo Bentancur",
        "Federico Bernardeschi",
    ]

    milan_players = [
        "Gianluigi Donnarumma",
        "Davide Calabria",
        "Leonardo Bonucci",
        "Alessio Romagnoli",
        "Ricardo Rodriguez",
        "Franck Kessie",
        "Manuel Locatelli",
        "Giacomo Bonaventura",
        "Suso",
        "Patrick Cutrone",
        "Hakan Calhanoglu",
    ]
    milan_bench = [
        "Marco Storari",
        "Antonio Donnarumma",
        "Jose Mauri",
        "Nikola Kalinic",
        "Andre Silva",
        "Fabio Borini",
        "Cristian Zapata",
        "Riccardo Montolivo",
        "Ignazio Abate",
        "Lucas Biglia",
        "Mateo Musacchio",
        "Luca Antonelli",
    ]
    print("===================================================")
    get_complete_data(juventus_players, curr_date, "milan", to_print=True)
    print("===================================================")
    get_complete_data(juventus_bench, curr_date, "milan", to_print=True)
    print("===================================================")
    get_complete_data(milan_players, curr_date, "juventus", to_print=True)
    print("===================================================")
    get_complete_data(milan_players, curr_date, "juventus", to_print=True)
    print("===================================================")

    print("Done in ", time.time() - start_time)

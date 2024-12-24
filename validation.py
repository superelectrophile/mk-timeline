import csv
import re
from pathlib import Path

import pandas as pd
from schema import And, Or, Schema, Use


def to_numeric_time(time: str) -> float:
    digits = time.split(":")
    assert len(digits) == 3, f"unable to parse time string: {time}"
    hours = int(digits[0])
    minutes = int(digits[1])
    seconds = float(digits[2])
    return 3600 * hours + 60 * minutes + seconds


def to_display_time(time: float) -> str:
    hours = int(time // 3600)
    minutes = int(time // 60) % 60
    seconds = time % 60

    return f"{hours:02}:{minutes:02}:{seconds:04.1f}"


HEX_CODE_REGEX = re.compile(r"#[\dABCDEF]{6}")


def is_hex_code(value: str) -> bool:
    return HEX_CODE_REGEX.match(value)


def is_valid_level(value: int) -> bool:
    return value >= 0


def get_rows(csv_file: Path) -> list:
    with csv_file.open("r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def validate(data_path: Path):
    # 1. Validate data files

    COLORS_SCHEMA = Schema([{"Color": str, "Hex Code": is_hex_code}])
    colors_list = COLORS_SCHEMA.validate(get_rows(data_path / "colors.csv"))
    colors = {row["Color"]: row for row in colors_list}

    MARBLES_SCHEMA = Schema(
        [
            {
                "Marble Name": str,
                "Full Name": str,
                "Type": str,
                "Color": lambda col: col in colors,
                "Final Level": And(
                    Use(int),
                    is_valid_level,
                ),
                "Kills": And(
                    Use(int),
                    lambda val: val >= 0,
                ),
            }
        ]
    )

    marbles_list = MARBLES_SCHEMA.validate(get_rows(data_path / "marbles.csv"))
    marbles = {row["Marble Name"]: row for row in marbles_list}

    BEGIN_SCHEMA = Schema(
        [
            {
                "Time": Use(to_numeric_time),
                "Marble Name": And(str, lambda name: name in marbles),
                "Location": Or("-", lambda loc: loc in marbles),
                "Level": And(Use(int), is_valid_level),
                "Type": Or("Born", "Summon", "Revive"),
            }
        ]
    )
    begins = BEGIN_SCHEMA.validate(get_rows(data_path / "begin.csv"))

    LEVEL_SCHEMA = Schema(
        [
            {
                "Time": Use(to_numeric_time),
                "Marble Name": And(str, lambda name: name in marbles),
                "Level": And(Use(int), is_valid_level),
            }
        ]
    )
    levels = LEVEL_SCHEMA.validate(get_rows(data_path / "level.csv"))

    END_SCHEMA = Schema(
        [
            {
                "Time": Use(to_numeric_time),
                "Marble Name": And(str, lambda name: name in marbles),
                "Location": Or("BATTLE", "-", lambda loc: loc in marbles),
                "Level": And(Use(int), is_valid_level),
                "Type": Or("Death", "Survive"),
            }
        ]
    )
    ends = END_SCHEMA.validate(get_rows(data_path / "end.csv"))

    BATTLE_SCHEMA = Schema(
        [
            {
                "Battle Id": str,
                "Begin": Use(to_numeric_time),
                "End": Use(to_numeric_time),
            }
        ]
    )
    battle_list: list = BATTLE_SCHEMA.validate(get_rows(data_path / "battles.csv"))
    battles = {row["Battle Id"]: row for row in battle_list}

    BATTLE_COLOR_SCHEMA = Schema(
        [
            {
                "Battle Id": lambda val: val in battles,
                "Color": lambda val: val in colors,
                "Is Winner": Use(bool),
            }
        ]
    )
    battle_colors = BATTLE_COLOR_SCHEMA.validate(
        get_rows(data_path / "battle-colors.csv")
    )

    BATTLE_MARBLE_SCHEMA = Schema(
        [
            {
                "Battle Id": lambda val: val in battles,
                "Marble Name": lambda val: val in marbles,
            }
        ]
    )
    battle_marbles = BATTLE_MARBLE_SCHEMA.validate(
        get_rows(data_path / "battle-marbles.csv")
    )

    colors_df = pd.DataFrame(colors_list)
    marbles_df = pd.DataFrame(marbles_list)
    begins_df = pd.DataFrame(begins)
    levels_df = pd.DataFrame(levels)
    ends_df = pd.DataFrame(ends)
    battles_df = pd.DataFrame(battle_list)
    battle_colors_df = pd.DataFrame(battle_colors)
    battle_marbles_df = pd.DataFrame(battle_marbles)

    # 2. Validate more complex data relationships

    # battles should not overlap
    battle_list.sort(key=lambda x: x["Begin"])
    for i in range(len(battle_list) - 1):
        battle1 = battle_list[i]
        battle2 = battle_list[i + 1]
        assert (
            battle1["End"] < battle2["Begin"]
        ), f"battle {battle1["Battle Id"]} ends after {battle2["Battle Id"]}"

    # check colors of marbles in battle
    for id in battles:
        battle_colors = battle_colors_df[battle_colors_df["Battle Id"] == id]["Color"]
        assert (
            battle_marbles_df[battle_marbles_df["Battle Id"] == id]
            .merge(marbles_df, on="Marble Name")["Color"]
            .isin(battle_colors)
            .all()
        )

    # verify history of all marbles
    for marble in marbles:
        events = []
        events.extend(
            begins_df[begins_df["Marble Name"] == marble]
            .apply(
                lambda row: (row["Time"], row["Type"], row["Level"], row["Location"]),
                axis=1,
            )
            .to_list()
        )
        events.extend(
            levels_df[levels_df["Marble Name"] == marble].apply(
                lambda row: (row["Time"], "Level", row["Level"]), axis=1
            )
        )
        events.extend(
            ends_df[ends_df["Marble Name"] == marble].apply(
                lambda row: (row["Time"], row["Type"], row["Level"], row["Location"]),
                axis=1,
            )
        )
        events.extend(
            battle_marbles_df[battle_marbles_df["Marble Name"] == marble]
            .merge(battles_df, on="Battle Id")
            .apply(lambda row: (row["Begin"], "Begin Battle"), axis=1)
        )
        events.extend(
            battle_marbles_df[battle_marbles_df["Marble Name"] == marble]
            .merge(battles_df, on="Battle Id")
            .apply(lambda row: (row["End"], "End Battle"), axis=1)
        )
        events.sort(key=lambda ev: ev[0])

        # print(marble)
        # for event in events:
        #     print(f"|\t{str(event)}")

        state = "unalive"
        level = None

        # doesn't handle rare case where a marble
        # is born in battle and immediately levels up
        # in that same battle; not possible before MK 27

        for event in events:
            type = event[1]
            match state:
                case "unalive":
                    match type:
                        case "Born" | "Summon":
                            state = "alive"
                            level = event[2]
                        case other:
                            raise ValueError(str(event))
                case "alive":
                    match type:
                        case "Begin Battle":
                            state = "battle"
                        case "Survive":
                            state = "done"
                            assert event[3] != "BATTLE"
                        case other:
                            raise ValueError(str(event))
                case "battle":
                    match type:
                        case "End Battle":
                            state = "alive"
                        case "Level":
                            assert event[2] == level + 1
                            level += 1
                        case "Death":
                            state = "dead"
                            assert event[3] == "BATTLE"
                        case other:
                            raise ValueError(str(event))
                case "dead":
                    match type:
                        case "Revive":
                            state = "alive"
                            assert level == event[2]
                        case "End Battle":
                            pass
                        case other:
                            raise ValueError(str(event))
                case "done":
                    raise ValueError("no more events when done")
                case other:
                    raise ValueError(f"bad state: {other}")

        assert (
            level
            == marbles_df[marbles_df["Marble Name"] == marble]["Final Level"].iloc[0]
        )

    return


if __name__ == "__main__":
    DATA_PATH = Path("data")
    validate(DATA_PATH)

# MK Timeline
Timeline graphic visualization for [Marble Kingdoms 27](https://www.youtube.com/watch?v=zAvNq0q4304). Thought it would be cool to do this. 

# Data Structure
```
data/colors.csv
| Color[str]
| Hex Code[str]

data/marbles.csv
| Marble Name[str]
| Full Name[str]
| Type[str]
| Color[str]
| Final Level[int]
| Kills[int]

data/begin.csv
| Time[time]
| Marble Name[str]
| Location[str]
| Level[str]
| Type[str]

data/level.csv
| Time[time]
| Marble Name[str]
| Level[str]

data/end.csv
| Time[time]
| Marble Name[str]
| Location[str]
| Level[str]
| Type[str]

data/battles.csv
| Battle Id[int]
| Begin[time]
| End[time]

data/battle-colors.csv
| Battle Id[int]
| Color[str]
| Is Winner[bool]

data/battle-marbles.csv
| Battle Id[int]
| Marble Name[str]
```


# Getting Started
```
mkdir -p debug
pip install -r requirements.txt
sh download-video.sh
```
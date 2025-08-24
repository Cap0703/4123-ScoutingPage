# 4123-ScoutingPage
A json configurable webpage for all things FRC Scouting

## Features
* Dynamic Forms through config.json
* Live Scoring - Auto, Teleop, and Endgame Period all have live scoring
* Offline Mode - When Users in the Pit Scouting and Match Scouting Forms lose connection, entries are saved locally and synced automatically when back online
* Customizable Config - Define fields, point values, options, and layout without changing any code
* Pit Scouting - Supports text, image, and structured fields
* Match Scouting - Includes sections such as; pre-match info, autonomous, teleop, endgame, and misc sections
* Mobile Support - Sections are collapsible on mobile for better user experience

## Documentation
### Match Form Structure
_________________

```
{
  "match_form": {
    "pre-match_info": { ... },
    "auto_period": { ... },
    "teleop_period": { ... },
    "endgame": { ... },
    "misc": { ... }
  }
}
```

### Form Field Types
Each section contains fields. The field type determines which form input is rendered.
_________________

#### Boolean
Checkbox that stores true/false.
```
"mobility": {
  "Type": "Boolean"
}
```
---
#### Boolean With Value
Checkbox that adds points when checked.
```
"left_starting_zone": {
  "Type": "Boolean with Value",
  "Value": 3
}
```
---
#### String
Text input field.
```
"comments": {
  "Type": "String"
}
```
---
#### Integer
Number input with +/– buttons.
```
"cubes_scored": {
  "Type": "Integer"
}
```
---
#### Scoring Object
Made/Missed counters with point value.
```
"L1": {
  "Made": 0,
  "Missed": 0,
  "Value": 3
}
```
Form auto-renders Made and Missed inputs.
Total Points = Made × Value.

---
#### Single Choice
Dropdown selection.
```
"starting_position": {
  "Type": "Single Choice",
  "options": ["Left", "Center", "Right"]
}
```
---
#### Single Choice with Values
Dropdown with scoring values.
```
"final_status": {
  "Type": "Single Choice",
  "options": ["Parked", "Climbed"],
  "values": [2, 6]
}
```
---
#### Multiple Choice
Checkbox list
```
"game_pieces": {
  "Type": "Multiple Choice",
  "options": ["Cube", "Cone"]
}
```
---
#### Multiple Choice with Values
Checkbox list where each option has a point value.
```
"coopertition_bonus": {
  "Type": "Multiple Choice",
  "options": ["Balanced", "Unbalanced"],
  "Values": [5, 0]
}
```
---
#### Timer
Start/Stop/Reset timer field.
```
"hang_time": {
  "Type": "Timer"
}
```
---
#### Image
File upload
```
"robot_picture": {
  "Type": "Image File"
}
```
---
### Computed Fields
config.json supports *computed_fields*, which lets you define fomrula for calculated values (like total points, accuracy, EPA-style stats).
Formulas in this section use SQL-like syntax but are executed in JavaScript on the frontend (team_summary.html).
_________________

**Example**
```
"computed_fields": {
  "auto_total": "json_extract(auto_json,'$.L1.Made') * json_extract(auto_json,'$.L1.Value') + json_extract(auto_json,'$.L2.Made') * json_extract(auto_json,'$.L2.Value')",
  "teleop_total": "json_extract(teleop_json,'$.L1.Made') * json_extract(teleop_json,'$.L1.Value') + json_extract(teleop_json,'$.L2.Made') * json_extract(teleop_json,'$.L2.Value')",
  "endgame_total": "CASE json_extract(endgame_json,'$.final_status') WHEN 'Climbed' THEN 6 ELSE 2 END",
  "total_points": "auto_total + teleop_total + endgame_total"
}
```
#### Supported Functions
* Round(value, precision) --> Round to given decimal places
* Coalesce(a, b, ...) --> First non-null value
* Case When ... Then ... Else ... End --> Conditional Logic
#### JSON Access
* *json_extract(auto_json, '$.L1.Made')* -- > Gets value from match JSON
* Supports access to *pre_match_json*, *auto_json*, *teleop_json*, *endgame_json*, *misc_json*

## Access
(https://four123-scoutingpage.onrender.com/)

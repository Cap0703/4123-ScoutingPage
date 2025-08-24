# Documentation
## Match Form Structure

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

## Form Field Types
&emsp;Each section contains fields. The field type determines which form input is rendered.

#### Boolean
&emsp;Checkbox that stores true/false.
```
"mobility": {
  "Type": "Boolean"
}
```
---
#### Boolean With Value
&emsp;Checkbox that adds points when checked.
```
"left_starting_zone": {
  "Type": "Boolean with Value",
  "Value": 3
}
```
---
#### String
&emsp;Text input field.
```
"comments": {
  "Type": "String"
}
```
---
#### Integer
&emsp;Number input with +/– buttons.
```
"cubes_scored": {
  "Type": "Integer"
}
```
---
#### Scoring Object
&emsp;Made/Missed counters with point value.
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
&emsp;Dropdown selection.
```
"starting_position": {
  "Type": "Single Choice",
  "options": ["Left", "Center", "Right"]
}
```
---
#### Single Choice with Values
&emsp;Dropdown with scoring values.
```
"final_status": {
  "Type": "Single Choice",
  "options": ["Parked", "Climbed"],
  "values": [2, 6]
}
```
---
#### Multiple Choice
&emsp;Checkbox list
```
"game_pieces": {
  "Type": "Multiple Choice",
  "options": ["Cube", "Cone"]
}
```
---
#### Multiple Choice with Values
&emsp;Checkbox list where each option has a point value.
```
"coopertition_bonus": {
  "Type": "Multiple Choice",
  "options": ["Balanced", "Unbalanced"],
  "Values": [5, 0]
}
```
---
#### Timer
&emsp;Start/Stop/Reset timer field.
```
"hang_time": {
  "Type": "Timer"
}
```
---
#### Image
&emsp;File upload
```
"robot_picture": {
  "Type": "Image File"
}
```
---
## Computed Fields
config.json supports *computed_fields*, which lets you define fomrula for calculated values (like total points, accuracy, EPA-style stats).
Formulas in this section use SQL-like syntax but are executed in JavaScript on the frontend (team_summary.html).

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
---
## Team Summary Config
&emsp;In config.json, you can configure what appears in Team Summary:
```
"team_summary": {
  "team_info": {
    "get_team_name": true,
    "get_team_epa": true,
    "get_team_rank_in_state": true,
    "get_team_rank_in_country": false,
    "get_team_rank_in_world": true,
    "year": 2025
  },
  "charts": {
    "Auto Coral Performance": {
      "x_label":"Match #",
      "y_label":"Auto Coral",
      "backgroundColor":"rgba(153, 102, 255, 0.2)",
      "borderColor":"rgba(153, 102, 255, 1)",
      "x":"match_number",
      "y":[
        "auto_coral_used",
        "auto_L1_made",
        "auto_L2_made",
        "auto_L3_made",
        "auto_L4_made"
      ],
      "graph": "line graph"
  },
  "tables": {
    "title":["Match Point Breakdown"],
    "table":{
      "match_point_breakdown_table":{
        "columns": [
          "match_number", 
          "match_type", 
          "auto_points", 
          "teleop_points", 
          "endgame_points", 
          "total_points"
        ]
      }
  }
}
```
* team_info → Controls what metadata is fetched via /api/team/{team}/info.
* charts → Define chart name, x-axis field, y-axis field(s), and labelss
* tables → Define table name and list of columns to display.

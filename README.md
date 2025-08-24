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
### Fields



## Access
(https://four123-scoutingpage.onrender.com/)

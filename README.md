# 4123-ScoutingPage
&emsp;A json configurable webpage for all things FRC Scouting

## Features
* Dynamic Forms through config.json
* Live Scoring - Auto, Teleop, and Endgame Period all have live scoring
* Offline Mode - When Users in the Pit Scouting and Match Scouting Forms lose connection, entries are saved locally and synced automatically when back online
* Customizable Config - Define fields, point values, options, and layout without changing any code
* Pit Scouting - Supports text, image, and structured fields
* Match Scouting - Includes sections such as; pre-match info, autonomous, teleop, endgame, and misc sections
* Mobile Support - Sections are collapsible on mobile for better user experience

## Infrastructure
* Frontend: HTML, CSS, JavaScript
* Backend: Python (Flask)
* Database: SQLite3

## API Endpoints
```
GET /api/config
```
&emsp;Returns config.json

---
```
POST /api/matches
```
&emsp;Upload match scouting entry

---
```
POST /api/pits
```
&emsp;Upload pit scouting entry

---
```
GET /api/team/{team}/averages
```
&emsp;Computed team average per team

---
```
GET /api/team/{team}/matches
```
&emsp;Raw match data per team

## Documentation
Visit docs/config.md

## Access
(https://four123-scoutingpage.onrender.com/)

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
* If hosting using a free service, many don't allow 3rd party API requests. (statbotics won't work)

## Infrastructure
* Frontend: HTML, CSS, JavaScript
* Backend: Python (Flask)
* Database: SQLite3

## API Endpoints
___

#### Core Data Endpoints

```GET / & GET /<path:path>```
* Serves the frontend application fromt he public directory.

```GET /api/config```
* Returns the entire configuration object from config.json.
    &emsp;Used to build forms and tables

```POST /api/upload```
* Handles image file uploads and saves it to the uploads directory then returns the path

```GET /uploads/<filename>```
* Serves an uploaded image file from the uploads directory


#### Match Scouting Endpoints

```POST /api/matches```
* Creates a new match scouting entry and inserts the data into the matches table

```GET /api/matches```
* Retrieves a paginated list of all match scouting records

```PUT /api/matches/<match_id>```
* Updates a specific match scouting entry by its ID

```DELETE /api/matches/<match_id>```
* Deletes a spcific match scouting entry by its ID

## Documentation
Visit docs/config.md

## Access
(https://cap0703.github.io/4123-ScoutingPage/)

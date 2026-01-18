# LunaSkye-Core
The primary goal of this project is to help users make informed economical decisions in EVE Online, using data gathered from the game's main trade hub, as well as the GSF Alliance Trade Hub.
There is a discord for this project which can be found on the GSF Forums.

## Modules
Each of these modules aims to create seperation at the different layers of the project, allowing for easier debugging, and easier expansion in the future.

### `ESI Interface`
The true "beating heart" of the core project, this module handles all interactions with ESI (EVE Online's API Interface).

### `The Market Hand`
Serving as the interface between the **`ESI Interface` Module**, and discord users. This module takes in discord slash commands, hands them off to a specific script in the **Market Module**, and returns the requested data.

### `Fitting Import Calculator`
A utility meant for those who want to import doctrine fits, this module uses data collected from the **`ESI Interface` Module** and uses it to help users know what parts of a fit are cheaper to import from Jita, and which parts are cheaper to buy localy.
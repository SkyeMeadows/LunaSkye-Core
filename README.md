# LunaSkye Core Modules

While currently undergoing a major rework of a majority of the codebase, these projects work to provide financial data centered around industry and mining for EVE Online.

This project is currently non-functional.

## Modules
Each of these modules aims to create seperation at the different layers of the project, allowing for easier debugging, and future expansion.

### ESI Interface
The true "beating heart" of the core project, this module handles all interactions with ESI (EVE Online's API Interface).
In its legacy version, the ESI-Interface module also ran various calculations of statistcs not directly available in ESI.

### The Market Hand
Serving as the interface between the **ESI Interface** module, and discord users, this module takes in discord slash commands, hands them off to a specific script in this module, and returns either a graph, or the other requested data.

### Anomaly Evaluator
[Deprecated] This module's development has been abandonded

### Fitting Import Calculator
[Deprecated] This module's development has been abandonded
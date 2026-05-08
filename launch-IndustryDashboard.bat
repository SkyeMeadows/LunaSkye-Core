:: hypercorn module_name:app_object - to run a specific part of a file

:: hypercorn myproject.main:app - to run a file inside a directory

:: hypercorn app:app --bind 0.0.0.0:3387 - to bind to a port

@echo on
hypercorn modules.webapps.industry_dashboard.webpage --bind localhost:5003
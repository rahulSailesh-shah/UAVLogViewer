# UAV Log Viewer

![log seeking](preview.gif "Logo Title Text 1")

This is a Javascript based log viewer for Mavlink telemetry and dataflash logs.
[Live demo here](http://plot.ardupilot.org).

## Backend

This project includes an AI-powered backend system for intelligent log analysis. The backend provides:

-   **Agentic AI Architecture** - Multi-agent workflow for intelligent log analysis
-   **Natural Language Queries** - Ask questions about your flight data in plain English
-   **Vector Database Search** - Semantic search through log message definitions
-   **Real-time Communication** - WebSocket-based communication with the frontend

For detailed setup and documentation, see the [Backend README](backend/README.md).

## Build Setup

```bash
# install dependencies
npm install

# serve with hot reload at localhost:8080
npm run dev

# build for production with minification
npm run build

# run unit tests
npm run unit

# run e2e tests
npm run e2e

# run all tests
npm test
```

# Docker

run the prebuilt docker image:

```bash
docker run -p 8080:8080 -d ghcr.io/ardupilot/uavlogviewer:latest

```

or build the docker file locally:

```bash

# Build Docker Image
docker build -t <your username>/uavlogviewer .

# Run Docker Image
docker run -e VUE_APP_CESIUM_TOKEN=<Your cesium ion token> -it -p 8080:8080 -v ${PWD}:/usr/src/app <your username>/uavlogviewer

# Navigate to localhost:8080 in your web browser

# changes should automatically be applied to the viewer

```

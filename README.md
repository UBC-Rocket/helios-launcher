# Project Helios Launcher

A comprehensive graphical launcher for managing and orchestrating Project Helios components and services. This application provides a user-friendly interface to configure, build, and deploy containerized Helios services including HeliosCore and the Livestreaming service.

## Overview

The Helios Launcher is a desktop application built with ImGui that serves as a centralized control center for Helios microservices. It manages:

- **Component Hierarchy**: Visual tree representation of all Helios components and their relationships
- **Docker Orchestration**: Automated building, management, and status tracking of Docker images
- **Configuration Management**: Save and load component configurations
- **Git Integration**: Automatic cloning and checkout of specific repository commits
- **Real-time Monitoring**: Live build status and progress tracking

## System Requirements

- **Python**: 3.12 or higher
- **Docker**: Latest version (required for containerized component deployment)
- **Git**: For repository cloning and version management
- **OS**: Windows, macOS, or Linux

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/helios-data/helios-launcher.git
cd helios-launcher
```

### 2. Set Up Python Environment

The project uses `uv` for package management. Install dependencies:

```bash
# Install using uv (recommended)
pip install uv

make submodule
uv sync
```

### 3. Generate Protocol Buffer Files

Before running the application, generate the required protobuf Python files:

```bash
make protos
```

This command compiles all `.proto` files in the `helios-protos/` directory into Python modules.

## Quick Start

### Running the Launcher

```bash
make run
```

Or directly:

```bash
uv run src/main.py
```

The application will launch with the Helios Launcher GUI window 

# Project Plan: Slurm TUI Monitor

**Role**: DevOps Project Manager
**Methodology**: Agile Epics

This document outlines the development roadmap broken down into verifiable epics. Each task includes a "Verification" step to ensure functionality before integration.

## 📦 Epic 1: Foundation & Environment Setup

Goal: Initialize the project structure, dependency management, and prove connectivity capability.

- [x] Task 1.1: Project Initialization

  - Initialize project using uv.
  - Define dependencies: textual, rich.
  - Create directory structure: src/, tests/.
  - Verification: uv sync runs successfully; import textual works in a test script.

- [x] Task 1.2: SSH Wrapper Prototype

  - Create a simple Python script using subprocess to run ssh <host> echo "success".
  - Handle ssh timeout and connection errors (e.g., host unreachable).
  - Verification: Script prints "success" when connected to the cluster and handles errors gracefully if VPN/Network is down.

## ⚙️ Epic 2: Core Data Engine (Backend)

Goal: Reliably fetch and parse raw data from Slurm without blocking the main thread.

- [x] Task 2.1: Squeue Parser

  - Implement method to run: squeue --me -o "%i|%j|%T|%M|%o|%Z" --noheader.
  - Create a parser to convert the pipe-delimited string into a list of Dictionaries/Objects.
  - Verification: Unit test with mocked stdout returns correct JSON structure for active jobs.

- [x] Task 2.2: Sacct Parser (History)

  - Implement method to run: sacct -X --format=JobID,JobName,State,Elapsed,WorkDir --units=M -n.
  - Handle whitespace formatting specific to sacct.
  - Verification: Unit test accurately parses a sample sacct output string into structured data.

- [x] Task 2.3: Data Aggregation Service

  - Create a class that merges squeue (active) and sacct (history) results.
  - Ensure active jobs take precedence over history if duplicates exist.
  - Verification: Running the service returns a unified list of jobs sorted by time.

## 🔧 Epic 3: Configuration & Path Resolution

Goal: Make the application flexible enough to handle complex directory structures.

- [ ] Task 3.1: Config Loader

  - Implement logic to load ~/.config/slurm_monitor/config.json.
  - Define defaults if file is missing.
  - Verification: App reads remote_host from JSON; falls back to defaults if file missing.

- [ ] Task 3.2: Log Path Strategy Pattern

  - Implement the logic to interpret {work_dir}, {job_id}, and {project_name} tokens.
  - Implement logic to check specific_projects mapping first, then default_pattern.
  - Verification: Test case: Passing work_dir="/home/user/project1" and job_id="123" correctly returns /home/user/project1/logs/out/123.txt based on config.

## 🖥️ Epic 4: User Interface (Frontend)

Goal: specific Visual implementation using Textual.

- [ ] Task 4.1: App Skeleton & Header

  - Create App class inheriting from textual.app.App.
  - Implement Header with: Connection Name, Last Updated Timestamp, and Loading Spinner.
  - Verification: App launches, shows TUI, and spinner animates.

- [ ] Task 4.2: Data Table Implementation

  - Implement DataTable widget.
  - Map data columns: ID, Name, Status, Time.
  - Apply Rich styling (Green for Running, Red for Fail, etc.).
  - Verification: Hardcoded mock data renders correctly with colors in the terminal.

- [ ] Task 4.3: Async Data Binding

  - Connect Epic 2 (Data Engine) to Epic 4 (UI) using set_interval.
  - Ensure UI remains responsive while ssh command runs in background.
  - Verification: App updates list every 2 seconds without freezing the cursor.

## 🎮 Epic 5: Interaction & Control

Goal: Implement Vim-like navigation and the core "Tail" feature.

- [ ] Task 5.1: Vim Navigation

  - Bind j/k to row selection movement.
  - Bind g/G to top/bottom scroll.
  - Verification: User can navigate the table without using arrow keys.

- [ ] Task 5.2: The "Tail" Context Switch

  - Implement Enter key handler.
  - Use driver.suspend_application_mode() to drop to shell.
  - Construct and run ssh -t <host> tail -f <path>.
  - Verification: Pressing Enter opens a full-screen tail; Ctrl+C returns exactly to the previous TUI state.

## 📚 Epic 6: Documentation & Onboarding

Goal: Ensure the user can actually connect.

- [ ] Task 6.1: SSH Key Guide

  - Write README.md section on ssh-keygen and ssh-copy-id.
  - Explain ~/.ssh/config ControlMaster (optional optimization for faster polling).
  - Verification: A standard user can follow instructions to set up password-less auth.

- [ ] Task 6.2: Config Examples

  - Provide config.example.json covering standard and complex project structures.

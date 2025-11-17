# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## response rule
대답은 한국말로 하고 코드의 주석들도 가능한 한국말로 해줘.

## Project Overview

This is a data analysis pipeline project for processing Korean financial/accounting JSON data. The workflow involves:
1. Converting JSON files to XLSX format
2. Merging multiple XLSX files
3. Preprocessing the data
4. Analyzing the processed data

## Data Structure

- **Source Data**: `jsons/` directory contains yearly JSON files (2021-2025)
- Each JSON file contains Korean accounting records with fields like:
  - `cd_acctit`: 계정코드 (Account code)
  - `nm_acctit`: 계정명 (Account name)
  - `mn_bungae1/2`: 금액 (Amount)
  - `da_date`: 날짜 (Date)
  - `nm_trade`: 거래처명 (Trading partner)
  - And other financial metadata fields

## Directory Structure & Architecture

```
no_code_analyse/
├── jsons/          # Source JSON data files (2021-2025)
├── jsons2xlsx/     # JSON to XLSX conversion module
├── Preprocessing/  # Data preprocessing module
├── src/            # Main execution files
│   └── modules/    # Functional modules organized by feature
├── test/           # Testing directory for development
└── docs/           # Documentation
```

## Development Workflow

### Architecture Pattern

- **Main executables**: Place in `src/` directory
- **Feature modules**: Create separate Python files in `src/modules/` organized by functionality
- **Testing first**: Develop and test in `test/` directory before moving to `src/modules/`

### Korean Workflow (질제컨 Process)

This project follows the "질문-제안-컨펌-실행" (Question-Suggest-Confirm-Execute) workflow:

1. **질문 (Question)**: Ask clarifying questions to understand user intent
2. **제안 (Suggestion)**: Propose implementation approaches
3. **컨펌 (Confirm)**: Wait for user confirmation before proceeding
4. **실행 (Execute)**: Implement after confirmation

### Required Actions on Each Task

When implementing features:
1. Create appropriate GitHub issues (`gh issue create`)
2. Generate suitable agents and personas for the task
3. Follow the test → develop → integrate workflow

## Python Environment

- Project uses **UV** for Python environment management
- Check for `uv.lock` or `pyproject.toml` to identify UV-managed projects
- Use `uv` commands for dependency management and execution

## Communication

- This is a Korean-language project
- Use Korean (한국어) for documentation and commit messages unless otherwise specified
- Financial terminology should use standard Korean accounting terms

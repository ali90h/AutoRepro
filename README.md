# AutoRepro

AutoRepro is a developer tools project that transforms issue descriptions into clear reproducibility steps and a shareable framework. Instead of wasting time wondering "How do I reproduce this?", AutoRepro automatically detects repository technologies, generates ready-made devcontainers, and writes prioritized repro plans (repro.md) with explicit assumptions and execution commands.

## Features

The current MVP scope includes three core commands:
- **scan**: Detect languages/frameworks from file pointers
- **init**: devcontainer  
- **plan**: Derive an execution plan from issue description (no execution)

The project targets multilingualism (initially Python/JS/Go) and emphasizes simplicity, transparency, and automated testing. The ultimate goal is to produce tests that automatically fail and open Draft PRs containing them, improving contribution quality and speeding up maintenance on GitHub.

## Installation

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ali90h/AutoRepro.git
   cd AutoRepro
   ```

2. **Create a Python 3.11 virtual environment:**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```

## Usage

### Running AutoRepro

```bash
# Display help and available commands
autorepro --help
```

Currently, AutoRepro is in early development and supports only the help interface. The MVP commands (scan, init, plan) are coming soon.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v
```

### Project Structure

```
autorepro/
├── README.md              # This file
├── LICENSE                # Apache-2.0
├── pyproject.toml         # Package configuration
├── autorepro/             # Main package
│   ├── __init__.py
│   └── cli.py            # Command line interface
├── tests/                 # Test suite
│   └── test_cli.py
└── .github/workflows/     # CI/CD
    └── ci.yml
```

## Requirements

- Python >= 3.11
- pytest (for development)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

This project is in early development. More contribution guidelines will be available as the project evolves.

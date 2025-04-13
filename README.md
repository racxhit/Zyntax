## Zyntax: A Smart NLP-Powered Terminal for System and Development Tasks

Zyntax is a natural language-powered command-line interface that lets you interact with your terminal using plain English. Forget memorizing complex shell commands and flags, just type what you want to do, and Zyntax takes care of the rest.

> ⚠️ **Status: Work In Progress / Under Active Development**  
> Core functionality is implemented, but expect bugs and limitations.

---

## About The Project

Traditional CLIs like **Bash**, **Zsh**, **Cmd**, and **PowerShell** are undeniably powerful, but often intimidating due to:

- Cryptic and complex syntax  
- A vast array of commands and flags  
- Cross-platform inconsistencies (Linux/macOS/Windows)

**Zyntax** simplifies this experience by acting as a smart bridge between human language and the command line. Powered by **Natural Language Processing (NLP)**, it interprets your plain-English instructions and converts them into valid terminal commands—automatically tailored to your OS.

---

## ✨ Features

- **🧠 Natural Language Understanding**  
  Type your command in plain English and Zyntax will figure out the rest.

- **🖥️ Cross-Platform Compatibility**  
  Supports Linux, macOS, and Windows by auto-detecting the platform.

- **📁 Core Command Coverage**  
  Includes operations like:
  - Files/Directories: `ls`/`dir`, `cd`, `pwd`, `mkdir`/`md`, `rm`/`del`, `cp`/`copy`, `mv`/`move`, `cat`/`type`, `touch`
  - System Info: `whoami`, memory and disk stats, process listing
  - Git: `git status`, `git init`, `git commit` with message detection

- **🤖 Fuzzy Matching**  
  Handles minor typos and similar phrasing.

- **💡 Suggestions**  
  Offers "Did you mean...?" when unsure.

- **⌨️ Direct Command Execution**  
  Passes through recognizable shell commands like `ls`, `cd ..` without NLP overhead.

---

## 🛠️ Getting Started

Follow these steps to install and run Zyntax locally:

### 📋 Prerequisites

- Python 3.8+
- `pip` (Python package manager)
- Git

### ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/racxhit/Zyntax-NLP-Terminal.git
cd Zyntax-NLP-Terminal

# Create a virtual environment
python -m venv venv

# Activate the environment
# macOS/Linux:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy English model if not auto-prompted
python -m spacy download en_core_web_sm
```

### ▶️ Running Zyntax

```bash
python main.py
```

You’ll see a `Zyntax>` prompt. Start typing in natural language!

---

## 🧪 Usage Examples

```bash
Zyntax> show me the files in this folder
# Executes: ls -la or dir

Zyntax> make a new directory called MyProject
# Executes: mkdir MyProject

Zyntax> change directory to MyProject
# Executes: cd MyProject

Zyntax> where am i
# Executes: pwd or cd

Zyntax> create an empty file named config.json
# Executes: touch config.json

Zyntax> rename config.json to settings.json
# Executes: mv config.json settings.json

Zyntax> check memory usage
# Displays memory info using psutil

Zyntax> what is the git status?
# Executes: git status

Zyntax> commit these changes with message "feat: initial structure"
# Executes: git commit -m "feat: initial structure"
```

---

## 🧰 Tech Stack

- **Python** — The backbone
- **spaCy** — NLP parsing (POS tagging, entity extraction)
- **RapidFuzz** — Fuzzy command and intent matching
- **psutil** — System-level information gathering

---

## 🐞 Known Issues & Areas for Improvement

- **Entity Extraction**: Occasionally struggles with edge cases or overly simple inputs.
- **Action Matching**: May confuse similar phrases, e.g., "show file X" vs. "show files."
- **Command Coverage**: Basic commands only; advanced flags/options are unsupported for now.


---

## 🔮 Roadmap

- 🔬 Improve NLP entity extraction and command matching
- 🔧 Add advanced utilities (`grep`, `find`, `curl`, etc.)
- 🧱 Extend support for:
  - Shell piping, redirection, and job control
  - Custom aliases and shell history
- 📦 Package as a PyPI module and/or standalone binary (via PyInstaller)
- 🖥️ *Stretch Goal:* Build a simple GUI wrapper for ease of use

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more details.

![License](https://img.shields.io/badge/License-MIT-blue.svg)



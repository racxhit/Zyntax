# Zyntax: Natural Language Terminal Interface

**Zyntax** is an intelligent terminal interface that understands natural language commands. Skip memorizing complex command syntax across different operating systems - just tell Zyntax what you want to do in plain English or Hinglish.

Zyntax bridges the gap between human language and command-line interfaces, making terminal operations accessible to everyone while maintaining the power and efficiency developers love.

🔥 **Cross-platform**: Works consistently on Linux, macOS, and Windows  
🧠 **Smart parsing**: Advanced NLP with spaCy for accurate intent recognition in English and Hinglish  
⚡ **Fast**: Optimized for real-time command processing  
🛠 **Extensible**: Built with modularity and extensibility in mind

---

## ✨ Features

- **Multilingual Support**: Works with English and Hinglish commands
- **Natural Language Processing**: Advanced command understanding using spaCy
- **Cross-Platform Compatibility**: Unified interface across Linux, macOS, and Windows
- **Smart Command Mapping**: Automatically translates to platform-specific commands
- **File Operations**: Create, move, copy, delete files and directories naturally
- **Git Integration**: Manage repositories with conversational commands
- **System Information**: Check memory, disk usage, and system status
- **Error Handling**: Clear feedback and graceful error recovery

## 🚀 Quick Start

### Installation

```bash
pip install zyntax
```

*Note: The required spaCy language model will be downloaded automatically on first run.*

### Usage

```bash
zyntax
```

```
🚀 Zyntax - Natural Language Terminal
💬 Type commands in natural language (English/Hinglish). Type 'exit' to quit.

Zyntax> create a new folder called my_project
Zyntax> change directory to my_project
Zyntax> make an empty file named README.md
Zyntax> folder banao docs
Zyntax> what's the git status?
```

## 📖 Command Examples

| Natural Language | Traditional Command |
|------------------|-------------------|
| `list all files` | `ls -la` / `dir` |
| `show current directory` | `pwd` / `cd` |
| `create folder called docs` | `mkdir docs` / `md docs` |
| `folder banao my_project` | `mkdir my_project` |
| `copy file.txt to backup/` | `cp file.txt backup/` / `copy file.txt backup\` |
| `remove old_file.txt` | `rm old_file.txt` / `del old_file.txt` |
| `show memory usage` | System info via psutil |
| `git commit with message "fix bug"` | `git commit -m "fix bug"` |

## 🛠 Supported Operations

- **File Management**: Create, read, copy, move, delete files
- **Directory Navigation**: Change directories, show current path
- **Git Operations**: Status, init, commit with message parsing
- **System Information**: Memory usage, user info, process management
- **Text Operations**: Display file contents, basic text manipulation

## 💻 Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **Linux** | ✅ Full Support | Native command mapping |
| **macOS** | ✅ Full Support | Uses Linux commands with macOS compatibility |
| **Windows** | ✅ Full Support | Automatic CMD/PowerShell translation |

## 📋 Requirements

- **Python**: 3.8 or higher
- **Operating System**: Linux, macOS, or Windows
- **Dependencies**: spaCy, rapidfuzz, psutil
- **Language Model**: en_core_web_sm (downloaded automatically)

## 🔧 Installation Details

### Using pip (Recommended)

```bash
pip install zyntax
```

The spaCy language model will be downloaded automatically on first run. If you prefer to download it manually beforehand:

```bash
python -m spacy download en_core_web_sm
```

### From Source

```bash
git clone https://github.com/racxhit/Zyntax.git
cd Zyntax
pip install -e .
```

## 🎯 Use Cases

- **Beginners**: Learn command-line operations without memorizing syntax
- **Cross-platform developers**: Use consistent commands across different systems
- **Automation**: Natural language scripting and task automation
- **Education**: Teaching terminal concepts with intuitive language
- **Productivity**: Faster command execution with conversational interface

## 🤝 Contributing

We welcome contributions! Please see our [contributing guidelines](https://github.com/racxhit/Zyntax/blob/main/CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/racxhit/Zyntax.git
cd Zyntax
pip install -e ".[dev]"
pytest tests/
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [spaCy](https://spacy.io/) for natural language processing
- Uses [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) for fuzzy string matching
- System operations powered by [psutil](https://github.com/giampaolo/psutil)

## 🔗 Links

- **Documentation**: [GitHub Wiki](https://github.com/racxhit/Zyntax/wiki)
- **Bug Reports**: [GitHub Issues](https://github.com/racxhit/Zyntax/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/racxhit/Zyntax/discussions)
- **PyPI Package**: [https://pypi.org/project/zyntax/](https://pypi.org/project/zyntax/)

---

**Made with ❤️ for developers who believe terminals should speak human**



# Quick Start Guide

This is a three-step quick setup guide for using evil-read-arxiv.

## Step 1: Install Dependencies

Run in your terminal:

```bash
pip install -r requirements.txt
```

## Step 2: Configuration

### 2.1 Set Environment Variables

Set the `OBSIDIAN_VAULT_PATH` environment variable to point to your Obsidian Vault path. All scripts will automatically read this variable, so there is no need to manually modify paths in the scripts.

```bash
# Windows PowerShell (permanent, restart terminal after setting)
[System.Environment]::SetEnvironmentVariable("OBSIDIAN_VAULT_PATH", "C:/Users/YourName/Documents/Obsidian Vault", "User")

# macOS/Linux (add to ~/.bashrc or ~/.zshrc)
echo 'export OBSIDIAN_VAULT_PATH="/Users/yourname/Documents/Obsidian Vault"' >> ~/.bashrc
source ~/.bashrc
```

### 2.2 Create Configuration File

```bash
cd evil-read-arxiv
cp config.example.yaml config.yaml
```

Edit `config.yaml` and modify:

```yaml
# Change this path to your Obsidian Vault path
vault_path: "/path/to/your/obsidian/vault"

# Modify keywords according to your research interests
research_domains:
  "YourResearchDomain1":
    keywords:
      - "keyword1"
      - "keyword2"
```

### 2.3 Place the Configuration File in Your Vault

```bash
# macOS/Linux
cp config.yaml "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml"

# Windows PowerShell
Copy-Item config.yaml "$env:OBSIDIAN_VAULT_PATH\99_System\Config\research_interests.yaml"
```

### 2.4 Install Skills to Claude Code

Copy the four skill folders from the evil-read-arxiv directory to your Claude Code skills directory:

```bash
# macOS/Linux
cp -r evil-read-arxiv/start-my-day ~/.claude/skills/
cp -r evil-read-arxiv/paper-analyze ~/.claude/skills/
cp -r evil-read-arxiv/extract-paper-images ~/.claude/skills/
cp -r evil-read-arxiv/paper-search ~/.claude/skills/

# Windows PowerShell
Copy-Item -Recurse evil-read-arxiv\start-my-day $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\paper-analyze $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\extract-paper-images $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\paper-search $env:USERPROFILE\.claude\skills\
```

## Step 3: Create Obsidian Directory Structure

Create the following directories in your Obsidian Vault:

```
YourVault/
├── 10_Daily/
├── 20_Research/
│   └── Papers/
├── 99_System/
│   └── Config/
│       └── research_interests.yaml  # Already copied in Step 2
```

## Getting Started

### 1. Open Claude Code

Open a terminal in your Obsidian Vault directory:

```bash
# Navigate to your Obsidian Vault directory
cd "$OBSIDIAN_VAULT_PATH"

# Launch Claude Code
claude-code
```

### 2. Start Daily Paper Recommendations

Type in Claude Code:

```
start my day
```

### 3. Analyze a Single Paper

Type in Claude Code:

```
paper-analyze 2602.12345
```

## Common arXiv Categories

| Category Code | Name | Description |
|---------------|------|-------------|
| cs.AI | Artificial Intelligence | AI |
| cs.LG | Learning | Machine Learning |
| cs.CL | Computation and Language | Computational Linguistics / NLP |
| cs.CV | Computer Vision | Computer Vision |
| cs.MM | Multimedia | Multimedia |
| cs.MA | Multiagent Systems | Multi-Agent Systems |
| cs.RO | Robotics | Robotics |

## Troubleshooting

### Issue: "Vault path not specified" or "Papers directory not found"

**Solution**:
1. Verify the environment variable is set:
   ```bash
   # Windows PowerShell
   echo $env:OBSIDIAN_VAULT_PATH

   # macOS/Linux
   echo $OBSIDIAN_VAULT_PATH
   ```
2. If empty, go back to Step 2 to set the environment variable
3. Verify the directory structure has been created correctly

### Issue: Paper image extraction failed

**Solution**:
1. Verify PyMuPDF is installed: `pip install PyMuPDF`
2. Check that the arXiv ID format is correct (e.g., 2602.12345)

### Issue: Keyword auto-linking is inaccurate

**Solution**: Edit the `COMMON_WORDS` set in `start-my-day/scripts/link_keywords.py` to add words you don't want to be auto-linked.

## Need Help?

- See [README.md](README.md) for detailed documentation
- Submit an Issue to the GitHub repository

# 🚀 Guide de Setup Complet - AI-Agent

## 📋 Prérequis

Avant de commencer, assurez-vous d'avoir :
- **Python 3.9+** installé
- **Git** configuré avec votre nom/email
- **Compte GitHub** avec accès
- **IDE** (VS Code recommandé)

---

## 🎯 ÉTAPE 1 : Création du Repository GitHub

### 1.1 Créer le repo sur GitHub
```bash
# Via GitHub Web Interface
1. Aller sur https://github.com
2. Cliquer "New Repository"
3. Nom : "AI-Agent"
4. Description : "Système intelligent d'automatisation du développement logiciel"
5. ✅ Private (si code sensible)
6. ✅ Add README.md
7. ✅ Add .gitignore (Python)
8. ✅ Add LICENSE (MIT recommandé)
```

### 1.2 Configuration des collaborateurs
```bash
# Via Settings > Manage Access
1. Ajouter Lorenzo et Elie comme Admin
2. Protéger les branches main et develop
```

---

## 🛠️ ÉTAPE 2 : Setup Local Initial

### 2.1 Clone et navigation
```bash
# Cloner le repo
git clone https://github.com/VOTRE_USERNAME/AI-Agent.git
cd AI-Agent

# Vérifier la configuration Git
git config --global user.name "Votre Nom"
git config --global user.email "votre.email@example.com"
```

### 2.2 Configuration GitFlow
```bash
# Créer la branche develop
git checkout -b develop
git push origin develop

# Définir develop comme branche par défaut
# (Via GitHub Settings > Branches > Default branch > develop)
```

---

## 📁 ÉTAPE 3 : Structure du Projet

### 3.1 Créer l'arborescence complète
```bash
# Créer tous les dossiers
mkdir -p config models tools nodes graph services utils docs

# Créer tous les fichiers Python
touch main.py requirements.txt .env.example
touch config/__init__.py config/settings.py
touch models/__init__.py models/schemas.py models/state.py
touch tools/__init__.py tools/base_tool.py tools/monday_tool.py tools/github_tool.py tools/claude_code_tool.py
touch nodes/__init__.py nodes/prepare_node.py nodes/implement_node.py nodes/test_node.py nodes/debug_node.py nodes/finalize_node.py nodes/update_node.py
touch graph/__init__.py graph/workflow_graph.py
touch services/__init__.py services/webhook_service.py
touch utils/__init__.py utils/logger.py utils/helpers.py

# Créer la documentation
touch docs/ARCHITECTURE.md docs/API.md docs/DEPLOYMENT.md
touch SETUP_GUIDE.md CHANGELOG.md
```

### 3.2 Créer le .gitignore Python complet
```bash
cat > .gitignore << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
PIPFILE.lock

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
*.log
logs/

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# AI-Agent specific
temp/
workspace/
repos/
.anthropic_cache/
EOF
```

---

## 🐍 ÉTAPE 4 : Configuration Python

### 4.1 Créer l'environnement virtuel
```bash
# Créer et activer venv
python -m venv venv

# Activation selon l'OS
# Linux/Mac :
source venv/bin/activate
# Windows :
# venv\Scripts\activate
```

### 4.2 Créer requirements.txt
```bash
cat > requirements.txt << 'EOF'
# ================================
# CORE FRAMEWORK - FastAPI & Server
# ================================
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# ================================
# LANGGRAPH & LANGCHAIN ECOSYSTEM
# ================================
langgraph==0.2.14
langchain==0.2.16
langchain-core==0.2.38
langchain-community==0.2.16
langchain-openai==0.1.23
langchain-anthropic==0.1.23

# ================================
# INTÉGRATIONS EXTERNES
# ================================
PyGithub==2.1.1
requests==2.31.0
httpx==0.25.2

# ================================
# DATA & SERIALIZATION
# ================================
pydantic>=2.5.0,<2.8.0
pydantic-settings>=2.1.0,<2.3.0
python-dotenv==1.0.0

# ================================
# UTILITAIRES SYSTÈME
# ================================
psutil==5.9.6
structlog==23.2.0
rich==13.7.0
python-dateutil==2.8.2
aiofiles==23.2.1

# ================================
# SÉCURITÉ & VALIDATION
# ================================
cryptography>=41.0.0,<44.0.0

# ================================
# IA
# ================================
anthropic>=0.30.0,<1.0.0

# ================================
# DÉVELOPPEMENT
# ================================
pytest==7.4.3
pytest-asyncio==0.21.1

# ================================
# PRODUCTION
# ================================
gunicorn==21.2.0
environs==10.3.0
GitPython==3.1.40
EOF
```

### 4.3 Installer les dépendances
```bash
pip install -r requirements.txt
```

---

## ⚙️ ÉTAPE 5 : Configuration Environnement

### 5.1 Créer .env.example
```bash
cat > .env.example << 'EOF'
# ================================
# API KEYS
# ================================
ANTHROPIC_API_KEY=your_claude_api_key_here
GITHUB_TOKEN=your_github_token_here
MONDAY_API_KEY=your_monday_api_key_here

# ================================
# WEBHOOK CONFIGURATION
# ================================
WEBHOOK_SECRET=your_webhook_secret_here
ALLOWED_ORIGINS=*

# ================================
# GIT CONFIGURATION
# ================================
DEFAULT_REPO_URL=https://github.com/username/repository.git
DEFAULT_BASE_BRANCH=main

# ================================
# MONDAY.COM CONFIGURATION
# ================================
MONDAY_BOARD_ID=your_board_id_here
MONDAY_TASK_COLUMN_ID=task_description
MONDAY_STATUS_COLUMN_ID=status

# ================================
# APPLICATION CONFIGURATION
# ================================
DEBUG=True
LOG_LEVEL=INFO

# ================================
# TIMEOUT CONFIGURATION
# ================================
TASK_TIMEOUT=1800
TEST_TIMEOUT=300
EOF
```

### 5.2 Créer votre fichier .env personnel
```bash
# Copier le template
cp .env.example .env

# Éditer avec vos vraies clés
# nano .env  # ou votre éditeur préféré
```

---

## 📚 ÉTAPE 6 : Documentation

### 6.1 README.md principal
```bash
cat > README.md << 'EOF'
# 🤖 AI-Agent - Système d'Automatisation IA

## 📖 Description

Système intelligent d'automatisation du développement logiciel intégrant Monday.com, GitHub et Claude AI pour automatiser le cycle complet de développement.

## 🏗️ Architecture

```
Monday.com → Webhook → LangGraph → Claude → GitHub
```

## 🚀 Installation Rapide

```bash
git clone https://github.com/VOTRE_USERNAME/AI-Agent.git
cd AI-Agent
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec vos clés
python main.py
```

## 📋 Prérequis

- Python 3.9+
- Clés API : Claude, GitHub, Monday.com
- Webhook endpoint publique

## 🔧 Configuration

Voir [SETUP_GUIDE.md](SETUP_GUIDE.md) pour la configuration complète.

## 📖 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Déploiement](docs/DEPLOYMENT.md)

## 🤝 Contribution

1. Fork le projet
2. Créer feature branch (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit (`git commit -m 'feat: ajouter nouvelle fonctionnalité'`)
4. Push (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer Pull Request

## 📜 License

MIT License - voir [LICENSE](LICENSE)
EOF
```

---

## 🔄 ÉTAPE 7 : GitFlow Workflow

### 7.1 Premier commit sur develop
```bash
# Ajouter tous les fichiers
git add .
git commit -m "feat: structure initiale du projet AI-Agent

- Configuration GitFlow avec develop/main
- Structure complète des dossiers et modules
- Requirements.txt avec versions stables
- Documentation de base
- Configuration environnement"

# Pousser vers develop
git push origin develop
```

### 7.2 Créer la première feature branch
```bash
# Créer branche pour l'étape 1 (webhook)
git checkout -b feature/webhook-setup

# Faire vos développements...
# git add .
# git commit -m "feat: implémentation webhook Monday.com"
# git push origin feature/webhook-setup

# Créer PR sur GitHub vers develop
```

---

## 🧪 ÉTAPE 8 : Validation

### 8.1 Tests de base
```bash
# Vérifier que Python fonctionne
python -c "import fastapi; print('FastAPI OK')"
python -c "import anthropic; print('Anthropic OK')"
python -c "import langgraph; print('LangGraph OK')"

# Lancer l'application (test rapide)
python -c "
from fastapi import FastAPI
app = FastAPI()
print('Application démarre correctement')
"
```

### 8.2 Vérification Git
```bash
# Vérifier les branches
git branch -a

# Vérifier les remotes
git remote -v

# Statut propre
git status
```

---

## 🎯 ÉTAPES SUIVANTES

1. **Créer les APIs keys** (Claude, GitHub, Monday)
2. **Configurer .env** avec vos vraies clés
3. **Créer feature/webhook-etape1** pour commencer le développement
4. **Configurer Monday.com webhook** pointant vers votre endpoint
5. **Tester le workflow complet**

---

## 🆘 Aide Rapide

```bash
# Routine quotidienne VyPerf
git fetch --all
git checkout develop
git pull origin develop
git checkout feature/votre-branche
git rebase develop
# ... travail ...
git add .
git commit -m "feat: description"
git push origin feature/votre-branche
```

## 📞 Support

- **Issues** : Via GitHub Issues
- **Documentation** : Dossier `docs/`
- **Chat** : Partager PRs dans le chat dédié 
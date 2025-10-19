# 🎯 Guide d'Implémentation - Détection LLM Intelligente

**Date**: 11 octobre 2025  
**Objectif**: Permettre au LLM de détecter automatiquement le langage du projet cloné (Webflow, Python, etc.)

---

## 📋 Étapes à Suivre

### ✅ Étape 1 : Corriger le Module LLM Enhanced Detector (5 min)

**Fichier**: `utils/llm_enhanced_detector.py`

Le fichier a déjà été créé mais a une erreur d'import. Il faut juste vérifier qu'il n'y a plus d'erreurs :

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
python -c "from utils.llm_enhanced_detector import detect_project_with_llm; print('✅ Import OK')"
```

Si erreur, les imports sont déjà corrigés. Passer à l'étape suivante.

---

### ✅ Étape 2 : Intégrer dans `implement_node.py` (15 min)

**Fichier à modifier**: `nodes/implement_node.py`

**Ligne ~407** - Remplacer la fonction `_analyze_project_structure()` :

```python
async def _analyze_project_structure(claude_tool: ClaudeCodeTool) -> Dict[str, Any]:
    """
    Analyse la structure du projet avec enrichissement LLM.
    
    Combine détection automatique + analyse LLM pour cas complexes.
    """
    try:
        # 1. Lister TOUS les fichiers
        ls_result = await claude_tool._arun(
            action="execute_command", 
            command="find . -type f -not -path './.git/*' -not -path './venv/*' -not -path './node_modules/*' | head -50"
        )
        
        structure_info = "Structure du projet:\n"
        files_found = []
        
        if ls_result["success"]:
            structure_info += ls_result["stdout"]
            files_found = ls_result["stdout"].strip().split('\n') if ls_result["stdout"].strip() else []
        
        # 2. Lire README si disponible
        readme_content = None
        try:
            readme_result = await claude_tool._arun(action="read_file", file_path="README.md", required=False)
            if readme_result["success"]:
                readme_content = readme_result.get("content", "")[:2000]
        except:
            pass
        
        # 3. Lire package.json si disponible
        package_json_content = None
        try:
            pkg_result = await claude_tool._arun(action="read_file", file_path="package.json", required=False)
            if pkg_result["success"]:
                package_json_content = pkg_result.get("content", "")[:1000]
        except:
            pass
        
        # 4. Lire requirements.txt si disponible
        requirements_content = None
        try:
            req_result = await claude_tool._arun(action="read_file", file_path="requirements.txt", required=False)
            if req_result["success"]:
                requirements_content = req_result.get("content", "")[:1000]
        except:
            pass
        
        # 5. ✨ NOUVEAU : Détection enrichie avec LLM
        from utils.llm_enhanced_detector import detect_project_with_llm
        
        logger.info("🤖 Analyse du projet avec enrichissement LLM...")
        
        enhanced_info = await detect_project_with_llm(
            files=files_found,
            readme_content=readme_content,
            package_json_content=package_json_content,
            requirements_txt_content=requirements_content,
            use_llm=True  # Activer l'analyse LLM
        )
        
        # 6. Logger les résultats
        logger.info(f"📊 Langage principal: {enhanced_info.primary_language.name} (confiance: {enhanced_info.confidence:.2f})")
        logger.info(f"📊 Type de projet: {enhanced_info.project_type}")
        logger.info(f"📊 Framework: {enhanced_info.framework or 'Aucun'}")
        logger.info(f"📊 Stack technique: {', '.join(enhanced_info.tech_stack)}")
        logger.info(f"📊 Architecture: {enhanced_info.architecture}")
        
        if enhanced_info.secondary_languages:
            logger.info(f"📊 Langages secondaires: {', '.join(enhanced_info.secondary_languages)}")
        
        # 7. Construire le retour avec informations enrichies
        return {
            "language_info": enhanced_info.primary_language,
            "enhanced_info": enhanced_info,  # ✨ NOUVEAU
            "project_type": enhanced_info.primary_language.type_id,
            "structure_text": structure_info,
            "files": files_found,
            "main_language": enhanced_info.primary_language.name,
            "confidence": enhanced_info.confidence,
            "extensions": enhanced_info.primary_language.primary_extensions,
            "build_files": enhanced_info.primary_language.build_files,
            "conventions": enhanced_info.primary_language.conventions,
            # Nouvelles informations enrichies
            "detected_framework": enhanced_info.framework,
            "detected_project_type": enhanced_info.project_type,
            "tech_stack": enhanced_info.tech_stack,
            "architecture": enhanced_info.architecture,
            "llm_recommendations": enhanced_info.recommendations
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'analyse du projet: {e}", exc_info=True)
        # Fallback sur détection de base
        from utils.language_detector import detect_language, LanguageInfo
        
        basic_detection = detect_language(files_found if 'files_found' in locals() else [])
        
        return {
            "language_info": basic_detection,
            "enhanced_info": None,
            "project_type": basic_detection.type_id,
            "structure_text": "Structure du projet non disponible",
            "files": [],
            "main_language": basic_detection.name,
            "confidence": basic_detection.confidence,
            "extensions": basic_detection.primary_extensions,
            "build_files": basic_detection.build_files,
            "conventions": basic_detection.conventions
        }
```

---

### ✅ Étape 3 : Enrichir le Prompt d'Implémentation (10 min)

**Fichier**: `nodes/implement_node.py`  
**Ligne ~506** - Dans `_create_implementation_prompt()` :

Ajouter après la génération des instructions de langage :

```python
# ✨ NOUVEAU : Ajouter contexte enrichi si disponible
if hasattr(project_analysis.get('enhanced_info'), 'description'):
    enhanced = project_analysis['enhanced_info']
    prompt += f"""

## 🤖 ANALYSE ENRICHIE DU PROJET

**Type de projet détecté**: {enhanced.project_type}
**Framework**: {enhanced.framework or 'Aucun framework spécifique détecté'}
**Architecture**: {enhanced.architecture}
**Stack technique complète**: {', '.join(enhanced.tech_stack)}

**Description du projet**:
{enhanced.description}

**Recommandations du LLM pour l'implémentation**:
"""
    for i, rec in enumerate(enhanced.recommendations, 1):
        prompt += f"\n{i}. {rec}"
    
    if enhanced.secondary_languages:
        prompt += f"""

**⚠️ ATTENTION - Langages secondaires détectés**: {', '.join(enhanced.secondary_languages)}
Assure-toi que ton implémentation est compatible avec ces langages si nécessaire.
"""
```

---

### ✅ Étape 4 : Tester le Système (10 min)

#### Test 1 : Projet Python Simple

```bash
# Créer un projet test
mkdir -p /tmp/test-python-project
cd /tmp/test-python-project
echo "flask==2.0.0" > requirements.txt
echo "# My Flask App" > README.md
mkdir -p src
echo "from flask import Flask" > src/app.py

# Tester la détection
cd /Users/rehareharanaivo/Desktop/AI-Agent
python -c "
import asyncio
from utils.llm_enhanced_detector import detect_project_with_llm

async def test():
    files = ['requirements.txt', 'README.md', 'src/app.py']
    result = await detect_project_with_llm(
        files=files,
        readme_content='# My Flask App',
        requirements_txt_content='flask==2.0.0',
        use_llm=True
    )
    print(f'✅ Langage: {result.primary_language.name}')
    print(f'✅ Framework: {result.framework}')
    print(f'✅ Type: {result.project_type}')
    print(f'✅ Description: {result.description}')

asyncio.run(test())
"
```

#### Test 2 : Projet Webflow/HTML

```bash
# Tester avec projet Webflow
python -c "
import asyncio
from utils.llm_enhanced_detector import detect_project_with_llm

async def test():
    files = [
        'index.html',
        'css/style.css', 
        'js/webflow.js',
        'images/logo.png'
    ]
    result = await detect_project_with_llm(
        files=files,
        readme_content='# My Webflow Site',
        use_llm=True
    )
    print(f'✅ Langage: {result.primary_language.name}')
    print(f'✅ Framework: {result.framework}')
    print(f'✅ Type: {result.project_type}')
    print(f'✅ Stack: {result.tech_stack}')

asyncio.run(test())
"
```

---

### ✅ Étape 5 : Activer dans le Workflow Complet (5 min)

**Fichier**: `nodes/implement_node.py`  
**Ligne ~141** - Dans `implement_task()` :

Ajouter après la récupération de `project_analysis` :

```python
# Logger les informations enrichies
if "enhanced_info" in project_analysis and project_analysis["enhanced_info"]:
    enhanced = project_analysis["enhanced_info"]
    logger.info("=" * 60)
    logger.info("🤖 ANALYSE LLM DU PROJET")
    logger.info("=" * 60)
    logger.info(f"Type: {enhanced.project_type}")
    logger.info(f"Framework: {enhanced.framework or 'Aucun'}")
    logger.info(f"Architecture: {enhanced.architecture}")
    logger.info(f"Stack: {', '.join(enhanced.tech_stack)}")
    logger.info(f"Description: {enhanced.description[:100]}...")
    logger.info("=" * 60)
```

---

## 🎯 Résultat Attendu

### Avant (Détection de base uniquement)
```
📊 Langage détecté: Python (confiance: 0.90)
📊 Extensions: .py
📊 Structure: structured
```

### Après (Avec enrichissement LLM)
```
🤖 Analyse du projet avec enrichissement LLM...
📊 Langage principal: Python (confiance: 0.95)
📊 Type de projet: web-app
📊 Framework: Flask
📊 Stack technique: Python, Flask, SQLAlchemy, PostgreSQL
📊 Architecture: monolithic
📊 Description: Application web Flask avec API REST et base de données PostgreSQL

🤖 ANALYSE LLM DU PROJET
============================================================
Type: web-app
Framework: Flask
Architecture: monolithic
Stack: Python, Flask, SQLAlchemy, PostgreSQL
Description: Application web Flask avec API REST et base de données...
============================================================
```

---

## 🔄 Cas d'Usage Spécifiques

### Cas 1 : Projet Webflow

**Fichiers détectés** :
```
index.html
css/webflow.css
js/webflow.js
```

**Résultat attendu** :
```
📊 Langage principal: HTML (confiance: 0.85)
📊 Type de projet: web-app
📊 Framework: Webflow
📊 Stack: HTML, CSS, JavaScript, Webflow
📊 Architecture: jamstack
```

### Cas 2 : Projet Python/Django

**Fichiers détectés** :
```
manage.py
requirements.txt (avec Django)
myapp/models.py
```

**Résultat attendu** :
```
📊 Langage principal: Python (confiance: 0.95)
📊 Type de projet: web-app
📊 Framework: Django
📊 Stack: Python, Django, PostgreSQL
📊 Architecture: monolithic
```

### Cas 3 : Projet React/TypeScript

**Fichiers détectés** :
```
package.json (avec react, typescript)
tsconfig.json
src/App.tsx
```

**Résultat attendu** :
```
📊 Langage principal: TypeScript (confiance: 0.90)
📊 Type de projet: web-app
📊 Framework: React
📊 Stack: TypeScript, React, Node.js
📊 Architecture: jamstack
```

---

## ⚙️ Configuration Optionnelle

### Désactiver le LLM (Mode Fallback)

Si vous voulez désactiver l'analyse LLM et revenir à la détection de base :

Dans `implement_node.py`, ligne de l'appel :

```python
enhanced_info = await detect_project_with_llm(
    files=files_found,
    readme_content=readme_content,
    package_json_content=package_json_content,
    requirements_txt_content=requirements_content,
    use_llm=False  # ⬅️ Désactiver ici
)
```

### Changer le Modèle LLM

Dans `utils/llm_enhanced_detector.py`, ligne ~61 :

```python
def __init__(self, use_llm: bool = True, llm_model: str = "gpt-4o-mini"):  # ⬅️ Changer ici
```

Options :
- `"gpt-4o-mini"` (rapide, moins cher)
- `"gpt-4o"` (plus précis, plus cher)
- `"claude-3-5-sonnet-20241022"` (Anthropic)

---

## 🐛 Dépannage

### Erreur : "Impossible de résoudre l'importation"

**Solution** : Les imports ont été corrigés. Relancer :
```bash
python -c "from utils.llm_enhanced_detector import detect_project_with_llm; print('OK')"
```

### Erreur : "LLM API Key manquante"

**Solution** : Vérifier `.env` :
```bash
OPENAI_API_KEY=sk-...
# ou
ANTHROPIC_API_KEY=sk-ant-...
```

### Le LLM ne se lance pas

**Solution** : Le système utilise automatiquement le fallback (détection de base sans LLM)

---

## 📊 Temps Estimé Total

| Étape | Temps |
|-------|-------|
| 1. Vérifier module LLM | 5 min |
| 2. Intégrer dans implement_node | 15 min |
| 3. Enrichir le prompt | 10 min |
| 4. Tester le système | 10 min |
| 5. Activer dans workflow | 5 min |
| **TOTAL** | **45 min** |

---

## ✅ Checklist Finale

- [ ] Module `llm_enhanced_detector.py` sans erreur d'import
- [ ] Fonction `_analyze_project_structure()` modifiée
- [ ] Fonction `_create_implementation_prompt()` enrichie
- [ ] Tests avec projet Python réussis
- [ ] Tests avec projet Webflow/HTML réussis
- [ ] Logs enrichis visibles dans la console
- [ ] Workflow complet testé avec un vrai projet

---

## 🎯 Prochaines Étapes (Optionnel)

1. **Ajouter plus de contexte** : Lire plus de fichiers de config (tsconfig.json, etc.)
2. **Améliorer le prompt LLM** : Affiner les instructions pour de meilleurs résultats
3. **Ajouter un cache** : Éviter de re-analyser le même projet
4. **Metrics** : Tracker la précision de la détection LLM

---

*Guide créé le 11 octobre 2025*  
*Temps estimé : 45 minutes*

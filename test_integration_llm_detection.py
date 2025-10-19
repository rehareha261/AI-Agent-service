# -*- coding: utf-8 -*-
"""
Test d'intégration end-to-end pour la détection LLM.
Simule le workflow complet d'analyse de projet.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.claude_code_tool import ClaudeCodeTool
from nodes.implement_node import _analyze_project_structure


async def create_test_project(project_type: str) -> str:
    """Crée un projet de test dans un répertoire temporaire."""
    
    temp_dir = tempfile.mkdtemp(prefix=f"test_{project_type}_")
    
    if project_type == "flask":
        # Créer un projet Flask simple
        Path(temp_dir, "src").mkdir(exist_ok=True)
        Path(temp_dir, "templates").mkdir(exist_ok=True)
        
        # requirements.txt
        with open(Path(temp_dir, "requirements.txt"), "w") as f:
            f.write("flask==2.0.0\nsqlalchemy==1.4.0\n")
        
        # README.md
        with open(Path(temp_dir, "README.md"), "w") as f:
            f.write("# Flask Test App\n\nSimple Flask application for testing.\n")
        
        # src/app.py
        with open(Path(temp_dir, "src", "app.py"), "w") as f:
            f.write("""from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello World'
""")
    
    elif project_type == "webflow":
        # Créer un projet Webflow simple
        Path(temp_dir, "css").mkdir(exist_ok=True)
        Path(temp_dir, "js").mkdir(exist_ok=True)
        
        # index.html
        with open(Path(temp_dir, "index.html"), "w") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="css/webflow.css">
</head>
<body>
    <h1>Webflow Site</h1>
    <script src="js/webflow.js"></script>
</body>
</html>
""")
        
        # README.md
        with open(Path(temp_dir, "README.md"), "w") as f:
            f.write("# Webflow Site\n\nResponsive website built with Webflow.\n")
        
        # css/webflow.css
        with open(Path(temp_dir, "css", "webflow.css"), "w") as f:
            f.write("body { font-family: Arial; }")
        
        # js/webflow.js
        with open(Path(temp_dir, "js", "webflow.js"), "w") as f:
            f.write("// Webflow interactions")
    
    return temp_dir


async def test_integration_flask():
    """Test d'intégration avec projet Flask."""
    print("\n" + "=" * 70)
    print("TEST INTÉGRATION 1 : Analyse complète d'un projet Flask")
    print("=" * 70)
    
    temp_dir = None
    try:
        # 1. Créer un projet test
        temp_dir = await create_test_project("flask")
        print(f"✅ Projet test créé: {temp_dir}")
        
        # 2. Créer un ClaudeCodeTool pointant sur ce répertoire
        claude_tool = ClaudeCodeTool()
        
        # Changer le répertoire de travail
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        # 3. Appeler _analyze_project_structure
        print("🔍 Analyse du projet avec détection LLM...")
        analysis = await _analyze_project_structure(claude_tool)
        
        # 4. Vérifier les résultats
        print("\n📊 RÉSULTATS DE L'ANALYSE:")
        print(f"  Langage principal: {analysis.get('main_language')}")
        print(f"  Type de projet: {analysis.get('project_type')}")
        print(f"  Confiance: {analysis.get('confidence', 0):.2f}")
        
        if "enhanced_info" in analysis and analysis["enhanced_info"]:
            enhanced = analysis["enhanced_info"]
            print(f"  🤖 Framework détecté: {enhanced.framework}")
            print(f"  🤖 Architecture: {enhanced.architecture}")
            print(f"  🤖 Stack: {', '.join(enhanced.tech_stack)}")
            print(f"  🤖 Type détaillé: {enhanced.project_type}")
            print(f"  🤖 Description: {enhanced.description[:80]}...")
        
        # 5. Vérifications
        assert analysis.get("main_language") == "Python", f"Langage incorrect: {analysis.get('main_language')}"
        assert "enhanced_info" in analysis, "enhanced_info manquant"
        
        enhanced = analysis["enhanced_info"]
        if enhanced:
            assert enhanced.framework and "flask" in enhanced.framework.lower(), f"Framework incorrect: {enhanced.framework}"
            assert enhanced.project_type == "web-app", f"Type incorrect: {enhanced.project_type}"
        
        print("\n✅ TEST INTÉGRATION 1 RÉUSSI")
        
        # Revenir au répertoire original
        os.chdir(original_cwd)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST INTÉGRATION 1 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        
        # Revenir au répertoire original
        if 'original_cwd' in locals():
            os.chdir(original_cwd)
        
        return False
        
    finally:
        # Nettoyer
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"🧹 Projet test nettoyé: {temp_dir}")


async def test_integration_webflow():
    """Test d'intégration avec projet Webflow."""
    print("\n" + "=" * 70)
    print("TEST INTÉGRATION 2 : Analyse complète d'un projet Webflow")
    print("=" * 70)
    
    temp_dir = None
    try:
        # 1. Créer un projet test
        temp_dir = await create_test_project("webflow")
        print(f"✅ Projet test créé: {temp_dir}")
        
        # 2. Créer un ClaudeCodeTool pointant sur ce répertoire
        claude_tool = ClaudeCodeTool()
        
        # Changer le répertoire de travail
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        # 3. Appeler _analyze_project_structure
        print("🔍 Analyse du projet avec détection LLM...")
        analysis = await _analyze_project_structure(claude_tool)
        
        # 4. Vérifier les résultats
        print("\n📊 RÉSULTATS DE L'ANALYSE:")
        print(f"  Langage principal: {analysis.get('main_language')}")
        print(f"  Type de projet: {analysis.get('project_type')}")
        print(f"  Confiance: {analysis.get('confidence', 0):.2f}")
        
        if "enhanced_info" in analysis and analysis["enhanced_info"]:
            enhanced = analysis["enhanced_info"]
            print(f"  🤖 Framework détecté: {enhanced.framework}")
            print(f"  🤖 Architecture: {enhanced.architecture}")
            print(f"  🤖 Stack: {', '.join(enhanced.tech_stack)}")
            print(f"  🤖 Type détaillé: {enhanced.project_type}")
            print(f"  🤖 Description: {enhanced.description[:80]}...")
        
        # 5. Vérifications
        assert analysis.get("main_language") in ["HTML", "JavaScript"], f"Langage incorrect: {analysis.get('main_language')}"
        assert "enhanced_info" in analysis, "enhanced_info manquant"
        
        enhanced = analysis["enhanced_info"]
        if enhanced:
            # Vérifier que Webflow est mentionné quelque part
            webflow_detected = (
                (enhanced.framework and "webflow" in enhanced.framework.lower()) or
                any("webflow" in tech.lower() for tech in enhanced.tech_stack) or
                "webflow" in enhanced.description.lower()
            )
            assert webflow_detected, "Webflow non détecté dans l'analyse"
        
        print("\n✅ TEST INTÉGRATION 2 RÉUSSI")
        
        # Revenir au répertoire original
        os.chdir(original_cwd)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST INTÉGRATION 2 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        
        # Revenir au répertoire original
        if 'original_cwd' in locals():
            os.chdir(original_cwd)
        
        return False
        
    finally:
        # Nettoyer
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"🧹 Projet test nettoyé: {temp_dir}")


async def main():
    """Exécute tous les tests d'intégration."""
    print("\n" + "=" * 70)
    print("🧪 TESTS D'INTÉGRATION END-TO-END")
    print("=" * 70)
    
    results = []
    
    # Test 1 : Flask
    results.append(await test_integration_flask())
    
    # Test 2 : Webflow
    results.append(await test_integration_webflow())
    
    # Résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DES TESTS D'INTÉGRATION")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if passed == total:
        print("\n✅ TOUS LES TESTS D'INTÉGRATION SONT PASSÉS !")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) d'intégration échoué(s)")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


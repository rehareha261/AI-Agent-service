# -*- coding: utf-8 -*-
"""
Tests pour la détection LLM intelligente.
Teste différents types de projets (Python, Webflow, React, etc.)
"""

import asyncio
import sys
from utils.llm_enhanced_detector import detect_project_with_llm

async def test_python_flask():
    """Test 1 : Projet Python/Flask"""
    print("\n" + "=" * 70)
    print("TEST 1 : Projet Python/Flask")
    print("=" * 70)
    
    files = [
        'requirements.txt',
        'README.md',
        'src/app.py',
        'src/models.py',
        'src/routes/api.py',
        'templates/index.html',
        'static/css/style.css'
    ]
    
    readme = """# My Flask Application

This is a web application built with Flask framework.
It includes:
- REST API endpoints
- PostgreSQL database
- User authentication
"""
    
    requirements = """flask==2.0.0
sqlalchemy==1.4.0
psycopg2-binary==2.9.0
flask-login==0.5.0
"""
    
    try:
        result = await detect_project_with_llm(
            files=files,
            readme_content=readme,
            requirements_txt_content=requirements,
            use_llm=True
        )
        
        print(f"✅ Langage principal: {result.primary_language.name}")
        print(f"✅ Type de projet: {result.project_type}")
        print(f"✅ Framework: {result.framework}")
        print(f"✅ Architecture: {result.architecture}")
        print(f"✅ Stack technique: {', '.join(result.tech_stack)}")
        print(f"✅ Confiance: {result.confidence:.2f}")
        print(f"✅ Description: {result.description[:100]}...")
        
        # Vérifications
        assert result.primary_language.name == "Python", f"Attendu: Python, Obtenu: {result.primary_language.name}"
        assert "flask" in result.framework.lower() if result.framework else False, "Framework Flask non détecté"
        assert result.project_type == "web-app", f"Type incorrect: {result.project_type}"
        
        print("\n✅ Test 1 RÉUSSI")
        return True
        
    except Exception as e:
        print(f"\n❌ Test 1 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_webflow_site():
    """Test 2 : Site Webflow/HTML"""
    print("\n" + "=" * 70)
    print("TEST 2 : Site Webflow/HTML")
    print("=" * 70)
    
    files = [
        'index.html',
        'about.html',
        'contact.html',
        'css/webflow.css',
        'css/normalize.css',
        'css/style.css',
        'js/webflow.js',
        'js/jquery.min.js',
        'images/logo.png',
        'images/hero-bg.jpg'
    ]
    
    readme = """# My Webflow Site

This is a responsive website built with Webflow.
Features:
- Responsive design
- Custom animations
- Contact form
"""
    
    try:
        result = await detect_project_with_llm(
            files=files,
            readme_content=readme,
            use_llm=True
        )
        
        print(f"✅ Langage principal: {result.primary_language.name}")
        print(f"✅ Type de projet: {result.project_type}")
        print(f"✅ Framework: {result.framework}")
        print(f"✅ Architecture: {result.architecture}")
        print(f"✅ Stack technique: {', '.join(result.tech_stack)}")
        print(f"✅ Confiance: {result.confidence:.2f}")
        print(f"✅ Description: {result.description[:100]}...")
        
        # Vérifications
        # Note: Peut détecter JavaScript (à cause de webflow.js) ou HTML, les deux sont valides
        assert result.primary_language.name in ["HTML", "JavaScript"], f"Attendu: HTML ou JavaScript, Obtenu: {result.primary_language.name}"
        assert result.project_type == "web-app", f"Type incorrect: {result.project_type}"
        # L'important est que Webflow soit détecté comme framework
        assert result.framework and "webflow" in result.framework.lower(), f"Framework Webflow non détecté: {result.framework}"
        
        print("\n✅ Test 2 RÉUSSI")
        return True
        
    except Exception as e:
        print(f"\n❌ Test 2 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_react_typescript():
    """Test 3 : Projet React/TypeScript"""
    print("\n" + "=" * 70)
    print("TEST 3 : Projet React/TypeScript")
    print("=" * 70)
    
    files = [
        'package.json',
        'tsconfig.json',
        'src/App.tsx',
        'src/index.tsx',
        'src/components/Header.tsx',
        'src/components/Footer.tsx',
        'src/hooks/useAuth.ts',
        'src/utils/api.ts',
        'public/index.html',
        'README.md'
    ]
    
    readme = """# React TypeScript App

Modern React application built with TypeScript.
Features:
- TypeScript for type safety
- React hooks
- Component-based architecture
"""
    
    package_json = """{
  "name": "my-react-app",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "typescript": "^4.9.0"
  },
  "devDependencies": {
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0"
  }
}"""
    
    try:
        result = await detect_project_with_llm(
            files=files,
            readme_content=readme,
            package_json_content=package_json,
            use_llm=True
        )
        
        print(f"✅ Langage principal: {result.primary_language.name}")
        print(f"✅ Type de projet: {result.project_type}")
        print(f"✅ Framework: {result.framework}")
        print(f"✅ Architecture: {result.architecture}")
        print(f"✅ Stack technique: {', '.join(result.tech_stack)}")
        print(f"✅ Confiance: {result.confidence:.2f}")
        print(f"✅ Description: {result.description[:100]}...")
        
        # Vérifications
        assert result.primary_language.name == "TypeScript", f"Attendu: TypeScript, Obtenu: {result.primary_language.name}"
        assert result.project_type == "web-app", f"Type incorrect: {result.project_type}"
        
        print("\n✅ Test 3 RÉUSSI")
        return True
        
    except Exception as e:
        print(f"\n❌ Test 3 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_without_llm():
    """Test 4 : Détection de base sans LLM (fallback)"""
    print("\n" + "=" * 70)
    print("TEST 4 : Détection de base sans LLM (fallback)")
    print("=" * 70)
    
    files = [
        'setup.py',
        'mylib/__init__.py',
        'mylib/core.py',
        'tests/test_core.py'
    ]
    
    try:
        result = await detect_project_with_llm(
            files=files,
            use_llm=False  # Désactiver le LLM
        )
        
        print(f"✅ Langage principal: {result.primary_language.name}")
        print(f"✅ Type de projet: {result.project_type}")
        print(f"✅ Framework: {result.framework}")
        print(f"✅ Confiance: {result.confidence:.2f}")
        
        # Vérifications
        assert result.primary_language.name == "Python", f"Attendu: Python, Obtenu: {result.primary_language.name}"
        
        print("\n✅ Test 4 RÉUSSI (mode fallback)")
        return True
        
    except Exception as e:
        print(f"\n❌ Test 4 ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Exécute tous les tests"""
    print("\n" + "=" * 70)
    print("🧪 TESTS DE DÉTECTION LLM INTELLIGENTE")
    print("=" * 70)
    
    results = []
    
    # Test 1 : Python/Flask
    results.append(await test_python_flask())
    
    # Test 2 : Webflow/HTML
    results.append(await test_webflow_site())
    
    # Test 3 : React/TypeScript
    results.append(await test_react_typescript())
    
    # Test 4 : Fallback sans LLM
    results.append(await test_without_llm())
    
    # Résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if passed == total:
        print("\n✅ TOUS LES TESTS SONT PASSÉS !")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) échoué(s)")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


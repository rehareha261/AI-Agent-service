# -*- coding: utf-8 -*-
"""Test d'intégration du système de tests universel."""

import asyncio
import tempfile
import os
from pathlib import Path
from utils.intelligent_test_detector import IntelligentTestDetector
from services.test_generator import TestGeneratorService


async def test_java_project():
    """Test complet sur un projet Java."""
    print("\n" + "="*70)
    print("🧪 TEST 1: PROJET JAVA")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📁 Création projet Java dans: {tmpdir}")
        
        # Créer structure Maven
        pom_path = Path(tmpdir) / "pom.xml"
        pom_path.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>test-app</artifactId>
    <version>1.0</version>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.9.0</version>
        </dependency>
    </dependencies>
</project>""")
        
        # Créer fichier Java
        src_dir = Path(tmpdir) / "src" / "main" / "java" / "com" / "test"
        src_dir.mkdir(parents=True)
        calculator_file = src_dir / "Calculator.java"
        calculator_file.write_text("""package com.test;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    
    public int subtract(int a, int b) {
        return a - b;
    }
}
""")
        
        # Détecter framework
        print("🔍 Détection du framework...")
        detector = IntelligentTestDetector()
        framework_info = await detector.detect_test_framework(tmpdir)
        
        print(f"✅ Framework détecté: {framework_info.framework}")
        print(f"   Langage: {framework_info.language}")
        print(f"   Pattern: {framework_info.test_file_pattern}")
        print(f"   Répertoire: {framework_info.test_directory}")
        print(f"   Commande: {framework_info.test_command}")
        print(f"   Confiance: {framework_info.confidence * 100:.1f}%")
        
        # Vérifications
        assert framework_info.language == "java", "Le langage doit être Java"
        assert framework_info.framework in ["junit5", "junit4"], "Framework doit être JUnit"
        assert "Test.java" in framework_info.test_file_pattern, "Pattern doit contenir Test.java"
        assert "test" in framework_info.test_command.lower(), "Commande doit contenir 'test'"
        
        # Générer template
        print("📝 Génération du template de test...")
        template = detector.get_test_generation_template(framework_info, "Calculator.java")
        
        assert "import org.junit.jupiter" in template or "import org.junit.Test" in template
        assert "CalculatorTest" in template
        assert "@Test" in template
        
        print("✅ Test Java: RÉUSSI\n")
        return True


async def test_python_project():
    """Test complet sur un projet Python."""
    print("\n" + "="*70)
    print("🐍 TEST 2: PROJET PYTHON")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📁 Création projet Python dans: {tmpdir}")
        
        # Créer requirements.txt
        req_path = Path(tmpdir) / "requirements.txt"
        req_path.write_text("pytest>=7.0.0\nrequests>=2.28.0\n")
        
        # Créer module Python
        math_file = Path(tmpdir) / "math_utils.py"
        math_file.write_text("""
def add(a, b):
    \"\"\"Additionne deux nombres.\"\"\"
    return a + b

def multiply(a, b):
    \"\"\"Multiplie deux nombres.\"\"\"
    return a * b

class Calculator:
    def __init__(self):
        self.result = 0
    
    def calculate(self, operation, a, b):
        if operation == "add":
            return add(a, b)
        elif operation == "multiply":
            return multiply(a, b)
""")
        
        # Détecter framework
        print("🔍 Détection du framework...")
        detector = IntelligentTestDetector()
        framework_info = await detector.detect_test_framework(tmpdir)
        
        print(f"✅ Framework détecté: {framework_info.framework}")
        print(f"   Langage: {framework_info.language}")
        print(f"   Pattern: {framework_info.test_file_pattern}")
        print(f"   Répertoire: {framework_info.test_directory}")
        print(f"   Commande: {framework_info.test_command}")
        print(f"   Confiance: {framework_info.confidence * 100:.1f}%")
        
        # Vérifications
        assert framework_info.language == "python", "Le langage doit être Python"
        assert framework_info.framework in ["pytest", "unittest"], "Framework doit être pytest ou unittest"
        assert "test_" in framework_info.test_file_pattern, "Pattern doit contenir test_"
        
        # Générer template
        print("📝 Génération du template de test...")
        template = detector.get_test_generation_template(framework_info, "math_utils.py")
        
        assert "test_" in template.lower()
        assert "math_utils" in template.lower()
        
        print("✅ Test Python: RÉUSSI\n")
        return True


async def test_javascript_project():
    """Test complet sur un projet JavaScript."""
    print("\n" + "="*70)
    print("📜 TEST 3: PROJET JAVASCRIPT")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📁 Création projet JavaScript dans: {tmpdir}")
        
        # Créer package.json
        pkg_path = Path(tmpdir) / "package.json"
        pkg_path.write_text("""{
  "name": "test-app",
  "version": "1.0.0",
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}""")
        
        # Créer fichier JS
        utils_file = Path(tmpdir) / "utils.js"
        utils_file.write_text("""
function sum(a, b) {
  return a + b;
}

function multiply(a, b) {
  return a * b;
}

module.exports = { sum, multiply };
""")
        
        # Détecter framework
        print("🔍 Détection du framework...")
        detector = IntelligentTestDetector()
        framework_info = await detector.detect_test_framework(tmpdir)
        
        print(f"✅ Framework détecté: {framework_info.framework}")
        print(f"   Langage: {framework_info.language}")
        print(f"   Pattern: {framework_info.test_file_pattern}")
        print(f"   Commande: {framework_info.test_command}")
        print(f"   Confiance: {framework_info.confidence * 100:.1f}%")
        
        # Vérifications
        assert framework_info.language == "javascript", "Le langage doit être JavaScript"
        assert framework_info.framework in ["jest", "mocha"], "Framework doit être Jest ou Mocha"
        
        # Générer template
        print("📝 Génération du template de test...")
        template = detector.get_test_generation_template(framework_info, "utils.js")
        
        assert "test" in template.lower() or "describe" in template
        
        print("✅ Test JavaScript: RÉUSSI\n")
        return True


async def test_unknown_project():
    """Test sur un projet inconnu (doit retourner fallback)."""
    print("\n" + "="*70)
    print("❓ TEST 4: PROJET INCONNU (FALLBACK)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📁 Création projet vide dans: {tmpdir}")
        
        # Créer juste un fichier texte
        (Path(tmpdir) / "README.txt").write_text("Empty project")
        
        # Détecter framework
        print("🔍 Détection du framework...")
        detector = IntelligentTestDetector()
        framework_info = await detector.detect_test_framework(tmpdir)
        
        print(f"✅ Framework fallback: {framework_info.framework}")
        print(f"   Langage: {framework_info.language}")
        print(f"   Confiance: {framework_info.confidence * 100:.1f}%")
        
        # Vérifications - doit retourner Python par défaut
        assert framework_info is not None, "Doit retourner un framework par défaut"
        assert framework_info.language == "python", "Fallback doit être Python"
        assert framework_info.confidence <= 0.7, "Confiance doit être basse pour fallback"
        
        print("✅ Test Fallback: RÉUSSI\n")
        return True


async def test_all_language_indicators():
    """Test que tous les langages configurés sont cohérents."""
    print("\n" + "="*70)
    print("🌍 TEST 5: COHÉRENCE DES LANGAGES")
    print("="*70)
    
    detector = IntelligentTestDetector()
    languages = detector.LANGUAGE_INDICATORS
    
    print(f"📊 Langages supportés: {len(languages)}")
    
    for lang_name, lang_info in languages.items():
        print(f"\n  {lang_name.upper()}:")
        
        # Vérifier structure
        assert "extensions" in lang_info, f"{lang_name}: manque 'extensions'"
        assert "build_files" in lang_info, f"{lang_name}: manque 'build_files'"
        assert "test_dirs" in lang_info, f"{lang_name}: manque 'test_dirs'"
        assert "frameworks" in lang_info, f"{lang_name}: manque 'frameworks'"
        
        print(f"    Extensions: {lang_info['extensions']}")
        print(f"    Frameworks: {list(lang_info['frameworks'].keys())}")
        
        # Vérifier chaque framework
        for fw_name, fw_info in lang_info["frameworks"].items():
            assert "indicators" in fw_info, f"{lang_name}/{fw_name}: manque 'indicators'"
            assert "test_pattern" in fw_info, f"{lang_name}/{fw_name}: manque 'test_pattern'"
            assert "command" in fw_info, f"{lang_name}/{fw_name}: manque 'command'"
            assert len(fw_info["indicators"]) > 0, f"{lang_name}/{fw_name}: indicators vide"
    
    print(f"\n✅ Test Cohérence: RÉUSSI")
    print(f"   {len(languages)} langages vérifiés")
    return True


def test_parse_framework_outputs():
    """Test du parsing des sorties de différents frameworks."""
    print("\n" + "="*70)
    print("📊 TEST 6: PARSING DES SORTIES")
    print("="*70)
    
    from nodes.test_node import _parse_framework_output
    
    tests = [
        {
            "name": "JUnit 5",
            "framework": "junit5",
            "output": "Tests run: 15, Failures: 3, Errors: 1, Skipped: 2\nBUILD SUCCESS",
            "expected": {"passed": 12, "failed": 3}
        },
        {
            "name": "pytest",
            "framework": "pytest",
            "output": "===== 8 passed, 2 failed in 5.2s =====",
            "expected": {"passed": 8, "failed": 2}
        },
        {
            "name": "Jest",
            "framework": "jest",
            "output": "Tests: 10 passed, 1 failed, 11 total",
            "expected": {"passed": 10, "failed": 1}
        },
        {
            "name": "Go test",
            "framework": "gotest",
            "output": "PASS\nPASS\nFAIL\nPASS",
            "expected": {"passed": 3, "failed": 1}
        }
    ]
    
    all_passed = True
    for test in tests:
        result = _parse_framework_output(test["output"], test["framework"])
        
        passed_ok = result["passed"] == test["expected"]["passed"]
        failed_ok = result["failed"] == test["expected"]["failed"]
        
        status = "✅" if (passed_ok and failed_ok) else "❌"
        print(f"  {status} {test['name']}: passed={result['passed']}, failed={result['failed']}")
        
        if not (passed_ok and failed_ok):
            print(f"      Attendu: {test['expected']}")
            all_passed = False
    
    assert all_passed, "Tous les parsings doivent réussir"
    print("\n✅ Test Parsing: RÉUSSI\n")
    return True


async def main():
    """Exécute tous les tests."""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "🧪 SUITE DE TESTS COMPLÈTE 🧪" + " "*22 + "║")
    print("╚" + "="*68 + "╝")
    
    results = []
    
    try:
        # Tests asynchrones
        results.append(("Java Project", await test_java_project()))
        results.append(("Python Project", await test_python_project()))
        results.append(("JavaScript Project", await test_javascript_project()))
        results.append(("Unknown Project (Fallback)", await test_unknown_project()))
        results.append(("Language Indicators", await test_all_language_indicators()))
        
        # Tests synchrones
        results.append(("Parse Framework Outputs", test_parse_framework_outputs()))
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Afficher résumé
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    
    for name, result in results:
        status = "✅ RÉUSSI" if result else "❌ ÉCHOUÉ"
        print(f"  {status}: {name}")
    
    print("\n" + "="*70)
    print(f"🎯 TOTAL: {passed}/{total} tests réussis ({passed*100//total}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT RÉUSSIS !")
        print("✅ Le système de tests universel est opérationnel.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)


# -*- coding: utf-8 -*-
"""Test rapide du workflow - version simplifiée."""

import asyncio
import tempfile
from pathlib import Path
from utils.intelligent_test_detector import IntelligentTestDetector
from nodes.test_node import _parse_framework_output


async def test_quick_workflow():
    """Test rapide du workflow complet."""
    print("\n╔════════════════════════════════════════════════╗")
    print("║    🧪 TEST RAPIDE DU WORKFLOW COMPLET 🧪      ║")
    print("╚════════════════════════════════════════════════╝\n")
    
    all_passed = True
    
    # Test 1: Projet Java
    print("1️⃣  TEST: Projet Java")
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "pom.xml").write_text("<project></project>")
        Path(tmpdir, "Main.java").write_text("public class Main {}")
        
        detector = IntelligentTestDetector()
        info = await detector.detect_test_framework(tmpdir)
        
        if info.language == "java" and info.framework in ["junit5", "junit4"]:
            print("   ✅ Java détecté correctement")
        else:
            print(f"   ❌ Erreur: {info.language}/{info.framework}")
            all_passed = False
    
    # Test 2: Projet Python
    print("\n2️⃣  TEST: Projet Python")
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "requirements.txt").write_text("pytest")
        Path(tmpdir, "app.py").write_text("def hello(): pass")
        
        detector = IntelligentTestDetector()
        info = await detector.detect_test_framework(tmpdir)
        
        if info.language == "python":
            print("   ✅ Python détecté correctement")
        else:
            print(f"   ❌ Erreur: {info.language}")
            all_passed = False
    
    # Test 3: Parsing JUnit
    print("\n3️⃣  TEST: Parsing JUnit")
    output = "Tests run: 10, Failures: 2, Errors: 0"
    result = _parse_framework_output(output, "junit5")
    
    if result['passed'] == 8 and result['failed'] == 2:
        print("   ✅ Parsing JUnit correct")
    else:
        print(f"   ❌ Erreur parsing: {result}")
        all_passed = False
    
    # Test 4: Parsing pytest
    print("\n4️⃣  TEST: Parsing pytest")
    output = "===== 5 passed, 1 failed in 2.5s ====="
    result = _parse_framework_output(output, "pytest")
    
    if result['passed'] == 5 and result['failed'] == 1:
        print("   ✅ Parsing pytest correct")
    else:
        print(f"   ❌ Erreur parsing: {result}")
        all_passed = False
    
    # Test 5: Fallback
    print("\n5️⃣  TEST: Fallback sur projet vide")
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = IntelligentTestDetector()
        info = await detector.detect_test_framework(tmpdir)
        
        if info is not None and info.language == "python":
            print("   ✅ Fallback fonctionne")
        else:
            print(f"   ❌ Erreur fallback")
            all_passed = False
    
    # Test 6: Templates
    print("\n6️⃣  TEST: Génération de templates")
    detector = IntelligentTestDetector()
    
    # Template Java
    from utils.intelligent_test_detector import TestFrameworkInfo
    java_info = TestFrameworkInfo(
        language="java", framework="junit5",
        test_file_pattern="*Test.java", test_directory="src/test/java",
        test_command="mvn test", build_command=None, dependencies=[],
        file_extension=".java", confidence=0.9
    )
    template = detector.get_test_generation_template(java_info, "MyClass.java")
    
    if "@Test" in template and "MyClassTest" in template:
        print("   ✅ Template Java généré")
    else:
        print("   ❌ Erreur template Java")
        all_passed = False
    
    # Résumé
    print("\n" + "="*50)
    if all_passed:
        print("✅ TOUS LES TESTS RÉUSSIS (6/6)")
        print("✅ Le workflow est opérationnel !")
        return True
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_quick_workflow())
    exit(0 if success else 1)


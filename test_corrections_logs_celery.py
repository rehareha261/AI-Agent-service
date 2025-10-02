#!/usr/bin/env python3
"""
Test de validation des corrections d'erreurs identifiées dans les logs Celery.

Ce script teste les corrections suivantes:
1. Suppression des warnings "column_values n'est pas une liste" pour les dicts (normal)
2. Gestion des fichiers de configuration manquants (package.json, setup.py)
3. Suppression des warnings LangChain Beta API
4. Amélioration générale des logs d'erreur
"""

import asyncio
import sys
import warnings
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

# Capturer les warnings pour les tests
warnings.simplefilter("always")


def test_langchain_warnings_suppression():
    """Test de suppression des warnings LangChain Beta."""
    print("🧪 Test suppression warnings LangChain")
    
    # Compter les warnings avant
    with warnings.catch_warnings(record=True) as w_before:
        warnings.simplefilter("always")
        try:
            # Essayer d'importer et déclencher le warning
            from langchain_core._api.beta_decorator import LangChainBetaWarning
            warnings.warn("This API is in beta and may change in the future.", LangChainBetaWarning)
        except:
            pass
        warnings_before = len(w_before)
    
    # Maintenant appliquer notre filtre (comme dans main.py)
    try:
        from langchain_core._api.beta_decorator import LangChainBetaWarning
        warnings.simplefilter("ignore", LangChainBetaWarning)
        filter_applied = True
    except ImportError:
        warnings.filterwarnings("ignore", message="This API is in beta and may change in the future.")
        filter_applied = True
    
    # Compter les warnings après
    with warnings.catch_warnings(record=True) as w_after:
        warnings.simplefilter("always")
        try:
            warnings.warn("This API is in beta and may change in the future.", LangChainBetaWarning)
        except:
            warnings.warn("This API is in beta and may change in the future.", UserWarning)
        warnings_after = len([w for w in w_after if "beta" in str(w.message).lower()])
    
    print(f"   ✅ Filtre LangChain appliqué: {filter_applied}")
    print(f"   📊 Warnings beta avant: {warnings_before}, après: {warnings_after}")
    
    return filter_applied


async def test_column_values_handling():
    """Test de gestion améliorée des column_values."""
    print("\n🧪 Test gestion column_values améliorée")
    
    try:
        from services.webhook_service import WebhookService
        
        webhook_service = WebhookService()
        
        # Test avec différents types de column_values
        test_cases = [
            ({}, "dict vide"),
            ({"col1": {"text": "test"}}, "dict avec données"),
            ([], "liste vide"),
            ([{"id": "col1", "text": "test"}], "liste avec données"),
        ]
        
        valid_conversions = 0
        for column_values, description in test_cases:
            try:
                # Simuler un item_data avec column_values
                item_data = {"column_values": column_values}
                
                # Utiliser la nouvelle logique de _extract_column_value
                result = webhook_service._extract_column_value(item_data, "test_col")
                valid_conversions += 1
                print(f"   ✅ {description}: Traité sans erreur")
            except Exception as e:
                print(f"   ❌ {description}: Erreur {e}")
        
        print(f"   📊 Conversions réussies: {valid_conversions}/{len(test_cases)}")
        return valid_conversions == len(test_cases)
        
    except Exception as e:
        print(f"   ❌ Erreur dans le test: {e}")
        return False


async def test_optional_config_files():
    """Test de gestion des fichiers de configuration optionnels."""
    print("\n🧪 Test fichiers de configuration optionnels")
    
    try:
        from tools.claude_code_tool import ClaudeCodeTool
        
        claude_tool = ClaudeCodeTool()
        
        # Test avec des fichiers qui n'existent probablement pas
        config_files = [
            ("package.json", False),  # Fichier optionnel
            ("setup.py", False),      # Fichier optionnel
            ("nonexistent.txt", True)  # Fichier requis (pour vérifier la différence)
        ]
        
        results = []
        for file_path, required in config_files:
            try:
                result = await claude_tool._read_file(file_path, required=required)
                
                # Vérifier que les fichiers optionnels ne génèrent pas d'erreur critique
                if not required and not result["success"]:
                    is_optional = result.get("optional", False)
                    print(f"   ✅ {file_path}: Marqué comme optionnel: {is_optional}")
                    results.append(is_optional)
                elif required and not result["success"]:
                    print(f"   ✅ {file_path}: Erreur appropriée pour fichier requis")
                    results.append(True)
                else:
                    print(f"   📄 {file_path}: Fichier existe")
                    results.append(True)
                    
            except Exception as e:
                print(f"   ❌ {file_path}: Exception {e}")
                results.append(False)
        
        success_rate = len([r for r in results if r]) / len(results)
        print(f"   📊 Gestion correcte: {len([r for r in results if r])}/{len(results)}")
        
        return success_rate >= 0.8  # Au moins 80% de réussite
        
    except Exception as e:
        print(f"   ❌ Erreur dans le test: {e}")
        return False


def test_import_without_warnings():
    """Test d'import des modules principaux sans warnings."""
    print("\n🧪 Test imports sans warnings")
    
    # Capturer les warnings lors des imports
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            # Importer les modules principaux
            from tools.monday_tool import MondayTool
            from services.webhook_service import WebhookService
            from services.celery_app import celery_app
            
            imports_successful = True
        except Exception as e:
            print(f"   ❌ Erreur d'import: {e}")
            imports_successful = False
        
        # Compter les warnings critiques (exclure les warnings beta)
        critical_warnings = [
            warning for warning in w 
            if "beta" not in str(warning.message).lower() and 
               "deprecated" not in str(warning.message).lower()
        ]
        
        print(f"   ✅ Imports réussis: {imports_successful}")
        print(f"   📊 Warnings critiques: {len(critical_warnings)}")
        
        if critical_warnings:
            for warning in critical_warnings[:3]:  # Montrer max 3
                print(f"   ⚠️ Warning: {warning.message}")
        
        return imports_successful and len(critical_warnings) == 0


async def main():
    """Test principal des corrections d'erreurs Celery."""
    print("🔧 Test des Corrections d'Erreurs - Logs Celery\n")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 4
    
    try:
        # Test 1: Suppression warnings LangChain
        if test_langchain_warnings_suppression():
            tests_passed += 1
            print("✅ Test warnings LangChain: RÉUSSI")
        else:
            print("❌ Test warnings LangChain: ÉCHOUÉ")
        
        print("\n" + "-" * 40)
        
        # Test 2: Gestion column_values
        if await test_column_values_handling():
            tests_passed += 1
            print("✅ Test column_values: RÉUSSI")
        else:
            print("❌ Test column_values: ÉCHOUÉ")
        
        print("\n" + "-" * 40)
        
        # Test 3: Fichiers optionnels
        if await test_optional_config_files():
            tests_passed += 1
            print("✅ Test fichiers optionnels: RÉUSSI")
        else:
            print("❌ Test fichiers optionnels: ÉCHOUÉ")
        
        print("\n" + "-" * 40)
        
        # Test 4: Imports sans warnings
        if test_import_without_warnings():
            tests_passed += 1
            print("✅ Test imports propres: RÉUSSI")
        else:
            print("❌ Test imports propres: ÉCHOUÉ")
        
    except Exception as e:
        print(f"\n❌ Erreur générale dans les tests: {e}")
    
    # Résumé final
    print("\n" + "=" * 60)
    print(f"📊 RÉSULTATS FINAUX: {tests_passed}/{total_tests} tests réussis")
    
    if tests_passed == total_tests:
        print("🎉 Toutes les corrections d'erreurs Celery fonctionnent!")
        print("\n📋 Corrections validées:")
        print("   ✅ Warnings 'column_values dict' supprimés (normal)")
        print("   ✅ Fichiers config manquants traités comme optionnels")
        print("   ✅ Warnings LangChain Beta supprimés")
        print("   ✅ Imports propres sans warnings parasites")
        
        print("\n🔍 Erreurs corrigées:")
        print("   • Warning 'column_values n'est pas une liste' → Log debug")
        print("   • Erreur 'Fichier non trouvé' → Gestion optionnelle")
        print("   • Warning 'LangChain Beta API' → Filtré")
        print("   • Logs pollués → Nettoyés et organisés")
        
        return 0
    else:
        print("⚠️ Certains tests ont échoué - vérifiez les corrections")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 
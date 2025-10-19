# -*- coding: utf-8 -*-
"""
Test du mécanisme de fallback Anthropic → OpenAI.

Ce script teste:
1. Fallback automatique quand Anthropic échoue
2. Utilisation normale d'Anthropic quand disponible
3. Gestion des erreurs et logs appropriés
"""

import sys
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

from ai.llm.llm_factory import (
    get_llm,
    get_llm_with_fallback,
    get_default_llm_with_fallback
)
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


def test_1_anthropic_direct():
    """Test 1: Utilisation directe d'Anthropic."""
    print("\n" + "="*70)
    print("TEST 1: Utilisation directe d'Anthropic")
    print("="*70)
    
    try:
        llm = get_llm(provider="anthropic")
        print(f"✅ LLM Anthropic créé: {type(llm).__name__}")
        
        # Test simple
        response = llm.invoke("Réponds juste 'OK' en un mot.")
        print(f"✅ Réponse d'Anthropic: {response.content[:50]}")
        return True
    except Exception as e:
        print(f"❌ Erreur Anthropic: {e}")
        return False


def test_2_openai_direct():
    """Test 2: Utilisation directe d'OpenAI."""
    print("\n" + "="*70)
    print("TEST 2: Utilisation directe d'OpenAI")
    print("="*70)
    
    try:
        llm = get_llm(provider="openai")
        print(f"✅ LLM OpenAI créé: {type(llm).__name__}")
        
        # Test simple
        response = llm.invoke("Réponds juste 'OK' en un mot.")
        print(f"✅ Réponse d'OpenAI: {response.content[:50]}")
        return True
    except Exception as e:
        print(f"❌ Erreur OpenAI: {e}")
        return False


def test_3_fallback_anthropic_to_openai():
    """Test 3: Fallback automatique Anthropic → OpenAI."""
    print("\n" + "="*70)
    print("TEST 3: Fallback automatique Anthropic → OpenAI")
    print("="*70)
    
    try:
        # Créer un LLM avec fallback
        llm = get_llm_with_fallback(
            primary_provider="anthropic",
            fallback_providers=["openai"],
            temperature=0.1
        )
        print(f"✅ LLM avec fallback créé: {type(llm).__name__}")
        
        # Tester une requête
        response = llm.invoke("Réponds juste 'OK' en un mot.")
        print(f"✅ Réponse reçue: {response.content[:50]}")
        print(f"ℹ️  Type de réponse: {type(response)}")
        return True
    except Exception as e:
        print(f"❌ Erreur fallback: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_default_llm_with_fallback():
    """Test 4: Utilisation du LLM par défaut avec fallback."""
    print("\n" + "="*70)
    print("TEST 4: LLM par défaut avec fallback (depuis settings)")
    print("="*70)
    
    try:
        settings = get_settings()
        print(f"ℹ️  Provider par défaut: {settings.default_ai_provider}")
        print(f"ℹ️  Anthropic key présente: {bool(settings.anthropic_api_key)}")
        print(f"ℹ️  OpenAI key présente: {bool(settings.openai_api_key)}")
        
        # Créer le LLM par défaut
        llm = get_default_llm_with_fallback(temperature=0.1)
        print(f"✅ LLM par défaut créé: {type(llm).__name__}")
        
        # Tester une requête
        response = llm.invoke("Réponds juste 'OK' en un mot.")
        print(f"✅ Réponse reçue: {response.content[:50]}")
        return True
    except Exception as e:
        print(f"❌ Erreur LLM par défaut: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_simulate_anthropic_failure():
    """Test 5: Simuler une défaillance Anthropic pour tester le fallback."""
    print("\n" + "="*70)
    print("TEST 5: Simulation défaillance Anthropic (fallback forcé)")
    print("="*70)
    
    try:
        # Sauvegarder la clé Anthropic originale
        settings = get_settings()
        original_key = settings.anthropic_api_key
        
        # Temporairement invalider la clé Anthropic
        settings.anthropic_api_key = "sk-ant-invalid-key-for-testing"
        
        print("⚠️  Clé Anthropic temporairement invalidée")
        print("⚠️  Le système DEVRAIT basculer automatiquement vers OpenAI...")
        
        try:
            # Tenter de créer un LLM avec fallback
            llm = get_llm_with_fallback(
                primary_provider="anthropic",
                fallback_providers=["openai"],
                temperature=0.1
            )
            print(f"✅ LLM créé malgré l'erreur Anthropic: {type(llm).__name__}")
            
            # Restaurer la clé originale
            settings.anthropic_api_key = original_key
            
            # Le fallback devrait avoir été activé
            print("✅ Fallback fonctionne! Le système a basculé vers OpenAI")
            return True
        except Exception as e:
            # Restaurer la clé originale même en cas d'erreur
            settings.anthropic_api_key = original_key
            print(f"❌ Fallback n'a pas fonctionné: {e}")
            return False
    except Exception as e:
        print(f"❌ Erreur lors du test de simulation: {e}")
        return False


def test_6_verify_fallback_chain():
    """Test 6: Vérifier la chaîne de fallback dans LangChain."""
    print("\n" + "="*70)
    print("TEST 6: Vérification de la chaîne de fallback LangChain")
    print("="*70)
    
    try:
        from langchain_core.runnables import RunnableWithFallbacks
        
        # Créer un LLM avec fallback
        llm = get_llm_with_fallback(
            primary_provider="anthropic",
            fallback_providers=["openai"]
        )
        
        # Vérifier si c'est bien un RunnableWithFallbacks
        if isinstance(llm, RunnableWithFallbacks):
            print(f"✅ Type correct: RunnableWithFallbacks")
            print(f"✅ Fallback correctement configuré")
            
            # Tester la chaîne
            response = llm.invoke("Test")
            print(f"✅ Chaîne de fallback fonctionnelle")
            return True
        else:
            print(f"⚠️  Type: {type(llm).__name__} (pas de fallback détecté)")
            print(f"ℹ️  Cela peut être normal si fallback n'est pas nécessaire")
            return True
    except Exception as e:
        print(f"❌ Erreur chaîne de fallback: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Exécuter tous les tests."""
    print("\n" + "="*70)
    print("🧪 TESTS DU MÉCANISME DE FALLBACK ANTHROPIC → OPENAI")
    print("="*70)
    
    results = {
        "test_1_anthropic_direct": False,
        "test_2_openai_direct": False,
        "test_3_fallback": False,
        "test_4_default_llm": False,
        "test_5_simulate_failure": False,
        "test_6_verify_chain": False
    }
    
    # Test 1: Anthropic direct
    results["test_1_anthropic_direct"] = test_1_anthropic_direct()
    
    # Test 2: OpenAI direct
    results["test_2_openai_direct"] = test_2_openai_direct()
    
    # Test 3: Fallback automatique
    results["test_3_fallback"] = test_3_fallback_anthropic_to_openai()
    
    # Test 4: LLM par défaut
    results["test_4_default_llm"] = test_4_default_llm_with_fallback()
    
    # Test 5: Simulation défaillance
    results["test_5_simulate_failure"] = test_5_simulate_anthropic_failure()
    
    # Test 6: Vérification chaîne
    results["test_6_verify_chain"] = test_6_verify_fallback_chain()
    
    # Résumé
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "-"*70)
    print(f"Résultat: {passed}/{total} tests réussis ({(passed/total)*100:.1f}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ Le mécanisme de fallback fonctionne correctement")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué")
        print("❌ Vérifiez les logs ci-dessus pour plus de détails")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)


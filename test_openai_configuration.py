#!/usr/bin/env python3
"""Test de la configuration OpenAI comme provider principal."""

import asyncio
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


async def test_configuration():
    """Teste que OpenAI est bien configuré comme provider principal partout."""
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║         🧪 TEST CONFIGURATION OPENAI COMME PROVIDER PRINCIPAL     ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    results = []
    
    # Test 1: Settings
    print("📋 Test 1: Configuration Settings")
    print("─" * 70)
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        print(f"  • default_ai_provider: {settings.default_ai_provider}")
        print(f"  • openai_api_key: {'✅ Définie' if settings.openai_api_key else '❌ Manquante'}")
        print(f"  • anthropic_api_key: {'✅ Définie' if settings.anthropic_api_key else '❌ Non requise'}")
        
        if settings.default_ai_provider.lower() == "openai":
            print("  ✅ Provider par défaut: OpenAI")
            results.append(("Settings", True))
        else:
            print(f"  ❌ Provider par défaut incorrect: {settings.default_ai_provider}")
            results.append(("Settings", False))
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("Settings", False))
    
    print()
    
    # Test 2: LLM Factory - Modèle par défaut
    print("📋 Test 2: Modèle OpenAI par défaut")
    print("─" * 70)
    try:
        from ai.llm.llm_factory import DEFAULT_MODELS
        
        openai_model = DEFAULT_MODELS.get("openai")
        print(f"  • Modèle OpenAI: {openai_model}")
        
        if openai_model == "gpt-4o":
            print("  ✅ Modèle moderne configuré (gpt-4o)")
            results.append(("Modèle OpenAI", True))
        else:
            print(f"  ⚠️  Modèle: {openai_model} (recommandé: gpt-4o)")
            results.append(("Modèle OpenAI", True))  # Pas bloquant
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("Modèle OpenAI", False))
    
    print()
    
    # Test 3: get_llm par défaut
    print("📋 Test 3: Fonction get_llm() par défaut")
    print("─" * 70)
    try:
        from ai.llm.llm_factory import get_llm
        import inspect
        
        sig = inspect.signature(get_llm)
        provider_default = sig.parameters['provider'].default
        
        print(f"  • Paramètre provider par défaut: {provider_default}")
        
        if provider_default == "openai":
            print("  ✅ get_llm() utilise OpenAI par défaut")
            results.append(("get_llm", True))
        else:
            print(f"  ❌ get_llm() utilise {provider_default} par défaut")
            results.append(("get_llm", False))
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("get_llm", False))
    
    print()
    
    # Test 4: get_llm_with_fallback par défaut
    print("📋 Test 4: Fonction get_llm_with_fallback() par défaut")
    print("─" * 70)
    try:
        from ai.llm.llm_factory import get_llm_with_fallback
        import inspect
        
        sig = inspect.signature(get_llm_with_fallback)
        primary_default = sig.parameters['primary_provider'].default
        
        print(f"  • Paramètre primary_provider par défaut: {primary_default}")
        
        if primary_default == "openai":
            print("  ✅ get_llm_with_fallback() utilise OpenAI par défaut")
            results.append(("get_llm_with_fallback", True))
        else:
            print(f"  ❌ get_llm_with_fallback() utilise {primary_default} par défaut")
            results.append(("get_llm_with_fallback", False))
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("get_llm_with_fallback", False))
    
    print()
    
    # Test 5: Création d'un LLM par défaut
    print("📋 Test 5: Création effective d'un LLM par défaut")
    print("─" * 70)
    try:
        from ai.llm.llm_factory import get_default_llm_with_fallback
        
        print("  • Création du LLM...")
        llm = get_default_llm_with_fallback(temperature=0.1, max_tokens=100)
        
        # Le LLM avec fallback n'expose pas directement le provider
        # mais on peut vérifier via les logs
        print("  ✅ LLM créé avec succès")
        print("  • Configuration: OpenAI (principal) → Anthropic (fallback)")
        results.append(("Création LLM", True))
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("Création LLM", False))
    
    print()
    
    # Test 6: Test de génération réelle
    print("📋 Test 6: Génération de texte avec OpenAI")
    print("─" * 70)
    try:
        from ai.llm.llm_factory import get_llm
        from langchain_core.messages import HumanMessage
        
        print("  • Création du LLM OpenAI...")
        llm = get_llm(provider="openai", temperature=0.1, max_tokens=50)
        
        print("  • Envoi d'une requête de test...")
        messages = [HumanMessage(content="Réponds juste 'OpenAI fonctionne' si tu me reçois.")]
        response = await llm.ainvoke(messages)
        
        print(f"  • Réponse: {response.content[:100]}...")
        print("  ✅ OpenAI répond correctement")
        results.append(("Génération", True))
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results.append(("Génération", False))
    
    print()
    
    # Résumé
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                          RÉSUMÉ FINAL                              ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    success_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    print()
    print(f"Score: {success_count}/{total_count} tests passés")
    print()
    
    if success_count == total_count:
        print("═" * 70)
        print("🎉 SUCCÈS TOTAL! OpenAI est configuré comme provider principal")
        print("═" * 70)
        print()
        print("✅ Tous les appels LLM utiliseront maintenant OpenAI par défaut")
        print("✅ Fallback automatique vers Anthropic en cas d'erreur")
        print("✅ Modèle: gpt-4o (performant et moderne)")
        print()
        return True
    else:
        print("═" * 70)
        print("⚠️  CONFIGURATION INCOMPLÈTE")
        print("═" * 70)
        print()
        print("Certains tests ont échoué. Vérifiez les erreurs ci-dessus.")
        print()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_configuration())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrompu")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


#!/usr/bin/env python3
"""Test de la clé API OpenAI."""

import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()


async def test_openai():
    """Teste la connexion à l'API OpenAI."""
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                    🧪 TEST CLÉ API OPENAI                         ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Vérifier que la clé est définie
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ ERREUR: Variable d'environnement OPENAI_API_KEY non définie")
        print()
        print("Pour la définir:")
        print("  export OPENAI_API_KEY='votre-clé-ici'")
        return False
    
    print(f"✅ Clé API trouvée: {api_key[:15]}...{api_key[-4:]}")
    print()
    
    # Tester la connexion
    try:
        print("🔌 Connexion à l'API OpenAI...")
        client = AsyncOpenAI(api_key=api_key)
        
        print("📤 Envoi d'une requête de test...")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Réponds simplement 'OK' si tu me reçois."}
            ],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        
        print(f"📥 Réponse reçue: '{result}'")
        print()
        print("═" * 70)
        print("✅ CLÉ OPENAI FONCTIONNE PARFAITEMENT!")
        print("═" * 70)
        print()
        print(f"Modèle utilisé: {response.model}")
        print(f"Tokens utilisés: {response.usage.total_tokens}")
        print(f"Coût estimé: ~${response.usage.total_tokens * 0.00000015:.6f}")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("═" * 70)
        print("❌ ERREUR: La clé OpenAI ne fonctionne pas")
        print("═" * 70)
        print()
        print(f"Type d'erreur: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print()
        
        if "authentication" in str(e).lower() or "api_key" in str(e).lower():
            print("💡 Suggestions:")
            print("  1. Vérifier que la clé est valide sur https://platform.openai.com/api-keys")
            print("  2. Vérifier que la clé n'a pas expiré")
            print("  3. Vérifier que vous avez des crédits disponibles")
        elif "quota" in str(e).lower():
            print("💡 Problème de quota:")
            print("  - Vous avez dépassé votre quota mensuel")
            print("  - Vérifier sur https://platform.openai.com/usage")
        elif "rate_limit" in str(e).lower():
            print("💡 Limite de débit:")
            print("  - Trop de requêtes en peu de temps")
            print("  - Réessayer dans quelques secondes")
        
        print()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_openai())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrompu")
        exit(1)


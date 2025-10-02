#!/usr/bin/env python3
"""
Script de test pour vérifier l'extraction d'URL GitHub depuis la description.
"""

from utils.github_parser import (
    extract_github_url_from_description,
    extract_github_info_from_description,
    enrich_task_with_description_info
)

def test_github_extraction():
    """Test des différents formats d'URL GitHub."""
    
    print("🧪 TEST D'EXTRACTION D'URL GITHUB")
    print("=" * 50)
    
    # Cas de test
    test_cases = [
        # Description, URL attendue
        ("Ajouter un module de monitoring pour https://github.com/mycompany/backend-api", 
         "https://github.com/mycompany/backend-api"),
        
        ("Repository: https://github.com/user/repo.git", 
         "https://github.com/user/repo"),
        
        ("Projet sur git@github.com:team/project.git", 
         "https://github.com/team/project"),
        
        ("Voir le code sur github.com/dev/awesome-app", 
         "https://github.com/dev/awesome-app"),
        
        ("[Code source](https://github.com/open/source)", 
         "https://github.com/open/source"),
        
        ("Repo github: https://github.com/company/app-frontend", 
         "https://github.com/company/app-frontend"),
         
        ("Pas d'URL GitHub dans cette description", 
         None),
    ]
    
    print("\n📋 Tests d'extraction basique:")
    for i, (description, expected) in enumerate(test_cases, 1):
        result = extract_github_url_from_description(description)
        status = "✅" if result == expected else "❌"
        print(f"{status} Test {i}: {result}")
        if result != expected:
            print(f"   Attendu: {expected}")
            print(f"   Obtenu:  {result}")
        print(f"   Description: {description}")
        print()

def test_enrichment():
    """Test de l'enrichissement des données de tâche."""
    
    print("\n🔧 TEST D'ENRICHISSEMENT DE TÂCHE")
    print("=" * 50)
    
    # Données de base de la tâche
    base_task = {
        "task_id": "123",
        "title": "Ajouter module monitoring",
        "description": "",
        "repository_url": "",
        "branch_name": "",
        "priority": "medium"
    }
    
    # Description riche
    rich_description = """
    Ajouter un module de monitoring temps réel des runs AI-Agent.
    
    Repository: https://github.com/mycompany/ai-agent
    Branch: feature/realtime-monitoring
    Files: services/monitoring_service.py, admin/monitoring_endpoints.py
    
    URGENT: Nécessaire pour la démo client demain
    Issue: #456
    @breaking-change @monitoring
    """
    
    print("📝 Description d'entrée:")
    print(rich_description)
    print()
    
    # Test d'enrichissement
    enriched = enrich_task_with_description_info(base_task, rich_description)
    
    print("📊 Résultat de l'enrichissement:")
    for key, value in enriched.items():
        if key in base_task and base_task[key] != value:
            print(f"✨ {key}: '{base_task[key]}' → '{value}'")
        elif key not in base_task and value:
            print(f"🆕 {key}: {value}")
        else:
            print(f"   {key}: {value}")
    
    print()

def test_info_extraction():
    """Test de l'extraction d'informations détaillées."""
    
    print("\n📊 TEST D'EXTRACTION D'INFORMATIONS DÉTAILLÉES")
    print("=" * 50)
    
    description = """
    Corriger le bug de connexion dans l'API.
    
    Repository: https://github.com/company/backend-api
    Issue: #789
    Branch: bugfix/connection-issue
    Files: api/auth.py, tests/test_auth.py
    
    CRITIQUE: Bloque la production
    @hotfix @security
    """
    
    # Test extraction d'infos GitHub
    github_info = extract_github_info_from_description(description)
    print("🔗 Informations GitHub extraites:")
    if github_info:
        for key, value in github_info.items():
            print(f"   {key}: {value}")
    else:
        print("   Aucune information GitHub trouvée")
    
    print()

if __name__ == "__main__":
    test_github_extraction()
    test_enrichment()
    test_info_extraction()
    
    print("🎉 Tests terminés!")
    print("\n💡 Usage dans Monday.com:")
    print("   1. Créez une tâche avec un titre")
    print("   2. Dans la description, mettez l'URL GitHub:")
    print("      'Repository: https://github.com/votre-user/votre-repo'")
    print("   3. L'agent extraira automatiquement l'URL !") 
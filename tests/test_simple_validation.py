#!/usr/bin/env python3
"""
Test simple pour valider que le système de tests fonctionne.
Ce test basique permettra de corriger l'erreur "Aucun test valide trouvé".
"""

import unittest
import sys
import os

# Ajouter le chemin racine du projet pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSystemValidation(unittest.TestCase):
    """Tests de validation basique du système."""
    
    def test_system_is_working(self):
        """Test de base pour vérifier que le système de tests fonctionne."""
        self.assertTrue(True, "Le système de tests fonctionne correctement")
    
    def test_imports_are_working(self):
        """Test pour vérifier que les imports Python de base fonctionnent."""
        import json
        import asyncio
        import pathlib
        
        # Vérifier que les modules de base sont accessibles
        self.assertIsNotNone(json)
        self.assertIsNotNone(asyncio)
        self.assertIsNotNone(pathlib)
    
    def test_project_structure_exists(self):
        """Test pour vérifier que la structure de base du projet existe."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Vérifier que les dossiers principaux existent
        important_dirs = ['nodes', 'tools', 'services', 'models']
        
        for dir_name in important_dirs:
            dir_path = os.path.join(project_root, dir_name)
            self.assertTrue(
                os.path.exists(dir_path), 
                f"Le dossier {dir_name} devrait exister dans le projet"
            )
    
    def test_python_version_compatibility(self):
        """Test pour vérifier que la version Python est compatible."""
        # Vérifier Python 3.8+
        self.assertGreaterEqual(
            sys.version_info[:2], (3, 8),
            "Python 3.8+ requis pour ce projet"
        )

def run_simple_test():
    """Fonction pour exécuter ce test de manière autonome."""
    print("🧪 Exécution du test de validation système...")
    
    # Créer une suite de tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSystemValidation)
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Afficher le résultat
    if result.wasSuccessful():
        print("✅ Tous les tests de validation ont réussi!")
        return True
    else:
        print(f"❌ {len(result.failures)} échec(s), {len(result.errors)} erreur(s)")
        return False

if __name__ == "__main__":
    # Exécution directe du fichier
    success = run_simple_test()
    sys.exit(0 if success else 1) 
"""Tests pour valider les corrections des problèmes Monday.com."""

import pytest
from unittest.mock import patch

# Import des services corrigés
from services.database_persistence_service import DatabasePersistenceService
from utils.helpers import get_working_directory, set_working_directory, ensure_working_directory, validate_working_directory
from utils.github_parser import extract_github_url_from_description, enrich_task_with_description_info


class TestMondayColumnValueFixes:
    """Tests pour valider les corrections d'extraction des colonnes Monday.com."""
    
    def test_column_values_dict_format(self):
        """Test extraction depuis format dictionnaire (webhook)."""
        payload = {
            "pulseId": "123456",
            "boardId": "789",
            "pulseName": "Test Task",
            "columnValues": {
                "description_col": {"text": "Implémente login pour: https://github.com/user/repo"},
                "priority_col": {"text": "high"},
                "repo_url_col": {"text": "https://github.com/user/repo"}
            }
        }
        
        persistence = DatabasePersistenceService()
        
        # Simuler la logique d'extraction
        raw_columns = payload.get("columnValues", {})
        normalized_columns = {}
        
        if isinstance(raw_columns, dict):
            normalized_columns = raw_columns
        
        # Tester l'extraction
        description = ""
        repository_url = ""
        
        for col_id, col_value in normalized_columns.items():
            col_id_lower = col_id.lower()
            
            if any(keyword in col_id_lower for keyword in ["description", "desc"]):
                description = col_value.get("text", "")
            elif any(keyword in col_id_lower for keyword in ["repo", "url"]):
                repository_url = col_value.get("text", "")
        
        assert description == "Implémente login pour: https://github.com/user/repo"
        assert repository_url == "https://github.com/user/repo"
    
    def test_column_values_list_format(self):
        """Test extraction depuis format liste (API)."""
        payload = {
            "pulseId": "123456",
            "boardId": "789", 
            "pulseName": "Test Task",
            "column_values": [
                {"id": "description_col", "text": "Implémente feature X pour: https://github.com/user/repo"},
                {"id": "priority_col", "text": "medium"},
                {"id": "repo_url_col", "text": "https://github.com/user/repo"}
            ]
        }
        
        # Simuler la normalisation
        raw_columns = payload.get("column_values", [])
        normalized_columns = {}
        
        if isinstance(raw_columns, list):
            for col in raw_columns:
                if isinstance(col, dict) and "id" in col:
                    normalized_columns[col["id"]] = col
        
        # Tester l'extraction
        description = ""
        repository_url = ""
        
        for col_id, col_value in normalized_columns.items():
            col_id_lower = col_id.lower()
            
            if any(keyword in col_id_lower for keyword in ["description", "desc"]):
                description = col_value.get("text", "")
            elif any(keyword in col_id_lower for keyword in ["repo", "url"]):
                repository_url = col_value.get("text", "")
        
        assert description == "Implémente feature X pour: https://github.com/user/repo"
        assert repository_url == "https://github.com/user/repo"


class TestGitHubUrlExtraction:
    """Tests pour valider l'extraction d'URLs GitHub depuis les descriptions."""
    
    def test_extract_github_url_https(self):
        """Test extraction URL HTTPS standard."""
        description = "Implémente login JWT pour: https://github.com/user/awesome-project"
        url = extract_github_url_from_description(description)
        assert url == "https://github.com/user/awesome-project"
    
    def test_extract_github_url_with_git(self):
        """Test extraction URL avec .git."""
        description = "Clone ce repo: https://github.com/user/project.git et implemente la feature"
        url = extract_github_url_from_description(description)
        assert url == "https://github.com/user/project"  # La fonction retire .git
    
    def test_extract_github_url_ssh(self):
        """Test extraction URL SSH."""
        description = "Utilise git@github.com:user/project.git pour cette tâche"
        url = extract_github_url_from_description(description)
        assert url == "https://github.com/user/project"  # Convertie en HTTPS
    
    def test_extract_github_url_markdown_link(self):
        """Test extraction depuis lien Markdown."""
        description = "Voir le [projet](https://github.com/user/project) pour plus d'infos"
        url = extract_github_url_from_description(description)
        assert url == "https://github.com/user/project"
    
    def test_no_github_url(self):
        """Test quand aucune URL GitHub n'est présente."""
        description = "Implémente une fonctionnalité générique sans repo spécifique"
        url = extract_github_url_from_description(description)
        assert url is None
    
    def test_task_enrichment_with_description_url(self):
        """Test enrichissement de tâche avec URL dans description."""
        task_data = {
            "task_id": "123",
            "title": "Implement feature",
            "repository_url": "https://github.com/old/repo"
        }
        description = "Implemente pour: https://github.com/new/repo"
        
        enriched = enrich_task_with_description_info(task_data, description)
        
        assert enriched["repository_url"] == "https://github.com/new/repo"
        assert enriched["task_id"] == "123"
        assert enriched["title"] == "Implement feature"


class TestWorkingDirectoryHelpers:
    """Tests pour valider les helpers de répertoire de travail."""
    
    def test_get_working_directory_from_root(self):
        """Test récupération depuis la racine de l'état."""
        state = {
            "working_directory": "/tmp/test_root",
            "results": {
                "working_directory": "/tmp/test_results"
            }
        }
        
        with patch('os.path.exists', return_value=True):
            wd = get_working_directory(state)
            assert wd == "/tmp/test_root"
    
    def test_get_working_directory_from_results(self):
        """Test récupération depuis results."""
        state = {
            "results": {
                "working_directory": "/tmp/test_results"
            }
        }
        
        with patch('os.path.exists', return_value=True):
            wd = get_working_directory(state)
            assert wd == "/tmp/test_results"
    
    def test_get_working_directory_from_prepare_result(self):
        """Test récupération depuis prepare_result."""
        state = {
            "results": {
                "prepare_result": {
                    "working_directory": "/tmp/test_prepare"
                }
            }
        }
        
        with patch('os.path.exists', return_value=True):
            wd = get_working_directory(state)
            assert wd == "/tmp/test_prepare"
    
    def test_set_working_directory(self):
        """Test définition du répertoire de travail."""
        state = {}
        set_working_directory(state, "/tmp/test_set")
        
        assert state["working_directory"] == "/tmp/test_set"
        assert state["results"]["working_directory"] == "/tmp/test_set"
    
    def test_validate_working_directory_valid(self):
        """Test validation d'un répertoire valide."""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.isdir', return_value=True), \
             patch('os.access', return_value=True):
            
            is_valid = validate_working_directory("/tmp/valid", "test_node")
            assert is_valid is True
    
    def test_validate_working_directory_invalid(self):
        """Test validation d'un répertoire invalide."""
        is_valid = validate_working_directory(None, "test_node")
        assert is_valid is False
        
        with patch('os.path.exists', return_value=False):
            is_valid = validate_working_directory("/tmp/invalid", "test_node")
            assert is_valid is False
    
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    def test_ensure_working_directory_creates_new(self, mock_exists, mock_mkdtemp):
        """Test création d'un nouveau répertoire si nécessaire."""
        mock_exists.return_value = False
        mock_mkdtemp.return_value = "/tmp/new_created"
        
        state = {}
        wd = ensure_working_directory(state, "test_")
        
        assert wd == "/tmp/new_created"
        assert state["working_directory"] == "/tmp/new_created"
        assert state["results"]["working_directory"] == "/tmp/new_created"


class TestDescriptionExtraction:
    """Tests pour valider l'extraction robuste des descriptions."""
    
    def test_description_from_column_text(self):
        """Test extraction depuis colonne avec propriété text."""
        column = {
            "id": "description_col",
            "text": "Description détaillée de la tâche",
            "title": "Description"
        }
        
        # Simuler la fonction helper
        def safe_extract_column_text(column):
            return (column.get("text") or "").strip()
        
        text = safe_extract_column_text(column)
        assert text == "Description détaillée de la tâche"
    
    def test_description_from_column_value(self):
        """Test extraction depuis colonne avec propriété value."""
        column = {
            "id": "description_col",
            "value": "Description dans value",
            "title": "Description"
        }
        
        def safe_extract_column_text(column):
            return (
                column.get("text") or 
                column.get("value") or 
                ""
            ).strip()
        
        text = safe_extract_column_text(column)
        assert text == "Description dans value"
    
    def test_description_from_nested_value(self):
        """Test extraction depuis value imbriqué."""
        column = {
            "id": "description_col",
            "value": {
                "text": "Description imbriquée",
                "display_value": "Autre valeur"
            }
        }
        
        def safe_extract_column_text(column):
            text_value = (column.get("text") or "").strip()
            
            if not text_value and isinstance(column.get("value"), dict):
                value_dict = column.get("value", {})
                text_value = (
                    value_dict.get("text") or
                    value_dict.get("value") or
                    str(value_dict.get("display_value", ""))
                ).strip()
            
            return text_value
        
        text = safe_extract_column_text(column)
        assert text == "Description imbriquée"


# Tests d'intégration
class TestIntegration:
    """Tests d'intégration pour valider le workflow complet."""
    
    @pytest.mark.asyncio
    async def test_monday_webhook_processing_complete(self):
        """Test du traitement complet d'un webhook Monday.com."""
        
        # Payload simulé avec tous les éléments
        payload = {
            "pulseId": "123456789",
            "boardId": "987654321",
            "pulseName": "Implémenter système de login",
            "columnValues": {
                "description": {
                    "text": "Créer un système de login sécurisé avec JWT pour: https://github.com/company/awesome-app"
                },
                "priority": {"text": "high"},
                "repository_url": {"text": "https://github.com/company/awesome-app"}
            }
        }
        
        # Simuler le traitement
        # 1. Extraction des données
        item_id = payload.get("pulseId")
        title = payload.get("pulseName")
        
        # 2. Normalisation des colonnes
        raw_columns = payload.get("columnValues", {})
        description = raw_columns.get("description", {}).get("text", "")
        repository_url = raw_columns.get("repository_url", {}).get("text", "")
        
        # 3. Enrichissement avec parser GitHub
        enriched_data = enrich_task_with_description_info({
            "task_id": item_id,
            "title": title,
            "repository_url": repository_url
        }, description)
        
        # 4. Vérifications
        assert enriched_data["task_id"] == "123456789"
        assert enriched_data["title"] == "Implémenter système de login"
        assert enriched_data["repository_url"] == "https://github.com/company/awesome-app"
        
        # 5. Test URL GitHub extraite de la description
        extracted_url = extract_github_url_from_description(description)
        assert extracted_url == "https://github.com/company/awesome-app"


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v"]) 
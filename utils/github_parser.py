"""Utilitaires pour extraire les informations GitHub depuis la description des tâches."""

import re
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_github_url_from_description(description: str) -> Optional[str]:
    """
    Extrait l'URL GitHub depuis la description d'une tâche.
    
    Supporte différents formats:
    - URLs complètes: https://github.com/user/repo
    - URLs avec .git: https://github.com/user/repo.git
    - URLs SSH: git@github.com:user/repo.git
    - Mentions courtes: github.com/user/repo
    - Liens dans markdown: [Repo](https://github.com/user/repo)
    - URLs avec contexte: "pour: https://github.com/user/repo"
    
    Args:
        description: Description de la tâche qui peut contenir une URL GitHub
        
    Returns:
        URL GitHub formatée ou None si non trouvée
    """
    if not description:
        return None
    
    logger.debug(f"🔍 Recherche URL GitHub dans description: {description[:200]}...")
    
    # ✅ AMÉLIORATION: Patterns harmonisés avec prepare_node.py
    patterns = [
        # URLs complètes HTTPS (plus strict)
        r'https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?(?:/[^\s]*)?',
        
        # URLs avec contexte descriptif
        r'(?:repository|repo|projet|github|code|source)[\s:=]*https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',
        
        # URLs SSH
        r'git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',
        
        # URLs courtes (avec protection contre faux positifs)
        r'github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?(?!/[\w-]+(?:\.[\w-]+)*$)',
        
        # Liens Markdown
        r'\[.*?\]\(https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?\)',
        
        # Patterns avec mots-clés français/anglais
        r'(?:pour|for|from|de|du|vers|to)[\s:]*https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?'
    ]
    
    for pattern_idx, pattern in enumerate(patterns):
        matches = re.findall(pattern, description, re.IGNORECASE)
        if matches:
            # Prendre le premier match valide
            match = matches[0]
            
            # Construire l'URL selon le type de match
            if isinstance(match, tuple) and len(match) >= 2:
                # Match avec groupes (owner, repo)
                owner, repo = match[0], match[1]
                url = f"https://github.com/{owner}/{repo}"
            elif isinstance(match, str):
                # Match simple - peut être une URL complète
                url = match
            else:
                continue
            
            # Normaliser l'URL
            if not url.startswith('http'):
                url = f"https://{url}"
            if url.endswith('.git'):
                url = url[:-4]
            
            # Validation basique de l'URL
            if re.match(r'https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', url):
                logger.info(f"✅ URL GitHub trouvée avec pattern {pattern_idx + 1} dans description: {url}")
                logger.debug(f"   Texte source: {description[:200]}...")
                return url
            else:
                logger.debug(f"⚠️ URL GitHub invalide trouvée: {url}")

    logger.info("ℹ️ Aucune URL GitHub trouvée dans la description")
    return None


def extract_github_info_from_description(description: str) -> Optional[Dict[str, str]]:
    """
    Extrait les informations GitHub détaillées depuis la description.
    
    Args:
        description: Description de la tâche
        
    Returns:
        Dictionnaire avec owner, repo, url ou None
    """
    github_url = extract_github_url_from_description(description)
    
    if not github_url:
        return None
    
    # Extraire owner et repo de l'URL
    match = re.search(r'github\.com/([^/]+)/([^/]+)', github_url)
    if match:
        owner = match.group(1)
        repo = match.group(2)
        
        return {
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "url": github_url,
            "clone_url": f"{github_url}.git",
            "ssh_url": f"git@github.com:{owner}/{repo}.git"
        }
    
    return None


def extract_additional_info_from_description(description: str) -> Dict[str, Any]:
    """
    Extrait des informations additionnelles depuis la description.
    
    Recherche:
    - Numéro d'issue: #123, issue #123
    - Branche suggérée: branch: feature/xxx
    - Fichiers à modifier: files: src/app.py, config.json
    - Tags: @urgent, @breaking-change
    
    Args:
        description: Description de la tâche
        
    Returns:
        Dictionnaire avec les informations extraites
    """
    info = {}
    
    if not description:
        return info
    
    # Numéro d'issue
    issue_match = re.search(r'(?:issue\s*#?|#)(\d+)', description, re.IGNORECASE)
    if issue_match:
        info["issue_number"] = int(issue_match.group(1))
    
    # Branche suggérée
    branch_patterns = [
        r'(?:branch|branche)[\s:]+([a-zA-Z0-9_.//-]+)',
        r'(?:git\s+checkout|checkout)\s+([a-zA-Z0-9_.//-]+)'
    ]
    
    for pattern in branch_patterns:
        branch_match = re.search(pattern, description, re.IGNORECASE)
        if branch_match:
            info["suggested_branch"] = branch_match.group(1)
            break
    
    # Fichiers à modifier
    files_patterns = [
        r'(?:files?|fichiers?)[\s:]+([a-zA-Z0-9_./,\s-]+)',
        r'(?:modify|modifier|update|mettre à jour)[\s:]+([a-zA-Z0-9_./,\s-]+\.(?:py|js|ts|json|md|txt|yml|yaml))',
    ]
    
    for pattern in files_patterns:
        files_match = re.search(pattern, description, re.IGNORECASE)
        if files_match:
            files_text = files_match.group(1)
            # Séparer par virgules et nettoyer
            files = [f.strip() for f in re.split(r'[,\s]+', files_text) if f.strip()]
            # Filtrer pour garder seulement les noms de fichiers valides
            valid_files = [f for f in files if re.match(r'^[a-zA-Z0-9_.//-]+\.[a-zA-Z]+$', f)]
            if valid_files:
                info["suggested_files"] = valid_files
                break
    
    # Tags
    tags = re.findall(r'@([a-zA-Z0-9_-]+)', description)
    if tags:
        info["tags"] = tags
    
    # Urgence
    if re.search(r'(?:urgent|critique|asap|immediately)', description, re.IGNORECASE):
        info["is_urgent"] = True
    
    # Breaking change
    if re.search(r'(?:breaking.?change|breaking|incompatible)', description, re.IGNORECASE):
        info["is_breaking"] = True
    
    return info


def enrich_task_with_description_info(task_data: Dict[str, Any], description: str) -> Dict[str, Any]:
    """
    Enrichit les données d'une tâche avec les informations extraites de la description.
    
    Args:
        task_data: Données actuelles de la tâche
        description: Description à analyser
        
    Returns:
        Données de tâche enrichies
    """
    enriched = task_data.copy()
    
    # ✅ CORRECTION CRITIQUE: Conserver la description dans les données enrichies
    enriched["description"] = description
    
    # URL GitHub - PRIORITÉ ABSOLUE À LA DESCRIPTION
    github_url = extract_github_url_from_description(description)
    if github_url:
        # L'URL trouvée dans la description REMPLACE toujours celle existante
        old_url = enriched.get("repository_url", "")
        enriched["repository_url"] = github_url
        
        if old_url and old_url != github_url:
            logger.info("🔄 Repository URL remplacée par celle de la description:")
            logger.info(f"   Ancienne: {old_url}")
            logger.info(f"   Nouvelle: {github_url}")
        else:
            logger.info(f"✅ Repository URL définie depuis la description: {github_url}")
    else:
        # Pas d'URL dans la description, garder celle existante
        existing_url = enriched.get("repository_url", "")
        if existing_url:
            logger.info(f"📝 Aucune URL GitHub dans description, utilisation de l'URL existante: {existing_url}")
        else:
            logger.warning("⚠️ Aucune URL GitHub trouvée ni dans description ni dans les paramètres")
    
    # Informations additionnelles
    extra_info = extract_additional_info_from_description(description)
    
    # Branche suggérée
    if extra_info.get("suggested_branch") and not enriched.get("branch_name"):
        enriched["branch_name"] = extra_info["suggested_branch"]
        logger.info(f"📝 Branche suggérée: {extra_info['suggested_branch']}")
    
    # Fichiers suggérés
    if extra_info.get("suggested_files"):
        if not enriched.get("files_to_modify"):
            enriched["files_to_modify"] = extra_info["suggested_files"]
            logger.info(f"📝 Fichiers suggérés: {extra_info['suggested_files']}")
    
    # Urgence
    if extra_info.get("is_urgent"):
        if enriched.get("priority", "").lower() in ["", "medium", "low"]:
            enriched["priority"] = "urgent"
            logger.info("📝 Priorité mise à jour: urgent (détectée dans description)")
    
    # Numéro d'issue
    if extra_info.get("issue_number"):
        enriched["issue_number"] = extra_info["issue_number"]
        logger.info(f"📝 Issue liée: #{extra_info['issue_number']}")
    
    # Tags
    if extra_info.get("tags"):
        enriched["tags"] = extra_info["tags"]
        logger.info(f"📝 Tags détectés: {extra_info['tags']}")
    
    return enriched 
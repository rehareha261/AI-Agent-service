# ✅ Checklist de vérification - Implémentation pg_partman

## 📋 Avant le déploiement

### ✅ Fichiers créés/modifiés

Vérifier que tous les fichiers suivants existent et sont corrects :

- [ ] `docker/postgres/Dockerfile` - Image PostgreSQL personnalisée
- [ ] `docker/postgres/init-scripts/01-enable-pg-partman.sql` - Installation pg_partman
- [ ] `docker/postgres/init-scripts/02-configure-webhook-events-partman.sql` - Configuration
- [ ] `docker/postgres/maintenance-partman.sh` - Script de maintenance
- [ ] `docker/postgres/cron-partman-maintenance` - Configuration cron
- [ ] `scripts/migrate_to_pg_partman.sql` - Script de migration
- [ ] `docker-compose.rabbitmq.yml` - Mis à jour avec build personnalisé
- [ ] `config/init-db.sql` - Schéma de base de données

### ✅ Vérification du Dockerfile

```bash
# Vérifier la syntaxe du Dockerfile
docker build -t test-pg-partman -f docker/postgres/Dockerfile docker/postgres/

# Nettoyer l'image de test
docker rmi test-pg-partman
```

**Résultat attendu** : Build réussi sans erreurs

### ✅ Vérification des scripts SQL

```bash
# Vérifier la syntaxe SQL des scripts d'initialisation
for file in docker/postgres/init-scripts/*.sql; do
  echo "Vérification de $file..."
  docker run --rm -v "$PWD/$file:/tmp/check.sql:ro" postgres:15-alpine \
    psql --set ON_ERROR_STOP=1 -f /tmp/check.sql --dry-run 2>&1 | grep -i error || echo "✅ OK"
done
```

### ✅ Sauvegarde (pour installation existante)

```bash
# Créer un dossier pour les sauvegardes
mkdir -p backups

# Sauvegarder la base de données actuelle
docker exec ai_agent_postgres pg_dump -U admin ai_agent_admin > backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Vérifier la sauvegarde
ls -lh backups/
```

**Résultat attendu** : Fichier de sauvegarde créé avec une taille > 0

## 🚀 Pendant le déploiement

### ✅ Construction de l'image

```bash
# Construire l'image PostgreSQL
docker-compose -f docker-compose.rabbitmq.yml build postgres
```

**Résultat attendu** :
```
Successfully built [image_id]
Successfully tagged ai_agent_postgres:pg_partman
```

**Points de contrôle** :
- [ ] Téléchargement de pg_partman réussi
- [ ] Compilation de pg_partman réussie
- [ ] Installation de dcron et bash réussie
- [ ] Copie des scripts de maintenance réussie

### ✅ Démarrage du container

```bash
# Arrêter le container existant si nécessaire
docker-compose -f docker-compose.rabbitmq.yml down postgres

# Démarrer le nouveau container
docker-compose -f docker-compose.rabbitmq.yml up -d postgres

# Suivre les logs en temps réel
docker-compose -f docker-compose.rabbitmq.yml logs -f postgres
```

**Points de contrôle dans les logs** :
- [ ] `🔧 Installation de pg_partman`
- [ ] `✅ Extension pg_partman installée avec succès`
- [ ] `📊 Configuration du partitionnement automatique`
- [ ] `✅ Table webhook_events enregistrée dans pg_partman`
- [ ] `✅ Configuration pg_partman terminée`

### ✅ Vérification de santé

```bash
# Vérifier que PostgreSQL est prêt
docker exec ai_agent_postgres pg_isready -U admin -d ai_agent_admin
```

**Résultat attendu** :
```
ai_agent_postgres:5432 - accepting connections
```

## 🔍 Après le déploiement

### ✅ Test 1 : Vérification de l'extension

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'pg_partman';
"
```

**Résultat attendu** :
```
  extname   | extversion 
------------+------------
 pg_partman | 5.0.1
```

- [ ] Extension installée
- [ ] Version correcte (5.0.1)

### ✅ Test 2 : Vérification de la configuration

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT 
    parent_table,
    partition_type,
    partition_interval,
    premake,
    retention,
    infinite_time_partitions
FROM partman.part_config
WHERE parent_table = 'public.webhook_events';
"
```

**Résultat attendu** :
```
     parent_table      | partition_type | partition_interval | premake | retention | infinite_time_partitions 
-----------------------+----------------+--------------------+---------+-----------+--------------------------
 public.webhook_events | native         | 1 mon              |       4 | 6 mons    | t
```

- [ ] Table configurée
- [ ] Intervalle = 1 mois
- [ ] Premake = 4
- [ ] Rétention = 6 mois
- [ ] Partitions infinies activé

### ✅ Test 3 : Vérification des partitions

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename LIKE 'webhook_events_%'
ORDER BY tablename;
"
```

**Résultat attendu** : Au moins 5-6 partitions listées

- [ ] Partitions existantes préservées (si migration)
- [ ] Nouvelles partitions créées (mois actuel + 4 mois futurs)
- [ ] Nommage correct : `webhook_events_YYYY_MM`

### ✅ Test 4 : Test d'insertion

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
-- Insérer un événement de test
INSERT INTO webhook_events (source, event_type, payload, headers, received_at)
VALUES (
    'test_pg_partman',
    'verification_test',
    '{\"test\": true, \"timestamp\": \"$(date -Iseconds)\"}'::jsonb,
    '{\"content-type\": \"application/json\"}'::jsonb,
    NOW()
)
RETURNING 
    webhook_events_id,
    tableoid::regclass AS partition,
    source,
    received_at;
"
```

**Résultat attendu** : Insertion réussie avec affichage de la partition utilisée

- [ ] Insertion réussie
- [ ] Partition correcte (mois actuel)
- [ ] ID généré correctement

### ✅ Test 5 : Vérification de la maintenance

```bash
# Exécuter manuellement la maintenance
docker exec ai_agent_postgres /usr/local/bin/maintenance-partman.sh
```

**Résultat attendu** :
```
==========================================
🔧 Maintenance pg_partman
==========================================
Date: 2025-10-14 XX:XX:XX
Database: ai_agent_admin
User: admin

✅ Maintenance terminée avec succès
==========================================
```

- [ ] Script exécuté sans erreur
- [ ] Affichage des statistiques
- [ ] Logs créés dans `/var/log/postgresql/partman-maintenance.log`

### ✅ Test 6 : Vérification du cron

```bash
# Vérifier que cron est installé et configuré
docker exec ai_agent_postgres cat /etc/crontabs/postgres
```

**Résultat attendu** :
```
0 2 * * * /maintenance-partman.sh >> /var/log/postgresql/partman-maintenance.log 2>&1
```

- [ ] Fichier cron existe
- [ ] Tâche configurée pour 2h du matin
- [ ] Redirection des logs configurée

### ✅ Test 7 : Test de performance

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
\timing on
-- Requête sur partition spécifique (devrait être rapide)
EXPLAIN ANALYZE
SELECT COUNT(*) 
FROM webhook_events 
WHERE received_at >= date_trunc('month', CURRENT_DATE)
  AND received_at < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month';
"
```

**Points de contrôle** :
- [ ] Plan d'exécution montre partition pruning
- [ ] Temps d'exécution acceptable (< 100ms pour peu de données)
- [ ] Une seule partition scannée

### ✅ Test 8 : Nettoyage des données de test

```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
DELETE FROM webhook_events WHERE source = 'test_pg_partman';
SELECT 'Test data cleaned' AS status;
"
```

- [ ] Données de test supprimées

## 📊 Métriques à surveiller

### Après 24h

```bash
# Vérifier que la maintenance s'est exécutée
docker exec ai_agent_postgres tail -100 /var/log/postgresql/partman-maintenance.log
```

- [ ] Log de maintenance du jour présent
- [ ] Aucune erreur dans les logs
- [ ] Partitions créées/nettoyées selon besoin

### Après 1 semaine

```bash
# Vérifier l'évolution de l'espace disque
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    (SELECT n_live_tup FROM pg_stat_user_tables 
     WHERE relname = tablename) AS rows_estimate
FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%'
ORDER BY tablename DESC
LIMIT 10;
"
```

- [ ] Espace disque stable
- [ ] Partitions anciennes supprimées (si > 6 mois)
- [ ] Nouvelles partitions créées au besoin

## 🚨 Points d'attention

### Erreurs potentielles et solutions

| Erreur | Cause probable | Solution |
|--------|----------------|----------|
| `extension "pg_partman" does not exist` | Compilation échouée | Reconstruire avec `--no-cache` |
| `no partition of relation found for row` | Partition manquante pour la date | Exécuter `partman.run_maintenance()` |
| `permission denied for schema partman` | Permissions incorrectes | Vérifier les GRANT dans init scripts |
| Container ne démarre pas | Erreur dans scripts init | Vérifier logs : `docker logs ai_agent_postgres` |

## ✅ Checklist finale

Avant de marquer l'implémentation comme terminée :

### Configuration
- [ ] pg_partman installé et fonctionnel
- [ ] webhook_events configuré avec rétention de 6 mois
- [ ] 4 mois de partitions futures créés
- [ ] Cron job configuré pour maintenance quotidienne

### Tests
- [ ] Test d'insertion réussi
- [ ] Test de requête réussi
- [ ] Partition pruning fonctionne
- [ ] Script de maintenance s'exécute sans erreur

### Documentation
- [ ] Documentation complète (`PG_PARTMAN_IMPLEMENTATION.md`)
- [ ] Scripts de migration disponibles
- [ ] Procédures de dépannage documentées

### Sécurité
- [ ] Sauvegarde effectuée (si migration)
- [ ] Pas de données perdues
- [ ] Performances acceptables

### Monitoring
- [ ] Logs de maintenance accessibles
- [ ] Métriques PostgreSQL stables
- [ ] Alertes configurées (si applicable)

## 📝 Rapport de vérification

```bash
# Générer un rapport complet
cat << 'EOF' > verification_report.sh
#!/bin/bash
echo "=========================================="
echo "RAPPORT DE VÉRIFICATION PG_PARTMAN"
echo "Date: $(date)"
echo "=========================================="
echo ""

echo "1. Extension pg_partman:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_partman';"
echo ""

echo "2. Configuration webhook_events:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c \
  "SELECT parent_table, partition_interval, premake, retention FROM partman.part_config WHERE parent_table = 'public.webhook_events';"
echo ""

echo "3. Partitions existantes:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c \
  "SELECT COUNT(*) as partition_count FROM pg_tables WHERE tablename LIKE 'webhook_events_%';"
echo ""

echo "4. Espace disque total:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c \
  "SELECT pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))) AS total_size FROM pg_tables WHERE tablename LIKE 'webhook_events%';"
echo ""

echo "=========================================="
echo "Vérification terminée"
echo "=========================================="
EOF

chmod +x verification_report.sh
./verification_report.sh
```

---

**Date** : 14 Octobre 2025  
**Version** : 1.0


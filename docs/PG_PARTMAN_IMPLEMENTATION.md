# 📊 Implémentation de pg_partman pour webhook_events

## 📝 Vue d'ensemble

Ce document décrit l'implémentation de **pg_partman** pour gérer automatiquement le partitionnement de la table `webhook_events`. Cette solution remplace la création manuelle de partitions mensuelles par un système entièrement automatisé.

## 🎯 Objectifs

- ✅ Automatiser la création de partitions mensuelles pour `webhook_events`
- ✅ Gérer automatiquement la rétention des données (6 mois)
- ✅ Éliminer la maintenance manuelle des partitions
- ✅ Améliorer les performances des requêtes sur les événements webhook
- ✅ Préparer 4 mois de partitions à l'avance

## 🏗️ Architecture

### Structure des fichiers créés

```
AI-Agent/
├── docker/
│   └── postgres/
│       ├── Dockerfile                          # Image PostgreSQL personnalisée avec pg_partman
│       ├── maintenance-partman.sh              # Script de maintenance automatique
│       ├── cron-partman-maintenance            # Configuration cron
│       └── init-scripts/
│           ├── 01-enable-pg-partman.sql        # Installation de pg_partman
│           └── 02-configure-webhook-events-partman.sql  # Configuration initiale
├── scripts/
│   └── migrate_to_pg_partman.sql               # Script de migration (pour BDD existantes)
├── config/
│   └── init-db.sql                             # Schéma de base de données initial
└── docker-compose.rabbitmq.yml                 # Mis à jour pour utiliser le Dockerfile personnalisé
```

## 🚀 Déploiement

### Pour une nouvelle installation

1. **Construire l'image PostgreSQL avec pg_partman** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml build postgres
   ```

2. **Démarrer les services** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml up -d postgres
   ```

3. **Vérifier l'installation** :
   ```bash
   docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin
   ```

   Puis dans psql :
   ```sql
   -- Vérifier que pg_partman est installé
   SELECT extversion FROM pg_extension WHERE extname = 'pg_partman';
   
   -- Vérifier la configuration de webhook_events
   SELECT * FROM partman.part_config WHERE parent_table = 'public.webhook_events';
   
   -- Lister les partitions créées
   SELECT 
       tablename,
       pg_size_pretty(pg_total_relation_size('public.' || tablename)) AS size
   FROM pg_tables 
   WHERE schemaname = 'public' 
     AND tablename LIKE 'webhook_events_%'
   ORDER BY tablename;
   ```

### Pour une installation existante

1. **Sauvegarder la base de données actuelle** :
   ```bash
   docker exec ai_agent_postgres pg_dump -U admin ai_agent_admin > backup_before_partman.sql
   ```

2. **Arrêter les services** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml down
   ```

3. **Construire la nouvelle image** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml build postgres
   ```

4. **Démarrer PostgreSQL seul** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml up -d postgres
   ```

5. **Attendre que PostgreSQL soit prêt** :
   ```bash
   docker exec ai_agent_postgres pg_isready -U admin
   ```

6. **Exécuter le script de migration** :
   ```bash
   docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < scripts/migrate_to_pg_partman.sql
   ```

7. **Démarrer tous les services** :
   ```bash
   docker-compose -f docker-compose.rabbitmq.yml up -d
   ```

## ⚙️ Configuration

### Paramètres pg_partman pour webhook_events

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| **Intervalle de partition** | 1 mois | Une nouvelle partition par mois |
| **Partitions pré-créées** | 4 | 4 mois de partitions à l'avance |
| **Rétention** | 6 mois | Les données plus anciennes sont supprimées |
| **Type de partitionnement** | Native (RANGE) | Utilise le partitionnement natif de PostgreSQL |
| **Colonne de partition** | `received_at` | Partition basée sur la date de réception |

### Maintenance automatique

La maintenance automatique s'exécute **tous les jours à 2h du matin** via cron et effectue :

1. ✅ Création de nouvelles partitions si nécessaire
2. ✅ Suppression des partitions expirées (> 6 mois)
3. ✅ Vérification de l'intégrité du partitionnement

Pour exécuter manuellement la maintenance :

```bash
# Depuis le host
docker exec ai_agent_postgres /usr/local/bin/maintenance-partman.sh

# Ou depuis PostgreSQL
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin \
  -c "SELECT partman.run_maintenance_proc();"
```

## 🔍 Vérification et tests

### 1. Vérifier que pg_partman fonctionne

```sql
-- Se connecter à la base de données
\c ai_agent_admin

-- Vérifier l'extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_partman';

-- Vérifier la configuration
SELECT 
    parent_table,
    partition_type,
    partition_interval,
    premake,
    retention,
    infinite_time_partitions
FROM partman.part_config;
```

**Résultat attendu** :
```
 parent_table          | partition_type | partition_interval | premake | retention | infinite_time_partitions
-----------------------+----------------+--------------------+---------+-----------+--------------------------
 public.webhook_events | native         | 1 mon              | 4       | 6 mons    | t
```

### 2. Vérifier les partitions créées

```sql
-- Lister toutes les partitions webhook_events
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename LIKE 'webhook_events_%'
ORDER BY tablename;
```

**Résultat attendu** : Au moins 5-6 partitions (mois actuel + 4 mois futurs + éventuellement mois précédent)

### 3. Tester l'insertion de données

```sql
-- Insérer un événement de test
INSERT INTO webhook_events (source, event_type, payload, headers, received_at)
VALUES (
    'test',
    'test_event',
    '{"test": true}'::jsonb,
    '{"content-type": "application/json"}'::jsonb,
    NOW()
);

-- Vérifier que l'événement est dans la bonne partition
SELECT 
    tableoid::regclass AS partition_name,
    webhook_events_id,
    source,
    event_type,
    received_at
FROM webhook_events
WHERE source = 'test'
ORDER BY received_at DESC
LIMIT 1;

-- Nettoyer le test
DELETE FROM webhook_events WHERE source = 'test';
```

### 4. Vérifier les logs de maintenance

```bash
# Voir les logs de la dernière maintenance
docker exec ai_agent_postgres tail -50 /var/log/postgresql/partman-maintenance.log
```

### 5. Tester la performance

```sql
-- Activer le timing
\timing on

-- Requête sur le mois actuel (devrait être très rapide)
SELECT COUNT(*) 
FROM webhook_events 
WHERE received_at >= date_trunc('month', CURRENT_DATE);

-- Requête sur les 6 derniers mois (utilise partition pruning)
SELECT 
    date_trunc('month', received_at) AS month,
    COUNT(*) AS events_count
FROM webhook_events
WHERE received_at >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY date_trunc('month', received_at)
ORDER BY month;
```

## 📊 Monitoring

### Requêtes utiles pour le monitoring

```sql
-- 1. Vue d'ensemble des partitions
SELECT 
    child.relname AS partition,
    pg_get_expr(child.relpartbound, child.oid) AS range,
    pg_size_pretty(pg_total_relation_size(child.oid)) AS size,
    (SELECT n_live_tup FROM pg_stat_user_tables 
     WHERE relname = child.relname) AS rows_estimate
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'webhook_events'
ORDER BY child.relname DESC;

-- 2. Espace disque utilisé par partition
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 3. Dernière exécution de la maintenance
SELECT 
    parent_table,
    last_partition,
    last_run_time
FROM partman.part_config_sub
WHERE parent_table = 'public.webhook_events';

-- 4. Statistiques d'utilisation
SELECT 
    schemaname,
    tablename,
    n_live_tup AS rows,
    n_dead_tup AS dead_rows,
    last_vacuum,
    last_autovacuum,
    last_analyze
FROM pg_stat_user_tables
WHERE tablename LIKE 'webhook_events_%'
ORDER BY tablename DESC;
```

## 🔧 Maintenance manuelle

### Forcer la création de partitions futures

```sql
-- Créer des partitions supplémentaires si nécessaire
SELECT partman.run_maintenance('public.webhook_events');
```

### Modifier la configuration

```sql
-- Changer le nombre de partitions pré-créées
UPDATE partman.part_config 
SET premake = 6 
WHERE parent_table = 'public.webhook_events';

-- Changer la rétention
UPDATE partman.part_config 
SET retention = '12 months',
    retention_keep_table = false
WHERE parent_table = 'public.webhook_events';

-- Appliquer immédiatement
SELECT partman.run_maintenance('public.webhook_events');
```

### Supprimer manuellement une partition ancienne

```sql
-- Lister les partitions
SELECT tablename FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%' 
ORDER BY tablename;

-- Supprimer une partition spécifique (ATTENTION : perte de données!)
DROP TABLE IF EXISTS webhook_events_2024_01 CASCADE;
```

## 🚨 Dépannage

### Problème : pg_partman n'est pas installé

**Symptôme** :
```
ERROR: extension "pg_partman" does not exist
```

**Solution** :
```bash
# Reconstruire l'image PostgreSQL
docker-compose -f docker-compose.rabbitmq.yml build --no-cache postgres
docker-compose -f docker-compose.rabbitmq.yml up -d postgres
```

### Problème : Les partitions ne sont pas créées automatiquement

**Vérification** :
```sql
SELECT * FROM partman.part_config WHERE parent_table = 'public.webhook_events';
```

**Si vide**, exécuter manuellement :
```bash
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < scripts/migrate_to_pg_partman.sql
```

### Problème : Cron ne s'exécute pas

**Vérification** :
```bash
# Vérifier que le cron tourne dans le container
docker exec ai_agent_postgres ps aux | grep cron

# Vérifier la configuration cron
docker exec ai_agent_postgres cat /etc/crontabs/postgres

# Exécuter manuellement
docker exec ai_agent_postgres /usr/local/bin/maintenance-partman.sh
```

### Problème : Erreur "no partition of relation found for row"

**Cause** : Tentative d'insertion de données hors des partitions existantes

**Solution** :
```sql
-- Créer immédiatement les partitions manquantes
SELECT partman.run_maintenance('public.webhook_events');
```

## 📈 Avantages de cette implémentation

1. **✅ Automatisation complète** : Plus besoin de créer manuellement des partitions
2. **✅ Performance optimale** : Les requêtes utilisent le partition pruning automatiquement
3. **✅ Gestion de la rétention** : Les anciennes données sont supprimées automatiquement
4. **✅ Anticipation** : 4 mois de partitions toujours prêts à l'avance
5. **✅ Maintenabilité** : Configuration centralisée et facilement modifiable
6. **✅ Observabilité** : Logs et métriques de maintenance automatiques

## 🔗 Références

- [Documentation pg_partman](https://github.com/pgpartman/pg_partman)
- [PostgreSQL Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [Best practices pour le partitionnement](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITIONING-OVERVIEW)

## 📝 Notes importantes

- ⚠️ **Sauvegardez toujours** avant de modifier le partitionnement
- ⚠️ Les partitions sont supprimées automatiquement après 6 mois (rétention)
- ⚠️ La maintenance automatique nécessite que le container reste actif
- ✅ Les performances sont optimales pour les requêtes sur des périodes récentes
- ✅ Le partitionnement est transparent pour l'application (aucune modification du code nécessaire)

---

**Date de création** : 14 Octobre 2025  
**Version** : 1.0  
**Auteur** : AI-Agent Team


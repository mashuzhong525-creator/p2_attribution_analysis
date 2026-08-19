-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: localhost    Database: bia
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `bia`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `bia` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `bia`;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('0003_auth_must_change_password');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `analysis_results`
--

DROP TABLE IF EXISTS `analysis_results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `analysis_results` (
  `id` varchar(32) NOT NULL,
  `task_id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `problem_definition` text NOT NULL,
  `key_metrics_json` json NOT NULL,
  `evidence_list_json` json NOT NULL,
  `conclusion_text` text NOT NULL,
  `missing_data_text` text NOT NULL,
  `next_action_text` text NOT NULL,
  `result_markdown` text NOT NULL,
  `result_file_path` varchar(512) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_res_task` (`task_id`),
  KEY `ix_res_conv` (`conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `analysis_results`
--

LOCK TABLES `analysis_results` WRITE;
/*!40000 ALTER TABLE `analysis_results` DISABLE KEYS */;
/*!40000 ALTER TABLE `analysis_results` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `analysis_tasks`
--

DROP TABLE IF EXISTS `analysis_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `analysis_tasks` (
  `id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `input_text` text NOT NULL,
  `task_status` varchar(16) NOT NULL,
  `current_step` int NOT NULL,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `error_message` text,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_task_conv_status` (`conversation_id`,`task_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `analysis_tasks`
--

LOCK TABLES `analysis_tasks` WRITE;
/*!40000 ALTER TABLE `analysis_tasks` DISABLE KEYS */;
/*!40000 ALTER TABLE `analysis_tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `attachments`
--

DROP TABLE IF EXISTS `attachments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `attachments` (
  `id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `message_id` varchar(32) DEFAULT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_path` varchar(512) NOT NULL,
  `file_type` varchar(32) NOT NULL,
  `file_size` bigint NOT NULL,
  `parse_status` varchar(16) NOT NULL,
  `parse_result_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_att_conv` (`conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `attachments`
--

LOCK TABLES `attachments` WRITE;
/*!40000 ALTER TABLE `attachments` DISABLE KEYS */;
/*!40000 ALTER TABLE `attachments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `audit_logs`
--

DROP TABLE IF EXISTS `audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_logs` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `action_type` varchar(32) NOT NULL,
  `target_type` varchar(32) NOT NULL,
  `target_id` varchar(64) DEFAULT NULL,
  `before_value` json DEFAULT NULL,
  `after_value` json DEFAULT NULL,
  `ip` varchar(64) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_audit_target` (`target_type`,`target_id`),
  KEY `ix_audit_user_created` (`user_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_logs`
--

LOCK TABLES `audit_logs` WRITE;
/*!40000 ALTER TABLE `audit_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `audit_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_auth_codes`
--

DROP TABLE IF EXISTS `auth_auth_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_auth_codes` (
  `id` varchar(32) NOT NULL,
  `code` varchar(64) NOT NULL,
  `client_id` varchar(64) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `redirect_uri` varchar(512) NOT NULL,
  `scope` json NOT NULL,
  `expires_at` datetime NOT NULL,
  `consumed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_auth_codes`
--

LOCK TABLES `auth_auth_codes` WRITE;
/*!40000 ALTER TABLE `auth_auth_codes` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_auth_codes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_clients`
--

DROP TABLE IF EXISTS `auth_clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_clients` (
  `id` varchar(32) NOT NULL,
  `client_id` varchar(64) NOT NULL,
  `client_secret_hash` varchar(255) NOT NULL,
  `redirect_uris` json NOT NULL,
  `scopes` json NOT NULL,
  `status` varchar(16) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_clients`
--

LOCK TABLES `auth_clients` WRITE;
/*!40000 ALTER TABLE `auth_clients` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_clients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_refresh_tokens`
--

DROP TABLE IF EXISTS `auth_refresh_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_refresh_tokens` (
  `id` varchar(32) NOT NULL,
  `token_hash` varchar(128) NOT NULL,
  `client_id` varchar(64) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `expires_at` datetime NOT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `ix_refresh_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_refresh_tokens`
--

LOCK TABLES `auth_refresh_tokens` WRITE;
/*!40000 ALTER TABLE `auth_refresh_tokens` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_refresh_tokens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_users`
--

DROP TABLE IF EXISTS `auth_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_users` (
  `id` varchar(32) NOT NULL,
  `username` varchar(64) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `must_change_password` tinyint(1) NOT NULL,
  `display_name` varchar(64) NOT NULL,
  `role` varchar(16) NOT NULL,
  `status` varchar(16) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_users`
--

LOCK TABLES `auth_users` WRITE;
/*!40000 ALTER TABLE `auth_users` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `context_summaries`
--

DROP TABLE IF EXISTS `context_summaries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `context_summaries` (
  `id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `start_seq_no` int NOT NULL,
  `end_seq_no` int NOT NULL,
  `summary_text` text NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_ctx_conv_end` (`conversation_id`,`end_seq_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `context_summaries`
--

LOCK TABLES `context_summaries` WRITE;
/*!40000 ALTER TABLE `context_summaries` DISABLE KEYS */;
/*!40000 ALTER TABLE `context_summaries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `conversations`
--

DROP TABLE IF EXISTS `conversations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversations` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `data_source_id` varchar(32) DEFAULT NULL,
  `title` varchar(128) NOT NULL,
  `status` varchar(16) NOT NULL,
  `last_message_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_conv_user_msg` (`user_id`,`last_message_at`),
  KEY `ix_conv_ds` (`data_source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `conversations`
--

LOCK TABLES `conversations` WRITE;
/*!40000 ALTER TABLE `conversations` DISABLE KEYS */;
/*!40000 ALTER TABLE `conversations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_sources`
--

DROP TABLE IF EXISTS `data_sources`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_sources` (
  `id` varchar(32) NOT NULL,
  `name` varchar(64) NOT NULL,
  `db_type` varchar(16) NOT NULL,
  `host` varchar(128) NOT NULL,
  `port` int NOT NULL,
  `database` varchar(64) NOT NULL,
  `username` varchar(64) NOT NULL,
  `password_encrypted` varchar(512) NOT NULL,
  `is_readonly` tinyint(1) NOT NULL,
  `is_enabled` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_sources`
--

LOCK TABLES `data_sources` WRITE;
/*!40000 ALTER TABLE `data_sources` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_sources` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `llm_calls`
--

DROP TABLE IF EXISTS `llm_calls`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `llm_calls` (
  `id` varchar(32) NOT NULL,
  `task_id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `model` varchar(64) NOT NULL,
  `prompt_tokens` int NOT NULL,
  `completion_tokens` int NOT NULL,
  `total_tokens` int NOT NULL,
  `cost` decimal(10,4) NOT NULL,
  `latency_ms` int NOT NULL,
  `status` varchar(16) NOT NULL,
  `error_message` text,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_llm_task` (`task_id`),
  KEY `ix_llm_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `llm_calls`
--

LOCK TABLES `llm_calls` WRITE;
/*!40000 ALTER TABLE `llm_calls` DISABLE KEYS */;
/*!40000 ALTER TABLE `llm_calls` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `messages`
--

DROP TABLE IF EXISTS `messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `messages` (
  `id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `task_id` varchar(32) DEFAULT NULL,
  `role` varchar(16) NOT NULL,
  `message_type` varchar(16) NOT NULL,
  `content` text NOT NULL,
  `tool_name` varchar(64) DEFAULT NULL,
  `tool_status` varchar(16) DEFAULT NULL,
  `seq_no` int NOT NULL,
  `created_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_msg_conv_created` (`conversation_id`,`created_at`),
  KEY `ix_msg_task` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `messages`
--

LOCK TABLES `messages` WRITE;
/*!40000 ALTER TABLE `messages` DISABLE KEYS */;
/*!40000 ALTER TABLE `messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_configs`
--

DROP TABLE IF EXISTS `system_configs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_configs` (
  `id` varchar(32) NOT NULL,
  `config_key` varchar(64) NOT NULL,
  `config_value` text NOT NULL,
  `config_type` varchar(16) NOT NULL,
  `config_group` varchar(32) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_configs`
--

LOCK TABLES `system_configs` WRITE;
/*!40000 ALTER TABLE `system_configs` DISABLE KEYS */;
/*!40000 ALTER TABLE `system_configs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `task_logs`
--

DROP TABLE IF EXISTS `task_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `task_logs` (
  `id` varchar(32) NOT NULL,
  `task_id` varchar(32) NOT NULL,
  `log_level` varchar(8) NOT NULL,
  `log_type` varchar(32) NOT NULL,
  `log_content` text NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_log_task_created` (`task_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `task_logs`
--

LOCK TABLES `task_logs` WRITE;
/*!40000 ALTER TABLE `task_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `task_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` varchar(32) NOT NULL,
  `external_user_id` varchar(64) NOT NULL,
  `username` varchar(64) NOT NULL,
  `display_name` varchar(64) NOT NULL,
  `role` varchar(16) NOT NULL,
  `status` varchar(16) NOT NULL,
  `last_login_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `external_user_id` (`external_user_id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `websocket_tokens`
--

DROP TABLE IF EXISTS `websocket_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `websocket_tokens` (
  `id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `conversation_id` varchar(32) NOT NULL,
  `token` varchar(64) NOT NULL,
  `expires_at` datetime NOT NULL,
  `consumed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `websocket_tokens`
--

LOCK TABLES `websocket_tokens` WRITE;
/*!40000 ALTER TABLE `websocket_tokens` DISABLE KEYS */;
/*!40000 ALTER TABLE `websocket_tokens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Current Database: `scenario_goods`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `scenario_goods` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `scenario_goods`;

--
-- Table structure for table `creative_change_log`
--

DROP TABLE IF EXISTS `creative_change_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `creative_change_log` (
  `channel_id` varchar(16) DEFAULT NULL,
  `change_date` date DEFAULT NULL,
  `note` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `creative_change_log`
--

LOCK TABLES `creative_change_log` WRITE;
/*!40000 ALTER TABLE `creative_change_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `creative_change_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_brand`
--

DROP TABLE IF EXISTS `dim_brand`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_brand` (
  `brand_id` varchar(16) NOT NULL,
  `brand_name` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_brand`
--

LOCK TABLES `dim_brand` WRITE;
/*!40000 ALTER TABLE `dim_brand` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_brand` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_category`
--

DROP TABLE IF EXISTS `dim_category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_category` (
  `category_id` varchar(16) NOT NULL,
  `category_name` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_category`
--

LOCK TABLES `dim_category` WRITE;
/*!40000 ALTER TABLE `dim_category` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_category` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_channel`
--

DROP TABLE IF EXISTS `dim_channel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_channel` (
  `channel_id` varchar(16) NOT NULL,
  `channel_name` varchar(32) DEFAULT NULL,
  `channel_type` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`channel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_channel`
--

LOCK TABLES `dim_channel` WRITE;
/*!40000 ALTER TABLE `dim_channel` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_channel` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_channel_budget_daily`
--

DROP TABLE IF EXISTS `dim_channel_budget_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_channel_budget_daily` (
  `channel_id` varchar(16) NOT NULL,
  `d` date NOT NULL,
  `budget` float DEFAULT NULL,
  `cost` float DEFAULT NULL,
  `bid` float DEFAULT NULL,
  `note` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`channel_id`,`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_channel_budget_daily`
--

LOCK TABLES `dim_channel_budget_daily` WRITE;
/*!40000 ALTER TABLE `dim_channel_budget_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_channel_budget_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_creative`
--

DROP TABLE IF EXISTS `dim_creative`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_creative` (
  `creative_id` varchar(32) NOT NULL,
  `channel_id` varchar(16) DEFAULT NULL,
  `theme` varchar(32) DEFAULT NULL,
  `ab_group` varchar(16) DEFAULT NULL,
  `change_date` date DEFAULT NULL,
  `note` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`creative_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_creative`
--

LOCK TABLES `dim_creative` WRITE;
/*!40000 ALTER TABLE `dim_creative` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_creative` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_date`
--

DROP TABLE IF EXISTS `dim_date`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_date` (
  `d` date NOT NULL,
  `month` varchar(8) DEFAULT NULL,
  `is_promo` int DEFAULT NULL,
  PRIMARY KEY (`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_date`
--

LOCK TABLES `dim_date` WRITE;
/*!40000 ALTER TABLE `dim_date` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_date` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_sku`
--

DROP TABLE IF EXISTS `dim_sku`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_sku` (
  `sku_id` varchar(32) NOT NULL,
  `sku_name` varchar(64) DEFAULT NULL,
  `category` varchar(32) DEFAULT NULL,
  `brand` varchar(32) DEFAULT NULL,
  `status` varchar(16) DEFAULT NULL,
  `list_price` float DEFAULT NULL,
  PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_sku`
--

LOCK TABLES `dim_sku` WRITE;
/*!40000 ALTER TABLE `dim_sku` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_sku` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_sku_ctr_baseline`
--

DROP TABLE IF EXISTS `dim_sku_ctr_baseline`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_sku_ctr_baseline` (
  `sku_id` varchar(32) NOT NULL,
  `window_start` date DEFAULT NULL,
  `window_end` date DEFAULT NULL,
  `avg_ctr` float DEFAULT NULL,
  `median_ctr` float DEFAULT NULL,
  `p10_ctr` float DEFAULT NULL,
  `p90_ctr` float DEFAULT NULL,
  `sample_days` int DEFAULT NULL,
  PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_sku_ctr_baseline`
--

LOCK TABLES `dim_sku_ctr_baseline` WRITE;
/*!40000 ALTER TABLE `dim_sku_ctr_baseline` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_sku_ctr_baseline` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fact_channel_daily`
--

DROP TABLE IF EXISTS `fact_channel_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact_channel_daily` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_id` varchar(16) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `exposure` int DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `conversions` int DEFAULT NULL,
  `gmv` float DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=601 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fact_channel_daily`
--

LOCK TABLES `fact_channel_daily` WRITE;
/*!40000 ALTER TABLE `fact_channel_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `fact_channel_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fact_creative_daily`
--

DROP TABLE IF EXISTS `fact_creative_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact_creative_daily` (
  `id` int NOT NULL AUTO_INCREMENT,
  `creative_id` varchar(32) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `exposure` int DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `ctr` float DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5025 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fact_creative_daily`
--

LOCK TABLES `fact_creative_daily` WRITE;
/*!40000 ALTER TABLE `fact_creative_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `fact_creative_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fact_sku_daily`
--

DROP TABLE IF EXISTS `fact_sku_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact_sku_daily` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sku_id` varchar(32) DEFAULT NULL,
  `channel_id` varchar(16) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `exposure` int DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `conversions` int DEFAULT NULL,
  `gmv` float DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=119371 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fact_sku_daily`
--

LOCK TABLES `fact_sku_daily` WRITE;
/*!40000 ALTER TABLE `fact_sku_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `fact_sku_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `promotion_calendar`
--

DROP TABLE IF EXISTS `promotion_calendar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `promotion_calendar` (
  `d` date NOT NULL,
  `name` varchar(64) DEFAULT NULL,
  `discount` float DEFAULT NULL,
  PRIMARY KEY (`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `promotion_calendar`
--

LOCK TABLES `promotion_calendar` WRITE;
/*!40000 ALTER TABLE `promotion_calendar` DISABLE KEYS */;
/*!40000 ALTER TABLE `promotion_calendar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sku_offline_log`
--

DROP TABLE IF EXISTS `sku_offline_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sku_offline_log` (
  `sku_id` varchar(32) DEFAULT NULL,
  `offline_date` date DEFAULT NULL,
  `reason` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sku_offline_log`
--

LOCK TABLES `sku_offline_log` WRITE;
/*!40000 ALTER TABLE `sku_offline_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `sku_offline_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Current Database: `scenario_inventory`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `scenario_inventory` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `scenario_inventory`;

--
-- Table structure for table `dim_date`
--

DROP TABLE IF EXISTS `dim_date`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_date` (
  `d` date NOT NULL,
  `month` varchar(8) DEFAULT NULL,
  PRIMARY KEY (`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_date`
--

LOCK TABLES `dim_date` WRITE;
/*!40000 ALTER TABLE `dim_date` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_date` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_sku`
--

DROP TABLE IF EXISTS `dim_sku`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_sku` (
  `sku_id` varchar(32) NOT NULL,
  `sku_name` varchar(64) DEFAULT NULL,
  `category` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_sku`
--

LOCK TABLES `dim_sku` WRITE;
/*!40000 ALTER TABLE `dim_sku` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_sku` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_sku_safety`
--

DROP TABLE IF EXISTS `dim_sku_safety`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_sku_safety` (
  `sku_id` varchar(32) NOT NULL,
  `wh_id` varchar(16) NOT NULL,
  `safety_stock` int DEFAULT NULL,
  `reorder_point` int DEFAULT NULL,
  `lead_time_days` int DEFAULT NULL,
  `avg_daily_sales` float DEFAULT NULL,
  `note` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`sku_id`,`wh_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_sku_safety`
--

LOCK TABLES `dim_sku_safety` WRITE;
/*!40000 ALTER TABLE `dim_sku_safety` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_sku_safety` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_warehouse`
--

DROP TABLE IF EXISTS `dim_warehouse`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_warehouse` (
  `wh_id` varchar(16) NOT NULL,
  `wh_name` varchar(32) DEFAULT NULL,
  `region` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`wh_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_warehouse`
--

LOCK TABLES `dim_warehouse` WRITE;
/*!40000 ALTER TABLE `dim_warehouse` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_warehouse` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dim_warehouse_transfer`
--

DROP TABLE IF EXISTS `dim_warehouse_transfer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dim_warehouse_transfer` (
  `transfer_id` varchar(32) NOT NULL,
  `sku_id` varchar(32) DEFAULT NULL,
  `from_wh` varchar(16) DEFAULT NULL,
  `to_wh` varchar(16) DEFAULT NULL,
  `qty` int DEFAULT NULL,
  `transfer_date` date DEFAULT NULL,
  `status` varchar(16) DEFAULT NULL,
  `reason` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`transfer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dim_warehouse_transfer`
--

LOCK TABLES `dim_warehouse_transfer` WRITE;
/*!40000 ALTER TABLE `dim_warehouse_transfer` DISABLE KEYS */;
/*!40000 ALTER TABLE `dim_warehouse_transfer` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fact_inventory_daily`
--

DROP TABLE IF EXISTS `fact_inventory_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact_inventory_daily` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sku_id` varchar(32) DEFAULT NULL,
  `wh_id` varchar(16) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `stock_qty` int DEFAULT NULL,
  `inbound` int DEFAULT NULL,
  `outbound` int DEFAULT NULL,
  `turnover_days` float DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=30001 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fact_inventory_daily`
--

LOCK TABLES `fact_inventory_daily` WRITE;
/*!40000 ALTER TABLE `fact_inventory_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `fact_inventory_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fact_supplier_leadtime_daily`
--

DROP TABLE IF EXISTS `fact_supplier_leadtime_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact_supplier_leadtime_daily` (
  `supplier_id` varchar(16) NOT NULL,
  `d` date NOT NULL,
  `lead_time_days` float DEFAULT NULL,
  `on_time_rate` float DEFAULT NULL,
  `lead_7d_avg` float DEFAULT NULL,
  `lead_30d_avg` float DEFAULT NULL,
  `note` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`supplier_id`,`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fact_supplier_leadtime_daily`
--

LOCK TABLES `fact_supplier_leadtime_daily` WRITE;
/*!40000 ALTER TABLE `fact_supplier_leadtime_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `fact_supplier_leadtime_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `purchase_order`
--

DROP TABLE IF EXISTS `purchase_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchase_order` (
  `po_id` varchar(32) NOT NULL,
  `sku_id` varchar(32) DEFAULT NULL,
  `wh_id` varchar(16) DEFAULT NULL,
  `order_date` date DEFAULT NULL,
  `qty` int DEFAULT NULL,
  `eta` date DEFAULT NULL,
  PRIMARY KEY (`po_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `purchase_order`
--

LOCK TABLES `purchase_order` WRITE;
/*!40000 ALTER TABLE `purchase_order` DISABLE KEYS */;
/*!40000 ALTER TABLE `purchase_order` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sales_daily`
--

DROP TABLE IF EXISTS `sales_daily`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sales_daily` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sku_id` varchar(32) DEFAULT NULL,
  `wh_id` varchar(16) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `sales_qty` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=30001 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sales_daily`
--

LOCK TABLES `sales_daily` WRITE;
/*!40000 ALTER TABLE `sales_daily` DISABLE KEYS */;
/*!40000 ALTER TABLE `sales_daily` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sales_forecast`
--

DROP TABLE IF EXISTS `sales_forecast`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sales_forecast` (
  `sku_id` varchar(32) NOT NULL,
  `wh_id` varchar(16) NOT NULL,
  `d` date NOT NULL,
  `forecast_qty` int NOT NULL COMMENT '预测销量',
  `dow` int NOT NULL COMMENT '周几 0=周一',
  `is_actual` int NOT NULL COMMENT '0=预测 1=已发生',
  `source_note` varchar(64) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`sku_id`,`wh_id`,`d`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sales_forecast`
--

LOCK TABLES `sales_forecast` WRITE;
/*!40000 ALTER TABLE `sales_forecast` DISABLE KEYS */;
/*!40000 ALTER TABLE `sales_forecast` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stock_anomaly_log`
--

DROP TABLE IF EXISTS `stock_anomaly_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stock_anomaly_log` (
  `sku_id` varchar(32) DEFAULT NULL,
  `wh_id` varchar(16) DEFAULT NULL,
  `d` date DEFAULT NULL,
  `anomaly_type` varchar(32) DEFAULT NULL,
  `detail` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stock_anomaly_log`
--

LOCK TABLES `stock_anomaly_log` WRITE;
/*!40000 ALTER TABLE `stock_anomaly_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `stock_anomaly_log` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-19 11:59:13

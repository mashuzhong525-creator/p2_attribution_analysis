-- 经营归因分析系统 · MySQL 初始化（首次建卷时执行）
-- 预建两个场景示例库并授予 bia 用户（bia 仅对业务库+场景库有权限）
CREATE DATABASE IF NOT EXISTS scenario_goods CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS scenario_inventory CHARACTER SET utf8mb4;
GRANT ALL PRIVILEGES ON scenario_goods.* TO 'bia'@'%';
GRANT ALL PRIVILEGES ON scenario_inventory.* TO 'bia'@'%';
GRANT CREATE ON *.* TO 'bia'@'%';
FLUSH PRIVILEGES;

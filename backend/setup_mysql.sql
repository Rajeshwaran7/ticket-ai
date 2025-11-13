-- MySQL Database Setup Script for Ticket AI System
-- Run this script to create the database and user

-- Create database
CREATE DATABASE IF NOT EXISTS ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (optional - you can use root or existing user)
-- Replace 'your_password' with a secure password
-- CREATE USER IF NOT EXISTS 'ticket_user'@'localhost' IDENTIFIED BY 'your_password';

-- Grant privileges
-- GRANT ALL PRIVILEGES ON ticket_ai.* TO 'ticket_user'@'localhost';
-- FLUSH PRIVILEGES;

-- Use the database
USE ticket_ai;

-- Tables will be created automatically by SQLAlchemy
-- This script just ensures the database exists

-- Show database info
SELECT 'Database ticket_ai created successfully!' AS status;
SHOW DATABASES LIKE 'ticket_ai';


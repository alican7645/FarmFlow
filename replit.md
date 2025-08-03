# Overview

A Turkish greenhouse management system built with Flask and SQLite that helps farmers and greenhouse operators manage production, inventory, and labor operations. The system provides a comprehensive dashboard for tracking planting schedules, harvest times, stock levels, worker hours, and generates reports for operational analysis.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask for server-side rendering
- **UI Framework**: Bootstrap 5 with dark theme for responsive design
- **Styling**: Custom CSS for enhanced card components, navigation, and progress bars
- **Icons**: Font Awesome 6.0 for consistent iconography
- **Language**: Turkish language interface for local market

## Backend Architecture
- **Web Framework**: Flask with route-based architecture and authentication
- **Database Systems**: Dual database setup - SQLite3 for operational data, PostgreSQL for user management
- **ORM**: SQLAlchemy for PostgreSQL user management, direct SQLite3 queries for business data
- **Authentication**: Flask-Login with secure password hashing and session management
- **Session Management**: Flask sessions with PostgreSQL-backed user storage
- **Error Handling**: Enhanced logging configuration with DEBUG level
- **File Structure**: Modular structure with separate models.py for user management

## Data Storage Solutions
- **Operational Database**: SQLite3 file-based database (sera.db) for business operations
- **User Database**: PostgreSQL for user authentication and management
- **SQLite Schema**: Six main tables:
  - `uretim` (production): Tracks greenhouse plantings, harvests, and yields
  - `hasat` (harvest): Records detailed harvest operations with plot/field, quantities, personnel, and delivery information
  - `stok` (inventory): Manages material stock levels with minimum thresholds
  - `personel` (personnel): Employee information and monthly salary tracking
  - `devam` (attendance): Daily attendance tracking for all personnel
  - `gorevler` (tasks): Task assignments and completion tracking
- **PostgreSQL Schema**: User management tables:
  - `users`: User accounts with roles and authentication data
  - `login_attempts`: Security logging for login attempts
- **Data Persistence**: Hybrid approach combining file-based and cloud database storage

## Core Features
- **Production Management**: Track planting dates, harvest schedules, greenhouse assignments, and yield calculations
- **Harvest Management**: Record detailed harvest operations including dates, plot/field locations, quantities, responsible personnel, and delivery destinations
- **Inventory Control**: Monitor stock levels with low-stock alerts and material categorization
- **Personnel Management**: Monthly salary-based employee tracking with position management
- **Attendance Tracking**: Daily attendance monitoring with status tracking (present/absent/leave/sick)
- **Task Management**: Assignment and tracking of daily tasks for personnel
- **User Management**: Admin control panel for creating and managing user accounts
- **Security Features**: Login attempt monitoring, role-based access control, secure authentication
- **Dashboard Analytics**: Summary statistics and operational overview including personnel costs
- **Reporting System**: Monthly production reports and Excel export for attendance data

## Authentication and Authorization
- **Authentication System**: Flask-Login with PostgreSQL user management
- **User Management**: Admin control panel for creating and managing user accounts
- **Role-Based Access**: Admin and regular user roles with different permissions
- **Session Security**: Secure session handling with PostgreSQL-backed user storage
- **Login Tracking**: Failed login attempt monitoring and user activity logging
- **Default Admin**: System creates default admin user (admin/admin123) on first startup

# External Dependencies

## Core Dependencies
- **Flask**: Web framework for routing and template rendering
- **Flask-Login**: User session management and authentication
- **Flask-SQLAlchemy**: PostgreSQL ORM for user management
- **SQLite3**: Built-in Python database for operational data persistence
- **PostgreSQL**: Cloud database for user authentication and security
- **Werkzeug**: Password hashing and security utilities
- **openpyxl**: Excel file generation for attendance reports
- **Jinja2**: Template engine (included with Flask)

## Frontend Dependencies
- **Bootstrap 5**: CSS framework via CDN (bootstrap-agent-dark-theme.min.css)
- **Font Awesome 6.0**: Icon library via CDN
- **Custom CSS**: Local stylesheet for application-specific styling

## Infrastructure Requirements
- **Python 3.x**: Runtime environment
- **File System**: Local storage for SQLite database file
- **Environment Variables**: Optional SESSION_SECRET for session security
- **Static File Serving**: Flask built-in static file handler

## External Integrations
- **CDN Services**: Bootstrap and Font Awesome served from external CDNs
- **No Third-party APIs**: Self-contained system with no external service dependencies
- **No Cloud Services**: Designed for local deployment and operation
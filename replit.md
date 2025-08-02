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
- **Web Framework**: Flask with simple route-based architecture
- **Database ORM**: Direct SQLite3 queries (no ORM abstraction)
- **Session Management**: Flask sessions with configurable secret key
- **Error Handling**: Basic logging configuration with DEBUG level
- **File Structure**: Single-file application (app.py) with separate templates and static assets

## Data Storage Solutions
- **Primary Database**: SQLite3 file-based database (sera.db)
- **Database Schema**: Four main tables:
  - `uretim` (production): Tracks greenhouse plantings, harvests, and yields
  - `hasat` (harvest): Records detailed harvest operations with plot/field, quantities, personnel, and delivery information
  - `stok` (inventory): Manages material stock levels with minimum thresholds
  - `iscilik` (labor): Records worker hours, tasks, and wages
- **Data Persistence**: File-based storage suitable for small to medium operations

## Core Features
- **Production Management**: Track planting dates, harvest schedules, greenhouse assignments, and yield calculations
- **Harvest Management**: Record detailed harvest operations including dates, plot/field locations, quantities, responsible personnel, and delivery destinations
- **Inventory Control**: Monitor stock levels with low-stock alerts and material categorization
- **Labor Tracking**: Record worker hours, calculate wages, and track task assignments
- **Dashboard Analytics**: Summary statistics and operational overview including harvest metrics
- **Reporting System**: Monthly production reports with success rates and yield analysis

## Authentication and Authorization
- **Current State**: No authentication system implemented
- **Session Security**: Basic Flask session handling with secret key configuration
- **Access Control**: Open access to all features (suitable for single-user or trusted environment)

# External Dependencies

## Core Dependencies
- **Flask**: Web framework for routing and template rendering
- **SQLite3**: Built-in Python database for data persistence
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
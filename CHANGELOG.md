# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-03-11

### Added
- **`on_change` callback for file inputs**: Added `on_change` parameter to `file_input()` method, allowing callbacks when files are selected

### Fixed
- **Type hints for `file_input`**: Fixed mypy overload errors in `RouteLitBuilder.file_input()` method by adding missing `accept` and `on_change` parameters to overload signatures

### Changed
- **Documentation formatting**: Improved code example indentation in docstrings for `RouteLit` class methods (`ui` property, `response()`, `fragment()`)
- **Project description**: Updated README to describe routelit as a "library" instead of "framework" for accuracy

## [0.6.0] - 2025-12-11

### Added
- **Caching functionality**: New `cache_data` decorator to cache function results based on input parameters, supporting both synchronous and asynchronous functions
- **File input functionality**: Added `_x_file_input` method to handle file uploads in RouteLitBuilder, supporting both single and multiple file inputs with proper type overloads
- **Flask integration documentation**: Quick start guide for using RouteLit with Flask, including example code and setup instructions
- **Multipart request support**: Enhanced `RouteLitRequest` with `is_multipart` and `get_files` methods for handling file uploads

### Changed
- **Importmap script handling**: Refactored index.html to include importmap script unconditionally, improving consistency between production and development environments
- **Installation instructions**: Enhanced documentation with alternative installation command for adding RouteLit

### Technical Improvements
- Added comprehensive tests for caching mechanism and file input functionality
- Improved session state persistence for file inputs
- Enhanced parameter exclusion logic in caching (excluding parameters starting with underscore)

### Developer Experience
- Better type hints and overloads for file input methods
- More flexible caching backend integration in RouteLit class

## [0.5.9] - Previous Release

[Initial release or previous version details would go here]

---

**Contributors**: Rolando Gómez Tabar

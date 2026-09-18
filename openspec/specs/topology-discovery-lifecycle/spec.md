# topology-discovery-lifecycle Specification

## Purpose
Manages the background discovery worker lifecycle to guarantee that consecutive discovery runs and application shutdowns execute cleanly without crashing due to references to deleted Qt C++ objects.

## Requirements

### Requirement: Consecutive network discoveries
The system SHALL allow users to execute multiple consecutive network discoveries without crashing or referencing deleted background worker objects.

#### Scenario: Discovery after previous discovery succeeded
- **WHEN** the user initiates a network discovery after a previous discovery has completed and populated the map
- **THEN** the system clears previous worker references and starts the new discovery without raising a RuntimeError

#### Scenario: Discovery after previous discovery failed
- **WHEN** the user initiates a network discovery after a previous discovery failed with an error
- **THEN** the system resets the worker state and allows starting a new discovery run cleanly

### Requirement: Safe topology tab shutdown
The system SHALL ensure that shutting down the topology view or application releases worker resources cleanly without invoking methods on deleted C++ worker objects.

#### Scenario: Shutdown after discovery completion
- **WHEN** the application or topology view is closed after a discovery run has finished
- **THEN** the system ignores or cleans up dead worker references and completes shutdown without error

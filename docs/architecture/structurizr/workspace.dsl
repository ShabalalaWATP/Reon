workspace "Mist Service" "Current executable architecture for the synthetic service-request application" {
    model {
        customer = person "Customer" "Submits requests, joins request conversations, receives products and accepts delivery."
        staff = person "Authorised staff member" "Routes demand, produces work, reviews packages or releases products in Staff context."
        administrator = person "Platform administrator" "Maintains identity and configuration metadata without request-content authority."
        operator = person "Runtime operator" "Deploys, observes, backs up and restores the service."

        mist = softwareSystem "Mist Service" "Human-led request, delivery and dissemination workspace." {
            web = container "Web application" "Context-aware forms, dashboards, queues, conversations and workspaces." "React 19, TypeScript 5.9, Vite 7, Nginx" {
                shell = component "Application shell and routes" "Builds Customer or Staff navigation and enforces route presentation." "React Router 8"
                features = component "Feature modules" "Requests, routing, tracking, delivery boards, packages, calendars, organisation and administration." "React 19"
                auth = component "Authentication and context client" "Owns session refresh, CSRF, CUSTOMER/STAFF switching and context-scoped cache rotation." "TypeScript"
                query = component "Typed API and server state" "Calls the same-origin API and bounds, keys and invalidates protected data." "TanStack Query 5, Zod 4"

                shell -> features "Presents authorised feature routes"
                features -> query "Loads and mutates bounded resources"
                auth -> query "Scopes protected requests by identity context and session generation"
            }

            api = container "Application API" "Authenticates, validates, authorises and records every application action." "Python 3.12+, FastAPI, Pydantic 2" {
                http = component "HTTP adapters" "Thin routers and validated request/response schemas." "FastAPI, Pydantic"
                application = component "Application services" "Coordinates request, conversation, work, product, configuration and administration use cases." "Python"
                domain = component "Domain policies" "Framework-free object, action, workflow and separation-of-duty decisions." "Python"
                ports = component "Focused application ports and records" "Narrow persistence, workflow, storage, scanning and audit contracts." "Protocols and immutable records"
                composition = component "Composition roots" "Wires SQLAlchemy repositories and external adapters per capability." "FastAPI dependencies"
                repositories = component "PostgreSQL adapters" "Owns parameterised SQLAlchemy persistence and bounded projections." "SQLAlchemy 2 async"
                workflowAdapter = component "Camunda adapter" "Uses the supported V2 API for definitions, process state and human tasks." "Camunda SDK 9"
                productAdapters = component "Product adapters" "Quarantines, scans, promotes and streams managed files; validates approved links." "Private filesystem, ClamAV"

                http -> application "Invokes use cases"
                application -> domain "Requests policy decisions"
                application -> ports "Depends on contracts"
                composition -> application "Constructs services"
                composition -> repositories "Constructs repositories"
                composition -> workflowAdapter "Constructs workflow client"
                composition -> productAdapters "Constructs product boundary"
                repositories -> ports "Implements persistence contracts"
                workflowAdapter -> ports "Implements workflow contracts"
                productAdapters -> ports "Implements product contracts"
            }

            worker = container "Fenced worker" "Dispatches durable workflow commands and reconciles bounded projections." "Python 3.12+, Camunda SDK"
            database = container "Application database" "Identity contexts, requests, conversations, route history, packages, audit, outbox and projections." "PostgreSQL 17, pgvector 0.8" "Database"
            storage = container "Private product storage" "Quarantines and stores clean managed product objects for synthetic evaluation." "Docker named volume" "File System"
            scanner = container "Malware scanner" "Scans complete quarantined objects before promotion." "ClamAV 1.5" "Container"

            web -> api "Uses same-origin JSON API" "HTTPS target, HTTP loopback locally"
            api -> database "Reads and writes application records" "SQLAlchemy/asyncpg"
            worker -> database "Claims leased work and reconciles projections" "SQLAlchemy/asyncpg"
            api -> storage "Quarantines, promotes and streams product files"
            api -> scanner "Scans complete quarantined objects" "INSTREAM"
        }

        camunda = softwareSystem "Camunda 8.9" "Owns BPMN process position and human user-task lifecycle."
        camundaDatabase = softwareSystem "Camunda database" "Camunda-owned storage, never read by Mist application code."

        customer -> web "Uses in Customer context"
        staff -> web "Uses in Staff context"
        administrator -> web "Uses metadata administration"
        operator -> api "Observes content-free health and readiness"
        api -> camunda "Queries supported workflow state" "V2 API"
        worker -> camunda "Starts processes and completes human tasks" "V2 API"
        camunda -> camundaDatabase "Owns"

        deploymentEnvironment "Local synthetic evaluation" {
            deploymentNode "Developer workstation" "Windows 11, macOS or Linux host" "Docker Compose" {
                deploymentNode "Application containers" "Loopback-published containers" "Docker" {
                    containerInstance web
                    containerInstance api
                    containerInstance worker
                    containerInstance scanner
                    softwareSystemInstance camunda
                }
                deploymentNode "Stateful containers and volumes" "Private local dependencies" "Docker" {
                    containerInstance database
                    containerInstance storage
                    softwareSystemInstance camundaDatabase
                }
            }
        }

        deploymentEnvironment "Private cloud synthetic evaluation" {
            deploymentNode "Private Linux VM" "No public application listener" "EC2 or Compute Engine" {
                deploymentNode "Docker Compose" "Unchanged synthetic topology" {
                    containerInstance web
                    containerInstance api
                    containerInstance worker
                    containerInstance database
                    containerInstance storage
                    containerInstance scanner
                    softwareSystemInstance camunda
                    softwareSystemInstance camundaDatabase
                }
            }
        }
    }

    views {
        systemContext mist "SystemContext" {
            include *
            autolayout lr
            title "Mist Service system context"
            description "People and systems around the current service."
        }

        container mist "Containers" {
            include *
            autolayout lr
            title "Mist Service containers"
            description "Executable containers and their supported interfaces."
        }

        component web "WebComponents" {
            include *
            autolayout lr
            title "Web application components"
            description "Context-aware presentation, feature and server-state boundaries."
        }

        component api "ApiComponents" {
            include *
            autolayout lr
            title "Application API components"
            description "Thin HTTP adapters around services, policies, focused ports and adapters."
        }

        dynamic mist "RequestDelivery" "Customer request to accepted product" {
            customer -> web "Submits a validated request"
            web -> api "Creates immutable submission"
            api -> database "Commits request, audit and process-start intent"
            worker -> camunda "Starts process and advances claimed human tasks"
            staff -> web "Routes, produces, reviews and releases"
            api -> storage "Promotes only clean managed files"
            customer -> web "Receives and accepts the disseminated package"
            autolayout lr
            title "End-to-end request delivery"
        }

        deployment * "Local synthetic evaluation" "LocalDeployment" {
            include *
            autolayout lr
            title "Local synthetic evaluation deployment"
            description "The executable Docker Compose topology on Windows, macOS or Linux."
        }

        deployment * "Private cloud synthetic evaluation" "PrivateCloudDeployment" {
            include *
            autolayout lr
            title "Private cloud synthetic evaluation deployment"
            description "The unchanged Compose topology on one private Linux VM behind an operator tunnel."
        }

        styles {
            element "Person" {
                shape Person
                background "#0f1b24"
                color "#f4f8fb"
                stroke "#36c7ff"
            }
            element "Software System" {
                background "#102a3b"
                color "#f4f8fb"
                stroke "#36c7ff"
            }
            element "Container" {
                background "#101e28"
                color "#f4f8fb"
                stroke "#36718d"
            }
            element "Component" {
                background "#15222b"
                color "#f4f8fb"
                stroke "#7aa8be"
            }
            element "Database" {
                shape Cylinder
                background "#14261f"
                color "#f4f8fb"
                stroke "#43c98b"
            }
            element "File System" {
                shape Folder
                background "#201c17"
                color "#f4f8fb"
                stroke "#d5a449"
            }
            relationship "Relationship" {
                color "#6bbbdc"
                thickness 2
            }
        }

        theme default
    }
}

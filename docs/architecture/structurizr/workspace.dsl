workspace "Mist Service" "Current executable architecture for the synthetic, human-led service-request application" {
    model {
        customer = person "Customer" "Submits requests, joins conversations, receives released products and accepts delivery."
        operationalUser = person "Authorised operational user" "Routes, assigns, produces, reviews or disseminates in Staff context."
        jiocUser = person "JIOC Routing User" "Reviews intake and selects one direct command route."
        coordinationUser = person "Request Coordination User" "Coordinates a selected command and selects one direct Ops route."
        opsUser = person "Ops Routing User" "Routes a request from the selected Ops group to one direct delivery team."
        teamManager = person "Team Manager" "Assigns Analysts, plans exact-team work and reviews the submitted product."
        teamAnalyst = person "Team Analyst" "Produces the product as Lead or Contributor and may ask the Customer for information."
        qcUser = person "QC User" "Performs an independent product review and may return changes."
        qcManager = person "QC Manager" "Performs independent review or disseminates a product reviewed by somebody else."
        administrator = person "Platform Administrator" "Maintains identities and safe configuration metadata without implicit request-content access."
        operator = person "Runtime operator" "Deploys, observes, backs up, restores and runs bounded maintenance commands."

        mist = softwareSystem "Mist Service" "Human-led request, delivery and dissemination workspace." {
            web = container "Web application" "Serves the React application, applies browser headers and proxies same-origin API calls." "React 19, TypeScript 5.9, Vite 7, Nginx" "Application" {
                shell = component "Application shell and route policy" "Builds Customer or Staff navigation and gates route presentation." "React Router 8"
                webFeatures = component "Feature modules" "Requests, routing, tracking, actions, workspaces, planning, products, analytics and administration." "React 19"
                webAuth = component "Authentication and context state" "Owns session refresh, CSRF, context switching and session-generation changes." "TypeScript"
                apiState = component "Typed API and server state" "Calls FastAPI only and validates, scopes, keys and invalidates protected data." "TanStack Query 5, Zod 4"

                shell -> webFeatures "Presents permitted feature routes"
                webFeatures -> apiState "Loads and mutates bounded resources"
                webAuth -> apiState "Scopes requests and cache generations"
            }

            api = container "Application API" "Authenticates, validates, authorises and records application actions through capability composition roots." "Python 3.12+, FastAPI, Pydantic 2" "Application" {
                http = component "HTTP composition" "Middleware, bounded errors, feature flags, routers and validated schemas." "FastAPI, Pydantic"
                capabilityComposition = component "Capability composition roots" "Constructs focused services for request, work, product, board, calendar, configuration, analytics, administration and security capabilities." "FastAPI dependencies"
                applicationServices = component "Application services" "Coordinates use cases and explicit transaction boundaries." "Python"
                domainPolicies = component "Domain policies" "Framework-free role, scope, route, assignment, transition and separation-of-duty decisions." "Python"
                applicationPorts = component "Focused ports and immutable records" "Small persistence, workflow, product, audit, clock and identity contracts." "Python Protocols"
                persistenceAdapters = component "SQLAlchemy adapters" "Implements bounded commands, queries and projections with object-level filtering." "SQLAlchemy 2 async"
                workflowAdapter = component "Camunda V2 adapter" "Queries supported process and user-task state without reading Camunda storage." "Camunda Python SDK 9"
                productBoundary = component "Managed product boundary" "Quarantines, validates, scans, promotes and streams files, and validates approved links." "Private storage adapter, ClamAV client"
                analyticsBoundary = component "Analytics projections" "Writes request, stage, capacity and operational facts with versioned definitions and grant-scoped reads." "SQLAlchemy projections"
                securityBoundary = component "Security and audit boundary" "Applies session, CSRF, pseudonymisation, security-event and tamper-evident audit controls." "Python"

                http -> capabilityComposition "Resolves capability dependencies"
                capabilityComposition -> applicationServices "Constructs use cases with narrow collaborators"
                applicationServices -> domainPolicies "Requests decisions"
                applicationServices -> applicationPorts "Depends on contracts"
                capabilityComposition -> persistenceAdapters "Wires repository adapters"
                capabilityComposition -> workflowAdapter "Wires the supported workflow client"
                capabilityComposition -> productBoundary "Wires one shared product runtime"
                persistenceAdapters -> applicationPorts "Implements"
                workflowAdapter -> applicationPorts "Implements"
                productBoundary -> applicationPorts "Implements"
                applicationServices -> analyticsBoundary "Projects authorised facts"
                http -> securityBoundary "Records bounded denials and telemetry"
            }

            worker = container "Fenced maintenance worker" "Claims named PostgreSQL leases, dispatches durable workflow work and reconciles failure-isolated projections." "Python 3.12+, Camunda SDK" "Application,Worker" {
                leaseLoop = component "Lease and heartbeat loop" "Fences each named job, renews ownership and records content-free readiness." "Python, PostgreSQL leases"
                workflowJobs = component "Workflow jobs" "Starts processes, dispatches task commands and cancellations, and reconciles supported Camunda state." "Python"
                projectionJobs = component "Projection jobs" "Reconciles notifications, membership and route-scoped request-search embeddings." "Python, FastEmbed"
                backgroundSecurity = component "Security and product jobs" "Processes pseudonymised password-assistance work and cleans expired quarantined uploads." "Python"

                leaseLoop -> workflowJobs "Runs with a named fence"
                leaseLoop -> projectionJobs "Runs with a named fence"
                leaseLoop -> backgroundSecurity "Runs with a named fence"
            }

            maintenance = container "Operator maintenance commands" "Runs retention, legal hold, restore checks, operational snapshots, audit attestation and bounded analytics rebuild or replay." "Python 3.12+ CLI" "Application,Maintenance"
            migrator = container "Schema migrator" "Applies the Alembic head and least-privilege PostgreSQL grants before API and worker startup." "Alembic, Python" "Application,Maintenance"
            database = container "Application database" "Authoritative application records, audit history, durable intents, configuration pins, analytics facts and requester-facing projections." "PostgreSQL 17, pgvector 0.8" "Database,ApplicationData"
            storage = container "Private product storage" "Local-only quarantine and clean product objects plus the adapter's recovery index." "Private Docker volume" "File System,ProductData"

            webApi = web -> api "Uses the same-origin JSON API" "HTTPS target; HTTP loopback locally"
            apiDatabase = api -> database "Reads and writes authoritative application records" "SQLAlchemy/asyncpg"
            workerDatabase = worker -> database "Claims leases, reads durable intents and reconciles projections" "SQLAlchemy/asyncpg"
            maintenance -> database "Runs bounded operator jobs" "SQLAlchemy/asyncpg"
            migrator -> database "Applies schema and runtime grants" "Alembic/asyncpg"
            api -> storage "Quarantines, promotes and streams authorised product files"
            worker -> storage "Removes expired quarantine objects"
            maintenance -> storage "Applies product retention when instructed"
        }

        camunda = softwareSystem "Camunda 8.9 Orchestration Cluster" "Owns BPMN process position and human user-task lifecycle." "WorkflowSystem" {
            orchestration = container "Orchestration Cluster API" "Executes the BPMN contract and exposes the supported V2 API and content-free health." "Camunda 8.9.14" "ExternalRuntime"
            camundaPrimary = container "Camunda primary state" "Camunda-owned local primary/runtime state. Mist application code never reads it." "Camunda named volumes" "Database,CamundaData"
            camundaSecondary = container "Camunda secondary storage" "Separately owned PostgreSQL database used only by Camunda secondary storage." "PostgreSQL 17" "Database,CamundaData"

            orchestration -> camundaPrimary "Owns primary process state"
            orchestration -> camundaSecondary "Maintains secondary storage" "JDBC"
        }

        scanner = softwareSystem "Malware scanning service" "Fails product promotion closed when complete quarantined objects cannot be scanned." "SecuritySystem" {
            clamav = container "ClamAV scanner" "Accepts INSTREAM scans on an isolated internal network." "ClamAV 1.5.3" "ExternalRuntime,Security"
            clamUpdater = container "Signature updater" "Refreshes a shared signature volume through the only scanner egress network." "freshclam" "ExternalRuntime,Security"
            clamUpdater -> clamav "Publishes read-only signatures through a shared volume"
        }
        signatureSource = softwareSystem "ClamAV signature service" "Public upstream signature distribution." "ExternalDependency"

        customerUses = customer -> web "Uses in Customer context"
        operationalUser -> web "Uses in Staff context"
        jiocUses = jiocUser -> web "Uses in Staff context"
        coordinationUses = coordinationUser -> web "Uses in Staff context"
        opsUses = opsUser -> web "Uses in Staff context"
        managerUses = teamManager -> web "Uses in Staff context"
        analystUses = teamAnalyst -> web "Uses in Staff context"
        qcUserUses = qcUser -> web "Uses in Staff context"
        qcManagerUses = qcManager -> web "Uses in Staff context"
        administrator -> web "Uses metadata administration without implicit content access"
        operator -> api "Observes content-free health"
        operator -> maintenance "Runs controlled operations"
        apiWorkflow = api -> camunda "Queries supported workflow state" "V2 API"
        workerWorkflow = worker -> camunda "Starts processes and completes or reconciles human tasks" "V2 API"
        api -> orchestration "Uses the supported V2 API"
        worker -> orchestration "Uses the supported V2 API"
        apiScanner = api -> scanner "Scans complete quarantined objects" "INSTREAM"
        api -> clamav "Streams quarantined objects" "INSTREAM"
        scannerSignatures = scanner -> signatureSource "Obtains malware signatures through the dedicated updater" "HTTPS"
        clamUpdater -> signatureSource "Downloads signature updates" "HTTPS"

        jioc = element "JIOC" "Root routing workspace" "The sealed request configuration starts every route here." "OrganisationUnit,RootUnit,SelectedRoute"
        digoc = element "DIGOC" "Command workspace" "A staffed, selectable direct child of JIOC." "OrganisationUnit,CommandUnit,SelectedRoute"
        sygoc = element "SYGOC" "Command workspace" "A staffed, selectable direct child of JIOC." "OrganisationUnit,CommandUnit"
        mygoc = element "MYGOC" "Command workspace" "A staffed, selectable direct child of JIOC." "OrganisationUnit,CommandUnit"
        ncgiOps = element "NCGI-A Ops" "Ops workspace" "A staffed, selectable direct child of DIGOC." "OrganisationUnit,OpsUnit,SelectedRoute"
        auroraOps = element "Aurora Ops" "Ops workspace" "A staffed, selectable direct child of DIGOC." "OrganisationUnit,OpsUnit"
        vertexOps = element "Vertex Ops" "Ops workspace" "A staffed, selectable direct child of DIGOC." "OrganisationUnit,OpsUnit"
        osgTeam = element "OSG Team" "Delivery-team workspace" "A staffed, selectable direct child of NCGI-A Ops." "OrganisationUnit,TeamUnit,SelectedRoute"
        cedarTeam = element "Cedar Team" "Delivery-team workspace" "A staffed, selectable direct child of NCGI-A Ops." "OrganisationUnit,TeamUnit"
        quartzTeam = element "Quartz Team" "Delivery-team workspace" "A staffed, selectable direct child of NCGI-A Ops." "OrganisationUnit,TeamUnit"

        jioc -> digoc "Offers as a direct selectable child"
        jioc -> sygoc "Offers as a direct selectable child"
        jioc -> mygoc "Offers as a direct selectable child"
        digoc -> ncgiOps "Offers as a direct selectable child"
        digoc -> auroraOps "Offers as a direct selectable child"
        digoc -> vertexOps "Offers as a direct selectable child"
        ncgiOps -> osgTeam "Offers as a direct selectable child"
        ncgiOps -> cedarTeam "Offers as a direct selectable child"
        ncgiOps -> quartzTeam "Offers as a direct selectable child"

        deploymentEnvironment "Local synthetic evaluation" {
            deploymentNode "Developer workstation" "Loopback-published Docker Compose host on Windows, macOS or Linux" "Docker Compose" {
                deploymentNode "Application runtimes" "Read-only containers with dropped capabilities" "Docker" {
                    containerInstance web
                    containerInstance api
                    containerInstance worker
                    containerInstance migrator
                }
                deploymentNode "Application state" "Private data network and named volumes" "Docker" {
                    containerInstance database
                    containerInstance storage
                    containerInstance camundaSecondary
                }
                deploymentNode "Workflow runtime" "Internal workflow network; V2 API and health published on loopback" "Docker" {
                    containerInstance orchestration
                    containerInstance camundaPrimary
                }
                deploymentNode "Scanner runtime" "Separate scan and signature-update networks" "Docker" {
                    containerInstance clamav
                    containerInstance clamUpdater
                }
                infrastructureNode "One-shot volume initialisers" "Root only for ownership setup, no network, then exit." "Docker Compose services"
            }
        }

        deploymentEnvironment "Private cloud synthetic evaluation" {
            deploymentNode "Private Linux VM" "No public application listener; operator tunnel required" "EC2 or Compute Engine" {
                deploymentNode "Docker Compose" "The synthetic topology is unchanged" "Docker" {
                    containerInstance web
                    containerInstance api
                    containerInstance worker
                    containerInstance migrator
                    containerInstance database
                    containerInstance storage
                    containerInstance orchestration
                    containerInstance camundaPrimary
                    containerInstance camundaSecondary
                    containerInstance clamav
                    containerInstance clamUpdater
                }
            }
        }
    }

    views {
        systemContext mist "SystemContext" "People and external systems around the current service." {
            include customer operationalUser administrator operator mist camunda scanner signatureSource
            autolayout lr 240 140
            title "Mist Service system context"
        }

        container mist "Containers" "Executable Mist runtimes and supported external interfaces." {
            include web api worker maintenance migrator database storage camunda scanner
            autolayout lr 260 160
            title "Mist Service runtime containers"
        }

        component web "WebComponents" "Browser presentation, identity-context and API-state boundaries." {
            include *
            autolayout lr 240 140
            title "Web application components"
        }

        component api "ApiComponents" "HTTP composition around capability services, focused ports and infrastructure adapters." {
            include *
            autolayout lr 240 140
            title "Application API components"
        }

        component worker "WorkerComponents" "Fenced workflow, projection, security and product maintenance jobs." {
            include *
            autolayout lr 240 140
            title "Fenced worker components"
        }

        dynamic mist "RoutingWorkflow" "Customer submission through exact-child organisation routing and team assignment." {
            customerUses "Submits a complete request"
            webApi "Validates and submits"
            apiDatabase "Commits content, configuration pin, audit event and start intent"
            workerWorkflow "Starts the pinned process definition"
            jiocUses "Claims intake and selects one direct command"
            coordinationUses "Claims coordination and selects one direct Ops group"
            opsUses "Claims Ops routing and selects one direct team"
            managerUses "Claims team assignment and names one Lead plus Contributors"
            workerWorkflow "Dispatches each committed human decision and reconciles the projection"
            autolayout tb
            title "Request submission and organisation routing"
        }

        dynamic mist "DeliveryWorkflow" "Assigned production through independent review, dissemination and Customer acceptance." {
            managerUses "Assigns one accountable Lead and optional Contributors"
            analystUses "Produces an immutable package and may request Customer information"
            webApi "Submits authorised product actions"
            apiScanner "Scans complete quarantined files before promotion"
            apiDatabase "Records product metadata, decision evidence and durable workflow intent"
            managerUses "A Team Manager reviews the submitted package"
            qcUserUses "A QC User or QC Manager performs independent review"
            qcManagerUses "A different eligible QC Manager disseminates the approved package"
            workerWorkflow "Completes the proven human tasks through the V2 API"
            customerUses "Downloads the released package, accepts delivery and may give feedback"
            autolayout tb
            title "Product production, review and dissemination"
        }

        dynamic mist "DurableWorkflowCommand" "Application command hand-off between PostgreSQL and Camunda without a distributed transaction." {
            webApi "Sends an authenticated, CSRF-protected action with expected version"
            apiDatabase "Authorises and commits durable intent, audit context, owner and generation"
            workerDatabase "Claims a fenced lease and closes the transaction"
            workerWorkflow "Calls Camunda with no SQL transaction or row lock held"
            workerWorkflow "Queries the exact task or process after conflict, timeout or lag"
            workerDatabase "Reauthorises, compares the fence and commits the proven projection"
            autolayout lr
            title "Durable workflow command and reconciliation"
        }

        custom "OrganisationRouting" "Configured organisation route" "Representative direct-child hierarchy. Every sibling shown is staffed and selectable." {
            include *
            autolayout tb 180 100
        }

        container scanner "ScannerSupplyChain" "Fail-closed scanning, read-only signature hand-off and the only scanner egress boundary." {
            include clamav clamUpdater mist signatureSource
            autolayout lr 220 140
        }

        deployment * "Local synthetic evaluation" "LocalDeployment" "Executable Docker Compose topology." {
            include *
            autolayout lr 240 140
            title "Local synthetic evaluation deployment"
        }

        deployment * "Private cloud synthetic evaluation" "PrivateCloudDeployment" "Unchanged synthetic Compose topology on one private VM." {
            include *
            autolayout lr 240 140
            title "Private cloud synthetic evaluation deployment"
        }

        styles {
            element "Person" {
                shape Person
                background "#0f1b24"
                color "#f4f8fb"
                stroke "#36c7ff"
                metadata false
                description false
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
                metadata false
            }
            element "Component" {
                background "#15222b"
                color "#f4f8fb"
                stroke "#7aa8be"
                metadata false
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
            element "WorkflowSystem" {
                background "#1a2032"
                color "#f4f8fb"
                stroke "#8f88dc"
            }
            element "SecuritySystem" {
                background "#201c17"
                color "#f4f8fb"
                stroke "#d5a449"
            }
            element "Maintenance" {
                background "#17231f"
                color "#f4f8fb"
                stroke "#43c98b"
            }
            element "OrganisationUnit" {
                shape RoundedBox
                background "#101e28"
                color "#f4f8fb"
                stroke "#526d7d"
            }
            element "SelectedRoute" {
                background "#102d3c"
                color "#f4f8fb"
                stroke "#36c7ff"
                strokeWidth 3
            }
            relationship "Relationship" {
                color "#5aaed1"
                thickness 2
            }
        }

        terminology {
            person "Person"
            softwareSystem "Software system"
            container "Runtime container"
            component "Component"
            deploymentNode "Deployment node"
            relationship "Relationship"
        }
    }
}

workspace "ISTARI Service" "Current executable architecture for the synthetic service-request application" {
    model {
        customer = person "Customer" "Submits requests, responds to questions, downloads products and gives feedback."
        routing = person "Routing user" "Routes requests through CRIOC, a command and an Ops group."
        delivery = person "Delivery user" "Assigns, produces, checks and releases service products."
        administrator = person "Platform administrator" "Maintains safe identity and configuration metadata."
        operator = person "Runtime operator" "Deploys, observes, backs up and restores the service."

        istari = softwareSystem "ISTARI Service" "Human-led request, delivery and dissemination workspace." {
            web = container "Web application" "Accessible forms, dashboards and workspaces." "React 19, TypeScript, Vite, Nginx"
            api = container "Application API" "Validates, authorises and records every application action." "Python 3.12+, FastAPI, SQLAlchemy"
            worker = container "Fenced worker" "Dispatches durable workflow commands and reconciles read models." "Python 3.12+"
            database = container "Application database" "Requests, people, assignments, products, audit and projections." "PostgreSQL 17, pgvector" "Database"
            storage = container "Private product storage" "Quarantines and stores approved product files." "Local adapter for synthetic evaluation" "File System"
            scanner = container "Malware scanner" "Scans quarantined uploads before promotion." "ClamAV 1.5" "Container"

            web -> api "Uses same-origin JSON API" "HTTPS target / HTTP loopback locally"
            api -> database "Reads and writes application records" "SQL/TLS target"
            worker -> database "Claims durable work and reconciles projections" "SQL/TLS target"
            api -> storage "Quarantines, promotes and streams product files"
            api -> scanner "Scans complete quarantined objects" "INSTREAM"
        }

        camunda = softwareSystem "Camunda 8.9" "Owns BPMN process position and human user-task lifecycle."
        camundaDatabase = softwareSystem "Camunda database" "Camunda-owned secondary storage; never accessed by application code."

        customer -> istari.web "Uses"
        routing -> istari.web "Uses"
        delivery -> istari.web "Uses"
        administrator -> istari.web "Uses"
        operator -> istari.api "Observes and operates"
        istari.api -> camunda "Queries supported workflow state" "V2 API"
        istari.worker -> camunda "Starts processes and completes human tasks" "V2 API"
        camunda -> camundaDatabase "Owns"
    }

    views {
        systemContext istari "SystemContext" {
            include *
            autolayout lr
            title "ISTARI Service system context"
            description "People and systems around ISTARI Service."
        }

        container istari "Containers" {
            include *
            autolayout lr
            title "ISTARI Service containers"
            description "Executable containers and their supported interfaces."
        }

        styles {
            element "Person" { shape Person background "#0f1b24" color "#f4f8fb" stroke "#36c7ff" }
            element "Software System" { background "#102a3b" color "#f4f8fb" stroke "#36c7ff" }
            element "Container" { background "#101e28" color "#f4f8fb" stroke "#36718d" }
            element "Database" { shape Cylinder background "#14261f" color "#f4f8fb" stroke "#43c98b" }
            element "File System" { shape Folder background "#201c17" color "#f4f8fb" stroke "#d5a449" }
            relationship "Relationship" { color "#6bbbdc" thickness 2 }
        }

        theme default
    }
}

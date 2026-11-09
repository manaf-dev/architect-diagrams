# Icon sources by vendor

Always confirm a reference with `icons.py search` / `icons.py show` before using it. Titles below are
examples of the naming style, not a promise that a given title exists.

| Platform | Use | Notes |
|---|---|---|
| **AWS** | `stencil:aws4/<Title>` | draw.io's official AWS Architecture Icons. Service icons are coloured squares (`resourceIcon`), e.g. `Lambda`, `API Gateway`, `DynamoDB`, `EventBridge`, `Simple Storage Service (S3)`, `Data Firehose`. Resource-level variants exist too (`Lambda Function`). Native stencils → PNG via render.py. Boundary colour `#232F3E`. |
| **Azure** | `drawio:azure2/<category>/<Name>.svg` | 704 official Azure icons as SVG, e.g. `azure2/compute/Function_Apps.svg`, `azure2/databases/SQL_Database.svg`, `azure2/networking/Front_Doors.svg`. File names lag behind renames: Entra ID is `azure2/other/Entra_Identity.svg` (current artwork) while `identity/Azure_Active_Directory.svg` is the old AAD icon, and some icons sit in two categories (App Services). `lib:azure-core#<Title>` uses current names ("Entra ID", "Azure Front Door"). Compare with `icons.py preview`. Boundary colour `#0078D4`. |
| **Microsoft (older set)** | `drawio:mscae/<Name>.svg` | Microsoft Cloud & Enterprise symbols, incl. `Kubernetes.svg`, DevOps/Office items. |
| **Google Cloud** | `stencil:gcp2/<Product>` | Product icons such as `Cloud Run`, `BigQuery`, `Pub/Sub`, `Cloud Storage` come as embedded SVG (search marks them "embedded SVG" — prefer those). Some entries are cards/native shapes. Boundary colour `#4285F4`. |
| **Kubernetes** | `stencil:kubernetes/<Title>` | Titles are the official abbreviations: `Pod`, `Deploy`, `SVC`, `ING`, `STS`, `DS`, `CronJob`, `PVC`, `CM`, `Secret`, `HPA`, `NS`, `Node`, `Control Plane`… (native; labelled variants exist via `@2`). Search by full name works too (`icons.py search ingress`). |
| **Microsoft Fabric / Power BI** | `lib:fabric-core#…`, `lib:fabric-artifacts#…`, `lib:fabric-datasources#…` | Community pack (github.com/astrzala/FabricToolset, MIT): `Fabric`, `One Lake`, `Lakehouse`, `Notebook`, `Pipeline`, `Semantic Model`, `Power BI Report`, `Data Warehouse`, `Eventstream`, `Users`… Credit it. |
| **Azure DevOps / Microsoft platforms** | `lib:azure-devops#…`, `lib:microsoft-platforms#…` | Same community pack. |
| **IBM, SAP, Active Directory, Atlassian, Dynamics 365** | `drawio:ibm/…`, `drawio:sap/…`, `drawio:active_directory/…`, `drawio:atlassian/…`, `drawio:dynamics365/…` | draw.io's bundled SVG sets. |
| **SaaS / OSS logos** (GitHub, Snowflake, Databricks, dbt, Kafka, Postgres, Terraform…) | `simpleicons:<slug>` (append `#RRGGBB` to recolour) | Simple Icons catalog (3,296 brands, searchable: `icons.py search kafka --set simpleicons`), drawn in each brand's colour. CC0 icons; brands' trademark rules still apply — use logos only to identify the product. |
| **Official vendor asset packs** | `svg:<path>` | If the user has downloaded AWS/Azure/GCP official icon zips, reference the SVGs directly — they then render in the SVG output too. |
| **Your organisation's icons** | `lib:<path-or-url>` or `svg:<path>` | Any draw.io library (`.xml` with `<mxlibrary>`) or folder of SVGs. Add aliases under `iconLibraries:` in the spec. |

## Licensing notes

AWS, Microsoft and Google publish their architecture icons for use in architecture diagrams; keep them
unmodified (no recolouring/stretching) and don't imply endorsement. Community packs (like the Fabric pack)
carry their own licence — keep the credit line. Brand logos identify products; don't use them decoratively.

## When an icon doesn't exist

Use a `box` with a clear name and type line (e.g. "Order service · Go on ECS"). A neutral box is always
better than a misleading icon. For a vendor service missing from the catalogs, check whether the catalogs
are stale (`icons.py build-catalogs`) before falling back.

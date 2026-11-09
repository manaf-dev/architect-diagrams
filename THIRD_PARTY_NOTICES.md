# Third-party notices

The skill's instructions and scripts are MIT-licensed (see `LICENSE`). The icon data it bundles or
downloads comes from the projects below and keeps their own licences and terms.

| Component | Where it's used | Source | Licence / terms |
|---|---|---|---|
| draw.io stencil catalogs (`aws4.json`, `gcp2.json`, `kubernetes.json`, `drawio-images.json`) | Icon names, draw.io style strings, embedded GCP product SVGs and the index of draw.io SVG icons | [jgraph/drawio](https://github.com/jgraph/drawio). Parsed statically from its sidebar sources by `icons.py build-catalogs` | Apache License 2.0 (draw.io). The icons depict third-party products and are subject to their owners' terms below |
| AWS Architecture Icons | `stencil:aws4/...` | Amazon Web Services, via draw.io | [AWS Architecture Icons terms](https://aws.amazon.com/architecture/icons/). For architecture diagrams; don't modify them or imply endorsement |
| Microsoft Azure icons | `drawio:azure2/...`, `drawio:mscae/...` | Microsoft, via draw.io | [Azure icon terms](https://learn.microsoft.com/azure/architecture/icons/). For architecture diagrams; don't modify them or imply endorsement |
| Google Cloud icons | `stencil:gcp2/...` | Google, via draw.io | [Google Cloud icon terms](https://cloud.google.com/icons). For architecture diagrams |
| Kubernetes icons | `stencil:kubernetes/...` | kubernetes/community icon set, via draw.io | Apache License 2.0 |
| Simple Icons (`simpleicons.json` index + SVGs fetched at runtime) | `simpleicons:<slug>` | [simple-icons](https://github.com/simple-icons/simple-icons) | CC0 1.0 for the icon data. Brand marks remain their owners' trademarks; use them only to identify the product |
| Microsoft Fabric & Azure Icon Pack (fetched at runtime, not bundled) | `lib:fabric-*`, `lib:azure-core`, `lib:azure-devops`, `lib:microsoft-platforms` | [astrzala/FabricToolset](https://github.com/astrzala/FabricToolset) | MIT. Credit the pack in diagrams that use it |
| draw.io viewer script (fetched at render time, not bundled) | `render.py` viewer engine | viewer.diagrams.net | Apache License 2.0 |

Trademarks belong to their respective owners. This project is not affiliated with, or endorsed by, any of
the vendors above.

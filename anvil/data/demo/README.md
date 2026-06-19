# Demo Data

This directory contains bundled demo data for the anvil training workbench. It's
organized by size (small, medium, large) with subdirectories (ingested as
corpora) and standalone `.txt` files (ingested as datasets).

## Contents

| Path | Type | Domain | Source | License |
|------|------|--------|--------|---------|
| small/names/ | Corpus | Names | Public name lists | Permissive / MIT |
| small/hello-world/ | Corpus | Code | Hand-crafted | Generated |
| small/presidents.txt | Dataset | Records | US State of the Union (Gutenberg #5010) | Public Domain |
| medium/alice/ | Corpus | Prose | Alice in Wonderland (Gutenberg #11) | Public Domain |
| medium/math-facts.txt | Dataset | Structure | Hand-crafted | Generated |
| large/earnest/ | Corpus | Prose | Importance of Being Earnest (Gutenberg #844) | Public Domain |

## Import

Run ``anvil bootstrap-datasets`` to import all demo data into the database.
This is also done automatically during ``make setup`` and on app startup.
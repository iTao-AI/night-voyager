#!/bin/sh
set -eu

# Role creation is completed with the M2 database catalog gate. Keeping this
# path explicit lets Compose mount one reviewed initialization entrypoint.

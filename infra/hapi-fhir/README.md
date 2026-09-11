# HAPI FHIR configuration

The `hapi-fhir` compose service runs the stock `hapiproject/hapi` image,
configured entirely through environment variables in `docker-compose.yml`
(Postgres datasource, `HAPI_FHIR_FHIR_VERSION=R4`). No custom image or
`application.yaml` is required for the default setup.

Drop a custom `application.yaml` in this directory and mount it into the
container (`/app/config/application.yaml`) if a future step needs settings
beyond what environment variables cover — e.g. custom search parameters,
subscriptions, or CORS rules for direct browser access to `/fhir`.

See [`docs/fhir-mapping.md`](../../docs/fhir-mapping.md) for the resource
mapping this server backs.

# deploy/

Deployment assets: `Dockerfile`, database init scripts (`db_setup/`), k8s/ansible manifests.

`docker-compose.yml` intentionally stays at the repository root: Docker Compose resolves
`${VAR}` interpolation against the `.env` in the *project directory*, which defaults to the
directory holding the compose file. Moving it here would silently break every
`${APP_PASSWORD}`-style reference.

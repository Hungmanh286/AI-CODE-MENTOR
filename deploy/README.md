# deploy/

Deployment assets: `Dockerfile`, database init scripts (`db_setup/`), k8s/ansible manifests.

`docker-compose.yml` intentionally stays at the repository root: Docker Compose resolves
`${VAR}` interpolation against the `.env` in the *project directory*, which defaults to the
directory holding the compose file. Moving it here would silently break every
`${APP_PASSWORD}`-style reference.

## nginx

`nginx/mentor-agui.conf` is the reverse-proxy block for the backend. The important part is
`location = /agent`: `proxy_buffering off` and a long `proxy_read_timeout`, otherwise the
AG-UI stream is buffered and the chat text appears all at once.

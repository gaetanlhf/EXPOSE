<h1 align="center">
    <a href="https://expose.sh/#gh-light-mode-only">
    <img src="./.github/assets/expose_logo_black.svg">
    </a>
    <a href="https://expose.sh/#gh-dark-mode-only">
    <img src="./.github/assets/expose_logo_white.svg">
    </a>
</h1>

<p align="center">
    <a href="#about">About</a> •
    <a href="#demo">Demo</a> •
    <a href="#features">Features</a> •
    <a href="#use-cases">Use-cases</a> •
    <a href="#access">Access</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#deployment">Deployment</a> •
    <a href="#faqs">FAQs</a>
</p>

## About

EXPOSE is your new favourite open source tool for exposing your local services on the public Internet with no installation or configuration required. EXPOSE relies on your SSH client and authenticates using the public SSH keys you have on your GitHub account.

To expose `localhost:3000`, simply type:
```bash
ssh -R 1:localhost:3000 expose.sh
```

If your computer username differs from your GitHub username:
```bash
ssh -R 1:localhost:3000 yourusername@expose.sh
```

## Demo

https://github.com/user-attachments/assets/9908b156-6e12-4a6e-8cf7-46b701f48461

## Features

- **Nothing to install**: use only your terminal and SSH client
- **Nothing to configure**: automatically retrieve public SSH keys from your GitHub account
- **Custom URL**: based on your GitHub username
- **Multiple protocols**: HTTP, HTTPS & WebSocket supported
- **QR code generation**: for easy mobile testing
- **Multiple tunnels**: up to 5 simultaneous services per account
- **Distributed system**: global routing for fastest access worldwide
- **Secure**: SSH encryption with automatic HTTPS certificates
- **Open source**: fully transparent and community-driven

## Use-cases

- **Demos and presentations**: access your applications from any internet-connected device
- **Mobile development**: expose local backends for Android/iOS app testing
- **Webhook testing**: test webhooks from payment gateways, messaging platforms, and APIs
- **Home server exposure**: make your Raspberry Pi or local server publicly accessible
- **Cross-device testing**: ensure your application works on all device types
- **Development sharing**: quickly share work-in-progress with team members

## Access

To prevent malicious use, you must star this repository to access EXPOSE. Authentication is handled through your GitHub SSH keys.

**Tunnel allocation:**
- Tunnels 1-3: Named as `username`, `username-2`, `username-3`, etc.
- Tunnels 4-5: Random names like `username-x7k2m9`
- Maximum: 5 concurrent tunnels per user
- Session limit: 2 hours (reconnectable unlimited times)

## Architecture

EXPOSE consists of three containerized components deployed globally using [Fly.io](https://fly.io):

### SSH Server (Python)
- Handles SSH connections and authentication
- Validates GitHub SSH keys and stargazer status
- Manages tunnel creation with slot-based naming
- Enforces connection limits and timeouts
- Creates Unix socket forwarding for local services

### Tools Service (Node.js)
- Acts as intermediary between SSH server and web server
- Manages GitHub API integration with caching
- Generates QR codes for tunnel URLs
- Handles cache management across distributed instances
- Serves local banner content

### Web Server (OpenResty/Nginx)
- Routes traffic to appropriate tunnels based on subdomains
- Handles caching and load balancing
- Provides HTTPS termination with automatic certificates
- Manages WebSocket upgrades

## Deployment

### Prerequisites

Generate an SSH key pair:
```bash
ssh-keygen -t ed25519 -f ./ssh_key -N ""
```

### Configuration

1. Copy the example configuration:
```bash
cp fly.toml.example fly.toml
```

2. Update the required configuration fields:
```toml
app = 'your-app-name'
primary_region = 'cdg'  # Choose your preferred region

[env]
  FLYDOTIO_APP_NAME = 'your-app-name'
  HTTP_URL = 'yourdomain.com'
  SSH_SERVER_URL = 'ssh.yourdomain.com'
  GITHUB_REPOSITORY = 'gaetanlhf/EXPOSE'
```

3. Configure optional settings:
   - Adjust `NAMED_TUNNELS_RANGE` and `RANDOM_TUNNELS_RANGE` for tunnel allocation
   - Set `TIMEOUT` for session duration (in minutes)
   - Modify `LOG_LEVEL` for debugging (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Deploy to Fly.io

1. Launch the application:
```bash
fly launch
```

2. Add the SSH private key secret:
```bash
fly secrets set SSH_SERVER_KEY="$(cat ssh_key)"
```

3. Configure DNS to point your domains to Fly.io's IPv4 and IPv6 addresses

4. Add HTTPS certificates in the Fly.io dashboard for your domains

### Local Development

1. Build the container:
```bash
docker build -t expose .
```

3. Run with required environment variables:
```bash
docker run -p 2222:2222 -p 80:80 \
  -e FLYDOTIO_APP_NAME=expose-local \
  -e HTTP_URL=localhost \
  -e SSH_SERVER_URL=localhost \
  -e GITHUB_REPOSITORY=gaetanlhf/EXPOSE \
  -e SSH_SERVER_KEY="$(cat ssh_key)" \
  expose
```

## Configuration Variables

### Required Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `app` | Fly.io application name | `my-expose-server` |
| `primary_region` | Fly.io deployment region | `cdg`, `lax`, `fra` |
| `FLYDOTIO_APP_NAME` | Must match the app name | `my-expose-server` |
| `HTTP_URL` | Domain for tunnel URLs | `expos.es` |
| `SSH_SERVER_URL` | SSH connection endpoint | `expose.sh` |
| `GITHUB_REPOSITORY` | Repository to check for stargazers | `gaetanlhf/EXPOSE` |

### Optional Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `NAMED_TUNNELS_RANGE` | `1-5` | Slots for username-based naming |
| `RANDOM_TUNNELS_RANGE` | `6-10` | Slots for random naming |
| `TIMEOUT` | `120` | Session timeout in minutes |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `SSH_SERVER_PORT` | `2222` | Internal SSH server port |
| `NODEJS_TOOLS_PORT` | `3000` | Internal tools service port |

## Usage Examples

Single tunnel:
```bash
ssh -R 1:localhost:3000 expose.sh
```

Multiple tunnels:
```bash
ssh -R 1:localhost:3000 -R 2:localhost:8080 expose.sh
```

Auto-reconnect:
```bash
until ssh -R 1:localhost:3000 expose.sh; do echo "Reconnecting..."; done
```

## FAQs

<details>
<summary>Is EXPOSE secure?</summary>
Yes, SSH is an encrypted protocol, and access to your application is secure thanks to automatic HTTPS certificates.
</details>

<details>
<summary>What do you mean by no installation and no configuration?</summary>
<strong>No installation</strong> because EXPOSE uses your existing SSH client. <strong>No configuration</strong> because EXPOSE automatically retrieves data from your SSH client and GitHub account.
</details>

<details>
<summary>How many tunnels can I create simultaneously?</summary>
You can create up to 10 simultaneous tunnels. Slots 1-5 use your username, slots 6-10 use random names.
</details>

<details>
<summary>What's the session time limit?</summary>
Each session lasts up to 2 hours, but you can reconnect unlimited times.
</details>

<details>
<summary>I see "Cannot connect to your local application" in the browser</summary>
Ensure your local application is running and accessible at `http://localhost:port`.
</details>

<details>
<summary>I see "connect_to localhost port failed" in terminal</summary>
Verify your local service is running on the specified port by testing `http://localhost:port` in your browser.
</details>

<details>
<summary>Does EXPOSE support other protocols?</summary>
EXPOSE supports HTTP, HTTPS, and WebSocket protocols through its web-based tunneling.
</details>

<details>
<summary>Where can I get help?</summary>
Open an issue on this repository or send an email to <a href="mailto:gaetan@expose.sh">gaetan@expose.sh</a>.
</details>

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see http://www.gnu.org/licenses/.

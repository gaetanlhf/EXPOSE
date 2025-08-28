import asyncio
import logging
import os
import sys
import time
from asyncio import AbstractEventLoop
from os import path
from types import FrameType
from typing import AnyStr, Optional, Tuple
from _asyncio import Task

import asyncssh
from asyncssh import SSHServerConnection
from asyncssh.channel import (
    SSHUNIXChannel,
    SSHUNIXSession,
    SSHUNIXSessionFactory,
)
from asyncssh.listener import create_unix_forward_listener
from loguru import logger
from loguru._handler import Handler
import requests
import socket

access_token: str = os.getenv("ACCESS_TOKEN", "")
unix_sockets_dir: str = os.getenv("UNIX_SOCKETS_DIRECTORY", "./")
main_url: str = os.getenv("MAIN_URL", "")
http_url: str = os.getenv("HTTP_URL", "")
ssh_server_url: str = os.getenv("SSH_SERVER_URL", "")
config_dir: str = os.getenv("CONFIG_DIRECTORY", ".")
timeout: int = int(os.getenv("TIMEOUT", "120"))
named_tunnels_range: str = os.getenv("NAMED_TUNNELS_RANGE", "1-3")
random_tunnels_range: str = os.getenv("RANDOM_TUNNELS_RANGE", "4-5")
ssh_server_host: str = os.getenv("SSH_SERVER_HOST", "0.0.0.0")
ssh_server_port: int = int(os.getenv("SSH_SERVER_PORT", "2222"))
ssh_server_key: str = os.getenv("SSH_SERVER_KEY", "")
log_level: str = os.getenv("LOG_LEVEL", "INFO")
log_depth: int = int(os.getenv("LOG_DEPTH", "2"))

key_matches_account_url: str = os.getenv("KEY_MATCHES_ACCOUNT_URL", "http://localhost:3000/keyMatchesAccount")
is_user_stargazer_url: str = os.getenv("IS_USER_STARGAZER_URL", "http://localhost:3000/isUserStargazer")
generate_qrcode_url: str = os.getenv("GENERATE_QRCODE_URL", "http://localhost:3000/generateQRCode")
banner_url: str = os.getenv("BANNER_URL", "http://localhost:3000/getBanner")
cache_add_url: str = os.getenv("CACHE_ADD_URL", "http://localhost:3000/addToNginxCache")
cache_remove_url: str = os.getenv("CACHE_REMOVE_URL", "http://localhost:3000/removeFromNginxCache")
check_if_tunnel_exists_url: str = os.getenv("CHECK_IF_TUNNEL_EXISTS", "http://localhost:3000/checkIfTunnelExists")


def get_ipv6_address(hostname: str) -> Optional[str]:
    try:
        result = socket.getaddrinfo(hostname, None, socket.AF_INET6)
        ipv6_address = result[0][4][0]
        return ipv6_address
    except (socket.gaierror, IndexError) as e:
        print(f"Error retrieving IPv6 address for {hostname}: {e}")
        return None


container_ip = get_ipv6_address("fly-local-6pn")


def parse_range(range_str: str) -> tuple:
    try:
        start, end = map(int, range_str.split('-'))
        return start, end
    except ValueError:
        return 1, 5


def get_max_slot() -> int:
    named_start, named_end = parse_range(named_tunnels_range)
    random_start, random_end = parse_range(random_tunnels_range)
    return max(named_end, random_end)


def is_slot_in_named_range(slot: int) -> bool:
    start, end = parse_range(named_tunnels_range)
    return start <= slot <= end


def is_slot_in_random_range(slot: int) -> bool:
    start, end = parse_range(random_tunnels_range)
    return start <= slot <= end


def key_matches_account(username: str, key: str) -> tuple:
    try:
        response = requests.get(
            key_matches_account_url, params={"username": username, "key": key}
        )
        if response.status_code == 200:
            data = response.json()
            matches = data.get("matches", False)
            is_stargazer = data.get("isStargazer", False)
            if matches:
                logging.info(f"Key matches account {username}")
                if is_stargazer:
                    logging.info(f"User {username} is a stargazer")
            else:
                logging.error(f"Key does not match account {username}")
            return matches, is_stargazer
        else:
            logging.info(f"User {username} not found or not a stargazer")
            return False, False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking SSH keys for {username}: {e}")
        return False, False


def is_user_stargazer(username: str) -> bool:
    try:
        response = requests.get(
            is_user_stargazer_url, params={"username": username}
        )
        if response.status_code == 200:
            is_stargazer = response.json().get("isStargazer", False)
            if is_stargazer:
                logging.info(f"User {username} is a stargazer")
            else:
                logging.info(f"User {username} is not a stargazer")
            return is_stargazer
        else:
            logging.info(f"User {username} is not a stargazer")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking stargazer status for user {username}: {e}")
        return False


def get_qrcode(url: str) -> str:
    try:
        data = requests.get(generate_qrcode_url, params={"url": url})
        qrcode = data.json().get("qrCodeText", "")
        return qrcode
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating QR Code for {url}: {e}")
        return ""


def add_to_cache(socket_name: str, ipv6_address: str) -> bool:
    try:
        response = requests.get(
            cache_add_url,
            params={"app_name": socket_name, "ipv6": ipv6_address},
            timeout=10,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error adding to nginx cache: {e}")
        return False


def remove_from_cache(socket_name: str) -> bool:
    try:
        response = requests.get(
            cache_remove_url, params={"app_name": socket_name}, timeout=10
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error removing from nginx cache: {e}")
        return False


def check_if_tunnel_exists(socket_name: str) -> bool:
    try:
        response = requests.get(
            check_if_tunnel_exists_url, params={"app_name": socket_name}, timeout=10
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking if tunnel exists: {e}")
        return False


def get_banner(banner_type: str) -> str:
    try:
        data = requests.get(banner_url, params={"type": banner_type})
        banner = data.json().get("bannerContent", "")
        return banner
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting banner for {banner_type}: {e}")
        return ""


class SSHServer(asyncssh.SSHServer):

    def __init__(self):
        self.conn: SSHServerConnection
        self.ip_addr: str
        self.socket_paths: dict = {}

    def connection_made(self, conn: SSHServerConnection) -> None:
        self.conn = conn
        self.ip_addr, _ = conn.get_extra_info("peername")

    def public_key_auth_supported(self):
        return True

    async def validate_public_key(self, username, key):
        try:
            for key_line in key.convert_to_public().export_public_key().decode().splitlines():
                is_key_matching, is_stargazer = key_matches_account(username, key_line)
                if is_key_matching:
                    self.conn.set_extra_info(key_matching=is_key_matching)
                    self.conn.set_extra_info(stargazer=is_stargazer)
                    break
            if not self.conn.get_extra_info("key_matching"):
                self.conn.set_extra_info(key_matching=False)
                self.conn.set_extra_info(stargazer=False)
            return True
        except Exception:
            self.conn.set_extra_info(key_matching=False)
            self.conn.set_extra_info(stargazer=False)
            return True

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            logging.info(f"Connection terminated: {str(exc)}")
        try:
            if self.socket_paths:
                for socket_path, socket_name in self.socket_paths.items():
                    if os.path.exists(socket_path):
                        os.remove(socket_path)
                    meta_file = os.path.join(unix_sockets_dir, f"{socket_name}.meta")
                    if os.path.exists(meta_file):
                        os.remove(meta_file)
                    remove_from_cache(socket_name)
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def server_requested(self, listen_host: str, listen_port: int):
        slot = listen_port
        max_slot = get_max_slot()
        if slot < 1 or slot > max_slot:
            self.conn.set_extra_info(invalid_slot=True)
            self.conn.set_extra_info(slot_number=slot)
            return None
            
        socket_name: str = self.conn.get_extra_info("username")
        
        if is_slot_in_named_range(slot):
            final_name = f"{socket_name}-{slot}" if slot > 1 else socket_name
        elif is_slot_in_random_range(slot):
            import random
            import string
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            final_name = f"{socket_name}-{random_suffix}"
        else:
            final_name = f"{socket_name}-{slot}" if slot > 1 else socket_name
        
        if check_if_tunnel_exists(final_name):
            self.conn.set_extra_info(tunnel_exists=True)
            self.conn.set_extra_info(existing_name=final_name)
            return None
        
        rewrite_path = os.path.join(unix_sockets_dir, f"{final_name}.sock")
        self.socket_paths[rewrite_path] = final_name
        
        meta_file = os.path.join(unix_sockets_dir, f"{final_name}.meta")
        open(meta_file, "w").close()
        
        add_to_cache(final_name, container_ip)
        self.conn.set_extra_info(socket_paths=self.socket_paths)

        async def tunnel_connection(
            session_factory: SSHUNIXSessionFactory[AnyStr],
        ) -> Tuple[SSHUNIXChannel[AnyStr], SSHUNIXSession[AnyStr]]:
            return await self.conn.create_connection(session_factory, listen_host, listen_port)

        try:
            return create_unix_forward_listener(
                self.conn, asyncio.get_event_loop(), tunnel_connection, rewrite_path
            )
        except OSError as e:
            logging.error(f"Error creating forward listener: {str(e)}")

    def unix_server_requested(self, listen_path: str):
        self.conn.set_extra_info(unix_socket_rejected=True)
        return None


async def handle_ssh_client(process) -> None:
    socket_paths: dict = process.get_extra_info("socket_paths")
    is_key_matching: bool = process.get_extra_info("key_matching")
    is_stargazer: bool = process.get_extra_info("stargazer")
    username: str = process.get_extra_info("username")
    invalid_slot: bool = process.get_extra_info("invalid_slot", False)
    slot_number: int = process.get_extra_info("slot_number", 0)
    tunnel_exists: bool = process.get_extra_info("tunnel_exists", False)
    existing_name: str = process.get_extra_info("existing_name", "")
    unix_socket_rejected: bool = process.get_extra_info("unix_socket_rejected", False)

    welcome_banner: str = get_banner("welcome")
    process.stdout.write(welcome_banner + "\n\n")

    if not is_key_matching:
        unrecognised_user_banner: str = get_banner("unrecognised_user")
        process.stdout.write(unrecognised_user_banner + "\n")
        process.logger.info("User rejected: SSH key does not match")
        process.exit(1)
        return

    if invalid_slot:
        max_slot = get_max_slot()
        response = f"Invalid slot number: {slot_number}. Please use slots 1-{max_slot} only.\n"
        process.stdout.write(response)
        process.logger.info(f"User rejected: invalid slot {slot_number}")
        process.exit(1)
        return

    if tunnel_exists:
        response = f"Tunnel already exists: {existing_name}. Please use a different slot.\n"
        process.stdout.write(response)
        process.logger.info(f"User rejected: tunnel {existing_name} already exists")
        process.exit(1)
        return

    if unix_socket_rejected or not socket_paths:
        named_start, named_end = parse_range(named_tunnels_range)
        random_start, random_end = parse_range(random_tunnels_range)
        max_slot = get_max_slot()
        timeout_hours = timeout // 60

        import random
        import string
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        
        response = f"""Usage: ssh -R <slot>:localhost:<localport> {ssh_server_url}

Tunnel naming rules:
- Slots {named_start}-{named_end}: Named as {username}, {username}-2, {username}-3, etc.
- Slots {random_start}-{random_end}: Random names like {username}-{random_suffix}
- Maximum: {max_slot} concurrent tunnels per user (slots 1-{max_slot})
- Session limit: {timeout_hours} hours

Only numbered slots are supported. Unix socket forwarding is not allowed.

Examples:
ssh -R 1:localhost:3000 {ssh_server_url}                              Named tunnel: {username}
ssh -R 2:localhost:8080 {ssh_server_url}                              Named tunnel: {username}-2
ssh -R 1:localhost:3000 -R 2:localhost:8080 {ssh_server_url}          Named tunnels: {username}, {username}-2
ssh -R {random_start}:localhost:9000 {ssh_server_url}                 Random tunnel name
"""
        process.stdout.write(response)
        if unix_socket_rejected:
            process.logger.info("User rejected: unix socket forwarding not allowed")
        else:
            process.logger.info("User rejected: not in port forwarding mode")
        process.exit(1)
        return

    async def process_timeout(proc):
        await asyncio.sleep(timeout * 60)
        response = f"\nTimeout: automatically disconnected after {timeout_hours} hours.\n"
        proc.stdout.write(response)
        proc.logger.info(f"User automatically disconnected after {timeout_hours} hours")
        proc.close()

    timeout_hours = timeout // 60
    for socket_path, socket_name in socket_paths.items():
        no_tls: str = f"{socket_name}.{http_url}"
        tls: str = f"https://{socket_name}.{http_url}"
        qrcode: str = get_qrcode(tls)
        
        response = f"Internet address: {no_tls}\nTLS termination: {tls}\n\n{qrcode}\n"
        process.stdout.write(response)
        process.logger.info(f"Exposed on {no_tls}")
    
    timeout_task: Task = asyncio.create_task(process_timeout(process))

    try:
        while not process.stdin.at_eof():
            try:
                await process.stdin.read()
            except asyncssh.TerminalSizeChanged:
                pass
    except Exception:
        pass
    finally:
        timeout_task.cancel()
        process.exit(0)


async def start_ssh_server() -> None:
    await asyncssh.create_server(
        SSHServer,
        host=ssh_server_host,
        port=ssh_server_port,
        server_host_keys=[path.join(config_dir, "id_rsa_host")],
        process_factory=handle_ssh_client,
        agent_forwarding=False,
        allow_scp=False,
        server_version="EXPOSE SSH Server",
        keepalive_interval=30,
    )
    logging.info("SSH server started successfully")


def check_unix_sockets_dir() -> None:
    if not path.exists(unix_sockets_dir):
        os.makedirs(unix_sockets_dir, exist_ok=True)
        logging.warning(f"Directory {unix_sockets_dir} created")
    else:
        logging.info(f"Directory {unix_sockets_dir} exists")


class InterceptHandler(logging.Handler):
    def emit(self, record):
        frame: FrameType = logging.currentframe()
        depth: int = log_depth
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(exception=record.exc_info).log(log_level, record.getMessage())


def init_logging():
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(log_level)
    fmt = "<green>[{time}]</green> <level>[{level}]</level> - <level>{message}</level>"
    logger.configure(handlers=[{"sink": sys.stdout, "serialize": False, "format": fmt}])


def check_if_ssh_key_exists():
    ssh_host_key_path: str = path.join(config_dir, "id_rsa_host")
    if not path.exists(ssh_host_key_path):
        logging.warning("SSH server key created from environment")
        with open(ssh_host_key_path, "w") as f:
            f.write(ssh_server_key)
        os.chmod(ssh_host_key_path, 0o600)
        logging.info("SSH server key created")
    else:
        logging.info("SSH server key exists")


if __name__ == "__main__":
    init_logging()
    logging.info("Starting EXPOSE tunnel SSH server")
    logging.info("Checking SSH server key")
    check_if_ssh_key_exists()
    os.umask(0o000)
    logging.info("Checking UNIX sockets directory")
    check_unix_sockets_dir()
    
    loop: AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_ssh_server())
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except (OSError, asyncssh.Error) as e:
        logging.critical(f"Error starting SSH server: {str(e)}")
        sys.exit(1)
    
    try:
        logging.info(f"SSH server listening on {ssh_server_host}:{ssh_server_port}")
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Server shutdown")
        sys.exit(0)
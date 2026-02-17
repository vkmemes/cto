#!/usr/bin/env python3
"""
Webhook server for auto-deployment from GitHub/GitLab
Run: python webhook_server.py
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import subprocess
from datetime import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from uvicorn import Config, Server

# Configuration
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "9000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PROJECT_DIR = os.getenv("PROJECT_DIR", "/opt/ygk")
DEPLOY_BRANCH = os.getenv("DEPLOY_BRANCH", "main")
DEPLOY_SCRIPT = os.getenv("DEPLOY_SCRIPT", f"{PROJECT_DIR}/deploy.sh")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webhook")


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature"""
    if not secret or not signature:
        return False
    
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


async def run_deployment():
    """Run deployment script"""
    try:
        result = subprocess.run(
            ["bash", DEPLOY_SCRIPT],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=120
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-1000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else ""
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Deployment timed out after 120 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def github_webhook(request: Request):
    """Handle GitHub webhook"""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery", "")
    
    logger.info(f"Received webhook: event={event}, delivery={delivery}")
    
    # Verify signature if secret is configured
    if WEBHOOK_SECRET:
        if not verify_signature(payload, signature, WEBHOOK_SECRET):
            logger.warning("Invalid webhook signature")
            return JSONResponse({"error": "Invalid signature"}, status_code=401)
    
    # Parse payload
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    # Handle ping event
    if event == "ping":
        return JSONResponse({"message": "Pong!", "zen": data.get("zen", "")})
    
    # Handle push event
    if event == "push":
        branch = data.get("ref", "").replace("refs/heads/", "")
        pusher = data.get("pusher", {}).get("name", "unknown")
        commits = len(data.get("commits", []))
        
        logger.info(f"Push by {pusher} to {branch} ({commits} commits)")
        
        if branch != DEPLOY_BRANCH:
            return JSONResponse({
                "message": f"Ignored push to {branch}",
                "expected_branch": DEPLOY_BRANCH
            })
        
        # Run deployment
        logger.info("Starting deployment...")
        result = await run_deployment()
        
        if result["success"]:
            logger.info("Deployment successful")
            return JSONResponse({
                "status": "success",
                "message": "Deployment completed",
                "branch": branch,
                "timestamp": datetime.now().isoformat()
            })
        else:
            logger.error(f"Deployment failed: {result.get('error', 'Unknown error')}")
            return JSONResponse({
                "status": "failed",
                "error": result.get("error", "Deployment failed"),
                "details": result.get("stderr", "")
            }, status_code=500)
    
    return JSONResponse({"message": f"Event {event} received"})


async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok",
        "service": "webhook-server",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    })


async def deploy_trigger(request: Request):
    """Manual deploy trigger (for testing)"""
    logger.info("Manual deployment triggered")
    result = await run_deployment()
    
    return JSONResponse({
        "status": "success" if result["success"] else "failed",
        "result": result,
        "timestamp": datetime.now().isoformat()
    })


# Create app
app = Starlette(
    routes=[
        Route("/webhook/github", github_webhook, methods=["POST"]),
        Route("/health", health_check),
        Route("/deploy", deploy_trigger, methods=["POST"]),
    ]
)


async def main():
    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not set! Webhook is insecure!")
    
    logger.info(f"Starting webhook server on port {WEBHOOK_PORT}")
    logger.info(f"Project directory: {PROJECT_DIR}")
    logger.info(f"Deploy branch: {DEPLOY_BRANCH}")
    
    config = Config(app=app, host="0.0.0.0", port=WEBHOOK_PORT)
    server = Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

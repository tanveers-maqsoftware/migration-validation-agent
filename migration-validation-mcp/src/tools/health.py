from datetime import datetime


def health_check():

    return {
        "status": "healthy",
        "server": "Migration Validation MCP",
        "timestamp": datetime.utcnow().isoformat()
    }